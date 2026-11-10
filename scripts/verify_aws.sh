#!/usr/bin/env bash
# Check that the team's AWS resources exist (LocalStack locally, real AWS in aws mode) and are configured to standard.
set -uo pipefail
cd "$(dirname "$0")/.."
N=${1:?environment name}
A=scripts/awscli.sh
fail=0
check() { if eval "$2" >/dev/null 2>&1; then echo "  ok   $1"; else echo "  FAIL $1"; fail=1; fi; }
check "S3 bucket exists"                  "$A s3api head-bucket --bucket $N-data"
check "bucket public access fully blocked" "[ \"\$($A s3api get-public-access-block --bucket $N-data --query 'PublicAccessBlockConfiguration.[BlockPublicAcls,BlockPublicPolicy,IgnorePublicAcls,RestrictPublicBuckets]' --output text)\" = 'True	True	True	True' ]"
check "bucket versioning enabled"         "[ \"\$($A s3api get-bucket-versioning --bucket $N-data --query Status --output text)\" = Enabled ]"
check "bucket encryption configured"      "$A s3api get-bucket-encryption --bucket $N-data"
check "SQS queue exists"                  "$A sqs get-queue-url --queue-name $N-events"
check "secret exists"                     "$A secretsmanager describe-secret --secret-id $N/app"
check "log group with retention"          "$A logs describe-log-groups --log-group-name-prefix /curve-metrics/$N --query 'logGroups[0].retentionInDays' --output text | grep -q 30"
check "IAM role exists"                   "$A iam get-role --role-name $N-app"
check "IAM policy attached to role"       "$A iam list-attached-role-policies --role-name $N-app --query 'AttachedPolicies[0].PolicyName' --output text | grep -q $N-app"
check "service account carries role ARN"  "kubectl -n $N get sa app -o jsonpath='{.metadata.annotations.eks\\.amazonaws\\.com/role-arn}' | grep -q $N-app"
check "config map carries resource names" "kubectl -n $N get cm cloud-resources -o jsonpath='{.data.S3_BUCKET}' | grep -q $N-data"
exit $fail
