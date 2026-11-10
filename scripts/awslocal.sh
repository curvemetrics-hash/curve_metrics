#!/usr/bin/env bash
# Run the AWS CLI against LocalStack, from inside the same docker network as the cluster.
exec docker run --rm --network kind \
  -e AWS_ACCESS_KEY_ID=test -e AWS_SECRET_ACCESS_KEY=test -e AWS_DEFAULT_REGION=us-east-1 \
  amazon/aws-cli:2.17.0 --endpoint-url http://curve-localstack:4566 "$@"
