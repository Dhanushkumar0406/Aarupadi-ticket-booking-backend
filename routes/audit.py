from flask import Blueprint, jsonify, request

from utils.auth import get_authenticated_user, require_admin
from utils.db import get_db_connection


audit_bp = Blueprint("audit_bp", __name__)


@audit_bp.route("/audit-logs", methods=["GET"])
def get_audit_logs():
    payload, error, status = get_authenticated_user()
    if error:
        return jsonify(error), status
    err, err_status = require_admin(payload)
    if err:
        return jsonify(err), err_status

    search = request.args.get("q")
    action = request.args.get("action")

    filters = []
    params = []

    if action:
        filters.append("action = ?")
        params.append(action.strip())
    if search:
        filters.append("(action LIKE ? OR actor_username LIKE ? OR target_id LIKE ?)")
        params.extend([f"%{search.strip()}%"] * 3)

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
    cur.execute(f"SELECT COUNT(*) AS count FROM audit_logs {where_clause}", params)
    total = cur.fetchone()["count"]

    cur.execute(
        f"""
        SELECT id, action, actor_user_id, actor_username, target_type, target_id, details, created_at
        FROM audit_logs
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
    )
