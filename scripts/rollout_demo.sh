#!/usr/bin/env bash
# Full rollout demo with assertions. Needs the local stack (make up).
#   scripts/rollout_demo.sh [N]      N environments, default 10
# Shows: provision at v1.0.0, a good release (v1.1.0) rolled out, a bad release (v1.2.0) blocked by
# the preview, and the same bad release stopped at the canary and rolled back when the preview
# is overridden. Cleans up the environments it created.
set -uo pipefail
cd "$(dirname "$0")/.."
export KUBECONFIG="$PWD/.local/kubeconfig"
N=${1:-10}
R="python3 -m rollout"
fails=0
check() { if [ "$2" = "$3" ]; then echo "  ok   $1"; else echo "  FAIL $1 (got '$2', want '$3')"; fails=$((fails+1)); fi; }
last_status() { $R last-run | jq -r .status; }

$R destroy >/dev/null 2>&1   # leftovers from an earlier run (fails harmlessly when there is no registry)
$R demo-registry "$N" || exit 1
$R purge-secrets >/dev/null   # a destroyed secret otherwise blocks reuse of its name (real AWS does this too)
trap '$R destroy >/dev/null 2>&1; $R purge-secrets >/dev/null 2>&1; echo "== cleaned up"' EXIT

echo "== provision $N environments at v1.0.0"
$R provision || exit 1
check "all environments compliant on v1.0.0" "$($R status | grep -c ' ok ')" "$N"

echo "== good release v1.1.0"
$R rollout v1.1.0; rc=$?
check "rollout completes" "$rc $(last_status)" "0 completed"
check "every environment now on v1.1.0" "$($R status | grep -c 'v1.1.0  v1.1.0')" "$N"
first=$($R registry | jq -r '.environments[0].name')
check "change really applied (log retention 90)" "$(scripts/awslocal.sh logs describe-log-groups --log-group-name-prefix /curve-metrics/$first --query 'logGroups[0].retentionInDays' --output text)" "90"

echo "== bad release v1.2.0, preview not overridden"
$R rollout v1.2.0 >/dev/null; rc=$?
check "blocked before anything changes" "$rc $(last_status)" "1 blocked_by_preview"
check "all environments still on v1.1.0" "$($R status | grep -c 'v1.1.0  v1.1.0')" "$N"

echo "== bad release v1.2.0, preview overridden"
$R rollout v1.2.0 --allow-destroy >/dev/null; rc=$?
check "stopped at the canary" "$rc $(last_status)" "1 aborted_at_canary"
check "canary was rolled back" "$($R last-run | jq -r '.records[0].rolled_back')" "true"
check "no environment left on v1.2.0" "$($R status | grep -c 'v1.2.0')" "0"
check "all environments still compliant" "$($R status | grep -c ' ok ')" "$N"

$R report --live >/dev/null && echo "  report written to site/index.html"
echo "failed checks: $fails"
[ $fails -eq 0 ]
