variable "name" {
  description = "Environment name; prefix for every cloud resource."
  type        = string
}

variable "namespace" {
  description = "Kubernetes namespace that will use the cloud resources."
  type        = string
}

variable "team" {
  type = string
}

variable "environment" {
  type = string
}

variable "oidc_provider_arn" {
  description = "ARN of the cluster's OIDC identity provider (IAM roles for service accounts)."
  type        = string
  default     = "arn:aws:iam::000000000000:oidc-provider/oidc.eks.local/id/EXAMPLE"
}

variable "oidc_issuer" {
  description = "OIDC issuer host and path without https://."
  type        = string
  default     = "oidc.eks.local/id/EXAMPLE"
}

variable "log_retention_days" {
  type    = number
  default = 30
}

variable "permissions_boundary_arn" {
  description = "IAM permissions boundary attached to the application role. Set it in real AWS so the pipeline can never create a role more powerful than the boundary allows."
  type        = string
  default     = null
}
