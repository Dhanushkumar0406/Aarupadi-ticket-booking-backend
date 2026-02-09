from flask import Blueprint, jsonify

from utils.auth import get_authenticated_user
from utils.db import get_db_connection


citizen_bp = Blueprint("citizen_bp", __name__)


@citizen_bp.route("/citizen/<int:citizen_id>", methods=["GET"])
def get_citizen(citizen_id):
    payload, error, status = get_authenticated_user()
    if error:
        return jsonify(error), status

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT citizen_id, name, age, gender, address FROM citizens WHERE citizen_id = ?",
        (citizen_id,),
    )
    row = cur.fetchone()
    conn.close()

    if row is None:
        return jsonify({"error": "Citizen not found."}), 404

    return jsonify(
        {
            "citizen_id": row["citizen_id"],
            "name": row["name"],
            "age": row["age"],
            "gender": row["gender"],
            "address": row["address"],
        }
    ), 200
