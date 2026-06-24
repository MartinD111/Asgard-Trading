from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from typing import Literal
from routers.auth import get_current_user

router = APIRouter(prefix="/api/backtest", tags=["Backtest"])

VALID_SYMBOLS = {"EUR_USD", "XAU_USD", "XAG_USD", "BTCUSDT"}
VALID_AGENTS = {"loki", "thor", "odin"}
MAX_CURVE_POINTS = 300


class BacktestRequest(BaseModel):
    symbol: str = "XAU_USD"
    days: int = 90
    agent: Literal["loki", "thor", "odin"] = "loki"
    initial_capital: float = 10_000.0

    @field_validator("symbol")
    @classmethod
    def symbol_valid(cls, v: str) -> str:
        if v not in VALID_SYMBOLS:
            raise ValueError(f"symbol must be one of {sorted(VALID_SYMBOLS)}")
        return v

    @field_validator("days")
    @classmethod
    def days_valid(cls, v: int) -> int:
        if not (7 <= v <= 365):
            raise ValueError("days must be between 7 and 365")
        return v

    @field_validator("initial_capital")
    @classmethod
    def capital_valid(cls, v: float) -> float:
        if not (100 <= v <= 10_000_000):
            raise ValueError("initial_capital must be between 100 and 10,000,000")
        return v


def _downsample(curve: list[float], target: int) -> list[float]:
    """LTTB-style simple uniform downsample to at most `target` points."""
    if len(curve) <= target:
        return curve
    step = len(curve) / target
    return [curve[int(i * step)] for i in range(target)] + [curve[-1]]


@router.post("/run")
async def run_backtest(
    req: BacktestRequest,
    _user: dict = Depends(get_current_user),
):
    try:
        from backtest.engine import run_backtest as _run
        metrics = await _run(
            symbol=req.symbol,
            days=req.days,
            agent=req.agent,
            initial_capital=req.initial_capital,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Backtest failed: {e}")

    summary = metrics.summary()
    equity_curve = _downsample(metrics.equity_curve, MAX_CURVE_POINTS)

    return {
        **summary,
        "equity_curve": [round(v, 2) for v in equity_curve],
        "winning_trades": metrics.winning_trades,
        "losing_trades": metrics.losing_trades,
        "avg_win": round(metrics.avg_win, 2),
        "avg_loss": round(metrics.avg_loss, 2),
    }
