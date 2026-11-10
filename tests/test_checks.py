"""Tests for the extended checks: each fails on a broken snapshot, passes on a clean one, and reports unknown when data is missing."""
import copy
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spaces import checks  # noqa: E402

NOW = 1_800_000_000
OLD = "2026-01-01T00:00:00Z"

GOOD_SPEC = {"serviceAccountName": "app", "securityContext": {"runAsNonRoot": True},
             "containers": [{"name": "c", "image": "registry/app:1.2.3",
                             "securityContext": {"allowPrivilegeEscalation": False, "runAsNonRoot": True},
                             "resources": {"limits": {"cpu": "1", "memory": "1Gi"}},
                             "readinessProbe": {"httpGet": {"path": "/"}}, "env": [{"name": "MODE", "value": "x"}]}]}

GOOD = {
    "ns": {"metadata": {"name": "a", "labels": {"pod-security.kubernetes.io/enforce": "restricted"}}},
    "errors": {},
    "k8s": {
        "Deployment": [{"metadata": {"name": "web"}, "spec": {"replicas": 2, "template": {"spec": GOOD_SPEC}}, "status": {"readyReplicas": 2}}],
        "Pod": [{"metadata": {"name": "web-1", "ownerReferences": [{}], "creationTimestamp": OLD},
                 "status": {"phase": "Running", "containerStatuses": [{"restartCount": 0, "state": {"running": {}}}]}}],
        "Service": [{"metadata": {"name": "web"}, "spec": {"type": "ClusterIP"}}],
        "Ingress": [{"metadata": {"name": "web"}, "spec": {"tls": [{"hosts": ["x"]}]}}],
        "NetworkPolicy": [{"metadata": {"name": "default-deny-ingress"}, "spec": {"policyTypes": ["Ingress", "Egress"]}}],
        "Role": [{"metadata": {"name": "r"}, "rules": [{"resources": ["pods"], "verbs": ["get"]}]}],
        "RoleBinding": [{"metadata": {"name": "team-admin-1"}, "roleRef": {"name": "admin"},
                         "subjects": [{"kind": "Group", "name": "g"}]}],
        "ServiceAccount": [{"metadata": {"name": "app", "annotations": {"eks.amazonaws.com/role-arn": "arn:aws:iam::1:role/a-app"}}}],
        "ConfigMap": [{"metadata": {"name": "cloud-resources"},
                       "data": {"S3_BUCKET": "a-data", "SECRET_ID": "a/app", "LOG_GROUP": "/curve-metrics/a", "SQS_QUEUE_URL": "http://x/1/a-events"}}],
        "ResourceQuota": [{"metadata": {"name": "standard-quota"}, "status": {"hard": {"pods": "20", "requests.cpu": "2"}, "used": {"pods": "2", "requests.cpu": "500m"}}}],
        "PersistentVolumeClaim": [{"metadata": {"name": "d"}, "status": {"phase": "Bound"}}],
        "Job": [{"metadata": {"name": "j"}, "spec": {"template": {"spec": GOOD_SPEC}}, "status": {"succeeded": 1}}],
        "Event": [],
    },
    "s3": {"exists": True}, "logs": {"exists": True, "retention": 30},
    "iam": {"policy_statements": [{"Effect": "Allow", "Action": ["s3:GetObject"], "Resource": ["arn"]}]},
    "aws_x": {
        "s3": {"policy": {"Statement": [{"Effect": "Deny", "Principal": "*", "Action": "s3:*",
                                         "Condition": {"Bool": {"aws:SecureTransport": "false"}}}]},
               "tags": {"managed-by": "x", "team": "a", "env": "dev"}},
        "sqs": {"redrive": {"deadLetterTargetArn": "x"}, "policy": None},
        "secret": {"rotation": True, "tags": []},
        "role": {"trust": {"Statement": [{"Effect": "Allow", "Principal": {"Federated": "arn"},
                                          "Condition": {"StringEquals": {"oidc:sub": "system:serviceaccount:a:app"}}}]},
                 "attached": ["a-app"], "inline": [], "arn": "arn:aws:iam::1:role/a-app"},
    },
}


def run(s):
    return {r["id"]: r for r in checks.evaluate(s, now=NOW)["extended"]}


def mutate(fn):
    s = copy.deepcopy(GOOD)
    fn(s)
    return s


def spec(s):
    return s["k8s"]["Deployment"][0]["spec"]["template"]["spec"]


def test_clean_snapshot_has_no_failures():
    bad = {k: (v["status"], v["evidence"]) for k, v in run(GOOD).items() if v["status"] != "pass"}
    assert not bad, bad


CASES = {
    "WLS-1": lambda s: spec(s)["containers"][0]["securityContext"].update({"privileged": True}),
    "WLS-2": lambda s: spec(s).update({"hostNetwork": True}),
    "WLS-3": lambda s: spec(s).update({"volumes": [{"name": "v", "hostPath": {"path": "/"}}]}),
    "WLS-4": lambda s: spec(s)["containers"][0]["securityContext"].pop("allowPrivilegeEscalation"),
    "WLS-5": lambda s: (spec(s).pop("securityContext"), spec(s)["containers"][0]["securityContext"].update({"runAsUser": 0})),
    "WLS-6": lambda s: spec(s)["containers"][0]["securityContext"].update({"capabilities": {"add": ["SYS_ADMIN"]}}),
    "WLS-7": lambda s: spec(s)["containers"][0].update({"image": "nginx:latest"}),
    "WLS-8": lambda s: spec(s)["containers"][0]["env"].append({"name": "DB_PASSWORD", "value": "hunter2"}),
    "WLS-9": lambda s: spec(s)["containers"][0].pop("readinessProbe"),
    "WLS-10": lambda s: spec(s).pop("serviceAccountName"),
    "WLS-11": lambda s: spec(s)["containers"][0].update({"resources": {}}),
    "NETX-1": lambda s: s["k8s"]["Service"][0]["spec"].update({"type": "LoadBalancer"}),
    "NETX-2": lambda s: s["k8s"]["Ingress"][0]["spec"].pop("tls"),
    "NETX-3": lambda s: s["k8s"]["NetworkPolicy"].append({"metadata": {"name": "x"}, "spec": {"ingress": [{"from": [{"ipBlock": {"cidr": "0.0.0.0/0"}}]}]}}),
    "NETX-4": lambda s: s["k8s"]["NetworkPolicy"][0]["spec"].update({"policyTypes": ["Ingress"]}),
    "ACCX-1": lambda s: s["k8s"]["Role"][0]["rules"].append({"resources": ["*"], "verbs": ["*"]}),
    "ACCX-2": lambda s: s["k8s"]["Role"][0]["rules"].append({"resources": ["secrets"], "verbs": ["get"]}),
    "ACCX-3": lambda s: s["k8s"]["RoleBinding"].append({"metadata": {"name": "hand-made"}, "roleRef": {"name": "admin"}, "subjects": []}),
    "ACCX-4": lambda s: s["k8s"]["RoleBinding"][0].update({"subjects": [{"kind": "ServiceAccount", "name": "z", "namespace": "other"}]}),
    "PSA-1": lambda s: s["ns"]["metadata"]["labels"].clear(),
    "DRF-1": lambda s: s["k8s"]["NetworkPolicy"].append({"metadata": {"name": "mystery"}, "spec": {}}),
    "DRF-2": lambda s: s["k8s"]["ServiceAccount"][0]["metadata"].update({"annotations": {}}),
    "DRF-3": lambda s: s["k8s"]["ConfigMap"][0]["data"].update({"S3_BUCKET": "other"}),
    "RTH-1": lambda s: s["k8s"]["Pod"][0]["status"]["containerStatuses"][0].update({"state": {"waiting": {"reason": "CrashLoopBackOff"}}}),
    "RTH-1b": lambda s: s["k8s"]["Pod"][0]["status"]["containerStatuses"][0].update({"state": {"terminated": {"reason": "Error", "exitCode": 1}}}),
    "RTH-2": lambda s: s["k8s"]["Pod"][0]["status"].update({"phase": "Pending"}),
    "RTH-3": lambda s: s["k8s"]["Pod"][0]["status"]["containerStatuses"][0].update({"restartCount": 9}),
    "RTH-4": lambda s: s["k8s"]["Deployment"][0]["status"].update({"readyReplicas": 1}),
    "RTH-5": lambda s: s["k8s"]["ResourceQuota"][0]["status"]["used"].update({"pods": "19"}),
    "RTH-6": lambda s: s["k8s"]["PersistentVolumeClaim"][0]["status"].update({"phase": "Pending"}),
    "RTH-7": lambda s: s["k8s"]["Event"].append({"type": "Warning", "reason": "FailedScheduling", "lastTimestamp": "2027-01-15T07:59:00Z"}),
    "RTH-8": lambda s: s["k8s"]["Job"][0]["status"].update({"failed": 2}),
    "S3X-1": lambda s: s["aws_x"]["s3"].update({"policy": None}),
    "S3X-2": lambda s: s["aws_x"]["s3"].update({"policy": {"Statement": [{"Effect": "Allow", "Principal": "*", "Action": "s3:GetObject"}]}}),
    "S3X-3": lambda s: s["aws_x"]["s3"].update({"tags": {}}),
    "SQSX-1": lambda s: s["aws_x"]["sqs"].update({"redrive": None}),
    "SQSX-2": lambda s: s["aws_x"]["sqs"].update({"policy": {"Statement": [{"Effect": "Allow", "Principal": {"AWS": "*"}}]}}),
    "SECX-1": lambda s: s["aws_x"]["secret"].update({"rotation": False}),
    "IAMX-1": lambda s: s["aws_x"]["role"]["trust"]["Statement"][0].update({"Principal": "*"}),
    "IAMX-2": lambda s: s["aws_x"]["role"]["attached"].append("AdministratorAccess"),
    "IAMX-3": lambda s: s["aws_x"]["role"].update({"inline": ["quick-fix"]}),
    "IAMX-4": lambda s: s["iam"]["policy_statements"].append({"Effect": "Allow", "Action": ["s3:*"], "Resource": ["arn"]}),
    "LOGX-1": lambda s: s["logs"].update({"retention": 7}),
}


def test_every_check_has_a_failing_case():
    assert {k.removesuffix("b") for k in CASES} == {c["id"] for c in checks.CHECKS}


def test_each_check_fails_when_broken():
    for key, fn in CASES.items():
        cid = key.removesuffix("b")  # "RTH-1b" is a second failing case for RTH-1
        r = run(mutate(fn))[cid]
        assert r["status"] == "fail", f"{cid}: {r}"
        assert r["fix"], f"{cid} needs a remediation hint"


def test_only_the_broken_check_fails():
    for key, fn in CASES.items():
        cid = key.removesuffix("b")
        failed = {k for k, v in run(mutate(fn)).items() if v["status"] == "fail"}
        # a few faults legitimately trip a neighbouring check; the target must be among them
        assert cid in failed and len(failed) <= 2, (cid, failed)


def test_missing_data_is_unknown_not_pass():
    r = run({**GOOD, "k8s": None, "errors": {"k8s": "kubectl failed"}})
    assert r["WLS-1"]["status"] == "unknown" and "kubectl failed" in r["WLS-1"]["evidence"]
    r = run({**GOOD, "aws_x": {**GOOD["aws_x"]}, "errors": {"aws.role": "denied"}})
    assert r["IAMX-1"]["status"] == "unknown"


def test_missing_resource_is_na_not_double_counted():
    r = run(mutate(lambda s: s["aws_x"].update({"sqs": None})))
    assert r["SQSX-1"]["status"] == "na" and r["SQSX-2"]["status"] == "na"


def test_missing_namespace_is_na_everywhere():
    assert {v["status"] for v in run({}).values()} == {"na"}


def test_summary_and_grade():
    rep = checks.evaluate(mutate(CASES["WLS-1"]), now=NOW)
    assert rep["extended_summary"]["severity"]["high"] == 1
    assert checks.grade({"compliant": True, **rep}) == "at risk"
    assert checks.grade({"compliant": False, **rep}) == "non-compliant"
    clean = checks.evaluate(GOOD, now=NOW)
    assert checks.grade({"compliant": True, **clean}) == "healthy"


def test_bad_object_does_not_hide_other_checks():
    s = mutate(lambda s: s["k8s"]["Role"].append({"metadata": {"name": "x"}, "rules": 5}))
    r = run(s)
    assert r["ACCX-1"]["status"] == "unknown" and r["WLS-1"]["status"] == "pass"
