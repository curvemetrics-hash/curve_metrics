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

from spaces import store, controls, checks, cron
from tests.test_controls import GOOD as GOOD_CTRL
from tests.test_checks import GOOD as GOOD_CHK

BASE_URL = "http://127.0.0.1:8080"

def log_header(title):
    print("\n" + "=" * 76)
    print(title)
    print("=" * 76)

def seed_sample_degraded(name, team, env, size, broken_code):
    snap = copy.deepcopy(GOOD_CHK)
    for k, v in GOOD_CTRL.items():
        if k not in snap:
            snap[k] = copy.deepcopy(v)
    snap["ns"]["metadata"]["labels"].update(GOOD_CTRL["ns"]["metadata"]["labels"])
    snap["ns"]["metadata"]["labels"].update({
        "curve-metrics/team": team,
        "curve-metrics/environment": env,
        "curve-metrics/size": size,
        "app.kubernetes.io/managed-by": "spaces"
    })
    snap["s3"].update(GOOD_CTRL["s3"])
    snap["quota"]["spec"]["hard"] = dict(controls.SIZE_PRESETS[size])
    snap["rolebindings"] = [{"name": "admin-binding", "role": "admin", "subjects": [f"{team}-admins"]}]

    if broken_code == "STO-1":
        snap["s3"]["public_block"] = [True, False, True, False]
    elif broken_code == "MSG-1":
        snap["sqs"]["sse"] = False
    elif broken_code == "WLS-1":
        snap["k8s"]["Deployment"][0]["spec"]["template"]["spec"]["containers"][0]["securityContext"]["privileged"] = True
    elif broken_code == "WLS-5":
        for d in snap["k8s"]["Deployment"]:
            for c in d["spec"]["template"]["spec"]["containers"]:
                c.setdefault("securityContext", {})["runAsUser"] = 0

    rep = controls.evaluate(snap)
    rep.update(checks.evaluate(snap))
    rep["grade"] = checks.grade(rep)
    rep["at"] = int(time.time())

    space_doc = {
        "request": {
            "name": name,
            "team": team,
            "environment": env,
            "size": size,
            "admin_groups": [f"{team}-admins"],
            "auto_remediate": True
        },
        "status": "ready",
        "stage": 10,
        "requested_at": int(time.time()) - 300,
        "ready_at": int(time.time()) - 200,
        "seconds_to_ready": 40,
        "latest": rep,
        "scans": [{"at": int(time.time()) - 200, "passed": rep["passed"], "total": rep["total"], "compliant": rep["compliant"], "grade": rep["grade"], "findings": rep["extended_summary"]["failed"]}]
    }
    store.put("space", name, space_doc)
    return rep

def test_feature_1_self_healing_cron():
    log_header("TEST 1: SELF-HEALING DAEMON (cron.auto_remediate_all)")
    print("1.1 Creating a degraded space 'cron-test-env' with SQS unencrypted (MSG-1)...")
    init_rep = seed_sample_degraded("cron-test-env", "ops", "dev", "small", "MSG-1")
    print(f"    Initial condition: Grade={init_rep['grade'].upper()}, Compliant={init_rep['compliant']} (Baseline: {init_rep['passed']}/{init_rep['total']})")
    assert not init_rep["compliant"], "Space should initially be non-compliant"

    print("1.2 Running cron.auto_remediate_all() self-healing daemon...")
    enqueued = cron.auto_remediate_all()
    print(f"    Self-healing daemon enqueued {enqueued} reconciliation job(s)")
    assert enqueued >= 1, "Self-healing daemon must enqueue at least 1 job"

    print("1.3 Waiting for worker to process the auto-remediation job...")
    for _ in range(40):
        with urllib.request.urlopen(f"{BASE_URL}/spaces/cron-test-env") as res:
            doc = json.loads(res.read().decode())
            latest = doc.get("latest", {})
            if doc.get("status") == "ready" and latest.get("compliant") is True and latest.get("grade") == "healthy":
                break
        time.sleep(0.5)

    with urllib.request.urlopen(f"{BASE_URL}/spaces/cron-test-env") as res:
        doc = json.loads(res.read().decode())
        latest = doc.get("latest", {})
        grade = latest.get("grade")
        comp = latest.get("compliant")
        print(f"    Post-remediation: Status='{doc.get('status')}', Grade='{grade.upper()}', Compliant={comp} (Baseline: {latest.get('passed')}/{latest.get('total')})")
        assert comp is True, "Environment must be compliant after self-healing"
        assert grade == "healthy", "Grade must be healthy after self-healing"
    print(">>> PASS: Feature 1 (Self-Healing Daemon) verified successfully.")

def test_feature_2_batch_fix_api():
    log_header("TEST 2: BATCH-FIX API (POST /spaces/batch-fix)")
    print("2.1 Creating two degraded spaces: 'batch-test-01' and 'batch-test-02'...")
    seed_sample_degraded("batch-test-01", "team-a", "test", "medium", "STO-1")
    seed_sample_degraded("batch-test-02", "team-b", "prod", "large", "WLS-1")

    print("2.2 Dispatching batch fix with payload: {'names': ['batch-test-01', 'batch-test-02']}...")
    req = urllib.request.Request(
        f"{BASE_URL}/spaces/batch-fix",
        data=json.dumps({"names": ["batch-test-01", "batch-test-02"]}).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": "test", "X-Role": "admin"}
    )
    with urllib.request.urlopen(req) as res:
        assert res.status == 202
        body = json.loads(res.read().decode())
        print(f"    Batch fix response: count={body.get('count')}, enqueued={body.get('enqueued')}")
        assert body.get("count") == 2, "Must enqueue exactly 2 jobs"

    print("2.3 Waiting for worker to reconcile both batch environments...")
    for name in ["batch-test-01", "batch-test-02"]:
        for _ in range(40):
            with urllib.request.urlopen(f"{BASE_URL}/spaces/{name}") as res:
                doc = json.loads(res.read().decode())
                if doc.get("status") == "ready" and doc.get("latest", {}).get("grade") == "healthy":
                    break
            time.sleep(0.5)

    for name in ["batch-test-01", "batch-test-02"]:
        with urllib.request.urlopen(f"{BASE_URL}/spaces/{name}") as res:
            doc = json.loads(res.read().decode())
            latest = doc.get("latest", {})
            print(f"    {name}: Status='{doc.get('status')}', Grade='{latest.get('grade').upper()}', Compliant={latest.get('compliant')}")
            assert latest.get("compliant") is True
            assert latest.get("grade") == "healthy"
    print(">>> PASS: Feature 2 (Batch-Fix API) verified successfully.")

def test_feature_3_drift_diff_and_copy_yaml():
    log_header("TEST 3: DRIFT DIFF & REMEDIATION RENDERING LOGIC")
    print("3.1 Creating 'diff-test-env' with both baseline and extended drift...")
    seed_sample_degraded("diff-test-env", "frontend", "dev", "small", "WLS-5")
    
    with urllib.request.urlopen(f"{BASE_URL}/spaces/diff-test-env") as res:
        doc = json.loads(res.read().decode())
        latest = doc.get("latest", {})
        open_findings = [f for f in latest.get("extended", []) if f["status"] == "fail"]
        print(f"    Inspected live findings count: {len(open_findings)}")
        assert len(open_findings) >= 1, "Should have open extended findings"
        for f in open_findings:
            print(f"    - Finding: {f['id']} | Evidence: '{f['evidence']}'")
            print(f"      Remediation fix provided: '{f['fix']}'")
            assert f["fix"] != "", "Each finding must carry an actionable fix snippet"

    print("3.2 Verifying UI assets contain Drift Diff tab & Copy button markup...")
    with urllib.request.urlopen(f"{BASE_URL}/static/app.js") as res:
        js = res.read().decode()
        assert '["diff", "Drift Diff"]' in js, "Drift Diff tab missing in app.js"
        assert 'function diff(s)' in js, "diff(s) renderer missing in app.js"
        assert 'Copy YAML Remediation' in js, "Copy button missing in app.js"
        assert 'batch-fix-btn' in js, "Batch-fix click handler missing in app.js"
    
    with urllib.request.urlopen(f"{BASE_URL}/static/index.html") as res:
        html = res.read().decode()
        assert 'id="batch-bar"' in html, "Batch action bar missing in index.html"
        assert 'id="select-all-env"' in html, "Select-all checkbox missing in index.html"
        assert 'id="batch-fix-btn"' in html, "Fix selected button missing in index.html"
    print(">>> PASS: Feature 3 (Drift Diff & Copy YAML) verified successfully.")

if __name__ == "__main__":
    test_feature_1_self_healing_cron()
    test_feature_2_batch_fix_api()
    test_feature_3_drift_diff_and_copy_yaml()
    log_header("ALL 3 NEW FEATURES VERIFIED 100% OPERATIONAL")
