import uuid
from datetime import datetime, timedelta, timezone

import jwt

from config.config import SECRET_KEY, TOKEN_EXPIRES_MINUTES


def _now():
    return datetime.now(timezone.utc)


def generate_token(user_id, role):
    expires = _now() + timedelta(minutes=TOKEN_EXPIRES_MINUTES)
    payload = {
        "sub": str(user_id),
        "role": role,
        "jti": uuid.uuid4().hex,
        "iat": int(_now().timestamp()),
        "exp": int(expires.timestamp()),
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
    return token, TOKEN_EXPIRES_MINUTES * 60


def decode_token(token):
    return jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
