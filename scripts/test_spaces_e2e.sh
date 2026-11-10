#!/usr/bin/env bash
# End-to-end test of Compliance-Ready Spaces against the local kind cluster and LocalStack.
# Creates two spaces through the API, checks all controls pass, breaks controls one by one,
# checks each is detected, re-applies, and checks it returns to compliant. Cleans up at the end.
# Requires: make up (cluster and LocalStack running).
set -uo pipefail
cd "$(dirname "$0")/.."
export KUBECONFIG="$PWD/.local/kubeconfig"
PORT=${PORT:-8089}; API=http://127.0.0.1:$PORT
SUF=$(date +%s | tail -c 6)
A="acme-$SUF"; B="globex-$SUF"; BAD="evil-$SUF"
AWS=scripts/awslocal.sh
fails=0; pass=0
ok()   { echo "  ok   $1"; pass=$((pass+1)); }
bad()  { echo "  FAIL $1"; fails=$((fails+1)); }
expect() { if [ "$2" = "$3" ]; then ok "$1"; else bad "$1 (got '$2', want '$3')"; fi; }
post() { curl -s -X POST "$API$1" ${2:+-d "$2"}; }
status() { curl -s "$API/spaces/$1" | jq -r .status; }
wait_status() { # name wanted timeout
  for _ in $(seq 1 $(( $3 / 3 ))); do s=$(status "$1"); [ "$s" = "$2" ] && return 0; case $s in rejected|failed) [ "$2" != "$s" ] && return 1;; esac; sleep 3; done; return 1; }
failing() { post "/spaces/$1/scan?wait=180" | jq -r '[.controls[]|select(.passed|not)|.id]|sort|join(",")'; }
summary() { post "/spaces/$1/scan?wait=180" | jq -r '"\(.passed)/\(.total)"'; }

rm -rf .local/spaces
export SQLITE_PATH="$PWD/.local/e2e.db"; rm -f "$SQLITE_PATH"*   # state lives in a database now; use a scratch one
PORT=$PORT python3 -m spaces.server & SRV=$!
cleanup() {
  kill $SRV 2>/dev/null
  echo "== cleanup"
  for n in $A $B; do
    BP=blueprints/standard_team_env
    tofu -chdir=$BP init -input=false -reconfigure -backend-config="$PWD/local/backend.hcl" -backend-config="key=$n.tfstate" >/dev/null 2>&1
    tofu -chdir=$BP destroy -auto-approve -input=false -var "kubeconfig_path=$KUBECONFIG" \
      -var-file="$PWD/.local/spaces/requests/$n.tfvars" -var-file="$PWD/local/local.tfvars" >/dev/null 2>&1 && echo "  destroyed $n" || echo "  destroy of $n failed (check manually)"
  done
}
trap cleanup EXIT
for _ in $(seq 1 20); do curl -s "$API/spaces" >/dev/null && break; sleep 0.5; done

echo "== 1 request validation"
expect "invalid size rejected with 400" "$(curl -s -o /dev/null -w '%{http_code}' -X POST $API/spaces -d '{"name":"x1","team":"t","environment":"dev","size":"huge","admin_groups":["g"]}')" 400
expect "malformed JSON rejected with 400" "$(curl -s -o /dev/null -w '%{http_code}' -X POST $API/spaces -d 'not json')" 400

echo "== 2 create two spaces through the API"
post /spaces "{\"name\":\"$A\",\"team\":\"acme\",\"environment\":\"dev\",\"size\":\"small\",\"admin_groups\":[\"acme-admins\"]}" >/dev/null
wait_status $A ready 400 && ok "space A reached ready" || bad "space A not ready"
post /spaces "{\"name\":\"$B\",\"team\":\"globex\",\"environment\":\"prod\",\"size\":\"large\",\"admin_groups\":[\"globex-admins\"]}" >/dev/null
wait_status $B ready 400 && ok "space B reached ready" || bad "space B not ready"
expect "duplicate name gives 409" "$(curl -s -o /dev/null -w '%{http_code}' -X POST $API/spaces -d "{\"name\":\"$A\",\"team\":\"acme\",\"environment\":\"dev\",\"size\":\"small\",\"admin_groups\":[\"g\"]}")" 409
echo "  seconds to ready: A=$(curl -s $API/spaces/$A | jq .seconds_to_ready) B=$(curl -s $API/spaces/$B | jq .seconds_to_ready)"
echo "  seconds to compliant: A=$(curl -s $API/spaces/$A | jq .seconds_to_compliant) B=$(curl -s $API/spaces/$B | jq .seconds_to_compliant)"

echo "== 3 new spaces are fully compliant"
expect "A controls" "$(summary $A)" "14/14"
expect "B controls" "$(summary $B)" "14/14"

echo "== 4 unsafe request is rejected by the pipeline"
post /spaces "{\"name\":\"$BAD\",\"team\":\"evil\",\"environment\":\"dev\",\"size\":\"small\",\"admin_groups\":[\"system:authenticated\"]}" >/dev/null
wait_status $BAD rejected 300 && ok "wildcard admin request rejected" || bad "wildcard admin request not rejected (status $(status $BAD))"
kubectl get ns $BAD >/dev/null 2>&1 && bad "rejected request still created a namespace" || ok "no namespace created for rejected request"

echo "== 5 break a managed control, detect, re-apply"
break_and_fix() { # label expected-id break-cmd
  eval "$3" >/dev/null 2>&1
  expect "$1: detected" "$(failing $A)" "$2"
  expect "$1: other space unaffected" "$(summary $B)" "14/14"
  post /spaces/$A/fix >/dev/null; wait_status $A ready 300 || bad "$1: re-apply did not finish"
  expect "$1: compliant after re-apply" "$(summary $A)" "14/14"
}
break_and_fix "delete default-deny policy" NET-1 "kubectl -n $A delete networkpolicy default-deny-ingress"
break_and_fix "make bucket public" STO-1 "$AWS s3api delete-public-access-block --bucket $A-data"
break_and_fix "change quota" RES-1 "kubectl -n $A patch resourcequota standard-quota --type merge -p '{\"spec\":{\"hard\":{\"pods\":\"999\"}}}'"
break_and_fix "suspend versioning" STO-2 "$AWS s3api put-bucket-versioning --bucket $A-data --versioning-configuration Status=Suspended"

echo "== 6 object added by hand (not managed by the blueprint)"
kubectl -n $A create rolebinding sneaky --clusterrole=admin --group=system:authenticated >/dev/null 2>&1
expect "wildcard binding detected" "$(failing $A)" "ACC-1"
post /spaces/$A/fix >/dev/null; wait_status $A ready 300
expect "re-apply does NOT remove an unmanaged binding (known limit)" "$(failing $A)" "ACC-1"
kubectl -n $A delete rolebinding sneaky >/dev/null 2>&1
expect "compliant after manual removal" "$(summary $A)" "14/14"

echo "== 7 deleted space is reported, not silently passed"
echo "  (checked by unit test test_empty_snapshot_fails_not_crashes)"

echo
echo "passed: $pass  failed: $fails"
[ $fails -eq 0 ]
