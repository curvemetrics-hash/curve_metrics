"""Shared state: documents, a job queue and an audit log, in SQLite (local) or Postgres (Render).

The web service and the worker are separate processes, so everything they share lives here.
Documents are JSON text in one table, keyed by (namespace, key). Namespaces in use:
  space            one document per environment (request, status, scans, results)
  rollout_registry one document, key 'registry'
  rollout_run      one document per finished rollout
  audit            one document per action, key sorted by time
"""
import contextlib
import json
import os
import sqlite3
import threading
import time
import uuid

from . import config

# jobs of the same group never run at the same time (they share a working directory or a state lock)
EXCLUSIVE = {"create": "provision", "fix": "provision", "rollout": "rollout", "preview": "rollout"}
LEASE_SECONDS = {"rollout": 3600, "preview": 1800, "create": 1200, "fix": 1200, "scan": 300}
MAX_ATTEMPTS = 3

SCHEMA = [
    "CREATE TABLE IF NOT EXISTS kv (ns TEXT NOT NULL, k TEXT NOT NULL, doc TEXT NOT NULL, updated DOUBLE PRECISION NOT NULL, PRIMARY KEY (ns, k))",
    """CREATE TABLE IF NOT EXISTS jobs (
        id TEXT PRIMARY KEY, kind TEXT NOT NULL, name TEXT, payload TEXT NOT NULL, status TEXT NOT NULL,
        actor TEXT, created DOUBLE PRECISION NOT NULL, started DOUBLE PRECISION, finished DOUBLE PRECISION,
        lease_until DOUBLE PRECISION, attempts INTEGER NOT NULL DEFAULT 0, worker TEXT, result TEXT)""",
    "CREATE INDEX IF NOT EXISTS jobs_status ON jobs (status, created)",
]


class Db:
    def __init__(self, url=None, path=None):
        self.url = url
        self.pg = bool(url and url.startswith(("postgres://", "postgresql://")))
        self.path = path
        self._lock = threading.Lock()
        self._ready = False

    def _connect(self):
        if self.pg:
            import psycopg  # only needed on Render; listed in requirements.txt
            return psycopg.connect(self.url, autocommit=False)
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        c = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA busy_timeout=30000")
        return c

    def sql(self, q):
        return q.replace("?", "%s") if self.pg else q

    @contextlib.contextmanager
    def tx(self):
        """One transaction. Writers are serialised (BEGIN IMMEDIATE on SQLite; row locks on Postgres)."""
        c = self._connect()
        try:
            if not self.pg:
                c.execute("BEGIN IMMEDIATE")
            yield _Cur(self, c)
            c.execute("COMMIT") if not self.pg else c.commit()
        except BaseException:
            try:
                c.execute("ROLLBACK") if not self.pg else c.rollback()
            except Exception:
                pass
            raise
        finally:
            c.close()

    def init(self):
        with self._lock:
            if self._ready:
                return
            with self.tx() as cur:
                if self.pg:
                    cur.run("SELECT pg_advisory_xact_lock(7)")
                for stmt in SCHEMA:
                    cur.run(stmt)
            self._ready = True


class _Cur:
    def __init__(self, db, conn):
        self.db, self.conn = db, conn

    def run(self, q, args=()):
        cur = self.conn.cursor()
        cur.execute(self.db.sql(q), args)
        return cur

    def rows(self, q, args=()):
        cur = self.run(q, args)
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]

    def one(self, q, args=()):
        r = self.rows(q, args)
        return r[0] if r else None


_db = None
_db_key = None
_db_guard = threading.Lock()


def db():
    """The shared database, opened once per configuration."""
    global _db, _db_key
    key = (config.database_url(), config.sqlite_path())
    with _db_guard:
        if _db is None or _db_key != key:
            _db = Db(url=config.database_url(), path=config.sqlite_path())
            _db_key = key
        d = _db
    d.init()
    return d


# ---- documents -----------------------------------------------------------------------------

def get(ns, k):
    with db().tx() as c:
        r = c.one("SELECT doc FROM kv WHERE ns=? AND k=?", (ns, k))
    return json.loads(r["doc"]) if r else None


def put(ns, k, doc):
    with db().tx() as c:
        c.run("INSERT INTO kv (ns,k,doc,updated) VALUES (?,?,?,?) ON CONFLICT (ns,k) DO UPDATE SET doc=EXCLUDED.doc, updated=EXCLUDED.updated",
              (ns, k, json.dumps(doc), time.time()))


def create(ns, k, doc):
    """Insert only if absent. Returns True when this call created it."""
    with db().tx() as c:
        cur = c.run("INSERT INTO kv (ns,k,doc,updated) VALUES (?,?,?,?) ON CONFLICT (ns,k) DO NOTHING",
                    (ns, k, json.dumps(doc), time.time()))
        return cur.rowcount == 1


def update(ns, k, fn, create_with=None):
    """Atomic read-modify-write. fn(doc) mutates the dict in place (or returns a new one)."""
    with db().tx() as c:
        r = c.one("SELECT doc FROM kv WHERE ns=? AND k=?" + (" FOR UPDATE" if db().pg else ""), (ns, k))
        if r is None and create_with is None:
            return None
        doc = json.loads(r["doc"]) if r else dict(create_with)
        out = fn(doc)
        doc = doc if out is None else out
        c.run("INSERT INTO kv (ns,k,doc,updated) VALUES (?,?,?,?) ON CONFLICT (ns,k) DO UPDATE SET doc=EXCLUDED.doc, updated=EXCLUDED.updated",
              (ns, k, json.dumps(doc), time.time()))
        return doc


def delete(ns, k):
    with db().tx() as c:
        c.run("DELETE FROM kv WHERE ns=? AND k=?", (ns, k))


def items(ns, newest_first=False, limit=None):
    q = "SELECT k, doc FROM kv WHERE ns=? ORDER BY k " + ("DESC" if newest_first else "ASC")
    args = [ns]
    if limit:
        q += " LIMIT ?"
        args.append(int(limit))
    with db().tx() as c:
        rows = c.rows(q, tuple(args))
    return [(r["k"], json.loads(r["doc"])) for r in rows]


# ---- audit ---------------------------------------------------------------------------------

def audit(actor, action, target="", detail=None, role=""):
    now = time.time()
    put("audit", f"{now:017.6f}-{uuid.uuid4().hex[:6]}",
        {"at": int(now), "actor": actor, "role": role, "action": action, "target": target, "detail": detail or {}})


def audit_log(limit=200):
    return [d for _, d in items("audit", newest_first=True, limit=limit)]


# ---- jobs ----------------------------------------------------------------------------------

def _job(r):
    if not r:
        return None
    r = dict(r)
    r["payload"] = json.loads(r["payload"] or "{}")
    r["result"] = json.loads(r["result"]) if r.get("result") else None
    return r


def enqueue(kind, name, payload=None, actor=""):
    jid = uuid.uuid4().hex
    with db().tx() as c:
        c.run("INSERT INTO jobs (id,kind,name,payload,status,actor,created) VALUES (?,?,?,?,?,?,?)",
              (jid, kind, name, json.dumps(payload or {}), "queued", actor, time.time()))
    return jid


def claim(worker, kinds=None):
    """Take the oldest runnable job, or None. Jobs in the same exclusive group never overlap."""
    now = time.time()
    with db().tx() as c:
        if db().pg:
            c.run("SELECT pg_advisory_xact_lock(42)")
        # a worker that died leaves a job 'running' past its lease: queue it again, or give up after MAX_ATTEMPTS
        c.run("UPDATE jobs SET status='failed', finished=?, result=? WHERE status='running' AND lease_until < ? AND attempts >= ?",
              (now, json.dumps({"error": "worker lost; gave up after retries"}), now, MAX_ATTEMPTS))
        c.run("UPDATE jobs SET status='queued', worker=NULL WHERE status='running' AND lease_until < ?", (now,))
        busy = {EXCLUSIVE[r["kind"]] for r in c.rows("SELECT DISTINCT kind FROM jobs WHERE status='running'") if r["kind"] in EXCLUSIVE}
        skip = [k for k, g in EXCLUSIVE.items() if g in busy]
        q, args = "SELECT * FROM jobs WHERE status='queued'", []
        if kinds:
            q += " AND kind IN (%s)" % ",".join("?" * len(kinds))
            args += list(kinds)
        if skip:
            q += " AND kind NOT IN (%s)" % ",".join("?" * len(skip))
            args += skip
        q += " ORDER BY created LIMIT 1" + (" FOR UPDATE SKIP LOCKED" if db().pg else "")
        j = c.one(q, tuple(args))
        if not j:
            return None
        lease = now + LEASE_SECONDS.get(j["kind"], 600)
        c.run("UPDATE jobs SET status='running', started=?, lease_until=?, attempts=attempts+1, worker=? WHERE id=?",
              (now, lease, worker, j["id"]))
        j.update(status="running", attempts=j["attempts"] + 1)
        return _job(j)


def complete(jid, ok, result=None):
    with db().tx() as c:
        c.run("UPDATE jobs SET status=?, finished=?, result=? WHERE id=?",
              ("done" if ok else "failed", time.time(), json.dumps(result or {}), jid))


def job(jid):
    with db().tx() as c:
        return _job(c.one("SELECT * FROM jobs WHERE id=?", (jid,)))


def recent_jobs(limit=50):
    with db().tx() as c:
        return [_job(r) for r in c.rows("SELECT * FROM jobs ORDER BY created DESC LIMIT ?", (int(limit),))]


def active_job_for(kind, name):
    with db().tx() as c:
        return _job(c.one("SELECT * FROM jobs WHERE kind=? AND name=? AND status IN ('queued','running') ORDER BY created LIMIT 1", (kind, name)))
