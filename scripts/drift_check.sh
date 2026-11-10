#!/usr/bin/env bash
# Scheduled drift check: plan against live state. Exit 0 = no drift, 2 = drift.
#   scripts/drift_check.sh local/fixtures/team-alpha-dev.tfvars
set -uo pipefail
cd "$(dirname "$0")/.."
REQUEST=${1:?usage: drift_check.sh <request.tfvars>}
BP=blueprints/standard_team_env
export KUBECONFIG=${KUBECONFIG:-$PWD/.local/kubeconfig}
NAME=$(sed -n 's/^name *= *"\(.*\)"/\1/p' "$REQUEST")
tofu -chdir=$BP init -input=false -reconfigure \
  -backend-config="$PWD/local/backend.hcl" -backend-config="key=${NAME}.tfstate" >/dev/null
tofu -chdir=$BP plan -input=false -detailed-exitcode -var "kubeconfig_path=$KUBECONFIG" \
  -var-file="$PWD/$REQUEST" -var-file="$PWD/local/local.tfvars" >/dev/null 2>&1
rc=$?
case $rc in
  0) echo "no drift: $NAME matches the blueprint" ;;
  2) echo "DRIFT DETECTED: $NAME differs from the blueprint" ;;
  *) echo "drift check failed to run (exit $rc)" ;;
esac
exit $rc
