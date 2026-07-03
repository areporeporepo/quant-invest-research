"""Descriptive signal set and group comparison.

"Signals" here are DESCRIPTIVE LABELS derived from historical data — trend
state, momentum, volatility regime, drawdown state, RSI zone. They summarize
what the series has been doing; they are not predictions and not advice. The
`outlook` string is assembled from the same labels and inherits the same
limits.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Optional

from . import indicators as ind
from .data_providers import PriceSeries, ProviderError, get_price_series


@dataclass
class Signal:
    name: str
    value: str
    detail: str


def derive_signals(series: PriceSeries) -> list[Signal]:
    closes = series.closes
    out: list[Signal] = []
    last = closes[-1] if closes else None
    sma20, sma50 = ind.sma(closes, 20), ind.sma(closes, 50)
    sma200 = ind.sma(closes, 200)

    # Trend state from moving-average stack
    if last and sma20 and sma50:
        if last > sma20 > sma50:
            out.append(Signal("trend", "uptrend",
                              "price above SMA20 above SMA50"))
        elif last < sma20 < sma50:
            out.append(Signal("trend", "downtrend",
                              "price below SMA20 below SMA50"))
        else:
            out.append(Signal("trend", "mixed",
                              "moving averages not aligned"))
    if last and sma200:
        out.append(Signal("long_term", "above SMA200" if last > sma200
                          else "below SMA200",
                          f"price {last:.2f} vs SMA200 {sma200:.2f}"))

    # Momentum: ~3-month (63 trading days) return
    if len(closes) > 63 and closes[-64] != 0:
        r3m = closes[-1] / closes[-64] - 1.0
        label = "positive" if r3m > 0.05 else "negative" if r3m < -0.05 else "flat"
        out.append(Signal("momentum_3m", label, f"{r3m:+.1%} over ~63 sessions"))

    # RSI zone
    rsi = ind.rsi(closes, 14)
    if rsi is not None:
        zone = "overbought" if rsi > 70 else "oversold" if rsi < 30 else "neutral"
        out.append(Signal("rsi_zone", zone, f"RSI14 = {rsi:.1f}"))

    # Volatility regime
    vol = ind.annualized_volatility(closes)
    if vol is not None:
        regime = "low" if vol < 0.20 else "moderate" if vol < 0.40 else "high"
        out.append(Signal("volatility_regime", regime,
                          f"annualized volatility {vol:.1%}"))

    # Drawdown state: how far below the window peak we sit now
    if closes:
        peak = max(closes)
        if peak > 0:
            off_peak = closes[-1] / peak - 1.0
            state = ("at/near peak" if off_peak > -0.05
                     else "pullback" if off_peak > -0.20 else "deep drawdown")
            out.append(Signal("drawdown_state", state,
                              f"{off_peak:+.1%} vs window peak"))
    return out


def outlook_text(signals: list[Signal]) -> str:
    """Plain-language summary of the descriptive labels. Not a forecast."""
    by = {s.name: s for s in signals}
    parts = []
    if "trend" in by:
        parts.append(f"the trend reads {by['trend'].value}")
    if "momentum_3m" in by:
        parts.append(f"3-month momentum is {by['momentum_3m'].value} "
                     f"({by['momentum_3m'].detail})")
    if "volatility_regime" in by:
        parts.append(f"volatility is {by['volatility_regime'].value}")
    if "drawdown_state" in by:
        parts.append(f"price is {by['drawdown_state'].detail} "
                     f"({by['drawdown_state'].value})")
    body = "; ".join(parts) if parts else "insufficient data"
    return (f"Descriptively, {body}. These labels summarize the past window "
            "only — they are not a prediction and not advice.")


# ---------------------------------------------------------------------------
# Vingroup family comparison
# ---------------------------------------------------------------------------
# Listed Vingroup-related tickers served by the DNSE feed. NOTE: VinFast Auto
# trades on NASDAQ as VFS in USD; the symbol "VFS" on Vietnamese exchanges is
# a DIFFERENT company (a securities firm) — deliberately excluded to avoid a
# wrong-asset trap.
GROUP_TICKERS: dict[str, str] = {
    "VIC": "Vingroup JSC (parent conglomerate)",
    "VHM": "Vinhomes (residential real estate)",
    "VRE": "Vincom Retail (malls/retail property)",
    "VPL": "Vinpearl (hospitality/leisure)",
    "VEF": "Vietnam Exhibition Fair Centre (Vingroup affiliate)",
}


def _pearson(xs: list[float], ys: list[float]) -> Optional[float]:
    n = min(len(xs), len(ys))
    if n < 20:  # too short to be meaningful
        return None
    xs, ys = xs[-n:], ys[-n:]
    mx, my = sum(xs) / n, sum(ys) / n
    cov = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    vx = sum((a - mx) ** 2 for a in xs)
    vy = sum((b - my) ** 2 for b in ys)
    if vx == 0 or vy == 0:
        return None
    return cov / (vx ** 0.5 * vy ** 0.5)


def group_comparison(tickers: Optional[list[str]] = None,
                     risk_free: float = 0.04) -> dict:
    """Side-by-side quant summary + return correlations for a ticker group."""
    names = tickers or list(GROUP_TICKERS)
    rows, rets, errors = {}, {}, {}
    for t in names:
        try:
            s = get_price_series(t)
        except ProviderError as e:
            errors[t] = str(e)
            continue
        closes = s.closes
        rows[s.ticker] = {
            "description": GROUP_TICKERS.get(s.ticker, ""),
            "source": s.source,
            "is_real_data": s.is_real,
            "n_observations": len(closes),
            "last_price": closes[-1] if closes else None,
            "total_return": ind.total_return(closes),
            "annualized_volatility": ind.annualized_volatility(closes),
            "sharpe_ratio": ind.sharpe_ratio(closes, risk_free_annual=risk_free),
            "max_drawdown": ind.max_drawdown(closes),
            "rsi_14": ind.rsi(closes, 14),
            "signals": [asdict(x) for x in derive_signals(s)],
        }
        rets[s.ticker] = ind.daily_returns(closes)
    keys = list(rows)
    correlations = {
        f"{a}/{b}": _pearson(rets[a], rets[b])
        for i, a in enumerate(keys) for b in keys[i + 1:]
    }
    return {
        "group": rows,
        "return_correlations": correlations,
        "errors": errors,
        "note": "VinFast (NASDAQ: VFS, USD) is intentionally excluded: the "
        "symbol VFS on Vietnamese exchanges is a different company. "
        "HOSE prices are quoted in thousands of VND.",
    }
