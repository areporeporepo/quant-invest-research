"""Scenario outlook engine: bear/base/bull cones for 2026-2029.

These are SCENARIOS, not forecasts. Each scenario is a compounding annual
rate applied to the last real data point; the assumptions live in
data/outlook.json where anyone can read and change them. The chart draws the
result as a shaded cone so the "future" part is visually distinct from data.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

DEFAULT_SCENARIOS = {
    "bear": {"annual_rate": -0.10, "label": "Bear: correction / policy tightening"},
    "base": {"annual_rate": 0.08, "label": "Base: trend growth"},
    "bull": {"annual_rate": 0.20, "label": "Bull: continued re-rating"},
}


def load_scenarios(series_key: str) -> dict:
    cfg_path = DATA_DIR / "outlook.json"
    if cfg_path.exists():
        cfg = json.loads(cfg_path.read_text())
        if series_key in cfg:
            return cfg[series_key]
        if "default" in cfg:
            return cfg["default"]
    return DEFAULT_SCENARIOS


def scenario_cone(last_date: str, last_value: float, series_key: str = "default",
                  horizon_end: str = "2029-12-31", points_per_year: int = 4) -> dict:
    """Quarterly scenario paths from (last_date, last_value) to horizon_end."""
    scenarios = load_scenarios(series_key)
    start = dt.date.fromisoformat(last_date[:10])
    end = dt.date.fromisoformat(horizon_end)
    step_days = max(1, round(365.25 / points_per_year))
    out: dict = {"anchor": {"date": last_date[:10], "value": last_value},
                 "scenarios": {}}
    for name, spec in scenarios.items():
        rate = float(spec["annual_rate"])
        path, d = [], start
        while d <= end:
            years = (d - start).days / 365.25
            path.append({"time": d.isoformat(),
                         "value": round(last_value * (1 + rate) ** years, 2)})
            d += dt.timedelta(days=step_days)
        if path[-1]["time"] != end.isoformat():
            years = (end - start).days / 365.25
            path.append({"time": end.isoformat(),
                         "value": round(last_value * (1 + rate) ** years, 2)})
        out["scenarios"][name] = {
            "annual_rate": rate,
            "label": spec.get("label", name),
            "path": path,
        }
    out["disclaimer"] = ("Scenario cones are illustrative compounding paths "
                         "from stated assumptions — not forecasts, not advice. "
                         "Edit the assumptions in data/outlook.json.")
    return out
