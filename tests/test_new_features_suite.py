"""Comprehensive Unit and Integration tests for all newly implemented features:
1. Decommissioning & Teardown (DELETE /spaces/<name>)
2. Compliance Audit Export (GET /api/compliance/export CSV/JSON)
3. Batch Fix Orchestration (POST /spaces/batch-fix)
4. Self-Healing Daemon (spaces.cron.auto_remediate_all)
5. Core Run Pipeline & Local Fallback Execution
"""
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from spaces import auth, config, controls, checks, core, cron, server, store, worker
from test_auth import AUD, KEY, TEAM, jwk, token

REQ = {"name": "test-space", "team": "qa", "environment": "dev", "size": "small", "admin_groups": ["qa-admins"], "auto_remediate": True}


@pytest.fixture
def app_server(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "test_app.db"))
    monkeypatch.setenv("AUTH_MODE", "cloudflare")
    monkeypatch.setenv("CF_TEAM_DOMAIN", TEAM)
    monkeypatch.setenv("CF_ACCESS_AUD", AUD)
    monkeypatch.setenv("ADMIN_EMAILS", "boss@acme.com")
    monkeypatch.setenv("OPERATOR_EMAILS", "dev@acme.com")
    monkeypatch.setattr(core, "REQ_DIR", str(tmp_path / "req"))
    auth._keys.update(at=0, jwks={})
    monkeypatch.setattr(auth, "_fetch_jwks", lambda d: {"k1": jwk(KEY, "k1")})
    srv = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    yield base
    srv.shutdown()


def req_call(base, path, method="GET", who=None, body=None, csrf=True):
    h = {}
    if who:
        h["Cf-Access-Jwt-Assertion"] = token({"email": who})
    if csrf:
        h["X-Requested-With"] = "console"
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(base + path, data=data, method=method, headers=h)
    try:
        with urllib.request.urlopen(r) as res:
            ct = res.headers.get("Content-Type", "")
            raw = res.read()
            payload = json.loads(raw.decode()) if "json" in ct else raw.decode()
            return res.status, payload, res.headers
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            payload = json.loads(raw.decode())
        except Exception:
            payload = raw.decode()
        return e.code, payload, e.headers


# -----------------------------------------------------------------------------
# 1. UNIT & INTEGRATION TESTS: DELETE /spaces/<name>
# -----------------------------------------------------------------------------

def test_delete_space_rbac_enforcement(app_server):
    store.put("space", "demo-env", {"request": REQ, "status": "ready"})
    
    # Viewer cannot delete (403)
    code, _, _ = req_call(app_server, "/spaces/demo-env", method="DELETE", who="viewer@acme.com")
    assert code == 403

    # Operator cannot delete (403)
    code, _, _ = req_call(app_server, "/spaces/demo-env", method="DELETE", who="dev@acme.com")
    assert code == 403


def test_delete_space_non_existent_404(app_server):
    code, res, _ = req_call(app_server, "/spaces/does-not-exist", method="DELETE", who="boss@acme.com")
    assert code == 404
    assert res["error"] == "not found"


def test_delete_space_active_provisioning_blocked(app_server):
    store.put("space", "building-env", {"request": REQ, "status": "provisioning"})
    code, res, _ = req_call(app_server, "/spaces/building-env", method="DELETE", who="boss@acme.com")
    assert code == 409
    assert "actively provisioning" in res["error"]


def test_delete_space_successful_decommission(app_server):
    store.put("space", "target-env", {"request": REQ, "status": "ready"})
    assert store.get("space", "target-env") is not None

    code, res, _ = req_call(app_server, "/spaces/target-env", method="DELETE", who="boss@acme.com")
    assert code == 200
    assert res["deleted"] is True
    assert res["name"] == "target-env"

    # Confirmed deleted from database
    assert store.get("space", "target-env") is None

    # Confirmed audit log entry
    audits = store.audit_log(5)
    evt = next((a for a in audits if a["action"] == "environment.destroy" and a["target"] == "target-env"), None)
    assert evt is not None
    assert evt["actor"] == "boss@acme.com"


# -----------------------------------------------------------------------------
# 2. UNIT & INTEGRATION TESTS: GET /api/compliance/export (CSV & JSON)
# -----------------------------------------------------------------------------

def test_export_compliance_csv_format(app_server):
    store.put("space", "export-env-1", {
        "request": {"name": "export-env-1", "team": "analytics", "environment": "dev", "size": "small"},
        "status": "ready",
        "latest": {"grade": "healthy", "compliant": True, "passed": 14, "total": 14, "extended_summary": {"failed": 0}}
    })

    code, data, headers = req_call(app_server, "/api/compliance/export?format=csv", who="dev@acme.com")
    assert code == 200
    assert "text/csv" in headers.get("Content-Type", "")
    assert 'attachment; filename="compliance-audit-report.csv"' in headers.get("Content-Disposition", "")
    assert "Environment,Team,Tier,Size,Status,Grade,Compliant" in data
    assert "export-env-1" in data


def test_export_compliance_json_format(app_server):
    store.put("space", "export-env-2", {
        "request": {"name": "export-env-2", "team": "orders", "environment": "prod", "size": "large"},
        "status": "ready",
        "latest": {"grade": "at risk", "compliant": True, "passed": 14, "total": 14, "extended_summary": {"failed": 1}}
    })

    code, data, headers = req_call(app_server, "/api/compliance/export?format=json", who="dev@acme.com")
    assert code == 200
    assert "application/json" in headers.get("Content-Type", "")
    assert isinstance(data, list)
    item = next((x for x in data if x.get("name") == "export-env-2"), None)
    assert item is not None
    assert item["team"] == "orders"
    assert item["latest"]["grade"] == "at risk"


# -----------------------------------------------------------------------------
# 3. UNIT & INTEGRATION TESTS: POST /spaces/batch-fix
# -----------------------------------------------------------------------------

def test_batch_fix_rbac(app_server):
    code, _, _ = req_call(app_server, "/spaces/batch-fix", method="POST", who="dev@acme.com", body={})
    assert code == 403


def test_batch_fix_explicit_names(app_server):
    store.put("space", "bf-1", {"request": REQ, "status": "ready", "latest": {"compliant": False, "grade": "non-compliant"}})
    store.put("space", "bf-2", {"request": REQ, "status": "ready", "latest": {"compliant": False, "grade": "non-compliant"}})

    code, res, _ = req_call(app_server, "/spaces/batch-fix", method="POST", who="boss@acme.com", body={"names": ["bf-1", "bf-2"]})
    assert code == 202
    assert res["count"] == 2
    assert len(res["enqueued"]) == 2
    assert {x["name"] for x in res["enqueued"]} == {"bf-1", "bf-2"}


def test_batch_fix_auto_detect_all_degraded(app_server):
    store.put("space", "healthy-env", {"request": REQ, "status": "ready", "latest": {"compliant": True, "grade": "healthy"}})
    store.put("space", "broken-env", {"request": REQ, "status": "ready", "latest": {"compliant": False, "grade": "non-compliant"}})
    store.put("space", "attention-env", {"request": REQ, "status": "ready", "latest": {"compliant": True, "grade": "needs attention"}})

    # Calling with empty body should find broken-env and attention-env, skipping healthy-env
    code, res, _ = req_call(app_server, "/spaces/batch-fix", method="POST", who="boss@acme.com", body={})
    assert code == 202
    enqueued_names = [x["name"] for x in res["enqueued"]]
    assert "broken-env" in enqueued_names
    assert "attention-env" in enqueued_names
    assert "healthy-env" not in enqueued_names


# -----------------------------------------------------------------------------
# 4. UNIT & INTEGRATION TESTS: cron.auto_remediate_all & core.validate
# -----------------------------------------------------------------------------

def test_core_validate_auto_remediate_flag():
    valid_body = {
        "name": "auto-test",
        "team": "team",
        "environment": "dev",
        "size": "small",
        "admin_groups": ["grp"],
        "auto_remediate": True
    }
    clean, err = core.validate(valid_body)
    assert err is None
    assert clean["auto_remediate"] is True

    valid_default = {
        "name": "auto-test-2",
        "team": "team",
        "environment": "dev",
        "size": "small",
        "admin_groups": ["grp"]
    }
    clean2, err2 = core.validate(valid_default)
    assert err2 is None
    assert clean2["auto_remediate"] is False


def test_cron_auto_remediate_worker_dispatch(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "cron_test.db"))

    store.put("space", "auto-heal-1", {
        "request": {"name": "auto-heal-1", "team": "devops", "environment": "dev", "size": "small", "auto_remediate": True},
        "status": "ready",
        "latest": {"compliant": False, "grade": "non-compliant"}
    })
    store.put("space", "auto-heal-2", {
        "request": {"name": "auto-heal-2", "team": "qa", "environment": "test", "size": "medium", "auto_remediate": False},
        "status": "ready",
        "latest": {"compliant": True, "grade": "healthy"}
    })

    count = cron.auto_remediate_all()
    assert count == 1
    active_fix = store.active_job_for("fix", "auto-heal-1")
    assert active_fix is not None
    assert active_fix["actor"] == "self-healing-daemon"


def test_core_run_pipeline_local_execution(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "ROOT", str(tmp_path))
    req_file = str(tmp_path / "test-env.tfvars")
    with open(req_file, "w") as f:
        f.write('name = "test-env"\n')

    # In local environments without tofu/terraform, run_pipeline smoothly simulates all 10 stages
    monkeypatch.setattr(time, "sleep", lambda s: None)
    ok, stage, log = core.run_pipeline(req_file)
    assert ok is True
    assert stage == 10
    assert "== 1 format" in log
    assert "== 10 metric" in log
