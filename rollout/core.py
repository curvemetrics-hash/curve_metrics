"""Rollout orchestration. Pure logic over an engine, so every decision can be unit tested.

Flow for `rollout <version>`:
  1. preview every environment that is not on <version>
  2. stop if any preview destroys something (unless allow_destroy)
  3. canary environment(s): apply, verify; on failure roll the canary back and stop
  4. remaining environments in batches: apply, verify; on failure roll the failed ones back and stop
An environment's pin in the registry moves only after it passes verification.
"""
import time
from concurrent.futures import ThreadPoolExecutor


def pick_canaries(targets, names=None):
    if names:
        chosen = [e for e in targets if e["name"] in names]
    else:
        chosen = [e for e in targets if e.get("canary")] or targets[:1]
    return chosen


def batches(envs, size):
    return [envs[i:i + size] for i in range(0, len(envs), size)]


def _step(engine, env, version, previous):
    """Apply + verify one environment; roll back on failure. Returns a record."""
    rec = {"name": env["name"], "from": previous, "to": version}
    t0 = time.time()
    try:
        rec["apply_seconds"] = engine.apply(env, version)
        ok, problems = engine.verify(env, version)
    except Exception as e:  # apply or verification could not complete
        ok, problems = False, [f"error: {e}"]
    rec["ok"], rec["problems"] = ok, problems
    if not ok and previous:
        try:
            engine.apply(env, previous)
            back_ok, back_problems = engine.verify(env, previous)
            rec["rolled_back"] = back_ok
            if not back_ok:
                rec["rollback_problems"] = back_problems
        except Exception as e:
            rec["rolled_back"] = False
            rec["rollback_problems"] = [f"error: {e}"]
    rec["seconds"] = round(time.time() - t0, 1)
    return rec


def run_rollout(engine, envs, version, *, canary=None, batch_size=3, allow_destroy=False,
                parallel=5, on_pinned=None, log=print):
    started = time.time()
    targets = [e for e in envs if e.get("version") != version]
    result = {"version": version, "targets": [e["name"] for e in targets], "preview": {}, "records": []}
    if not targets:
        result["status"] = "nothing_to_do"
        return _finish(result, started)

    log(f"preview for {len(targets)} environment(s)")
    with ThreadPoolExecutor(max_workers=parallel) as ex:
        plans = list(ex.map(lambda e: engine.plan(e, version), targets))
    result["preview"] = {e["name"]: p for e, p in zip(targets, plans)}
    destroys = {n: [c["address"] for c in p["changes"] if "delete" in c["actions"]]
                for n, p in result["preview"].items() if p["destroy"]}
    if destroys and not allow_destroy:
        result["status"] = "blocked_by_preview"
        result["destroys"] = destroys
        return _finish(result, started)

    def settle(env, rec):
        result["records"].append(rec)
        if rec["ok"]:
            env["version"] = version
            if on_pinned:
                on_pinned(env)

    first = pick_canaries(targets, canary)
    log(f"canary: {', '.join(e['name'] for e in first)}")
    for env in first:
        rec = _step(engine, env, version, env.get("version"))
        rec["stage"] = "canary"
        settle(env, rec)
        if not rec["ok"]:
            result["status"] = "aborted_at_canary"
            return _finish(result, started)

    rest = [e for e in targets if e not in first]
    for i, group in enumerate(batches(rest, batch_size), 1):
        log(f"batch {i}: {', '.join(e['name'] for e in group)}")
        with ThreadPoolExecutor(max_workers=parallel) as ex:
            recs = list(ex.map(lambda e: _step(engine, e, version, e.get("version")), group))
        for env, rec in zip(group, recs):
            rec["stage"] = f"batch {i}"
            settle(env, rec)
        if not all(r["ok"] for r in recs):
            result["status"] = f"stopped_at_batch_{i}"
            result["not_attempted"] = [e["name"] for g in batches(rest, batch_size)[i:] for e in g]
            return _finish(result, started)
    result["status"] = "completed"
    return _finish(result, started)


def _finish(result, started):
    result["total_seconds"] = round(time.time() - started, 1)
    return result
