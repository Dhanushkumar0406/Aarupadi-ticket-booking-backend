from werkzeug.security import generate_password_hash
from utils.db import get_db_connection


HASH_PREFIXES = ("pbkdf2:", "scrypt:", "argon2:")


def _is_hashed(value):
    return isinstance(value, str) and value.startswith(HASH_PREFIXES)


REGISTRATION_COLUMNS = {
    "name": "TEXT NOT NULL DEFAULT ''",
    "city": "TEXT NOT NULL DEFAULT ''",
    "district": "TEXT NOT NULL DEFAULT ''",
    "age": "INTEGER NOT NULL DEFAULT 0",
    "aadhar_number": "TEXT NOT NULL DEFAULT ''",
    "package_language": "TEXT NOT NULL DEFAULT ''",
    "cost": "INTEGER NOT NULL DEFAULT 0",
    "boarding_point": "TEXT NOT NULL DEFAULT ''",
    "created_by_user_id": "INTEGER",
    "updated_at": "TEXT",
    "aadhar_document": "TEXT DEFAULT NULL",
}


def _ensure_registration_columns(cur):
    cur.execute("PRAGMA table_info(registrations)")
    existing = {row["name"] for row in cur.fetchall()}
    for column, definition in REGISTRATION_COLUMNS.items():
        if column not in existing:
            cur.execute(f"ALTER TABLE registrations ADD COLUMN {column} {definition}")


def _ensure_password_hashes(cur):
    cur.execute("SELECT id, password FROM users")
    rows = cur.fetchall()
    for row in rows:
        password = row["password"] or ""
        if not _is_hashed(password):
            cur.execute(
                "UPDATE users SET password = ? WHERE id = ?",
                (generate_password_hash(password), row["id"]),
            )


def init_db():
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            role TEXT NOT NULL
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS citizens (
            citizen_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            age INTEGER NOT NULL,
            gender TEXT NOT NULL,
            address TEXT NOT NULL
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS registrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            citizen_id TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            city TEXT NOT NULL,
            district TEXT NOT NULL,
            age INTEGER NOT NULL,
            temple_name TEXT NOT NULL,
            cost INTEGER NOT NULL,
            boarding_point TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            created_by_user_id INTEGER,
            updated_at TEXT
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS revoked_tokens (
            jti TEXT PRIMARY KEY,
            revoked_at TEXT NOT NULL
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT NOT NULL,
            actor_user_id INTEGER,
            actor_username TEXT,
            target_type TEXT,
            target_id TEXT,
            details TEXT,
            created_at TEXT NOT NULL
        )
        """
    )

    conn.commit()
    _ensure_registration_columns(cur)

    seed_users = [
        ("RANJITHKUMAR ADMIN", generate_password_hash("RANJITH!1301"), "admin"),
    ]

    cur.execute("SELECT COUNT(*) AS count FROM users")
    if cur.fetchone()["count"] == 0:
        cur.executemany(
            "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
            seed_users,
        )
    else:
        for username, password, role in seed_users:
            cur.execute("SELECT id FROM users WHERE username = ?", (username,))
            if cur.fetchone() is None:
                cur.execute(
                    "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                    (username, password, role),
                )

    _ensure_password_hashes(cur)

    # Ensure users table has a status column
    cur.execute("PRAGMA table_info(users)")
    user_cols = {row["name"] for row in cur.fetchall()}
    if "status" not in user_cols:
        cur.execute("ALTER TABLE users ADD COLUMN status TEXT NOT NULL DEFAULT 'APPROVED'")
        conn.commit()

    cur.execute("SELECT COUNT(*) AS count FROM citizens")
    if cur.fetchone()["count"] == 0:
        cur.executemany(
            """
            INSERT INTO citizens (citizen_id, name, age, gender, address)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                (1001, "Lakshmi Narayanan", 67, "Female", "12 Temple Road, Madurai"),
                (1002, "Ravi Kumar", 72, "Male", "5 Main Street, Tirunelveli"),
                (1003, "Meena Devi", 64, "Female", "44 Hill View, Palani"),
            ],
        )

    conn.commit()
    conn.close()
