"""API tests that do not need the cluster: validation, request files, duplicate handling."""
import os

import pytest
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spaces import core, server, store  # noqa: E402

OK = {"name": "acme-dev", "team": "acme", "environment": "dev", "size": "small", "admin_groups": ["acme-admins"]}


def test_valid_request_accepted():
    req, err = server.validate(OK)
    assert err is None and req["name"] == "acme-dev"


def test_bad_inputs_rejected_with_message():
    for patch, word in [({"name": "Bad_Name"}, "name"), ({"name": ""}, "name"), ({"environment": "staging"}, "environment"),
                        ({"size": "huge"}, "size"), ({"admin_groups": []}, "admin_groups"),
                        ({"admin_groups": [""]}, "admin_groups"), ({"team": "A B"}, "team")]:
        req, err = server.validate({**OK, **patch})
        assert req is None and word in err, patch
    assert server.validate("x")[0] is None


def test_request_file_is_valid_tfvars(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "REQ_DIR", str(tmp_path))
    monkeypatch.setattr(core, "ROOT", str(tmp_path))
    core.write_request(core.validate(OK)[0])
    text = (tmp_path / "acme-dev.tfvars").read_text()
    assert 'name = "acme-dev"' in text and 'admin_groups = ["acme-admins"]' in text


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "api.db"))
    monkeypatch.setenv("AUTH_MODE", "off")


def test_duplicate_space_conflicts_and_queues_one_job(db):
    code, obj = server.create_space(OK, "me")
    assert code == 202 and obj["status"] == "provisioning"
    assert server.create_space(OK, "me")[0] == 409
    assert len(store.recent_jobs()) == 1 and store.recent_jobs()[0]["kind"] == "create"
    assert store.get("space", "acme-dev")["requested_by"] == "me"


def test_one_scan_job_per_space_at_a_time(db):
    a = server.queue_scan("x", "me")
    assert server.queue_scan("x", "you") == a
    store.claim("w")
    store.complete(a, True)
    assert server.queue_scan("x", "me") != a


def test_summary_shape(db):
    server.create_space(OK, "me")
    s = server.summary("acme-dev", store.get("space", "acme-dev"))
    assert s["name"] == "acme-dev" and s["status"] == "provisioning" and s["latest"] == {} and s["team"] == "acme"


def test_scheduled_scan_queues_only_ready_spaces_once(db):
    from spaces import cron
    store.create("space", "a", {"status": "ready"})
    store.create("space", "b", {"status": "provisioning"})
    store.create("space", "c", {"status": "ready"})
    assert cron.scan_all() == 2
    assert cron.scan_all() == 2  # running it again does not pile up duplicate scans
    queued = [j for j in store.recent_jobs() if j["kind"] == "scan"]
    assert sorted(j["name"] for j in queued) == ["a", "c"]
    assert store.audit_log()[0]["action"] == "scan.all"
