"""Rollout operations on shared state. Used by the worker (jobs), the web API and the command line.

The registry (which environments exist and which blueprint version each is pinned to) and the run
history live in the shared store, not in local files, so the web service and the worker agree.
"""
import os
import re
import time

from spaces import config, store

from . import core
from .engine import ROOT, Engine

NS_REG, NS_RUN, KEY = "rollout_registry", "rollout_run", "registry"
VERSION_RE = re.compile(r"^v?\d+\.\d+\.\d+([-.][0-9A-Za-z.]+)?$")
ENV_FIELDS = ("name", "team", "environment", "size", "admin_groups", "version")


def catalog_dir():
    return config.get("CATALOG_DIR", os.path.join(ROOT, ".local", "rollout", "catalog"))


def registry():
    return store.get(NS_REG, KEY) or {"environments": []}


def save_registry(reg):
    store.put(NS_REG, KEY, reg)


def check_registry(doc):
    """Return (clean_registry, error)."""
    if not isinstance(doc, dict) or not isinstance(doc.get("environments"), list) or not doc["environments"]:
        return None, "registry needs a non-empty 'environments' list"
    names, out = set(), []
    for e in doc["environments"]:
        if not isinstance(e, dict) or any(k not in e for k in ENV_FIELDS):
            return None, f"each environment needs: {', '.join(ENV_FIELDS)}"
        if e["name"] in names:
            return None, f"duplicate environment {e['name']}"
        if not VERSION_RE.match(str(e["version"])):
            return None, f"{e['name']}: version must look like v1.2.3"
        names.add(e["name"])
        out.append({**{k: e[k] for k in ENV_FIELDS}, **({"canary": True} if e.get("canary") else {})})
    return {"environments": out}, None


def pin_one(env):
    """Persist one environment's new pin right after it passes verification."""
    def apply(reg):
        for e in reg["environments"]:
            if e["name"] == env["name"]:
                e["version"] = env["version"]
    store.update(NS_REG, KEY, apply)


def engine():
    return Engine(catalog_dir(), kubeconfig=config.kubeconfig())


def versions():
    """Release tags in the catalog, newest first."""
    import subprocess
    p = subprocess.run(["git", "-C", catalog_dir(), "tag", "--sort=-v:refname"], capture_output=True, text=True)
    return p.stdout.split() if p.returncode == 0 else []


def preview(payload):
    version = payload["version"]
    reg, eng = registry(), engine()
    out = {}
    for e in reg["environments"]:
        if e["version"] != version:
            out[e["name"]] = eng.plan(e, version)
    destroys = {n: [c["address"] for c in p["changes"] if "delete" in c["actions"]] for n, p in out.items() if p["destroy"]}
    return {"ok": True, "version": version, "plans": out, "destroys": destroys}


def rollout(payload):
    reg = registry()
    res = core.run_rollout(engine(), reg["environments"], payload["version"], canary=payload.get("canary") or None,
                           batch_size=int(payload.get("batch", 3)), allow_destroy=bool(payload.get("allow_destroy")),
                           on_pinned=pin_one)
    res["at"] = int(time.time())
    store.put(NS_RUN, f"{res['at']:012d}-{payload['version']}", res)
    return {"ok": res["status"] in ("completed", "nothing_to_do"), **{k: res[k] for k in ("version", "status", "total_seconds")}}


def runs(limit=50):
    return [d for _, d in store.items(NS_RUN, newest_first=True, limit=limit)]
