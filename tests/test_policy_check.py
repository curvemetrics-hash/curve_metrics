import copy
import importlib.util
import pathlib

spec = importlib.util.spec_from_file_location(
    "policy_check", pathlib.Path(__file__).parent.parent / "scripts" / "policy_check.py"
)
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)


def good_plan():
    def res(rtype, values, address=None):
        return {"type": rtype, "address": address or rtype, "values": values}

    return {
        "planned_values": {
            "root_module": {
                "child_modules": [
                    {
                        "resources": [
                            res("kubernetes_namespace_v1", {"metadata": [{"labels": {
                                "curve-metrics/team": "a", "curve-metrics/environment": "dev"}}]}),
                            res("kubernetes_resource_quota_v1", {"spec": [{"hard": {"requests.storage": "50Gi", "persistentvolumeclaims": "5", "count/ingresses.networking.k8s.io": "3"}}]}),
                            res("kubernetes_limit_range_v1", {}),
                            res("kubernetes_network_policy_v1", {"metadata": [{"name": "default-deny-ingress"}]}),
                            res("kubernetes_role_binding_v1", {
                                "role_ref": [{"name": "admin"}],
                                "subject": [{"name": "a-admins"}]}, "rb"),
                        ]
                    }
                ]
            }
        }
    }


def test_good_plan_passes():
    assert policy.check(good_plan()) == []


def _mutate(fn):
    plan = copy.deepcopy(good_plan())
    fn(plan["planned_values"]["root_module"]["child_modules"][0]["resources"])
    return policy.check(plan)


def test_missing_label_fails():
    out = _mutate(lambda r: r[0]["values"]["metadata"][0]["labels"].pop("curve-metrics/team"))
    assert any("missing label" in p for p in out)


def test_quota_without_storage_limit_fails():
    out = _mutate(lambda r: r[1]["values"]["spec"][0]["hard"].pop("requests.storage"))
    assert any("requests.storage" in p for p in out)


def test_missing_quota_fails():
    out = _mutate(lambda r: r.__delitem__(1))
    assert "no resource quota" in out


def test_missing_default_deny_fails():
    out = _mutate(lambda r: r.__delitem__(3))
    assert any("default-deny" in p for p in out)


def test_cluster_admin_binding_fails():
    out = _mutate(lambda r: r[4]["values"]["role_ref"][0].update(name="cluster-admin"))
    assert any("cluster-admin" in p for p in out)


def test_authenticated_group_fails():
    out = _mutate(lambda r: r[4]["values"]["subject"][0].update(name="system:authenticated"))
    assert any("system:authenticated" in p for p in out)


def test_empty_plan_fails():
    assert policy.check({"planned_values": {"root_module": {}}})


def _with_cloud(plan, extra):
    plan["planned_values"]["root_module"]["child_modules"][0]["resources"].extend(extra)
    return plan


def _r(rtype, values):
    return {"type": rtype, "address": rtype, "values": values}


def good_cloud():
    return [
        _r("aws_s3_bucket", {}),
        _r("aws_s3_bucket_public_access_block", {
            "block_public_acls": True, "block_public_policy": True,
            "ignore_public_acls": True, "restrict_public_buckets": True}),
        _r("aws_sqs_queue", {"sqs_managed_sse_enabled": True}),
        _r("aws_cloudwatch_log_group", {"retention_in_days": 30}),
    ]


def test_good_cloud_resources_pass():
    assert policy.check(_with_cloud(good_plan(), good_cloud())) == []


def test_bucket_without_public_access_block_fails():
    out = policy.check(_with_cloud(good_plan(), good_cloud()[:1]))
    assert any("no public access block" in p for p in out)


def test_partial_public_access_block_fails():
    cloud = good_cloud()
    cloud[1]["values"]["restrict_public_buckets"] = False
    out = policy.check(_with_cloud(good_plan(), cloud))
    assert any("does not block all public access" in p for p in out)


def test_unencrypted_queue_fails():
    cloud = good_cloud()
    cloud[2]["values"]["sqs_managed_sse_enabled"] = False
    assert any("not encrypted" in p for p in policy.check(_with_cloud(good_plan(), cloud)))


def test_log_group_without_retention_fails():
    cloud = good_cloud()
    cloud[3]["values"]["retention_in_days"] = 0
    assert any("no retention" in p for p in policy.check(_with_cloud(good_plan(), cloud)))


def test_wildcard_iam_policy_fails():
    cloud = good_cloud() + [_r("aws_iam_policy", {"policy": '{"Statement":[{"Action":"*","Resource":"*"}]}'})]
    assert any("wildcard" in p for p in policy.check(_with_cloud(good_plan(), cloud)))
