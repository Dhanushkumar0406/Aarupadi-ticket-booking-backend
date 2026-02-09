from flask import Blueprint, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

from utils.audit import log_action
from utils.auth import get_authenticated_user, revoke_token
from utils.db import get_db_connection
from utils.token import generate_token


auth_bp = Blueprint("auth_bp", __name__)


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()

    if not username or not password:
        return jsonify({"error": "Username and password are required."}), 400

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, username, password, role, status FROM users WHERE username = ?",
        (username,),
    )
    row = cur.fetchone()
    if row is None:
        conn.close()
        return jsonify({"error": "Invalid credentials."}), 401

    stored_password = row["password"] or ""
    is_hashed = stored_password.startswith(("pbkdf2:", "scrypt:", "argon2:"))
    if is_hashed:
        valid = check_password_hash(stored_password, password)
    else:
        valid = stored_password == password
        if valid:
            cur.execute(
                "UPDATE users SET password = ? WHERE id = ?",
                (generate_password_hash(password), row["id"]),
            )
            conn.commit()

    conn.close()

    if not valid:
        return jsonify({"error": "Invalid credentials."}), 401

    user_status = row["status"] if "status" in row.keys() else "APPROVED"
    if row["role"] != "admin" and user_status == "PENDING":
        return jsonify({"error": "Your account is pending admin approval."}), 403
    if row["role"] != "admin" and user_status == "REJECTED":
        return jsonify({"error": "Your account has been rejected."}), 403

    token, expires_in = generate_token(row["id"], row["role"])
    log_action("login", actor_user_id=row["id"])

    return jsonify(
        {
            "id": row["id"],
            "username": row["username"],
            "role": row["role"],
            "token": token,
            "expires_in": expires_in,
        }
    ), 200


@auth_bp.route("/signup", methods=["POST"])
def signup():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()

    if not username or not password:
        return jsonify({"error": "Username and password are required."}), 400
    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters."}), 400

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE username = ?", (username,))
    if cur.fetchone() is not None:
        conn.close()
        return jsonify({"error": "Username already exists."}), 409

    cur.execute(
        "INSERT INTO users (username, password, role, status) VALUES (?, ?, 'user', 'PENDING')",
        (username, generate_password_hash(password)),
    )
    conn.commit()
    user_id = cur.lastrowid
    conn.close()

    log_action("signup", actor_user_id=user_id)

    return jsonify(
        {
            "id": user_id,
            "username": username,
            "message": "Account created. Please wait for admin approval before logging in.",
        }
    ), 201


@auth_bp.route("/logout", methods=["POST"])
def logout():
    payload, error, status = get_authenticated_user()
    if error:
        return jsonify(error), status

    revoke_token(payload.get("jti"))
    try:
        actor_id = int(payload.get("sub"))
    except (TypeError, ValueError):
        actor_id = None
    log_action("logout", actor_user_id=actor_id)

    return jsonify({"message": "Logged out"}), 200
