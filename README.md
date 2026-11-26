# FERRO Y — Game Store Platform (Flask + PostgreSQL)

A full-stack **PostgreSQL** database and **Flask** web app built from [`steam_er_diagram.png`](steam_er_diagram.png).

## Database Schema (17 Tables)
Defined in [`sql/01_schema.sql`](sql/01_schema.sql), seeded by [`sql/02_seed.sql`](sql/02_seed.sql). The original MySQL version is kept in [`legacy_mysql/`](legacy_mysql/).

- **Catalog & Metadata**: `publishers`, `developers`, `games`, `tags`, `game_tags`
- **Users & Social**: `users`, `friendships` (PL/pgSQL trigger blocks self-friending)
- **Sales & Pricing**: `sales`, `sale_items`
- **Commerce & Wallet**: `orders`, `order_items`, `wallet_transactions`
- **Player Activity**: `user_library`, `wishlist`, `reviews`, `achievements`, `user_achievements`

## Key Features
- Member ID / username / email + password login (scrypt hashes), registration, logout.
- Rupee wallet with atomic purchases (`SELECT ... FOR UPDATE`), orders, line items, wallet ledger.
- Storefront with seasonal sales, wishlist, library & playtime, achievements, reviews, friends.
- Admin-only catalog management and a read-only SQL explorer (enforced by a PostgreSQL read-only transaction).

## Running locally
```bash
pip install -r requirements.txt
createdb steam_db
export DATABASE_URL=postgresql://USER:PASS@127.0.0.1:5432/steam_db
python scripts/init_db.py      # creates tables, loads demo data if empty
python app.py                  # http://127.0.0.1:5050
```
Demo Member IDs `1`-`6`, password `password123`. Member `1` is the admin.

## Deploying to Render (no Docker)
1. Create a free PostgreSQL database (Render Postgres, Neon, Supabase, Aiven...) and copy its connection string.
2. Render: **New -> Web Service**, this repo, branch `main`, **Language: Python 3**.
   - Build: `pip install -r requirements.txt`
   - Start: `python scripts/init_db.py && gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --timeout 60`
   - Health check path: `/healthz`
3. Environment variables:

| Variable | Value |
|---|---|
| `DATABASE_URL` | your Postgres connection string (include `?sslmode=require` if the provider needs it) |
| `FERRO_SECRET_KEY` | long random string |
| `FERRO_COOKIE_SECURE` | `1` |
| `ADMIN_USER_IDS` | `1` (comma-separated member IDs) |
| `ENABLE_SQL_EXPLORER` | `1` or `0` |
| `SEED_DEMO_DATA` | `1` first deploy; `0` afterwards if you want no demo data on a fresh DB |
| `PYTHON_VERSION` | `3.12.7` |

On boot `scripts/init_db.py` creates missing tables and seeds demo data only when `users` is empty, so redeploys never wipe data. Change the demo passwords after the first login.
