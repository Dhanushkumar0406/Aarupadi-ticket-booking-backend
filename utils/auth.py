from flask import request
import jwt

from utils.db import get_db_connection
from utils.token import decode_token


def _get_bearer_token():
    auth_header = request.headers.get("Authorization", "")
    if auth_header.lower().startswith("bearer "):
        return auth_header.split(" ", 1)[1].strip()
    return None


def _is_token_revoked(jti):
    if not jti:
        return False
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM revoked_tokens WHERE jti = ?", (jti,))
    revoked = cur.fetchone() is not None
    conn.close()
    return revoked


def get_authenticated_user():
    token = _get_bearer_token()
    if not token:
        return None, {"error": "Authorization token required."}, 401

    try:
        payload = decode_token(token)
    except jwt.ExpiredSignatureError:
        return None, {"error": "Token expired. Please login again."}, 401
    except jwt.InvalidTokenError:
        return None, {"error": "Invalid token."}, 401

    if _is_token_revoked(payload.get("jti")):
        return None, {"error": "Token revoked. Please login again."}, 401

    return payload, None, None


def get_optional_user():
    token = _get_bearer_token()
    if not token:
        return None, None, None

    try:
        payload = decode_token(token)
        if _is_token_revoked(payload.get("jti")):
            return None, None, None
        return payload, None, None
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None, None, None


def require_admin(payload):
    if payload is None or payload.get("role") != "admin":
        return {"error": "Admin access required."}, 403
    return None, None


def revoke_token(jti):
    if not jti:
        return
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT OR IGNORE INTO revoked_tokens (jti, revoked_at) VALUES (?, datetime('now'))",
        (jti,),
    )
    conn.commit()
    conn.close()
