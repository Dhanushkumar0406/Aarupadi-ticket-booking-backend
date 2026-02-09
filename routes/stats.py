from flask import Blueprint, jsonify

from utils.auth import get_authenticated_user, require_admin
from utils.db import get_db_connection


stats_bp = Blueprint("stats_bp", __name__)


@stats_bp.route("/stats", methods=["GET"])
def get_stats():
    payload, error, status = get_authenticated_user()
    if error:
        return jsonify(error), status
    err, err_status = require_admin(payload)
    if err:
        return jsonify(err), err_status

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) AS count FROM registrations")
    total = cur.fetchone()["count"]

    cur.execute("SELECT status, COUNT(*) AS count FROM registrations GROUP BY status")
    status_counts = {row["status"]: row["count"] for row in cur.fetchall()}

    cur.execute(
        """
        SELECT temple_name, COUNT(*) AS count
        FROM registrations
        GROUP BY temple_name
        ORDER BY count DESC
        """
    )
    by_temple = [dict(row) for row in cur.fetchall()]

    cur.execute(
        """
        SELECT district, COUNT(*) AS count
        FROM registrations
        GROUP BY district
        ORDER BY count DESC
        """
    )
    by_district = [dict(row) for row in cur.fetchall()]

    cur.execute(
        """
        SELECT
            COALESCE(SUM(cost), 0) AS revenue,
            SUM(CASE WHEN cost = 0 THEN 1 ELSE 0 END) AS free_count,
            SUM(CASE WHEN cost > 0 THEN 1 ELSE 0 END) AS paid_count
        FROM registrations
        """
    )
    revenue_row = cur.fetchone()

    conn.close()

    return jsonify(
        {
            "totals": {
                "registrations": total,
                "pending": status_counts.get("PENDING", 0),
                "approved": status_counts.get("APPROVED", 0),
                "rejected": status_counts.get("REJECTED", 0),
                "cancelled": status_counts.get("CANCELLED", 0),
            },
            "revenue": {
                "total": revenue_row["revenue"] or 0,
                "paid_count": revenue_row["paid_count"] or 0,
                "free_count": revenue_row["free_count"] or 0,
            },
            "by_temple": by_temple,
            "by_district": by_district,
        }
    )
