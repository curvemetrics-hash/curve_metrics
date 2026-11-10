provider "kubernetes" {
  config_path = var.kubeconfig_path
}

# With aws_local = true every AWS call goes to LocalStack at aws_endpoint.
# With aws_local = false the provider talks to real AWS with normal credentials.
provider "aws" {
  region                      = var.aws_region
  access_key                  = var.aws_local ? "test" : null
  secret_key                  = var.aws_local ? "test" : null
  skip_credentials_validation = var.aws_local
  skip_metadata_api_check     = var.aws_local
  skip_requesting_account_id  = var.aws_local
  s3_use_path_style           = var.aws_local

  dynamic "endpoints" {
    for_each = var.aws_local ? [1] : []
    content {
      s3             = var.aws_endpoint
      iam            = var.aws_endpoint
      sqs            = var.aws_endpoint
      secretsmanager = var.aws_endpoint
      cloudwatchlogs = var.aws_endpoint
      sts            = var.aws_endpoint
    }
  }
}

module "environment" {
  source = "../../modules/namespace_baseline"

  name                          = var.name
  team                          = var.team
  environment                   = var.environment
  size                          = var.size
  admin_groups                  = var.admin_groups
  allow_ingress_from_namespaces = var.allow_ingress_from_namespaces
  extra_labels                  = var.extra_labels
  allow_ingress_controller      = var.allow_ingress_controller
  ingress_controller_namespace  = var.ingress_controller_namespace
}

module "cloud" {
  count  = var.enable_cloud_resources ? 1 : 0
  source = "../../modules/team_cloud_bindings"

  name        = var.name
  namespace   = module.environment.namespace
  team        = var.team
  environment = var.environment

  # null keeps the module defaults (a placeholder used with LocalStack)
  oidc_provider_arn = coalesce(var.oidc_provider_arn, "arn:aws:iam::000000000000:oidc-provider/oidc.eks.local/id/EXAMPLE")
  oidc_issuer       = coalesce(var.oidc_issuer, "oidc.eks.local/id/EXAMPLE")

  permissions_boundary_arn = var.permissions_boundary_arn
}
