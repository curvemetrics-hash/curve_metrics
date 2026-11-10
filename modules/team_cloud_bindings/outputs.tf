output "bucket" {
  value = aws_s3_bucket.data.bucket
}

output "queue_url" {
  value = aws_sqs_queue.events.url
}

output "secret_name" {
  value = aws_secretsmanager_secret.app.name
}

output "log_group" {
  value = aws_cloudwatch_log_group.app.name
}

output "role_arn" {
  value = aws_iam_role.app.arn
}
