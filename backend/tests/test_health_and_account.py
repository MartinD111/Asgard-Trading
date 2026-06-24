"""
Tests for:
  - GET  /health              (main.py)
  - GET  /account/export      (routers/account.py)
  - DELETE /account           (routers/account.py)

All tests are unit-level: no real DB, Redis, or network calls.
Endpoint functions are called directly with AsyncMock dependencies,
following the same pattern as the rest of this test suite.
"""
from __future__ import annotations

import pytest
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

# ─── Shared test user ────────────────────────────────────────────────────────

TEST_USER = {
    "id": "aaaaaaaa-0000-0000-0000-000000000001",
    "username": "testuser",
    "is_admin": False,
    "avatar_id": "loki",
}


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _empty_db_execute():
    """AsyncMock DB whose execute() always returns an empty result set."""
    db = AsyncMock()
    empty = MagicMock()
    empty.fetchone.return_value = None
    empty.fetchall.return_value = []
    empty.keys.return_value = []
    db.execute = AsyncMock(return_value=empty)
    return db


def _mock_request(redis=None):
    """Minimal Request-like object carrying an app.state.redis."""
    req = MagicMock()
    req.app.state.redis = redis or AsyncMock()
    return req


# ─── GET /health ──────────────────────────────────────────────────────────────

class TestHealth:
    """health() is defined in main.py and references app.state.redis inline."""

    async def test_all_healthy_returns_ok(self):
        from main import app, health

        mock_redis = AsyncMock()
        app.state.redis = mock_redis

        mock_db = AsyncMock()

        @asynccontextmanager
        async def _session():
            yield mock_db

        with patch("db.database.AsyncSessionLocal", _session):
            result = await health()

        assert result["status"] == "ok"
        assert result["redis"] == "ok"
        assert result["db"] == "ok"

    async def test_redis_failure_degrades_status(self):
        from main import app, health

        mock_redis = AsyncMock()
        mock_redis.ping.side_effect = ConnectionError("refused")
        app.state.redis = mock_redis

        mock_db = AsyncMock()

        @asynccontextmanager
        async def _session():
            yield mock_db

        with patch("db.database.AsyncSessionLocal", _session):
            result = await health()

        assert result["status"] == "degraded"
        assert result["redis"] == "error"

    async def test_db_failure_degrades_status(self):
        from main import app, health

        mock_redis = AsyncMock()
        app.state.redis = mock_redis

        class _FailSession:
            async def __aenter__(self):
                raise OSError("DB unreachable")
            async def __aexit__(self, *a):
                pass

        with patch("db.database.AsyncSessionLocal", _FailSession):
            result = await health()

        assert result["status"] == "degraded"
        assert result["db"] == "error"

    async def test_no_redis_reports_not_initialized(self):
        from main import app, health

        app.state.redis = None

        mock_db = AsyncMock()

        @asynccontextmanager
        async def _session():
            yield mock_db

        with patch("db.database.AsyncSessionLocal", _session):
            result = await health()

        assert result["redis"] == "not_initialized"
        # status may still be ok if DB is fine
        assert result["db"] == "ok"

    async def test_response_includes_mode_field(self):
        from main import app, health

        app.state.redis = AsyncMock()
        mock_db = AsyncMock()

        @asynccontextmanager
        async def _session():
            yield mock_db

        with patch("db.database.AsyncSessionLocal", _session):
            result = await health()

        assert "mode" in result
        assert isinstance(result["mode"], str)

    async def test_both_failures_still_returns_dict(self):
        """health() must never raise — always returns a dict even when everything is down."""
        from main import app, health

        bad_redis = AsyncMock()
        bad_redis.ping.side_effect = RuntimeError("down")
        app.state.redis = bad_redis

        class _FailSession:
            async def __aenter__(self):
                raise RuntimeError("DB down")
            async def __aexit__(self, *a):
                pass

        with patch("db.database.AsyncSessionLocal", _FailSession):
            result = await health()

        assert isinstance(result, dict)
        assert result["status"] == "degraded"
        assert result["redis"] == "error"
        assert result["db"] == "error"


# ─── GET /account/export ──────────────────────────────────────────────────────

class TestAccountExport:
    """Tests for export_account_data() — calls function directly with mocked DB."""

    def _db_with_account(self):
        """DB mock that returns a minimal account row + empty lists everywhere else."""
        db = AsyncMock()

        acc_row = MagicMock()
        acc_row._fields = ("balance", "equity", "peak_equity", "drawdown", "created_at")
        acc_row.__iter__ = lambda self: iter([100_000.0, 100_000.0, 100_000.0, 0.0, "2024-01-01T00:00:00"])

        acc_result = MagicMock()
        acc_result.fetchone.return_value = acc_row

        empty = MagicMock()
        empty.fetchall.return_value = []
        empty.keys.return_value = []

        # execute() is called 4 times: virtual_accounts, positions, audit_log, broker_connections
        db.execute = AsyncMock(side_effect=[acc_result, empty, empty, empty])
        return db

    async def test_returns_user_id_and_username(self):
        from routers.account import export_account_data
        result = await export_account_data(current_user=TEST_USER, db=self._db_with_account())
        assert result["user"]["id"] == TEST_USER["id"]
        assert result["user"]["username"] == TEST_USER["username"]

    async def test_response_has_all_expected_keys(self):
        from routers.account import export_account_data
        result = await export_account_data(current_user=TEST_USER, db=self._db_with_account())
        assert set(result.keys()) == {"user", "account", "broker_connections", "positions", "audit_log"}

    async def test_account_data_present_when_row_exists(self):
        from routers.account import export_account_data
        result = await export_account_data(current_user=TEST_USER, db=self._db_with_account())
        assert result["account"] is not None

    async def test_positions_is_empty_list(self):
        from routers.account import export_account_data
        result = await export_account_data(current_user=TEST_USER, db=self._db_with_account())
        assert result["positions"] == []

    async def test_account_none_when_no_virtual_account_row(self):
        from routers.account import export_account_data

        db = AsyncMock()
        no_row = MagicMock()
        no_row.fetchone.return_value = None

        empty = MagicMock()
        empty.fetchall.return_value = []
        empty.keys.return_value = []

        db.execute = AsyncMock(side_effect=[no_row, empty, empty, empty])
        result = await export_account_data(current_user=TEST_USER, db=db)
        assert result["account"] is None

    async def test_positions_populated_from_db(self):
        from routers.account import export_account_data

        db = AsyncMock()

        acc_row = MagicMock()
        acc_row._fields = ("balance", "equity", "peak_equity", "drawdown", "created_at")
        acc_row.__iter__ = lambda self: iter([100_000.0, 100_000.0, 100_000.0, 0.0, "2024-01-01"])
        acc_result = MagicMock()
        acc_result.fetchone.return_value = acc_row

        pos_row = ("XAU_USD", "BUY", 1.0, 1800.0, "OPEN", "2024-01-01", None, 50.0)
        pos_result = MagicMock()
        pos_result.fetchall.return_value = [pos_row]
        pos_result.keys.return_value = ["symbol", "side", "quantity", "entry_price",
                                         "status", "opened_at", "closed_at", "realized_pnl"]

        empty = MagicMock()
        empty.fetchall.return_value = []
        empty.keys.return_value = []

        db.execute = AsyncMock(side_effect=[acc_result, pos_result, empty, empty])
        result = await export_account_data(current_user=TEST_USER, db=db)
        assert len(result["positions"]) == 1
        assert result["positions"][0]["symbol"] == "XAU_USD"


# ─── DELETE /account ──────────────────────────────────────────────────────────

class TestDeleteAccount:
    """Tests for delete_account() — calls function directly with mocked DB + Request."""

    async def test_returns_status_deleted(self):
        from routers.account import delete_account
        db = _empty_db_execute()
        request = _mock_request()
        result = await delete_account(request=request, current_user=TEST_USER, db=db)
        assert result["status"] == "deleted"

    async def test_returns_correct_user_id(self):
        from routers.account import delete_account
        db = _empty_db_execute()
        request = _mock_request()
        result = await delete_account(request=request, current_user=TEST_USER, db=db)
        assert result["user_id"] == TEST_USER["id"]

    async def test_commits_transaction(self):
        from routers.account import delete_account
        db = _empty_db_execute()
        request = _mock_request()
        await delete_account(request=request, current_user=TEST_USER, db=db)
        db.commit.assert_awaited_once()

    async def test_executes_four_sql_statements(self):
        """Deletes broker_connections, updates positions, deletes prediction_logs, updates users."""
        from routers.account import delete_account
        db = _empty_db_execute()
        request = _mock_request()
        await delete_account(request=request, current_user=TEST_USER, db=db)
        assert db.execute.await_count == 4

    async def test_clears_redis_keys(self):
        from routers.account import delete_account
        mock_redis = AsyncMock()
        db = _empty_db_execute()
        request = _mock_request(redis=mock_redis)
        await delete_account(request=request, current_user=TEST_USER, db=db)
        mock_redis.delete.assert_awaited_once()

    async def test_redis_delete_called_with_correct_user_keys(self):
        """Redis deletes the live-mode and kill-switch keys scoped to this user's ID."""
        from routers.account import delete_account
        mock_redis = AsyncMock()
        db = _empty_db_execute()
        request = _mock_request(redis=mock_redis)
        await delete_account(request=request, current_user=TEST_USER, db=db)
        call_args = mock_redis.delete.call_args[0]
        uid = TEST_USER["id"]
        assert f"user:{uid}:live_mode" in call_args
        assert f"kill_switch:user:{uid}" in call_args
