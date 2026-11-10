mock_provider "kubernetes" {}

variables {
  name         = "team-alpha-dev"
  team         = "alpha"
  environment  = "dev"
  size         = "small"
  admin_groups = ["alpha-admins"]
}

run "small_environment_has_standard_labels_and_quota" {
  command = plan

  assert {
    condition     = kubernetes_namespace_v1.this.metadata[0].labels["curve-metrics/team"] == "alpha"
    error_message = "team label missing"
  }
  assert {
    condition     = kubernetes_namespace_v1.this.metadata[0].labels["curve-metrics/environment"] == "dev"
    error_message = "environment label missing"
  }
  assert {
    condition     = kubernetes_resource_quota_v1.this.spec[0].hard["requests.cpu"] == "2" && kubernetes_resource_quota_v1.this.spec[0].hard["pods"] == "20"
    error_message = "small quota wrong"
  }
  assert {
    condition     = kubernetes_resource_quota_v1.this.spec[0].hard["requests.storage"] == "50Gi" && kubernetes_resource_quota_v1.this.spec[0].hard["persistentvolumeclaims"] == "5"
    error_message = "small storage defaults wrong"
  }
  assert {
    condition     = kubernetes_resource_quota_v1.this.spec[0].hard["count/ingresses.networking.k8s.io"] == "3"
    error_message = "small ingress limit wrong"
  }
}

run "large_environment_quota" {
  command = plan
  variables {
    size = "large"
  }
  assert {
    condition     = kubernetes_resource_quota_v1.this.spec[0].hard["limits.memory"] == "32Gi" && kubernetes_resource_quota_v1.this.spec[0].hard["pods"] == "100"
    error_message = "large quota wrong"
  }
  assert {
    condition     = kubernetes_resource_quota_v1.this.spec[0].hard["requests.storage"] == "500Gi" && kubernetes_resource_quota_v1.this.spec[0].hard["persistentvolumeclaims"] == "20" && kubernetes_resource_quota_v1.this.spec[0].hard["count/ingresses.networking.k8s.io"] == "10"
    error_message = "large storage and ingress defaults wrong"
  }
}

run "default_deny_network_policy_present" {
  command = plan

  assert {
    condition     = length(kubernetes_network_policy_v1.default_deny_ingress.spec[0].policy_types) == 1 && kubernetes_network_policy_v1.default_deny_ingress.spec[0].policy_types[0] == "Ingress"
    error_message = "default deny ingress policy missing"
  }
}

run "ingress_controller_policy_by_default" {
  command = plan

  assert {
    condition     = length(kubernetes_network_policy_v1.allow_ingress_controller) == 1
    error_message = "ingress controller policy should exist by default"
  }
}

run "ingress_controller_policy_can_be_disabled" {
  command = plan
  variables {
    allow_ingress_controller = false
  }
  assert {
    condition     = length(kubernetes_network_policy_v1.allow_ingress_controller) == 0
    error_message = "ingress controller policy should be absent when disabled"
  }
}

run "no_extra_namespace_policy_without_allowlist" {
  command = plan
  assert {
    condition     = length(kubernetes_network_policy_v1.allow_listed_namespaces) == 0
    error_message = "allow-listed policy should not exist without an allowlist"
  }
}

run "allowlist_creates_policy" {
  command = plan
  variables {
    allow_ingress_from_namespaces = ["monitoring"]
  }
  assert {
    condition     = length(kubernetes_network_policy_v1.allow_listed_namespaces) == 1
    error_message = "allow-listed policy missing"
  }
}

run "admin_groups_create_role_bindings" {
  command = plan
  variables {
    admin_groups = ["alpha-admins", "alpha-leads"]
  }
  assert {
    condition     = length(kubernetes_role_binding_v1.admins) == 2
    error_message = "expected two role bindings"
  }
}

run "no_admin_groups_no_role_bindings" {
  command = plan
  variables {
    admin_groups = []
  }
  assert {
    condition     = length(kubernetes_role_binding_v1.admins) == 0
    error_message = "expected no role bindings"
  }
}

run "rejects_invalid_size" {
  command = plan
  variables {
    size = "huge"
  }
  expect_failures = [var.size]
}

run "rejects_invalid_environment" {
  command = plan
  variables {
    environment = "staging"
  }
  expect_failures = [var.environment]
}

run "rejects_invalid_name" {
  command = plan
  variables {
    name = "Bad_Name"
  }
  expect_failures = [var.name]
}

run "rejects_wildcard_admin_group" {
  command = plan
  variables {
    admin_groups = ["system:authenticated"]
  }
  expect_failures = [var.admin_groups]
}
