"""Idempotent PostgreSQL bootstrap for hosted deployments (Render, Neon, ...).

- Creates the 17 tables if missing and applies small upgrades (sql/01_schema.sql).
- Loads demo data (sql/02_seed.sql) ONLY if the users table is empty,
  so redeploys never wipe data. Set SEED_DEMO_DATA=0 to skip seeding.
- RESET_DEMO_DATA=1 replaces the OLD FERRO Y demo data with the SAUNA demo data.
  It wipes every table, and does nothing once the new data is in place.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from db import get_connection  # noqa: E402

TABLES = (
    "publishers, developers, games, users, friendships, orders, wallet_transactions, "
    "order_items, user_library, reviews, wishlist, sales, sale_items, achievements, "
    "user_achievements, tags, game_tags"
)
HOLIDAY_SALE = "SAUNA Early Christmas Sale 2026"


def run_file(cur, name):
    with open(os.path.join(ROOT, "sql", name), encoding="utf-8") as f:
        cur.execute(f.read())  # psycopg2 runs multi-statement scripts in one call


def has_old_demo_data(cur):
    cur.execute(
        "SELECT EXISTS (SELECT 1 FROM users WHERE email = 'arjun@ferroy.io') "
        "AND NOT EXISTS (SELECT 1 FROM users WHERE role = 'admin') AS old"
    )
    return cur.fetchone()["old"]


def apply_holiday_update(cur):
    """Add the holiday 2026 games, prices and sale to demo databases, once."""
    cur.execute(
        "SELECT EXISTS (SELECT 1 FROM users WHERE email = 'admin@sauna.io') "
        "AND NOT EXISTS (SELECT 1 FROM sales WHERE title = %s) AS due",
        (HOLIDAY_SALE,),
    )
    if cur.fetchone()["due"]:
        run_file(cur, "03_holiday_2026.sql")
        print("holiday 2026 update applied")


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
            elif not empty and has_old_demo_data(cur):
                if os.environ.get("RESET_DEMO_DATA") == "1":
                    cur.execute(f"TRUNCATE {TABLES} RESTART IDENTITY CASCADE")
                    run_file(cur, "02_seed.sql")
                    print("old demo data replaced with SAUNA demo data")
                else:
                    print(
                        "WARNING: old FERRO Y demo data found (no publisher or admin accounts). "
                        "Set RESET_DEMO_DATA=1 to wipe it and load the SAUNA demo data."
                    )
            else:
                print("seed skipped (users exist or SEED_DEMO_DATA=0)")
            apply_holiday_update(cur)
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    main()
