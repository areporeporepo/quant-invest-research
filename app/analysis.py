"""Assemble a full quant snapshot from a price series.

This is descriptive analytics only. It reports what the numbers *are*; it does
not tell you what to *do*. Interpretation and disclaimers live in the API layer
and the README.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Optional

from . import indicators as ind
from .data_providers import PriceSeries


@dataclass
class Snapshot:
    ticker: str
    source: str
    is_real_data: bool
    n_observations: int
    last_price: Optional[float]
    total_return: Optional[float]
    annualized_volatility: Optional[float]
    sharpe_ratio: Optional[float]
    max_drawdown: Optional[float]
    sma_20: Optional[float]
    sma_50: Optional[float]
    ema_20: Optional[float]
    rsi_14: Optional[float]
    trend: str
    data_note: str


def _trend_label(last: Optional[float], sma20: Optional[float],
                 sma50: Optional[float]) -> str:
    if last is None or sma20 is None or sma50 is None:
        return "insufficient-data"
    if last > sma20 > sma50:
        return "uptrend"
    if last < sma20 < sma50:
        return "downtrend"
    return "mixed"


def build_snapshot(series: PriceSeries, risk_free: float = 0.04) -> Snapshot:
    closes = series.closes
    last = closes[-1] if closes else None
    sma20 = ind.sma(closes, 20)
    sma50 = ind.sma(closes, 50)
    return Snapshot(
        ticker=series.ticker,
        source=series.source,
        is_real_data=series.is_real,
        n_observations=len(closes),
        last_price=last,
        total_return=ind.total_return(closes),
        annualized_volatility=ind.annualized_volatility(closes),
        sharpe_ratio=ind.sharpe_ratio(closes, risk_free_annual=risk_free),
        max_drawdown=ind.max_drawdown(closes),
        sma_20=sma20,
        sma_50=sma50,
        ema_20=ind.ema(closes, 20),
        rsi_14=ind.rsi(closes, 14),
        trend=_trend_label(last, sma20, sma50),
        data_note=series.note,
    )


def snapshot_dict(series: PriceSeries, risk_free: float = 0.04) -> dict:
    return asdict(build_snapshot(series, risk_free))
