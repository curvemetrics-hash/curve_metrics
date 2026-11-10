output "namespace" {
  value = module.environment.namespace
}

output "quota" {
  value = module.environment.quota
}

output "cloud" {
  value = var.enable_cloud_resources ? {
    bucket      = module.cloud[0].bucket
    queue_url   = module.cloud[0].queue_url
    secret_name = module.cloud[0].secret_name
    log_group   = module.cloud[0].log_group
    role_arn    = module.cloud[0].role_arn
  } : null
}
