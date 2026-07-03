"""Runtime configuration, read entirely from environment variables.

Nothing secret is ever hard-coded or committed. Copy `.env.example` to `.env`,
fill in your keys, and load it (the app auto-loads `.env` if python-dotenv is
installed).
"""

from __future__ import annotations

import os
from dataclasses import dataclass

try:  # optional convenience; app works without it if env vars are already set
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover
    pass


@dataclass(frozen=True)
class Settings:
    # Which market-data provider to use: "dnse" | "alphavantage" | "finnhub" | "stub"
    # "dnse" serves REAL Vietnamese (HOSE/HNX) daily data with no API key.
    price_provider: str = os.getenv("PRICE_PROVIDER", "dnse")
    alphavantage_key: str = os.getenv("ALPHAVANTAGE_API_KEY", "")
    finnhub_key: str = os.getenv("FINNHUB_API_KEY", "")

    # Satellite / alternative-data provider (Sentinel Hub has a free tier).
    sentinelhub_client_id: str = os.getenv("SENTINELHUB_CLIENT_ID", "")
    sentinelhub_client_secret: str = os.getenv("SENTINELHUB_CLIENT_SECRET", "")

    # Default asset under study. Vinhomes (Vingroup's real-estate arm) trades
    # on the Ho Chi Minh Stock Exchange (HOSE) as VHM. The DNSE provider takes
    # the bare HOSE code; global vendors may want a ".VN" suffix instead.
    default_ticker: str = os.getenv("DEFAULT_TICKER", "VHM")

    risk_free_rate: float = float(os.getenv("RISK_FREE_RATE", "0.04"))


settings = Settings()
