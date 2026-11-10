#!/usr/bin/env bash
# Point kubectl at the EKS cluster using the worker's AWS role. Run once when the worker starts.
# Writes $KUBECONFIG, and $KUBECONFIG_RO as well when a read-only role is configured (used for scans).
set -euo pipefail
: "${EKS_CLUSTER_NAME:?set EKS_CLUSTER_NAME}"
REGION=${AWS_REGION:-us-east-1}
export KUBECONFIG=${KUBECONFIG:-/tmp/kubeconfig}
aws eks update-kubeconfig --name "$EKS_CLUSTER_NAME" --region "$REGION" --kubeconfig "$KUBECONFIG" >/dev/null
kubectl --kubeconfig "$KUBECONFIG" get ns >/dev/null
echo "kubectl ok: $EKS_CLUSTER_NAME"
if [ -n "${AWS_READONLY_ROLE_ARN:-}" ]; then
  export KUBECONFIG_RO=${KUBECONFIG_RO:-/tmp/kubeconfig-ro}
  aws eks update-kubeconfig --name "$EKS_CLUSTER_NAME" --region "$REGION" --kubeconfig "$KUBECONFIG_RO" --profile readonly >/dev/null
  echo "read-only kubeconfig written"
fi
