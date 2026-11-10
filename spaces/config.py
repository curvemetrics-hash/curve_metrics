"""Runtime configuration, read from the environment. Functions, not constants, so tests can change it.

  PLATFORM_MODE   local (default: kind + LocalStack)  |  aws (real AWS and a real cluster)
  AUTH_MODE       off (default, localhost only)       |  cloudflare (Cloudflare Access login)
  DATABASE_URL    postgres://... on Render; unset means a SQLite file under .local/
  EMBEDDED_WORKER 1 runs the job worker inside the web process (local dev); 0 on Render
"""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get(name, default=None):
    v = os.environ.get(name)
    return v if v not in (None, "") else default


def mode():
    return get("PLATFORM_MODE", "local")


def is_aws():
    return mode() == "aws"


def auth_mode():
    return get("AUTH_MODE", "off")


def database_url():
    return get("DATABASE_URL")


def sqlite_path():
    return get("SQLITE_PATH", os.path.join(ROOT, ".local", "platform.db"))


def embedded_worker():
    return get("EMBEDDED_WORKER", "1" if not is_aws() else "0") == "1"


def host():
    return get("HOST", "127.0.0.1")


def port():
    return int(get("PORT", "8080"))


def emails(name):
    """Comma separated list from the environment; entries like '@example.com' match a whole domain."""
    return [x.strip().lower() for x in (get(name, "") or "").split(",") if x.strip()]


def kubeconfig(readonly=False):
    base = get("KUBECONFIG", os.path.join(ROOT, ".local", "kubeconfig"))
    ro = get("KUBECONFIG_RO")
    return ro if (readonly and ro) else base


def check_startup():
    """Refuse unsafe combinations before serving anything."""
    problems = []
    if auth_mode() == "off" and host() not in ("127.0.0.1", "localhost", "::1") and get("ALLOW_INSECURE") != "1":
        problems.append("AUTH_MODE=off is only allowed on localhost; set AUTH_MODE=cloudflare")
    if auth_mode() == "cloudflare":
        for v in ("CF_TEAM_DOMAIN", "CF_ACCESS_AUD"):
            if not get(v):
                problems.append(f"{v} is required when AUTH_MODE=cloudflare")
    if is_aws() and not database_url() and get("ALLOW_SQLITE_IN_AWS") != "1":
        problems.append("DATABASE_URL is required when PLATFORM_MODE=aws (web and worker must share state)")
    return problems


def tf_backend_args():
    """Flags for `tofu init`: local state in LocalStack, or the real S3 bucket and DynamoDB lock table."""
    if not is_aws():
        return [f"-backend-config={os.path.join(ROOT, 'local', 'backend.hcl')}"]
    need = {"TF_STATE_BUCKET": get("TF_STATE_BUCKET"), "TF_LOCK_TABLE": get("TF_LOCK_TABLE")}
    missing = [k for k, v in need.items() if not v]
    if missing:
        raise RuntimeError("missing environment: " + ", ".join(missing))
    return [f"-backend-config=bucket={need['TF_STATE_BUCKET']}", f"-backend-config=dynamodb_table={need['TF_LOCK_TABLE']}",
            f"-backend-config=region={get('AWS_REGION', 'us-east-1')}", "-backend-config=encrypt=true"]


def tf_var_args():
    """Flags for plan, apply and destroy that differ between local and real AWS."""
    if not is_aws():
        return [f"-var-file={os.path.join(ROOT, 'local', 'local.tfvars')}"]
    out = [f"-var=aws_region={get('AWS_REGION', 'us-east-1')}"]
    for var, env in (("oidc_provider_arn", "OIDC_PROVIDER_ARN"), ("oidc_issuer", "OIDC_ISSUER")):
        if not get(env):
            raise RuntimeError(f"missing environment: {env}")
        out.append(f"-var={var}={get(env)}")
    if get("PERMISSIONS_BOUNDARY_ARN"):
        out.append(f"-var=permissions_boundary_arn={get('PERMISSIONS_BOUNDARY_ARN')}")
    return out
