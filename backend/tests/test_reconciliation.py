"""
Unit tests for the broker reconciliation service.

All DB and broker calls are mocked — no real connections required.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest

from services.reconciliation import (
    _mark_order,
    _update_position_fill,
    _close_position_stub,
    _reconcile,
)


# ─── Shared helpers ───────────────────────────────────────────────────────────

def _make_db_ctx(mock_db: AsyncMock):
    """Return a patched AsyncSessionLocal context manager that yields mock_db."""
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=mock_db)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx


def _pending_row(
    *,
    broker: str = "oanda",
    broker_order_id: str = "broker-oid-1",
    age_seconds: int = 60,
    position_id: str | None = "pos-uuid-1",
) -> tuple:
    created_at = datetime.now(timezone.utc) - timedelta(seconds=age_seconds)
    return (
        "order-uuid-1",   # id
        "user-uuid-1",    # user_id
        position_id,      # position_id
        broker,           # broker
        broker_order_id,  # broker_order_id
        "XAU_USD",        # symbol
        "0.1",            # quantity
        created_at,       # created_at
    )


# ─── _mark_order ─────────────────────────────────────────────────────────────

async def test_mark_order_executes_update_and_commits():
    mock_db = AsyncMock()
    with patch("db.database.AsyncSessionLocal", return_value=_make_db_ctx(mock_db)):
        await _mark_order("order-uuid-1", "FILLED", 1900.5, 0.1, None)

    mock_db.execute.assert_called_once()
    mock_db.commit.assert_called_once()


async def test_mark_order_passes_correct_params():
    mock_db = AsyncMock()
    with patch("db.database.AsyncSessionLocal", return_value=_make_db_ctx(mock_db)):
        await _mark_order("oid", "CANCELLED", 0.0, 0.0, "Timeout")

    params = mock_db.execute.call_args[0][1]
    assert params["st"] == "CANCELLED"
    assert params["fp"] == 0.0
    assert params["fq"] == 0.0
    assert params["err"] == "Timeout"
    assert params["id"] == "oid"


# ─── _update_position_fill ────────────────────────────────────────────────────

async def test_update_position_fill_sets_entry_and_current_price():
    mock_db = AsyncMock()
    with patch("db.database.AsyncSessionLocal", return_value=_make_db_ctx(mock_db)):
        await _update_position_fill("pos-uuid-1", 1905.0, 0.05)

    params = mock_db.execute.call_args[0][1]
    assert params["fp"] == 1905.0
    assert params["fq"] == 0.05
    assert params["id"] == "pos-uuid-1"
    mock_db.commit.assert_called_once()


# ─── _close_position_stub ─────────────────────────────────────────────────────

async def test_close_position_stub_runs_update_and_audit_insert():
    mock_db = AsyncMock()
    with patch("db.database.AsyncSessionLocal", return_value=_make_db_ctx(mock_db)):
        await _close_position_stub("pos-uuid-1", "order-uuid-1", "Broker timeout")

    assert mock_db.execute.call_count == 2
    mock_db.commit.assert_called_once()


async def test_close_position_stub_passes_reason_in_payload():
    import json

    mock_db = AsyncMock()
    with patch("db.database.AsyncSessionLocal", return_value=_make_db_ctx(mock_db)):
        await _close_position_stub("pos-uuid-1", "order-uuid-1", "Broker cancelled")

    # Second execute is the audit_log INSERT; check the payload param
    second_call_params = mock_db.execute.call_args_list[1][0][1]
    payload = json.loads(second_call_params["payload"])
    assert payload["reason"] == "Broker cancelled"


# ─── _reconcile — paper broker path ──────────────────────────────────────────

async def test_reconcile_paper_order_marks_filled():
    row = _pending_row(broker="paper", broker_order_id="")

    mock_db = AsyncMock()
    res = MagicMock()
    res.fetchall.return_value = [row]
    mock_db.execute = AsyncMock(return_value=res)

    with patch("db.database.AsyncSessionLocal", return_value=_make_db_ctx(mock_db)), \
         patch("services.reconciliation._mark_order", new=AsyncMock()) as mock_mark:
        await _reconcile(redis=AsyncMock())

    mock_mark.assert_called_once_with("order-uuid-1", "FILLED", 0.0, 0.1, None)


async def test_reconcile_no_pending_rows_returns_early():
    mock_db = AsyncMock()
    res = MagicMock()
    res.fetchall.return_value = []
    mock_db.execute = AsyncMock(return_value=res)

    with patch("db.database.AsyncSessionLocal", return_value=_make_db_ctx(mock_db)), \
         patch("services.reconciliation._mark_order", new=AsyncMock()) as mock_mark:
        await _reconcile(redis=AsyncMock())

    mock_mark.assert_not_called()


# ─── _reconcile — hard timeout path ──────────────────────────────────────────

async def test_reconcile_timed_out_order_is_cancelled():
    # Order created 6 minutes ago → past the 5-minute PENDING_TIMEOUT
    row = _pending_row(broker="oanda", broker_order_id="oanda-oid", age_seconds=370)

    mock_db = AsyncMock()
    res = MagicMock()
    res.fetchall.return_value = [row]
    mock_db.execute = AsyncMock(return_value=res)

    with patch("db.database.AsyncSessionLocal", return_value=_make_db_ctx(mock_db)), \
         patch("services.reconciliation._mark_order", new=AsyncMock()) as mock_mark, \
         patch("services.reconciliation._close_position_stub", new=AsyncMock()) as mock_close:
        await _reconcile(redis=AsyncMock())

    mock_mark.assert_called_once()
    args = mock_mark.call_args[0]
    assert args[1] == "CANCELLED"
    mock_close.assert_called_once_with("pos-uuid-1", "order-uuid-1", "Broker order timeout")


# ─── _reconcile — live broker FILLED path ────────────────────────────────────

async def test_reconcile_filled_broker_response_updates_position():
    from brokers.base import OrderResult

    row = _pending_row(broker="oanda", broker_order_id="oanda-oid", age_seconds=60)

    mock_db = AsyncMock()
    res = MagicMock()
    res.fetchall.return_value = [row]
    mock_db.execute = AsyncMock(return_value=res)

    filled_result = OrderResult(
        broker_order_id="oanda-oid", status="FILLED",
        filled_price=1910.0, filled_qty=0.1,
    )
    mock_broker = AsyncMock()
    mock_broker.get_order_status = AsyncMock(return_value=filled_result)

    with patch("db.database.AsyncSessionLocal", return_value=_make_db_ctx(mock_db)), \
         patch("brokers.router.get_broker_for_user", return_value=mock_broker), \
         patch("services.reconciliation._mark_order", new=AsyncMock()) as mock_mark, \
         patch("services.reconciliation._update_position_fill", new=AsyncMock()) as mock_fill:
        await _reconcile(redis=AsyncMock())

    mock_mark.assert_called_once_with("order-uuid-1", "FILLED", 1910.0, 0.1, None)
    mock_fill.assert_called_once_with("pos-uuid-1", 1910.0, 0.1)


# ─── _reconcile — live broker CANCELLED path ─────────────────────────────────

async def test_reconcile_cancelled_broker_response_closes_position():
    from brokers.base import OrderResult

    row = _pending_row(broker="coinbase", broker_order_id="cb-oid", age_seconds=60)

    mock_db = AsyncMock()
    res = MagicMock()
    res.fetchall.return_value = [row]
    mock_db.execute = AsyncMock(return_value=res)

    cancelled_result = OrderResult(
        broker_order_id="cb-oid", status="CANCELLED",
        filled_price=0.0, filled_qty=0.0, error="order expired",
    )
    mock_broker = AsyncMock()
    mock_broker.get_order_status = AsyncMock(return_value=cancelled_result)

    with patch("db.database.AsyncSessionLocal", return_value=_make_db_ctx(mock_db)), \
         patch("brokers.router.get_broker_for_user", return_value=mock_broker), \
         patch("services.reconciliation._mark_order", new=AsyncMock()) as mock_mark, \
         patch("services.reconciliation._close_position_stub", new=AsyncMock()) as mock_close:
        await _reconcile(redis=AsyncMock())

    mock_mark.assert_called_once()
    assert mock_mark.call_args[0][1] == "CANCELLED"
    mock_close.assert_called_once_with("pos-uuid-1", "order-uuid-1", "Broker cancelled")


# ─── _reconcile — broker still PENDING (no-op) ───────────────────────────────

async def test_reconcile_pending_broker_response_leaves_order():
    from brokers.base import OrderResult

    row = _pending_row(broker="oanda", broker_order_id="oanda-oid", age_seconds=60)

    mock_db = AsyncMock()
    res = MagicMock()
    res.fetchall.return_value = [row]
    mock_db.execute = AsyncMock(return_value=res)

    pending_result = OrderResult(
        broker_order_id="oanda-oid", status="PENDING",
        filled_price=0.0, filled_qty=0.0,
    )
    mock_broker = AsyncMock()
    mock_broker.get_order_status = AsyncMock(return_value=pending_result)

    with patch("db.database.AsyncSessionLocal", return_value=_make_db_ctx(mock_db)), \
         patch("brokers.router.get_broker_for_user", return_value=mock_broker), \
         patch("services.reconciliation._mark_order", new=AsyncMock()) as mock_mark, \
         patch("services.reconciliation._close_position_stub", new=AsyncMock()) as mock_close:
        await _reconcile(redis=AsyncMock())

    mock_mark.assert_not_called()
    mock_close.assert_not_called()
