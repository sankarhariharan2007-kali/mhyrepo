"""Idempotent database bootstrap for hosted deployments (Render, etc.).

- Creates the 17 tables if missing (sql/01_schema.sql).
- Loads demo data (sql/02_seed.sql) ONLY if the USERS table is empty,
  so redeploys never wipe production data.
- Handles `DELIMITER` blocks (trigger) that PyMySQL cannot parse natively.
Set SEED_DEMO_DATA=0 to skip seeding.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db import get_connection  # noqa: E402

SQL_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sql")


def split_statements(text):
    delim, buf, out = ";", [], []
    for line in text.splitlines():
        m = re.match(r"^\s*DELIMITER\s+(\S+)\s*$", line, re.I)
        if m:
            delim = m.group(1)
            continue
        if not buf and (not line.strip() or line.lstrip().startswith("--")):
            continue
        buf.append(line)
        if line.rstrip().endswith(delim):
            stmt = "\n".join(buf).rstrip()
            out.append(stmt[: -len(delim)].rstrip())
            buf = []
    if buf and "\n".join(buf).strip():
        out.append("\n".join(buf).strip())
    return out


def run_file(cur, name):
    with open(os.path.join(SQL_DIR, name), encoding="utf-8") as f:
        stmts = split_statements(f.read())
    for s in stmts:
        head = s.lstrip().split(None, 2)
        kw = " ".join(head[:2]).upper() if head else ""
        if kw == "CREATE DATABASE" or kw.startswith("USE"):
            continue  # the managed database/user already exists
        cur.execute(s)
    return len(stmts)


def main():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            n = run_file(cur, "01_schema.sql")
            conn.commit()
            print(f"schema ok ({n} statements)")
            cur.execute("SELECT COUNT(*) AS c FROM USERS")
            empty = cur.fetchone()["c"] == 0
            if empty and os.environ.get("SEED_DEMO_DATA", "1") == "1":
                n = run_file(cur, "02_seed.sql")
                conn.commit()
                print(f"seed loaded ({n} statements)")
            else:
                print("seed skipped (users exist or SEED_DEMO_DATA=0)")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
