import json

from utils.db import get_db_connection


def log_action(action, actor_user_id=None, target_type=None, target_id=None, details=None):
    conn = get_db_connection()
    cur = conn.cursor()

    actor_username = None
    if actor_user_id is not None:
        cur.execute("SELECT username FROM users WHERE id = ?", (actor_user_id,))
        row = cur.fetchone()
        if row:
            actor_username = row["username"]

    cur.execute(
        """
        INSERT INTO audit_logs (action, actor_user_id, actor_username, target_type, target_id, details, created_at)
        VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
        """,
        (
            action,
            actor_user_id,
            actor_username,
            target_type,
            str(target_id) if target_id is not None else None,
            json.dumps(details) if details is not None else None,
        ),
    )
    conn.commit()
    conn.close()
