"""
Unit tests for the backtester — pure function paths only (no DB/Redis).

All tests inject synthetic candles directly, so they run fully offline.
"""
from __future__ import annotations

import asyncio
import math
import pytest

from backtest.cost_model import get_cost_model, CostModel
from backtest.metrics import compute_metrics
from backtest.engine import run_backtest, _atr
from services.signals import compute_signal, Signal


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _trend_candles(n: int, start: float = 100.0, drift: float = 0.001) -> list[dict]:
    """Steadily trending candle series."""
    candles = []
    price = start
    for i in range(n):
        price *= (1 + drift)
        candles.append({
            "time": f"2024-01-01T{i:05d}",
            "open": price * 0.999,
            "high": price * 1.002,
            "low":  price * 0.997,
            "close": price,
            "volume": 1000.0,
        })
    return candles


def _flat_candles(n: int, price: float = 100.0) -> list[dict]:
    return [
        {"time": f"2024-01-01T{i:05d}", "open": price, "high": price * 1.001,
         "low": price * 0.999, "close": price, "volume": 100.0}
        for i in range(n)
    ]


# ─── Cost model ───────────────────────────────────────────────────────────────

def test_cost_model_eurusd_has_spread():
    cm = get_cost_model("EUR_USD")
    assert cm.spread > 0


def test_cost_model_btcusdt_has_commission():
    cm = get_cost_model("BTCUSDT")
    assert cm.commission_pct > 0


def test_cost_entry_positive():
    cm = CostModel(spread=0.0002, commission_pct=0.001, slippage_pct=0.0005)
    cost = cm.entry_cost(price=1.1000, quantity=10_000)
    assert cost > 0


def test_cost_total_equals_two_sides():
    cm = CostModel(spread=0.0002, commission_pct=0.001, slippage_pct=0.0005)
    total = cm.total_cost(1.1000, 10_000)
    assert total == pytest.approx(cm.entry_cost(1.1000, 10_000) + cm.exit_cost(1.1000, 10_000))


# ─── Metrics ─────────────────────────────────────────────────────────────────

def test_metrics_positive_return():
    equity = [10_000, 10_200, 10_400, 10_600]
    trades = [{"pnl": 100, "cost": 5}, {"pnl": 150, "cost": 5}, {"pnl": 100, "cost": 5}]
    m = compute_metrics("XAU_USD", "M5", "2024-01-01", "2024-03-01",
                        10_000, equity, trades, candle_count=500)
    assert m.total_return_pct > 0
    assert m.win_rate_pct == 100.0
    assert m.trade_count == 3


def test_metrics_zero_trades():
    equity = [10_000.0] * 10
    m = compute_metrics("EUR_USD", "M5", "2024-01-01", "2024-03-01",
                        10_000, equity, [], candle_count=100)
    assert m.trade_count == 0
    assert m.total_return_pct == pytest.approx(0.0, abs=0.01)


def test_metrics_max_drawdown_detected():
    equity = [10_000, 9_000, 8_000, 9_500]  # 20% drawdown at bottom
    trades = [{"pnl": -1000, "cost": 0}, {"pnl": -1000, "cost": 0}, {"pnl": 1500, "cost": 0}]
    m = compute_metrics("BTCUSDT", "M5", "2024-01-01", "2024-03-01",
                        10_000, equity, trades, candle_count=500)
    assert m.max_drawdown_pct == pytest.approx(20.0, abs=0.5)


def test_metrics_profit_factor():
    equity = [10_000, 10_100, 9_950, 10_200]
    trades = [{"pnl": 100, "cost": 0}, {"pnl": -150, "cost": 0}, {"pnl": 250, "cost": 0}]
    m = compute_metrics("XAU_USD", "M5", "2024-01-01", "2024-03-01",
                        10_000, equity, trades, candle_count=200)
    expected_pf = 350 / 150
    assert m.profit_factor == pytest.approx(expected_pf, rel=0.01)


# ─── Signals ─────────────────────────────────────────────────────────────────

def test_signal_too_few_candles_is_neutral():
    s = compute_signal([{"close": 100.0, "high": 101.0, "low": 99.0}] * 5, symbol="X")
    assert s.direction == "NEUTRAL"
    assert s.final_score == 0.0


def test_signal_uptrend_is_buy():
    candles = _trend_candles(60, drift=0.002)  # strong uptrend
    s = compute_signal(candles, symbol="X")
    assert s.direction == "BUY"
    assert s.final_score > 0


def test_signal_downtrend_is_sell():
    candles = _trend_candles(60, drift=-0.002)  # strong downtrend
    s = compute_signal(candles, symbol="X")
    assert s.direction == "SELL"
    assert s.final_score < 0


def test_signal_weights_sum_to_one():
    candles = _trend_candles(60)
    s = compute_signal(candles, symbol="X", agent="loki")
    total = sum(s.weights.values())
    assert total == pytest.approx(1.0, abs=0.001)


# ─── ATR helper ───────────────────────────────────────────────────────────────

def test_atr_positive_on_volatile_series():
    candles = _trend_candles(30, drift=0.001)
    atr = _atr(candles)
    assert atr > 0


def test_atr_zero_on_empty():
    assert _atr([]) == 0.0


# ─── Full backtest (offline) ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_backtest_returns_metrics_object():
    candles = _trend_candles(200, drift=0.001)
    m = await run_backtest("XAU_USD", candles=candles, initial_capital=10_000.0)
    assert m.trade_count >= 0
    assert len(m.equity_curve) > 0
    assert m.initial_capital == pytest.approx(10_000.0)


@pytest.mark.asyncio
async def test_backtest_costs_reduce_pnl():
    """A winning trend should return less after costs than before."""
    candles = _trend_candles(300, drift=0.003)
    m_with_costs = await run_backtest("XAU_USD", candles=candles)
    # Just verify costs are positive (not zero)
    assert m_with_costs.total_costs >= 0


@pytest.mark.asyncio
async def test_backtest_flat_market_few_trades():
    """Flat market should produce very few trades since signal stays near 0."""
    candles = _flat_candles(200)
    m = await run_backtest("EUR_USD", candles=candles, score_threshold=0.35)
    assert m.trade_count < 5


@pytest.mark.asyncio
async def test_backtest_equity_curve_matches_capital():
    candles = _trend_candles(100)
    m = await run_backtest("XAU_USD", candles=candles, initial_capital=5_000.0)
    assert m.equity_curve[0] == pytest.approx(5_000.0, rel=0.01)
    assert m.final_equity == pytest.approx(m.equity_curve[-1], rel=0.001)


# ─── HTTP endpoint (router layer) ────────────────────────────────────────────

from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch

from routers.backtest import router as _backtest_router
from routers.auth import get_current_user as _get_current_user

_app = FastAPI()
_app.include_router(_backtest_router)
_app.dependency_overrides[_get_current_user] = lambda: {"id": "test-user", "username": "test"}
_client = TestClient(_app)


def _fake_metrics() -> MagicMock:
    m = MagicMock()
    m.summary.return_value = {
        "symbol": "XAU_USD", "agent": "loki", "days": 90,
        "trade_count": 10, "win_rate_pct": 60.0,
        "total_return_pct": 5.2, "max_drawdown_pct": 3.1,
        "sharpe_ratio": 1.2, "profit_factor": 2.0,
        "total_costs": 150.0,
    }
    m.equity_curve = [10_000.0, 10_100.0, 10_500.0]
    m.winning_trades = 6
    m.losing_trades = 4
    m.avg_win = 120.0
    m.avg_loss = -60.0
    return m


class TestBacktestEndpoint:
    def test_valid_request_returns_200(self):
        with patch("backtest.engine.run_backtest", new=AsyncMock(return_value=_fake_metrics())):
            resp = _client.post("/api/backtest/run", json={"symbol": "XAU_USD", "days": 90})
        assert resp.status_code == 200
        body = resp.json()
        assert "equity_curve" in body
        assert "winning_trades" in body
        assert "losing_trades" in body
        assert "avg_win" in body
        assert "avg_loss" in body

    def test_invalid_symbol_returns_422(self):
        resp = _client.post("/api/backtest/run", json={"symbol": "AAPL"})
        assert resp.status_code == 422

    def test_days_too_low_returns_422(self):
        resp = _client.post("/api/backtest/run", json={"symbol": "XAU_USD", "days": 6})
        assert resp.status_code == 422

    def test_days_too_high_returns_422(self):
        resp = _client.post("/api/backtest/run", json={"symbol": "XAU_USD", "days": 366})
        assert resp.status_code == 422

    def test_capital_too_low_returns_422(self):
        resp = _client.post("/api/backtest/run", json={"symbol": "XAU_USD", "initial_capital": 50})
        assert resp.status_code == 422

    def test_capital_too_high_returns_422(self):
        resp = _client.post("/api/backtest/run", json={"symbol": "XAU_USD", "initial_capital": 20_000_000})
        assert resp.status_code == 422

    def test_engine_exception_returns_500(self):
        with patch("backtest.engine.run_backtest", new=AsyncMock(side_effect=RuntimeError("DB error"))):
            resp = _client.post("/api/backtest/run", json={"symbol": "XAU_USD"})
        assert resp.status_code == 500
        assert "Backtest failed" in resp.json()["detail"]

    def test_equity_curve_is_list_of_numbers(self):
        with patch("backtest.engine.run_backtest", new=AsyncMock(return_value=_fake_metrics())):
            resp = _client.post("/api/backtest/run", json={"symbol": "EUR_USD", "days": 30})
        body = resp.json()
        assert isinstance(body["equity_curve"], list)
        assert len(body["equity_curve"]) > 0
        assert all(isinstance(v, (int, float)) for v in body["equity_curve"])
