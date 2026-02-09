from datetime import datetime, timedelta

import jwt


def generate_token(user, secret, expires_minutes):
    payload = {
        "user_id": user.id,
        "role": user.role,
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + timedelta(minutes=expires_minutes),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def decode_token(token, secret):
    return jwt.decode(token, secret, algorithms=["HS256"])
