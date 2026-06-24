"""
Broker connection service — Fernet encryption for per-user API keys.

Keys are encrypted at rest using the platform FERNET_KEY from env.
They are decrypted only in-memory at order time and never logged or
returned to the client.

Storage: broker_connections table (one row per user × broker × environment).
"""
from __future__ import annotations

import os
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


# ─── Encryption helpers ───────────────────────────────────────────────────────

def _fernet() -> Fernet:
    key = os.getenv("FERNET_KEY", "")
    if not key:
        raise RuntimeError("FERNET_KEY environment variable is not set")
    return Fernet(key.encode())


def encrypt_secret(plaintext: str) -> bytes:
    return _fernet().encrypt(plaintext.encode())


def decrypt_secret(ciphertext: bytes) -> str:
    try:
        return _fernet().decrypt(ciphertext).decode()
    except InvalidToken as exc:
        raise ValueError("Unable to decrypt broker secret — FERNET_KEY may have changed") from exc


# ─── DB helpers ───────────────────────────────────────────────────────────────

async def save_broker_connection(
    db: AsyncSession,
    user_id: str,
    broker: str,
    environment: str,
    api_key: str,
    api_secret: Optional[str],
    account_id: Optional[str],
) -> str:
    """
    Upsert a broker connection for a user. Returns the connection UUID.
    The api_key and api_secret are encrypted before storage.
    """
    enc_key = encrypt_secret(api_key)
    enc_secret = encrypt_secret(api_secret) if api_secret else None

    result = await db.execute(
        text("""
            INSERT INTO broker_connections
                (user_id, broker, environment, encrypted_key, encrypted_secret, account_id)
            VALUES (:uid, :broker, :env, :ekey, :esecret, :acct)
            ON CONFLICT (user_id, broker, environment) DO UPDATE SET
                encrypted_key    = EXCLUDED.encrypted_key,
                encrypted_secret = EXCLUDED.encrypted_secret,
                account_id       = EXCLUDED.account_id,
                is_active        = TRUE,
                updated_at       = NOW()
            RETURNING id
        """),
        {
            "uid":     str(user_id),
            "broker":  broker.lower(),
            "env":     environment.lower(),
            "ekey":    enc_key,
            "esecret": enc_secret,
            "acct":    account_id,
        },
    )
    row = result.fetchone()
    await db.commit()
    return str(row[0])


async def list_broker_connections(db: AsyncSession, user_id: str) -> list[dict]:
    """Return broker connections for a user — metadata only, no keys."""
    result = await db.execute(
        text("""
            SELECT id, broker, environment, account_id, is_active, created_at, updated_at
            FROM broker_connections
            WHERE user_id = :uid
            ORDER BY broker, environment
        """),
        {"uid": str(user_id)},
    )
    cols = result.keys()
    return [dict(zip(cols, r)) for r in result.fetchall()]


async def delete_broker_connection(db: AsyncSession, connection_id: str, user_id: str) -> bool:
    """Delete a broker connection. Returns True if a row was deleted."""
    result = await db.execute(
        text("DELETE FROM broker_connections WHERE id = :cid AND user_id = :uid RETURNING id"),
        {"cid": connection_id, "uid": str(user_id)},
    )
    await db.commit()
    return result.fetchone() is not None


async def get_decrypted_keys(
    db: AsyncSession,
    user_id: str,
    broker: str,
    environment: str,
) -> Optional[dict]:
    """
    Fetch and decrypt API keys for a specific broker connection.
    Returns None if no active connection exists.
    Only call this at order time — never store or log the returned values.
    """
    result = await db.execute(
        text("""
            SELECT encrypted_key, encrypted_secret, account_id
            FROM broker_connections
            WHERE user_id = :uid AND broker = :broker AND environment = :env AND is_active = TRUE
        """),
        {"uid": str(user_id), "broker": broker.lower(), "env": environment.lower()},
    )
    row = result.fetchone()
    if not row:
        return None
    return {
        "api_key":    decrypt_secret(bytes(row[0])),
        "api_secret": decrypt_secret(bytes(row[1])) if row[1] else None,
        "account_id": row[2],
    }
