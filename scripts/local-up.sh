#!/usr/bin/env bash
# Start LocalStack (state backend, metrics) and a throwaway kind cluster.
# Uses its own kubeconfig at .local/kubeconfig and never touches ~/.kube/config.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p .local

if ! docker ps --format '{{.Names}}' | grep -q '^curve-localstack$'; then
  docker rm -f curve-localstack >/dev/null 2>&1 || true
  docker run -d --name curve-localstack -p 4566:4566 \
    -e SERVICES=s3,dynamodb,iam,sqs,secretsmanager,logs,sts localstack/localstack:3.8 >/dev/null
fi
echo "waiting for LocalStack..."
for _ in $(seq 1 60); do
  curl -sf http://localhost:4566/_localstack/health >/dev/null && break
  sleep 2
done
curl -sf http://localhost:4566/_localstack/health >/dev/null || { echo "LocalStack did not start"; exit 1; }

tofu -chdir=local/bootstrap init -input=false >/dev/null
tofu -chdir=local/bootstrap apply -auto-approve -input=false >/dev/null
echo "LocalStack backend ready (state bucket, lock table, metrics bucket)"

if ! kind get clusters 2>/dev/null | grep -q '^curve-metrics-local$'; then
  kind create cluster --config local/kind-config.yaml --image kindest/node:v1.31.2 \
    --kubeconfig .local/kubeconfig --wait 120s
fi
# preload the AWS CLI image so the demo workload starts without pulling
kind load docker-image amazon/aws-cli:2.17.0 --name curve-metrics-local >/dev/null 2>&1 || true
# let pods in the cluster reach LocalStack by name (http://curve-localstack:4566)
docker network connect kind curve-localstack 2>/dev/null || true
# attaching the network briefly interrupts the published port; wait until it answers steadily
ok=0
for _ in $(seq 1 30); do
  if curl -sf -m 3 http://localhost:4566/_localstack/health >/dev/null; then ok=$((ok+1)); else ok=0; fi
  [ "$ok" -ge 5 ] && break
  sleep 1
done
[ "$ok" -ge 5 ] || { echo "LocalStack not answering after network attach"; exit 1; }
KUBECONFIG=.local/kubeconfig kubectl get nodes
