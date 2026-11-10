#!/usr/bin/env bash
# Container start: turn the Render environment variables into AWS CLI profiles, then run the command.
#   AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY   keys of a tiny IAM user that can only assume the roles below
#   AWS_ROLE_ARN                                the pipeline role (profile "platform", used by default)
#   AWS_READONLY_ROLE_ARN                       optional read-only role for scans (profile "readonly")
set -euo pipefail
if [ -n "${AWS_ROLE_ARN:-}" ]; then
  : "${AWS_ACCESS_KEY_ID:?}" "${AWS_SECRET_ACCESS_KEY:?}"
  REGION=${AWS_REGION:-us-east-1}
  mkdir -p "$HOME/.aws"
  {
    echo "[profile base]"; echo "region = $REGION"
    echo "[profile platform]"; echo "region = $REGION"; echo "role_arn = $AWS_ROLE_ARN"
    echo "source_profile = base"; echo "role_session_name = curve-platform"
    if [ -n "${AWS_READONLY_ROLE_ARN:-}" ]; then
      echo "[profile readonly]"; echo "region = $REGION"; echo "role_arn = $AWS_READONLY_ROLE_ARN"
      echo "source_profile = base"; echo "role_session_name = curve-readonly"
    fi
  } > "$HOME/.aws/config"
  { echo "[base]"; echo "aws_access_key_id = $AWS_ACCESS_KEY_ID"; echo "aws_secret_access_key = $AWS_SECRET_ACCESS_KEY"; } > "$HOME/.aws/credentials"
  chmod 600 "$HOME/.aws/config" "$HOME/.aws/credentials"
  # tools must use the assumed role, not the long-lived keys, so remove the keys from the environment
  unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY
  export AWS_PROFILE=platform
fi
exec "$@"
