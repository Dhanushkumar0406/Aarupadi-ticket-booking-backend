import random
from flask import Blueprint, jsonify, request

from utils.audit import log_action
from utils.auth import get_authenticated_user, get_optional_user, require_admin
from utils.db import get_db_connection


registration_bp = Blueprint("registration_bp", __name__)

TEMPLE_PRICES = {
    "Palani": 200,
    "Thiruchendur": 250,
    "Swamimalai": 350,
    "Thirupparamkunram": 350,
    "Pazhamudircholai": 350,
    "Tiruttani": 300,
    "Marudhamalai": 150,
}


def calculate_cost(age, temple_name):
    if age > 60:
        return 0
    return TEMPLE_PRICES.get(temple_name, 0)


def generate_citizen_id():
    return f"MTP-{random.randint(10000, 99999)}"


def _parse_int(value, field_name):
    try:
        return int(value), None
    except (TypeError, ValueError):
        return None, {"error": f"{field_name} must be a number."}


def _validate_temple(temple_name):
    if temple_name not in TEMPLE_PRICES:
        return {"error": "Invalid temple selection."}
    return None


@registration_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}

    name = data.get("name", "").strip()
    city = data.get("city", "").strip()
    district = data.get("district", "").strip()
    age = data.get("age")
    aadhar_number = data.get("aadhar_number", "").strip()
    package_language = data.get("package_language", "").strip()

    if not name:
        return jsonify({"error": "Name is required."}), 400
    if not city:
        return jsonify({"error": "City is required."}), 400
    if not district:
        return jsonify({"error": "District is required."}), 400
    if age is None or age == "":
        return jsonify({"error": "Age is required."}), 400
    if not aadhar_number:
        return jsonify({"error": "Aadhar number is required."}), 400

    age, err = _parse_int(age, "Age")
    if err:
        return jsonify(err), 400

    if age >= 60:
        cost = 0
        temple_name = "Aarupadai Murugan Temples - Free Package"
        package_language = "Free"
    else:
        if not package_language or package_language not in ["Tamil", "English"]:
            return jsonify({"error": "Package language is required for age below 60."}), 400
        cost = 2500
        temple_name = "Aarupadai Murugan Temples Package" if package_language == "English" else "ஆறுபடை முருகன் கோவில் பேக்கேஜ்"

    payload, auth_error, auth_status = get_optional_user()
    created_by_user_id = None
    if payload and payload.get("sub") is not None:
        try:
            created_by_user_id = int(payload.get("sub"))
        except (TypeError, ValueError):
            created_by_user_id = None

    citizen_id = generate_citizen_id()

    conn = get_db_connection()
    cur = conn.cursor()

    while True:
        cur.execute("SELECT id FROM registrations WHERE citizen_id = ?", (citizen_id,))
        if cur.fetchone() is None:
            break
        citizen_id = generate_citizen_id()

    cur.execute(
        """
        INSERT INTO registrations (
            citizen_id, name, city, district, age, aadhar_number, temple_name, cost,
            boarding_point, status, package_language, created_at, created_by_user_id
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING', ?, datetime('now'), ?)
        """,
        (citizen_id, name, city, district, age, aadhar_number, temple_name, cost, city, package_language, created_by_user_id),
    )
    conn.commit()
    registration_id = cur.lastrowid
    conn.close()

    log_action(
        "create_registration",
        actor_user_id=created_by_user_id,
        target_type="registration",
        target_id=registration_id,
        details={
            "citizen_id": citizen_id,
            "name": name,
        },
    )

    return jsonify(
        {
            "message": "Registration submitted for approval",
            "id": registration_id,
            "citizen_id": citizen_id,
            "status": "PENDING",
            "cost": cost,
            "package": temple_name,
        }
    ), 201


@registration_bp.route("/my-registrations", methods=["GET"])
def get_my_registrations():
    payload, error, status = get_authenticated_user()
    if error:
        return jsonify(error), status

    try:
        user_id = int(payload.get("sub"))
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid user."}), 400

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, citizen_id, name, city, district, age, aadhar_number, temple_name, cost,
               boarding_point, status, package_language, created_at, updated_at
        FROM registrations
        WHERE created_by_user_id = ?
        ORDER BY created_at DESC
        """,
        (user_id,),
    )
    rows = cur.fetchall()
    conn.close()

    return jsonify({"items": [dict(row) for row in rows]}), 200


@registration_bp.route("/registrations", methods=["GET"])
def get_registrations():
    payload, error, status = get_authenticated_user()
    if error:
        return jsonify(error), status
    err, err_status = require_admin(payload)
    if err:
        return jsonify(err), err_status

    status_filter = request.args.get("status")
    search = request.args.get("q")
    temple = request.args.get("temple")
    district = request.args.get("district")
    city = request.args.get("city")
    date_from = request.args.get("from")
    date_to = request.args.get("to")

    filters = []
    params = []

    if status_filter:
        filters.append("status = ?")
        params.append(status_filter.strip().upper())
    if temple:
        filters.append("temple_name = ?")
        params.append(temple.strip())
    if district:
        filters.append("district = ?")
        params.append(district.strip())
    if city:
        filters.append("city = ?")
        params.append(city.strip())
    if search:
        filters.append("(name LIKE ? OR citizen_id LIKE ?)")
        params.extend([f"%{search.strip()}%", f"%{search.strip()}%"])
    if date_from:
        filters.append("date(created_at) >= date(?)")
        params.append(date_from)
    if date_to:
        filters.append("date(created_at) <= date(?)")
        params.append(date_to)

    where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""

    try:
        page = int(request.args.get("page", 1))
    except ValueError:
        page = 1
    try:
        limit = int(request.args.get("limit", 20))
    except ValueError:
        limit = 20

    page = max(page, 1)
    limit = min(max(limit, 1), 100)
    offset = (page - 1) * limit

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(f"SELECT COUNT(*) as count FROM registrations {where_clause}", params)
    total = cur.fetchone()["count"]

    cur.execute(
        f"""
        SELECT id, citizen_id, name, city, district, age, aadhar_number, temple_name, cost,
               boarding_point, status, package_language, created_at, created_by_user_id, updated_at
        FROM registrations
        {where_clause}
        ORDER BY created_at DESC
        LIMIT ? OFFSET ?
        """,
        params + [limit, offset],
    )
    rows = cur.fetchall()
    conn.close()

    return jsonify(
        {
            "items": [dict(row) for row in rows],
            "page": page,
            "limit": limit,
            "total": total,
            "pages": (total + limit - 1) // limit if total else 1,
        }
    ), 200


@registration_bp.route("/registration/<int:registration_id>", methods=["PATCH"])
def update_registration(registration_id):
    payload, error, status = get_authenticated_user()
    if error:
        return jsonify(error), status

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, created_by_user_id, age, temple_name, city, status, aadhar_number
        FROM registrations WHERE id = ?
        """,
        (registration_id,),
    )
    existing = cur.fetchone()
    if existing is None:
        conn.close()
        return jsonify({"error": "Registration not found."}), 404

    try:
        actor_id = int(payload.get("sub"))
    except (TypeError, ValueError):
        actor_id = None

    is_admin = payload.get("role") == "admin"
    if not is_admin and existing["created_by_user_id"] != actor_id:
        conn.close()
        return jsonify({"error": "Not authorized to edit this registration."}), 403

    data = request.get_json(silent=True) or {}
    updates = {}

    if "name" in data:
        name = str(data.get("name", "")).strip()
        if not name:
            conn.close()
            return jsonify({"error": "Name is required."}), 400
        updates["name"] = name

    if "city" in data:
        city = str(data.get("city", "")).strip()
        if not city:
            conn.close()
            return jsonify({"error": "City is required."}), 400
        updates["city"] = city
        updates["boarding_point"] = city

    if "district" in data:
        district = str(data.get("district", "")).strip()
        if not district:
            conn.close()
            return jsonify({"error": "District is required."}), 400
        updates["district"] = district

    if "aadhar_number" in data:
        aadhar = str(data.get("aadhar_number", "")).strip()
        if not aadhar:
            conn.close()
            return jsonify({"error": "Aadhar number is required."}), 400
        updates["aadhar_number"] = aadhar

    age = existing["age"]
    temple_name = existing["temple_name"]

    if "age" in data:
        age_value, err = _parse_int(data.get("age"), "Age")
        if err:
            conn.close()
            return jsonify(err), 400
        age = age_value
        updates["age"] = age_value

    if "temple_name" in data:
        temple_value = str(data.get("temple_name", "")).strip()
        temple_err = _validate_temple(temple_value)
        if temple_err:
            conn.close()
            return jsonify(temple_err), 400
        temple_name = temple_value
        updates["temple_name"] = temple_value

    if "status" in data:
        if not is_admin:
            conn.close()
            return jsonify({"error": "Only admins can update status."}), 403
        status_value = str(data.get("status", "")).strip().upper()
        if status_value not in {"PENDING", "APPROVED", "REJECTED", "CANCELLED"}:
            conn.close()
            return jsonify({"error": "Invalid status."}), 400
        updates["status"] = status_value

    if not updates:
        conn.close()
        return jsonify({"error": "No valid fields to update."}), 400

    if "age" in updates or "temple_name" in updates:
        updates["cost"] = calculate_cost(age, temple_name)

    updates["updated_at"] = "datetime('now')"

    set_clause = ", ".join(
        f"{field} = {value}" if value == "datetime('now')" else f"{field} = ?"
        for field, value in updates.items()
    )

    params = [value for value in updates.values() if value != "datetime('now')"]
    params.append(registration_id)
    cur.execute(f"UPDATE registrations SET {set_clause} WHERE id = ?", params)
    conn.commit()
    conn.close()

    log_action(
        "update_registration",
        actor_user_id=actor_id,
        target_type="registration",
        target_id=registration_id,
        details={"updates": updates},
    )

    return jsonify({"message": "Registration updated."}), 200


@registration_bp.route("/registration/<int:registration_id>", methods=["DELETE"])
def cancel_registration(registration_id):
    payload, error, status = get_authenticated_user()
    if error:
        return jsonify(error), status

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, created_by_user_id FROM registrations WHERE id = ?",
        (registration_id,),
    )
    existing = cur.fetchone()
    if existing is None:
        conn.close()
        return jsonify({"error": "Registration not found."}), 404

    try:
        actor_id = int(payload.get("sub"))
    except (TypeError, ValueError):
        actor_id = None

    is_admin = payload.get("role") == "admin"
    if not is_admin and existing["created_by_user_id"] != actor_id:
        conn.close()
        return jsonify({"error": "Not authorized to cancel this registration."}), 403

    cur.execute("DELETE FROM registrations WHERE id = ?", (registration_id,))
    conn.commit()
    conn.close()

    log_action(
        "delete_registration",
        actor_user_id=actor_id,
        target_type="registration",
        target_id=registration_id,
    )

    return jsonify({"message": "Registration deleted."}), 200
