terraform {
  required_version = ">= 1.6.0"

  required_providers {
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.30"
    }
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.60"
    }
  }

  # Remote state with locking. Bucket, lock table, endpoint and key are
  # supplied at init time (see local/backend.hcl and scripts/ci.sh).
  backend "s3" {}
}
