#!/usr/bin/env bash
# One run of every check against the local stack (kind + LocalStack). Needs: make up.
# Prints one line per step with its real exit code, then a summary. Exit 1 if any step failed.
set -uo pipefail
cd "$(dirname "$0")/.."
export KUBECONFIG="$PWD/.local/kubeconfig"
results=()
step() { # name, command...
  local name=$1; shift
  echo "=== $name"
  "$@" > ".local/validate-$$.log" 2>&1; local rc=$?
  tail -n 6 ".local/validate-$$.log" | sed 's/^/    /'
  results+=("$rc $name")
}
curl -sf http://localhost:4566/_localstack/health >/dev/null || { echo "LocalStack is not running (make up)"; exit 2; }

step "module unit tests (tofu test, mocked providers)" make test
step "python tests (policy, controls, api, rollout)"   make policy-test
step "pipeline: team-alpha-dev (dev, small)"            make ci-alpha
step "pipeline: team-beta-prod (prod, large)"           make ci-beta
step "pipeline: wildcard-admin request is rejected"     make ci-bad
step "drift check: no drift"                            make drift-alpha
step "demo workload uses S3, SQS, secret, logs"         make demo-alpha
step "network policy is enforced (with control case)"   make netpol-alpha
step "compliance spaces end to end"                     scripts/test_spaces_e2e.sh
step "rollout manager demo (4 environments)"            scripts/rollout_demo.sh 4

echo; echo "=== AWS resources in LocalStack now"
A=scripts/awslocal.sh
echo "S3 buckets:";   $A s3api list-buckets --query 'Buckets[].Name' --output text | tr '\t' '\n' | sed 's/^/  /'
echo "SQS queues:";   $A sqs list-queues --query 'QueueUrls[]' --output text | tr '\t' '\n' | sed 's#.*/#  #'
echo "Secrets:";      $A secretsmanager list-secrets --query 'SecretList[].Name' --output text | tr '\t' '\n' | sed 's/^/  /'
echo "IAM roles:";    $A iam list-roles --query 'Roles[].RoleName' --output text | tr '\t' '\n' | sed 's/^/  /'
echo "Log groups:";   $A logs describe-log-groups --query 'logGroups[].logGroupName' --output text | tr '\t' '\n' | sed 's/^/  /'

echo; echo "=== SUMMARY"
fails=0
for r in "${results[@]}"; do rc=${r%% *}; n=${r#* }; if [ "$rc" = 0 ]; then echo "  PASS  $n"; else echo "  FAIL  $n (exit $rc)"; fails=$((fails+1)); fi; done
echo "failed steps: $fails"
rm -f ".local/validate-$$.log"
[ $fails -eq 0 ]
