locals {
  tags = {
    "managed-by" = "platform-blueprint"
    "team"       = var.team
    "env"        = var.environment
  }
  service_account = "app"
}

resource "aws_s3_bucket" "data" {
  bucket = "${var.name}-data"
  tags   = local.tags
}

resource "aws_s3_bucket_public_access_block" "data" {
  bucket                  = aws_s3_bucket.data.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "data" {
  bucket = aws_s3_bucket.data.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "data" {
  bucket = aws_s3_bucket.data.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_sqs_queue" "events" {
  name                    = "${var.name}-events"
  sqs_managed_sse_enabled = true
  tags                    = local.tags
}

resource "aws_secretsmanager_secret" "app" {
  name = "${var.name}/app"
  tags = local.tags
}

resource "aws_cloudwatch_log_group" "app" {
  name              = "/curve-metrics/${var.name}"
  retention_in_days = var.log_retention_days
  tags              = local.tags
}

resource "aws_iam_role" "app" {
  name                 = "${var.name}-app"
  tags                 = local.tags
  permissions_boundary = var.permissions_boundary_arn

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Federated = var.oidc_provider_arn }
      Action    = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringEquals = {
          "${var.oidc_issuer}:sub" = "system:serviceaccount:${var.namespace}:${local.service_account}"
        }
      }
    }]
  })
}

resource "aws_iam_policy" "app" {
  name = "${var.name}-app"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject", "s3:ListBucket"]
        Resource = [aws_s3_bucket.data.arn, "${aws_s3_bucket.data.arn}/*"]
      },
      {
        Effect   = "Allow"
        Action   = ["sqs:SendMessage", "sqs:ReceiveMessage", "sqs:DeleteMessage"]
        Resource = [aws_sqs_queue.events.arn]
      },
      {
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = [aws_secretsmanager_secret.app.arn]
      },
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = ["${aws_cloudwatch_log_group.app.arn}:*"]
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "app" {
  role       = aws_iam_role.app.name
  policy_arn = aws_iam_policy.app.arn
}

# Kubernetes side: the identity the workload runs as, and the names it needs.
resource "kubernetes_service_account_v1" "app" {
  metadata {
    name      = local.service_account
    namespace = var.namespace
    annotations = {
      "eks.amazonaws.com/role-arn" = aws_iam_role.app.arn
    }
  }
}

resource "kubernetes_config_map_v1" "cloud" {
  metadata {
    name      = "cloud-resources"
    namespace = var.namespace
  }

  data = {
    S3_BUCKET     = aws_s3_bucket.data.bucket
    SQS_QUEUE_URL = aws_sqs_queue.events.url
    SECRET_ID     = aws_secretsmanager_secret.app.name
    LOG_GROUP     = aws_cloudwatch_log_group.app.name
    AWS_ROLE_ARN  = aws_iam_role.app.arn
  }
}
