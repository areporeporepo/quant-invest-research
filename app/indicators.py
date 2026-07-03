"""Quant indicators.

Pure functions over a price series (list or 1-D array of closing prices,
oldest first). No network, no I/O — so they are deterministic and unit-testable.
Every function tolerates short/degenerate input by returning None rather than
raising, so callers can render partial analyses.
"""

from __future__ import annotations

import math
from typing import Optional, Sequence

TRADING_DAYS = 252  # convention for annualizing daily stats


def _clean(prices: Sequence[float]) -> list[float]:
    return [float(p) for p in prices if p is not None and not math.isnan(float(p))]


def daily_returns(prices: Sequence[float]) -> list[float]:
    """Simple period-over-period returns: r_t = p_t / p_{t-1} - 1."""
    p = _clean(prices)
    return [p[i] / p[i - 1] - 1.0 for i in range(1, len(p)) if p[i - 1] != 0]


def total_return(prices: Sequence[float]) -> Optional[float]:
    p = _clean(prices)
    if len(p) < 2 or p[0] == 0:
        return None
    return p[-1] / p[0] - 1.0


def mean(xs: Sequence[float]) -> Optional[float]:
    xs = list(xs)
    return sum(xs) / len(xs) if xs else None


def stdev(xs: Sequence[float]) -> Optional[float]:
    """Sample standard deviation (n-1)."""
    xs = list(xs)
    if len(xs) < 2:
        return None
    m = sum(xs) / len(xs)
    var = sum((x - m) ** 2 for x in xs) / (len(xs) - 1)
    return math.sqrt(var)


def annualized_volatility(prices: Sequence[float], periods: int = TRADING_DAYS) -> Optional[float]:
    sd = stdev(daily_returns(prices))
    return sd * math.sqrt(periods) if sd is not None else None


def sma(prices: Sequence[float], window: int) -> Optional[float]:
    """Simple moving average of the most recent `window` closes."""
    p = _clean(prices)
    if len(p) < window or window <= 0:
        return None
    return sum(p[-window:]) / window


def ema(prices: Sequence[float], window: int) -> Optional[float]:
    """Exponential moving average (most recent value of the EMA series)."""
    p = _clean(prices)
    if len(p) < window or window <= 0:
        return None
    k = 2.0 / (window + 1.0)
    e = sum(p[:window]) / window  # seed with SMA
    for price in p[window:]:
        e = price * k + e * (1.0 - k)
    return e


def rsi(prices: Sequence[float], window: int = 14) -> Optional[float]:
    """Wilder's Relative Strength Index over `window` periods (0-100)."""
    p = _clean(prices)
    if len(p) <= window:
        return None
    gains, losses = [], []
    for i in range(1, len(p)):
        change = p[i] - p[i - 1]
        gains.append(max(change, 0.0))
        losses.append(max(-change, 0.0))
    avg_gain = sum(gains[:window]) / window
    avg_loss = sum(losses[:window]) / window
    for i in range(window, len(gains)):
        avg_gain = (avg_gain * (window - 1) + gains[i]) / window
        avg_loss = (avg_loss * (window - 1) + losses[i]) / window
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def sharpe_ratio(prices: Sequence[float], risk_free_annual: float = 0.0,
                 periods: int = TRADING_DAYS) -> Optional[float]:
    """Annualized Sharpe ratio from the daily return series."""
    rets = daily_returns(prices)
    m, sd = mean(rets), stdev(rets)
    if m is None or sd in (None, 0):
        return None
    rf_daily = risk_free_annual / periods
    return ((m - rf_daily) / sd) * math.sqrt(periods)


def max_drawdown(prices: Sequence[float]) -> Optional[float]:
    """Largest peak-to-trough decline as a negative fraction (e.g. -0.35)."""
    p = _clean(prices)
    if len(p) < 2:
        return None
    peak = p[0]
    worst = 0.0
    for price in p:
        peak = max(peak, price)
        if peak > 0:
            worst = min(worst, price / peak - 1.0)
    return worst
