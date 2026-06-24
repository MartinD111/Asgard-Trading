#!/bin/sh
# Run Alembic migrations then hand off to uvicorn.
# Used as the Docker CMD in production — never run with --reload in prod.
set -e

echo "[entrypoint] Running Alembic migrations..."
alembic upgrade head

echo "[entrypoint] Seeding admin password..."
python seed_admin.py

echo "[entrypoint] Starting uvicorn..."
exec uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1 --log-level warning
