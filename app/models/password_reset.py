"""Password reset token model for email-based forgot-password flow."""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any

from app.utils.db import get_db_connection

TOKEN_TTL_HOURS = 1


def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode()).hexdigest()


def create_reset_token(user_id: str) -> str:
    """
    Generate a secure raw token, store its SHA-256 hash in the DB with a 1-hour
    expiry, and return the raw token to be sent in the reset email.
    Any previous unused tokens for this user are invalidated first.
    """
    raw_token = secrets.token_urlsafe(32)
    token_hash = _hash_token(raw_token)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=TOKEN_TTL_HOURS)

    with get_db_connection() as conn, conn.cursor() as cur:
        # Invalidate any previous unused tokens for this user
        cur.execute(
            "UPDATE password_reset_tokens SET used_at = now() WHERE user_id = %s AND used_at IS NULL",
            (user_id,),
        )
        cur.execute(
            """
            INSERT INTO password_reset_tokens (user_id, token_hash, expires_at)
            VALUES (%s, %s, %s)
            """,
            (user_id, token_hash, expires_at),
        )
        conn.commit()

    return raw_token


def get_valid_token(raw_token: str) -> Optional[Dict[str, Any]]:
    """
    Look up a token by its hash. Returns the row dict if valid (not expired,
    not used), otherwise None.
    """
    token_hash = _hash_token(raw_token)
    sql = """
        SELECT id, user_id, token_hash, expires_at, used_at, created_at
        FROM password_reset_tokens
        WHERE token_hash = %s
          AND expires_at > now()
          AND used_at IS NULL
    """
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (token_hash,))
        row = cur.fetchone()
        if not row:
            return None
        cols = ["id", "user_id", "token_hash", "expires_at", "used_at", "created_at"]
        return dict(zip(cols, row))


def mark_token_used(token_id: str) -> None:
    """Mark a token as used so it cannot be replayed."""
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE password_reset_tokens SET used_at = now() WHERE id = %s",
            (token_id,),
        )
        conn.commit()
