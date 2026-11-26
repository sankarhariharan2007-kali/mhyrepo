import os
import re
from contextlib import contextmanager
from decimal import Decimal
from flask import Flask, jsonify, render_template, request, session
from werkzeug.security import check_password_hash, generate_password_hash
import pymysql

from db import get_connection, serialize_row, serialize_rows

app = Flask(__name__)
app.secret_key = os.environ.get("SAUNA_SECRET_KEY", "sauna-session-secret-2026")
app.config["TEMPLATES_AUTO_RELOAD"] = True

ALLOWED_TABLES = {
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


def _active_discount_subquery():
    return """
        SELECT si.game_id, MAX(si.discount_pct) AS discount_pct,
               SUBSTRING_INDEX(GROUP_CONCAT(s.title ORDER BY si.discount_pct DESC SEPARATOR '||'), '||', 1) AS sale_title
        FROM SALE_ITEMS si
        JOIN SALES s ON s.sale_id = si.sale_id
        WHERE NOW() BETWEEN s.start_date AND s.end_date
        GROUP BY si.game_id
    """


@app.errorhandler(pymysql.MySQLError)
def handle_mysql_error(err):
    code = err.args[0] if err.args else 500
    msg = err.args[1] if len(err.args) > 1 else str(err)
    return jsonify({"error": f"Database error ({code}): {msg}"}), 400


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
        return jsonify({
            "authenticated": True,
            "user_id": int(user["user_id"]),
            "username": user["username"],
            "role": user["role"],
            "publisher_id": session["publisher_id"],
            "publisher_name": user["publisher_name"],
            "wallet_balance": float(user["wallet_balance"]),
            "country": user["country"],
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
    country = (data.get("country") or "India").strip()

    if not username or not email or not password:
        return _error("Username, email, and password are required.")
    if len(password) < 4:
        return _error("Password must be at least 4 characters.")

    pw_hash = generate_password_hash(password)
    with db_cursor(commit=True) as (_, cur):
        publisher_id = None
        publisher_name = None
        wallet = 0.0

        if account_type == "publisher":
            publisher_name = (data.get("publisher_name") or "").strip()
            if not publisher_name:
                return _error("Publisher / Studio Name is required for Publisher registration.")
            founded_year = data.get("founded_year") or None
            website = (data.get("website") or "").strip() or None
            cur.execute("SELECT publisher_id, name FROM PUBLISHERS WHERE name = %s", (publisher_name,))
            existing_pub = cur.fetchone()
            if existing_pub:
                publisher_id = int(existing_pub["publisher_id"])
                publisher_name = existing_pub["name"]
            else:
                cur.execute(
                    "INSERT INTO PUBLISHERS (name, country, founded_year, website) VALUES (%s, %s, %s, %s)",
                    (publisher_name, country, founded_year, website),
                )
                publisher_id = cur.lastrowid
        else:
            wallet = float(data.get("wallet_balance") or 0)
            if wallet < 0:
                return _error("Initial wallet balance cannot be negative.")

        cur.execute(
            "INSERT INTO USERS (username, email, password_hash, role, publisher_id, wallet_balance, country) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (username, email, pw_hash, account_type, publisher_id, wallet, country),
        )
        user_id = cur.lastrowid
        if account_type == "user" and wallet > 0:
            cur.execute(
                "INSERT INTO WALLET_TRANSACTIONS (user_id, amount, txn_type, reference_order_id) "
                "VALUES (%s, %s, 'deposit', NULL)",
                (user_id, wallet),
            )

        session["user_id"] = int(user_id)
        session["role"] = account_type
        session["publisher_id"] = int(publisher_id) if publisher_id else None
        return jsonify({
            "authenticated": True,
            "user_id": int(user_id),
            "username": username,
            "role": account_type,
            "publisher_id": session["publisher_id"],
            "publisher_name": publisher_name,
            "wallet_balance": float(wallet),
            "country": country,
        }), 201


@app.route("/api/auth/logout", methods=["POST"])
def auth_logout():
    session.clear()
    return jsonify({"authenticated": False, "logged_out": True})


@app.route("/api/auth/me", methods=["GET"])
def auth_me():
    uid = session.get("user_id")
    if not uid:
        return jsonify({"authenticated": False, "user": None})

    with db_cursor() as (_, cur):
        cur.execute(
            "SELECT u.user_id, u.username, u.role, u.publisher_id, p.name AS publisher_name, "
            "u.wallet_balance, u.country, u.created_at "
            "FROM USERS u LEFT JOIN PUBLISHERS p ON p.publisher_id = u.publisher_id "
            "WHERE u.user_id = %s",
            (int(uid),),
        )
        user = cur.fetchone()
        if not user:
            session.clear()
            return jsonify({"authenticated": False, "user": None})

        session["role"] = user["role"]
        session["publisher_id"] = int(user["publisher_id"]) if user["publisher_id"] else None

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
        conditions.append("(g.title LIKE %s OR g.description LIKE %s)")
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
                   SUM(CASE WHEN is_recommended = 1 THEN 1 ELSE 0 END) AS positive_count
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
        if user_id:
            cur.execute(
                "SELECT 1 FROM USER_LIBRARY WHERE user_id = %s AND game_id = %s",
                (int(user_id), game_id),
            )
            game["owned"] = cur.fetchone() is not None
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
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
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
        game_id = cur.lastrowid
        for tid in tag_ids:
            cur.execute("INSERT IGNORE INTO GAME_TAGS (game_id, tag_id) VALUES (%s, %s)", (game_id, int(tid)))
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
            SELECT ul.user_id, ul.game_id, ul.acquired_at, ul.playtime_minutes, ul.last_played_at,
                   g.title, g.description, g.age_rating, p.name AS publisher_name, d.name AS developer_name,
                   (SELECT COUNT(*) FROM ACHIEVEMENTS a WHERE a.game_id = g.game_id) AS total_achievements,
                   (SELECT COUNT(*) FROM USER_ACHIEVEMENTS ua
                    JOIN ACHIEVEMENTS a ON a.achievement_id = ua.achievement_id
                    WHERE ua.user_id = ul.user_id AND a.game_id = g.game_id) AS unlocked_achievements
            FROM USER_LIBRARY ul
            JOIN GAMES g ON g.game_id = ul.game_id
            JOIN PUBLISHERS p ON p.publisher_id = g.publisher_id
            JOIN DEVELOPERS d ON d.developer_id = g.developer_id
            WHERE ul.user_id = %s
            ORDER BY ul.last_played_at DESC, ul.acquired_at DESC
            """,
            (uid,),
        )
        return jsonify(serialize_rows(cur.fetchall()))


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
            "UPDATE USER_LIBRARY SET playtime_minutes = playtime_minutes + %s, last_played_at = NOW() "
            "WHERE user_id = %s AND game_id = %s",
            (minutes, uid, game_id),
        )
        if cur.rowcount == 0:
            return _error("Game not found in user library.", 404)
        cur.execute(
            "SELECT * FROM USER_LIBRARY WHERE user_id = %s AND game_id = %s",
            (uid, game_id),
        )
        return jsonify(serialize_row(cur.fetchone()))


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
            "INSERT IGNORE INTO USER_ACHIEVEMENTS (user_id, achievement_id, unlocked_at) "
            "VALUES (%s, %s, NOW())",
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
            "INSERT IGNORE INTO WISHLIST (user_id, game_id, added_at) VALUES (%s, %s, NOW())",
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
    amount = Decimal(str(data.get("amount") or 0))
    if amount <= 0:
        return _error("Deposit amount must be greater than zero.")
    with db_cursor(commit=True) as (_, cur):
        cur.execute(
            "UPDATE USERS SET wallet_balance = wallet_balance + %s WHERE user_id = %s",
            (amount, uid),
        )
        if cur.rowcount == 0:
            return _error("User not found.", 404)
        cur.execute(
            "INSERT INTO WALLET_TRANSACTIONS (user_id, amount, txn_type, reference_order_id) "
            "VALUES (%s, %s, 'deposit', NULL)",
            (uid, amount),
        )
        cur.execute("SELECT wallet_balance FROM USERS WHERE user_id = %s", (uid,))
        row = serialize_row(cur.fetchone())
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
        for g in games:
            eff = Decimal(str(_compute_effective_price(g["base_price"], g["discount_pct"])))
            total += eff
            line_items.append((g["game_id"], eff))

        current_balance = Decimal(str(user["wallet_balance"]))
        if total > 0:
            if current_balance < total:
                return _error(
                    f"Insufficient Wallet balance (₹{float(current_balance):.2f} < ₹{float(total):.2f})."
                )
            cur.execute(
                "UPDATE USERS SET wallet_balance = wallet_balance - %s WHERE user_id = %s",
                (total, uid),
            )
        new_balance = current_balance - total

        cur.execute(
            "INSERT INTO ORDERS (user_id, total_amount, payment_method, status) "
            "VALUES (%s, %s, %s, 'completed')",
            (uid, total, "SAUNA Wallet"),
        )
        order_id = cur.lastrowid

        for gid, price in line_items:
            cur.execute(
                "INSERT INTO ORDER_ITEMS (order_id, game_id, price_at_purchase) VALUES (%s, %s, %s)",
                (order_id, gid, price),
            )
            cur.execute(
                "INSERT INTO USER_LIBRARY (user_id, game_id, acquired_at, playtime_minutes) "
                "VALUES (%s, %s, NOW(), 0)",
                (uid, gid),
            )
            cur.execute("DELETE FROM WISHLIST WHERE user_id = %s AND game_id = %s", (uid, gid))

        if total > 0:
            cur.execute(
                "INSERT INTO WALLET_TRANSACTIONS (user_id, amount, txn_type, reference_order_id) "
                "VALUES (%s, %s, 'purchase', %s)",
                (uid, -total, order_id),
            )

        return jsonify({
            "order_id": order_id,
            "total_amount": float(total),
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
            "SELECT * FROM ORDERS WHERE user_id = %s ORDER BY created_at DESC, order_id DESC",
            (uid,),
        )
        orders = serialize_rows(cur.fetchall())
        if not orders:
            return jsonify([])
        order_ids = [o["order_id"] for o in orders]
        placeholders = ",".join(["%s"] * len(order_ids))
        cur.execute(
            f"SELECT oi.*, g.title FROM ORDER_ITEMS oi JOIN GAMES g ON g.game_id = oi.game_id "
            f"WHERE oi.order_id IN ({placeholders}) ORDER BY oi.order_item_id ASC",
            order_ids,
        )
        items_by_order = {}
        for item in serialize_rows(cur.fetchall()):
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
            "SELECT * FROM WALLET_TRANSACTIONS WHERE user_id = %s "
            "ORDER BY created_at DESC, txn_id DESC",
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
            ON DUPLICATE KEY UPDATE
                is_recommended = VALUES(is_recommended),
                review_text = VALUES(review_text),
                playtime_at_review = VALUES(playtime_at_review)
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
        return jsonify({
            "publishers": publishers,
            "developers": developers,
            "tags": tags,
            "sales": sales,
            "sale_items": sale_items,
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
            "INSERT INTO PUBLISHERS (name, country, founded_year, website) VALUES (%s, %s, %s, %s)",
            (name, data.get("country"), data.get("founded_year") or None, data.get("website")),
        )
        return jsonify({"publisher_id": cur.lastrowid}), 201


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
            "INSERT INTO DEVELOPERS (name, country, website) VALUES (%s, %s, %s)",
            (name, data.get("country"), data.get("website")),
        )
        return jsonify({"developer_id": cur.lastrowid}), 201


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
            "INSERT INTO TAGS (name, description) VALUES (%s, %s)",
            (name, data.get("description") or ""),
        )
        return jsonify({"tag_id": cur.lastrowid}), 201


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
            "INSERT INTO SALES (title, start_date, end_date) VALUES (%s, %s, %s)",
            (title, start_date, end_date),
        )
        return jsonify({"sale_id": cur.lastrowid}), 201


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
            ON DUPLICATE KEY UPDATE discount_pct = VALUES(discount_pct)
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
            "INSERT INTO ACHIEVEMENTS (game_id, name, description, is_hidden) VALUES (%s, %s, %s, %s)",
            (int(game_id), name, data.get("description") or "", bool(data.get("is_hidden", False))),
        )
        return jsonify({"achievement_id": cur.lastrowid}), 201


# ---------------------------------------------------------------------------
# MySQL Schema & Live SQL Explorer (All 17 ER Tables)
# ---------------------------------------------------------------------------
@app.route("/api/db/tables", methods=["GET"])
def list_db_tables():
    _, err = _require_admin()
    if err:
        return err
    with db_cursor() as (_, cur):
        tables = []
        for tbl in sorted(ALLOWED_TABLES):
            cur.execute(f"SELECT COUNT(*) AS cnt FROM `{tbl}`")
            cnt = cur.fetchone()["cnt"]
            cur.execute(
                "SELECT COLUMN_NAME AS column_name, COLUMN_TYPE AS column_type, "
                "COLUMN_KEY AS column_key, IS_NULLABLE AS is_nullable "
                "FROM information_schema.columns "
                "WHERE table_schema = DATABASE() AND table_name = %s "
                "ORDER BY ordinal_position",
                (tbl,),
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
    limit = min(int(request.args.get("limit", 100)), 500)
    with db_cursor() as (_, cur):
        cur.execute(f"SELECT * FROM `{tbl}` LIMIT %s", (limit,))
        rows = _mask_admin_rows(
            serialize_rows(cur.fetchall()),
            mask_txn_amount=(tbl == "wallet_transactions"),
        )
        cols = [d[0] for d in cur.description] if cur.description else []
        return jsonify({"table_name": tbl.upper(), "columns": cols, "rows": rows})


@app.route("/api/db/query", methods=["POST"])
def run_readonly_query():
    _, err = _require_admin()
    if err:
        return err
    data = request.get_json(force=True) or {}
    sql = (data.get("sql") or "").strip()
    if not sql:
        return _error("SQL query cannot be empty.")
    stripped = re.sub(r"^\s*(--[^\n]*\n|/\*.*?\*/\s*)*", "", sql, flags=re.S).strip()
    first_kw = stripped.split(None, 1)[0].upper() if stripped else ""
    if first_kw not in ("SELECT", "SHOW", "DESCRIBE", "DESC", "EXPLAIN", "WITH"):
        return _error("SQL Explorer only allows read-only queries (SELECT, SHOW, DESCRIBE, EXPLAIN, WITH).")
    if ";" in stripped[:-1]:
        return _error("Only a single SQL statement is allowed per query.")
    if re.search(r"\b(wallet_balance|password_hash)\b", stripped, flags=re.I):
        return _error("Wallet balance and password hash are masked for Platform Admin.", 403)

    with db_cursor() as (_, cur):
        cur.execute(stripped)
        mentions_wallet_txn = bool(re.search(r"\bwallet_transactions\b", stripped, flags=re.I))
        rows = _mask_admin_rows(
            serialize_rows(cur.fetchmany(200)),
            mask_txn_amount=mentions_wallet_txn,
        )
        cols = [d[0] for d in cur.description] if cur.description else []
        return jsonify({"columns": cols, "rows": rows, "row_count": len(rows)})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5050"))
    app.run(host="0.0.0.0", port=port, debug=False)
