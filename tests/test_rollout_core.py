"""Rollout decisions, tested with a fake engine (no cluster needed)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rollout import core  # noqa: E402


class Fake:
    def __init__(self, destroys=(), bad_apply=(), bad_verify=(), bad_rollback=()):
        self.destroys, self.bad_apply, self.bad_verify, self.bad_rollback = set(destroys), set(bad_apply), set(bad_verify), set(bad_rollback)
        self.applied = []  # (name, version)

    def plan(self, env, version):
        ch = [{"address": "x.y", "actions": ["delete"]}] if env["name"] in self.destroys else [{"address": "a.b", "actions": ["update"]}]
        return {"add": 0, "change": 0 if env["name"] in self.destroys else 1, "destroy": 1 if env["name"] in self.destroys else 0, "changes": ch}

    def apply(self, env, version):
        self.applied.append((env["name"], version))
        if env["name"] in self.bad_apply and version == "v2":
            raise RuntimeError("provider error")
        return 1.0

    def verify(self, env, version):
        if env["name"] in self.bad_verify and version == "v2":
            return False, ["NET-1: policy missing"]
        if env["name"] in self.bad_rollback and version == "v1":
            return False, ["still broken"]
        return True, []


def envs(n=7):
    return [{"name": f"e{i}", "version": "v1", **({"canary": True} if i == 0 else {})} for i in range(n)]


def run(engine, es=None, **kw):
    pinned = []
    r = core.run_rollout(engine, es or envs(), "v2", on_pinned=lambda e: pinned.append(e["name"]), log=lambda *_: None, **kw)
    return r, pinned


def test_success_updates_every_pin_canary_first():
    f = Fake()
    r, pinned = run(f, batch_size=3)
    assert r["status"] == "completed" and len(pinned) == 7
    assert f.applied[0] == ("e0", "v2")  # canary goes first
    assert [x["stage"] for x in r["records"]][:1] == ["canary"]


def test_nothing_to_do_when_already_current():
    es = [{"name": "a", "version": "v2"}]
    r, _ = run(Fake(), es)
    assert r["status"] == "nothing_to_do"


def test_destroy_in_preview_blocks_before_anything_is_applied():
    f = Fake(destroys=["e3"])
    r, pinned = run(f)
    assert r["status"] == "blocked_by_preview" and r["destroys"] == {"e3": ["x.y"]}
    assert f.applied == [] and pinned == []


def test_destroy_allowed_with_flag():
    r, _ = run(Fake(destroys=["e3"]), allow_destroy=True)
    assert r["status"] == "completed"


def test_canary_failure_rolls_back_and_touches_nothing_else():
    f = Fake(bad_verify=["e0"])
    r, pinned = run(f)
    assert r["status"] == "aborted_at_canary" and pinned == []
    assert f.applied == [("e0", "v2"), ("e0", "v1")]
    assert r["records"][0]["rolled_back"] is True


def test_batch_failure_stops_rollout_and_rolls_back_only_failed_env():
    f = Fake(bad_verify=["e4"])
    r, pinned = run(f, batch_size=3)  # canary e0; batch1 e1-e3; batch2 e4-e6 fails on e4
    assert r["status"] == "stopped_at_batch_2"
    assert ("e4", "v1") in f.applied
    assert "e4" not in pinned and {"e0", "e1", "e2", "e3", "e5", "e6"} <= set(pinned)


def test_batch_failure_leaves_later_batches_untouched():
    f = Fake(bad_verify=["e2"])
    r, pinned = run(f, envs(10), batch_size=3)  # batch1 = e1-e3 fails on e2
    assert r["status"] == "stopped_at_batch_1"
    assert r["not_attempted"] == ["e4", "e5", "e6", "e7", "e8", "e9"]
    assert not any(n in pinned for n in r["not_attempted"])


def test_apply_error_counts_as_failure_and_rolls_back():
    f = Fake(bad_apply=["e0"])
    r, _ = run(f)
    assert r["status"] == "aborted_at_canary" and "provider error" in r["records"][0]["problems"][0]


def test_failed_rollback_is_reported_not_hidden():
    f = Fake(bad_verify=["e0"], bad_rollback=["e0"])
    r, _ = run(f)
    assert r["records"][0]["rolled_back"] is False and r["records"][0]["rollback_problems"]


def test_canary_defaults_to_flagged_env_else_first():
    es = [{"name": "a"}, {"name": "b", "canary": True}]
    assert [e["name"] for e in core.pick_canaries(es)] == ["b"]
    assert [e["name"] for e in core.pick_canaries([{"name": "a"}, {"name": "b"}])] == ["a"]
    assert [e["name"] for e in core.pick_canaries(es, ["a"])] == ["a"]


def test_batches_split_evenly():
    assert [len(b) for b in core.batches(list(range(7)), 3)] == [3, 3, 1]


def test_report_renders_runs_and_escapes_html():
    from rollout import report
    reg = {"environments": [{"name": "a<b", "environment": "dev", "version": "v1"}]}
    runs = [{"version": "v2", "status": "aborted_at_canary", "at": 1, "total_seconds": 3, "targets": ["a"],
             "records": [{"stage": "canary", "name": "a", "ok": False, "seconds": 1, "rolled_back": True, "problems": ["<x>"]}]}]
    page = report.render(reg, runs, {"a<b": "v1"})
    assert "a&lt;b" in page and "&lt;x&gt;" in page and "aborted_at_canary" in page and "<x>" not in page
