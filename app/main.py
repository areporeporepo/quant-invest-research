"""FastAPI backend exposing the quant snapshot and alt-data endpoints.

Run:  uvicorn app.main:app --reload
Docs: http://127.0.0.1:8000/docs

Every response that carries market numbers also carries an explicit disclaimer
and a flag telling you whether the data is real or synthetic. This service is
for research and education. It does not provide personalized financial advice
or buy/sell recommendations.
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import JSONResponse

import json
from dataclasses import asdict
from pathlib import Path

from fastapi.staticfiles import StaticFiles

from .analysis import snapshot_dict
from .config import settings
from .data_providers import (ProviderError, get_dnse_ohlc,
                             get_ohlc_any, get_price_series)
from .outlook import scenario_cone
from .psm import load_psm
from .satellite import SITES, fetch_planet_crop
from .signals import derive_signals, group_comparison, outlook_text

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
WEB_DIR = BASE_DIR / "web"

DISCLAIMER = (
    "Educational/research use only. Not investment advice, not a recommendation "
    "to buy or sell any security, and not a statement about whether now is a good "
    "or bad time to invest. Data may be synthetic or delayed. Verify independently "
    "and consult a licensed professional before making decisions."
)

app = FastAPI(
    title="Quant Investment Research API",
    version="0.1.0",
    description="Backend for market-data quant indicators + satellite alt-data. "
    + DISCLAIMER,
)


@app.get("/api")
def api_root():
    return {
        "service": "quant-invest-research",
        "price_provider": settings.price_provider,
        "default_ticker": settings.default_ticker,
        "endpoints": ["/health", "/snapshot", "/signals", "/group",
                      "/satellite/sites", "/satellite/image",
                      "/satellite/change", "/satellite/change/image", "/docs"],
        "disclaimer": DISCLAIMER,
    }


@app.get("/health")
def health():
    return {"status": "ok", "price_provider": settings.price_provider}


@app.get("/snapshot")
def snapshot(ticker: str | None = None):
    """Quant snapshot (returns, volatility, Sharpe, drawdown, MAs, RSI, trend)."""
    try:
        series = get_price_series(ticker)
    except ProviderError as e:
        raise HTTPException(status_code=502, detail=f"data provider error: {e}")
    data = snapshot_dict(series, risk_free=settings.risk_free_rate)
    return JSONResponse({"snapshot": data, "disclaimer": DISCLAIMER})


@app.get("/signals")
def signals(ticker: str | None = None):
    """Descriptive signal set + plain-language outlook for one ticker.

    Labels (trend, momentum, RSI zone, volatility regime, drawdown state)
    describe the historical window only — not a forecast, not advice.
    """
    try:
        series = get_price_series(ticker)
    except ProviderError as e:
        raise HTTPException(status_code=502, detail=f"data provider error: {e}")
    sigs = derive_signals(series)
    return JSONResponse({
        "ticker": series.ticker,
        "source": series.source,
        "is_real_data": series.is_real,
        "signals": [asdict(s) for s in sigs],
        "outlook": outlook_text(sigs),
        "disclaimer": DISCLAIMER,
    })


@app.get("/group")
def group(tickers: str | None = None):
    """Side-by-side quant comparison of the Vingroup family (VIC, VHM, VRE,
    VPL, VEF) or a custom comma-separated `tickers` list, with pairwise
    return correlations."""
    names = [t.strip().upper() for t in tickers.split(",")] if tickers else None
    result = group_comparison(names, risk_free=settings.risk_free_rate)
    result["disclaimer"] = DISCLAIMER
    return JSONResponse(result)


@app.get("/api/candles")
def api_candles(ticker: str = "VHM", days: int = 800):
    """Real daily OHLCV candles, chart-ready for Lightweight Charts."""
    try:
        candles, unit, source = get_ohlc_any(ticker, days)
    except ProviderError as e:
        raise HTTPException(status_code=502, detail=str(e))
    return JSONResponse({"ticker": ticker.upper(), "candles": candles,
                         "unit": unit, "source": source})


@app.get("/api/events")
def api_events(relevance: str | None = None):
    """Curated, dated, source-attributed events for chart markers."""
    path = DATA_DIR / "events.json"
    events = json.loads(path.read_text()).get("events", []) if path.exists() else []
    if relevance:
        wanted = {r.strip() for r in relevance.split(",")}
        events = [e for e in events if e.get("relevance") in wanted]
    return JSONResponse({"events": sorted(events, key=lambda e: e["date"])})


@app.get("/api/psm")
def api_psm():
    """USD/m² series per project from the curated dataset (+ live FX)."""
    return JSONResponse(load_psm())


@app.get("/api/outlook")
def api_outlook(series: str = "vhm", last_date: str | None = None,
                last_value: float | None = None,
                horizon_end: str = "2029-12-31"):
    """Scenario cone (bear/base/bull) from the last real point to 2029.

    With no explicit anchor: series="vhm" (or any ticker) anchors to its
    latest real close; series="psm:<project>" anchors to that project's
    latest curated USD/m² point.
    """
    if last_date is None or last_value is None:
        if series.startswith("psm:"):
            proj = load_psm()["projects"].get(series[4:])
            if not proj or not proj["points"]:
                raise HTTPException(status_code=404,
                                    detail=f"no psm data for '{series[4:]}'")
            last = proj["points"][-1]
            last_date, last_value = last["time"], last["value"]
        else:
            try:
                candles, _, _ = get_ohlc_any(series, days=60)
            except ProviderError as e:
                raise HTTPException(status_code=502, detail=str(e))
            last_date, last_value = candles[-1]["time"], candles[-1]["close"]
    key = series.lower()
    return JSONResponse(scenario_cone(last_date, float(last_value),
                                      series_key=key, horizon_end=horizon_end))


@app.get("/api/psm_outlooks")
def api_psm_outlooks(horizon_end: str = "2029-12-31"):
    """Scenario cones for EVERY project in the curated USD/m² dataset,
    each anchored on that project's latest sourced point."""
    projects = load_psm()["projects"]
    cones = {}
    for key, proj in projects.items():
        if not proj["points"]:
            continue
        last = proj["points"][-1]
        cones[key] = scenario_cone(last["time"], float(last["value"]),
                                   series_key=f"psm:{key}",
                                   horizon_end=horizon_end)
        cones[key]["label"] = proj["label"]
    return JSONResponse({"cones": cones, "disclaimer": DISCLAIMER})


@app.get("/satellite/sites")
def satellite_sites():
    """Verifiable, auditable coordinates for the physical sites we track."""
    return {
        "sites": {k: vars(v) for k, v in SITES.items()},
        "note": "Coordinates are approximate site centroids; verify against "
        "public maps before relying on them.",
    }


@app.get("/satellite/image")
def satellite_image(site: str = "vinhomes_vu_yen",
                    date_from: str = "2026-06-01",
                    date_to: str = "2026-07-14",
                    max_cloud: float = 0.3):
    """REAL PlanetScope (~3 m, daily revisit) imagery for a tracked site.
    Requires PL_API_KEY. Scene ID/time/cloud in headers for verifiability."""
    result = fetch_planet_crop(site, date_from, date_to, max_cloud=max_cloud)
    if result.fetched and result.image_bytes:
        return Response(content=result.image_bytes, media_type="image/jpeg",
                        headers={"X-Scene-Id": result.scene_id,
                                 "X-Scene-Datetime": result.scene_datetime,
                                 "X-Cloud-Cover": str(result.cloud_cover or ""),
                                 "X-Source": "planet"})
    return JSONResponse({"fetched": False,
                         "site": vars(result.site) if result.site else None,
                         "reason": result.reason})


@app.get("/api/planet_metrics")
def api_planet_metrics():
    """Planet 3 m land-cover metrics per site (Orders API, clipped analytic
    bands). Shares of covered area are the comparable quantity."""
    path = DATA_DIR / "planet_metrics.json"
    if not path.exists():
        return JSONResponse({"ok": False, "reason": "no cached metrics"})
    return JSONResponse(json.loads(path.read_text()))



# Interactive chart web app (TradingView Lightweight Charts PWA).
# Mounted last so all API routes above take precedence.
if WEB_DIR.exists():
    app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
