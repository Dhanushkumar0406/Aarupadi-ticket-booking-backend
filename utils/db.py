import sqlite3
from config.config import DATABASE


def get_db_connection():
    """
    Create and return a SQLite connection.

    When SQLite connects to a file path that does not exist,
    it automatically creates the database file for us.
    """
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn
