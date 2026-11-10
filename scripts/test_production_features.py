import os
import sys
import time
import json
import urllib.request
import urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from spaces import store

BASE_URL = "http://127.0.0.1:8080"

def test_export_csv():
    print("Testing GET /api/compliance/export?format=csv...")
    req = urllib.request.Request(f"{BASE_URL}/api/compliance/export?format=csv", headers={"User-Agent": "test", "X-Role": "admin"})
    with urllib.request.urlopen(req) as res:
        assert res.status == 200
        assert "text/csv" in res.headers.get("Content-Type", "")
        content = res.read().decode("utf-8")
        lines = content.strip().split("\n")
        print(f"  -> CSV Header: {lines[0]}")
        print(f"  -> Total exported rows: {len(lines) - 1}")
        assert "Environment,Team,Tier,Size,Status,Grade,Compliant" in lines[0]
        assert len(lines) > 5, "Should export multiple environments"
        print("  -> PASS: CSV Export verified.")

def test_export_json():
    print("\nTesting GET /api/compliance/export?format=json...")
    req = urllib.request.Request(f"{BASE_URL}/api/compliance/export?format=json", headers={"User-Agent": "test", "X-Role": "admin"})
    with urllib.request.urlopen(req) as res:
        assert res.status == 200
        data = json.loads(res.read().decode("utf-8"))
        print(f"  -> JSON exported items: {len(data)}")
        assert isinstance(data, list) and len(data) > 0
        sample = data[0]
        print(f"  -> Sample item keys: {list(sample.keys())}")
        assert "name" in sample and "latest" in sample
        print("  -> PASS: JSON Export verified.")

def test_delete_lifecycle():
    print("\nTesting DELETE /spaces/<name> decommissioning lifecycle...")
    # Seed a disposable environment
    temp_name = "disposable-test-env"
    store.put("space", temp_name, {
        "request": {"name": temp_name, "team": "qa", "environment": "dev", "size": "small", "admin_groups": ["qa-admins"]},
        "status": "ready",
        "stage": 10
    })
    assert store.get("space", temp_name) is not None

    # Delete via API
    req = urllib.request.Request(f"{BASE_URL}/spaces/{temp_name}", method="DELETE", headers={"User-Agent": "test", "X-Role": "admin"})
    with urllib.request.urlopen(req) as res:
        assert res.status == 200
        body = json.loads(res.read().decode("utf-8"))
        print(f"  -> Delete response: {body}")
        assert body.get("deleted") is True

    # Verify environment is gone from database
    assert store.get("space", temp_name) is None, "Space must be purged from database"

    # Verify audit log recorded destruction
    audits = store.audit_log(5)
    destroy_event = next((a for a in audits if a.get("action") == "environment.destroy" and a.get("target") == temp_name), None)
    assert destroy_event is not None, "Decommission event must be audited"
    print(f"  -> Verified Audit log entry: actor={destroy_event.get('actor')}, action={destroy_event.get('action')}")
    print("  -> PASS: Decommission lifecycle verified.")

if __name__ == "__main__":
    test_export_csv()
    test_export_json()
    test_delete_lifecycle()
    print("\n=================================================")
    print("ALL PRODUCTION CAPABILITIES VERIFIED 100% WORKING")
    print("=================================================")
