import os
import re
from contextlib import contextmanager
from decimal import Decimal, ROUND_HALF_UP
from flask import Flask, jsonify, render_template, request, session
from werkzeug.security import check_password_hash, generate_password_hash
import psycopg2
import psycopg2.errors

from db import get_connection, serialize_row, serialize_rows

app = Flask(__name__)
_secret = os.environ.get("SAUNA_SECRET_KEY") or os.environ.get("FERRO_SECRET_KEY")
if not _secret and os.environ.get("RENDER"):
    # With a public default key anyone could forge an admin session cookie.
    raise RuntimeError("Set SAUNA_SECRET_KEY to a long random string in the Environment page.")
app.secret_key = _secret or "sauna-local-dev-only"
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=(
        os.environ.get("SAUNA_COOKIE_SECURE") or os.environ.get("FERRO_COOKIE_SECURE")
    ) == "1",
)
ENABLE_SQL_EXPLORER = os.environ.get("ENABLE_SQL_EXPLORER", "1") == "1"
app.config["TEMPLATES_AUTO_RELOAD"] = True

ALLOWED_TABLES = {
    "currencies",
    "regions",
    "publishers",
    "developers",
    "games",
    "users",
    "friendships",
    "orders",
    "wallet_transactions",
    "order_items",
    "user_library",
    "reviews",
    "wishlist",
    "sales",
    "sale_items",
    "achievements",
    "user_achievements",
    "tags",
    "game_tags",
}

REFUND_MAX_PLAYTIME_MINUTES = 120
REFUND_MAX_DAYS = 14
REFUND_MAX_SECONDS = REFUND_MAX_DAYS * 86400


@contextmanager
def db_cursor(commit=False):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            yield conn, cur
        if commit:
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _error(message, status=400):
    return jsonify({"error": message}), status


def _require_auth(expected_user_id=None):
    uid = session.get("user_id")
    if not uid:
        return None, _error("Please log in to continue.", 401)
    if expected_user_id is not None and int(uid) != int(expected_user_id):
        return None, _error("Forbidden: you can only access your own account.", 403)
    return int(uid), None


def _require_publisher():
    uid = session.get("user_id")
    role = session.get("role")
    pub_id = session.get("publisher_id")
    if not uid:
        return None, None, _error("Please log in as a Publisher to continue.", 401)
    if role != "publisher" or not pub_id:
        return None, None, _error("Publisher account required for this action.", 403)
    return int(uid), int(pub_id), None


def _require_admin():
    uid = session.get("user_id")
    role = session.get("role")
    if not uid:
        return None, _error("Platform Admin login required.", 401)
    if role != "admin":
        return None, _error("Forbidden: only Platform Admin can access Data Explorer.", 403)
    return int(uid), None


def _compute_effective_price(base_price, discount_pct):
    base = Decimal(str(base_price))
    if not discount_pct:
        return round(float(base), 2)
    discounted = base * (Decimal("100") - Decimal(str(discount_pct))) / Decimal("100")
    return round(float(discounted), 2)


def _convert_from_inr(amount_inr, rate_from_inr, minor_units=2):
    amt = Decimal(str(amount_inr or 0))
    rate = Decimal(str(rate_from_inr or 1))
    units = int(minor_units or 0)
    quant = Decimal("1") if units == 0 else Decimal("1").scaleb(-units)
    return (amt * rate).quantize(quant, rounding=ROUND_HALF_UP)


def _convert_to_inr(display_amount, rate_from_inr):
    amt = Decimal(str(display_amount or 0))
    rate = Decimal(str(rate_from_inr or 1))
    return (amt / rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _format_currency_text(display_amount, symbol, minor_units=2):
    units = int(minor_units or 0)
    val = float(display_amount or 0)
    if units == 0:
        return f"{symbol}{round(val):,}"
    return f"{symbol}{val:,.{units}f}"


def _region_select_sql():
    return (
        "SELECT r.region_id, r.country_name, r.country_code, r.currency_code, "
        "c.name AS currency_name, c.symbol, c.minor_units, c.rate_from_inr "
        "FROM REGIONS r JOIN CURRENCIES c ON c.currency_code = r.currency_code "
    )


def _resolve_region(cur, region_id=None, country_name=None):
    base_sql = _region_select_sql()
    row = None
    if region_id:
        cur.execute(base_sql + "WHERE r.region_id = %s", (int(region_id),))
        row = cur.fetchone()
    if not row and country_name:
        cur.execute(base_sql + "WHERE LOWER(r.country_name) = LOWER(%s)", (country_name.strip(),))
        row = cur.fetchone()
    if not row:
        cur.execute(base_sql + "WHERE r.currency_code = 'INR' ORDER BY r.region_id ASC LIMIT 1")
        row = cur.fetchone()
    if not row:
        return {
            "region_id": 1,
            "country_name": "India",
            "country_code": "IN",
            "currency_code": "INR",
            "currency_name": "Indian Rupee",
            "symbol": "₹",
            "minor_units": 2,
            "rate_from_inr": 1.0,
        }
    return serialize_row(row)


def _resolve_active_region(cur):
    sess_rid = session.get("region_id")
    if sess_rid:
        return _resolve_region(cur, region_id=sess_rid)
    uid = session.get("user_id")
    if uid:
        cur.execute("SELECT region_id, country FROM USERS WHERE user_id = %s", (int(uid),))
        u = cur.fetchone()
        if u:
            reg = _resolve_region(cur, region_id=u.get("region_id"), country_name=u.get("country"))
            session["region_id"] = int(reg["region_id"])
            return reg
    return _resolve_region(cur)


def _evaluate_refund_eligibility(playtime_minutes, price_at_purchase, seconds_since_purchase):
    """Evaluate Steam 2-hour (<120m) & 14-day refund eligibility."""
    playtime = int(playtime_minutes or 0)
    price = float(price_at_purchase or 0)
    if price <= 0 or seconds_since_purchase is None:
        return {
            "refund_eligible": False,
            "refundable_amount": 0.0,
            "refund_minutes_remaining": 0,
            "refund_days_remaining": 0,
            "refund_status_text": "Free license (no paid purchase)",
        }

    elapsed_sec = max(0, int(seconds_since_purchase))
    mins_left = max(0, REFUND_MAX_PLAYTIME_MINUTES - playtime)
    secs_left = max(0, REFUND_MAX_SECONDS - elapsed_sec)
    days_left = secs_left // 86400

    if playtime >= REFUND_MAX_PLAYTIME_MINUTES:
        return {
            "refund_eligible": False,
            "refundable_amount": round(price, 2),
            "refund_minutes_remaining": 0,
            "refund_days_remaining": days_left,
            "refund_status_text": f"Ineligible · {playtime}m played (2-hour / 120m limit reached)",
        }

    if elapsed_sec > REFUND_MAX_SECONDS:
        days_ago = elapsed_sec // 86400
        return {
            "refund_eligible": False,
            "refundable_amount": round(price, 2),
            "refund_minutes_remaining": mins_left,
            "refund_days_remaining": 0,
            "refund_status_text": f"Ineligible · Purchased {days_ago}d ago (14-day limit exceeded)",
        }

    window_label = f"{days_left}d left" if days_left >= 1 else "<1d left"
    return {
        "refund_eligible": True,
        "refundable_amount": round(price, 2),
        "refund_minutes_remaining": mins_left,
        "refund_days_remaining": days_left,
        "refund_status_text": f"Eligible · {playtime}m / 120m played · {window_label}",
    }


def _active_discount_subquery():
    return """
        SELECT DISTINCT ON (si.game_id)
               si.game_id, si.discount_pct, s.title AS sale_title
        FROM sale_items si
        JOIN sales s ON s.sale_id = si.sale_id
        WHERE NOW() BETWEEN s.start_date AND s.end_date
        ORDER BY si.game_id, si.discount_pct DESC
    """


@app.errorhandler(psycopg2.Error)
def handle_db_error(err):
    diag = getattr(err, "diag", None)
    msg = (diag.message_primary if diag and diag.message_primary else str(err)).strip()
    if isinstance(err, psycopg2.errors.UniqueViolation):
        msg = "That value already exists (duplicate)."
    elif isinstance(err, psycopg2.errors.ForeignKeyViolation):
        msg = "Referenced record does not exist or is still in use."
    elif isinstance(err, psycopg2.errors.CheckViolation):
        msg = "A value violates a data constraint."
    status = 503 if isinstance(err, psycopg2.OperationalError) else 400
    return jsonify({"error": f"Database error: {msg}"}), status


@app.route("/healthz")
def healthz():
    with db_cursor() as (_, cur):
        cur.execute("SELECT 1 AS ok")
        cur.fetchone()
    return jsonify({"status": "ok"})


@app.route("/")
def index():
    return render_template("index.html")


# ---------------------------------------------------------------------------
# Authentication (User & Publisher Login / Register / Logout)
# ---------------------------------------------------------------------------
@app.route("/api/auth/login", methods=["POST"])
def auth_login():
    data = request.get_json(force=True) or {}
    identifier = str(data.get("identifier") or data.get("user_id") or "").strip()
    password = data.get("password") or ""
    account_type = (data.get("account_type") or "user").strip().lower()
    if account_type not in ("user", "publisher", "admin"):
        return _error("Account type must be 'user', 'publisher', or 'admin'.")
    if not identifier or not password:
        return _error("Username (or Member ID) and password are required.")

    with db_cursor() as (_, cur):
        base_sql = (
            "SELECT u.*, p.name AS publisher_name FROM USERS u "
            "LEFT JOIN PUBLISHERS p ON p.publisher_id = u.publisher_id "
        )
        if identifier.isdigit():
            cur.execute(base_sql + "WHERE u.user_id = %s", (int(identifier),))
        else:
            cur.execute(
                base_sql + "WHERE u.username = %s OR u.email = %s",
                (identifier, identifier),
            )
        user = cur.fetchone()
        if not user or not check_password_hash(user["password_hash"], password):
            return _error("Invalid credentials or password.", 401)

        if user["role"] != account_type:
            role_labels = {"user": "User", "publisher": "Publisher", "admin": "Platform Admin"}
            expected_label = role_labels.get(user["role"], user["role"])
            return _error(
                f"This account is registered as {expected_label}. Please choose '{expected_label}' to log in.",
                403,
            )

        session["user_id"] = int(user["user_id"])
        session["role"] = user["role"]
        session["publisher_id"] = int(user["publisher_id"]) if user["publisher_id"] else None
        region = _resolve_region(cur, region_id=user.get("region_id"), country_name=user.get("country"))
        session["region_id"] = int(region["region_id"])
        return jsonify({
            "authenticated": True,
            "user_id": int(user["user_id"]),
            "username": user["username"],
            "role": user["role"],
            "publisher_id": session["publisher_id"],
            "publisher_name": user["publisher_name"],
            "wallet_balance": float(user["wallet_balance"]),
            "country": region["country_name"],
            "region_id": int(region["region_id"]),
            "active_region": region,
        })


@app.route("/api/auth/register", methods=["POST"])
def auth_register():
    data = request.get_json(force=True) or {}
    account_type = (data.get("account_type") or "user").strip().lower()
    if account_type not in ("user", "publisher"):
        return _error("Account type must be 'user' or 'publisher'.")

    username = (data.get("username") or "").strip()
    email = (data.get("email") or "").strip()
    password = data.get("password") or ""
    region_id_req = data.get("region_id")
    country_req = (data.get("country") or "").strip()

    if not username or not email or not password:
        return _error("Username, email, and password are required.")
    if len(password) < 4:
        return _error("Password must be at least 4 characters.")

    pw_hash = generate_password_hash(password)
    with db_cursor(commit=True) as (_, cur):
        region = _resolve_region(cur, region_id=region_id_req, country_name=country_req or "India")
        country = region["country_name"]
        region_id = int(region["region_id"])
        rate = Decimal(str(region["rate_from_inr"]))
        minor_units = int(region["minor_units"])
        curr_code = region["currency_code"]

        publisher_id = None
        publisher_name = None
        wallet_inr = Decimal("0.00")
        display_wallet = Decimal("0.00")

        if account_type == "publisher":
            publisher_name = (data.get("publisher_name") or "").strip()
            if not publisher_name:
                return _error("Publisher / Studio Name is required for Publisher registration.")
            founded_year = data.get("founded_year") or None
            website = (data.get("website") or "").strip() or None
            cur.execute("SELECT 1 FROM PUBLISHERS WHERE LOWER(name) = LOWER(%s)", (publisher_name,))
            if cur.fetchone():
                return _error("A studio with this name already exists. Choose a different studio name.", 409)
            cur.execute(
                "INSERT INTO PUBLISHERS (name, country, founded_year, website) "
                "VALUES (%s, %s, %s, %s) RETURNING publisher_id",
                (publisher_name, country, founded_year, website),
            )
            publisher_id = cur.fetchone()["publisher_id"]
        else:
            raw_wallet = Decimal(str(data.get("wallet_balance") or 0))
            if raw_wallet < 0:
                return _error("Initial wallet balance cannot be negative.")
            if data.get("input_in_active_currency"):
                display_wallet = raw_wallet
                wallet_inr = _convert_to_inr(raw_wallet, rate)
            else:
                wallet_inr = raw_wallet.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                display_wallet = _convert_from_inr(wallet_inr, rate, minor_units)

        cur.execute(
            "INSERT INTO USERS (username, email, password_hash, role, publisher_id, wallet_balance, country, region_id) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING user_id",
            (username, email, pw_hash, account_type, publisher_id, wallet_inr, country, region_id),
        )
        user_id = cur.fetchone()["user_id"]
        if account_type == "user" and wallet_inr > 0:
            cur.execute(
                "INSERT INTO WALLET_TRANSACTIONS "
                "(user_id, amount, currency_code, exchange_rate_used, display_amount, txn_type, reference_order_id) "
                "VALUES (%s, %s, %s, %s, %s, 'deposit', NULL)",
                (user_id, wallet_inr, curr_code, rate, display_wallet),
            )

        session["user_id"] = int(user_id)
        session["role"] = account_type
        session["publisher_id"] = int(publisher_id) if publisher_id else None
        session["region_id"] = region_id
        return jsonify({
            "authenticated": True,
            "user_id": int(user_id),
            "username": username,
            "role": account_type,
            "publisher_id": session["publisher_id"],
            "publisher_name": publisher_name,
            "wallet_balance": float(wallet_inr),
            "country": country,
            "region_id": region_id,
            "active_region": region,
        }), 201


@app.route("/api/auth/region", methods=["PUT"])
def set_active_region():
    data = request.get_json(force=True) or {}
    region_id = data.get("region_id")
    if not region_id:
        return _error("region_id is required.")
    with db_cursor(commit=True) as (_, cur):
        cur.execute(_region_select_sql() + "WHERE r.region_id = %s", (int(region_id),))
        row = cur.fetchone()
        if not row:
            return _error("Unknown region.", 404)
        region = serialize_row(row)
        session["region_id"] = int(region["region_id"])
        uid = session.get("user_id")
        if uid:
            cur.execute(
                "UPDATE USERS SET region_id = %s, country = %s WHERE user_id = %s",
                (int(region["region_id"]), region["country_name"], int(uid)),
            )
        return jsonify({"active_region": region})


@app.route("/api/auth/logout", methods=["POST"])
def auth_logout():
    session.clear()
    return jsonify({"authenticated": False, "logged_out": True})


@app.route("/api/auth/me", methods=["GET"])
def auth_me():
    uid = session.get("user_id")
    with db_cursor() as (_, cur):
        if not uid:
            return jsonify({"authenticated": False, "user": None, "active_region": _resolve_active_region(cur)})

        cur.execute(
            "SELECT u.user_id, u.username, u.role, u.publisher_id, p.name AS publisher_name, "
            "u.wallet_balance, u.country, u.region_id, u.created_at "
            "FROM USERS u LEFT JOIN PUBLISHERS p ON p.publisher_id = u.publisher_id "
            "WHERE u.user_id = %s",
            (int(uid),),
        )
        user = cur.fetchone()
        if not user:
            session.clear()
            return jsonify({"authenticated": False, "user": None, "active_region": _resolve_active_region(cur)})

        session["role"] = user["role"]
        session["publisher_id"] = int(user["publisher_id"]) if user["publisher_id"] else None
        active_region = _resolve_active_region(cur)

        cur.execute(
            "SELECT COUNT(*) AS owned_games, COALESCE(SUM(playtime_minutes), 0) AS total_playtime "
            "FROM USER_LIBRARY WHERE user_id = %s",
            (int(uid),),
        )
        lib = cur.fetchone()
        cur.execute("SELECT COUNT(*) AS wishlist_count FROM WISHLIST WHERE user_id = %s", (int(uid),))
        wish = cur.fetchone()
        cur.execute(
            "SELECT COUNT(*) AS friend_count FROM FRIENDSHIPS "
            "WHERE status = 'accepted' AND (user_id = %s OR friend_id = %s)",
            (int(uid), int(uid)),
        )
        friends = cur.fetchone()
        cur.execute(
            "SELECT COUNT(*) AS unlocked_achievements FROM USER_ACHIEVEMENTS WHERE user_id = %s",
            (int(uid),),
        )
        ach = cur.fetchone()

        published_games = 0
        if user["role"] == "publisher" and user["publisher_id"]:
            cur.execute(
                "SELECT COUNT(*) AS cnt FROM GAMES WHERE publisher_id = %s",
                (int(user["publisher_id"]),),
            )
            published_games = int(cur.fetchone()["cnt"])

        admin_stats = {}
        if user["role"] == "admin":
            cur.execute("SELECT COUNT(*) AS cnt FROM USERS")
            total_users = int(cur.fetchone()["cnt"])
            cur.execute("SELECT COUNT(*) AS cnt FROM GAMES")
            total_games = int(cur.fetchone()["cnt"])
            cur.execute("SELECT COUNT(*) AS cnt FROM ORDERS")
            total_orders = int(cur.fetchone()["cnt"])
            admin_stats = {
                "total_tables": len(ALLOWED_TABLES),
                "total_users": total_users,
                "total_games": total_games,
                "total_orders": total_orders,
            }

        return jsonify({
            "authenticated": True,
            "user": serialize_row(user),
            "active_region": active_region,
            "stats": {
                "owned_games": int(lib["owned_games"]),
                "total_playtime_minutes": int(lib["total_playtime"]),
                "wishlist_count": int(wish["wishlist_count"]),
                "friend_count": int(friends["friend_count"]),
                "unlocked_achievements": int(ach["unlocked_achievements"]),
                "published_games": published_games,
                **admin_stats,
            },
        })


# ---------------------------------------------------------------------------
# Users & Profile (Protected: only logged-in user)
# ---------------------------------------------------------------------------
@app.route("/api/users/<int:user_id>/summary", methods=["GET"])
def user_summary(user_id):
    uid, err = _require_auth(user_id)
    if err:
        return err
    return auth_me()


# ---------------------------------------------------------------------------
# Games Catalog & Storefront
# ---------------------------------------------------------------------------
@app.route("/api/games", methods=["GET"])
def list_games():
    q = (request.args.get("q") or "").strip()
    tag_id = request.args.get("tag_id", type=int)
    publisher_id = request.args.get("publisher_id", type=int)
    developer_id = request.args.get("developer_id", type=int)
    on_sale = request.args.get("on_sale") == "1"
    user_id = session.get("user_id")

    conditions = []
    params = []
    if q:
        conditions.append("(g.title ILIKE %s OR g.description ILIKE %s)")
        like = f"%{q}%"
        params.extend([like, like])
    if tag_id:
        conditions.append("EXISTS (SELECT 1 FROM GAME_TAGS gt2 WHERE gt2.game_id = g.game_id AND gt2.tag_id = %s)")
        params.append(tag_id)
    if publisher_id:
        conditions.append("g.publisher_id = %s")
        params.append(publisher_id)
    if developer_id:
        conditions.append("g.developer_id = %s")
        params.append(developer_id)
    if on_sale:
        conditions.append("sd.discount_pct IS NOT NULL")

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    sql = f"""
        SELECT
            g.game_id, g.title, g.description, g.release_date, g.base_price,
            g.publisher_id, p.name AS publisher_name,
            g.developer_id, d.name AS developer_name,
            g.age_rating,
            sd.discount_pct,
            sd.sale_title,
            COALESCE(rev.review_count, 0) AS review_count,
            COALESCE(rev.positive_count, 0) AS positive_count,
            COALESCE(ach.ach_count, 0) AS achievement_count
        FROM GAMES g
        JOIN PUBLISHERS p ON p.publisher_id = g.publisher_id
        JOIN DEVELOPERS d ON d.developer_id = g.developer_id
        LEFT JOIN ({_active_discount_subquery()}) sd ON sd.game_id = g.game_id
        LEFT JOIN (
            SELECT game_id, COUNT(*) AS review_count,
                   SUM(CASE WHEN is_recommended THEN 1 ELSE 0 END) AS positive_count
            FROM REVIEWS
            GROUP BY game_id
        ) rev ON rev.game_id = g.game_id
        LEFT JOIN (
            SELECT game_id, COUNT(*) AS ach_count
            FROM ACHIEVEMENTS
            GROUP BY game_id
        ) ach ON ach.game_id = g.game_id
        {where_clause}
        ORDER BY g.game_id DESC
    """

    with db_cursor() as (_, cur):
        cur.execute(sql, params)
        games = serialize_rows(cur.fetchall())

        cur.execute(
            "SELECT gt.game_id, t.tag_id, t.name "
            "FROM GAME_TAGS gt JOIN TAGS t ON t.tag_id = gt.tag_id ORDER BY t.name"
        )
        tags_by_game = {}
        for row in cur.fetchall():
            tags_by_game.setdefault(row["game_id"], []).append(
                {"tag_id": row["tag_id"], "name": row["name"]}
            )

        owned_set, wish_set = set(), set()
        if user_id:
            cur.execute("SELECT game_id FROM USER_LIBRARY WHERE user_id = %s", (int(user_id),))
            owned_set = {r["game_id"] for r in cur.fetchall()}
            cur.execute("SELECT game_id FROM WISHLIST WHERE user_id = %s", (int(user_id),))
            wish_set = {r["game_id"] for r in cur.fetchall()}

        for g in games:
            gid = g["game_id"]
            g["tags"] = tags_by_game.get(gid, [])
            g["discount_pct"] = int(g["discount_pct"]) if g["discount_pct"] else 0
            g["effective_price"] = _compute_effective_price(g["base_price"], g["discount_pct"])
            g["owned"] = gid in owned_set
            g["wishlisted"] = gid in wish_set
            rc = int(g["review_count"])
            pc = int(g["positive_count"])
            g["positive_pct"] = round((pc / rc) * 100) if rc > 0 else None

        return jsonify(games)


@app.route("/api/games/<int:game_id>", methods=["GET"])
def get_game_detail(game_id):
    user_id = session.get("user_id")
    with db_cursor() as (_, cur):
        cur.execute(
            f"""
            SELECT g.*, p.name AS publisher_name, p.website AS publisher_website,
                   d.name AS developer_name, d.website AS developer_website,
                   sd.discount_pct, sd.sale_title
            FROM GAMES g
            JOIN PUBLISHERS p ON p.publisher_id = g.publisher_id
            JOIN DEVELOPERS d ON d.developer_id = g.developer_id
            LEFT JOIN ({_active_discount_subquery()}) sd ON sd.game_id = g.game_id
            WHERE g.game_id = %s
            """,
            (game_id,),
        )
        game = serialize_row(cur.fetchone())
        if not game:
            return _error("Game not found.", 404)

        game["discount_pct"] = int(game["discount_pct"]) if game["discount_pct"] else 0
        game["effective_price"] = _compute_effective_price(game["base_price"], game["discount_pct"])

        cur.execute(
            "SELECT t.tag_id, t.name FROM GAME_TAGS gt JOIN TAGS t ON t.tag_id = gt.tag_id "
            "WHERE gt.game_id = %s ORDER BY t.name",
            (game_id,),
        )
        game["tags"] = serialize_rows(cur.fetchall())

        cur.execute(
            "SELECT r.*, u.username, u.country FROM REVIEWS r "
            "JOIN USERS u ON u.user_id = r.user_id "
            "WHERE r.game_id = %s ORDER BY r.helpful_votes DESC, r.created_at DESC",
            (game_id,),
        )
        game["reviews"] = serialize_rows(cur.fetchall())

        cur.execute(
            "SELECT a.*, CASE WHEN ua.user_id IS NOT NULL THEN 1 ELSE 0 END AS unlocked, ua.unlocked_at "
            "FROM ACHIEVEMENTS a "
            "LEFT JOIN USER_ACHIEVEMENTS ua ON ua.achievement_id = a.achievement_id AND ua.user_id = %s "
            "WHERE a.game_id = %s ORDER BY a.achievement_id ASC",
            (int(user_id) if user_id else -1, game_id),
        )
        game["achievements"] = serialize_rows(cur.fetchall())

        game["owned"] = False
        game["wishlisted"] = False
        game["refund_info"] = None
        if user_id:
            cur.execute(
                "SELECT playtime_minutes, active_session_started_at FROM USER_LIBRARY WHERE user_id = %s AND game_id = %s",
                (int(user_id), game_id),
            )
            lib_row = cur.fetchone()
            game["owned"] = lib_row is not None
            if lib_row is not None:
                cur.execute(
                    """
                    SELECT oi.order_id, oi.order_item_id, oi.price_at_purchase,
                           o.created_at AS purchased_at,
                           EXTRACT(EPOCH FROM (NOW() - o.created_at))::bigint AS seconds_since_purchase
                    FROM ORDER_ITEMS oi
                    JOIN ORDERS o ON o.order_id = oi.order_id
                    WHERE o.user_id = %s AND oi.game_id = %s AND oi.status = 'purchased'
                    ORDER BY o.created_at DESC, oi.order_item_id DESC
                    LIMIT 1
                    """,
                    (int(user_id), game_id),
                )
                oi_row = cur.fetchone()
                refund_meta = _evaluate_refund_eligibility(
                    lib_row["playtime_minutes"],
                    oi_row["price_at_purchase"] if oi_row else 0,
                    oi_row["seconds_since_purchase"] if oi_row else None,
                )
                if lib_row["active_session_started_at"] is not None:
                    refund_meta["refund_eligible"] = False
                    refund_meta["refund_status_text"] = "Session running · Exit game before refunding"
                game["refund_info"] = {
                    **refund_meta,
                    "playtime_minutes": int(lib_row["playtime_minutes"]),
                    "order_id": int(oi_row["order_id"]) if oi_row else None,
                    "purchased_at": serialize_row(oi_row)["purchased_at"] if oi_row else None,
                }
            cur.execute(
                "SELECT 1 FROM WISHLIST WHERE user_id = %s AND game_id = %s",
                (int(user_id), game_id),
            )
            game["wishlisted"] = cur.fetchone() is not None

        return jsonify(game)


@app.route("/api/publisher/games", methods=["GET"])
def publisher_games():
    _, pub_id, err = _require_publisher()
    if err:
        return err
    with db_cursor() as (_, cur):
        cur.execute(
            f"""
            SELECT g.*, d.name AS developer_name, sd.discount_pct, sd.sale_title,
                   (SELECT COUNT(*) FROM USER_LIBRARY ul WHERE ul.game_id = g.game_id) AS owners_count,
                   (SELECT COUNT(*) FROM ACHIEVEMENTS a WHERE a.game_id = g.game_id) AS achievement_count
            FROM GAMES g
            JOIN DEVELOPERS d ON d.developer_id = g.developer_id
            LEFT JOIN ({_active_discount_subquery()}) sd ON sd.game_id = g.game_id
            WHERE g.publisher_id = %s
            ORDER BY g.game_id DESC
            """,
            (pub_id,),
        )
        rows = serialize_rows(cur.fetchall())
        for r in rows:
            r["discount_pct"] = int(r["discount_pct"]) if r["discount_pct"] else 0
            r["effective_price"] = _compute_effective_price(r["base_price"], r["discount_pct"])
        return jsonify(rows)


@app.route("/api/games", methods=["POST"])
def create_game():
    _, pub_id, err = _require_publisher()
    if err:
        return err
    data = request.get_json(force=True) or {}
    title = (data.get("title") or "").strip()
    if not title:
        return _error("Game title is required.")
    developer_id = data.get("developer_id")
    if not developer_id:
        return _error("Developer is required.")

    base_price = float(data.get("base_price") or 0)
    if base_price < 0:
        return _error("Base price cannot be negative.")

    tag_ids = data.get("tag_ids") or []
    with db_cursor(commit=True) as (_, cur):
        cur.execute(
            "INSERT INTO GAMES (title, description, release_date, base_price, publisher_id, developer_id, age_rating) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING game_id",
            (
                title,
                data.get("description") or "",
                data.get("release_date") or None,
                base_price,
                pub_id,
                int(developer_id),
                data.get("age_rating") or "Everyone",
            ),
        )
        game_id = cur.fetchone()["game_id"]
        for tid in tag_ids:
            cur.execute("INSERT INTO GAME_TAGS (game_id, tag_id) VALUES (%s, %s) ON CONFLICT DO NOTHING", (game_id, int(tid)))
        cur.execute("SELECT * FROM GAMES WHERE game_id = %s", (game_id,))
        return jsonify(serialize_row(cur.fetchone())), 201


@app.route("/api/games/<int:game_id>", methods=["DELETE"])
def delete_game(game_id):
    _, pub_id, err = _require_publisher()
    if err:
        return err
    with db_cursor(commit=True) as (_, cur):
        cur.execute("DELETE FROM GAMES WHERE game_id = %s AND publisher_id = %s", (game_id, pub_id))
        if cur.rowcount == 0:
            return _error("Game not found or belongs to another publisher.", 404)
        return jsonify({"deleted": game_id})


# ---------------------------------------------------------------------------
# Library & Achievements
# ---------------------------------------------------------------------------
@app.route("/api/users/<int:user_id>/library", methods=["GET"])
def user_library(user_id):
    uid, err = _require_auth(user_id)
    if err:
        return err
    with db_cursor() as (_, cur):
        cur.execute(
            """
            SELECT ul.user_id, ul.game_id, ul.acquired_at,
                   ul.playtime_minutes, ul.playtime_seconds, ul.last_played_at,
                   ul.active_session_started_at,
                   EXTRACT(EPOCH FROM (NOW() - ul.active_session_started_at))::bigint AS active_session_elapsed_seconds,
                   ul.last_session_started_at, ul.last_session_ended_at, ul.last_session_seconds,
                   g.title, g.description, g.age_rating, p.name AS publisher_name, d.name AS developer_name,
                   latest_oi.order_id, latest_oi.order_item_id, latest_oi.price_at_purchase,
                   latest_oi.purchased_at, latest_oi.seconds_since_purchase,
                   (SELECT COUNT(*) FROM ACHIEVEMENTS a WHERE a.game_id = g.game_id) AS total_achievements,
                   (SELECT COUNT(*) FROM USER_ACHIEVEMENTS ua
                    JOIN ACHIEVEMENTS a ON a.achievement_id = ua.achievement_id
                    WHERE ua.user_id = ul.user_id AND a.game_id = g.game_id) AS unlocked_achievements
            FROM USER_LIBRARY ul
            JOIN GAMES g ON g.game_id = ul.game_id
            JOIN PUBLISHERS p ON p.publisher_id = g.publisher_id
            JOIN DEVELOPERS d ON d.developer_id = g.developer_id
            LEFT JOIN (
                SELECT oi.order_item_id, oi.order_id, oi.game_id, oi.price_at_purchase,
                       o.created_at AS purchased_at,
                       EXTRACT(EPOCH FROM (NOW() - o.created_at))::bigint AS seconds_since_purchase,
                       ROW_NUMBER() OVER (
                           PARTITION BY o.user_id, oi.game_id
                           ORDER BY o.created_at DESC, oi.order_item_id DESC
                       ) AS rn
                FROM ORDER_ITEMS oi
                JOIN ORDERS o ON o.order_id = oi.order_id
                WHERE o.user_id = %s AND oi.status = 'purchased'
            ) latest_oi ON latest_oi.game_id = ul.game_id AND latest_oi.rn = 1
            WHERE ul.user_id = %s
            ORDER BY (ul.active_session_started_at IS NOT NULL) DESC,
                     ul.last_played_at DESC NULLS LAST, ul.acquired_at DESC
            """,
            (uid, uid),
        )
        rows = serialize_rows(cur.fetchall())
        for r in rows:
            r["playtime_seconds"] = max(int(r.get("playtime_seconds") or 0), int(r.get("playtime_minutes") or 0) * 60)
            r.update(
                _evaluate_refund_eligibility(
                    r.get("playtime_minutes"),
                    r.get("price_at_purchase"),
                    r.get("seconds_since_purchase"),
                )
            )
            if r.get("active_session_started_at"):
                r["refund_eligible"] = False
                r["refund_status_text"] = "Session running · Exit game before refunding"
        return jsonify(rows)


@app.route("/api/users/<int:user_id>/library/<int:game_id>/play/start", methods=["POST"])
def start_play_session(user_id, game_id):
    uid, err = _require_auth(user_id)
    if err:
        return err
    with db_cursor(commit=True) as (_, cur):
        cur.execute(
            "SELECT active_session_started_at FROM USER_LIBRARY "
            "WHERE user_id = %s AND game_id = %s FOR UPDATE",
            (uid, game_id),
        )
        lib = cur.fetchone()
        if not lib:
            return _error("Game not found in user library.", 404)
        if lib["active_session_started_at"] is not None:
            started_str = serialize_row(lib)["active_session_started_at"]
            return _error(f"Game session is already running (started at {started_str}).", 400)

        cur.execute(
            "UPDATE USER_LIBRARY SET active_session_started_at = NOW(), last_played_at = NOW() "
            "WHERE user_id = %s AND game_id = %s",
            (uid, game_id),
        )
        cur.execute(
            "SELECT user_id, game_id, active_session_started_at, last_played_at "
            "FROM USER_LIBRARY WHERE user_id = %s AND game_id = %s",
            (uid, game_id),
        )
        row = serialize_row(cur.fetchone())
        row["started"] = True
        return jsonify(row)


@app.route("/api/users/<int:user_id>/library/<int:game_id>/play/exit", methods=["POST"])
def exit_play_session(user_id, game_id):
    uid, err = _require_auth(user_id)
    if err:
        return err
    with db_cursor(commit=True) as (_, cur):
        cur.execute(
            """
            SELECT playtime_minutes, playtime_seconds, active_session_started_at,
                   EXTRACT(EPOCH FROM (NOW() - active_session_started_at))::bigint AS elapsed_seconds
            FROM USER_LIBRARY
            WHERE user_id = %s AND game_id = %s
            FOR UPDATE
            """,
            (uid, game_id),
        )
        lib = cur.fetchone()
        if not lib:
            return _error("Game not found in user library.", 404)
        if lib["active_session_started_at"] is None:
            return _error("No active play session to exit.", 400)

        elapsed = max(1, int(lib["elapsed_seconds"] or 0))
        base_seconds = max(int(lib["playtime_seconds"] or 0), int(lib["playtime_minutes"] or 0) * 60)
        new_total_seconds = base_seconds + elapsed
        new_total_minutes = new_total_seconds // 60

        cur.execute(
            """
            UPDATE USER_LIBRARY
            SET playtime_seconds = %s,
                playtime_minutes = %s,
                last_session_started_at = active_session_started_at,
                last_session_ended_at = NOW(),
                last_session_seconds = %s,
                last_played_at = NOW(),
                active_session_started_at = NULL
            WHERE user_id = %s AND game_id = %s
            """,
            (new_total_seconds, new_total_minutes, elapsed, uid, game_id),
        )
        cur.execute(
            "SELECT * FROM USER_LIBRARY WHERE user_id = %s AND game_id = %s",
            (uid, game_id),
        )
        row = serialize_row(cur.fetchone())
        row["exited"] = True
        return jsonify(row)


@app.route("/api/users/<int:user_id>/library/<int:game_id>/play", methods=["POST"])
def record_playtime(user_id, game_id):
    uid, err = _require_auth(user_id)
    if err:
        return err
    data = request.get_json(silent=True) or {}
    minutes = int(data.get("minutes", 30))
    if minutes <= 0:
        return _error("Playtime minutes must be positive.")
    with db_cursor(commit=True) as (_, cur):
        cur.execute(
            "SELECT playtime_minutes, playtime_seconds FROM USER_LIBRARY "
            "WHERE user_id = %s AND game_id = %s FOR UPDATE",
            (uid, game_id),
        )
        lib = cur.fetchone()
        if not lib:
            return _error("Game not found in user library.", 404)
        base_seconds = max(int(lib["playtime_seconds"] or 0), int(lib["playtime_minutes"] or 0) * 60)
        new_total_seconds = base_seconds + (minutes * 60)
        new_total_minutes = new_total_seconds // 60
        cur.execute(
            "UPDATE USER_LIBRARY SET playtime_seconds = %s, playtime_minutes = %s, last_played_at = NOW() "
            "WHERE user_id = %s AND game_id = %s",
            (new_total_seconds, new_total_minutes, uid, game_id),
        )
        cur.execute(
            "SELECT * FROM USER_LIBRARY WHERE user_id = %s AND game_id = %s",
            (uid, game_id),
        )
        return jsonify(serialize_row(cur.fetchone()))


@app.route("/api/users/<int:user_id>/library/<int:game_id>/refund", methods=["POST"])
def refund_game(user_id, game_id):
    uid, err = _require_auth(user_id)
    if err:
        return err
    data = request.get_json(silent=True) or {}
    reason = (data.get("reason") or "Requested by player").strip()[:255] or "Requested by player"

    with db_cursor(commit=True) as (_, cur):
        cur.execute("SELECT user_id, role, wallet_balance FROM USERS WHERE user_id = %s FOR UPDATE", (uid,))
        user = cur.fetchone()
        if not user:
            return _error("User not found.", 404)
        if user["role"] != "user":
            return _error("Only User accounts can refund purchases.", 403)

        cur.execute(
            "SELECT user_id, game_id, playtime_minutes, acquired_at, active_session_started_at "
            "FROM USER_LIBRARY WHERE user_id = %s AND game_id = %s FOR UPDATE",
            (uid, game_id),
        )
        lib = cur.fetchone()
        if not lib:
            return _error("Game not found in your library.", 404)
        if lib["active_session_started_at"] is not None:
            return _error("Please exit the active game session before requesting a refund.", 400)

        cur.execute(
            """
            SELECT oi.order_item_id, oi.order_id, oi.price_at_purchase, oi.status,
                   o.created_at AS purchased_at,
                   EXTRACT(EPOCH FROM (NOW() - o.created_at))::bigint AS seconds_since_purchase,
                   g.title AS game_title
            FROM ORDER_ITEMS oi
            JOIN ORDERS o ON o.order_id = oi.order_id
            JOIN GAMES g ON g.game_id = oi.game_id
            WHERE o.user_id = %s AND oi.game_id = %s AND oi.status = 'purchased'
            ORDER BY o.created_at DESC, oi.order_item_id DESC
            LIMIT 1
            FOR UPDATE
            """,
            (uid, game_id),
        )
        item = cur.fetchone()
        if not item:
            return _error("No refundable paid purchase found for this game.", 400)

        refund_amount = Decimal(str(item["price_at_purchase"]))
        if refund_amount <= 0:
            return _error("Free titles cannot be refunded.", 400)

        playtime = int(lib["playtime_minutes"] or 0)
        if playtime >= REFUND_MAX_PLAYTIME_MINUTES:
            return _error(
                f"Refund ineligible under Steam 2-hour policy: {playtime}m played (must be under {REFUND_MAX_PLAYTIME_MINUTES} minutes / 2 hours).",
                400,
            )

        elapsed_sec = int(item["seconds_since_purchase"] or 0)
        if elapsed_sec > REFUND_MAX_SECONDS:
            days_ago = elapsed_sec // 86400
            return _error(
                f"Refund ineligible under Steam policy: purchased {days_ago} days ago (must be within {REFUND_MAX_DAYS} days).",
                400,
            )

        cur.execute(
            "UPDATE ORDER_ITEMS SET status = 'refunded', refunded_at = NOW(), refund_reason = %s "
            "WHERE order_item_id = %s",
            (reason, item["order_item_id"]),
        )
        cur.execute(
            "SELECT COUNT(*) AS remaining FROM ORDER_ITEMS WHERE order_id = %s AND status = 'purchased'",
            (item["order_id"],),
        )
        remaining = int(cur.fetchone()["remaining"])
        new_order_status = "refunded" if remaining == 0 else "partially_refunded"
        cur.execute(
            "UPDATE ORDERS SET status = %s WHERE order_id = %s",
            (new_order_status, item["order_id"]),
        )
        region = _resolve_active_region(cur)
        rate = Decimal(str(region["rate_from_inr"]))
        minor_units = int(region["minor_units"])
        curr_code = region["currency_code"]
        display_refund = _convert_from_inr(refund_amount, rate, minor_units)

        cur.execute(
            "UPDATE USERS SET wallet_balance = wallet_balance + %s WHERE user_id = %s",
            (refund_amount, uid),
        )
        cur.execute(
            "INSERT INTO WALLET_TRANSACTIONS "
            "(user_id, amount, currency_code, exchange_rate_used, display_amount, txn_type, reference_order_id) "
            "VALUES (%s, %s, %s, %s, %s, 'refund', %s)",
            (uid, refund_amount, curr_code, rate, display_refund, item["order_id"]),
        )
        cur.execute(
            "DELETE FROM USER_LIBRARY WHERE user_id = %s AND game_id = %s",
            (uid, game_id),
        )

        new_balance = Decimal(str(user["wallet_balance"])) + refund_amount
        return jsonify({
            "refunded": True,
            "game_id": game_id,
            "game_title": item["game_title"],
            "order_id": int(item["order_id"]),
            "order_item_id": int(item["order_item_id"]),
            "refund_amount": float(refund_amount),
            "display_refund_amount": float(display_refund),
            "currency_code": curr_code,
            "wallet_balance": float(new_balance),
            "order_status": new_order_status,
        })


@app.route("/api/users/<int:user_id>/achievements/<int:achievement_id>/unlock", methods=["POST"])
def unlock_achievement(user_id, achievement_id):
    uid, err = _require_auth(user_id)
    if err:
        return err
    with db_cursor(commit=True) as (_, cur):
        cur.execute("SELECT game_id FROM ACHIEVEMENTS WHERE achievement_id = %s", (achievement_id,))
        ach = cur.fetchone()
        if not ach:
            return _error("Achievement not found.", 404)
        cur.execute(
            "SELECT 1 FROM USER_LIBRARY WHERE user_id = %s AND game_id = %s",
            (uid, ach["game_id"]),
        )
        if not cur.fetchone():
            return _error("User must own the game to unlock its achievements.")
        cur.execute(
            "INSERT INTO USER_ACHIEVEMENTS (user_id, achievement_id, unlocked_at) "
            "VALUES (%s, %s, NOW()) ON CONFLICT DO NOTHING",
            (uid, achievement_id),
        )
        return jsonify({"unlocked": True, "achievement_id": achievement_id})


# ---------------------------------------------------------------------------
# Wishlist
# ---------------------------------------------------------------------------
@app.route("/api/users/<int:user_id>/wishlist", methods=["GET"])
def get_wishlist(user_id):
    uid, err = _require_auth(user_id)
    if err:
        return err
    with db_cursor() as (_, cur):
        cur.execute(
            f"""
            SELECT w.user_id, w.game_id, w.added_at,
                   g.title, g.base_price, g.age_rating, p.name AS publisher_name,
                   sd.discount_pct, sd.sale_title
            FROM WISHLIST w
            JOIN GAMES g ON g.game_id = w.game_id
            JOIN PUBLISHERS p ON p.publisher_id = g.publisher_id
            LEFT JOIN ({_active_discount_subquery()}) sd ON sd.game_id = g.game_id
            WHERE w.user_id = %s
            ORDER BY w.added_at DESC
            """,
            (uid,),
        )
        rows = serialize_rows(cur.fetchall())
        for r in rows:
            r["discount_pct"] = int(r["discount_pct"]) if r["discount_pct"] else 0
            r["effective_price"] = _compute_effective_price(r["base_price"], r["discount_pct"])
        return jsonify(rows)


@app.route("/api/users/<int:user_id>/wishlist", methods=["POST"])
def add_wishlist(user_id):
    uid, err = _require_auth(user_id)
    if err:
        return err
    data = request.get_json(force=True) or {}
    game_id = data.get("game_id")
    if not game_id:
        return _error("game_id is required.")
    with db_cursor(commit=True) as (_, cur):
        cur.execute(
            "SELECT 1 FROM USER_LIBRARY WHERE user_id = %s AND game_id = %s",
            (uid, int(game_id)),
        )
        if cur.fetchone():
            return _error("You already own this game.")
        cur.execute(
            "INSERT INTO WISHLIST (user_id, game_id, added_at) VALUES (%s, %s, NOW()) ON CONFLICT DO NOTHING",
            (uid, int(game_id)),
        )
        return jsonify({"added": True, "game_id": int(game_id)}), 201


@app.route("/api/users/<int:user_id>/wishlist/<int:game_id>", methods=["DELETE"])
def remove_wishlist(user_id, game_id):
    uid, err = _require_auth(user_id)
    if err:
        return err
    with db_cursor(commit=True) as (_, cur):
        cur.execute(
            "DELETE FROM WISHLIST WHERE user_id = %s AND game_id = %s",
            (uid, game_id),
        )
        return jsonify({"removed": game_id})


# ---------------------------------------------------------------------------
# Checkout, Orders & Wallet Transactions
# ---------------------------------------------------------------------------
@app.route("/api/users/<int:user_id>/wallet/deposit", methods=["POST"])
def deposit_wallet(user_id):
    uid, err = _require_auth(user_id)
    if err:
        return err
    data = request.get_json(force=True) or {}
    raw_amount = Decimal(str(data.get("amount") or 0))
    if raw_amount <= 0:
        return _error("Deposit amount must be greater than zero.")
    with db_cursor(commit=True) as (_, cur):
        region = _resolve_active_region(cur)
        rate = Decimal(str(region["rate_from_inr"]))
        minor_units = int(region["minor_units"])
        curr_code = region["currency_code"]

        if data.get("input_in_active_currency"):
            display_amount = raw_amount
            inr_amount = _convert_to_inr(raw_amount, rate)
        else:
            inr_amount = raw_amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            display_amount = _convert_from_inr(inr_amount, rate, minor_units)

        if inr_amount <= 0:
            return _error("Deposit amount is too small after currency conversion.")

        cur.execute(
            "UPDATE USERS SET wallet_balance = wallet_balance + %s WHERE user_id = %s",
            (inr_amount, uid),
        )
        if cur.rowcount == 0:
            return _error("User not found.", 404)
        cur.execute(
            "INSERT INTO WALLET_TRANSACTIONS "
            "(user_id, amount, currency_code, exchange_rate_used, display_amount, txn_type, reference_order_id) "
            "VALUES (%s, %s, %s, %s, %s, 'deposit', NULL)",
            (uid, inr_amount, curr_code, rate, display_amount),
        )
        cur.execute("SELECT wallet_balance FROM USERS WHERE user_id = %s", (uid,))
        row = serialize_row(cur.fetchone())
        row["deposited_inr"] = float(inr_amount)
        row["deposited_display_amount"] = float(display_amount)
        row["currency_code"] = curr_code
        return jsonify(row)


@app.route("/api/users/<int:user_id>/checkout", methods=["POST"])
def checkout(user_id):
    uid, err = _require_auth(user_id)
    if err:
        return err
    data = request.get_json(force=True) or {}
    game_ids = [int(g) for g in (data.get("game_ids") or [])]
    payment_method = (data.get("payment_method") or "SAUNA Wallet").strip()
    if not game_ids:
        return _error("Select at least one game to purchase.")

    with db_cursor(commit=True) as (_, cur):
        region = _resolve_active_region(cur)
        rate = Decimal(str(region["rate_from_inr"]))
        minor_units = int(region["minor_units"])
        curr_code = region["currency_code"]
        symbol = region["symbol"]

        cur.execute("SELECT user_id, wallet_balance FROM USERS WHERE user_id = %s FOR UPDATE", (uid,))
        user = cur.fetchone()
        if not user:
            return _error("User not found.", 404)

        placeholders = ",".join(["%s"] * len(game_ids))
        cur.execute(
            f"SELECT game_id FROM USER_LIBRARY WHERE user_id = %s AND game_id IN ({placeholders})",
            [uid] + game_ids,
        )
        already_owned = [r["game_id"] for r in cur.fetchall()]
        if already_owned:
            return _error(f"Already owned game ID(s): {already_owned}")

        cur.execute(
            f"""
            SELECT g.game_id, g.title, g.base_price, sd.discount_pct
            FROM GAMES g
            LEFT JOIN ({_active_discount_subquery()}) sd ON sd.game_id = g.game_id
            WHERE g.game_id IN ({placeholders})
            """,
            game_ids,
        )
        games = cur.fetchall()
        if len(games) != len(set(game_ids)):
            return _error("One or more requested games do not exist.", 404)

        line_items = []
        total = Decimal("0.00")
        display_total = Decimal("0.00")
        for g in games:
            eff = Decimal(str(_compute_effective_price(g["base_price"], g["discount_pct"])))
            disp_eff = _convert_from_inr(eff, rate, minor_units)
            total += eff
            display_total += disp_eff
            line_items.append((g["game_id"], eff, disp_eff))

        current_balance = Decimal(str(user["wallet_balance"]))
        if total > 0:
            if current_balance < total:
                disp_bal = _convert_from_inr(current_balance, rate, minor_units)
                return _error(
                    f"Insufficient Wallet balance ({_format_currency_text(disp_bal, symbol, minor_units)} < {_format_currency_text(display_total, symbol, minor_units)})."
                )
            cur.execute(
                "UPDATE USERS SET wallet_balance = wallet_balance - %s WHERE user_id = %s",
                (total, uid),
            )
        new_balance = current_balance - total

        cur.execute(
            "INSERT INTO ORDERS "
            "(user_id, total_amount, currency_code, exchange_rate_used, display_total_amount, payment_method, status) "
            "VALUES (%s, %s, %s, %s, %s, %s, 'completed') RETURNING order_id",
            (uid, total, curr_code, rate, display_total, "SAUNA Wallet"),
        )
        order_id = cur.fetchone()["order_id"]

        for gid, price, disp_price in line_items:
            cur.execute(
                "INSERT INTO ORDER_ITEMS (order_id, game_id, price_at_purchase, display_price_at_purchase) "
                "VALUES (%s, %s, %s, %s)",
                (order_id, gid, price, disp_price),
            )
            cur.execute(
                "INSERT INTO USER_LIBRARY (user_id, game_id, acquired_at, playtime_minutes, playtime_seconds) "
                "VALUES (%s, %s, NOW(), 0, 0)",
                (uid, gid),
            )
            cur.execute("DELETE FROM WISHLIST WHERE user_id = %s AND game_id = %s", (uid, gid))

        if total > 0:
            cur.execute(
                "INSERT INTO WALLET_TRANSACTIONS "
                "(user_id, amount, currency_code, exchange_rate_used, display_amount, txn_type, reference_order_id) "
                "VALUES (%s, %s, %s, %s, %s, 'purchase', %s)",
                (uid, -total, curr_code, rate, -display_total, order_id),
            )

        return jsonify({
            "order_id": order_id,
            "total_amount": float(total),
            "display_total_amount": float(display_total),
            "currency_code": curr_code,
            "wallet_balance": float(new_balance),
            "games_purchased": len(line_items),
        }), 201


@app.route("/api/users/<int:user_id>/orders", methods=["GET"])
def user_orders(user_id):
    uid, err = _require_auth(user_id)
    if err:
        return err
    with db_cursor() as (_, cur):
        cur.execute(
            """
            SELECT o.*, c.symbol AS currency_symbol, c.minor_units,
                   EXTRACT(EPOCH FROM (NOW() - o.created_at))::bigint AS seconds_since_purchase
            FROM ORDERS o
            LEFT JOIN CURRENCIES c ON c.currency_code = o.currency_code
            WHERE o.user_id = %s
            ORDER BY o.created_at DESC, o.order_id DESC
            """,
            (uid,),
        )
        orders = serialize_rows(cur.fetchall())
        if not orders:
            return jsonify([])
        cur.execute(
            "SELECT game_id, playtime_minutes FROM USER_LIBRARY WHERE user_id = %s",
            (uid,),
        )
        lib_playtime = {r["game_id"]: int(r["playtime_minutes"]) for r in cur.fetchall()}
        order_by_id = {o["order_id"]: o for o in orders}
        order_ids = list(order_by_id.keys())
        placeholders = ",".join(["%s"] * len(order_ids))
        cur.execute(
            f"SELECT oi.*, g.title FROM ORDER_ITEMS oi JOIN GAMES g ON g.game_id = oi.game_id "
            f"WHERE oi.order_id IN ({placeholders}) ORDER BY oi.order_item_id ASC",
            order_ids,
        )
        items_by_order = {}
        for item in serialize_rows(cur.fetchall()):
            parent_order = order_by_id[item["order_id"]]
            item["currency_code"] = parent_order.get("currency_code") or "INR"
            item["currency_symbol"] = parent_order.get("currency_symbol") or "₹"
            item["minor_units"] = int(parent_order.get("minor_units") if parent_order.get("minor_units") is not None else 2)
            if item.get("status") == "purchased" and item["game_id"] in lib_playtime:
                playtime = lib_playtime[item["game_id"]]
                item["playtime_minutes"] = playtime
                item.update(
                    _evaluate_refund_eligibility(
                        playtime,
                        item["price_at_purchase"],
                        parent_order["seconds_since_purchase"],
                    )
                )
            else:
                item["refund_eligible"] = False
                item["refund_status_text"] = None
            items_by_order.setdefault(item["order_id"], []).append(item)
        for o in orders:
            o["items"] = items_by_order.get(o["order_id"], [])
        return jsonify(orders)


@app.route("/api/users/<int:user_id>/wallet-transactions", methods=["GET"])
def user_wallet_transactions(user_id):
    uid, err = _require_auth(user_id)
    if err:
        return err
    with db_cursor() as (_, cur):
        cur.execute(
            """
            SELECT wt.*, c.symbol AS currency_symbol, c.minor_units
            FROM WALLET_TRANSACTIONS wt
            LEFT JOIN CURRENCIES c ON c.currency_code = wt.currency_code
            WHERE wt.user_id = %s
            ORDER BY wt.created_at DESC, wt.txn_id DESC
            """,
            (uid,),
        )
        return jsonify(serialize_rows(cur.fetchall()))


# ---------------------------------------------------------------------------
# Reviews
# ---------------------------------------------------------------------------
@app.route("/api/games/<int:game_id>/reviews", methods=["POST"])
def create_review(game_id):
    uid, err = _require_auth()
    if err:
        return err
    data = request.get_json(force=True) or {}
    is_recommended = bool(data.get("is_recommended", True))
    review_text = (data.get("review_text") or "").strip()
    if not review_text:
        return _error("Review text cannot be empty.")

    with db_cursor(commit=True) as (_, cur):
        cur.execute(
            "SELECT playtime_minutes FROM USER_LIBRARY WHERE user_id = %s AND game_id = %s",
            (uid, game_id),
        )
        lib = cur.fetchone()
        if not lib:
            return _error("You must own this game in your library to review it.")

        cur.execute(
            """
            INSERT INTO REVIEWS (user_id, game_id, is_recommended, review_text, playtime_at_review, helpful_votes)
            VALUES (%s, %s, %s, %s, %s, 0)
            ON CONFLICT (user_id, game_id) DO UPDATE SET
                is_recommended = EXCLUDED.is_recommended,
                review_text = EXCLUDED.review_text,
                playtime_at_review = EXCLUDED.playtime_at_review
            """,
            (uid, game_id, is_recommended, review_text, lib["playtime_minutes"]),
        )
        return jsonify({"saved": True}), 201


@app.route("/api/reviews/<int:review_id>/helpful", methods=["POST"])
def vote_helpful(review_id):
    _, err = _require_auth()
    if err:
        return err
    with db_cursor(commit=True) as (_, cur):
        cur.execute("UPDATE REVIEWS SET helpful_votes = helpful_votes + 1 WHERE review_id = %s", (review_id,))
        if cur.rowcount == 0:
            return _error("Review not found.", 404)
        cur.execute("SELECT helpful_votes FROM REVIEWS WHERE review_id = %s", (review_id,))
        return jsonify(serialize_row(cur.fetchone()))


# ---------------------------------------------------------------------------
# Friendships
# ---------------------------------------------------------------------------
@app.route("/api/users/<int:user_id>/friends", methods=["GET"])
def list_friends(user_id):
    uid, err = _require_auth(user_id)
    if err:
        return err
    with db_cursor() as (_, cur):
        cur.execute(
            """
            SELECT f.user_id, f.friend_id, f.status, f.created_at,
                   u.username AS other_username, u.country AS other_country,
                   u.user_id AS other_user_id,
                   CASE WHEN f.user_id = %s THEN 'outgoing' ELSE 'incoming' END AS direction
            FROM FRIENDSHIPS f
            JOIN USERS u ON u.user_id = CASE WHEN f.user_id = %s THEN f.friend_id ELSE f.user_id END
            WHERE f.user_id = %s OR f.friend_id = %s
            ORDER BY f.status ASC, f.created_at DESC
            """,
            (uid, uid, uid, uid),
        )
        return jsonify(serialize_rows(cur.fetchall()))


@app.route("/api/users/<int:user_id>/friends", methods=["POST"])
def send_friend_request(user_id):
    uid, err = _require_auth(user_id)
    if err:
        return err
    data = request.get_json(force=True) or {}
    friend_id = data.get("friend_id")
    if not friend_id:
        return _error("Friend Member ID is required.")
    friend_id = int(friend_id)
    with db_cursor(commit=True) as (_, cur):
        cur.execute("SELECT 1 FROM USERS WHERE user_id = %s", (friend_id,))
        if not cur.fetchone():
            return _error(f"Member ID #{friend_id} does not exist.", 404)
        cur.execute(
            "SELECT 1 FROM FRIENDSHIPS WHERE (user_id = %s AND friend_id = %s) OR (user_id = %s AND friend_id = %s)",
            (uid, friend_id, friend_id, uid),
        )
        if cur.fetchone():
            return _error("Friendship or pending request already exists with this member.")
        cur.execute(
            "INSERT INTO FRIENDSHIPS (user_id, friend_id, status) VALUES (%s, %s, 'pending')",
            (uid, friend_id),
        )
        return jsonify({"sent": True}), 201


@app.route("/api/users/<int:user_id>/friends/<int:other_id>", methods=["PUT"])
def update_friendship(user_id, other_id):
    uid, err = _require_auth(user_id)
    if err:
        return err
    data = request.get_json(force=True) or {}
    status = (data.get("status") or "accepted").strip()
    if status not in ("accepted", "pending", "blocked"):
        return _error("Invalid friendship status.")
    with db_cursor(commit=True) as (_, cur):
        cur.execute(
            "UPDATE FRIENDSHIPS SET status = %s "
            "WHERE (user_id = %s AND friend_id = %s) OR (user_id = %s AND friend_id = %s)",
            (status, uid, other_id, other_id, uid),
        )
        if cur.rowcount == 0:
            return _error("Friendship record not found.", 404)
        return jsonify({"updated": True, "status": status})


@app.route("/api/users/<int:user_id>/friends/<int:other_id>", methods=["DELETE"])
def delete_friendship(user_id, other_id):
    uid, err = _require_auth(user_id)
    if err:
        return err
    with db_cursor(commit=True) as (_, cur):
        cur.execute(
            "DELETE FROM FRIENDSHIPS "
            "WHERE (user_id = %s AND friend_id = %s) OR (user_id = %s AND friend_id = %s)",
            (uid, other_id, other_id, uid),
        )
        return jsonify({"deleted": True})


# ---------------------------------------------------------------------------
# Metadata & Admin Management (Publishers, Developers, Tags, Sales, Achievements)
# ---------------------------------------------------------------------------
@app.route("/api/meta", methods=["GET"])
def get_meta():
    with db_cursor() as (_, cur):
        cur.execute("SELECT * FROM PUBLISHERS ORDER BY name")
        publishers = serialize_rows(cur.fetchall())
        cur.execute("SELECT * FROM DEVELOPERS ORDER BY name")
        developers = serialize_rows(cur.fetchall())
        cur.execute("SELECT * FROM TAGS ORDER BY name")
        tags = serialize_rows(cur.fetchall())
        cur.execute(
            """
            SELECT s.*,
                   (NOW() BETWEEN s.start_date AND s.end_date) AS is_active,
                   COUNT(si.game_id) AS item_count
            FROM SALES s
            LEFT JOIN SALE_ITEMS si ON si.sale_id = s.sale_id
            GROUP BY s.sale_id
            ORDER BY s.start_date DESC
            """
        )
        sales = serialize_rows(cur.fetchall())
        cur.execute(
            "SELECT si.*, g.title AS game_title, s.title AS sale_title "
            "FROM SALE_ITEMS si "
            "JOIN GAMES g ON g.game_id = si.game_id "
            "JOIN SALES s ON s.sale_id = si.sale_id "
            "ORDER BY si.sale_id DESC, g.title"
        )
        sale_items = serialize_rows(cur.fetchall())
        cur.execute("SELECT * FROM CURRENCIES ORDER BY currency_code")
        currencies = serialize_rows(cur.fetchall())
        cur.execute(_region_select_sql() + "ORDER BY r.country_name")
        regions = serialize_rows(cur.fetchall())
        return jsonify({
            "publishers": publishers,
            "developers": developers,
            "tags": tags,
            "sales": sales,
            "sale_items": sale_items,
            "currencies": currencies,
            "regions": regions,
        })


@app.route("/api/publishers", methods=["POST"])
def create_publisher():
    _, _, err = _require_publisher()
    if err:
        return err
    data = request.get_json(force=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return _error("Publisher name is required.")
    with db_cursor(commit=True) as (_, cur):
        cur.execute(
            "INSERT INTO PUBLISHERS (name, country, founded_year, website) VALUES (%s, %s, %s, %s) RETURNING publisher_id",
            (name, data.get("country"), data.get("founded_year") or None, data.get("website")),
        )
        return jsonify({"publisher_id": cur.fetchone()["publisher_id"]}), 201


@app.route("/api/developers", methods=["POST"])
def create_developer():
    _, _, err = _require_publisher()
    if err:
        return err
    data = request.get_json(force=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return _error("Developer name is required.")
    with db_cursor(commit=True) as (_, cur):
        cur.execute(
            "INSERT INTO DEVELOPERS (name, country, website) VALUES (%s, %s, %s) RETURNING developer_id",
            (name, data.get("country"), data.get("website")),
        )
        return jsonify({"developer_id": cur.fetchone()["developer_id"]}), 201


@app.route("/api/tags", methods=["POST"])
def create_tag():
    _, _, err = _require_publisher()
    if err:
        return err
    data = request.get_json(force=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return _error("Tag name is required.")
    with db_cursor(commit=True) as (_, cur):
        cur.execute(
            "INSERT INTO TAGS (name, description) VALUES (%s, %s) RETURNING tag_id",
            (name, data.get("description") or ""),
        )
        return jsonify({"tag_id": cur.fetchone()["tag_id"]}), 201


@app.route("/api/sales", methods=["POST"])
def create_sale():
    _, _, err = _require_publisher()
    if err:
        return err
    data = request.get_json(force=True) or {}
    title = (data.get("title") or "").strip()
    start_date = data.get("start_date")
    end_date = data.get("end_date")
    if not title or not start_date or not end_date:
        return _error("Sale title, start_date, and end_date are required.")
    with db_cursor(commit=True) as (_, cur):
        cur.execute(
            "INSERT INTO SALES (title, start_date, end_date) VALUES (%s, %s, %s) RETURNING sale_id",
            (title, start_date, end_date),
        )
        return jsonify({"sale_id": cur.fetchone()["sale_id"]}), 201


@app.route("/api/sales/<int:sale_id>/items", methods=["POST"])
def add_sale_item(sale_id):
    _, pub_id, err = _require_publisher()
    if err:
        return err
    data = request.get_json(force=True) or {}
    game_id = data.get("game_id")
    discount_pct = int(data.get("discount_pct") or 0)
    if not game_id or not (1 <= discount_pct <= 100):
        return _error("Valid game_id and discount_pct (1-100) are required.")
    with db_cursor(commit=True) as (_, cur):
        cur.execute("SELECT 1 FROM GAMES WHERE game_id = %s AND publisher_id = %s", (int(game_id), pub_id))
        if not cur.fetchone():
            return _error("You can only discount games published by your studio.", 403)
        cur.execute(
            """
            INSERT INTO SALE_ITEMS (sale_id, game_id, discount_pct) VALUES (%s, %s, %s)
            ON CONFLICT (sale_id, game_id) DO UPDATE SET discount_pct = EXCLUDED.discount_pct
            """,
            (sale_id, int(game_id), discount_pct),
        )
        return jsonify({"saved": True}), 201


@app.route("/api/achievements", methods=["POST"])
def create_achievement():
    _, pub_id, err = _require_publisher()
    if err:
        return err
    data = request.get_json(force=True) or {}
    game_id = data.get("game_id")
    name = (data.get("name") or "").strip()
    if not game_id or not name:
        return _error("game_id and achievement name are required.")
    with db_cursor(commit=True) as (_, cur):
        cur.execute("SELECT 1 FROM GAMES WHERE game_id = %s AND publisher_id = %s", (int(game_id), pub_id))
        if not cur.fetchone():
            return _error("You can only add achievements to games published by your studio.", 403)
        cur.execute(
            "INSERT INTO ACHIEVEMENTS (game_id, name, description, is_hidden) VALUES (%s, %s, %s, %s) RETURNING achievement_id",
            (int(game_id), name, data.get("description") or "", bool(data.get("is_hidden", False))),
        )
        return jsonify({"achievement_id": cur.fetchone()["achievement_id"]}), 201


# ---------------------------------------------------------------------------
# Schema & Live SQL Explorer (All 17 ER Tables)
# ---------------------------------------------------------------------------
@app.route("/api/db/tables", methods=["GET"])
def list_db_tables():
    _, err = _require_admin()
    if err:
        return err
    with db_cursor() as (_, cur):
        tables = []
        for tbl in sorted(ALLOWED_TABLES):  # whitelisted names only
            cur.execute(f"SELECT COUNT(*) AS cnt FROM {tbl}")
            cnt = cur.fetchone()["cnt"]
            cur.execute(
                """
                SELECT c.column_name,
                       c.data_type AS column_type,
                       CASE WHEN pk.column_name IS NOT NULL THEN 'PRI' ELSE '' END AS column_key,
                       c.is_nullable
                FROM information_schema.columns c
                LEFT JOIN (
                    SELECT kcu.column_name
                    FROM information_schema.table_constraints tc
                    JOIN information_schema.key_column_usage kcu
                      ON kcu.constraint_name = tc.constraint_name
                     AND kcu.table_schema = tc.table_schema
                     AND kcu.table_name = tc.table_name
                    WHERE tc.constraint_type = 'PRIMARY KEY'
                      AND tc.table_schema = current_schema()
                      AND tc.table_name = %s
                ) pk ON pk.column_name = c.column_name
                WHERE c.table_schema = current_schema() AND c.table_name = %s
                ORDER BY c.ordinal_position
                """,
                (tbl, tbl),
            )
            cols = serialize_rows(cur.fetchall())
            tables.append({"table_name": tbl.upper(), "row_count": int(cnt), "columns": cols})
        return jsonify(tables)


def _mask_admin_rows(rows, mask_txn_amount=False):
    masked_cols = {"password_hash", "wallet_balance"}
    if mask_txn_amount:
        masked_cols.add("amount")
    for r in rows:
        for col in list(r.keys()):
            if col.lower() in masked_cols:
                r[col] = "********"
    return rows


@app.route("/api/db/tables/<table_name>", methods=["GET"])
def inspect_table(table_name):
    _, err = _require_admin()
    if err:
        return err
    tbl = table_name.lower()
    if tbl not in ALLOWED_TABLES:
        return _error("Unknown table name.", 404)
    limit = max(1, min(request.args.get("limit", 100, type=int), 500))
    with db_cursor() as (_, cur):
        cur.execute(f"SELECT * FROM {tbl} LIMIT %s", (limit,))
        rows = _mask_admin_rows(
            serialize_rows(cur.fetchall()),
            mask_txn_amount=(tbl == "wallet_transactions"),
        )
        cols = [d[0] for d in cur.description] if cur.description else []
        return jsonify({"table_name": tbl.upper(), "columns": cols, "rows": rows})


# Server-side functions, statistics views (they can hold sampled column values),
# functions that run SQL hidden in a string, and escaped identifiers.
_BLOCKED_SQL = re.compile(
    r"pg_stat|\bpg_(read|ls|sleep|terminate|cancel|reload|file|logical|create|drop|advisory)\w*|"
    r"\blo_(import|export|get|put)\w*|\bdblink\w*|\w+_to_xml\w*|\bts_(stat|rewrite)\b|"
    r"\bcopy\b|\bset_config\b|\bcurrent_setting\b|\bu&",
    re.I,
)


@app.route("/api/db/query", methods=["POST"])
def run_readonly_query():
    _, err = _require_admin()
    if err:
        return err
    if not ENABLE_SQL_EXPLORER:
        return _error("SQL Explorer is disabled on this deployment.", 403)
    data = request.get_json(force=True) or {}
    sql = (data.get("sql") or "").strip()
    if not sql:
        return _error("SQL query cannot be empty.")
    stripped = re.sub(r"^\s*(--[^\n]*\n|/\*.*?\*/\s*)*", "", sql, flags=re.S).strip()
    first_kw = stripped.split(None, 1)[0].upper() if stripped else ""
    if first_kw not in ("SELECT", "EXPLAIN", "WITH", "TABLE", "VALUES"):
        return _error("SQL Explorer only allows read-only queries (SELECT, WITH, EXPLAIN).")
    if re.match(r"EXPLAIN\s+(\(.*?\)\s*)?ANALY[SZ]E", stripped, re.I):
        return _error("EXPLAIN ANALYZE is not allowed.")
    if re.search(r"\b(wallet_balance|password_hash)\b", stripped, flags=re.I):
        return _error("Wallet balance and password hash are masked for Platform Admin.", 403)
    if _BLOCKED_SQL.search(stripped):
        return _error("This query uses restricted views or functions.", 403)
    body = stripped.rstrip().rstrip(";")
    # One statement only. This also guarantees the query cannot COMMIT the masking below.
    if ";" in body:
        return _error("Only a single SQL statement is allowed per query.")

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL lock_timeout = 3000")
            cur.execute("SET LOCAL statement_timeout = 5000")
            # Overwrite private values inside this transaction only (always rolled
            # back), so aliases, casts or row_to_json() cannot reveal them.
            cur.execute("UPDATE users SET password_hash = '********', wallet_balance = 0")
            cur.execute("UPDATE wallet_transactions SET amount = 0")
            # From here PostgreSQL itself refuses every write.
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute(body)
            mentions_wallet_txn = bool(re.search(r"\bwallet_transactions\b", stripped, flags=re.I))
            rows = _mask_admin_rows(
                serialize_rows(cur.fetchmany(200)),
                mask_txn_amount=mentions_wallet_txn,
            )
            cols = [d[0] for d in cur.description] if cur.description else []
        return jsonify({"columns": cols, "rows": rows, "row_count": len(rows)})
    finally:
        conn.rollback()
        conn.close()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5050"))
    app.run(host="0.0.0.0", port=port, debug=False)
