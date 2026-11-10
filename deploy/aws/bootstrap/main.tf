# One-time setup in the AWS account, run by a human administrator (not by the pipeline):
#   - remote state bucket and lock table for the blueprint
#   - a permissions boundary that caps every role the pipeline creates for a team
#   - the pipeline role (creates environments) and a read-only role (scans)
#   - an IAM user for Render that can do nothing except assume those two roles
# No access key is created here, so no secret ends up in Terraform state. Create it once with
#   aws iam create-access-key --user-name <render_user>   and paste it into Render.
data "aws_caller_identity" "me" {}

locals {
  account = data.aws_caller_identity.me.account_id
  p       = var.prefix
  arn     = "arn:aws"
}

# ---- state ---------------------------------------------------------------------------------
resource "aws_s3_bucket" "state" {
  bucket = "${local.p}-tfstate-${local.account}"
}

resource "aws_s3_bucket_versioning" "state" {
  bucket = aws_s3_bucket.state.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "state" {
  bucket = aws_s3_bucket.state.id
  rule {
    apply_server_side_encryption_by_default { sse_algorithm = "AES256" }
  }
}

resource "aws_s3_bucket_public_access_block" "state" {
  bucket                  = aws_s3_bucket.state.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_policy" "state_tls_only" {
  bucket = aws_s3_bucket.state.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "DenyPlainHttp"
      Effect    = "Deny"
      Principal = "*"
      Action    = "s3:*"
      Resource  = [aws_s3_bucket.state.arn, "${aws_s3_bucket.state.arn}/*"]
      Condition = { Bool = { "aws:SecureTransport" = "false" } }
    }]
  })
}

resource "aws_dynamodb_table" "lock" {
  name         = "${local.p}-tflock"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "LockID"

  attribute {
    name = "LockID"
    type = "S"
  }

  point_in_time_recovery { enabled = true }
  server_side_encryption { enabled = true }
}

# ---- boundary: the most any team application role can ever do ----------------------------------
resource "aws_iam_policy" "app_boundary" {
  name = "${local.p}-app-boundary"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      { Effect = "Allow", Action = ["s3:GetObject", "s3:PutObject", "s3:ListBucket"], Resource = ["${local.arn}:s3:::*-data", "${local.arn}:s3:::*-data/*"] },
      { Effect = "Allow", Action = ["sqs:SendMessage", "sqs:ReceiveMessage", "sqs:DeleteMessage"], Resource = "${local.arn}:sqs:*:${local.account}:*-events" },
      { Effect = "Allow", Action = ["secretsmanager:GetSecretValue"], Resource = "${local.arn}:secretsmanager:*:${local.account}:secret:*/app-*" },
      { Effect = "Allow", Action = ["logs:CreateLogStream", "logs:PutLogEvents"], Resource = "${local.arn}:logs:*:${local.account}:log-group:/curve-metrics/*:*" },
    ]
  })
}

# ---- the user Render holds ------------------------------------------------------------------------
resource "aws_iam_user" "render" {
  name = "${local.p}-render"
}

resource "aws_iam_user_policy" "render_assume_only" {
  name = "assume-platform-roles-only"
  user = aws_iam_user.render.name
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "sts:AssumeRole"
      Resource = [aws_iam_role.pipeline.arn, aws_iam_role.readonly.arn]
    }]
  })
}

data "aws_iam_policy_document" "trust_render" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "AWS"
      identifiers = [aws_iam_user.render.arn]
    }
  }
}

# ---- pipeline role: creates and changes environments ------------------------------------------------
resource "aws_iam_role" "pipeline" {
  name                 = "${local.p}-pipeline"
  assume_role_policy   = data.aws_iam_policy_document.trust_render.json
  max_session_duration = 3600
}

resource "aws_iam_role_policy" "pipeline" {
  name = "environments"
  role = aws_iam_role.pipeline.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      { Sid = "StateObjects", Effect = "Allow", Action = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"], Resource = "${aws_s3_bucket.state.arn}/*" },
      { Sid = "StateBucket", Effect = "Allow", Action = ["s3:ListBucket", "s3:GetBucketVersioning"], Resource = aws_s3_bucket.state.arn },
      { Sid = "StateLock", Effect = "Allow", Action = ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:DeleteItem", "dynamodb:DescribeTable"], Resource = aws_dynamodb_table.lock.arn },
      {
        Sid      = "TeamBuckets", Effect = "Allow",
        Action   = ["s3:CreateBucket", "s3:DeleteBucket", "s3:Get*", "s3:List*", "s3:PutBucket*", "s3:PutEncryptionConfiguration"],
        Resource = "${local.arn}:s3:::*-data"
      },
      {
        Sid      = "TeamQueues", Effect = "Allow",
        Action   = ["sqs:CreateQueue", "sqs:DeleteQueue", "sqs:Get*", "sqs:List*", "sqs:SetQueueAttributes", "sqs:TagQueue", "sqs:UntagQueue"],
        Resource = "${local.arn}:sqs:*:${local.account}:*-events"
      },
      { Sid = "ListQueues", Effect = "Allow", Action = "sqs:ListQueues", Resource = "*" },
      {
        Sid      = "TeamSecrets", Effect = "Allow",
        Action   = ["secretsmanager:CreateSecret", "secretsmanager:DeleteSecret", "secretsmanager:DescribeSecret", "secretsmanager:GetResourcePolicy", "secretsmanager:PutResourcePolicy", "secretsmanager:TagResource", "secretsmanager:UntagResource", "secretsmanager:UpdateSecret", "secretsmanager:RestoreSecret"],
        Resource = "${local.arn}:secretsmanager:*:${local.account}:secret:*/app-*"
      },
      {
        Sid      = "TeamLogs", Effect = "Allow",
        Action   = ["logs:CreateLogGroup", "logs:DeleteLogGroup", "logs:PutRetentionPolicy", "logs:DeleteRetentionPolicy", "logs:TagResource", "logs:UntagResource", "logs:ListTagsForResource", "logs:ListTagsLogGroup"],
        Resource = "${local.arn}:logs:*:${local.account}:log-group:/curve-metrics/*"
      },
      { Sid = "DescribeLogs", Effect = "Allow", Action = "logs:DescribeLogGroups", Resource = "*" },
      {
        Sid       = "TeamRolesNeedBoundary", Effect = "Allow", Action = "iam:CreateRole", Resource = "${local.arn}:iam::${local.account}:role/*-app",
        Condition = { StringEquals = { "iam:PermissionsBoundary" = aws_iam_policy.app_boundary.arn } }
      },
      {
        Sid      = "TeamRoles", Effect = "Allow",
        Action   = ["iam:DeleteRole", "iam:GetRole", "iam:UpdateAssumeRolePolicy", "iam:TagRole", "iam:UntagRole", "iam:ListRoleTags", "iam:ListAttachedRolePolicies", "iam:ListRolePolicies", "iam:ListInstanceProfilesForRole"],
        Resource = "${local.arn}:iam::${local.account}:role/*-app"
      },
      {
        Sid       = "AttachOnlyTeamPolicies", Effect = "Allow", Action = ["iam:AttachRolePolicy", "iam:DetachRolePolicy"], Resource = "${local.arn}:iam::${local.account}:role/*-app",
        Condition = { ArnLike = { "iam:PolicyARN" = "${local.arn}:iam::${local.account}:policy/*-app" } }
      },
      {
        Sid      = "TeamPolicies", Effect = "Allow",
        Action   = ["iam:CreatePolicy", "iam:DeletePolicy", "iam:GetPolicy", "iam:GetPolicyVersion", "iam:ListPolicyVersions", "iam:CreatePolicyVersion", "iam:DeletePolicyVersion", "iam:TagPolicy", "iam:UntagPolicy"],
        Resource = "${local.arn}:iam::${local.account}:policy/*-app"
      },
      { Sid = "DescribeCluster", Effect = "Allow", Action = "eks:DescribeCluster", Resource = "${local.arn}:eks:${var.region}:${local.account}:cluster/${var.cluster_name}" },
      { Sid = "NeverRemoveTheBoundary", Effect = "Deny", Action = "iam:DeleteRolePermissionsBoundary", Resource = "*" },
      {
        Sid       = "NeverSwapTheBoundary", Effect = "Deny", Action = "iam:PutRolePermissionsBoundary", Resource = "*",
        Condition = { StringNotEquals = { "iam:PermissionsBoundary" = aws_iam_policy.app_boundary.arn } }
      },
    ]
  })
}

# ---- read-only role: scans -------------------------------------------------------------------------
resource "aws_iam_role" "readonly" {
  name                 = "${local.p}-readonly"
  assume_role_policy   = data.aws_iam_policy_document.trust_render.json
  max_session_duration = 3600
}

resource "aws_iam_role_policy" "readonly" {
  name = "scan"
  role = aws_iam_role.readonly.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["s3:ListBucket", "s3:GetBucketPublicAccessBlock", "s3:GetBucketVersioning", "s3:GetEncryptionConfiguration", "s3:GetBucketPolicy", "s3:GetBucketTagging"]
        Resource = "${local.arn}:s3:::*-data"
      },
      { Effect = "Allow", Action = ["sqs:GetQueueUrl", "sqs:GetQueueAttributes", "sqs:ListQueueTags"], Resource = "${local.arn}:sqs:*:${local.account}:*-events" },
      { Effect = "Allow", Action = ["secretsmanager:DescribeSecret"], Resource = "${local.arn}:secretsmanager:*:${local.account}:secret:*/app-*" },
      { Effect = "Allow", Action = ["logs:DescribeLogGroups"], Resource = "*" },
      {
        Effect   = "Allow"
        Action   = ["iam:GetRole", "iam:ListAttachedRolePolicies", "iam:ListRolePolicies"]
        Resource = "${local.arn}:iam::${local.account}:role/*-app"
      },
      { Effect = "Allow", Action = ["iam:GetPolicy", "iam:GetPolicyVersion"], Resource = "${local.arn}:iam::${local.account}:policy/*-app" },
      { Effect = "Allow", Action = "eks:DescribeCluster", Resource = "${local.arn}:eks:${var.region}:${local.account}:cluster/${var.cluster_name}" },
    ]
  })
}
