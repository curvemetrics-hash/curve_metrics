"""Command line for the rollout manager.

  python3 -m rollout demo-registry [N]        write a demo registry of N environments
  python3 -m rollout registry                 print the registry as JSON
  python3 -m rollout registry-import FILE     replace the registry from a JSON file
  python3 -m rollout last-run                 print the newest rollout record as JSON
  python3 -m rollout provision                create every environment at its pinned version
  python3 -m rollout status                   pinned vs actual version and compliance, per environment
  python3 -m rollout preview <version>        show what would change, change nothing
  python3 -m rollout rollout <version> [--canary NAME] [--batch N] [--allow-destroy]
  python3 -m rollout report [--live]          write site/index.html from the registry and past runs
  python3 -m rollout destroy                  tear every environment down (local cleanup)
"""
import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor

from . import service
from .engine import ROOT

BASE = os.path.join(ROOT, ".local", "rollout")


def demo_registry(n):
    teams = ["payments", "search", "billing", "ingest", "reports"]
    envs = []
    for i in range(n):
        env = ["dev", "test", "prod"][i % 3]
        envs.append({"name": f"svc{i + 1:02d}-{env}", "team": teams[i % len(teams)], "environment": env,
                     "size": ["small", "medium", "large"][i % 3], "admin_groups": [f"{teams[i % len(teams)]}-admins"],
                     "version": "v1.0.0", **({"canary": True} if i == 0 else {})})
    return {"catalog": os.path.join(BASE, "catalog"), "environments": envs}


def table(rows, head):
    w = [max(len(str(r[i])) for r in rows + [head]) for i in range(len(head))]
    for r in [head] + rows:
        print("  ".join(str(c).ljust(w[i]) for i, c in enumerate(r)))


def main(argv=None):
    ap = argparse.ArgumentParser(prog="rollout")
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("demo-registry"); d.add_argument("n", nargs="?", type=int, default=10)
    sub.add_parser("provision"); sub.add_parser("status"); sub.add_parser("destroy")
    sub.add_parser("registry"); sub.add_parser("last-run")
    ri = sub.add_parser("registry-import"); ri.add_argument("file")
    sub.add_parser("purge-secrets", help="LOCAL DEMO ONLY: force-delete secrets so names can be reused")
    rp = sub.add_parser("report"); rp.add_argument("--out", default=os.path.join(ROOT, "site", "index.html"))
    rp.add_argument("--live", action="store_true", help="also read the actual version from the cluster")
    p = sub.add_parser("preview"); p.add_argument("version")
    r = sub.add_parser("rollout"); r.add_argument("version"); r.add_argument("--canary", action="append")
    r.add_argument("--batch", type=int, default=3); r.add_argument("--allow-destroy", action="store_true")
    a = ap.parse_args(argv)

    if a.cmd == "demo-registry":
        from . import catalog
        catalog.build(os.path.join(BASE, "catalog"))
        service.save_registry(demo_registry(a.n))
        print(f"saved a registry of {a.n} environments and a catalog with tags v1.0.0 v1.1.0 v1.2.0")
        return 0

    if a.cmd == "registry":
        print(json.dumps(service.registry(), indent=1))
        return 0
    if a.cmd == "registry-import":
        with open(a.file) as f:
            reg, err = service.check_registry(json.load(f))
        if err:
            print(err, file=sys.stderr)
            return 1
        service.save_registry(reg)
        print(f"registry replaced: {len(reg['environments'])} environments")
        return 0
    if a.cmd == "last-run":
        runs = service.runs(1)
        print(json.dumps(runs[0] if runs else {}, indent=1))
        return 0

    reg = service.registry()
    envs = reg["environments"]
    eng = service.engine()

    if a.cmd == "report":
        from . import report
        actual = {e["name"]: eng.actual_version(e) for e in envs} if a.live else None
        print(report.build(reg, service.runs(200), a.out, actual))
        return 0

    if a.cmd == "provision":
        t0 = time.time()
        with ThreadPoolExecutor(max_workers=5) as ex:
            secs = list(ex.map(lambda e: eng.apply(e, e["version"]), envs))
        print(f"provisioned {len(envs)} environments in {round(time.time() - t0)}s (avg {round(sum(secs) / len(secs), 1)}s each)")
        return 0

    if a.cmd == "status":
        def row(e):
            actual = eng.actual_version(e)
            ok, problems = (eng.verify(e, actual) if actual else (False, ["not found"]))
            return [e["name"], e["environment"], e["version"], actual or "-",
                    "ok" if ok else f"{len(problems)} problem(s)"]
        with ThreadPoolExecutor(max_workers=3) as ex:
            rows = list(ex.map(row, envs))
        table(rows, ["environment", "kind", "pinned", "actual", "compliance"])
        return 0

    if a.cmd == "preview":
        for e in envs:
            if e["version"] == a.version:
                continue
            pl = eng.plan(e, a.version)
            flag = "  <-- DESTROYS" if pl["destroy"] else ""
            print(f"{e['name']}: +{pl['add']} ~{pl['change']} -{pl['destroy']}{flag}")
            for c in pl["changes"]:
                print(f"    {'/'.join(c['actions']):8} {c['address']}")
        return 0

    if a.cmd == "rollout":
        service.rollout({"version": a.version, "canary": a.canary, "batch": a.batch, "allow_destroy": a.allow_destroy})
        res = service.runs(1)[0]
        print(f"\nrollout to {a.version}: {res['status']} in {res['total_seconds']}s")
        for rec in res["records"]:
            line = f"  {rec['stage']:8} {rec['name']}: {'ok' if rec['ok'] else 'FAILED'} ({rec['seconds']}s)"
            if not rec["ok"]:
                line += f"; rolled back: {rec.get('rolled_back')}; " + "; ".join(rec["problems"])
            print(line)
        for n, items in res.get("destroys", {}).items():
            print(f"  blocked: {n} would destroy {', '.join(items)} (use --allow-destroy to proceed)")
        if res.get("not_attempted"):
            print(f"  not attempted: {', '.join(res['not_attempted'])}")
        return 0 if res["status"] in ("completed", "nothing_to_do") else 1

    if a.cmd == "purge-secrets":
        for e in envs:
            eng.purge_secret(e)
        print(f"purged secrets for {len(envs)} environments (local demo only)")
        return 0

    if a.cmd == "destroy":
        with ThreadPoolExecutor(max_workers=5) as ex:
            list(ex.map(eng.destroy, envs))
        print(f"destroyed {len(envs)} environments")
        return 0


if __name__ == "__main__":
    sys.exit(main())
