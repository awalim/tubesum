"""
PostgreSQL user database — handles auth, usage tracking, and subscription tiers.
Rewritten from SQLite to asyncpg for Railway PostgreSQL.
"""
import asyncpg
import hashlib
import secrets
import os
from datetime import datetime, date, timedelta

# ── Free tier limits ───────────────────────────────────────────────────────────
FREE_DAILY_LIMIT = 3   # summaries per day for free users

DATABASE_URL = os.environ.get("DATABASE_URL")

# ── Connection pool ────────────────────────────────────────────────────────────
_pool: asyncpg.Pool = None

async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=10)
    return _pool

async def get_conn():
    pool = await get_pool()
    return pool


async def init_db():
    """Create tables if they don't exist. Called on startup."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS tubesum_users (
            id                     SERIAL PRIMARY KEY,
            email                  TEXT    UNIQUE NOT NULL,
            password_hash          TEXT    NOT NULL,
            salt                   TEXT    NOT NULL,
            tier                   TEXT    NOT NULL DEFAULT 'free',
            stripe_customer_id     TEXT,
            stripe_subscription_id TEXT,
            created_at             TIMESTAMP NOT NULL DEFAULT NOW(),
            is_active              BOOLEAN NOT NULL DEFAULT TRUE
        );

        CREATE TABLE IF NOT EXISTS tubesum_sessions (
            token      TEXT PRIMARY KEY,
            user_id    INTEGER NOT NULL REFERENCES tubesum_users(id) ON DELETE CASCADE,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            expires_at TIMESTAMP NOT NULL
        );

        CREATE TABLE IF NOT EXISTS tubesum_usage (
            id         SERIAL PRIMARY KEY,
            user_id    INTEGER NOT NULL REFERENCES tubesum_users(id) ON DELETE CASCADE,
            used_on    DATE    NOT NULL,
            count      INTEGER NOT NULL DEFAULT 0,
            UNIQUE(user_id, used_on)
        );

        CREATE TABLE IF NOT EXISTS tubesum_password_reset_tokens (
            token      TEXT PRIMARY KEY,
            user_id    INTEGER NOT NULL REFERENCES tubesum_users(id) ON DELETE CASCADE,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            expires_at TIMESTAMP NOT NULL
        );
        """)


# ── Password helpers ───────────────────────────────────────────────────────────

def _hash_password(password: str, salt: str) -> str:
    return hashlib.sha256((salt + password).encode()).hexdigest()


# ── User management ────────────────────────────────────────────────────────────

async def create_user(email: str, password: str) -> dict | None:
    """Returns user dict or None if email already taken."""
    email_lower = email.lower().strip()
    salt = secrets.token_hex(16)
    pw_hash = _hash_password(password, salt)
    pool = await get_pool()
    async with pool.acquire() as conn:
        existing = await conn.fetchrow(
            "SELECT id FROM tubesum_users WHERE email = $1 AND is_active = TRUE",
            email_lower
        )
        if existing:
            return None
        try:
            await conn.execute(
                "INSERT INTO tubesum_users (email, password_hash, salt) VALUES ($1, $2, $3)",
                email_lower, pw_hash, salt
            )
        except asyncpg.UniqueViolationError:
            return None
    return await get_user_by_email(email)


async def verify_user(email: str, password: str) -> dict | None:
    """Returns user dict if credentials valid, else None."""
    user = await get_user_by_email(email)
    if not user:
        return None
    expected = _hash_password(password, user["salt"])
    if secrets.compare_digest(expected, user["password_hash"]):
        return user
    return None


async def get_user_by_email(email: str) -> dict | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM tubesum_users WHERE email = $1 AND is_active = TRUE",
            email.lower().strip()
        )
    return dict(row) if row else None


async def get_user_by_id(user_id: int) -> dict | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM tubesum_users WHERE id = $1 AND is_active = TRUE",
            user_id
        )
    return dict(row) if row else None


# ── Sessions ──────────────────────────────────────────────────────────────────

async def create_session(user_id: int) -> str:
    """Creates a session token valid for 30 days."""
    token = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(days=30)
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO tubesum_sessions (token, user_id, expires_at) VALUES ($1, $2, $3)",
            token, user_id, expires_at
        )
    return token


async def get_user_from_token(token: str) -> dict | None:
    """Returns user dict if token is valid and not expired."""
    if not token:
        return None
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT u.* FROM tubesum_users u
            JOIN tubesum_sessions s ON s.user_id = u.id
            WHERE s.token = $1
              AND s.expires_at > NOW()
              AND u.is_active = TRUE
        """, token)
    return dict(row) if row else None


async def delete_session(token: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM tubesum_sessions WHERE token = $1", token)


# ── Usage tracking ────────────────────────────────────────────────────────────

async def get_daily_usage(user_id: int) -> int:
    today = date.today()
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT count FROM tubesum_usage WHERE user_id = $1 AND used_on = $2",
            user_id, today
        )
    return row["count"] if row else 0


async def increment_usage(user_id: int):
    today = date.today()
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO tubesum_usage (user_id, used_on, count) VALUES ($1, $2, 1)
            ON CONFLICT (user_id, used_on) DO UPDATE SET count = tubesum_usage.count + 1
        """, user_id, today)


async def can_use(user: dict) -> tuple[bool, str]:
    """Returns (allowed, reason). Pro users always allowed."""
    if user["tier"] == "pro":
        return True, "ok"
    used = await get_daily_usage(user["id"])
    if used >= FREE_DAILY_LIMIT:
        return False, f"Daily limit reached ({FREE_DAILY_LIMIT} summaries/day on free plan)"
    return True, "ok"


# ── Stripe helpers ────────────────────────────────────────────────────────────

async def upgrade_to_pro(user_id: int, stripe_customer_id: str, stripe_subscription_id: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE tubesum_users
            SET tier = 'pro',
                stripe_customer_id = $1,
                stripe_subscription_id = $2
            WHERE id = $3
        """, stripe_customer_id, stripe_subscription_id, user_id)


async def downgrade_to_free(stripe_subscription_id: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE tubesum_users SET tier = 'free'
            WHERE stripe_subscription_id = $1
        """, stripe_subscription_id)


# ── Password reset tokens ─────────────────────────────────────────────────────

async def create_password_reset_token(user_id: int, token: str, ttl_seconds: int = 3600):
    expires_at = datetime.utcnow() + timedelta(seconds=ttl_seconds)
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO tubesum_password_reset_tokens (token, user_id, expires_at) VALUES ($1, $2, $3)",
            token, user_id, expires_at
        )


async def get_valid_password_reset_user_id(token: str) -> int | None:
    if not token:
        return None
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT user_id FROM tubesum_password_reset_tokens
            WHERE token = $1 AND expires_at > NOW()
        """, token)
    return row["user_id"] if row else None


async def delete_password_reset_token(token: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM tubesum_password_reset_tokens WHERE token = $1", token
        )


async def update_user_password(user_id: int, new_password: str):
    salt = secrets.token_hex(16)
    pw_hash = _hash_password(new_password, salt)
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE tubesum_users SET password_hash = $1, salt = $2 WHERE id = $3",
            pw_hash, salt, user_id
        )
