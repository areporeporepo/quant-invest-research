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

from dataclasses import asdict

from .analysis import snapshot_dict
from .change_detection import ChangeError, change_composite_jpeg, detect_change
from .config import settings
from .data_providers import ProviderError, get_price_series
from .satellite import SITES, fetch_stac_crop, fetch_stac_scene, fetch_true_color
from .signals import derive_signals, group_comparison, outlook_text

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


@app.get("/")
def root():
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


@app.get("/satellite/change")
def satellite_change(site: str = "vinhomes_vu_yen",
                     from_a: str = "2025-01-01", to_a: str = "2025-04-01",
                     from_b: str = "2026-04-01", to_b: str = "2026-07-01",
                     max_cloud: float = 20.0):
    """NDVI-based land-clearing/construction change between two date windows.

    Compares the least-cloudy Sentinel-2 scene in window A vs window B and
    reports vegetated/cleared areas in hectares, with both scene IDs for
    reproducibility and explicit caveats.
    """
    try:
        rep = detect_change(site, from_a, to_a, from_b, to_b, max_cloud)
    except ChangeError as e:
        return JSONResponse({"ok": False, "reason": str(e)})
    d = asdict(rep)
    d["site"] = vars(rep.site)
    return JSONResponse({"ok": True, "report": d, "disclaimer": DISCLAIMER})


@app.get("/satellite/change/image")
def satellite_change_image(site: str = "vinhomes_vu_yen",
                           from_a: str = "2025-01-01", to_a: str = "2025-04-01",
                           from_b: str = "2026-04-01", to_b: str = "2026-07-01",
                           max_cloud: float = 20.0):
    """Side-by-side true-colour crops (before | after) with newly cleared
    land tinted red on the 'after' panel. JPEG."""
    try:
        jpeg, rep = change_composite_jpeg(site, from_a, to_a, from_b, to_b,
                                          max_cloud)
    except ChangeError as e:
        return JSONResponse({"ok": False, "reason": str(e)})
    return Response(content=jpeg, media_type="image/jpeg", headers={
        "X-Scene-A": rep.scene_a.scene_id,
        "X-Scene-B": rep.scene_b.scene_id,
        "X-Cleared-Ha": str(rep.cleared_ha),
    })


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
                    date_from: str = "2026-04-01",
                    date_to: str = "2026-07-01",
                    provider: str = "stac",
                    max_cloud: float = 30.0,
                    crop: bool = True):
    """Fetch a REAL satellite image for a tracked site.

    provider="stac" (default): keyless Sentinel-2 via the public Earth Search
    catalogue. With crop=true (default) it does a 10 m-resolution windowed
    read of the scene's true-colour COG centred on the site; with crop=false
    it returns the whole-tile preview. Scene ID / timestamp / cloud cover are
    in response headers so anyone can re-derive the exact scene.
    provider="sentinelhub": custom-rendered crop, needs Sentinel Hub creds.

    On failure returns 200 JSON explaining why, so the pipeline never
    hard-fails on a missing key or a cloudy month.
    """
    if provider == "sentinelhub":
        result = fetch_true_color(site, date_from, date_to)
        media_type = "image/png"
    elif crop:
        result = fetch_stac_crop(site, date_from, date_to, max_cloud=max_cloud)
        media_type = "image/jpeg"
    else:
        result = fetch_stac_scene(site, date_from, date_to, max_cloud=max_cloud)
        media_type = "image/jpeg"
    if result.fetched and result.image_bytes:
        return Response(
            content=result.image_bytes,
            media_type=media_type,
            headers={
                "X-Scene-Id": result.scene_id,
                "X-Scene-Datetime": result.scene_datetime,
                "X-Cloud-Cover": str(result.cloud_cover or ""),
                "X-Source": result.source or provider,
            },
        )
    return JSONResponse({
        "fetched": False,
        "site": vars(result.site) if result.site else None,
        "reason": result.reason,
        "hint": "provider=stac needs no key; try a wider date range or higher "
        "max_cloud. provider=sentinelhub needs SENTINELHUB_CLIENT_ID/SECRET "
        "(free tier at https://www.sentinel-hub.com/).",
    })
