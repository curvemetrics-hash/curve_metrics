"""Engine: does the real work for one environment at one blueprint version.

Materialize the version from the catalog (git archive), then run OpenTofu with a state file per
environment. Verification reuses the compliance checker from spaces/.
"""
import json
import os
import shutil
import subprocess
import threading
import time

from spaces import collect, config, controls

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORK = os.path.join(ROOT, ".local", "rollout", "work")
VERSION_LABEL = "curve-metrics/blueprint-version"
_init_lock = threading.Lock()
_verify_slots = threading.Semaphore(3)  # each scan starts many short processes


class EngineError(RuntimeError):
    pass


class Engine:
    def __init__(self, catalog, kubeconfig=None):
        self.catalog = catalog
        self.kubeconfig = kubeconfig or config.kubeconfig()
        self.cache = os.environ.get("TF_PLUGIN_CACHE_DIR") or os.path.join(ROOT, ".local", "rollout", "plugin-cache")
        os.makedirs(self.cache, exist_ok=True)
        self.env = {**os.environ, "KUBECONFIG": self.kubeconfig, "TF_PLUGIN_CACHE_DIR": self.cache,
                    "TF_IN_AUTOMATION": "1"}

    # --- helpers -----------------------------------------------------------------------
    def _run(self, cmd, cwd=None):
        p = subprocess.run(cmd, cwd=cwd, env=self.env, capture_output=True, text=True)
        if p.returncode != 0:
            raise EngineError(f"{' '.join(cmd[:3])} failed: {(p.stderr or p.stdout).strip()[-400:]}")
        return p.stdout

    def _workdir(self, name):
        return os.path.join(WORK, name)

    def materialize(self, env, version):
        """Extract blueprints/ and modules/ at `version` into a fresh per-environment work dir."""
        wd = self._workdir(env["name"])
        shutil.rmtree(wd, ignore_errors=True)
        os.makedirs(wd)
        arc = subprocess.run(["git", "-C", self.catalog, "archive", version, "blueprints", "modules"],
                             capture_output=True)
        if arc.returncode != 0:
            raise EngineError(f"version {version} not found in catalog")
        tar = subprocess.run(["tar", "-x", "-C", wd], input=arc.stdout, capture_output=True)
        if tar.returncode != 0:
            raise EngineError("could not extract blueprint")
        tfvars = os.path.join(wd, "request.tfvars")
        with open(tfvars, "w") as f:
            for k in ("name", "team", "environment", "size"):
                f.write(f"{k} = {json.dumps(env[k])}\n")
            f.write(f"admin_groups = {json.dumps(env['admin_groups'])}\n")
            f.write(f"extra_labels = {json.dumps({VERSION_LABEL: version})}\n")
        return wd

    def _bp(self, wd):
        return os.path.join(wd, "blueprints", "standard_team_env")

    def _init(self, env, wd):
        with _init_lock:
            self._run(["tofu", f"-chdir={self._bp(wd)}", "init", "-input=false", "-reconfigure",
                       *config.tf_backend_args(), f"-backend-config=key=rollout/{env['name']}.tfstate"])

    def _plan(self, env, wd):
        args = ["-input=false", f"-var=kubeconfig_path={self.kubeconfig}",
                f"-var-file={os.path.join(wd, 'request.tfvars')}", *config.tf_var_args()]
        self._run(["tofu", f"-chdir={self._bp(wd)}", "plan", *args, "-out=plan.bin"])
        out = self._run(["tofu", f"-chdir={self._bp(wd)}", "show", "-json", "plan.bin"])
        return json.loads(out)

    # --- operations --------------------------------------------------------------------
    def plan(self, env, version):
        """What would change if `env` moved to `version`. Nothing is applied."""
        wd = self.materialize(env, version)
        self._init(env, wd)
        changes = [{"address": c["address"], "actions": c["change"]["actions"]}
                   for c in self._plan(env, wd).get("resource_changes", [])
                   if c["change"]["actions"] != ["no-op"]]
        count = lambda a: sum(1 for c in changes if a in c["actions"])  # noqa: E731
        return {"add": count("create"), "change": count("update"), "destroy": count("delete"), "changes": changes}

    def apply(self, env, version):
        """Move `env` to `version`. Returns elapsed seconds."""
        t0 = time.time()
        wd = self.materialize(env, version)
        self._init(env, wd)
        self._plan(env, wd)
        self._run(["tofu", f"-chdir={self._bp(wd)}", "apply", "-input=false", "plan.bin"])
        return round(time.time() - t0, 1)

    def actual_version(self, env):
        p = subprocess.run(["kubectl", "get", "ns", env["name"], "-o", "json"], env=self.env,
                           capture_output=True, text=True)
        if p.returncode != 0:
            return None
        return json.loads(p.stdout)["metadata"].get("labels", {}).get(VERSION_LABEL)

    def verify(self, env, version):
        """Return (ok, problems). Checks the version label and all compliance controls."""
        with _verify_slots:
            snap = collect.collect(env["name"])
        report = controls.evaluate(snap)
        problems = [f"{c['id']}: {c['evidence']}" for c in report["controls"] if not c["passed"]]
        have = ((snap.get("ns") or {}).get("metadata") or {}).get("labels", {}).get(VERSION_LABEL)
        if have != version:
            problems.append(f"version label is {have}, expected {version}")
        return (not problems), problems

    def destroy(self, env):
        wd = self._workdir(env["name"])
        if not os.path.isdir(wd):
            wd = self.materialize(env, env.get("version") or "v1.0.0")
        self._init(env, wd)
        self._run(["tofu", f"-chdir={self._bp(wd)}", "destroy", "-auto-approve", "-input=false",
                   f"-var=kubeconfig_path={self.kubeconfig}", f"-var-file={os.path.join(wd, 'request.tfvars')}",
                   *config.tf_var_args()])

    def purge_secret(self, env, name=None):
        """LOCAL DEMO ONLY: delete the secret immediately so the name can be reused.
        Real AWS keeps a deleted secret for a recovery window; the module keeps that safe default.
        A secret already marked deleted must be restored before it can be force-deleted."""
        if config.is_aws():
            raise EngineError("purge_secret is for LocalStack only and is refused against real AWS")
        sid = f"{name or env['name']}/app"
        aws = os.path.join(ROOT, "scripts", "awslocal.sh")
        for args in (["restore-secret"], ["delete-secret", "--force-delete-without-recovery"]):
            subprocess.run([aws, "secretsmanager", *args, "--secret-id", sid],
                           env=self.env, capture_output=True, text=True)
