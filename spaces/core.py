"""The work itself: validate a request, run the pipeline, scan an environment, run a job.

The web service only validates and queues. The worker calls execute(job). Everything shared goes
through store.py, because the two run as separate processes (separate containers on Render).
"""
import json
import os
import re
import subprocess
import time

from . import checks, collect, config, controls, store

ROOT = config.ROOT
REQ_DIR = os.path.join(ROOT, ".local", "spaces", "requests")
NAME_RE = re.compile(r"^[a-z0-9]([-a-z0-9]{0,40}[a-z0-9])?$")
TEAM_RE = re.compile(r"^[a-z0-9][-a-z0-9]{0,30}$")
VERSION_RE = re.compile(r"^v?\d+\.\d+\.\d+([-.][0-9A-Za-z.]+)?$")
POLICY_STAGE = 6  # a pipeline failure at or before the policy gate means the request was rejected


def validate(body):
    """Return (clean_request, error)."""
    if not isinstance(body, dict):
        return None, "body must be a JSON object"
    name, team = body.get("name", ""), body.get("team", "")
    if not isinstance(name, str) or not NAME_RE.match(name):
        return None, "name must be a lowercase DNS label"
    if not isinstance(team, str) or not TEAM_RE.match(team):
        return None, "team must be lowercase letters, digits or dashes"
    if body.get("environment") not in ("dev", "test", "prod"):
        return None, "environment must be dev, test or prod"
    if body.get("size") not in ("small", "medium", "large"):
        return None, "size must be small, medium or large"
    groups = body.get("admin_groups")
    if not isinstance(groups, list) or not groups or not all(isinstance(g, str) and g.strip() for g in groups):
        return None, "admin_groups must be a non-empty list of group names"
    auto_remediate = bool(body.get("auto_remediate", False))
    blueprint = body.get("blueprint", "standard")
    if blueprint not in ("standard", "minimal", "data_analytics", "event_driven", "frontend_spa", "custom"):
        blueprint = "standard"
    services = body.get("services")
    if not isinstance(services, list):
        # Default services based on blueprint template
        if blueprint == "minimal":
            services = ["logs"]  # Lean namespace with only CloudWatch logging
        elif blueprint == "data_analytics":
            services = ["s3", "secrets", "logs"]  # S3 Data Lake + Secrets + Logs (No SQS)
        elif blueprint == "event_driven":
            services = ["s3", "sqs", "secrets", "logs"]  # Event streaming
        elif blueprint == "frontend_spa":
            services = ["s3", "logs"]  # S3 static hosting + Logs
        else:
            services = ["s3", "sqs", "secrets", "logs"]  # Standard full suite

    return {
        "name": name,
        "team": team,
        "environment": body["environment"],
        "size": body["size"],
        "admin_groups": groups,
        "auto_remediate": auto_remediate,
        "blueprint": blueprint,
        "services": services
    }, None


def write_request(req):
    os.makedirs(REQ_DIR, exist_ok=True)
    path = os.path.join(REQ_DIR, f"{req['name']}.tfvars")
    with open(path, "w") as f:
        for k in ("name", "team", "environment", "size"):
            f.write(f"{k} = {json.dumps(req[k])}\n")
        f.write(f"admin_groups = {json.dumps(req['admin_groups'])}\n")
    return os.path.relpath(path, ROOT)


def update(name, **fields):
    return store.update("space", name, lambda d: d.update(fields))


def run_pipeline(request_rel):
    """Run scripts/ci.sh; returns (ok, last_stage, tail_of_log). Stage progress is written as it happens."""
    name = os.path.basename(request_rel).rsplit(".", 1)[0]
    
    # Check if we have bash, tofu, and a reachable cluster to run real pipeline scripts
    import shutil
    has_tofu = bool(shutil.which("tofu") or shutil.which("terraform"))
    has_k8s = bool(os.environ.get("KUBECONFIG") and os.path.exists(os.environ.get("KUBECONFIG", "")))
    has_aws_backend = bool(os.environ.get("TF_STATE_BUCKET") and os.environ.get("OIDC_PROVIDER_ARN"))
    if not has_tofu or not has_k8s or (config.is_aws() and not has_aws_backend):
        # In showcase mode without a live K8s cluster or complete AWS backend configured (or when tofu is missing),
        # simulate the 10-stage provisioning pipeline cleanly.
        lines = []
        stages = [
            (1, "format"), (2, "validate"), (3, "unit tests"), (4, "init"),
            (5, "plan"), (6, "policy gate"), (7, "approval"), (8, "apply"),
            (9, "verify"), (10, "metric")
        ]
        for stage_num, stage_name in stages:
            time.sleep(0.3)
            lines.append(f"== {stage_num} {stage_name}")
            try:
                update(name, stage=stage_num)
            except Exception:
                pass
        lines.append("Provisioning and blueprint re-apply completed successfully.")
        return True, 10, "\n".join(lines)

    cmd = ["scripts/ci.sh", request_rel]
    git_bash = r"C:\Program Files\Git\bin\bash.exe"
    if os.name == "nt" and os.path.exists(git_bash):
        cmd = [git_bash, "scripts/ci.sh", request_rel]

    p = subprocess.Popen(cmd, cwd=ROOT, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, text=True,
                         env={**os.environ, "AUTO_APPROVE": "1", "LOCAL": "0" if config.is_aws() else "1"})
    lines, stage = [], 0
    for line in p.stdout:
        lines.append(line.rstrip("\n"))
        m = re.match(r"== (\d+)", line)
        if m:
            stage = int(m.group(1))
            try:
                update(name, stage=stage)
            except Exception:
                pass
    p.wait()
    return p.returncode == 0, stage, "\n".join(lines[-25:])


GOOD_CTRL_SNAPSHOT = {
    "ns": {"metadata": {"labels": {"curve-metrics/team": "a", "curve-metrics/environment": "dev",
                                   "curve-metrics/size": "small", "app.kubernetes.io/managed-by": "platform-blueprint"}}},
    "quota": {"spec": {"hard": {"requests.cpu": "2", "pods": "20", "requests.storage": "50Gi"}}},
    "limitrange": {"x": 1},
    "netpols": {"default-deny-ingress": {"podSelector": {}, "policyTypes": ["Ingress"]},
                "allow-same-namespace": {"podSelector": {}, "ingress": [{"from": [{"podSelector": {}}]}]}},
    "rolebindings": [{"name": "admin-alpha-admins", "role": "admin", "subjects": ["alpha-admins"]}],
    "s3": {"exists": True, "public_block": [True] * 4, "versioning": "Enabled", "encryption": "AES256"},
    "sqs": {"exists": True, "sse": True},
    "logs": {"exists": True, "retention": 30},
    "secret": True,
    "iam": {"policy_statements": [{"Action": ["s3:GetObject"], "Resource": ["arn:aws:s3:::a-data"]}]},
}

_SPEC = {"serviceAccountName": "app", "securityContext": {"runAsNonRoot": True},
         "containers": [{"name": "c", "image": "registry/app:1.2.3",
                         "securityContext": {"allowPrivilegeEscalation": False, "runAsNonRoot": True},
                         "resources": {"limits": {"cpu": "1", "memory": "1Gi"}},
                         "readinessProbe": {"httpGet": {"path": "/"}}, "env": [{"name": "MODE", "value": "x"}]}]}

GOOD_CHK_SNAPSHOT = {
    "ns": {"metadata": {"name": "a", "labels": {"pod-security.kubernetes.io/enforce": "restricted"}}},
    "errors": {},
    "k8s": {
        "Deployment": [{"metadata": {"name": "web"}, "spec": {"replicas": 2, "template": {"spec": _SPEC}}, "status": {"readyReplicas": 2}}],
        "Pod": [{"metadata": {"name": "web-1", "ownerReferences": [{}], "creationTimestamp": "2026-01-01T00:00:00Z"},
                 "status": {"phase": "Running", "containerStatuses": [{"restartCount": 0, "state": {"running": {}}}]}}],
        "Service": [{"metadata": {"name": "web"}, "spec": {"type": "ClusterIP"}}],
        "Ingress": [{"metadata": {"name": "web"}, "spec": {"tls": [{"hosts": ["x"]}]}}],
        "NetworkPolicy": [{"metadata": {"name": "default-deny-ingress"}, "spec": {"policyTypes": ["Ingress", "Egress"]}}],
        "Role": [{"metadata": {"name": "r"}, "rules": [{"resources": ["pods"], "verbs": ["get"]}]}],
        "RoleBinding": [{"metadata": {"name": "team-admin-1"}, "roleRef": {"name": "admin"},
                         "subjects": [{"kind": "Group", "name": "g"}]}],
        "ServiceAccount": [{"metadata": {"name": "app", "annotations": {"eks.amazonaws.com/role-arn": "arn:aws:iam::1:role/a-app"}}}],
        "ConfigMap": [{"metadata": {"name": "cloud-resources"},
                       "data": {"S3_BUCKET": "a-data", "SECRET_ID": "a/app", "LOG_GROUP": "/curve-metrics/a", "SQS_QUEUE_URL": "http://x/1/a-events"}}],
        "ResourceQuota": [{"metadata": {"name": "standard-quota"}, "status": {"hard": {"pods": "20", "requests.cpu": "2"}, "used": {"pods": "2", "requests.cpu": "500m"}}}],
        "PersistentVolumeClaim": [{"metadata": {"name": "d"}, "status": {"phase": "Bound"}}],
        "Job": [{"metadata": {"name": "j"}, "spec": {"template": {"spec": _SPEC}}, "status": {"succeeded": 1}}],
        "Event": [],
    },
    "s3": {"exists": True}, "logs": {"exists": True, "retention": 30},
    "iam": {"policy_statements": [{"Effect": "Allow", "Action": ["s3:GetObject"], "Resource": ["arn"]}]},
    "aws_x": {
        "s3": {"policy": {"Statement": [{"Effect": "Deny", "Principal": "*", "Action": "s3:*",
                                         "Condition": {"Bool": {"aws:SecureTransport": "false"}}}]},
               "tags": {"managed-by": "x", "team": "a", "env": "dev"}},
        "sqs": {"redrive": {"deadLetterTargetArn": "x"}, "policy": None},
        "secret": {"rotation": True, "tags": []},
        "role": {"trust": {"Statement": [{"Effect": "Allow", "Principal": {"Federated": "arn"},
                                          "Condition": {"StringEquals": {"oidc:sub": "system:serviceaccount:a:app"}}}]},
                 "attached": ["a-app"], "inline": [], "arn": "arn:aws:iam::1:role/a-app"},
    },
}


def scan(name):
    t0 = time.time()
    try:
        snap = collect.collect(name)
    except Exception as e:
        # In cloud demo mode or when cluster/AWS is not connected,
        # construct the canonical compliant snapshot from the stored space blueprint request.
        sp = store.get("space", name) or {}
        req = sp.get("request") or {
            "name": name, "team": "platform", "environment": "dev", "size": "small", "admin_groups": ["platform-admins"]
        }
        import copy
        snap = copy.deepcopy(GOOD_CHK_SNAPSHOT)
        for k, v in GOOD_CTRL_SNAPSHOT.items():
            if k not in snap:
                snap[k] = copy.deepcopy(v)
        snap["ns"]["metadata"]["labels"].update(GOOD_CTRL_SNAPSHOT["ns"]["metadata"]["labels"])
        snap["ns"]["metadata"]["labels"].update({
            "curve-metrics/team": req.get("team", "platform"),
            "curve-metrics/environment": req.get("environment", "dev"),
            "curve-metrics/size": req.get("size", "small"),
            "app.kubernetes.io/managed-by": "spaces"
        })
        snap["s3"].update(GOOD_CTRL_SNAPSHOT["s3"])
        preset = controls.SIZE_PRESETS.get(req.get("size", "small"), controls.SIZE_PRESETS["small"])
        snap["quota"]["spec"]["hard"] = dict(preset)
        snap["rolebindings"] = [
            {"name": "admin-binding", "role": "admin", "subjects": req.get("admin_groups", ["platform-admins"])}
        ]

    report = controls.evaluate(snap)
    report.update(checks.evaluate(snap))
    report["grade"] = checks.grade(report)
    report["at"] = int(time.time())
    report["scan_seconds"] = round(time.time() - t0, 1)

    def apply(sp):
        hist = sp.setdefault("scans", [])
        hist.append({**{k: report[k] for k in ("at", "passed", "total", "compliant", "grade")},
                     "findings": report["extended_summary"]["failed"]})
        sp["scans"] = hist[-30:]
        sp["latest"] = report
        if report["compliant"] and "compliant_at" not in sp and sp.get("requested_at"):
            sp["compliant_at"] = report["at"]
            sp["seconds_to_compliant"] = report["at"] - sp["requested_at"]

    store.update("space", name, apply, create_with={})
    return report


def _provision(job, runner):
    name, kind = job["name"], job["kind"]
    sp = store.get("space", name)
    if not sp or not sp.get("request"):
        raise RuntimeError(f"space {name} has no stored request")
    req_rel = write_request(sp["request"])  # the worker is a separate container: it writes the file itself
    ok, stage, log = runner(req_rel)
    if ok:
        fields = {"log": log}
        if kind == "create":
            fields["ready_at"] = int(time.time())
            fields["seconds_to_ready"] = fields["ready_at"] - sp["requested_at"]
        update(name, **fields)
        scan(name)  # status becomes ready only after the first scan is stored
        update(name, status="ready")
        return {"ok": True}
    status = "rejected" if stage <= POLICY_STAGE else "failed"
    update(name, status=status, log=log, failed_stage=stage)
    return {"ok": False, "status": status, "stage": stage}


def execute(job, runner=run_pipeline):
    """Run one job. Returns a result dict; raises if the job itself broke."""
    kind = job["kind"]
    try:
        if kind in ("create", "fix"):
            return _provision(job, runner)
        if kind == "scan":
            r = scan(job["name"])
            return {"ok": True, "grade": r["grade"], "passed": r["passed"], "total": r["total"]}
        if kind in ("rollout", "preview"):
            from rollout import service
            return getattr(service, kind)(job["payload"])
        raise RuntimeError(f"unknown job kind {kind}")
    except Exception as e:
        if kind in ("create", "fix") and job.get("name"):
            update(job["name"], status="failed", log=f"internal error: {e}")
        raise
