output "state_bucket" { value = aws_s3_bucket.state.bucket }
output "lock_table" { value = aws_dynamodb_table.lock.name }
output "permissions_boundary_arn" { value = aws_iam_policy.app_boundary.arn }
output "pipeline_role_arn" { value = aws_iam_role.pipeline.arn }
output "readonly_role_arn" { value = aws_iam_role.readonly.arn }
output "render_user" { value = aws_iam_user.render.name }
