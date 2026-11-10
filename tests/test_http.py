"""The running web service, over real HTTP: login, roles, request forgery guard, headers, queue to worker."""
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
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)
from spaces import auth, core, server, store, worker  # noqa: E402
from test_auth import AUD, KEY, TEAM, jwk, token  # noqa: E402

REQ = {"name": "acme-dev", "team": "acme", "environment": "dev", "size": "small", "admin_groups": ["acme-admins"]}


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "h.db"))
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
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def call(base, path, method="GET", who=None, body=None, csrf=True):
    h = {}
    if who:
        h["Cf-Access-Jwt-Assertion"] = token({"email": who})
    if csrf:
        h["X-Requested-With"] = "console"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(base + path, data=data, method=method, headers=h)
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read() or b"{}") if "json" in r.headers.get("Content-Type", "") else r.read(), r.headers
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}"), e.headers


def test_health_is_open_everything_else_needs_login(app):
    assert call(app, "/healthz")[0] == 200
    for path in ("/", "/spaces", "/rollout", "/api/me", "/jobs", "/static/app.js"):
        assert call(app, path)[0] == 401, path


def test_forged_token_is_refused(app):
    from test_auth import OTHER
    req = urllib.request.Request(app + "/spaces", headers={"Cf-Access-Jwt-Assertion": token(key=OTHER)})  # signed by the wrong key
    with pytest.raises(urllib.error.HTTPError) as e:
        urllib.request.urlopen(req)
    assert e.value.code == 401


def test_roles_gate_every_action(app):
    assert call(app, "/spaces", who="rando@acme.com")[0] == 200  # viewer can read
    assert call(app, "/spaces", "POST", "rando@acme.com", REQ)[0] == 403  # but not request
    assert call(app, "/spaces", "POST", "dev@acme.com", REQ)[0] == 202  # operator can
    assert call(app, "/spaces/acme-dev/fix", "POST", "dev@acme.com")[0] == 403  # re-apply is admin only
    assert call(app, "/rollout/start", "POST", "dev@acme.com", {"version": "v1.2.3"})[0] == 403
    assert call(app, "/rollout/preview", "POST", "dev@acme.com", {"version": "v1.2.3"})[0] == 202
    assert call(app, "/audit", who="dev@acme.com")[0] == 403
    assert call(app, "/audit", who="boss@acme.com")[0] == 200
    assert call(app, "/rollout/registry", "PUT", "dev@acme.com", {})[0] == 403


def test_missing_csrf_header_blocks_writes(app):
    assert call(app, "/spaces", "POST", "dev@acme.com", REQ, csrf=False)[0] == 403
    assert call(app, "/spaces", who="dev@acme.com", csrf=False)[0] == 200  # reads do not need it


def test_security_headers_and_no_store(app):
    _, _, h = call(app, "/spaces", who="dev@acme.com")
    assert "script-src 'self'" in h["Content-Security-Policy"] and h["X-Frame-Options"] == "DENY"
    assert h["X-Content-Type-Options"] == "nosniff" and h["Cache-Control"] == "no-store"
    code, page, h = call(app, "/", who="dev@acme.com")
    assert code == 200 and b"Platform Console" in page and "text/html" in h["Content-Type"]


def test_static_path_traversal_is_not_served(app):
    for p in ("/static/../server.py", "/static/..%2fserver.py", "/static/app.js/../../config.py", "/static/nothing.js"):
        assert call(app, p, who="dev@acme.com")[0] == 404, p


def test_create_validation_and_audit(app):
    assert call(app, "/spaces", "POST", "dev@acme.com", {**REQ, "name": "Bad Name"})[0] == 400
    code, obj, _ = call(app, "/spaces", "POST", "dev@acme.com", REQ)
    assert code == 202 and obj["job"]
    assert call(app, "/spaces", "POST", "dev@acme.com", REQ)[0] == 409
    log = call(app, "/audit", who="boss@acme.com")[1]
    assert log[0]["action"] == "environment.create" and log[0]["actor"] == "dev@acme.com" and log[0]["role"] == "operator"


def test_oversized_and_invalid_bodies(app):
    req = urllib.request.Request(app + "/spaces", data=b"x" * 70000, method="POST",
                                 headers={"Cf-Access-Jwt-Assertion": token({"email": "dev@acme.com"}), "X-Requested-With": "console"})
    with pytest.raises(urllib.error.HTTPError) as e:
        urllib.request.urlopen(req)
    assert e.value.code == 400
    assert call(app, "/rollout/start", "POST", "boss@acme.com", {"version": "latest; rm -rf /"})[0] == 400


def test_request_flows_through_queue_to_worker(app, monkeypatch):
    """create -> job -> worker runs the (fake) pipeline -> environment is ready -> scan with ?wait=."""
    fake_report = {"grade": "healthy", "passed": 14, "total": 14, "compliant": True, "controls": [], "extended": [],
                   "extended_summary": {"failed": 0, "total": 0, "passed": 0, "na": 0, "unknown": 0, "severity": {"high": 0, "medium": 0, "low": 0}}}

    def fake_scan(name):
        store.update("space", name, lambda d: d.update(latest={**fake_report, "at": int(time.time())}))
        return fake_report

    monkeypatch.setattr(core, "scan", fake_scan)
    code, obj, _ = call(app, "/spaces", "POST", "dev@acme.com", REQ)
    assert code == 202
    assert worker.run_one("t", runner=lambda rel: (True, 10, "ok")) is True
    sp = call(app, "/spaces/acme-dev", who="dev@acme.com")[1]
    assert sp["status"] == "ready" and sp["seconds_to_ready"] >= 0
    assert os.path.exists(os.path.join(core.REQ_DIR, "acme-dev.tfvars"))  # the worker wrote the request file

    t = threading.Thread(target=lambda: (time.sleep(0.6), worker.run_one("t2")))
    t.start()
    code, rep, _ = call(app, "/spaces/acme-dev/scan?wait=20", "POST", "dev@acme.com")
    t.join()
    assert code == 200 and rep["grade"] == "healthy"


def test_policy_rejection_is_recorded(app):
    call(app, "/spaces", "POST", "dev@acme.com", {**REQ, "name": "evil-dev"})
    worker.run_one("t", runner=lambda rel: (False, 6, "policy: wildcard admin"))
    sp = call(app, "/spaces/evil-dev", who="dev@acme.com")[1]
    assert sp["status"] == "rejected" and sp["failed_stage"] == 6 and "wildcard" in sp["log"]
    job = call(app, "/jobs", who="dev@acme.com")[1][0]
    assert job["status"] == "failed"


def test_failed_scan_job_returns_502(app, monkeypatch):
    call(app, "/spaces", "POST", "dev@acme.com", REQ)
    store.update("space", "acme-dev", lambda d: d.update(status="ready"))
    monkeypatch.setattr(core, "scan", lambda n: (_ for _ in ()).throw(RuntimeError("cluster unreachable")))
    worker.run_one("t", runner=lambda rel: (True, 10, ""))  # drain the create job
    threading.Thread(target=lambda: (time.sleep(0.5), worker.run_one("t2"))).start()
    code, obj, _ = call(app, "/spaces/acme-dev/scan?wait=20", "POST", "dev@acme.com")
    assert code == 502 and "unreachable" in obj["error"]


def test_startup_refuses_unsafe_config(monkeypatch):
    from spaces import config
    monkeypatch.setenv("AUTH_MODE", "off")
    monkeypatch.setenv("HOST", "0.0.0.0")
    assert any("AUTH_MODE=off" in p for p in config.check_startup())
    monkeypatch.setenv("AUTH_MODE", "cloudflare")
    monkeypatch.delenv("CF_TEAM_DOMAIN", raising=False)
    assert any("CF_TEAM_DOMAIN" in p for p in config.check_startup())
    monkeypatch.setenv("PLATFORM_MODE", "aws")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert any("DATABASE_URL" in p for p in config.check_startup())
