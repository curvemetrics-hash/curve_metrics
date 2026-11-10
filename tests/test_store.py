"""Shared state and job queue (SQLite here; the same code runs on Postgres in production)."""
import os
import sys
import threading
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spaces import store  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    # TEST_DATABASE_URL runs the same tests against Postgres (it is wiped first)
    url = os.environ.get("TEST_DATABASE_URL")
    if url:
        monkeypatch.setenv("DATABASE_URL", url)
        with store.db().tx() as c:
            c.run("DELETE FROM kv")
            c.run("DELETE FROM jobs")
    else:
        monkeypatch.delenv("DATABASE_URL", raising=False)
        monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "t.db"))
    yield


def test_put_get_create_update_delete():
    assert store.get("space", "a") is None
    assert store.create("space", "a", {"n": 1}) is True
    assert store.create("space", "a", {"n": 2}) is False  # second create loses
    assert store.get("space", "a") == {"n": 1}
    assert store.update("space", "a", lambda d: d.update(n=5)) == {"n": 5}
    assert store.update("space", "missing", lambda d: None) is None
    assert store.update("space", "new", lambda d: d.update(x=1), create_with={}) == {"x": 1}
    store.delete("space", "a")
    assert store.get("space", "a") is None


def test_concurrent_updates_do_not_lose_writes():
    store.put("space", "c", {"n": 0})

    def bump():
        for _ in range(15):
            store.update("space", "c", lambda d: d.update(n=d["n"] + 1))

    ts = [threading.Thread(target=bump) for _ in range(6)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert store.get("space", "c")["n"] == 90


def test_items_are_ordered():
    for k in "bca":
        store.put("x", k, {"k": k})
    assert [k for k, _ in store.items("x")] == ["a", "b", "c"]
    assert [k for k, _ in store.items("x", newest_first=True, limit=2)] == ["c", "b"]


def test_job_lifecycle():
    jid = store.enqueue("scan", "a", {"x": 1}, actor="me")
    j = store.claim("w1")
    assert j["id"] == jid and j["payload"] == {"x": 1} and j["status"] == "running" and j["attempts"] == 1
    assert store.claim("w2") is None  # nothing left
    store.complete(jid, True, {"ok": 1})
    done = store.job(jid)
    assert done["status"] == "done" and done["result"] == {"ok": 1}


def test_jobs_in_one_exclusive_group_never_overlap():
    a, b = store.enqueue("create", "a"), store.enqueue("fix", "b")
    scan = store.enqueue("scan", "a")
    first = store.claim("w1")
    assert first["id"] == a
    second = store.claim("w2")  # the other provisioning job must wait; the scan may run
    assert second["id"] == scan
    assert store.claim("w3") is None
    store.complete(a, True)
    assert store.claim("w3")["id"] == b


def test_worker_filter_by_kind():
    store.enqueue("rollout", "r")
    assert store.claim("w", kinds=["scan"]) is None
    assert store.claim("w", kinds=["rollout"])["kind"] == "rollout"


def test_lost_worker_job_is_retried_then_abandoned(monkeypatch):
    jid = store.enqueue("scan", "a")
    for attempt in range(1, store.MAX_ATTEMPTS + 1):
        j = store.claim("w")
        assert j and j["attempts"] == attempt
        with store.db().tx() as c:  # simulate a crashed worker: the lease runs out
            c.run("UPDATE jobs SET lease_until=? WHERE id=?", (time.time() - 1, jid))
    assert store.claim("w") is None
    j = store.job(jid)
    assert j["status"] == "failed" and "worker lost" in j["result"]["error"]


def test_audit_is_newest_first():
    store.audit("a@x.com", "create", "env1", role="admin")
    time.sleep(0.01)
    store.audit("b@x.com", "scan", "env1")
    log = store.audit_log()
    assert [e["actor"] for e in log] == ["b@x.com", "a@x.com"] and log[1]["role"] == "admin"
