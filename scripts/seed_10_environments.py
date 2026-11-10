import os
import sys
import time
import copy

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from spaces import store, controls, checks
from tests.test_controls import GOOD as GOOD_CTRL
from tests.test_checks import GOOD as GOOD_CHK

# Define 10 environments representing real-world distribution:
# 6 Healthy (all 14 baseline pass, 0 high/med findings)
# 2 Needs Attention (14 baseline pass, 1-2 medium findings with actionable fixes)
# 1 At Risk (14 baseline pass, 1 high finding with critical fix)
# 1 Non-Compliant (fails baseline control, e.g. SQS unencrypted)
ENVIRONMENTS = [
    {
        "name": "payments-dev",
        "team": "payments",
        "environment": "dev",
        "size": "small",
        "admin_groups": ["payments-admins"],
        "flavor": "healthy",
        "seconds_to_ready": 38,
    },
    {
        "name": "checkout-staging",
        "team": "checkout",
        "environment": "test",
        "size": "medium",
        "admin_groups": ["checkout-admins"],
        "flavor": "healthy",
        "seconds_to_ready": 52,
    },
    {
        "name": "orders-prod",
        "team": "orders",
        "environment": "prod",
        "size": "large",
        "admin_groups": ["orders-admins", "orders-leads"],
        "flavor": "healthy",
        "seconds_to_ready": 68,
    },
    {
        "name": "analytics-dev",
        "team": "analytics",
        "environment": "dev",
        "size": "medium",
        "admin_groups": ["analytics-admins"],
        "flavor": "attention",  # medium finding: WLS-5 containers run as root
        "seconds_to_ready": 44,
    },
    {
        "name": "auth-prod",
        "team": "auth",
        "environment": "prod",
        "size": "large",
        "admin_groups": ["auth-admins"],
        "flavor": "healthy",
        "seconds_to_ready": 71,
    },
    {
        "name": "search-dev",
        "team": "search",
        "environment": "dev",
        "size": "small",
        "admin_groups": ["search-admins"],
        "flavor": "at_risk",  # high finding: WLS-1 privileged container
        "seconds_to_ready": 41,
    },
    {
        "name": "billing-test",
        "team": "billing",
        "environment": "test",
        "size": "medium",
        "admin_groups": ["billing-admins"],
        "flavor": "healthy",
        "seconds_to_ready": 49,
    },
    {
        "name": "inventory-dev",
        "team": "inventory",
        "environment": "dev",
        "size": "small",
        "admin_groups": ["inventory-admins"],
        "flavor": "attention",  # medium finding: WLS-7 image uses latest/unpinned tag
        "seconds_to_ready": 36,
    },
    {
        "name": "gateway-prod",
        "team": "platform",
        "environment": "prod",
        "size": "large",
        "admin_groups": ["platform-admins"],
        "flavor": "healthy",
        "seconds_to_ready": 79,
    },
    {
        "name": "notifications-dev",
        "team": "notifications",
        "environment": "dev",
        "size": "small",
        "admin_groups": ["notifications-admins"],
        "flavor": "non_compliant",  # fails baseline control MSG-1 (SQS unencrypted)
        "seconds_to_ready": 34,
    },
]

def make_clean_snapshot(env_cfg):
    snap = copy.deepcopy(GOOD_CHK)
    for k, v in GOOD_CTRL.items():
        if k not in snap:
            snap[k] = copy.deepcopy(v)
    
    # Namespace labels
    snap["ns"]["metadata"]["labels"].update(GOOD_CTRL["ns"]["metadata"]["labels"])
    snap["ns"]["metadata"]["labels"].update({
        "curve-metrics/team": env_cfg["team"],
        "curve-metrics/environment": env_cfg["environment"],
        "curve-metrics/size": env_cfg["size"],
        "app.kubernetes.io/managed-by": "spaces"
    })
    
    # S3 bucket config
    snap["s3"].update(GOOD_CTRL["s3"])
    
    # Resource quota presets
    preset = controls.SIZE_PRESETS[env_cfg["size"]]
    snap["quota"]["spec"]["hard"] = dict(preset)
    
    # Role bindings to named admin group
    snap["rolebindings"] = [
        {"name": "admin-binding", "role": "admin", "subjects": env_cfg["admin_groups"]}
    ]
    
    # Flavor adjustments
    flavor = env_cfg["flavor"]
    if flavor == "non_compliant":
        # Break baseline control MSG-1
        snap["sqs"]["sse"] = False
    elif flavor == "at_risk":
        # Add high finding: WLS-1 (privileged container)
        if snap.get("k8s", {}).get("Deployment"):
            snap["k8s"]["Deployment"][0]["spec"]["template"]["spec"]["containers"][0]["securityContext"]["privileged"] = True
    elif flavor == "attention":
        # Add medium finding: WLS-5 (run as root)
        if snap.get("k8s", {}).get("Deployment"):
            for d in snap["k8s"]["Deployment"]:
                for c in d["spec"]["template"]["spec"]["containers"]:
                    c.setdefault("securityContext", {})["runAsUser"] = 0
    return snap

def seed_10():
    print("Populating 10 environments with realistic compliance and posture scans...")
    now = int(time.time())
    
    for i, cfg in enumerate(ENVIRONMENTS, 1):
        name = cfg["name"]
        print(f"[{i:02d}/10] Processing {name} ({cfg['environment']} · {cfg['size']})...")
        snap = make_clean_snapshot(cfg)
        
        rep = controls.evaluate(snap)
        rep.update(checks.evaluate(snap))
        rep["grade"] = checks.grade(rep)
        rep["at"] = now
        rep["scan_seconds"] = 1.15
        
        req_at = now - (10 - i) * 120 - cfg["seconds_to_ready"]
        ready_at = req_at + cfg["seconds_to_ready"]
        
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
            "requested_at": req_at,
            "ready_at": ready_at,
            "seconds_to_ready": cfg["seconds_to_ready"],
            "log": f"== 1 format\n== 2 validate\n== 3 tests\n== 4 init\n== 5 plan\n== 6 policy\n== 7 approve\n== 8 apply\n== 9 verify\n== 10 metric\nProvisioning completed successfully in {cfg['seconds_to_ready']}s.",
            "latest": rep,
            "scans": [
                {
                    "at": ready_at,
                    "passed": rep["passed"],
                    "total": rep["total"],
                    "compliant": rep["compliant"],
                    "grade": rep["grade"],
                    "findings": rep["extended_summary"]["failed"]
                }
            ]
        }
        if rep["compliant"]:
            space_doc["compliant_at"] = ready_at
            space_doc["seconds_to_compliant"] = cfg["seconds_to_ready"]
            
        store.put("space", name, space_doc)
        failed_ctrls = [c["id"] for c in rep["controls"] if not c["passed"]]
        failed_ext = [r["id"] for r in rep.get("extended", []) if r["status"] == "fail"]
        print(f"       Result: Grade={rep['grade'].upper()} (Baseline: {rep['passed']}/{rep['total']} | Extended Failed: {failed_ext})")

if __name__ == "__main__":
    seed_10()
