# SAUNA — Digital Game Store & Publisher Portal (Flask + PostgreSQL)

A full-stack **PostgreSQL** database and **Flask** web app built from [`steam_er_diagram.png`](steam_er_diagram.png).

## Database Schema (19 Tables)
Defined in [`sql/01_schema.sql`](sql/01_schema.sql), seeded by [`sql/02_seed.sql`](sql/02_seed.sql); ER diagrams: [`sauna_er_diagram.png`](sauna_er_diagram.png), [`sauna_er_model.pdf`](sauna_er_model.pdf) (presentation: [`sauna_er_model.pptx`](sauna_er_model.pptx)). The original MySQL version is kept in [`legacy_mysql/`](legacy_mysql/).

- **Localization & Multi-Currency**: `currencies`, `regions`
- **Catalog & Metadata**: `publishers`, `developers`, `games`, `tags`, `game_tags`
- **Users & Social**: `users`, `friendships` (PL/pgSQL trigger blocks self-friending)
- **Sales & Pricing**: `sales`, `sale_items`
- **Commerce & Wallet**: `orders`, `order_items` (PL/pgSQL trigger `trg_order_items_steam_refund_policy`), `wallet_transactions`
- **Player Activity**: `user_library` (play/exit session timestamps), `wishlist`, `reviews`, `achievements`, `user_achievements`

## Key Features
- Three roles: **User**, **Publisher** and **Platform Admin**, with username / email / Member ID login (`scrypt` hashes).
- **Region-based multi-currency**: pick a country in the header (India ₹, Japan ¥, USA $, UK £, Poland zł, Canada CA$, Australia A$, Germany/France €). Money is stored in INR; orders and wallet transactions snapshot the currency and exchange rate used.
- Atomic wallet purchases (`SELECT ... FOR UPDATE`), orders, line items, wallet ledger.
- **Steam 2-hour refund policy**: paid games can be refunded if played under 120 minutes and bought within 14 days. Enforced in Flask and in the database trigger.
- **Play tracking**: Play / Exit sessions accumulate playtime in the library.
- Storefront with featured spotlight, sales, wishlist, library, achievements, reviews, friends.
- Publisher Studio: publish games, add discounts and achievements for your own catalog.
- Admin-only Data Explorer with a read-only SQL runner. Password hashes, wallet balances and wallet transaction amounts are masked.

## UPI payments
Choosing **UPI** in the cart (amount always shown in INR) shows [`static/images/upi_qr.png`](static/images/upi_qr.png), and the payer types the amount shown. To change the account, replace the image and `UPI_LINK` in `static/js/app.js`. There is no payment gateway, so payments are **not verified**: no order is created and no games are added. Wallet checkout is unchanged.

## Holiday 2026 update
[`sql/03_holiday_2026.sql`](sql/03_holiday_2026.sql) is applied once on boot to a database holding the demo data. It sets regular rupee prices (looked up 26 November 2026; they do not update by themselves), adds 12 games (24 in all) and starts the **Early Christmas Sale** (26 November to 31 December 2026, IST). The Christmas theme shows only while a sale with "Christmas" in its title is active.

## Season End Sale: F1 25
[`sql/05_f1_season_end_sale.sql`](sql/05_f1_season_end_sale.sql) is applied once on boot, after the holiday update. It adds **F1 25** (₹4,999) and the **SAUNA Season End Sale 2026**, 27 November to 31 December 2026 (IST), which gives **85% off F1 25 only**. The price does not update by itself.

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
**One click:** Render -> **New -> Blueprint**, pick this repo. [`render.yaml`](render.yaml) creates the web service and a Postgres database and wires `DATABASE_URL` and a generated `SAUNA_SECRET_KEY`. (Render's free Postgres expires after 30 days; upgrade or point `DATABASE_URL` at Neon/Supabase for a permanent demo.)

**Manual setup:**
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
