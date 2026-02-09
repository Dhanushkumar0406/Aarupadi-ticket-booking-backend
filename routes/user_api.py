from flask import Blueprint, jsonify

from utils.auth import get_authenticated_user
from utils.db import get_db_connection


user_api_bp = Blueprint("user_api", __name__, url_prefix="/api/user")


@user_api_bp.route("/ticket", methods=["GET"])
def my_ticket():
    payload, error, status = get_authenticated_user()
    if error:
        return jsonify(error), status

    user_id = payload.get("sub")

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, citizen_id, name, city, district, age, temple_name, cost,
               boarding_point, status, created_at
        FROM registrations
        WHERE created_by_user_id = ?
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (user_id,),
    )
    row = cur.fetchone()
    conn.close()

    return jsonify({"ticket": dict(row) if row else None})
