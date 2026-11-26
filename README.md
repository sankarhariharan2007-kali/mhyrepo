# SAUNA — Digital Game Store & Publisher Portal (Flask + PostgreSQL)

A full-stack **PostgreSQL** database and **Flask** web app built from [`steam_er_diagram.png`](steam_er_diagram.png).

## Database Schema (17 Tables)
Defined in [`sql/01_schema.sql`](sql/01_schema.sql), seeded by [`sql/02_seed.sql`](sql/02_seed.sql). The original MySQL version is kept in [`legacy_mysql/`](legacy_mysql/).

- **Catalog & Metadata**: `publishers`, `developers`, `games`, `tags`, `game_tags`
- **Users & Social**: `users`, `friendships` (PL/pgSQL trigger blocks self-friending)
- **Sales & Pricing**: `sales`, `sale_items`
- **Commerce & Wallet**: `orders`, `order_items`, `wallet_transactions`
- **Player Activity**: `user_library`, `wishlist`, `reviews`, `achievements`, `user_achievements`

## Key Features
- Three roles: **User**, **Publisher** and **Platform Admin**, with username / email / Member ID login.
- Rupee wallet with atomic purchases (`SELECT ... FOR UPDATE`), orders, line items, wallet ledger.
- Storefront with featured spotlight, sales, wishlist, library, achievements, reviews, friends.
- Publisher Studio: publish games, add discounts and achievements for your own catalog.
- Admin-only Data Explorer with a read-only SQL runner. Password hashes, wallet balances and wallet transaction amounts are masked.

## Running locally
```bash
pip install -r requirements.txt
createdb steam_db
export DATABASE_URL=postgresql://USER:PASS@127.0.0.1:5432/steam_db
python scripts/init_db.py      # creates tables, loads demo data if empty
python app.py                  # http://127.0.0.1:5050
```
Demo accounts (password `password123`). Pick the matching account type on the login screen.

| Account type | Username |
|---|---|
| User | `arjun_dev`, `elena_vance`, `kenji_k`, `marta_r`, `liam_os`, `sara_chen` |
| Publisher | `valve_pub`, `cdpr_pub`, `supergiant_pub` |
| Platform Admin | `admin` |

These passwords are public, so treat a deployment seeded with them as a demo only.

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
| `SAUNA_SECRET_KEY` | long random string, required on Render (`FERRO_SECRET_KEY` also works) |
| `SAUNA_COOKIE_SECURE` | `1` (`FERRO_COOKIE_SECURE` also works) |
| `ENABLE_SQL_EXPLORER` | `1` or `0` |
| `SEED_DEMO_DATA` | `1` first deploy; `0` afterwards if you want no demo data on a fresh DB |
| `RESET_DEMO_DATA` | `1` once, only to replace the old FERRO Y demo data. **Wipes all tables.** |
| `PYTHON_VERSION` | `3.12.7` |

On boot `scripts/init_db.py` creates missing tables, upgrades older ones and seeds demo data only when `users` is empty, so redeploys do not wipe data unless you set `RESET_DEMO_DATA=1` on an old FERRO Y database.
