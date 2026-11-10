# One image for the web service, the worker and the scheduled scan (Render picks the command).
# Tools are pinned and checksum-verified. Match KUBECTL_VERSION to your EKS version (one minor either way).
FROM python:3.12-slim

ARG TOFU_VERSION=1.13.2
ARG KUBECTL_VERSION=1.33.0
ARG AWSCLI_VERSION=2.17.0

RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl unzip git jq \
 && rm -rf /var/lib/apt/lists/*

RUN set -eux; \
    case "$(dpkg --print-architecture)" in amd64) A=amd64; AW=x86_64 ;; arm64) A=arm64; AW=aarch64 ;; *) echo "unsupported arch"; exit 1 ;; esac; \
    cd /tmp; \
    B="https://github.com/opentofu/opentofu/releases/download/v${TOFU_VERSION}"; \
    curl -fsSLO "$B/tofu_${TOFU_VERSION}_linux_${A}.zip"; \
    curl -fsSLO "$B/tofu_${TOFU_VERSION}_SHA256SUMS"; \
    grep " tofu_${TOFU_VERSION}_linux_${A}.zip\$" "tofu_${TOFU_VERSION}_SHA256SUMS" | sha256sum -c -; \
    unzip -q "tofu_${TOFU_VERSION}_linux_${A}.zip" tofu -d /usr/local/bin; \
    K="https://dl.k8s.io/release/v${KUBECTL_VERSION}/bin/linux/${A}/kubectl"; \
    curl -fsSLo /usr/local/bin/kubectl "$K"; \
    echo "$(curl -fsSL "$K.sha256")  /usr/local/bin/kubectl" | sha256sum -c -; \
    chmod +x /usr/local/bin/kubectl; \
    curl -fsSLo awscli.zip "https://awscli.amazonaws.com/awscli-exe-linux-${AW}-${AWSCLI_VERSION}.zip"; \
    unzip -q awscli.zip; ./aws/install; \
    rm -rf /tmp/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN useradd --uid 10001 --create-home app && mkdir -p /opt/tf-plugins && chown app /opt/tf-plugins /app
COPY --chown=app:app . /app
USER app

# Download the Terraform providers once at build time so jobs do not depend on the registry being fast.
ENV TF_PLUGIN_CACHE_DIR=/opt/tf-plugins TF_IN_AUTOMATION=1 PYTHONUNBUFFERED=1 HOST=0.0.0.0
RUN tofu -chdir=blueprints/standard_team_env init -backend=false -input=false >/dev/null \
 && rm -rf blueprints/standard_team_env/.terraform

# Safe by default: the console refuses to start without AUTH_MODE=cloudflare on a non-local address.
ENTRYPOINT ["/app/deploy/entrypoint.sh"]
CMD ["python", "-m", "spaces.server"]
