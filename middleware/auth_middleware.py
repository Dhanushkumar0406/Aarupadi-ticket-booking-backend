import logging
from functools import wraps

from flask import current_app, g, jsonify, request

from models import db
from models.user import User
from utils.jwt import decode_token

logger = logging.getLogger(__name__)


def token_required(role=None):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            auth_header = request.headers.get("Authorization", "")
            if not auth_header.startswith("Bearer "):
                logger.warning("Auth failed: missing or invalid Authorization header")
                return (
                    jsonify({"error": "Missing or invalid Authorization header."}),
                    401,
                )

            token = auth_header.split(" ", 1)[1].strip()
            if not token:
                logger.warning("Auth failed: empty token")
                return jsonify({"error": "Missing token."}), 401

            try:
                payload = decode_token(
                    token,
                    current_app.config["JWT_SECRET_KEY"],
                )
            except Exception as exc:
                logger.warning("Auth failed: token decode error: %s", exc)
                return jsonify({"error": "Invalid or expired token."}), 401

            user_id = payload.get("user_id")
            if not user_id:
                return jsonify({"error": "Invalid token payload."}), 401

            user = db.session.get(User, user_id)
            if not user:
                return jsonify({"error": "User not found."}), 401

            if role and user.role != role:
                return jsonify({"error": "Forbidden."}), 403

            g.current_user = user
            return fn(*args, **kwargs)

        return wrapper

    return decorator
