"""Idempotent PostgreSQL bootstrap for hosted deployments (Render, Neon, ...).

- Creates the 17 tables if missing (sql/01_schema.sql).
- Loads demo data (sql/02_seed.sql) ONLY if the users table is empty,
  so redeploys never wipe data. Set SEED_DEMO_DATA=0 to skip seeding.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from db import get_connection  # noqa: E402


def run_file(cur, name):
    with open(os.path.join(ROOT, "sql", name), encoding="utf-8") as f:
        cur.execute(f.read())  # psycopg2 runs multi-statement scripts in one call


def main():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # Serialise concurrent boots (multiple workers/instances).
            cur.execute("SELECT pg_advisory_xact_lock(727001)")
            run_file(cur, "01_schema.sql")
            print("schema ok")
            cur.execute("SELECT COUNT(*) AS c FROM users")
            empty = cur.fetchone()["c"] == 0
            if empty and os.environ.get("SEED_DEMO_DATA", "1") == "1":
                run_file(cur, "02_seed.sql")
                print("seed loaded")
            else:
                print("seed skipped (users exist or SEED_DEMO_DATA=0)")
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    main()
