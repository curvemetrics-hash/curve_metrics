variable "name" {
  description = "Namespace name for the team environment."
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9]([-a-z0-9]{0,60}[a-z0-9])?$", var.name))
    error_message = "name must be a valid lowercase DNS label (letters, digits, hyphens; at most 62 characters)."
  }
}

variable "team" {
  description = "Owning team."
  type        = string
}

variable "environment" {
  description = "Environment stage."
  type        = string

  validation {
    condition     = contains(["dev", "test", "prod"], var.environment)
    error_message = "environment must be one of: dev, test, prod."
  }
}

variable "size" {
  description = "Environment size preset."
  type        = string
  default     = "small"

  validation {
    condition     = contains(["small", "medium", "large"], var.size)
    error_message = "size must be one of: small, medium, large."
  }
}

variable "admin_groups" {
  description = "Groups granted the namespace-scoped admin role."
  type        = list(string)
  default     = []

  validation {
    condition     = !contains(var.admin_groups, "system:authenticated") && !contains(var.admin_groups, "system:unauthenticated")
    error_message = "admin_groups must not include system:authenticated or system:unauthenticated."
  }
}

variable "allow_ingress_from_namespaces" {
  description = "Other namespaces allowed to send traffic in."
  type        = list(string)
  default     = []
}

variable "allow_ingress_controller" {
  description = "Allow the cluster's ingress controller to reach workloads in the namespace."
  type        = bool
  default     = true
}

variable "ingress_controller_namespace" {
  description = "Namespace of the ingress controller (for example ingress-nginx, or openshift-ingress on OpenShift)."
  type        = string
  default     = "ingress-nginx"
}

variable "extra_labels" {
  description = "Additional labels."
  type        = map(string)
  default     = {}
}
