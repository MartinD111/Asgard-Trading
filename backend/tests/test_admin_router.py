"""
Unit tests for the admin router.

DB and admin-auth dependencies are fully mocked — no real DB or JWT required.
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers.admin import router as admin_router
from routers.auth import get_current_admin
from db.database import get_db

# ─── Test app setup ───────────────────────────────────────────────────────────

_ADMIN = {"id": "admin-uuid", "username": "admin", "is_admin": True}

_app = FastAPI()
_app.include_router(admin_router)
_app.dependency_overrides[get_current_admin] = lambda: _ADMIN


def _make_mock_db() -> AsyncMock:
    db = AsyncMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    return db


def _with_db(mock_db: AsyncMock):
    async def _override():
        yield mock_db
    _app.dependency_overrides[get_db] = _override


# ─── GET /api/admin/users ─────────────────────────────────────────────────────

class TestGetUsers:
    def test_returns_user_list(self):
        uid = str(uuid.uuid4())
        row = MagicMock()
        row._mapping = {
            "id": uid, "username": "alice",
            "is_admin": False, "avatar_id": "odin",
            "created_at": "2024-01-01T00:00:00",
        }

        mock_db = _make_mock_db()
        res = MagicMock()
        res.fetchall.return_value = [row]
        mock_db.execute = AsyncMock(return_value=res)
        _with_db(mock_db)

        resp = TestClient(_app).get("/api/admin/users")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["username"] == "alice"

    def test_returns_empty_list_when_no_users(self):
        mock_db = _make_mock_db()
        res = MagicMock()
        res.fetchall.return_value = []
        mock_db.execute = AsyncMock(return_value=res)
        _with_db(mock_db)

        resp = TestClient(_app).get("/api/admin/users")
        assert resp.status_code == 200
        assert resp.json() == []


# ─── POST /api/admin/users ────────────────────────────────────────────────────

class TestCreateUser:
    def test_creates_user_and_returns_201(self):
        uid = str(uuid.uuid4())
        user_row = (uid, "newuser", False, "odin")

        mock_db = _make_mock_db()
        insert_res = MagicMock()
        insert_res.fetchone.return_value = user_row
        va_res = MagicMock()
        mock_db.execute = AsyncMock(side_effect=[insert_res, va_res])
        _with_db(mock_db)

        resp = TestClient(_app).post(
            "/api/admin/users",
            json={"username": "newuser", "password": "secret123"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["username"] == "newuser"
        assert body["id"] == uid
        assert body["is_admin"] is False

    def test_hashes_password_before_insert(self):
        uid = str(uuid.uuid4())
        user_row = (uid, "newuser", False, "odin")

        mock_db = _make_mock_db()
        insert_res = MagicMock()
        insert_res.fetchone.return_value = user_row
        mock_db.execute = AsyncMock(side_effect=[insert_res, MagicMock()])
        _with_db(mock_db)

        TestClient(_app).post(
            "/api/admin/users",
            json={"username": "newuser", "password": "plain"},
        )

        # The param sent to INSERT should not be the plain password
        params = mock_db.execute.call_args_list[0][0][1]
        assert params["p"] != "plain"

    def test_db_error_returns_400(self):
        mock_db = _make_mock_db()
        mock_db.execute = AsyncMock(side_effect=Exception("duplicate key"))
        _with_db(mock_db)

        resp = TestClient(_app).post(
            "/api/admin/users",
            json={"username": "dupuser", "password": "pass"},
        )
        assert resp.status_code == 400
        assert "Error creating user" in resp.json()["detail"]


# ─── DELETE /api/admin/users/{user_id} ───────────────────────────────────────

class TestDeleteUser:
    def test_deletes_user_returns_200(self):
        uid = str(uuid.uuid4())
        mock_db = _make_mock_db()
        mock_db.execute = AsyncMock(return_value=MagicMock())
        _with_db(mock_db)

        resp = TestClient(_app).delete(f"/api/admin/users/{uid}")
        assert resp.status_code == 200
        assert resp.json()["message"] == "User deleted successfully"

    def test_delete_calls_execute_with_user_id(self):
        uid = str(uuid.uuid4())
        mock_db = _make_mock_db()
        mock_db.execute = AsyncMock(return_value=MagicMock())
        _with_db(mock_db)

        TestClient(_app).delete(f"/api/admin/users/{uid}")
        params = mock_db.execute.call_args[0][1]
        assert params["id"] == uid


# ─── GET /api/admin/stats ─────────────────────────────────────────────────────

class TestGetStats:
    def test_returns_pnl_per_user(self):
        uid = str(uuid.uuid4())

        pnl_row = (150.0, 300.0)      # pnl_24h, pnl_7d

        user_row = MagicMock()
        user_row._mapping = {"id": uid, "username": "alice"}

        pnl_res = MagicMock()
        pnl_res.fetchone.return_value = pnl_row

        users_res = MagicMock()
        users_res.fetchall.return_value = [user_row]

        mock_db = _make_mock_db()
        mock_db.execute = AsyncMock(side_effect=[pnl_res, users_res])
        _with_db(mock_db)

        resp = TestClient(_app).get("/api/admin/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["username"] == "alice"
        assert data[0]["pnl_24h"] == 150.0
        assert data[0]["pnl_7d"] == 300.0

    def test_returns_zero_pnl_when_no_closed_positions(self):
        pnl_row = (0.0, 0.0)

        user_row = MagicMock()
        user_row._mapping = {"id": str(uuid.uuid4()), "username": "bob"}

        pnl_res = MagicMock()
        pnl_res.fetchone.return_value = pnl_row
        users_res = MagicMock()
        users_res.fetchall.return_value = [user_row]

        mock_db = _make_mock_db()
        mock_db.execute = AsyncMock(side_effect=[pnl_res, users_res])
        _with_db(mock_db)

        resp = TestClient(_app).get("/api/admin/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data[0]["pnl_24h"] == 0.0
        assert data[0]["pnl_7d"] == 0.0
