#!/usr/bin/env python3
"""Policy gate: checks an OpenTofu plan (JSON) against the platform rules.

Usage: policy_check.py plan.json
Exit status 0 when every rule passes, 1 otherwise.
"""
import json
import sys

FORBIDDEN_GROUPS = {"system:authenticated", "system:unauthenticated"}
REQUIRED_LABELS = ("curve-metrics/team", "curve-metrics/environment")


def resources(plan):
    root = plan.get("planned_values", {}).get("root_module", {})
    stack = [root]
    while stack:
        mod = stack.pop()
        for res in mod.get("resources", []):
            yield res
        stack.extend(mod.get("child_modules", []))


def check(plan):
    problems = []
    res = list(resources(plan))
    by_type = {}
    for r in res:
        by_type.setdefault(r["type"], []).append(r)

    namespaces = by_type.get("kubernetes_namespace_v1", [])
    if not namespaces:
        problems.append("no namespace in plan")
    for ns in namespaces:
        labels = (ns["values"]["metadata"][0].get("labels") or {})
        for key in REQUIRED_LABELS:
            if not labels.get(key):
                problems.append(f"namespace {ns['address']} missing label {key}")

    quotas = by_type.get("kubernetes_resource_quota_v1", [])
    if not quotas:
        problems.append("no resource quota")
    for q in quotas:
        hard = (q["values"].get("spec") or [{}])[0].get("hard") or {}
        for key in ("requests.storage", "persistentvolumeclaims", "count/ingresses.networking.k8s.io"):
            if key not in hard:
                problems.append(f"{q['address']} has no {key} limit")
    if not by_type.get("kubernetes_limit_range_v1"):
        problems.append("no limit range")

    deny = [
        p for p in by_type.get("kubernetes_network_policy_v1", [])
        if p["values"]["metadata"][0].get("name") == "default-deny-ingress"
    ]
    if not deny:
        problems.append("no default-deny ingress network policy")

    buckets = by_type.get("aws_s3_bucket", [])
    blocks = by_type.get("aws_s3_bucket_public_access_block", [])
    if len(blocks) < len(buckets):
        problems.append("an S3 bucket has no public access block")
    for blk in blocks:
        v = blk["values"]
        if not all(v.get(k) for k in ("block_public_acls", "block_public_policy",
                                      "ignore_public_acls", "restrict_public_buckets")):
            problems.append(f"{blk['address']} does not block all public access")
    for q in by_type.get("aws_sqs_queue", []):
        if not q["values"].get("sqs_managed_sse_enabled"):
            problems.append(f"{q['address']} is not encrypted")
    for lg in by_type.get("aws_cloudwatch_log_group", []):
        if not lg["values"].get("retention_in_days"):
            problems.append(f"{lg['address']} has no retention period")
    for pol in by_type.get("aws_iam_policy", []):
        text = pol["values"].get("policy")  # unknown at plan time when it refers to new resources
        if text and ('"Action":"*"' in text.replace(" ", "") or '"*"' in text):
            problems.append(f"{pol['address']} contains a wildcard action or resource")

    for rb in by_type.get("kubernetes_role_binding_v1", []):
        values = rb["values"]
        if values["role_ref"][0]["name"] == "cluster-admin":
            problems.append(f"{rb['address']} binds cluster-admin")
        for subject in values["subject"]:
            if subject["name"] in FORBIDDEN_GROUPS:
                problems.append(f"{rb['address']} grants access to {subject['name']}")
    return problems


def main():
    with open(sys.argv[1]) as handle:
        plan = json.load(handle)
    problems = check(plan)
    if problems:
        print("POLICY FAILED:")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("policy check passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
