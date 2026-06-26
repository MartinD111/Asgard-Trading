"""
Set the admin account password from the ADMIN_PASSWORD environment variable.
Run once at startup (after alembic upgrade head). Idempotent — safe on every deploy.
"""
import asyncio
import logging
import os
import sys

logger = logging.getLogger(__name__)


async def _seed() -> None:
    password = os.getenv("ADMIN_PASSWORD", "").strip()
    if not password:
        logger.warning("[seed_admin] ADMIN_PASSWORD not set — skipping.")
        return

    if password.startswith("CHANGE_ME"):
        logger.error("[seed_admin] ADMIN_PASSWORD is still the placeholder — aborting startup.")
        sys.exit(1)

    import bcrypt
    from sqlalchemy import text
    from db.database import AsyncSessionLocal

    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text("UPDATE users SET password_hash = :h WHERE username = 'admin'"),
            {"h": hashed},
        )
        await session.commit()

    if result.rowcount:
        logger.info("[seed_admin] Admin password updated.")
    else:
        logger.warning("[seed_admin] No 'admin' user found — password not set.")


if __name__ == "__main__":
    asyncio.run(_seed())
