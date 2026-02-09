from flask import Blueprint, jsonify, request

from utils.audit import log_action
from utils.auth import get_authenticated_user, require_admin
from utils.db import get_db_connection


admin_bp = Blueprint("admin_bp", __name__)


@admin_bp.route("/approve", methods=["POST"])
def approve():
    payload, error, status = get_authenticated_user()
    if error:
        return jsonify(error), status
    err, err_status = require_admin(payload)
    if err:
        return jsonify(err), err_status

    data = request.get_json(silent=True) or {}
    registration_id = data.get("registration_id")
    
    if not registration_id:
        return jsonify({"error": "Registration ID is required."}), 400

    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute(
        "UPDATE registrations SET status = 'APPROVED', updated_at = datetime('now') WHERE id = ?",
        (registration_id,),
    )
    conn.commit()
    conn.close()

    log_action(
        "approve_registration",
        actor_user_id=int(payload.get("sub")),
        target_type="registration",
        target_id=registration_id,
    )
    
    return jsonify({"message": "Registration approved"}), 200


@admin_bp.route("/reject", methods=["POST"])
def reject():
    payload, error, status = get_authenticated_user()
    if error:
        return jsonify(error), status
    err, err_status = require_admin(payload)
    if err:
        return jsonify(err), err_status

    data = request.get_json(silent=True) or {}
    registration_id = data.get("registration_id")
    if not registration_id:
        return jsonify({"error": "Registration ID is required."}), 400

    response, status_code = _update_status(registration_id, "REJECTED")
    if status_code == 200:
        log_action(
            "reject_registration",
            actor_user_id=int(payload.get("sub")),
            target_type="registration",
            target_id=registration_id,
        )
    return response, status_code


def _update_status(registration_id, status):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE registrations SET status = ?, updated_at = datetime('now') WHERE id = ?",
        (status, registration_id),
    )
    conn.commit()
    updated = cur.rowcount
    conn.close()

    if updated == 0:
        return jsonify({"error": "Registration not found."}), 404

    return jsonify({"message": f"Registration {status.lower()}"}), 200
