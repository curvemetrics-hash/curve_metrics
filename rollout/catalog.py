"""Build a demo blueprint catalog: a git repo with three tagged releases.

  v1.0.0  the blueprint as it is today
  v1.1.0  a good change: log retention default 30 -> 90 days
  v1.2.0  a BAD change: removes the default-deny network policy (a regression)

A real catalog is any git repo holding blueprints/ and modules/ with version tags.
"""
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def sync_remote():
    """Production: keep a clone of the blueprint repository (CATALOG_URL) up to date, with all tags.
    A private repository needs a read-only deploy token inside the URL or a git credential helper."""
    url = os.environ.get("CATALOG_URL")
    if not url:
        return None
    dest = os.environ.get("CATALOG_DIR", os.path.join(ROOT, ".local", "rollout", "catalog"))
    if os.path.isdir(os.path.join(dest, ".git")):
        subprocess.run(["git", "-C", dest, "fetch", "--tags", "--prune", "--force", "origin"], check=True, capture_output=True)
    else:
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        subprocess.run(["git", "clone", "--quiet", url, dest], check=True, capture_output=True)
    return dest


def _git(repo, *args):
    subprocess.run(["git", "-C", repo, "-c", "user.name=catalog", "-c", "user.email=catalog@example.invalid",
                    *args], check=True, capture_output=True)


def _edit(path, fn):
    text = open(path).read()
    new = fn(text)
    assert new != text, f"edit changed nothing in {path}"
    open(path, "w").write(new)


def build(dest):
    shutil.rmtree(dest, ignore_errors=True)
    os.makedirs(dest)
    for d in ("blueprints", "modules"):
        shutil.copytree(os.path.join(ROOT, d), os.path.join(dest, d),
                        ignore=shutil.ignore_patterns(".terraform", ".terraform.lock.hcl", "plan.*", "*.tfstate*"))
    _git(dest, "init", "-q", "-b", "main")
    _git(dest, "add", "-A")
    _git(dest, "commit", "-q", "-m", "v1.0.0: current blueprint")
    _git(dest, "tag", "v1.0.0")

    _edit(os.path.join(dest, "modules/team_cloud_bindings/variables.tf"),
          lambda t: re.sub(r'(variable "log_retention_days" \{.*?default\s*=\s*)30', r"\g<1>90", t, flags=re.S))
    _git(dest, "commit", "-qam", "v1.1.0: keep logs 90 days")
    _git(dest, "tag", "v1.1.0")

    _edit(os.path.join(dest, "modules/namespace_baseline/main.tf"),
          lambda t: re.sub(r'resource "kubernetes_network_policy_v1" "default_deny_ingress" \{.*?\n\}\n\n', "", t, flags=re.S))
    _git(dest, "commit", "-qam", "v1.2.0: simplify network policies (contains a regression)")
    _git(dest, "tag", "v1.2.0")
    return dest


if __name__ == "__main__":
    print(build(sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, ".local", "rollout", "catalog")))
