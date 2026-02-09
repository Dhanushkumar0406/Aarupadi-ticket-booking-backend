import random

from flask import Blueprint, jsonify, request
from werkzeug.security import check_password_hash

from utils.audit import log_action
from utils.auth import get_authenticated_user, require_admin
from utils.db import get_db_connection
from utils.token import generate_token


admin_api_bp = Blueprint("admin_api", __name__, url_prefix="/api/admin")

TEMPLE_PRICES = {
    "Palani": 200,
    "Thiruchendur": 250,
    "Swamimalai": 350,
    "Thirupparamkunram": 350,
    "Pazhamudircholai": 350,
    "Tiruttani": 300,
    "Marudhamalai": 150,
}


def _calculate_cost(age, temple_name):
    if age > 60:
        return 0
    return TEMPLE_PRICES.get(temple_name, 0)


def _generate_citizen_id():
    return f"MTP-{random.randint(10000, 99999)}"


@admin_api_bp.route("/login", methods=["POST"])
def admin_login():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = (data.get("password") or "").strip()

    if not username or not password:
        return jsonify({"error": "Username and password required."}), 400

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, username, password, role FROM users WHERE username = ? AND role = 'admin'",
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

    conn.close()

    if not valid:
        return jsonify({"error": "Invalid credentials."}), 401

    token, expires_in = generate_token(row["id"], row["role"])
    log_action("admin_login", actor_user_id=row["id"])

    return jsonify({
        "token": token,
        "role": row["role"],
        "id": row["id"],
        "username": row["username"],
        "expires_in": expires_in,
    })


@admin_api_bp.route("/pending-users", methods=["GET"])
def pending_users():
    payload, error, status = get_authenticated_user()
    if error:
        return jsonify(error), status
    err, err_status = require_admin(payload)
    if err:
        return jsonify(err), err_status

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, username, role, status FROM users WHERE role = 'user' AND status = 'PENDING'")
    rows = cur.fetchall()
    conn.close()

    return jsonify({"users": [dict(row) for row in rows]})


@admin_api_bp.route("/approve/<int:user_id>", methods=["POST"])
def approve_user(user_id):
    payload, error, status = get_authenticated_user()
    if error:
        return jsonify(error), status
    err, err_status = require_admin(payload)
    if err:
        return jsonify(err), err_status

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, username, role, status FROM users WHERE id = ? AND role = 'user'", (user_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "User not found."}), 404

    cur.execute("UPDATE users SET status = 'APPROVED' WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()

    log_action(
        "approve_user",
        actor_user_id=int(payload.get("sub")),
        target_type="user",
        target_id=user_id,
    )

    return jsonify({"message": "User approved", "user": dict(row) | {"status": "APPROVED"}})


@admin_api_bp.route("/reject/<int:user_id>", methods=["POST"])
def reject_user(user_id):
    payload, error, status = get_authenticated_user()
    if error:
        return jsonify(error), status
    err, err_status = require_admin(payload)
    if err:
        return jsonify(err), err_status

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, username, role, status FROM users WHERE id = ? AND role = 'user'", (user_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "User not found."}), 404

    cur.execute("UPDATE users SET status = 'REJECTED' WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()

    log_action(
        "reject_user",
        actor_user_id=int(payload.get("sub")),
        target_type="user",
        target_id=user_id,
    )

    return jsonify({"message": "User rejected", "user": dict(row) | {"status": "REJECTED"}})


@admin_api_bp.route("/ticket/<int:user_id>", methods=["POST"])
def issue_ticket(user_id):
    payload, error, status = get_authenticated_user()
    if error:
        return jsonify(error), status
    err, err_status = require_admin(payload)
    if err:
        return jsonify(err), err_status

    data = request.get_json(silent=True) or {}
    boarding_point = (data.get("boarding_point") or "").strip()
    temple_name = (data.get("temple_name") or "").strip()
    age = data.get("age")

    if not boarding_point or not temple_name or age is None:
        return jsonify({"error": "Missing required fields.", "fields": ["boarding_point", "temple_name", "age"]}), 400

    try:
        age = int(age)
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid age."}), 400

    if temple_name not in TEMPLE_PRICES:
        return jsonify({"error": "Invalid temple name."}), 400

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, username, status FROM users WHERE id = ? AND role = 'user'", (user_id,))
    user = cur.fetchone()
    if not user:
        conn.close()
        return jsonify({"error": "User not found."}), 404

    if user["status"] != "APPROVED":
        conn.close()
        return jsonify({"error": "User must be approved before issuing a ticket."}), 403

    cost = _calculate_cost(age, temple_name)
    citizen_id = _generate_citizen_id()

    while True:
        cur.execute("SELECT id FROM registrations WHERE citizen_id = ?", (citizen_id,))
        if cur.fetchone() is None:
            break
        citizen_id = _generate_citizen_id()

    cur.execute(
        """
        INSERT INTO registrations (
            citizen_id, name, city, district, age, temple_name, cost,
            boarding_point, status, created_at, created_by_user_id
        )
        VALUES (?, ?, ?, '', ?, ?, ?, ?, 'APPROVED', datetime('now'), ?)
        """,
        (citizen_id, user["username"], boarding_point, age, temple_name, cost, boarding_point, int(payload.get("sub"))),
    )
    conn.commit()
    ticket_id = cur.lastrowid
    conn.close()

    log_action(
        "issue_ticket",
        actor_user_id=int(payload.get("sub")),
        target_type="user",
        target_id=user_id,
        details={"ticket_id": ticket_id, "temple_name": temple_name, "cost": cost},
    )

    return jsonify({
        "message": "Ticket issued",
        "ticket": {
            "id": ticket_id,
            "citizen_id": citizen_id,
            "temple_name": temple_name,
            "boarding_point": boarding_point,
            "age": age,
            "cost": cost,
            "is_free": cost == 0,
        },
    })
