"""Cloudflare Access token checks, with a throwaway RSA key standing in for Cloudflare's."""
import base64
import json
import os
import sys
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from cryptography.hazmat.primitives import hashes  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import padding, rsa  # noqa: E402

from spaces import auth  # noqa: E402

TEAM, AUD = "acme.cloudflareaccess.com", "aud-123"


def b64(b):
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def jwk(key, kid):
    n = key.public_key().public_numbers()
    return {"kid": kid, "kty": "RSA", "n": b64(n.n.to_bytes(256, "big")), "e": b64(n.e.to_bytes(3, "big"))}


def token(claims=None, key=KEY, kid="k1", alg="RS256"):
    c = {"iss": f"https://{TEAM}", "aud": [AUD], "exp": time.time() + 600, "email": "Dev@Acme.com", **(claims or {})}
    h, p = b64(json.dumps({"alg": alg, "kid": kid}).encode()), b64(json.dumps(c).encode())
    sig = key.sign(f"{h}.{p}".encode(), padding.PKCS1v15(), hashes.SHA256())
    return f"{h}.{p}.{b64(sig)}"


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    auth._keys.update(at=0, jwks={})
    for v in ("ADMIN_EMAILS", "OPERATOR_EMAILS", "ACCESS_DEFAULT_ROLE"):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setenv("AUTH_MODE", "cloudflare")
    monkeypatch.setenv("CF_TEAM_DOMAIN", TEAM)
    monkeypatch.setenv("CF_ACCESS_AUD", AUD)
    monkeypatch.setattr(auth, "_fetch_jwks", lambda d: {"k1": jwk(KEY, "k1")})


def verify(t, **kw):
    return auth.verify_token(t, TEAM, AUD, fetch=lambda d: {"k1": jwk(KEY, "k1")}, **kw)


def test_valid_token():
    assert verify(token())["email"] == "Dev@Acme.com"


@pytest.mark.parametrize("t,why", [
    (lambda: token(key=OTHER), "signature"),
    (lambda: token({"aud": ["someone-else"]}), "audience"),
    (lambda: token({"iss": "https://evil.example.com"}), "issuer"),
    (lambda: token({"exp": time.time() - 3600}), "expired"),
    (lambda: token({"nbf": time.time() + 3600}), "not yet valid"),
    (lambda: token(alg="none"), "algorithm"),
    (lambda: token(alg="HS256"), "algorithm"),
    (lambda: token(kid="unknown"), "signing key"),
    (lambda: "not.a.jwt", "malformed"),
    (lambda: "garbage", "malformed"),
])
def test_bad_tokens_rejected(t, why):
    with pytest.raises(auth.AuthError) as e:
        verify(t())
    assert why in str(e.value)


def test_tampered_payload_rejected():
    h, p, s = token().split(".")
    forged = b64(json.dumps({"iss": f"https://{TEAM}", "aud": [AUD], "exp": time.time() + 600, "email": "admin@acme.com"}).encode())
    with pytest.raises(auth.AuthError):
        verify(f"{h}.{forged}.{s}")


def test_roles_from_environment(monkeypatch):
    monkeypatch.setenv("ADMIN_EMAILS", "boss@acme.com, @platform.acme.com")
    monkeypatch.setenv("OPERATOR_EMAILS", "dev@acme.com")
    assert auth.role_for("boss@acme.com") == "admin"
    assert auth.role_for("x@platform.acme.com") == "admin"
    assert auth.role_for("dev@acme.com") == "operator"
    assert auth.role_for("rando@acme.com") == "viewer"
    monkeypatch.setenv("ACCESS_DEFAULT_ROLE", "none")
    assert auth.role_for("rando@acme.com") == "none"


def test_identify_from_header_and_cookie(monkeypatch):
    monkeypatch.setenv("OPERATOR_EMAILS", "dev@acme.com")
    assert auth.identify({"Cf-Access-Jwt-Assertion": token()}) == {"id": "dev@acme.com", "role": "operator"}
    assert auth.identify({"Cookie": f"a=b; CF_Authorization={token()}"})["id"] == "dev@acme.com"


def test_missing_token_is_401_and_unlisted_with_none_is_403(monkeypatch):
    with pytest.raises(auth.AuthError) as e:
        auth.identify({})
    assert e.value.code == 401
    monkeypatch.setenv("ACCESS_DEFAULT_ROLE", "none")
    with pytest.raises(auth.AuthError) as e:
        auth.identify({"Cf-Access-Jwt-Assertion": token()})
    assert e.value.code == 403


def test_service_token_uses_common_name(monkeypatch):
    monkeypatch.setenv("OPERATOR_EMAILS", "ci-bot")
    c = {"email": None, "common_name": "ci-bot"}
    assert auth.identify({"Cf-Access-Jwt-Assertion": token(c)}) == {"id": "ci-bot", "role": "operator"}


def test_auth_off_is_local_admin(monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "off")
    assert auth.identify({}) == {"id": "local", "role": "admin"}


def test_allows_ordering():
    assert auth.allows("admin", "operator") and auth.allows("operator", "viewer")
    assert not auth.allows("viewer", "operator")
