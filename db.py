import os
from datetime import date, datetime
from decimal import Decimal

import psycopg2
from psycopg2.extras import RealDictCursor

# Preferred: one connection string (Render, Neon, Supabase, Aiven all provide one).
#   DATABASE_URL=postgresql://user:pass@host:5432/dbname?sslmode=require
# Fallback: discrete PG* variables for local development.


def get_connection():
    """Return a psycopg2 connection (dict rows, manual transactions)."""
    url = os.environ.get("DATABASE_URL")
    if url:
        if url.startswith("postgres://"):
            url = "postgresql://" + url[len("postgres://"):]
        conn = psycopg2.connect(url, cursor_factory=RealDictCursor, connect_timeout=10)
    else:
        conn = psycopg2.connect(
            host=os.environ.get("PGHOST", "127.0.0.1"),
            port=int(os.environ.get("PGPORT", "5432")),
            user=os.environ.get("PGUSER", "postgres"),
            password=os.environ.get("PGPASSWORD", ""),
            dbname=os.environ.get("PGDATABASE", "steam_db"),
            sslmode=os.environ.get("PGSSLMODE", "prefer"),
            cursor_factory=RealDictCursor,
            connect_timeout=10,
        )
    conn.autocommit = False
    return conn


def serialize_value(val):
    """Convert PostgreSQL/Python types into JSON-safe primitives."""
    if isinstance(val, Decimal):
        return float(val)
    if isinstance(val, datetime):
        return val.isoformat(sep=" ")
    if isinstance(val, date):
        return val.isoformat()
    if isinstance(val, (bytes, memoryview)):
        return bytes(val).decode("utf-8", errors="replace")
    return val


def serialize_row(row):
    if row is None:
        return None
    return {k: serialize_value(v) for k, v in row.items()}


def serialize_rows(rows):
    return [serialize_row(r) for r in rows]
