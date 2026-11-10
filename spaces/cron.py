"""Scheduled jobs for Render's cron service:  python -m spaces.cron scan-all

Queues one scan per ready environment. It needs only DATABASE_URL: the worker does the scanning.
"""
import sys

from . import server, store


def scan_all():
    n = 0
    for name, sp in store.items("space"):
        if sp.get("status") == "ready":
            server.queue_scan(name, "schedule")
            n += 1
    store.audit("schedule", "scan.all", "", {"queued": n}, "system")
    print(f"queued scans for {n} environment(s)")
    return n


def auto_remediate_all():
    """Scan and automatically trigger blueprint reconciliation on non-compliant environments."""
    reconciled = 0
    for name, sp in store.items("space"):
        req = sp.get("request") or {}
        latest = sp.get("latest") or {}
        # Reconcile if marked auto_remediate or non-compliant/failed
        should_fix = req.get("auto_remediate") or not latest.get("compliant") or sp.get("status") in ("failed", "rejected")
        if should_fix:
            if not store.active_job_for("fix", name) and sp.get("status") != "provisioning":
                store.enqueue("fix", name, {}, actor="self-healing-daemon")
                store.audit("system", "space.auto_remediate", name, {"grade": latest.get("grade")}, "system")
                reconciled += 1
    print(f"self-healing daemon enqueued {reconciled} reconciliation job(s)")
    return reconciled


def main(argv):
    if argv[:1] == ["scan-all"]:
        scan_all()
        return 0
    if argv[:1] == ["auto-remediate"]:
        auto_remediate_all()
        return 0
    print("usage: python -m spaces.cron [scan-all | auto-remediate]", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
