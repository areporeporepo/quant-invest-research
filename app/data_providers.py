"""Market-data providers.

Provider-agnostic: every provider returns a list of daily closing prices,
oldest first, so the rest of the app never cares where the numbers came from.

Providers:
  - "dnse": REAL daily OHLC for Vietnamese (HOSE/HNX) tickers via DNSE's public
    chart API (services.entrade.com.vn). No key required. Default.
  - "stub": deterministic synthetic series. No key, no network. Lets you run
    and test the whole pipeline offline. Clearly labelled as NOT real data.
  - "alphavantage": free tier, needs ALPHAVANTAGE_API_KEY.
  - "finnhub": free tier, needs FINNHUB_API_KEY.

All real providers degrade gracefully: on any network/key/parse error they
raise ProviderError with a human-readable reason instead of crashing.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

from .config import settings


class ProviderError(RuntimeError):
    pass


@dataclass
class PriceSeries:
    ticker: str
    closes: list[float]
    source: str
    is_real: bool
    note: str = ""
    dates: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Stub provider: deterministic, offline, obviously-synthetic.
# ---------------------------------------------------------------------------
def _stub_series(ticker: str, n: int = 180) -> PriceSeries:
    """A reproducible pseudo-random walk seeded by the ticker name.

    Deterministic (no RNG) so tests and demos are stable and it is impossible
    to mistake this for a live quote.
    """
    seed = sum(ord(c) for c in ticker) or 1
    price = 10.0 + (seed % 40)
    closes = []
    for i in range(n):
        # smooth, bounded wiggle from a sine mix — no randomness, fully repeatable
        drift = math.sin(i / 9.0 + seed) * 0.9 + math.sin(i / 23.0) * 1.6
        price = max(0.5, price * (1.0 + drift / 100.0))
        closes.append(round(price, 2))
    return PriceSeries(
        ticker=ticker.upper(),
        closes=closes,
        source="stub",
        is_real=False,
        note="SYNTHETIC data — for pipeline testing only. Not a real quote.",
    )


# ---------------------------------------------------------------------------
# Real providers (network). Imported lazily so the app runs without requests.
# ---------------------------------------------------------------------------
def _http_get_json(url: str, params: dict) -> dict:
    try:
        import requests
    except ImportError as e:  # pragma: no cover
        raise ProviderError("`requests` not installed; run `pip install requests`") from e
    try:
        resp = requests.get(url, params=params, timeout=20)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        raise ProviderError(f"HTTP request failed: {e}") from e


def _alphavantage_series(ticker: str) -> PriceSeries:
    if not settings.alphavantage_key:
        raise ProviderError("ALPHAVANTAGE_API_KEY is not set")
    data = _http_get_json(
        "https://www.alphavantage.co/query",
        {
            "function": "TIME_SERIES_DAILY",
            "symbol": ticker,
            "outputsize": "compact",
            "apikey": settings.alphavantage_key,
        },
    )
    series = data.get("Time Series (Daily)")
    if not series:
        raise ProviderError(f"AlphaVantage returned no series: {data.get('Note') or data}")
    items = sorted(series.items())  # oldest first by date string
    closes = [float(v["4. close"]) for _, v in items]
    dates = [d for d, _ in items]
    return PriceSeries(ticker.upper(), closes, "alphavantage", True, dates=dates)


def _dnse_series(ticker: str, days: int = 400) -> PriceSeries:
    """Real daily closes for Vietnamese tickers (e.g. VHM on HOSE), keyless.

    Uses DNSE's public chart endpoint. Symbols are bare HOSE/HNX codes
    ("VHM", not "VHM.VN") — a trailing ".VN" is stripped for convenience.
    """
    import datetime as dt
    import time

    symbol = ticker.upper().removesuffix(".VN")
    now = int(time.time())
    data = _http_get_json(
        "https://services.entrade.com.vn/chart-api/v2/ohlcs/stock",
        {
            "symbol": symbol,
            "resolution": "1D",
            "from": now - 60 * 60 * 24 * days,
            "to": now,
        },
    )
    closes = data.get("c") or []
    stamps = data.get("t") or []
    if not closes:
        raise ProviderError(f"DNSE returned no candles for '{symbol}': {str(data)[:200]}")
    dates = [dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%Y-%m-%d")
             for t in stamps]
    return PriceSeries(
        ticker=symbol,
        closes=[float(c) for c in closes],
        source="dnse",
        is_real=True,
        note="Real daily closes from DNSE public chart API (HOSE/HNX). "
        "Prices are in thousands of VND as quoted by the exchange feed.",
        dates=dates,
    )


def get_dnse_ohlc(ticker: str, days: int = 800) -> list[dict]:
    """Real daily OHLCV candles for HOSE/HNX tickers, keyless, chart-ready.

    Returns [{time: 'YYYY-MM-DD', open, high, low, close, volume}, ...] in the
    format TradingView Lightweight Charts consumes directly.
    """
    import datetime as dt
    import time

    symbol = ticker.upper().removesuffix(".VN")
    now = int(time.time())
    data = _http_get_json(
        "https://services.entrade.com.vn/chart-api/v2/ohlcs/stock",
        {"symbol": symbol, "resolution": "1D",
         "from": now - 60 * 60 * 24 * days, "to": now},
    )
    if not data.get("c"):
        raise ProviderError(f"DNSE returned no candles for '{symbol}'")
    return [
        {
            "time": dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%Y-%m-%d"),
            "open": float(o), "high": float(h), "low": float(l),
            "close": float(c), "volume": float(v),
        }
        for t, o, h, l, c, v in zip(data["t"], data["o"], data["h"],
                                    data["l"], data["c"], data["v"])
    ]


def _finnhub_series(ticker: str) -> PriceSeries:
    if not settings.finnhub_key:
        raise ProviderError("FINNHUB_API_KEY is not set")
    # Finnhub candles need a time range; caller can extend as needed.
    import time

    now = int(time.time())
    data = _http_get_json(
        "https://finnhub.io/api/v1/stock/candle",
        {
            "symbol": ticker,
            "resolution": "D",
            "from": now - 60 * 60 * 24 * 400,
            "to": now,
            "token": settings.finnhub_key,
        },
    )
    if data.get("s") != "ok" or not data.get("c"):
        raise ProviderError(f"Finnhub returned no data: {data}")
    return PriceSeries(ticker.upper(), [float(c) for c in data["c"]], "finnhub", True)


def get_price_series(ticker: Optional[str] = None) -> PriceSeries:
    """Fetch a daily-close series using the configured provider.

    Never raises for the stub provider. For real providers, raises
    ProviderError on failure so the API layer can report it cleanly.
    """
    ticker = (ticker or settings.default_ticker).upper()
    provider = settings.price_provider.lower()
    if provider == "dnse":
        return _dnse_series(ticker)
    if provider == "alphavantage":
        return _alphavantage_series(ticker)
    if provider == "finnhub":
        return _finnhub_series(ticker)
    return _stub_series(ticker)
