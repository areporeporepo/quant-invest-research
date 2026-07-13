"""Price-per-square-meter (USD/m²) series for property projects.

There is no free API for Vietnamese primary-market property prices, so this
module serves a CURATED dataset (data/psm.json): dated price points, each
carrying its original currency/unit and a named public source, so every dot
on the chart is auditable. VND-denominated points are converted to USD with
a cached live FX rate (keyless API) with a static fallback.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
FALLBACK_VND_PER_USD = 26000.0  # rough mid-2026 level; used only if FX API fails

# Approximate yearly-average VND/USD for converting HISTORICAL price points.
# Using today's rate on a 2023 price would overstate its USD value by ~10%.
# Points dated in the current year (or beyond the table) use the live rate.
FX_BY_YEAR = {2023: 23800.0, 2024: 25200.0, 2025: 25900.0}

_fx_cache: dict = {"rate": None, "ts": 0.0, "source": ""}


def vnd_per_usd() -> tuple[float, str]:
    """Live VND/USD (cached 6h) from a keyless API, with static fallback."""
    if _fx_cache["rate"] and time.time() - _fx_cache["ts"] < 6 * 3600:
        return _fx_cache["rate"], _fx_cache["source"]
    try:
        import requests

        r = requests.get("https://open.er-api.com/v6/latest/USD", timeout=15)
        r.raise_for_status()
        rate = float(r.json()["rates"]["VND"])
        _fx_cache.update(rate=rate, ts=time.time(), source="open.er-api.com (live)")
    except Exception:
        _fx_cache.update(rate=FALLBACK_VND_PER_USD, ts=time.time(),
                         source=f"static fallback ({FALLBACK_VND_PER_USD:.0f})")
    return _fx_cache["rate"], _fx_cache["source"]


def _to_usd_per_m2(point: dict, live_rate: float) -> float | None:
    cur = point.get("currency", "")
    price = float(point["price"])
    if cur == "USD_per_m2":
        return round(price, 0)
    year = int(point["date"][:4])
    rate = FX_BY_YEAR.get(year, live_rate)
    if cur == "VND_million_per_m2":
        return round(price * 1_000_000 / rate, 0)
    if cur == "VND_per_m2":
        return round(price / rate, 0)
    return None


def load_psm() -> dict:
    """Dataset grouped per project as chart-ready USD/m² series."""
    path = DATA_DIR / "psm.json"
    if not path.exists():
        return {"projects": {}, "fx": None,
                "note": "data/psm.json not found — seed it to light up this chart"}
    raw = json.loads(path.read_text())
    rate, fx_source = vnd_per_usd()
    projects: dict = {}
    for p in raw.get("psm_points", []):
        usd = _to_usd_per_m2(p, rate)
        if usd is None:
            continue
        key = p["project"]
        proj = projects.setdefault(key, {
            "label": p.get("label", key), "points": []})
        proj["points"].append({
            "time": (p["date"] + "-01")[:10] if len(p["date"]) == 7 else p["date"],
            "value": usd,
            "segment": p.get("segment", ""),
            "kind": p.get("kind", ""),
            "source": p.get("source", ""),
            "url": p.get("url", ""),
        })
    for proj in projects.values():
        proj["points"].sort(key=lambda x: x["time"])
    return {
        "projects": projects,
        "fx": {"vnd_per_usd": rate, "source": fx_source},
        "notes": raw.get("notes", []),
        "disclaimer": "Curated, source-attributed price points — coverage is "
        "sparse and segments (apartment vs low-rise) are not directly "
        "comparable. Verify each point via its source before relying on it.",
    }
