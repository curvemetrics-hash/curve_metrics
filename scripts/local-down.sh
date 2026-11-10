#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
kind delete cluster --name curve-metrics-local --kubeconfig .local/kubeconfig 2>/dev/null || true
docker rm -f curve-localstack >/dev/null 2>&1 || true
rm -rf .local
echo "local environment removed"
