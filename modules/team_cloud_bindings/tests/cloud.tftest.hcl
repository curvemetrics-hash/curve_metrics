mock_provider "aws" {
  mock_resource "aws_iam_policy" {
    defaults = { arn = "arn:aws:iam::000000000000:policy/mock" }
  }
  mock_resource "aws_iam_role" {
    defaults = { arn = "arn:aws:iam::000000000000:role/mock" }
  }
  mock_resource "aws_s3_bucket" {
    defaults = { arn = "arn:aws:s3:::mock-bucket" }
  }
  mock_resource "aws_sqs_queue" {
    defaults = {
      arn = "arn:aws:sqs:us-east-1:000000000000:mock"
      url = "http://localhost:4566/000000000000/mock"
    }
  }
  mock_resource "aws_secretsmanager_secret" {
    defaults = { arn = "arn:aws:secretsmanager:us-east-1:000000000000:secret:mock" }
  }
  mock_resource "aws_cloudwatch_log_group" {
    defaults = { arn = "arn:aws:logs:us-east-1:000000000000:log-group:mock" }
  }
}
mock_provider "kubernetes" {}

variables {
  name        = "team-alpha-dev"
  namespace   = "team-alpha-dev"
  team        = "alpha"
  environment = "dev"
}

run "bucket_is_private_encrypted_and_versioned" {
  command = plan

  assert {
    condition     = aws_s3_bucket.data.bucket == "team-alpha-dev-data"
    error_message = "bucket name wrong"
  }
  assert {
    condition     = aws_s3_bucket_public_access_block.data.block_public_acls && aws_s3_bucket_public_access_block.data.block_public_policy && aws_s3_bucket_public_access_block.data.ignore_public_acls && aws_s3_bucket_public_access_block.data.restrict_public_buckets
    error_message = "public access must be fully blocked"
  }
  assert {
    condition     = aws_s3_bucket_versioning.data.versioning_configuration[0].status == "Enabled"
    error_message = "versioning must be enabled"
  }
}

run "queue_secret_and_logs_are_named_from_the_environment" {
  command = plan

  assert {
    condition     = aws_sqs_queue.events.name == "team-alpha-dev-events" && aws_sqs_queue.events.sqs_managed_sse_enabled
    error_message = "queue name or encryption wrong"
  }
  assert {
    condition     = aws_secretsmanager_secret.app.name == "team-alpha-dev/app"
    error_message = "secret name wrong"
  }
  assert {
    condition     = aws_cloudwatch_log_group.app.name == "/curve-metrics/team-alpha-dev" && aws_cloudwatch_log_group.app.retention_in_days == 30
    error_message = "log group wrong"
  }
}

run "role_is_bound_to_the_namespace_service_account_only" {
  command = plan

  assert {
    condition     = strcontains(aws_iam_role.app.assume_role_policy, "system:serviceaccount:team-alpha-dev:app")
    error_message = "trust policy must name this namespace's service account"
  }
}

run "policy_has_no_wildcard_actions" {
  command = plan

  assert {
    condition     = !strcontains(aws_iam_policy.app.policy, "\"*\"")
    error_message = "policy must not contain wildcard actions or resources"
  }
}

run "kubernetes_side_exposes_the_names_to_the_workload" {
  command = plan

  assert {
    condition     = kubernetes_service_account_v1.app.metadata[0].name == "app" && kubernetes_service_account_v1.app.metadata[0].namespace == "team-alpha-dev"
    error_message = "service account wrong"
  }
  assert {
    condition     = kubernetes_config_map_v1.cloud.data["S3_BUCKET"] == "team-alpha-dev-data"
    error_message = "config map must carry the bucket name"
  }
}

run "boundary_is_attached_when_given" {
  command = plan

  variables {
    permissions_boundary_arn = "arn:aws:iam::123456789012:policy/platform-app-boundary"
  }

  assert {
    condition     = aws_iam_role.app.permissions_boundary == "arn:aws:iam::123456789012:policy/platform-app-boundary"
    error_message = "the application role must carry the permissions boundary"
  }
}
