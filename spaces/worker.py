"""Job worker. Runs as its own process on Render (python -m spaces.worker), or as a thread when
EMBEDDED_WORKER=1 (local development).

It holds the cloud credentials; the web service does not.
"""
import os
import signal
import socket
import subprocess
import sys
import threading
import traceback

from . import config, core, store

POLL_SECONDS = 2.0


def bootstrap_runtime():
    """Once per start: log in to the cluster, and fetch the blueprint catalog when one is configured."""
    if not config.is_aws():
        return
    login = os.path.join(config.ROOT, "scripts", "cluster-login.sh")
    p = subprocess.run([login], capture_output=True, text=True)
    print(f"cluster login: {'ok' if p.returncode == 0 else 'FAILED ' + (p.stderr or p.stdout).strip()[-300:]}", flush=True)
    from rollout import catalog
    catalog.sync_remote()


def run_one(worker_id, runner=core.run_pipeline, kinds=None):
    """Claim and run a single job. Returns True if there was one."""
    job = store.claim(worker_id, kinds=kinds)
    if not job:
        return False
    print(f"job {job['id'][:8]} {job['kind']} {job['name'] or ''} started", flush=True)
    try:
        result = core.execute(job, runner=runner)
        store.complete(job["id"], bool(result.get("ok", True)), result)
    except Exception as e:
        traceback.print_exc()
        store.complete(job["id"], False, {"error": str(e)[:500]})
    print(f"job {job['id'][:8]} finished", flush=True)
    return True


def loop(stop, worker_id=None):
    worker_id = worker_id or f"{socket.gethostname()}-{os.getpid()}"
    while not stop.is_set():
        try:
            if not run_one(worker_id):
                stop.wait(POLL_SECONDS)
        except Exception:
            traceback.print_exc()
            stop.wait(POLL_SECONDS * 2)  # database hiccup: back off, keep running


def start_thread():
    stop = threading.Event()
    t = threading.Thread(target=loop, args=(stop,), daemon=True, name="embedded-worker")
    t.start()
    return stop


def main():
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *a: stop.set())
    signal.signal(signal.SIGINT, lambda *a: stop.set())
    bootstrap_runtime()
    print(f"worker started ({config.mode()} mode)", flush=True)
    loop(stop)
    print("worker stopped", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
