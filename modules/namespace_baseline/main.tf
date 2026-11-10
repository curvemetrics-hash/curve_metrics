locals {
  size_presets = {
    small  = { requests_cpu = "2", limits_cpu = "4", requests_memory = "4Gi", limits_memory = "8Gi", pods = "20", storage = "50Gi", pvcs = "5", ingresses = "3" }
    medium = { requests_cpu = "4", limits_cpu = "8", requests_memory = "8Gi", limits_memory = "16Gi", pods = "50", storage = "200Gi", pvcs = "10", ingresses = "5" }
    large  = { requests_cpu = "8", limits_cpu = "16", requests_memory = "16Gi", limits_memory = "32Gi", pods = "100", storage = "500Gi", pvcs = "20", ingresses = "10" }
  }
  preset = local.size_presets[var.size]

  labels = merge(var.extra_labels, {
    "app.kubernetes.io/managed-by" = "platform-blueprint"
    "curve-metrics/team"           = var.team
    "curve-metrics/environment"    = var.environment
    "curve-metrics/size"           = var.size
  })
}

resource "kubernetes_namespace_v1" "this" {
  metadata {
    name   = var.name
    labels = local.labels
  }
}

resource "kubernetes_resource_quota_v1" "this" {
  metadata {
    name      = "standard-quota"
    namespace = kubernetes_namespace_v1.this.metadata[0].name
  }

  spec {
    hard = {
      "requests.cpu"    = local.preset.requests_cpu
      "limits.cpu"      = local.preset.limits_cpu
      "requests.memory" = local.preset.requests_memory
      "limits.memory"   = local.preset.limits_memory
      "pods"            = local.preset.pods
      # storage and ingress defaults
      "requests.storage"                  = local.preset.storage
      "persistentvolumeclaims"            = local.preset.pvcs
      "count/ingresses.networking.k8s.io" = local.preset.ingresses
    }
  }
}

resource "kubernetes_limit_range_v1" "this" {
  metadata {
    name      = "standard-limits"
    namespace = kubernetes_namespace_v1.this.metadata[0].name
  }

  spec {
    limit {
      type = "Container"
      default = {
        cpu    = "500m"
        memory = "512Mi"
      }
      default_request = {
        cpu    = "100m"
        memory = "128Mi"
      }
    }
  }
}

resource "kubernetes_network_policy_v1" "default_deny_ingress" {
  metadata {
    name      = "default-deny-ingress"
    namespace = kubernetes_namespace_v1.this.metadata[0].name
  }

  spec {
    pod_selector {}
    policy_types = ["Ingress"]
  }
}

resource "kubernetes_network_policy_v1" "allow_same_namespace" {
  metadata {
    name      = "allow-same-namespace"
    namespace = kubernetes_namespace_v1.this.metadata[0].name
  }

  spec {
    pod_selector {}
    policy_types = ["Ingress"]

    ingress {
      from {
        pod_selector {}
      }
    }
  }
}

# Ingress default: let the cluster's ingress controller reach workloads in this namespace.
resource "kubernetes_network_policy_v1" "allow_ingress_controller" {
  count = var.allow_ingress_controller ? 1 : 0

  metadata {
    name      = "allow-ingress-controller"
    namespace = kubernetes_namespace_v1.this.metadata[0].name
  }

  spec {
    pod_selector {}
    policy_types = ["Ingress"]

    ingress {
      from {
        namespace_selector {
          match_labels = {
            "kubernetes.io/metadata.name" = var.ingress_controller_namespace
          }
        }
      }
    }
  }
}

resource "kubernetes_network_policy_v1" "allow_listed_namespaces" {
  count = length(var.allow_ingress_from_namespaces) > 0 ? 1 : 0

  metadata {
    name      = "allow-listed-namespaces"
    namespace = kubernetes_namespace_v1.this.metadata[0].name
  }

  spec {
    pod_selector {}
    policy_types = ["Ingress"]

    dynamic "ingress" {
      for_each = toset(var.allow_ingress_from_namespaces)
      content {
        from {
          namespace_selector {
            match_labels = {
              "kubernetes.io/metadata.name" = ingress.value
            }
          }
        }
      }
    }
  }
}

resource "kubernetes_role_binding_v1" "admins" {
  for_each = toset(var.admin_groups)

  metadata {
    name      = "team-admin-${substr(sha1(each.value), 0, 8)}"
    namespace = kubernetes_namespace_v1.this.metadata[0].name
  }

  role_ref {
    api_group = "rbac.authorization.k8s.io"
    kind      = "ClusterRole"
    name      = "admin"
  }

  subject {
    kind      = "Group"
    name      = each.value
    api_group = "rbac.authorization.k8s.io"
  }
}
