#!/usr/bin/env bash
# Run a workload inside the environment that uses the AWS resources the blueprint created:
# it reads its resource names from the ConfigMap, writes to S3, sends an SQS message,
# reads the secret and writes a log event. LocalStack does not enforce IAM, so this shows
# the resources are reachable and wired, not that the role's permissions are enforced.
set -euo pipefail
cd "$(dirname "$0")/.."
N=${1:?environment name}
export KUBECONFIG=${KUBECONFIG:-$PWD/.local/kubeconfig}
A=scripts/awslocal.sh

$A secretsmanager put-secret-value --secret-id "$N/app" --secret-string "local-demo-value" >/dev/null
kubectl -n "$N" delete job demo-workload --ignore-not-found >/dev/null
kubectl -n "$N" apply -f - >/dev/null <<YAML
apiVersion: batch/v1
kind: Job
metadata:
  name: demo-workload
spec:
  backoffLimit: 0
  template:
    spec:
      restartPolicy: Never
      serviceAccountName: app
      containers:
        - name: app
          image: amazon/aws-cli:2.17.0
          envFrom:
            - configMapRef:
                name: cloud-resources
          env:
            - { name: AWS_ENDPOINT_URL, value: "http://curve-localstack:4566" }
            - { name: AWS_ACCESS_KEY_ID, value: test }
            - { name: AWS_SECRET_ACCESS_KEY, value: test }
            - { name: AWS_DEFAULT_REGION, value: us-east-1 }
          command: ["/bin/sh", "-c"]
          args:
            - |
              set -e
              echo "hello from $HOSTNAME" > /tmp/hello.txt
              aws s3 cp /tmp/hello.txt "s3://\$S3_BUCKET/hello.txt"
              aws sqs send-message --queue-url "\$SQS_QUEUE_URL" --message-body "demo event" >/dev/null
              aws secretsmanager get-secret-value --secret-id "\$SECRET_ID" --query SecretString --output text
              STREAM="run-\$(date +%s)"
              aws logs create-log-stream --log-group-name "\$LOG_GROUP" --log-stream-name "\$STREAM"
              aws logs put-log-events --log-group-name "\$LOG_GROUP" --log-stream-name "\$STREAM" \
                --log-events "timestamp=\$(date +%s)000,message=demo workload ran" >/dev/null
              echo "workload finished: used S3, SQS, Secrets Manager and Logs"
YAML
kubectl -n "$N" wait --for=condition=complete job/demo-workload --timeout=180s
echo "--- workload output"; kubectl -n "$N" logs job/demo-workload | tail -4
echo "--- what the workload left in AWS (LocalStack)"
$A s3 ls "s3://$N-data/"
echo "SQS messages waiting: $($A sqs get-queue-attributes --queue-url http://curve-localstack:4566/000000000000/$N-events --attribute-names ApproximateNumberOfMessages --query Attributes.ApproximateNumberOfMessages --output text)"
$A logs filter-log-events --log-group-name "/curve-metrics/$N" --query 'events[0].message' --output text
