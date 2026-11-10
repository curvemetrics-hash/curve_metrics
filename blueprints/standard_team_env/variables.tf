variable "kubeconfig_path" {
  description = "Path to the kubeconfig for the target cluster."
  type        = string
}

variable "name" {
  type = string
}

variable "team" {
  type = string
}

variable "environment" {
  type = string
}

variable "size" {
  type    = string
  default = "small"
}

variable "admin_groups" {
  type    = list(string)
  default = []
}

variable "allow_ingress_from_namespaces" {
  type    = list(string)
  default = []
}

variable "allow_ingress_controller" {
  type    = bool
  default = true
}

variable "ingress_controller_namespace" {
  type    = string
  default = "ingress-nginx"
}

variable "extra_labels" {
  type    = map(string)
  default = {}
}

variable "enable_cloud_resources" {
  description = "Also create the team's AWS resources and bind them to the namespace."
  type        = bool
  default     = true
}

variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "aws_local" {
  description = "Point the AWS provider at LocalStack."
  type        = bool
  default     = false
}

variable "aws_endpoint" {
  description = "LocalStack endpoint, used only when aws_local is true."
  type        = string
  default     = null
}

variable "oidc_provider_arn" {
  description = "ARN of the cluster's IAM OIDC provider (real AWS). Empty keeps the module's local placeholder."
  type        = string
  default     = null
}

variable "oidc_issuer" {
  description = "Issuer of the cluster's OIDC provider without https:// (real AWS)."
  type        = string
  default     = null
}

variable "permissions_boundary_arn" {
  description = "IAM permissions boundary for the application role (real AWS). Null means none."
  type        = string
  default     = null
}
