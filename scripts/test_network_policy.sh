#!/usr/bin/env bash
# Proves the network policies are enforced, not just present.
#   scripts/test_network_policy.sh team-alpha-dev
# A web server runs inside the environment. Clients try to reach it from:
#   1. the same namespace            -> must be reachable
#   2. an unrelated namespace        -> must be BLOCKED by default-deny
#   3. an allow-listed namespace     -> must be reachable (only if the request allow-lists kube-system)
#   control: an unrelated namespace reaching a server with NO policies -> must be reachable,
#            which shows case 2 was blocked by the policy and not by a network fault.
set -uo pipefail
cd "$(dirname "$0")/.."
NS=${1:?environment namespace}
export KUBECONFIG=${KUBECONFIG:-$PWD/.local/kubeconfig}
IMG=busybox:1.36
OUT=np-outsider
CTL=np-control
fail=0

cleanup() {
  kubectl -n "$NS" delete pod,svc np-server --ignore-not-found >/dev/null 2>&1
  kubectl delete ns "$OUT" "$CTL" --ignore-not-found --timeout=120s >/dev/null 2>&1
}
trap cleanup EXIT
cleanup; sleep 2

serve() { # namespace
  kubectl -n "$1" run np-server --image=$IMG --image-pull-policy=IfNotPresent --port 8080 \
    -- sh -c 'mkdir -p /www && echo ok > /www/index.html && httpd -f -p 8080 -h /www' >/dev/null
  kubectl -n "$1" expose pod np-server --port 8080 >/dev/null
  kubectl -n "$1" wait --for=condition=Ready pod/np-server --timeout=90s >/dev/null
}
reach() { # from-namespace target-url
  kubectl -n "$1" run "np-$RANDOM" --rm -i --restart=Never --image=$IMG --image-pull-policy=IfNotPresent \
    -- wget -q -T 4 -O- "$2" >/dev/null 2>&1
}
expect() { # label want(reachable|blocked) from url
  reach "$3" "$4"; rc=$?
  if [ "$2" = reachable ] && [ $rc -eq 0 ]; then echo "  ok   $1: reachable"
  elif [ "$2" = blocked ] && [ $rc -ne 0 ]; then echo "  ok   $1: blocked"
  else echo "  FAIL $1: expected $2"; fail=1; fi
}

kubectl create ns "$OUT" >/dev/null; kubectl create ns "$CTL" >/dev/null
serve "$NS"; serve "$CTL"

expect "same namespace -> $NS"                     reachable "$NS"       "http://np-server:8080"
expect "unrelated namespace -> $NS (default-deny)" blocked   "$OUT"      "http://np-server.$NS:8080"
if kubectl -n "$NS" get networkpolicy allow-listed-namespaces >/dev/null 2>&1; then
  expect "allow-listed kube-system -> $NS"         reachable "kube-system" "http://np-server.$NS:8080"
fi
expect "control: unrelated -> namespace with no policy" reachable "$OUT" "http://np-server.$CTL:8080"
exit $fail
