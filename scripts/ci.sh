#!/usr/bin/env bash
# Local run of the pipeline stages for one request file.
#   scripts/ci.sh local/fixtures/team-alpha-dev.tfvars
# Stages: format, validate, unit tests, init (remote state), plan, policy gate,
# approval, apply, verify (cluster and AWS), record metric.
# LOCAL=1 (default) points the AWS provider at LocalStack; LOCAL=0 uses real AWS and needs
# TF_STATE_BUCKET, TF_LOCK_TABLE, OIDC_PROVIDER_ARN, OIDC_ISSUER (see deploy/README.md).
set -euo pipefail
cd "$(dirname "$0")/.."

REQUEST=${1:?usage: ci.sh <request.tfvars>}
BP=blueprints/standard_team_env
export KUBECONFIG="${KUBECONFIG:-$PWD/.local/kubeconfig}"
NAME=$(sed -n 's/^name *= *"\(.*\)"/\1/p' "$REQUEST")
REQUESTED=$(date +%s)
LOCAL_VARS=(); BACKEND_ARGS=()
if [ "${LOCAL:-1}" = "1" ]; then
  LOCAL_VARS=(-var-file="$PWD/local/local.tfvars"); BACKEND_ARGS=(-backend-config="$PWD/local/backend.hcl")
else
  export PLATFORM_MODE=aws
  : "${TF_STATE_BUCKET:?}" "${TF_LOCK_TABLE:?}" "${OIDC_PROVIDER_ARN:?}" "${OIDC_ISSUER:?}"
  LOCAL_VARS=(-var "aws_region=${AWS_REGION:-us-east-1}" -var "oidc_provider_arn=$OIDC_PROVIDER_ARN" -var "oidc_issuer=$OIDC_ISSUER")
  if [ -n "${PERMISSIONS_BOUNDARY_ARN:-}" ]; then LOCAL_VARS+=(-var "permissions_boundary_arn=$PERMISSIONS_BOUNDARY_ARN"); fi
  BACKEND_ARGS=(-backend-config="bucket=$TF_STATE_BUCKET" -backend-config="dynamodb_table=$TF_LOCK_TABLE"
                -backend-config="region=${AWS_REGION:-us-east-1}" -backend-config="encrypt=true")
fi

echo "== 1 format";   tofu fmt -check -recursive modules blueprints local/bootstrap
echo "== 2 validate"
for m in namespace_baseline team_cloud_bindings; do
  tofu -chdir=modules/$m init -backend=false -input=false >/dev/null
  tofu -chdir=modules/$m validate
done
echo "== 3 unit tests"
for m in namespace_baseline team_cloud_bindings; do tofu -chdir=modules/$m test; done
echo "== 4 init (remote state in LocalStack)"
tofu -chdir=$BP init -input=false -reconfigure \
  "${BACKEND_ARGS[@]}" -backend-config="key=${NAME}.tfstate" >/dev/null
tofu -chdir=$BP validate
echo "== 5 plan"
tofu -chdir=$BP plan -input=false -var "kubeconfig_path=$KUBECONFIG" \
  -var-file="$PWD/$REQUEST" "${LOCAL_VARS[@]}" -out=plan.bin >/dev/null
tofu -chdir=$BP show -json plan.bin > $BP/plan.json
echo "== 6 policy gate"
python3 scripts/policy_check.py $BP/plan.json
echo "== 7 approval"
if [ "${AUTO_APPROVE:-}" = "1" ]; then echo "auto-approved (local test run)"; else
  read -r -p "approve apply? [y/N] " a; [ "$a" = "y" ] || { echo "not approved"; exit 1; }; fi
echo "== 8 apply"
tofu -chdir=$BP apply -input=false plan.bin
READY=$(date +%s)
echo "== 9 verify cluster"
scripts/verify.sh "$NAME"
echo "== 9b verify AWS resources"
scripts/verify_aws.sh "$NAME"
echo "== 10 metric"
python3 scripts/record_metric.py "$NAME" "$REQUESTED" "$READY" 0 success
