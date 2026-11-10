"""Compliance controls. Pure functions over a snapshot of live state, so each can be unit tested.

A snapshot is a plain dict gathered by collect.py:
  ns, quota, limitrange : dict or None   (Kubernetes objects)
  netpols               : {name: spec}
  rolebindings          : [{"name", "role", "subjects": [..names..]}]
  s3   : {"exists", "public_block": [4 bools] or None, "versioning", "encryption"}
  sqs  : {"exists", "sse"}
  logs : {"exists", "retention"}
  secret : bool
  iam  : {"policy_statements": list or None}
These are engineering controls. Passing them does not make a space SOC 2 or ISO certified.
"""

SIZE_PRESETS = {  # must match modules/namespace_baseline (a test in tests/ guards this)
    "small": {"requests.cpu": "2", "pods": "20", "requests.storage": "50Gi"},
    "medium": {"requests.cpu": "4", "pods": "50", "requests.storage": "200Gi"},
    "large": {"requests.cpu": "8", "pods": "100", "requests.storage": "500Gi"},
}
OPEN_SUBJECTS = {"system:authenticated", "system:unauthenticated", "system:serviceaccounts"}
REQUIRED_LABELS = ["curve-metrics/team", "curve-metrics/environment", "curve-metrics/size",
                   "app.kubernetes.io/managed-by"]


def _labels(s):
    return ((s.get("ns") or {}).get("metadata") or {}).get("labels") or {}


def c_default_deny(s):
    p = (s.get("netpols") or {}).get("default-deny-ingress")
    ok = bool(p) and p.get("podSelector") == {} and "Ingress" in (p.get("policyTypes") or []) and not p.get("ingress")
    return ok, "default-deny-ingress present and selects all pods" if ok else "default-deny-ingress missing or altered"


def c_no_allow_all(s):
    bad = [n for n, p in (s.get("netpols") or {}).items()
           for r in (p.get("ingress") or []) if not r.get("from")]
    return not bad, "no policy allows ingress from everywhere" if not bad else f"allow-all ingress in: {', '.join(bad)}"


def c_no_open_admin(s):
    bad = [b["name"] for b in s.get("rolebindings") or []
           if b["role"] == "cluster-admin" or OPEN_SUBJECTS & set(b["subjects"])]
    return not bad, "no cluster-admin or open-subject bindings" if not bad else f"open or cluster-admin binding: {', '.join(bad)}"


def c_named_admins(s):
    named = [b["name"] for b in s.get("rolebindings") or []
             if any(x and not x.startswith("system:") for x in b["subjects"])]
    return bool(named), "admin access granted to named groups" if named else "no named admin group bound"


def c_quota(s):
    q = ((s.get("quota") or {}).get("spec") or {}).get("hard")
    size = _labels(s).get("curve-metrics/size")
    if not q or size not in SIZE_PRESETS:
        return False, "quota missing or size label missing"
    want = SIZE_PRESETS[size]
    diff = {k: (q.get(k), v) for k, v in want.items() if q.get(k) != v}
    return not diff, f"quota matches size {size}" if not diff else f"quota differs from size {size}: {diff}"


def c_limitrange(s):
    ok = bool(s.get("limitrange"))
    return ok, "limit range present" if ok else "limit range missing"


def c_labels(s):
    missing = [k for k in REQUIRED_LABELS if not _labels(s).get(k)]
    return not missing, "ownership labels present" if not missing else f"missing labels: {', '.join(missing)}"


def c_s3_public(s):
    b = (s.get("s3") or {}).get("public_block")
    ok = bool(b) and len(b) == 4 and all(b)
    return ok, "S3 public access fully blocked" if ok else "S3 public access not fully blocked"


def c_s3_version(s):
    v = (s.get("s3") or {}).get("versioning")
    return v == "Enabled", f"S3 versioning {v}"


def c_s3_encrypt(s):
    e = (s.get("s3") or {}).get("encryption")
    return bool(e), f"S3 encryption {e}" if e else "S3 encryption not configured"


def c_sqs_sse(s):
    ok = bool((s.get("sqs") or {}).get("sse"))
    return ok, "SQS server-side encryption on" if ok else "SQS encryption off or queue missing"


def c_logs(s):
    r = (s.get("logs") or {}).get("retention")
    return bool(r), f"log retention {r} days" if r else "log group missing or no retention set"


def c_secret(s):
    ok = bool(s.get("secret"))
    return ok, "secret exists" if ok else "secret missing"


def c_iam_scoped(s):
    st = (s.get("iam") or {}).get("policy_statements")
    if not st:
        return False, "IAM policy missing"
    wild = [x for x in st if "*" in _as_list(x.get("Resource")) or "*" in _as_list(x.get("Action"))]
    return not wild, "IAM policy limited to this space's resources" if not wild else "IAM policy uses wildcard action or resource"


def _as_list(v):
    return v if isinstance(v, list) else [v]


# (id, area, title, function)
CONTROLS = [
    ("NET-1", "Network", "Default-deny ingress policy", c_default_deny),
    ("NET-2", "Network", "No allow-from-everywhere ingress", c_no_allow_all),
    ("ACC-1", "Access", "No wildcard or cluster-admin access", c_no_open_admin),
    ("ACC-2", "Access", "Admin access goes to named groups", c_named_admins),
    ("RES-1", "Resources", "Quota matches size", c_quota),
    ("RES-2", "Resources", "Limit range present", c_limitrange),
    ("OWN-1", "Ownership", "Required labels present", c_labels),
    ("STO-1", "Storage", "S3 public access blocked", c_s3_public),
    ("STO-2", "Storage", "S3 versioning enabled", c_s3_version),
    ("STO-3", "Storage", "S3 encryption configured", c_s3_encrypt),
    ("MSG-1", "Messaging", "SQS encryption on", c_sqs_sse),
    ("LOG-1", "Logging", "Log retention set", c_logs),
    ("SEC-1", "Secrets", "Secret exists", c_secret),
    ("SEC-2", "Secrets", "IAM policy scoped to this space", c_iam_scoped),
]


def evaluate(snapshot):
    """Run every control. Returns the report dict for one scan."""
    results = []
    for cid, area, title, fn in CONTROLS:
        if not snapshot.get("ns"):  # a missing space must not pass controls that have nothing to object to
            ok, evidence = False, "space (namespace) not found"
        else:
            ok, evidence = fn(snapshot)
        results.append({"id": cid, "area": area, "title": title, "passed": bool(ok), "evidence": evidence})
    passed = sum(r["passed"] for r in results)
    return {"controls": results, "passed": passed, "total": len(results), "compliant": passed == len(results)}
