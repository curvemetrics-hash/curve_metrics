"""Extended checks: security posture, exposure, access, drift, runtime faults and deeper AWS configuration.

The 14 baseline controls in controls.py decide `compliant`. These checks add severity-rated findings
with a remediation hint. They never change `compliant`; they feed `grade` and the severity counts.

Each check returns (status, evidence) where status is one of:
  pass     the property holds
  fail     a finding
  na       nothing to check (for example no workloads, or the resource does not exist; baseline reports that)
  unknown  the data could not be collected, so the check says nothing either way

These are engineering checks chosen by the author. They are not mapped to CIS, SOC 2 or ISO.
"""
import calendar
import re
import time

SEVERITIES = ("high", "medium", "low")
EXPECTED_NETPOLS = {"default-deny-ingress", "allow-same-namespace", "allow-ingress-controller", "allow-listed-namespaces"}
SECRET_NAME = re.compile(r"(PASSWORD|PASSWD|SECRET|TOKEN|API_?KEY|PRIVATE_?KEY|ACCESS_?KEY)", re.I)
BAD_WAITING = {"CrashLoopBackOff", "ImagePullBackOff", "ErrImagePull", "CreateContainerConfigError",
               "InvalidImageName", "CreateContainerError"}
BAD_EVENTS = {"FailedScheduling", "FailedMount", "BackOff", "Unhealthy", "FailedCreate", "Evicted",
              "OOMKilling", "FailedAttachVolume", "FailedCreatePodSandBox"}
RISKY_CAPS = {"ALL", "SYS_ADMIN", "NET_ADMIN", "SYS_PTRACE", "SYS_MODULE", "DAC_OVERRIDE", "NET_RAW"}
ADMIN_ROLES = {"admin", "edit", "cluster-admin", "owner"}
MIN_LOG_RETENTION_DAYS = 30
QUOTA_WARN = 0.8
PENDING_SECONDS = 300
RESTART_LIMIT = 5
EVENT_WINDOW_SECONDS = 3600

CHECKS = []


def check(cid, area, title, severity, fix, needs="k8s"):
    def deco(fn):
        CHECKS.append({"id": cid, "area": area, "title": title, "severity": severity, "fix": fix,
                       "needs": needs, "fn": fn})
        return fn
    return deco


# ---- helpers -------------------------------------------------------------------------------

def _items(s, kind):
    return (s.get("k8s") or {}).get(kind, [])


def _ts(v):
    try:
        return calendar.timegm(time.strptime(v, "%Y-%m-%dT%H:%M:%SZ"))
    except (TypeError, ValueError):
        return None


def _workloads(s):
    """(label, pod_spec) for every controller template and every bare pod."""
    out = []
    for kind in ("Deployment", "StatefulSet", "DaemonSet", "Job"):
        for w in _items(s, kind):
            out.append((f"{kind}/{w['metadata']['name']}", (w.get("spec", {}).get("template") or {}).get("spec") or {}))
    for w in _items(s, "CronJob"):
        t = ((w.get("spec", {}).get("jobTemplate") or {}).get("spec", {}).get("template") or {}).get("spec") or {}
        out.append((f"CronJob/{w['metadata']['name']}", t))
    for p in _items(s, "Pod"):
        if not p["metadata"].get("ownerReferences"):
            out.append((f"Pod/{p['metadata']['name']}", p.get("spec") or {}))
    return out


def _containers(spec):
    return (spec.get("containers") or []) + (spec.get("initContainers") or [])


def _scan(s, pred):
    """Return the labels of workloads where pred(label, spec) is true, or na if there are none."""
    wl = _workloads(s)
    if not wl:
        return "na", "no workloads in this namespace"
    bad = sorted({lbl for lbl, spec in wl if pred(lbl, spec)})
    return ("fail", ", ".join(bad)) if bad else ("pass", f"{len(wl)} workload(s) checked")


def _cscan(s, pred):
    return _scan(s, lambda lbl, spec: any(pred(c, spec) for c in _containers(spec)))


def _aslist(v):
    return v if isinstance(v, list) else [v]


def _stmts(doc):
    return [x for x in _aslist((doc or {}).get("Statement") or []) if isinstance(x, dict)]


def _star_principal(st):
    p = st.get("Principal")
    return p == "*" or (isinstance(p, dict) and "*" in _aslist(p.get("AWS", [])))


# ---- workload security ---------------------------------------------------------------------

@check("WLS-1", "Workload", "No privileged containers", "high", "Remove securityContext.privileged: true.")
def _wls1(s):
    return _cscan(s, lambda c, sp: (c.get("securityContext") or {}).get("privileged") is True)


@check("WLS-2", "Workload", "No host network, PID or IPC", "high", "Remove hostNetwork, hostPID and hostIPC from the pod spec.")
def _wls2(s):
    return _scan(s, lambda lbl, sp: any(sp.get(k) for k in ("hostNetwork", "hostPID", "hostIPC")))


@check("WLS-3", "Workload", "No hostPath volumes", "high", "Use emptyDir, a PersistentVolumeClaim or a ConfigMap instead of hostPath.")
def _wls3(s):
    return _scan(s, lambda lbl, sp: any("hostPath" in v for v in sp.get("volumes") or []))


@check("WLS-4", "Workload", "Privilege escalation disabled", "medium", "Set securityContext.allowPrivilegeEscalation: false.")
def _wls4(s):
    return _cscan(s, lambda c, sp: (c.get("securityContext") or {}).get("allowPrivilegeEscalation") is not False)


@check("WLS-5", "Workload", "Containers do not run as root", "medium", "Set runAsNonRoot: true (and a non-zero runAsUser) in the securityContext.")
def _wls5(s):
    def root(c, sp):
        cs, ps = c.get("securityContext") or {}, sp.get("securityContext") or {}
        if cs.get("runAsUser") == 0 or (cs.get("runAsUser") is None and ps.get("runAsUser") == 0):
            return True
        return not (cs.get("runAsNonRoot") or ps.get("runAsNonRoot")) and not (cs.get("runAsUser") or ps.get("runAsUser"))
    return _cscan(s, root)


@check("WLS-6", "Workload", "No dangerous Linux capabilities", "high", "Drop ALL capabilities and add back only what is needed (for example NET_BIND_SERVICE).")
def _wls6(s):
    return _cscan(s, lambda c, sp: bool(RISKY_CAPS & set(((c.get("securityContext") or {}).get("capabilities") or {}).get("add") or [])))


@check("WLS-7", "Workload", "Images use a pinned tag", "medium", "Use a specific version tag or a digest. Avoid ':latest' and untagged images.")
def _wls7(s):
    def floating(c, sp):
        img = c.get("image", "")
        if "@sha256:" in img:
            return False
        last = img.rsplit("/", 1)[-1]
        return ":" not in last or last.endswith(":latest")
    return _cscan(s, floating)


@check("WLS-8", "Workload", "No literal secrets in environment variables", "high", "Reference a Secret with valueFrom.secretKeyRef instead of a literal value.")
def _wls8(s):
    return _cscan(s, lambda c, sp: any(SECRET_NAME.search(e.get("name", "")) and e.get("value") for e in c.get("env") or []))


@check("WLS-9", "Workload", "Readiness probe defined", "low", "Add a readinessProbe so traffic only reaches ready pods.")
def _wls9(s):
    wl = [(lbl, sp) for lbl, sp in _workloads(s) if not lbl.startswith(("Job/", "CronJob/"))]
    if not wl:
        return "na", "no long-running workloads"
    bad = sorted({lbl for lbl, sp in wl if any(not c.get("readinessProbe") for c in sp.get("containers") or [])})
    return ("fail", ", ".join(bad)) if bad else ("pass", f"{len(wl)} workload(s) checked")


@check("WLS-10", "Workload", "Dedicated service account", "low", "Run workloads as the 'app' service account (or another dedicated one), not 'default'.")
def _wls10(s):
    return _scan(s, lambda lbl, sp: sp.get("serviceAccountName", "default") == "default")


@check("WLS-11", "Workload", "CPU and memory limits set", "low", "Set resources.limits.cpu and resources.limits.memory on every container.")
def _wls11(s):
    def nolimit(c, sp):
        lim = (c.get("resources") or {}).get("limits") or {}
        return not (lim.get("cpu") and lim.get("memory"))
    return _cscan(s, nolimit)


# ---- exposure ------------------------------------------------------------------------------

@check("NETX-1", "Exposure", "No NodePort or LoadBalancer services", "medium", "Use ClusterIP and expose through the ingress controller.")
def _netx1(s):
    bad = [x["metadata"]["name"] for x in _items(s, "Service") if x.get("spec", {}).get("type") in ("NodePort", "LoadBalancer")]
    return ("fail", ", ".join(bad)) if bad else ("pass", "no externally exposed services")


@check("NETX-2", "Exposure", "Ingresses use TLS", "medium", "Add a spec.tls section with a certificate secret.")
def _netx2(s):
    ing = _items(s, "Ingress")
    if not ing:
        return "na", "no ingresses"
    bad = [i["metadata"]["name"] for i in ing if not i.get("spec", {}).get("tls")]
    return ("fail", ", ".join(bad)) if bad else ("pass", f"{len(ing)} ingress(es) with TLS")


@check("NETX-3", "Exposure", "No network policy opens to 0.0.0.0/0", "high", "Replace ipBlock 0.0.0.0/0 with specific namespaces, pods or CIDR ranges.")
def _netx3(s):
    bad = [p["metadata"]["name"] for p in _items(s, "NetworkPolicy")
           for r in (p.get("spec", {}).get("ingress") or []) + (p.get("spec", {}).get("egress") or [])
           for peer in (r.get("from") or []) + (r.get("to") or [])
           if (peer.get("ipBlock") or {}).get("cidr") in ("0.0.0.0/0", "::/0")]
    return ("fail", ", ".join(sorted(set(bad)))) if bad else ("pass", "no policy opens to all addresses")


@check("NETX-4", "Exposure", "Egress is restricted", "low", "Add a default-deny egress policy and allow only needed destinations (DNS, AWS endpoints).")
def _netx4(s):
    ok = any("Egress" in (p.get("spec", {}).get("policyTypes") or []) for p in _items(s, "NetworkPolicy"))
    return ("pass", "an egress policy exists") if ok else ("fail", "no egress policy: workloads can reach any destination")


# ---- access --------------------------------------------------------------------------------

@check("ACCX-1", "Access", "No wildcard roles", "high", "Replace '*' verbs and resources in Roles with the specific ones needed.")
def _accx1(s):
    bad = [r["metadata"]["name"] for r in _items(s, "Role") for x in r.get("rules") or []
           if "*" in (x.get("verbs") or []) or "*" in (x.get("resources") or [])]
    return ("fail", ", ".join(sorted(set(bad)))) if bad else ("pass", f"{len(_items(s, 'Role'))} role(s) checked")


@check("ACCX-2", "Access", "No broad read access to Secrets", "medium", "Limit get/list/watch on secrets to named resourceNames.")
def _accx2(s):
    bad = [r["metadata"]["name"] for r in _items(s, "Role") for x in r.get("rules") or []
           if "secrets" in (x.get("resources") or []) and not x.get("resourceNames")
           and {"get", "list", "watch"} & set(x.get("verbs") or [])]
    return ("fail", ", ".join(sorted(set(bad)))) if bad else ("pass", "no role reads all secrets")


@check("ACCX-3", "Access", "Only blueprint-managed admin bindings", "medium", "Remove admin bindings that were added by hand, or add the group to the request file.")
def _accx3(s):
    bad = [b["metadata"]["name"] for b in _items(s, "RoleBinding")
           if (b.get("roleRef") or {}).get("name") in ADMIN_ROLES and not b["metadata"]["name"].startswith("team-admin-")]
    return ("fail", ", ".join(bad)) if bad else ("pass", "all admin bindings come from the blueprint")


@check("ACCX-4", "Access", "No service accounts from other namespaces bound", "low", "Bind only subjects from this namespace unless the access is deliberate.")
def _accx4(s):
    ns = ((s.get("ns") or {}).get("metadata") or {}).get("name")
    bad = [b["metadata"]["name"] for b in _items(s, "RoleBinding") for sub in b.get("subjects") or []
           if sub.get("kind") == "ServiceAccount" and sub.get("namespace") not in (None, ns)]
    return ("fail", ", ".join(sorted(set(bad)))) if bad else ("pass", "no cross-namespace service account bindings")


@check("PSA-1", "Access", "Pod Security Admission enforced", "medium",
       "Label the namespace pod-security.kubernetes.io/enforce=baseline (or restricted). The blueprint does not set this yet.")
def _psa1(s):
    lbl = (((s.get("ns") or {}).get("metadata") or {}).get("labels") or {}).get("pod-security.kubernetes.io/enforce")
    return ("pass", f"enforce={lbl}") if lbl in ("baseline", "restricted") else ("fail", f"enforce label is {lbl or 'not set'}")


# ---- drift ---------------------------------------------------------------------------------

@check("DRF-1", "Drift", "No unexpected network policies", "medium", "Review policies that are not in the blueprint; remove them or add them to the blueprint.")
def _drf1(s):
    bad = sorted(p["metadata"]["name"] for p in _items(s, "NetworkPolicy") if p["metadata"]["name"] not in EXPECTED_NETPOLS)
    return ("fail", ", ".join(bad)) if bad else ("pass", "only blueprint network policies present")


@check("DRF-2", "Drift", "Service account is bound to the IAM role", "medium", "Re-apply the blueprint so the 'app' service account carries the role-arn annotation.")
def _drf2(s):
    ns = ((s.get("ns") or {}).get("metadata") or {}).get("name", "")
    sa = next((x for x in _items(s, "ServiceAccount") if x["metadata"]["name"] == "app"), None)
    if not sa:
        return "fail", "service account 'app' is missing"
    arn = (sa["metadata"].get("annotations") or {}).get("eks.amazonaws.com/role-arn", "")
    return (("pass", "role-arn annotation points at this space's role") if arn.endswith(f":role/{ns}-app")
            else ("fail", f"role-arn annotation is {arn or 'missing'}"))


@check("DRF-3", "Drift", "cloud-resources ConfigMap matches the real resources", "medium", "Re-apply the blueprint to rewrite the ConfigMap.")
def _drf3(s):
    ns = ((s.get("ns") or {}).get("metadata") or {}).get("name", "")
    cm = next((x for x in _items(s, "ConfigMap") if x["metadata"]["name"] == "cloud-resources"), None)
    if not cm:
        return "fail", "ConfigMap 'cloud-resources' is missing"
    d = cm.get("data") or {}
    want = {"S3_BUCKET": f"{ns}-data", "SECRET_ID": f"{ns}/app", "LOG_GROUP": f"/curve-metrics/{ns}"}
    diff = [k for k, v in want.items() if d.get(k) != v]
    if not str(d.get("SQS_QUEUE_URL", "")).endswith(f"/{ns}-events"):
        diff.append("SQS_QUEUE_URL")
    return ("fail", "differs: " + ", ".join(diff)) if diff else ("pass", "names match")


# ---- runtime faults ------------------------------------------------------------------------

@check("RTH-1", "Runtime", "No crashing or unpullable pods", "high", "Run 'kubectl describe pod' and 'kubectl logs --previous'; fix the image, config or memory limit.")
def _rth1(s):
    bad = []
    for p in _items(s, "Pod"):
        for c in (p.get("status", {}).get("containerStatuses") or []):
            w = (c.get("state", {}).get("waiting") or {}).get("reason")
            t = (c.get("lastState", {}).get("terminated") or {}).get("reason")
            now_t = c.get("state", {}).get("terminated") or {}
            owner_job = any(o.get("kind") == "Job" for o in p["metadata"].get("ownerReferences") or [])
            # between restarts a crashing container shows as terminated, not as CrashLoopBackOff
            crashed = (now_t.get("exitCode", 0) != 0 and not owner_job) or \
                      (t in ("Error", "OOMKilled") and c.get("restartCount", 0) >= 2 and not c.get("ready"))
            if w in BAD_WAITING or t == "OOMKilled" or crashed:
                bad.append(f"{p['metadata']['name']} ({w or now_t.get('reason') or t})")
    return ("fail", ", ".join(bad)) if bad else ("pass", f"{len(_items(s, 'Pod'))} pod(s) healthy")


@check("RTH-2", "Runtime", "No pods stuck Pending", "medium", "Check 'kubectl describe pod' events: quota, node capacity, unbound volume or a taint.")
def _rth2(s):
    now = s.get("_now") or time.time()
    bad = [p["metadata"]["name"] for p in _items(s, "Pod")
           if p.get("status", {}).get("phase") == "Pending"
           and now - (_ts(p["metadata"].get("creationTimestamp")) or now) > PENDING_SECONDS]
    return ("fail", ", ".join(bad)) if bad else ("pass", "no pod pending for more than 5 minutes")


@check("RTH-3", "Runtime", "No restart loops", "medium", "Look at logs from the previous run; restarts usually mean a crash or a failing liveness probe.")
def _rth3(s):
    bad = [f"{p['metadata']['name']} ({c['restartCount']})" for p in _items(s, "Pod")
           for c in p.get("status", {}).get("containerStatuses") or [] if c.get("restartCount", 0) >= RESTART_LIMIT]
    return ("fail", ", ".join(bad)) if bad else ("pass", f"no container restarted {RESTART_LIMIT} or more times")


@check("RTH-4", "Runtime", "Workloads have all replicas available", "medium", "Run 'kubectl rollout status' and check pod events.")
def _rth4(s):
    bad = []
    for kind in ("Deployment", "StatefulSet"):
        for w in _items(s, kind):
            want, ready = w.get("spec", {}).get("replicas", 1), w.get("status", {}).get("readyReplicas", 0)
            if ready < want:
                bad.append(f"{kind}/{w['metadata']['name']} ({ready}/{want})")
    for w in _items(s, "DaemonSet"):
        st = w.get("status", {})
        if st.get("numberReady", 0) < st.get("desiredNumberScheduled", 0):
            bad.append(f"DaemonSet/{w['metadata']['name']}")
    return ("fail", ", ".join(bad)) if bad else ("pass", "all replicas ready")


@check("RTH-5", "Runtime", "Quota has headroom", "medium", "Raise the size in the request file, or reduce usage. Over 80% of any quota counts.")
def _rth5(s):
    q = next((x for x in _items(s, "ResourceQuota") if x["metadata"]["name"] == "standard-quota"), None)
    if not q:
        return "na", "no standard-quota"
    hard, used = q.get("status", {}).get("hard") or {}, q.get("status", {}).get("used") or {}
    hot = []
    for k, h in hard.items():
        u = _qty(used.get(k, "0"))
        if _qty(h) and u / _qty(h) >= QUOTA_WARN:
            hot.append(f"{k} {used.get(k)}/{h}")
    return ("fail", ", ".join(hot)) if hot else ("pass", "all quotas under 80%")


def _qty(v):
    v = str(v)
    for suf, mult in (("Ki", 2**10), ("Mi", 2**20), ("Gi", 2**30), ("Ti", 2**40), ("m", 0.001), ("k", 1e3), ("M", 1e6), ("G", 1e9)):
        if v.endswith(suf):
            try:
                return float(v[:-len(suf)]) * mult
            except ValueError:
                return 0.0
    try:
        return float(v)
    except ValueError:
        return 0.0


@check("RTH-6", "Runtime", "Volume claims are bound", "medium", "Check the storage class and 'kubectl describe pvc'.")
def _rth6(s):
    pvcs = _items(s, "PersistentVolumeClaim")
    if not pvcs:
        return "na", "no volume claims"
    bad = [p["metadata"]["name"] for p in pvcs if p.get("status", {}).get("phase") != "Bound"]
    return ("fail", ", ".join(bad)) if bad else ("pass", f"{len(pvcs)} claim(s) bound")


@check("RTH-7", "Runtime", "No recent warning events", "low", "Read 'kubectl get events' for the reason; these usually point at scheduling, mounting or probe failures.")
def _rth7(s):
    now = s.get("_now") or time.time()
    bad = {}
    for e in _items(s, "Event"):
        t = _ts(e.get("lastTimestamp") or e.get("eventTime") or "")
        if e.get("type") == "Warning" and e.get("reason") in BAD_EVENTS and (t is None or now - t <= EVENT_WINDOW_SECONDS):
            bad[e["reason"]] = bad.get(e["reason"], 0) + 1
    return ("fail", ", ".join(f"{k} x{v}" for k, v in sorted(bad.items()))) if bad else ("pass", "no warning events in the last hour")


@check("RTH-8", "Runtime", "No failed jobs", "low", "Check job logs; delete the job after fixing the cause.")
def _rth8(s):
    jobs = _items(s, "Job")
    if not jobs:
        return "na", "no jobs"
    bad = [j["metadata"]["name"] for j in jobs if j.get("status", {}).get("failed")]
    return ("fail", ", ".join(bad)) if bad else ("pass", f"{len(jobs)} job(s) without failures")


# ---- AWS -----------------------------------------------------------------------------------

def _aws_part(s, key):
    return ((s.get("aws_x") or {}).get(key))


@check("S3X-1", "AWS Storage", "Bucket policy requires TLS", "medium",
       "Add a bucket policy that denies requests where aws:SecureTransport is false. The blueprint does not set this yet.", needs="aws.s3")
def _s3x1(s):
    if not (s.get("s3") or {}).get("exists"):
        return "na", "bucket missing (see STO-1)"
    for st in _stmts((_aws_part(s, "s3") or {}).get("policy")):
        cond = json_s(st.get("Condition"))
        if st.get("Effect") == "Deny" and "aws:securetransport" in cond and "false" in cond:
            return "pass", "policy denies non-TLS requests"
    return "fail", "no policy denies plain-HTTP access"


def json_s(v):
    import json
    return json.dumps(v or {}).lower()


@check("S3X-2", "AWS Storage", "Bucket policy does not allow everyone", "high", "Remove statements that allow Principal '*' without a restricting condition.", needs="aws.s3")
def _s3x2(s):
    if not (s.get("s3") or {}).get("exists"):
        return "na", "bucket missing (see STO-1)"
    bad = [st for st in _stmts((_aws_part(s, "s3") or {}).get("policy"))
           if st.get("Effect") == "Allow" and _star_principal(st) and not st.get("Condition")]
    return ("fail", f"{len(bad)} statement(s) allow Principal '*'") if bad else ("pass", "no open allow statements")


@check("S3X-3", "AWS Storage", "Bucket has ownership tags", "low", "Add managed-by, team and env tags.", needs="aws.s3")
def _s3x3(s):
    if not (s.get("s3") or {}).get("exists"):
        return "na", "bucket missing (see STO-1)"
    tags = (_aws_part(s, "s3") or {}).get("tags") or {}
    miss = [k for k in ("managed-by", "team", "env") if not tags.get(k)]
    return ("fail", "missing tags: " + ", ".join(miss)) if miss else ("pass", "tags present")


@check("SQSX-1", "AWS Messaging", "Queue has a dead-letter queue", "low", "Add a redrive policy so poison messages do not loop forever. The blueprint does not set this yet.", needs="aws.sqs")
def _sqsx1(s):
    q = _aws_part(s, "sqs")
    if q is None:
        return "na", "queue missing (see MSG-1)"
    return ("pass", "redrive policy set") if q.get("redrive") else ("fail", "no dead-letter queue")


@check("SQSX-2", "AWS Messaging", "Queue policy does not allow everyone", "high", "Remove statements that allow Principal '*' without a condition.", needs="aws.sqs")
def _sqsx2(s):
    q = _aws_part(s, "sqs")
    if q is None:
        return "na", "queue missing (see MSG-1)"
    bad = [st for st in _stmts(q.get("policy")) if st.get("Effect") == "Allow" and _star_principal(st) and not st.get("Condition")]
    return ("fail", f"{len(bad)} open statement(s)") if bad else ("pass", "no open allow statements")


@check("SECX-1", "AWS Secrets", "Secret rotation enabled", "low", "Configure automatic rotation in Secrets Manager.", needs="aws.secret")
def _secx1(s):
    d = _aws_part(s, "secret")
    if d is None:
        return "na", "secret missing (see SEC-1)"
    return ("pass", "rotation enabled") if d.get("rotation") else ("fail", "rotation is off")


@check("IAMX-1", "AWS IAM", "Role trust is limited to this service account", "high",
       "The trust policy must name the cluster's OIDC provider and a ':sub' condition for this namespace's service account.", needs="aws.role")
def _iamx1(s):
    r = _aws_part(s, "role")
    if r is None:
        return "na", "role missing (see SEC-2)"
    for st in _stmts(r.get("trust")):
        if _star_principal(st):
            return "fail", "trust policy allows Principal '*'"
        if ":sub" not in json_s(st.get("Condition")):
            return "fail", "trust statement has no ':sub' condition"
    return "pass", "trust is conditioned on a service account"


@check("IAMX-2", "AWS IAM", "Only the blueprint policy is attached", "high", "Detach any extra managed policy, especially AdministratorAccess.", needs="aws.role")
def _iamx2(s):
    r = _aws_part(s, "role")
    if r is None:
        return "na", "role missing (see SEC-2)"
    extra = [p for p in r.get("attached", []) if p != f"{((s.get('ns') or {}).get('metadata') or {}).get('name', '')}-app"]
    return ("fail", "extra policies: " + ", ".join(extra)) if extra else ("pass", "one policy attached")


@check("IAMX-3", "AWS IAM", "No inline policies on the role", "medium", "Move inline policy into the Terraform-managed policy.", needs="aws.role")
def _iamx3(s):
    r = _aws_part(s, "role")
    if r is None:
        return "na", "role missing (see SEC-2)"
    return ("fail", ", ".join(r["inline"])) if r.get("inline") else ("pass", "no inline policies")


@check("IAMX-4", "AWS IAM", "No service-wide wildcard actions", "medium", "List specific actions instead of 's3:*' or 'sqs:*'.", needs="aws.role")
def _iamx4(s):
    st = (s.get("iam") or {}).get("policy_statements")
    if not st:
        return "na", "policy missing (see SEC-2)"
    bad = sorted({a for x in st if x.get("Effect", "Allow") == "Allow" for a in _aslist(x.get("Action", [])) if a.endswith(":*")})
    return ("fail", ", ".join(bad)) if bad else ("pass", "all actions are specific")


@check("LOGX-1", "AWS Logging", f"Log retention is at least {MIN_LOG_RETENTION_DAYS} days", "low",
       "Raise log_retention_days in the request.", needs="aws.base")
def _logx1(s):
    lg = s.get("logs") or {}
    if not lg.get("exists"):
        return "na", "log group missing (see LOG-1)"
    r = lg.get("retention")
    if not r:
        return "na", "no retention set (see LOG-1)"
    return ("pass", f"{r} days") if r >= MIN_LOG_RETENTION_DAYS else ("fail", f"{r} days")


# ---- evaluation ----------------------------------------------------------------------------

def _available(s, needs):
    errs = s.get("errors") or {}
    if needs == "aws.base":
        return None
    if needs.startswith("aws."):
        key = needs
        if key in errs:
            return errs[key]
        if s.get("aws_x") is None:
            return errs.get("aws", "AWS data not collected")
        return None
    if s.get("k8s") is None:
        return errs.get("k8s", "Kubernetes data not collected")
    return None


def evaluate(snapshot, now=None):
    snap = dict(snapshot)
    snap["_now"] = now or time.time()
    results = []
    for c in CHECKS:
        if not snap.get("ns"):
            status, ev = "na", "space (namespace) not found"
        else:
            miss = _available(snap, c["needs"])
            if miss:
                status, ev = "unknown", f"could not check: {miss}"
            else:
                try:
                    status, ev = c["fn"](snap)
                except Exception as e:  # a bad object must not hide the other checks
                    status, ev = "unknown", f"check error: {e}"
        results.append({"id": c["id"], "area": c["area"], "title": c["title"], "severity": c["severity"],
                        "status": status, "evidence": ev, "fix": c["fix"] if status == "fail" else ""})
    failed = [r for r in results if r["status"] == "fail"]
    sev = {k: sum(r["severity"] == k for r in failed) for k in SEVERITIES}
    return {"extended": results,
            "extended_summary": {"total": len(results), "passed": sum(r["status"] == "pass" for r in results),
                                 "failed": len(failed), "na": sum(r["status"] == "na" for r in results),
                                 "unknown": sum(r["status"] == "unknown" for r in results), "severity": sev}}


def grade(report):
    """One word for the whole space. Baseline compliance comes first; then the worst open finding."""
    if not report.get("compliant"):
        return "non-compliant"
    sev = (report.get("extended_summary") or {}).get("severity") or {}
    if sev.get("high"):
        return "at risk"
    if sev.get("medium"):
        return "needs attention"
    return "healthy"
