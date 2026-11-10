#!/usr/bin/env bash
# Check that the live namespace matches the standard.
set -euo pipefail
NS=${1:?namespace}
export KUBECONFIG=${KUBECONFIG:-$PWD/.local/kubeconfig}
fail=0
check() { if eval "$2" >/dev/null 2>&1; then echo "  ok   $1"; else echo "  FAIL $1"; fail=1; fi; }
check "namespace exists"            "kubectl get ns $NS"
check "team label set"              "kubectl get ns $NS -o jsonpath='{.metadata.labels.curve-metrics/team}' | grep -q ."
check "resource quota present"      "kubectl -n $NS get resourcequota standard-quota"
check "limit range present"         "kubectl -n $NS get limitrange standard-limits"
check "default-deny policy present" "kubectl -n $NS get networkpolicy default-deny-ingress"
check "same-namespace policy"       "kubectl -n $NS get networkpolicy allow-same-namespace"
check "storage limit in quota"       "kubectl -n $NS get resourcequota standard-quota -o jsonpath='{.spec.hard.requests\\.storage}' | grep -q Gi"
check "ingress limit in quota"       "kubectl -n $NS get resourcequota standard-quota -o jsonpath='{.spec.hard.count/ingresses\\.networking\\.k8s\\.io}' | grep -q ."
check "ingress controller policy"    "kubectl -n $NS get networkpolicy allow-ingress-controller"
check "no cluster-admin binding"    "! kubectl -n $NS get rolebinding -o jsonpath='{.items[*].roleRef.name}' | grep -q cluster-admin"
exit $fail
