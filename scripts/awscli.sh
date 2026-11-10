#!/usr/bin/env bash
# The AWS CLI for the current mode: real AWS (PLATFORM_MODE=aws) or LocalStack (default).
if [ "${PLATFORM_MODE:-local}" = "aws" ]; then exec aws "$@"; fi
exec "$(dirname "$0")/awslocal.sh" "$@"
