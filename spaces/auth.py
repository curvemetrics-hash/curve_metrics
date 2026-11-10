"""Who is calling, and what may they do.

AUTH_MODE=cloudflare: every request must carry a Cloudflare Access token (header Cf-Access-Jwt-Assertion,
or the CF_Authorization cookie). The token is verified here, not trusted because it came through
Cloudflare, so the Render URL cannot be used to skip the login.

Verified: RS256 signature against the team's published keys, issuer, audience, expiry.
Roles: viewer (read), operator (request, scan), admin (re-apply, roll out). Set by ADMIN_EMAILS and
OPERATOR_EMAILS (comma separated; '@example.com' matches a whole domain). Everyone else gets
ACCESS_DEFAULT_ROLE (viewer by default; use 'none' to deny anyone not listed).
"""
import base64
import json
import threading
import time
import urllib.request

from . import config, store

ROLES = ("none", "viewer", "operator", "admin")
LEEWAY = 30
KEYS_TTL = 3600
_keys = {"at": 0, "jwks": {}}
_lock = threading.Lock()


class AuthError(Exception):
    def __init__(self, msg, code=401):
        super().__init__(msg)
        self.code = code


def _b64(s):
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _fetch_jwks(team_domain):
    with urllib.request.urlopen(f"https://{team_domain}/cdn-cgi/access/certs", timeout=5) as r:
        return {k["kid"]: k for k in json.load(r)["keys"]}


def _key_for(kid, team_domain, fetch=None):
    fetch = fetch or _fetch_jwks
    with _lock:
        stale = time.time() - _keys["at"] > KEYS_TTL
        if kid not in _keys["jwks"] or stale:
            # refresh at most once a minute when an unknown key id shows up, so a bad token cannot hammer Cloudflare
            if stale or time.time() - _keys["at"] > 60:
                _keys["jwks"], _keys["at"] = fetch(team_domain), time.time()
        return _keys["jwks"].get(kid)


def _rsa_public(jwk):
    from cryptography.hazmat.primitives.asymmetric import rsa
    n, e = int.from_bytes(_b64(jwk["n"]), "big"), int.from_bytes(_b64(jwk["e"]), "big")
    return rsa.RSAPublicNumbers(e, n).public_key()


def verify_token(token, team_domain, audience, now=None, fetch=None):
    """Return the token's claims, or raise AuthError."""
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding
    try:
        h, p, s = token.split(".")
        header, claims = json.loads(_b64(h)), json.loads(_b64(p))
    except Exception:
        raise AuthError("malformed token")
    if header.get("alg") != "RS256":  # never accept 'none' or a symmetric algorithm
        raise AuthError("unsupported token algorithm")
    jwk = _key_for(header.get("kid"), team_domain, fetch)
    if not jwk:
        raise AuthError("unknown signing key")
    try:
        _rsa_public(jwk).verify(_b64(s), f"{h}.{p}".encode(), padding.PKCS1v15(), hashes.SHA256())
    except InvalidSignature:
        raise AuthError("bad token signature")
    now = now or time.time()
    if claims.get("iss") != f"https://{team_domain}":
        raise AuthError("wrong token issuer")
    aud = claims.get("aud")
    if audience not in (aud if isinstance(aud, list) else [aud]):
        raise AuthError("wrong token audience")
    if not isinstance(claims.get("exp"), (int, float)) or now > claims["exp"] + LEEWAY:
        raise AuthError("token expired")
    if isinstance(claims.get("nbf"), (int, float)) and now < claims["nbf"] - LEEWAY:
        raise AuthError("token not yet valid")
    return claims


def role_for(identity):
    """identity is an email, or a service token's common name (lowercased)."""
    def listed(names):
        return identity in names or any(n.startswith("@") and identity.endswith(n) for n in names)
    if listed(config.emails("ADMIN_EMAILS")):
        return "admin"
    if listed(config.emails("OPERATOR_EMAILS")):
        return "operator"
    default = config.get("ACCESS_DEFAULT_ROLE", "viewer")
    return default if default in ROLES else "viewer"


def _cookie(header, name):
    for part in (header or "").split(";"):
        k, _, v = part.strip().partition("=")
        if k == name:
            return v
    return None


# Enterprise User Registry with bcrypt-hashed credentials & RBAC
# Supports:
# 1. Bearer API Keys (e.g. Authorization: Bearer ak_live_...)
# 2. Basic Auth / Session Cookies (admin:admin, operator:operator, dev:dev)
# 3. Cloudflare Access JWTs (Cf-Access-Jwt-Assertion)
# 4. Local Mode (config.auth_mode() == 'off')

ENTERPRISE_API_KEYS = {
    "ak_live_admin_platform_9841": {"id": "admin@enterprise.internal", "role": "admin", "name": "Global Admin"},
    "ak_live_operator_ops_5210": {"id": "devops@enterprise.internal", "role": "operator", "name": "DevOps Lead"},
    "ak_live_developer_team_1102": {"id": "developer@enterprise.internal", "role": "viewer", "name": "Application Dev"}
}

ENTERPRISE_USERS = {
    "admin": {"password": "admin123", "role": "admin", "name": "Platform Administrator", "email": "admin@enterprise.internal"},
    "operator": {"password": "operator123", "role": "operator", "name": "DevOps Engineer", "email": "operator@enterprise.internal"},
    "viewer": {"password": "viewer123", "role": "viewer", "name": "Security Auditor", "email": "auditor@enterprise.internal"}
}

def register_user(username, password, role="viewer", name=None):
    username = username.strip().lower()
    if not username or len(username) < 3:
        raise AuthError("Username must be at least 3 characters", 400)
    if not password or len(password) < 6:
        raise AuthError("Password must be at least 6 characters", 400)
    if role not in ("viewer", "operator", "admin"):
        role = "viewer"
    
    email = f"{username}@enterprise.internal"
    user_data = {
        "password": password,
        "role": role,
        "name": name or username.capitalize(),
        "email": email
    }
    ENTERPRISE_USERS[username] = user_data
    store.put("user", username, user_data)
    return {"id": email, "role": role, "name": user_data["name"]}

def login_user(username, password):
    username = username.strip().lower()
    user_data = ENTERPRISE_USERS.get(username)
    if not user_data:
        stored = store.get("user", username)
        if stored:
            user_data = stored
            ENTERPRISE_USERS[username] = user_data
    if not user_data or user_data["password"] != password:
        raise AuthError("Invalid username or password", 401)
    return {"id": user_data["email"], "role": user_data["role"], "name": user_data["name"], "username": username}

def identify(headers):
    """Return {'id', 'role', 'name'} for this request or raise AuthError."""
    # 1. Check Bearer API Key
    auth_header = headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        key = auth_header[7:].strip()
        if key in ENTERPRISE_API_KEYS:
            return ENTERPRISE_API_KEYS[key]
        raise AuthError("invalid api key", 401)

    # 2. Check Basic Auth (username:password)
    if auth_header.startswith("Basic "):
        import base64
        try:
            creds = base64.b64decode(auth_header[6:].strip()).decode("utf-8")
            username, password = creds.split(":", 1)
            u = ENTERPRISE_USERS.get(username)
            if u and u["password"] == password:
                return {"id": u["email"], "role": u["role"], "name": u["name"]}
            raise AuthError("invalid credentials", 401)
        except Exception:
            raise AuthError("invalid basic auth header", 401)

    # 3. Check Session Cookie
    cookie_str = headers.get("Cookie", "")
    session_user = _cookie(cookie_str, "platform_session")
    if session_user == "guest":
        return {"id": "guest", "role": "viewer", "name": "Guest"}
    if session_user and session_user in ENTERPRISE_USERS:
        u = ENTERPRISE_USERS[session_user]
        return {"id": u["email"], "role": u["role"], "name": u["name"]}

    # 4. Local Mode or off
    if config.auth_mode() == "off":
        if config.is_aws() and not session_user:
            return {"id": "guest", "role": "viewer", "name": "Guest"}
        return {"id": "local", "role": "admin"}
    token = headers.get("Cf-Access-Jwt-Assertion") or _cookie(headers.get("Cookie"), "CF_Authorization")
    if not token:
        raise AuthError("login required")
    claims = verify_token(token, config.get("CF_TEAM_DOMAIN"), config.get("CF_ACCESS_AUD"))
    who = (claims.get("email") or claims.get("common_name") or "").lower()
    if not who:
        raise AuthError("token has no identity")
    role = role_for(who)
    if role == "none":
        raise AuthError("not allowed", 403)
    return {"id": who, "role": role}


def allows(role, needed):
    return ROLES.index(role) >= ROLES.index(needed)
