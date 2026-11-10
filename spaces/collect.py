"""Gather a snapshot of one space from the cluster (kubectl) and AWS (the real AWS CLI, or LocalStack via
awslocal.sh in local mode). In aws mode a read-only role is used when AWS_READONLY_ROLE_ARN is set."""
import json
import os
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor

from . import config

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MISSING = re.compile(r"NotFound|NoSuch|ResourceNotFound|does not exist|not found|NonExistent|404", re.I)


class CollectError(RuntimeError):
    pass


def _env():
    env = {**os.environ, "KUBECONFIG": config.kubeconfig(readonly=True)}
    if config.is_aws() and config.get("AWS_READONLY_ROLE_ARN"):
        env["AWS_PROFILE"] = "readonly"  # written by deploy/entrypoint.sh
    return env


def _run(cmd, parse=True):
    p = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT,
                       env=_env())
    if p.returncode != 0:
        if MISSING.search(p.stderr):
            return None
        raise CollectError(f"{' '.join(cmd[:4])}...: {p.stderr.strip()[:200]}")
    if not parse:
        return p.stdout
    return json.loads(p.stdout) if p.stdout.strip() else {}


def _k(*args):
    return _run(["kubectl", *args, "-o", "json"])


def _aws(*args):
    if config.is_aws():
        return _run(["aws", *args, "--output", "json"])
    return _run(["scripts/awslocal.sh", *args, "--output", "json"])


def _s3(name):
    b = f"{name}-data"
    if _aws("s3api", "head-bucket", "--bucket", b) is None:
        return {"exists": False}
    pab = _aws("s3api", "get-public-access-block", "--bucket", b)
    ver = _aws("s3api", "get-bucket-versioning", "--bucket", b) or {}
    enc = _aws("s3api", "get-bucket-encryption", "--bucket", b)
    cfg = (pab or {}).get("PublicAccessBlockConfiguration")
    rules = ((enc or {}).get("ServerSideEncryptionConfiguration") or {}).get("Rules") or []
    return {
        "exists": True,
        "public_block": [cfg.get(k, False) for k in ("BlockPublicAcls", "BlockPublicPolicy",
                                                    "IgnorePublicAcls", "RestrictPublicBuckets")] if cfg else None,
        "versioning": ver.get("Status"),
        "encryption": rules[0]["ApplyServerSideEncryptionByDefault"]["SSEAlgorithm"] if rules else None,
    }


def _sqs(name):
    url = _aws("sqs", "get-queue-url", "--queue-name", f"{name}-events")
    if not url:
        return {"exists": False}
    attrs = (_aws("sqs", "get-queue-attributes", "--queue-url", url["QueueUrl"],
                  "--attribute-names", "All") or {}).get("Attributes", {})
    return {"exists": True, "sse": attrs.get("SqsManagedSseEnabled") == "true" or bool(attrs.get("KmsMasterKeyId"))}


def _logs(name):
    g = (_aws("logs", "describe-log-groups", "--log-group-name-prefix", f"/curve-metrics/{name}") or {}).get("logGroups") or []
    g = [x for x in g if x["logGroupName"] == f"/curve-metrics/{name}"]
    return {"exists": bool(g), "retention": g[0].get("retentionInDays") if g else None}


def _iam(name):
    att = (_aws("iam", "list-attached-role-policies", "--role-name", f"{name}-app") or {}).get("AttachedPolicies")
    if not att:
        return {"policy_statements": None}
    pol = _aws("iam", "get-policy", "--policy-arn", att[0]["PolicyArn"])
    ver = _aws("iam", "get-policy-version", "--policy-arn", att[0]["PolicyArn"],
               "--version-id", pol["Policy"]["DefaultVersionId"])
    doc = ver["PolicyVersion"]["Document"]
    return {"policy_statements": doc.get("Statement")}


K8S_KINDS = ("pods,deployments,statefulsets,daemonsets,jobs,cronjobs,services,ingresses,"
             "serviceaccounts,persistentvolumeclaims,roles,rolebindings,configmaps,networkpolicies,resourcequotas")


def _k8s_extra(name):
    """Workloads, services, RBAC, quota usage and events. Secrets are never read."""
    items = (_k("-n", name, "get", K8S_KINDS) or {}).get("items", [])
    out = {}
    for i in items:
        out.setdefault(i.get("kind", "?"), []).append(i)
    out["Event"] = (_k("-n", name, "get", "events") or {}).get("items", [])
    return out


def _json_attr(v):
    try:
        return json.loads(v) if isinstance(v, str) else v
    except ValueError:
        return None


def _aws_extra(name):
    """Deeper AWS facts. Each section is gathered on its own so one failure does not hide the rest."""
    b = f"{name}-data"
    out, errors = {}, {}

    def section(key, fn):
        try:
            out[key] = fn()
        except Exception as e:  # collect what we can; the check reports 'could not check'
            errors[key] = str(e)[:160]

    def s3():
        pol = _aws("s3api", "get-bucket-policy", "--bucket", b)
        tags = _aws("s3api", "get-bucket-tagging", "--bucket", b)
        return {"policy": _json_attr((pol or {}).get("Policy")),
                "tags": {t["Key"]: t["Value"] for t in (tags or {}).get("TagSet", [])}}

    def sqs():
        url = _aws("sqs", "get-queue-url", "--queue-name", f"{name}-events")
        if not url:
            return None
        a = (_aws("sqs", "get-queue-attributes", "--queue-url", url["QueueUrl"], "--attribute-names", "All") or {}).get("Attributes", {})
        return {"redrive": _json_attr(a.get("RedrivePolicy")), "policy": _json_attr(a.get("Policy"))}

    def secret():
        d = _aws("secretsmanager", "describe-secret", "--secret-id", f"{name}/app")
        return None if d is None else {"rotation": bool(d.get("RotationEnabled")), "tags": d.get("Tags") or []}

    def role():
        r = _aws("iam", "get-role", "--role-name", f"{name}-app")
        if r is None:
            return None
        att = (_aws("iam", "list-attached-role-policies", "--role-name", f"{name}-app") or {}).get("AttachedPolicies") or []
        inline = (_aws("iam", "list-role-policies", "--role-name", f"{name}-app") or {}).get("PolicyNames") or []
        return {"trust": r["Role"].get("AssumeRolePolicyDocument"), "attached": [a["PolicyName"] for a in att],
                "inline": inline, "arn": r["Role"].get("Arn")}

    for k, fn in (("s3", s3), ("sqs", sqs), ("secret", secret), ("role", role)):
        section(k, fn)
    return out, errors


def collect(name):
    """Return a snapshot for namespace/space `name`."""
    ns_json = _k("get", "ns", name)
    with ThreadPoolExecutor(max_workers=8) as ex:
        f = {
            "quota": ex.submit(_k, "-n", name, "get", "resourcequota", "standard-quota"),
            "limitrange": ex.submit(_k, "-n", name, "get", "limitrange", "standard-limits"),
            "np": ex.submit(_k, "-n", name, "get", "networkpolicy"),
            "rb": ex.submit(_k, "-n", name, "get", "rolebinding"),
            "s3": ex.submit(_s3, name), "sqs": ex.submit(_sqs, name), "logs": ex.submit(_logs, name),
            "secret": ex.submit(_aws, "secretsmanager", "describe-secret", "--secret-id", f"{name}/app"),
            "iam": ex.submit(_iam, name),
        }
        extra_k = ex.submit(_k8s_extra, name) if ns_json else None
        extra_a = ex.submit(_aws_extra, name) if ns_json else None
        r = {k: v.result() for k, v in f.items()}
        errors = {}
        k8s = aws_x = None
        for label, fut in (("k8s", extra_k), ("aws", extra_a)):
            if fut is None:
                continue
            try:
                res = fut.result()
            except Exception as e:
                errors[label] = str(e)[:160]
                continue
            if label == "k8s":
                k8s = res
            else:
                aws_x, aws_err = res
                errors.update({f"aws.{k}": v for k, v in aws_err.items()})
    return {
        "k8s": k8s, "aws_x": aws_x, "errors": errors,
        "ns": ns_json,
        "quota": r["quota"], "limitrange": r["limitrange"],
        "netpols": {i["metadata"]["name"]: i["spec"] for i in (r["np"] or {}).get("items", [])},
        "rolebindings": [{"name": i["metadata"]["name"], "role": i["roleRef"]["name"],
                          "subjects": [s.get("name", "") for s in i.get("subjects") or []]}
                         for i in (r["rb"] or {}).get("items", [])],
        "s3": r["s3"], "sqs": r["sqs"], "logs": r["logs"],
        "secret": bool(r["secret"]), "iam": r["iam"],
    }
