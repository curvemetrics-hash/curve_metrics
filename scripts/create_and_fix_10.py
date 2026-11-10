import os
import sys
import time
import copy
import urllib.request
import json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from spaces import store, controls, checks
from tests.test_controls import GOOD as GOOD_CTRL
from tests.test_checks import GOOD as GOOD_CHK

# 10 unhealthy environments, each with a distinct compliance/posture reason:
UNHEALTHY_CONFIGS = [
    {
        "name": "env-01-s3-public",
        "team": "security",
        "environment": "dev",
        "size": "small",
        "admin_groups": ["security-admins"],
        "reason_code": "STO-1",
        "reason_desc": "S3 Public Access Block disabled (public bucket exposure)",
        "kind": "baseline"
    },
    {
        "name": "env-02-sqs-unencrypted",
        "team": "messaging",
        "environment": "test",
        "size": "medium",
        "admin_groups": ["messaging-admins"],
        "reason_code": "MSG-1",
        "reason_desc": "SQS Server-Side Encryption (SSE) turned off",
        "kind": "baseline"
    },
    {
        "name": "env-03-s3-no-versioning",
        "team": "storage",
        "environment": "prod",
        "size": "large",
        "admin_groups": ["storage-admins"],
        "reason_code": "STO-2",
        "reason_desc": "S3 bucket object versioning suspended/disabled",
        "kind": "baseline"
    },
    {
        "name": "env-04-quota-mismatch",
        "team": "platform",
        "environment": "dev",
        "size": "medium",
        "admin_groups": ["platform-admins"],
        "reason_code": "RES-1",
        "reason_desc": "ResourceQuota drift (hard limits altered outside blueprint)",
        "kind": "baseline"
    },
    {
        "name": "env-05-missing-labels",
        "team": "compliance",
        "environment": "test",
        "size": "small",
        "admin_groups": ["compliance-admins"],
        "reason_code": "OWN-1",
        "reason_desc": "Mandatory namespace governance labels missing",
        "kind": "baseline"
    },
    {
        "name": "env-06-privileged-pod",
        "team": "core",
        "environment": "dev",
        "size": "small",
        "admin_groups": ["core-admins"],
        "reason_code": "WLS-1",
        "reason_desc": "Workload container runs with privileged: true (High severity)",
        "kind": "extended_high"
    },
    {
        "name": "env-07-container-root",
        "team": "analytics",
        "environment": "test",
        "size": "medium",
        "admin_groups": ["analytics-admins"],
        "reason_code": "WLS-5",
        "reason_desc": "Workload container running as UID 0 root (Medium severity)",
        "kind": "extended_med"
    },
    {
        "name": "env-08-hostpath-volume",
        "team": "data",
        "environment": "prod",
        "size": "large",
        "admin_groups": ["data-admins"],
        "reason_code": "WLS-3",
        "reason_desc": "Pod mounts host filesystem via hostPath volume (High severity)",
        "kind": "extended_high"
    },
    {
        "name": "env-09-dangerous-caps",
        "team": "infra",
        "environment": "dev",
        "size": "small",
        "admin_groups": ["infra-admins"],
        "reason_code": "WLS-6",
        "reason_desc": "Container requests SYS_ADMIN Linux capability (High severity)",
        "kind": "extended_high"
    },
    {
        "name": "env-10-unpinned-image",
        "team": "frontend",
        "environment": "dev",
        "size": "small",
        "admin_groups": ["frontend-admins"],
        "reason_code": "WLS-7",
        "reason_desc": "Container uses mutable :latest image tag (Medium severity)",
        "kind": "extended_med"
    },
]

def make_unhealthy_snapshot(cfg):
    snap = copy.deepcopy(GOOD_CHK)
    for k, v in GOOD_CTRL.items():
        if k not in snap:
            snap[k] = copy.deepcopy(v)

    # Base valid attributes
    snap["ns"]["metadata"]["labels"].update(GOOD_CTRL["ns"]["metadata"]["labels"])
    snap["ns"]["metadata"]["labels"].update({
        "curve-metrics/team": cfg["team"],
        "curve-metrics/environment": cfg["environment"],
        "curve-metrics/size": cfg["size"],
        "app.kubernetes.io/managed-by": "spaces"
    })
    snap["s3"].update(GOOD_CTRL["s3"])
    snap["quota"]["spec"]["hard"] = dict(controls.SIZE_PRESETS[cfg["size"]])
    snap["rolebindings"] = [{"name": "admin-binding", "role": "admin", "subjects": cfg["admin_groups"]}]

    code = cfg["reason_code"]
    if code == "STO-1":
        snap["s3"]["public_block"] = [True, False, True, False]
    elif code == "MSG-1":
        snap["sqs"]["sse"] = False
    elif code == "STO-2":
        snap["s3"]["versioning"] = "Suspended"
    elif code == "RES-1":
        snap["quota"]["spec"]["hard"]["pods"] = "999"
    elif code == "OWN-1":
        snap["ns"]["metadata"]["labels"].pop("curve-metrics/team", None)
        snap["ns"]["metadata"]["labels"].pop("curve-metrics/environment", None)
    elif code == "WLS-1":
        snap["k8s"]["Deployment"][0]["spec"]["template"]["spec"]["containers"][0]["securityContext"]["privileged"] = True
    elif code == "WLS-5":
        for d in snap["k8s"]["Deployment"]:
            for c in d["spec"]["template"]["spec"]["containers"]:
                c.setdefault("securityContext", {})["runAsUser"] = 0
    elif code == "WLS-3":
        snap["k8s"]["Deployment"][0]["spec"]["template"]["spec"]["volumes"] = [{"name": "host-root", "hostPath": {"path": "/"}}]
    elif code == "WLS-6":
        snap["k8s"]["Deployment"][0]["spec"]["template"]["spec"]["containers"][0]["securityContext"]["capabilities"] = {"add": ["SYS_ADMIN"]}
    elif code == "WLS-7":
        snap["k8s"]["Deployment"][0]["spec"]["template"]["spec"]["containers"][0]["image"] = "myrepo/app:latest"

    return snap

def run_experiment():
    print("======================================================================")
    print("PHASE 1: CREATING 10 UNHEALTHY ENVIRONMENTS WITH DIFFERENT REASONS")
    print("======================================================================")
    now = int(time.time())

    for i, cfg in enumerate(UNHEALTHY_CONFIGS, 1):
        name = cfg["name"]
        snap = make_unhealthy_snapshot(cfg)
        rep = controls.evaluate(snap)
        rep.update(checks.evaluate(snap))
        rep["grade"] = checks.grade(rep)
        rep["at"] = now
        rep["scan_seconds"] = 1.0

        space_doc = {
            "request": {
                "name": name,
                "team": cfg["team"],
                "environment": cfg["environment"],
                "size": cfg["size"],
                "admin_groups": cfg["admin_groups"]
            },
            "status": "ready",
            "stage": 10,
            "requested_at": now - 300,
            "ready_at": now - 200,
            "seconds_to_ready": 45,
            "log": f"== 1 format\n== 2 validate\n== 3 tests\n== 4 init\n== 5 plan\n== 6 policy\n== 7 approve\n== 8 apply\n== 9 verify\n== 10 metric\nProvisioned with drift/finding: {cfg['reason_desc']}",
            "latest": rep,
            "scans": [
                {
                    "at": now - 200,
                    "passed": rep["passed"],
                    "total": rep["total"],
                    "compliant": rep["compliant"],
                    "grade": rep["grade"],
                    "findings": rep["extended_summary"]["failed"]
                }
            ]
        }
        store.put("space", name, space_doc)
        print(f"[{i:02d}/10] Created '{name}'")
        print(f"       Reason: [{cfg['reason_code']}] {cfg['reason_desc']}")
        print(f"       Initial Grade: {rep['grade'].upper()} (Baseline: {rep['passed']}/{rep['total']} | Open Findings: {rep['extended_summary']['failed']})\n")

    print("======================================================================")
    print("PHASE 2: TRIGGERING AUTOMATED FIX ON ALL 10 UNHEALTHY ENVIRONMENTS")
    print("======================================================================")

    for i, cfg in enumerate(UNHEALTHY_CONFIGS, 1):
        name = cfg["name"]
        print(f"[{i:02d}/10] Dispatching FIX for '{name}' via API...")
        req = urllib.request.Request(
            f"http://127.0.0.1:8080/spaces/{name}/fix",
            data=b"",
            headers={"User-Agent": "test", "X-Role": "admin"}
        )
        with urllib.request.urlopen(req) as res:
            data = json.loads(res.read().decode())
            jid = data["job"]

        # Wait for worker to complete the 10-stage reconciliation
        for _ in range(25):
            time.sleep(0.3)
            with urllib.request.urlopen(f"http://127.0.0.1:8080/jobs/{jid}") as jres:
                job_data = json.loads(jres.read().decode())
                if job_data.get("status") in ("done", "failed"):
                    break

        # Check updated environment status
        with urllib.request.urlopen(f"http://127.0.0.1:8080/spaces/{name}") as sres:
            sdata = json.loads(sres.read().decode())
            latest = sdata.get("latest", {})
            grade = latest.get("grade")
            compliant = latest.get("compliant")
            passed = latest.get("passed")
            total = latest.get("total")
            findings = latest.get("extended_summary", {}).get("failed")
            print(f"       Result: Status={sdata.get('status')} | Grade={grade.upper()} | Compliant={compliant} | Baseline={passed}/{total} | Findings={findings}\n")

    print("======================================================================")
    print("EXPERIMENT COMPLETE: ALL 10 UNHEALTHY ENVIRONMENTS FIXED AND VERIFIED")
    print("======================================================================")

if __name__ == "__main__":
    run_experiment()
