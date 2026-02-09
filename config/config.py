import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _get_bool_env(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _get_int_env(name, default):
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


SECRET_KEY = os.getenv("SECRET_KEY", "change-this-to-a-strong-key")
DEBUG = _get_bool_env("FLASK_DEBUG", True)
DATABASE = os.getenv("DATABASE_PATH", os.path.join(BASE_DIR, "database.db"))
TOKEN_EXPIRES_MINUTES = _get_int_env("TOKEN_EXPIRES_MINUTES", 480)
