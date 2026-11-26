import os
from datetime import date, datetime
from decimal import Decimal
import pymysql
from pymysql.cursors import DictCursor


DB_CONFIG = {
    "host": os.environ.get("MYSQL_HOST", "127.0.0.1"),
    "port": int(os.environ.get("MYSQL_PORT", "3306")),
    "user": os.environ.get("MYSQL_USER", "root"),
    "password": os.environ.get("MYSQL_PASSWORD", ""),
    "database": os.environ.get("MYSQL_DB", "steam_db"),
    "charset": "utf8mb4",
    "cursorclass": DictCursor,
    "autocommit": False,
}

SOCKET_PATH = os.environ.get(
    "MYSQL_UNIX_SOCKET",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "mysql_data", "mysql.sock"),
)


def get_connection():
    """Return a PyMySQL connection to steam_db."""
    cfg = dict(DB_CONFIG)
    if os.path.exists(SOCKET_PATH) and cfg["host"] in ("localhost", "127.0.0.1"):
        cfg["unix_socket"] = SOCKET_PATH
    return pymysql.connect(**cfg)


def serialize_value(val):
    """Convert MySQL/Python types into JSON-safe primitives."""
    if isinstance(val, Decimal):
        return float(val)
    if isinstance(val, (datetime, date)):
        return val.isoformat(sep=" ") if isinstance(val, datetime) else val.isoformat()
    if isinstance(val, bytes):
        return val.decode("utf-8", errors="replace")
    return val


def serialize_row(row):
    if row is None:
        return None
    return {k: serialize_value(v) for k, v in row.items()}


def serialize_rows(rows):
    return [serialize_row(r) for r in rows]
