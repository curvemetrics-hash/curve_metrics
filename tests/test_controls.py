"""Unit tests for compliance controls: each control passes when intact and fails when broken."""
import copy
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spaces import controls  # noqa: E402

GOOD = {
    "ns": {"metadata": {"labels": {"curve-metrics/team": "a", "curve-metrics/environment": "dev",
                                   "curve-metrics/size": "small", "app.kubernetes.io/managed-by": "platform-blueprint"}}},
    "quota": {"spec": {"hard": {"requests.cpu": "2", "pods": "20", "requests.storage": "50Gi"}}},
    "limitrange": {"x": 1},
    "netpols": {"default-deny-ingress": {"podSelector": {}, "policyTypes": ["Ingress"]},
                "allow-same-namespace": {"podSelector": {}, "ingress": [{"from": [{"podSelector": {}}]}]}},
    "rolebindings": [{"name": "admin-alpha-admins", "role": "admin", "subjects": ["alpha-admins"]}],
    "s3": {"exists": True, "public_block": [True] * 4, "versioning": "Enabled", "encryption": "AES256"},
    "sqs": {"exists": True, "sse": True},
    "logs": {"exists": True, "retention": 30},
    "secret": True,
    "iam": {"policy_statements": [{"Action": ["s3:GetObject"], "Resource": ["arn:aws:s3:::a-data"]}]},
}


def failing(snapshot):
    return {c["id"] for c in controls.evaluate(snapshot)["controls"] if not c["passed"]}


def mutate(fn):
    s = copy.deepcopy(GOOD)
    fn(s)
    return s


def test_good_snapshot_passes_everything():
    r = controls.evaluate(GOOD)
    assert r["compliant"] and r["passed"] == r["total"] == len(controls.CONTROLS)


def test_each_control_fails_when_broken():
    cases = {
        "NET-1": lambda s: s["netpols"].pop("default-deny-ingress"),
        "NET-2": lambda s: s["netpols"].update({"open": {"podSelector": {}, "ingress": [{}]}}),
        "ACC-1": lambda s: s["rolebindings"].append({"name": "x", "role": "admin", "subjects": ["system:authenticated"]}),
        "ACC-2": lambda s: s.update({"rolebindings": []}),
        "RES-1": lambda s: s["quota"]["spec"]["hard"].update({"pods": "999"}),
        "RES-2": lambda s: s.update({"limitrange": None}),
        "OWN-1": lambda s: s["ns"]["metadata"]["labels"].pop("curve-metrics/team"),
        "STO-1": lambda s: s["s3"].update({"public_block": None}),
        "STO-2": lambda s: s["s3"].update({"versioning": "Suspended"}),
        "STO-3": lambda s: s["s3"].update({"encryption": None}),
        "MSG-1": lambda s: s["sqs"].update({"sse": False}),
        "LOG-1": lambda s: s["logs"].update({"retention": None}),
        "SEC-1": lambda s: s.update({"secret": False}),
        "SEC-2": lambda s: s["iam"]["policy_statements"].append({"Action": "*", "Resource": "*"}),
    }
    assert set(cases) == {c[0] for c in controls.CONTROLS}, "every control needs a failing case"
    for cid, fn in cases.items():
        assert failing(mutate(fn)) == {cid}, f"{cid} should be the only failure"


def test_cluster_admin_role_fails_even_for_named_group():
    s = mutate(lambda s: s["rolebindings"].append({"name": "ca", "role": "cluster-admin", "subjects": ["alpha-admins"]}))
    assert failing(s) == {"ACC-1"}


def test_empty_snapshot_fails_not_crashes():
    r = controls.evaluate({})
    assert not r["compliant"] and r["passed"] == 0


def test_size_presets_match_terraform_module():
    tf = open(os.path.join(os.path.dirname(__file__), "..", "modules", "namespace_baseline", "main.tf")).read()
    for size, want in controls.SIZE_PRESETS.items():
        line = re.search(rf'{size}\s*=\s*\{{(.*?)\}}', tf).group(1)
        assert re.search(rf'requests_cpu\s*=\s*"{want["requests.cpu"]}"', line)
        assert re.search(rf'pods\s*=\s*"{want["pods"]}"', line)
        assert re.search(rf'storage\s*=\s*"{want["requests.storage"]}"', line)
