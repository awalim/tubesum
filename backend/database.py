"""
SQLite user database — handles auth, usage tracking, and subscription tiers.
Uses only stdlib + existing deps (no new ORM needed for this scale).
"""
import sqlite3
import hashlib
import secrets
import os
from datetime import datetime, date
from pathlib import Path

DB_PATH = Path(__file__).parent / "users.db"

# ── Free tier limits ───────────────────────────────────────────────────────────
FREE_DAILY_LIMIT = 3   # summaries per day for free users


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create tables if they don't exist."""
    with get_conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            email         TEXT    UNIQUE NOT NULL,
            password_hash TEXT    NOT NULL,
            salt          TEXT    NOT NULL,
            tier          TEXT    NOT NULL DEFAULT 'free',   -- 'free' | 'pro'
            stripe_customer_id    TEXT,
            stripe_subscription_id TEXT,
            created_at    TEXT    NOT NULL DEFAULT (datetime('now')),
            is_active     INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS sessions (
            token      TEXT PRIMARY KEY,
            user_id    INTEGER NOT NULL REFERENCES users(id),
            created_at TEXT    NOT NULL DEFAULT (datetime('now')),
            expires_at TEXT    NOT NULL
        );

        CREATE TABLE IF NOT EXISTS usage (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL REFERENCES users(id),
            used_on    TEXT    NOT NULL,   -- date string YYYY-MM-DD
            count      INTEGER NOT NULL DEFAULT 0,
            UNIQUE(user_id, used_on)
        );
        """)


# ── Password helpers ───────────────────────────────────────────────────────────

def _hash_password(password: str, salt: str) -> str:
    return hashlib.sha256((salt + password).encode()).hexdigest()


def create_user(email: str, password: str) -> dict | None:
    """Returns user dict or None if email already taken."""
    salt = secrets.token_hex(16)
    pw_hash = _hash_password(password, salt)
    try:
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO users (email, password_hash, salt) VALUES (?, ?, ?)",
                (email.lower().strip(), pw_hash, salt)
            )
        return get_user_by_email(email)
    except sqlite3.IntegrityError:
        return None


def verify_user(email: str, password: str) -> dict | None:
    """Returns user dict if credentials valid, else None."""
    user = get_user_by_email(email)
    if not user:
        return None
    expected = _hash_password(password, user["salt"])
    if secrets.compare_digest(expected, user["password_hash"]):
        return user
    return None


def get_user_by_email(email: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE email = ? AND is_active = 1",
            (email.lower().strip(),)
        ).fetchone()
    return dict(row) if row else None


def get_user_by_id(user_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE id = ? AND is_active = 1", (user_id,)
        ).fetchone()
    return dict(row) if row else None


# ── Sessions ──────────────────────────────────────────────────────────────────

def create_session(user_id: int) -> str:
    """Creates a session token valid for 30 days."""
    token = secrets.token_urlsafe(32)
    expires = datetime.utcnow().replace(hour=0, minute=0, second=0).strftime("%Y-%m-%d")
    # Simple: store token with 30-day rolling expiry
    from datetime import timedelta
    expires_at = (datetime.utcnow() + timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO sessions (token, user_id, expires_at) VALUES (?, ?, ?)",
            (token, user_id, expires_at)
        )
    return token


def get_user_from_token(token: str) -> dict | None:
    """Returns user dict if token is valid and not expired."""
    if not token:
        return None
    with get_conn() as conn:
        row = conn.execute("""
            SELECT u.* FROM users u
            JOIN sessions s ON s.user_id = u.id
            WHERE s.token = ?
              AND s.expires_at > datetime('now')
              AND u.is_active = 1
        """, (token,)).fetchone()
    return dict(row) if row else None


def delete_session(token: str):
    with get_conn() as conn:
        conn.execute("DELETE FROM sessions WHERE token = ?", (token,))


# ── Usage tracking ────────────────────────────────────────────────────────────

def get_daily_usage(user_id: int) -> int:
    today = date.today().isoformat()
    with get_conn() as conn:
        row = conn.execute(
            "SELECT count FROM usage WHERE user_id = ? AND used_on = ?",
            (user_id, today)
        ).fetchone()
    return row["count"] if row else 0


def increment_usage(user_id: int):
    today = date.today().isoformat()
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO usage (user_id, used_on, count) VALUES (?, ?, 1)
            ON CONFLICT(user_id, used_on) DO UPDATE SET count = count + 1
        """, (user_id, today))


def can_use(user: dict) -> tuple[bool, str]:
    """
    Returns (allowed: bool, reason: str).
    Pro users always allowed. Free users limited to FREE_DAILY_LIMIT/day.
    """
    if user["tier"] == "pro":
        return True, "ok"
    used = get_daily_usage(user["id"])
    if used >= FREE_DAILY_LIMIT:
        return False, f"Daily limit reached ({FREE_DAILY_LIMIT} summaries/day on free plan)"
    return True, "ok"


# ── Stripe helpers ────────────────────────────────────────────────────────────

def upgrade_to_pro(user_id: int, stripe_customer_id: str, stripe_subscription_id: str):
    with get_conn() as conn:
        conn.execute("""
            UPDATE users
            SET tier = 'pro',
                stripe_customer_id = ?,
                stripe_subscription_id = ?
            WHERE id = ?
        """, (stripe_customer_id, stripe_subscription_id, user_id))


def downgrade_to_free(stripe_subscription_id: str):
    with get_conn() as conn:
        conn.execute("""
            UPDATE users SET tier = 'free'
            WHERE stripe_subscription_id = ?
        """, (stripe_subscription_id,))


# ── Init on import ────────────────────────────────────────────────────────────
init_db()
