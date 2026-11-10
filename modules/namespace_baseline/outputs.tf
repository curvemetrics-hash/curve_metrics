output "namespace" {
  description = "Name of the created namespace."
  value       = kubernetes_namespace_v1.this.metadata[0].name
}

output "quota" {
  description = "Resource quota applied."
  value       = kubernetes_resource_quota_v1.this.spec[0].hard
}
