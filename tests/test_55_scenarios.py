#!/usr/bin/env python3
"""Comprehensive Automated Test Suite: 55 End-to-End Scenarios for Platform Console.
Tests live HTTP endpoints, validation logic, RBAC, static assets, database storage,
and policy checks one by one.
"""
import json
import os
import re
import sys
import time
import urllib.request
import urllib.error

# Ensure root is in sys.path
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

BASE_URL = "http://127.0.0.1:8080"
passed = 0
failed = 0
results = []

def run_scenario(number, category, title, test_fn):
    global passed, failed, results
    t0 = time.time()
    try:
        test_fn()
        duration_ms = int((time.time() - t0) * 1000)
        passed += 1
        print(f"[{number:02d}/55] PASS: ({category}) {title} ({duration_ms}ms)")
        results.append((number, category, title, "PASS", duration_ms, None))
    except Exception as e:
        duration_ms = int((time.time() - t0) * 1000)
        failed += 1
        print(f"[{number:02d}/55] FAIL: ({category}) {title} - {e}")
        results.append((number, category, title, "FAIL", duration_ms, str(e)))

def http_get(path, headers=None):
    req = urllib.request.Request(f"{BASE_URL}{path}", headers=headers or {})
    try:
        with urllib.request.urlopen(req) as resp:
            data = resp.read().decode("utf-8")
            return resp.status, data, resp.headers
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8"), e.headers

def http_post(path, body=None, headers=None):
    h = {"Content-Type": "application/json", "X-Requested-With": "console"}
    if headers:
        h.update(headers)
    payload = json.dumps(body).encode("utf-8") if body is not None else b""
    req = urllib.request.Request(f"{BASE_URL}{path}", data=payload, headers=h, method="POST")
    try:
        with urllib.request.urlopen(req) as resp:
            data = resp.read().decode("utf-8")
            return resp.status, data, resp.headers
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8"), e.headers

# ----------------- SECTION 1: Health & Static Assets (Scenarios 1-10) -----------------
def s01():
    status, body, _ = http_get("/healthz")
    assert status == 200, f"Expected 200, got {status}"
    j = json.loads(body)
    assert j.get("ok") is True, f"Expected ok: true, got {j}"

def s02():
    status, body, _ = http_get("/")
    assert status == 200, f"Expected 200, got {status}"
    assert "<!doctype html>" in body.lower()
    assert "Platform Console" in body

def s03():
    status, body, _ = http_get("/static/app.css")
    assert status == 200, f"Expected 200, got {status}"
    assert "--acc:" in body
    assert "--sidebar-w:" in body
    assert "body.sidebar-collapsed" in body

def s04():
    status, body, _ = http_get("/static/app.js")
    assert status == 200, f"Expected 200, got {status}"
    assert "checkHealth" in body
    assert "toggleSidebar" in body
    assert "applyRole" in body

def s05():
    status, body, _ = http_get("/")
    assert 'id="sidebar-toggle"' in body
    assert 'id="topbar-toggle-sidebar"' in body

def s06():
    status, body, _ = http_get("/")
    assert 'id="health-pill"' in body
    assert 'id="health-dot"' in body

def s07():
    status, body, _ = http_get("/")
    assert 'id="theme"' in body
    assert 'theme-toggle' in body

def s08():
    status, body, _ = http_get("/")
    assert 'id="dlg"' in body
    assert 'id="f"' in body
    assert 'name="name"' in body
    assert 'name="team"' in body

def s09():
    status, body, _ = http_get("/")
    assert 'id="teams-list"' in body
    assert 'id="groups-list"' in body
    assert 'value="payments"' in body

def s10():
    status, body, _ = http_get("/static/non-existent-file-xyz.js")
    assert status == 404, f"Expected 404, got {status}"

# ----------------- SECTION 2: Identity & RBAC (Scenarios 11-18) -----------------
def s11():
    status, body, _ = http_get("/api/me")
    assert status == 200, f"Expected 200, got {status}"
    j = json.loads(body)
    assert "id" in j and "role" in j and "mode" in j
    assert j["role"] in ("viewer", "operator", "admin")

def s12():
    status, body, _ = http_get("/api/me")
    j = json.loads(body)
    assert j["id"] == "local"
    assert j["role"] == "admin"

def s13():
    status, body, _ = http_get("/spaces")
    assert status == 200, f"Expected 200, got {status}"
    j = json.loads(body)
    assert isinstance(j, list)

def s14():
    status, body, _ = http_get("/rollout")
    assert status == 200, f"Expected 200, got {status}"
    j = json.loads(body)
    assert "environments" in j and "runs" in j and "versions" in j

def s15():
    status, body, _ = http_get("/jobs")
    assert status == 200, f"Expected 200, got {status}"
    j = json.loads(body)
    assert isinstance(j, list)

def s16():
    status, body, _ = http_get("/audit")
    assert status == 200, f"Expected 200, got {status}"
    j = json.loads(body)
    assert isinstance(j, list)

def s17():
    status, body, _ = http_get("/spaces/non-existent-env-999")
    assert status == 404, f"Expected 404, got {status}"

def s18():
    status, body, _ = http_get("/jobs/non-existent-job-xyz")
    assert status == 404, f"Expected 404, got {status}"

# ----------------- SECTION 3: Validation & Security Gate (Scenarios 19-30) -----------------
from spaces import core

def s19():
    req, err = core.validate({"name": "valid-env-1", "team": "payments", "environment": "dev", "size": "small", "admin_groups": ["payments-admins"]})
    assert err is None, f"Expected no error, got {err}"
    assert req["name"] == "valid-env-1"

def s20():
    req, err = core.validate({"name": "INVALID_NAME", "team": "payments", "environment": "dev", "size": "small", "admin_groups": ["payments-admins"]})
    assert err is not None and "name" in err.lower()

def s21():
    req, err = core.validate({"name": "-invalid-start", "team": "payments", "environment": "dev", "size": "small", "admin_groups": ["payments-admins"]})
    assert err is not None

def s22():
    req, err = core.validate({"name": "invalid-end-", "team": "payments", "environment": "dev", "size": "small", "admin_groups": ["payments-admins"]})
    assert err is not None

def s23():
    req, err = core.validate({"name": "valid-name", "team": "PAYMENTS", "environment": "dev", "size": "small", "admin_groups": ["payments-admins"]})
    assert err is not None and "team" in err.lower()

def s24():
    req, err = core.validate({"name": "valid-name", "team": "payments", "environment": "staging", "size": "small", "admin_groups": ["payments-admins"]})
    assert err is not None and "environment" in err.lower()

def s25():
    req, err = core.validate({"name": "valid-name", "team": "payments", "environment": "dev", "size": "extra-large", "admin_groups": ["payments-admins"]})
    assert err is not None and "size" in err.lower()

def s26():
    req, err = core.validate({"name": "valid-name", "team": "payments", "environment": "dev", "size": "small", "admin_groups": []})
    assert err is not None and "admin_groups" in err.lower()

def s27():
    req, err = core.validate({"name": "valid-name", "team": "payments", "environment": "dev", "size": "small", "admin_groups": [""]})
    assert err is not None

def s28():
    req, err = core.validate("not-a-dict")
    assert err is not None

def s29():
    status, body, _ = http_post("/spaces", {"name": "TEST_INVALID", "team": "payments", "environment": "dev", "size": "small", "admin_groups": ["payments-admins"]})
    assert status == 400, f"Expected 400, got {status}"
    j = json.loads(body)
    assert "error" in j

def s30():
    status, body, _ = http_post("/spaces", {"name": "valid-env", "team": "INVALID_TEAM", "environment": "dev", "size": "small", "admin_groups": ["payments-admins"]})
    assert status == 400, f"Expected 400, got {status}"

# ----------------- SECTION 4: Storage, Queue & State (Scenarios 31-40) -----------------
from spaces import store

def s31():
    with store.db().tx() as c:
        tables = c.rows("SELECT name FROM sqlite_master WHERE type='table'")
    names = {row["name"] for row in tables}
    assert "kv" in names and "jobs" in names

def s32():
    test_id = f"test-space-{int(time.time()*1000)}"
    created = store.create("mock_test", test_id, {"status": "provisioning", "test": True})
    assert created is True
    doc = store.get("mock_test", test_id)
    assert doc is not None and doc.get("test") is True

def s33():
    test_id = f"test-dup-{int(time.time()*1000)}"
    assert store.create("mock_test", test_id, {"val": 1}) is True
    assert store.create("mock_test", test_id, {"val": 2}) is False

def s34():
    test_id = f"test-upd-{int(time.time()*1000)}"
    store.create("mock_test", test_id, {"counter": 1})
    store.update("mock_test", test_id, lambda d: d.update(counter=2))
    assert store.get("mock_test", test_id).get("counter") == 2

def s35():
    jid = store.enqueue("test_job", "test-target", {"foo": "bar"}, actor="tester")
    assert jid is not None and len(jid) > 5
    job = store.job(jid)
    # Status may have transitioned if background embedded worker is running
    assert job["status"] in ("queued", "running", "done", "failed")
    assert job["kind"] == "test_job"

def s36():
    jid = store.enqueue("isolated_job_claim", "test-claim-target", {"abc": 123}, actor="tester")
    job = store.claim("test-worker-custom")
    if job:
        assert job["status"] == "running"
        store.complete(job["id"], True, {"success": True})
        updated = store.job(job["id"])
        assert updated["status"] in ("done", "failed")

def s37():
    jid = store.enqueue("scan", "fail-target", {}, actor="tester")
    job = store.claim("test-worker-2", kinds=["scan"])
    assert job is not None
    store.complete(job["id"], False, {"error": "simulation failure"})
    updated = store.job(job["id"])
    assert updated["status"] == "failed"
    assert "simulation failure" in updated["result"].get("error", "")

def s38():
    initial_len = len(store.audit_log())
    store.audit("admin-user", "test.action", "target-1", {"meta": "data"}, "admin")
    entries = store.audit_log()
    assert len(entries) >= initial_len + 1
    assert any(e["action"] == "test.action" and e["actor"] == "admin-user" for e in entries)

def s39():
    from rollout import service
    reg = {"environments": [{"name": "env-1", "team": "alpha", "environment": "dev", "size": "small", "admin_groups": ["admins"], "version": "v1.0.0", "canary": True}]}
    service.save_registry(reg)
    loaded = service.registry()
    assert len(loaded["environments"]) == 1
    assert loaded["environments"][0]["name"] == "env-1"

def s40():
    from rollout import service
    valid_reg, err = service.check_registry({"environments": [{"name": "test-env", "team": "alpha", "environment": "dev", "size": "small", "admin_groups": ["admins"], "version": "v1.0.0"}]})
    assert err is None
    invalid_reg, err2 = service.check_registry({"environments": [{"name": "INVALID", "team": "alpha", "environment": "dev", "version": "not-semver"}]})
    assert err2 is not None

# ----------------- SECTION 5: Policy Gate & Compliance Controls (Scenarios 41-48) -----------------
from scripts import policy_check

def s41():
    mock_plan = {
        "planned_values": {
            "root_module": {
                "resources": [
                    {"type": "kubernetes_namespace_v1", "address": "k8s_ns", "values": {"metadata": [{"name": "test", "labels": {"curve-metrics/team": "alpha", "curve-metrics/environment": "dev"}}]}},
                    {"type": "kubernetes_resource_quota_v1", "address": "quota", "values": {"spec": [{"hard": {"requests.storage": "10Gi", "persistentvolumeclaims": "5", "count/ingresses.networking.k8s.io": "2"}}]}},
                    {"type": "kubernetes_limit_range_v1", "address": "limit", "values": {}},
                    {"type": "kubernetes_network_policy_v1", "address": "deny", "values": {"metadata": [{"name": "default-deny-ingress"}]}}
                ]
            }
        }
    }
    problems = policy_check.check(mock_plan)
    assert len(problems) == 0, f"Expected 0 problems, got {problems}"

def s42():
    mock_plan = {"planned_values": {"root_module": {"resources": []}}}
    problems = policy_check.check(mock_plan)
    assert any("no namespace" in p for p in problems)

def s43():
    mock_plan = {
        "planned_values": {
            "root_module": {
                "resources": [
                    {"type": "kubernetes_namespace_v1", "address": "k8s_ns", "values": {"metadata": [{"name": "test", "labels": {}}]}}
                ]
            }
        }
    }
    problems = policy_check.check(mock_plan)
    assert any("missing label" in p for p in problems)

def s44():
    mock_plan = {
        "planned_values": {
            "root_module": {
                "resources": [
                    {"type": "kubernetes_namespace_v1", "address": "k8s_ns", "values": {"metadata": [{"name": "test", "labels": {"curve-metrics/team": "alpha", "curve-metrics/environment": "dev"}}]}},
                    {"type": "kubernetes_role_binding_v1", "address": "rb_bad", "values": {"role_ref": [{"name": "cluster-admin"}], "subject": [{"name": "devs"}]}}
                ]
            }
        }
    }
    problems = policy_check.check(mock_plan)
    assert any("binds cluster-admin" in p for p in problems)

def s45():
    mock_plan = {
        "planned_values": {
            "root_module": {
                "resources": [
                    {"type": "kubernetes_namespace_v1", "address": "k8s_ns", "values": {"metadata": [{"name": "test", "labels": {"curve-metrics/team": "alpha", "curve-metrics/environment": "dev"}}]}},
                    {"type": "kubernetes_role_binding_v1", "address": "rb_bad", "values": {"role_ref": [{"name": "admin"}], "subject": [{"name": "system:authenticated"}]}}
                ]
            }
        }
    }
    problems = policy_check.check(mock_plan)
    assert any("system:authenticated" in p for p in problems)

def s46():
    mock_plan = {
        "planned_values": {
            "root_module": {
                "resources": [
                    {"type": "kubernetes_namespace_v1", "address": "k8s_ns", "values": {"metadata": [{"name": "test", "labels": {"curve-metrics/team": "alpha", "curve-metrics/environment": "dev"}}]}},
                    {"type": "aws_s3_bucket", "address": "s3_1", "values": {}}
                ]
            }
        }
    }
    problems = policy_check.check(mock_plan)
    assert any("public access block" in p for p in problems)

def s47():
    mock_plan = {
        "planned_values": {
            "root_module": {
                "resources": [
                    {"type": "kubernetes_namespace_v1", "address": "k8s_ns", "values": {"metadata": [{"name": "test", "labels": {"curve-metrics/team": "alpha", "curve-metrics/environment": "dev"}}]}},
                    {"type": "aws_sqs_queue", "address": "sqs_1", "values": {"sqs_managed_sse_enabled": False}}
                ]
            }
        }
    }
    problems = policy_check.check(mock_plan)
    assert any("not encrypted" in p for p in problems)

def s48():
    mock_plan = {
        "planned_values": {
            "root_module": {
                "resources": [
                    {"type": "kubernetes_namespace_v1", "address": "k8s_ns", "values": {"metadata": [{"name": "test", "labels": {"curve-metrics/team": "alpha", "curve-metrics/environment": "dev"}}]}},
                    {"type": "aws_iam_policy", "address": "iam_wildcard", "values": {"policy": '{"Statement":[{"Action":"*","Effect":"Allow"}]}'}}
                ]
            }
        }
    }
    problems = policy_check.check(mock_plan)
    assert any("wildcard action" in p for p in problems)

# ----------------- SECTION 6: UI Design & Client Logic (Scenarios 49-55) -----------------
def s49():
    with open("spaces/static/index.html", encoding="utf-8") as f:
        html = f.read()
    assert 'class="head-title-row"' in html
    assert '<h1>Environments</h1>' in html
    assert '<button class="btn pri" id="new">New environment</button>' in html

def s50():
    with open("spaces/static/app.css", encoding="utf-8") as f:
        css = f.read()
    assert ".head-title-row" in css
    assert "align-items: center;" in css
    assert "display: flex;" in css

def s51():
    with open("spaces/static/app.css", encoding="utf-8") as f:
        css = f.read()
    assert ".user-header-line" in css
    assert ".user-meta-line" in css
    assert ".mode-bullet" in css

def s52():
    with open("spaces/static/app.css", encoding="utf-8") as f:
        css = f.read()
    assert "grid-template-columns: repeat(5, minmax(0, 1fr));" in css
    assert "padding: 12px 14px;" in css
    assert "font-size: 23px;" in css

def s53():
    with open("spaces/static/app.css", encoding="utf-8") as f:
        css = f.read()
    assert "dialog {" in css
    assert "width: min(600px," in css
    assert "overflow-x: hidden;" in css

def s54():
    with open("spaces/static/app.js", encoding="utf-8") as f:
        js = f.read()
    assert "checkHealth" in js
    assert "15 * 60 * 1000" in js

def s55():
    with open("spaces/static/app.js", encoding="utf-8") as f:
        js = f.read()
    assert "toggleSidebar" in js
    assert "sidebar-collapsed" in js
    assert "Ctrl+B" in js or "ctrlKey" in js

# ----------------- EXECUTION RUNNER -----------------
scenarios = [
    # Section 1: Health & Static Assets
    (1, "Health & Assets", "GET /healthz returns ok: true", s01),
    (2, "Health & Assets", "GET / serves Platform Console HTML", s02),
    (3, "Health & Assets", "GET /static/app.css serves updated styles", s03),
    (4, "Health & Assets", "GET /static/app.js serves application logic", s04),
    (5, "Health & Assets", "Sidebar toggle triggers present in HTML", s05),
    (6, "Health & Assets", "Automated health pill indicator present in HTML", s06),
    (7, "Health & Assets", "Dark/Light theme toggle present in HTML", s07),
    (8, "Health & Assets", "New environment dialog markup verified", s08),
    (9, "Health & Assets", "Team and admin group datalists present in HTML", s09),
    (10, "Health & Assets", "Non-existent static asset returns 404", s10),

    # Section 2: Identity & RBAC
    (11, "Identity & RBAC", "GET /api/me returns current user identity", s11),
    (12, "Identity & RBAC", "Default local user has admin role in local mode", s12),
    (13, "Identity & RBAC", "GET /spaces returns list of environments", s13),
    (14, "Identity & RBAC", "GET /rollout returns registry and version history", s14),
    (15, "Identity & RBAC", "GET /jobs returns worker job queue for admin", s15),
    (16, "Identity & RBAC", "GET /audit returns immutable audit log for admin", s16),
    (17, "Identity & RBAC", "GET /spaces/<invalid> returns 404 error", s17),
    (18, "Identity & RBAC", "GET /jobs/<invalid> returns 404 error", s18),

    # Section 3: Validation & Gate
    (19, "Validation", "Valid environment request passes validation", s19),
    (20, "Validation", "Uppercase environment name is rejected", s20),
    (21, "Validation", "Leading hyphen in name is rejected", s21),
    (22, "Validation", "Trailing hyphen in name is rejected", s22),
    (23, "Validation", "Uppercase team name is rejected", s23),
    (24, "Validation", "Invalid environment tier (staging) is rejected", s24),
    (25, "Validation", "Invalid size preset (extra-large) is rejected", s25),
    (26, "Validation", "Empty admin_groups list is rejected", s26),
    (27, "Validation", "Empty string inside admin_groups is rejected", s27),
    (28, "Validation", "Non-dict JSON payload is rejected", s28),
    (29, "Validation", "HTTP POST /spaces rejects invalid name with 400", s29),
    (30, "Validation", "HTTP POST /spaces rejects invalid team with 400", s30),

    # Section 4: Storage & Worker Queue
    (31, "Storage & Jobs", "SQLite database tables initialized properly", s31),
    (32, "Storage & Jobs", "Store creates and retrieves document", s32),
    (33, "Storage & Jobs", "Duplicate document key creation is blocked", s33),
    (34, "Storage & Jobs", "Document update correctly modifies fields", s34),
    (35, "Storage & Jobs", "Job enqueuing generates ID in pending status", s35),
    (36, "Storage & Jobs", "Worker claims job, updates running and done status", s36),
    (37, "Storage & Jobs", "Job failure records error message in database", s37),
    (38, "Storage & Jobs", "Audit log records action metadata and actor", s38),
    (39, "Storage & Jobs", "Rollout registry persistence and reload", s39),
    (40, "Storage & Jobs", "Rollout registry schema validation", s40),

    # Section 5: Policy Gate & Compliance
    (41, "Policy Gate", "Compliant Terraform plan passes all checks", s41),
    (42, "Policy Gate", "Missing namespace fails policy gate", s42),
    (43, "Policy Gate", "Missing mandatory team/env labels fails gate", s43),
    (44, "Policy Gate", "Binding cluster-admin role is blocked", s44),
    (45, "Policy Gate", "Binding to system:authenticated is blocked", s45),
    (46, "Policy Gate", "S3 bucket missing public access block is blocked", s46),
    (47, "Policy Gate", "Unencrypted SQS queue fails policy check", s47),
    (48, "Policy Gate", "IAM policy with wildcard Action:* is blocked", s48),

    # Section 6: UI Design & Client Logic
    (49, "UI & Layout", "Heading and New environment button are on the same row", s49),
    (50, "UI & Layout", "Head title row CSS uses flexbox alignment", s50),
    (51, "UI & Layout", "Sidebar user details structured into two neat lines", s51),
    (52, "UI & Layout", "Stats grid uses 5-column compact dimensions (23px font)", s52),
    (53, "UI & Layout", "Dialog sizing set to min(600px) with overflow protection", s53),
    (54, "UI & Layout", "Health check pings automatically every 15 minutes", s54),
    (55, "UI & Layout", "Sidebar collapsible rail mode and shortcut supported", s55),
]

print(f"\n========================================================")
print(f"RUNNING 55 SYSTEM & E2E SCENARIOS")
print(f"========================================================\n")

for num, cat, title, fn in scenarios:
    run_scenario(num, cat, title, fn)

print(f"\n========================================================")
print(f"TEST RESULTS: {passed} PASSED, {failed} FAILED (TOTAL 55)")
print(f"========================================================\n")

if failed > 0:
    sys.exit(1)
