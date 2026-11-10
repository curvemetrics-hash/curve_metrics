import os
import sys
import time
import copy
import json
import urllib.request
import urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from spaces import store, controls, checks
from tests.test_controls import GOOD as GOOD_CTRL
from tests.test_checks import GOOD as GOOD_CHK

BASE_URL = "http://127.0.0.1:8080"

# 12 challenging stress-test scenarios covering edge cases:
STRESS_SCENARIOS = [
    {
        "id": "STRESS-01",
        "name": "stress-01-multi-baseline-drift",
        "team": "core", "env": "dev", "size": "small", "groups": ["core-admins"],
        "desc": "Multiple baseline failures at once (S3 public + SQS unencrypted + quota mismatch)",
        "setup": lambda s: [
            s["s3"].update({"public_block": [False, False, False, False]}),
            s["sqs"].update({"sse": False}),
            s["quota"]["spec"]["hard"].update({"pods": "999"})
        ]
    },
    {
        "id": "STRESS-02",
        "name": "stress-02-compound-findings",
        "team": "sec", "env": "test", "size": "medium", "groups": ["sec-admins"],
        "desc": "Multiple High + Medium extended findings (privileged pod + hostPath + root UID)",
        "setup": lambda s: [
            s["k8s"]["Deployment"][0]["spec"]["template"]["spec"]["containers"][0]["securityContext"].update({"privileged": True, "runAsUser": 0}),
            s["k8s"]["Deployment"][0]["spec"]["template"]["spec"].update({"volumes": [{"name": "rootfs", "hostPath": {"path": "/"}}]})
        ]
    },
    {
        "id": "STRESS-03",
        "name": "stress-03-policy-rejected-recovery",
        "team": "billing", "env": "prod", "size": "large", "groups": ["billing-admins"],
        "desc": "Environment stuck in rejected state at stage 6 policy gate",
        "setup": lambda s: None,
        "init_status": "rejected", "init_stage": 6, "failed_stage": 6
    },
    {
        "id": "STRESS-04",
        "name": "stress-04-iam-wildcard-drift",
        "team": "auth", "env": "prod", "size": "large", "groups": ["auth-admins"],
        "desc": "IAM policy drifted with wildcard Action:* and Resource:* (SEC-2 fail)",
        "setup": lambda s: s["iam"].update({"policy_statements": [{"Effect": "Allow", "Action": "*", "Resource": "*"}]})
    },
    {
        "id": "STRESS-05",
        "name": "stress-05-large-scale-prod-drift",
        "team": "data", "env": "prod", "size": "large", "groups": ["data-admins", "lead-admins"],
        "desc": "Large tier environment with missing LimitRange and S3 encryption off",
        "setup": lambda s: [
            s.update({"limitrange": None}),
            s["s3"].update({"encryption": None})
        ]
    },
    {
        "id": "STRESS-06",
        "name": "stress-06-missing-secret",
        "team": "payments", "env": "dev", "size": "small", "groups": ["payments-admins"],
        "desc": "Baseline control SEC-1 failure: application secret missing in store",
        "setup": lambda s: s.update({"secret": False})
    },
    {
        "id": "STRESS-07",
        "name": "stress-07-open-admin-binding",
        "team": "infra", "env": "test", "size": "medium", "groups": ["infra-admins"],
        "desc": "ACC-1 failure: role bound to system:authenticated open group",
        "setup": lambda s: s["rolebindings"].append({"name": "bad-binding", "role": "admin", "subjects": ["system:authenticated"]})
    },
    {
        "id": "STRESS-08",
        "name": "stress-08-no-named-admin",
        "team": "gateway", "env": "prod", "size": "large", "groups": ["gateway-admins"],
        "desc": "ACC-2 failure: no named admin group bound to the space",
        "setup": lambda s: s.update({"rolebindings": []})
    },
    {
        "id": "STRESS-09",
        "name": "stress-09-corrupted-netpols",
        "team": "network", "env": "dev", "size": "small", "groups": ["network-admins"],
        "desc": "NET-1 failure: default-deny-ingress network policy deleted",
        "setup": lambda s: s.update({"netpols": {}})
    },
    {
        "id": "STRESS-10",
        "name": "stress-10-allow-all-ingress",
        "team": "api", "env": "dev", "size": "medium", "groups": ["api-admins"],
        "desc": "NET-2 failure: dangerous ingress rule allowing traffic from everywhere",
        "setup": lambda s: s["netpols"].update({"allow-all": {"podSelector": {}, "ingress": [{"ports": [{"port": 80}]}]}})
    },
    {
        "id": "STRESS-11",
        "name": "stress-11-log-retention-expired",
        "team": "audit", "env": "prod", "size": "large", "groups": ["audit-admins"],
        "desc": "LOG-1 failure: CloudWatch log group retention period deleted",
        "setup": lambda s: s["logs"].update({"retention": None})
    },
    {
        "id": "STRESS-12",
        "name": "stress-12-rbac-unauthorized-role",
        "team": "ops", "env": "test", "size": "small", "groups": ["ops-admins"],
        "desc": "ACC-1 failure: namespace admin assigned cluster-admin role",
        "setup": lambda s: s["rolebindings"].append({"name": "cluster-admin-bind", "role": "cluster-admin", "subjects": ["ops-admins"]})
    },
]

def make_space_snapshot(cfg):
    snap = copy.deepcopy(GOOD_CHK)
    for k, v in GOOD_CTRL.items():
        if k not in snap:
            snap[k] = copy.deepcopy(v)
    snap["ns"]["metadata"]["labels"].update(GOOD_CTRL["ns"]["metadata"]["labels"])
    snap["ns"]["metadata"]["labels"].update({
        "curve-metrics/team": cfg["team"],
        "curve-metrics/environment": cfg["env"],
        "curve-metrics/size": cfg["size"],
        "app.kubernetes.io/managed-by": "spaces"
    })
    snap["s3"].update(GOOD_CTRL["s3"])
    snap["quota"]["spec"]["hard"] = dict(controls.SIZE_PRESETS[cfg["size"]])
    snap["rolebindings"] = [{"name": "admin-binding", "role": "admin", "subjects": cfg["groups"]}]
    
    if cfg["setup"]:
        cfg["setup"](snap)
    return snap

def run_deep_stress_test():
    print("=" * 78)
    print("EXTENSIVE STRESS TESTING SUITE: 12 ADVERSARIAL FAILURE & RECOVERY SCENARIOS")
    print("=" * 78)
    now = int(time.time())

    passed_count = 0
    total_count = len(STRESS_SCENARIOS)

    for idx, sc in enumerate(STRESS_SCENARIOS, 1):
        name = sc["name"]
        print(f"\n[{idx:02d}/{total_count}] Scenario: {sc['id']} - {sc['desc']}")
        
        # 1. Seed the degraded/unhealthy space
        snap = make_space_snapshot(sc)
        rep = controls.evaluate(snap)
        rep.update(checks.evaluate(snap))
        rep["grade"] = checks.grade(rep)
        rep["at"] = now
        rep["scan_seconds"] = 1.0

        init_status = sc.get("init_status", "ready")
        init_stage = sc.get("init_stage", 10)
        failed_stage = sc.get("failed_stage")

        space_doc = {
            "request": {
                "name": name,
                "team": sc["team"],
                "environment": sc["env"],
                "size": sc["size"],
                "admin_groups": sc["groups"]
            },
            "status": init_status,
            "stage": init_stage,
            "failed_stage": failed_stage,
            "requested_at": now - 600,
            "ready_at": now - 500 if init_status == "ready" else None,
            "seconds_to_ready": 50 if init_status == "ready" else None,
            "log": f"Initial failure state for scenario {sc['id']}",
            "latest": rep,
            "scans": [
                {
                    "at": now - 500,
                    "passed": rep["passed"],
                    "total": rep["total"],
                    "compliant": rep["compliant"],
                    "grade": rep["grade"],
                    "findings": rep["extended_summary"]["failed"]
                }
            ]
        }
        store.put("space", name, space_doc)
        print(f"       Initial Condition: Status='{init_status}', Grade='{rep['grade'].upper()}', Compliant={rep['compliant']} (Baseline: {rep['passed']}/{rep['total']})")

        # 2. Trigger Fix via Live HTTP API
        req = urllib.request.Request(
            f"{BASE_URL}/spaces/{name}/fix",
            data=b"",
            headers={"User-Agent": "stress-test", "X-Role": "admin"}
        )
        t_start = time.time()
        try:
            with urllib.request.urlopen(req) as res:
                assert res.status == 202, f"Expected 202, got {res.status}"
                body = json.loads(res.read().decode())
                jid = body["job"]
        except Exception as e:
            print(f"       FAILED TO DISPATCH FIX: {e}")
            continue

        # 3. Wait for Background Worker Reconciliation
        success = False
        for _ in range(30):
            time.sleep(0.3)
            with urllib.request.urlopen(f"{BASE_URL}/jobs/{jid}") as jres:
                job_data = json.loads(jres.read().decode())
                st = job_data.get("status")
                if st == "done":
                    success = True
                    break
                elif st == "failed":
                    print(f"       Job failed: {job_data.get('result')}")
                    break

        assert success, f"Job {jid} did not complete successfully"

        # 4. Rigorous Post-Fix Verification
        with urllib.request.urlopen(f"{BASE_URL}/spaces/{name}") as sres:
            sdata = json.loads(sres.read().decode())
            latest = sdata.get("latest", {})
            st = sdata.get("status")
            grade = latest.get("grade")
            comp = latest.get("compliant")
            passed = latest.get("passed")
            total = latest.get("total")
            findings = latest.get("extended_summary", {}).get("failed")
            dur = round(time.time() - t_start, 2)

            # Verification assertions:
            is_valid = (
                st == "ready" and
                grade == "healthy" and
                comp is True and
                passed == 14 and
                total == 14 and
                findings == 0
            )

            if is_valid:
                passed_count += 1
                print(f"       VERIFIED RECOVERY: Grade={grade.upper()} | Compliant={comp} | Baseline={passed}/{total} | Findings={findings} ({dur}s)")
            else:
                print(f"       VERIFICATION FAILED: st={st}, grade={grade}, comp={comp}, passed={passed}")

    print("\n" + "=" * 78)
    print(f"FINAL STRESS TEST RESULT: {passed_count} / {total_count} SCENARIOS 100% RECOVERED AND VERIFIED")
    print("=" * 78)
    return passed_count == total_count

if __name__ == "__main__":
    ok = run_deep_stress_test()
    sys.exit(0 if ok else 1)
