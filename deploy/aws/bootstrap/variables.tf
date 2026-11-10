variable "region" {
  description = "AWS region for everything."
  type        = string
}

variable "prefix" {
  description = "Name prefix for state storage and roles."
  type        = string
  default     = "curve-platform"
}

variable "cluster_name" {
  description = "EKS cluster the roles may describe (to build a kubeconfig)."
  type        = string
}
