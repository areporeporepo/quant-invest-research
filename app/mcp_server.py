"""AI-native access: an MCP server over the research data.

Model Context Protocol is how AI assistants (Claude et al.) interact with
apps as of 2026. This server exposes the same data the iPhone web app
renders — as tools an AI can call to READ the research and to EDIT the
curated datasets (price points, events, scenario assumptions). Edits are
written to data/*.json, so they appear in the web app on its next refresh:
one source of truth, two front-ends (humans get charts, AIs get tools).

Run (stdio):        python -m app.mcp_server
Claude Code:        claude mcp add vuyen -- python -m app.mcp_server
Claude Desktop:     add the same command to claude_desktop_config.json

Following the MCP Apps pattern (SEP-1865, announced 2026-01-26), the server
also serves a self-contained chart UI as a ui:// resource; hosts that
support MCP Apps can render it inline, others simply ignore it.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from .data_providers import get_dnse_ohlc, get_price_series
from .analysis import snapshot_dict
from .config import settings
from .outlook import scenario_cone
from .psm import load_psm
from .signals import derive_signals, group_comparison, outlook_text

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
WEB_DIR = Path(__file__).resolve().parent.parent / "web"

DISCLAIMER = ("Research/education only — descriptive of historical data, "
              "not investment advice, not a forecast.")

mcp = FastMCP(
    "vuyen-research",
    instructions="Quant research data for Vinhomes/Vingroup (HOSE) and the "
    "Vũ Yên (Royal Island) property project: real market data, quant "
    "indicators, curated USD/m² points, chart events and scenario outlooks. "
    "Write tools edit the same JSON datasets the companion web app renders. "
    + DISCLAIMER,
)


def _read_json(path: Path, fallback: dict) -> dict:
    return json.loads(path.read_text()) if path.exists() else fallback


def _write_json(path: Path, obj: dict) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n")


# ---------------------------------------------------------------- read tools

@mcp.tool()
def get_market_snapshot(ticker: str = "VHM") -> dict:
    """Quant snapshot for a HOSE/HNX ticker from real daily data: total
    return, annualized volatility, Sharpe, max drawdown, SMA/EMA, RSI, trend.
    Prices are in thousands of VND."""
    return {"snapshot": snapshot_dict(get_price_series(ticker),
                                      risk_free=settings.risk_free_rate),
            "disclaimer": DISCLAIMER}


@mcp.tool()
def get_signals(ticker: str = "VHM") -> dict:
    """Descriptive signal labels (trend, momentum, RSI zone, volatility
    regime, drawdown state) plus a plain-language outlook sentence."""
    series = get_price_series(ticker)
    sigs = derive_signals(series)
    return {"ticker": series.ticker,
            "signals": [asdict(s) for s in sigs],
            "outlook": outlook_text(sigs),
            "disclaimer": DISCLAIMER}


@mcp.tool()
def get_group_comparison(tickers: str = "") -> dict:
    """Side-by-side quant comparison of the Vingroup family (VIC, VHM, VRE,
    VPL, VEF by default; or a comma-separated custom list) with pairwise
    daily-return correlations."""
    names = [t.strip().upper() for t in tickers.split(",") if t.strip()] or None
    return group_comparison(names, risk_free=settings.risk_free_rate)


@mcp.tool()
def get_recent_candles(ticker: str = "VHM", sessions: int = 30) -> dict:
    """Most recent daily OHLCV candles (real, DNSE feed, thousand VND).
    Use small `sessions` values; the full history lives in the web app."""
    candles = get_dnse_ohlc(ticker, days=max(sessions * 2, 60))
    return {"ticker": ticker.upper(), "unit": "thousand VND",
            "candles": candles[-max(1, min(sessions, 250)):]}


@mcp.tool()
def get_psm_data() -> dict:
    """Curated USD/m² price points per property project (Vũ Yên Royal
    Island and comparables), each with its public source, plus live FX."""
    return load_psm()


@mcp.tool()
def get_events() -> dict:
    """Curated dated events shown as markers on the charts (launches,
    policy changes, satellite findings), each with source attribution."""
    return _read_json(DATA_DIR / "events.json", {"events": []})


@mcp.tool()
def get_outlook(series: str = "vhm", horizon_end: str = "2029-12-31") -> dict:
    """Bear/base/bull scenario cone to `horizon_end`. `series` is a ticker
    ("VHM") or "psm:<project_key>". Scenarios are stated assumptions
    compounded forward — not forecasts."""
    if series.startswith("psm:"):
        proj = load_psm()["projects"].get(series[4:])
        if not proj or not proj["points"]:
            return {"error": f"no psm data for '{series[4:]}'"}
        last = proj["points"][-1]
        anchor_date, anchor_value = last["time"], last["value"]
    else:
        candles = get_dnse_ohlc(series, days=30)
        anchor_date, anchor_value = candles[-1]["time"], candles[-1]["close"]
    return scenario_cone(anchor_date, float(anchor_value),
                         series_key=series.lower(), horizon_end=horizon_end)


# --------------------------------------------------------------- write tools

@mcp.tool()
def add_psm_point(project: str, label: str, date: str, price: float,
                  currency: str, segment: str, kind: str, source: str,
                  url: str = "") -> dict:
    """Add a USD/m² price point to the curated dataset (appears in the web
    app's USD/m² chart on refresh).

    project: snake_case key, e.g. "vu_yen_royal_island". label: display
    name. date: YYYY-MM or YYYY-MM-DD. currency: one of USD_per_m2 |
    VND_million_per_m2 | VND_per_m2. segment: apartment|low-rise|villa|
    mixed. kind: primary|resale|report_average. source: REQUIRED named
    public source — never add a number without one."""
    if currency not in {"USD_per_m2", "VND_million_per_m2", "VND_per_m2"}:
        return {"ok": False, "error": "invalid currency unit"}
    if not source.strip():
        return {"ok": False, "error": "source attribution is required"}
    path = DATA_DIR / "psm.json"
    data = _read_json(path, {"psm_points": [], "notes": []})
    data["psm_points"].append({
        "project": project, "label": label, "date": date, "price": price,
        "currency": currency, "segment": segment, "kind": kind,
        "source": source, "url": url,
    })
    _write_json(path, data)
    return {"ok": True, "total_points": len(data["psm_points"])}


@mcp.tool()
def add_event(date: str, title: str, detail: str, relevance: str,
              source: str, url: str = "", title_vi: str = "",
              detail_vi: str = "", short: str = "") -> dict:
    """Add a dated event marker to the charts. relevance: vu_yen|vhm|macro
    (or a ticker in lowercase). Provide Vietnamese title_vi/detail_vi when
    possible — the app is Vietnamese-first. source is required."""
    if not source.strip():
        return {"ok": False, "error": "source attribution is required"}
    path = DATA_DIR / "events.json"
    data = _read_json(path, {"events": []})
    data["events"].append({k: v for k, v in {
        "date": date, "title": title, "detail": detail, "short": short,
        "title_vi": title_vi, "detail_vi": detail_vi,
        "relevance": relevance, "source": source, "url": url,
    }.items() if v})
    _write_json(path, data)
    return {"ok": True, "total_events": len(data["events"])}


@mcp.tool()
def set_outlook_scenario(series_key: str, scenario: str, annual_rate: float,
                         label: str) -> dict:
    """Set one scenario assumption for a series' outlook cone. series_key:
    "vhm", "default", or "psm:<project>". scenario: bear|base|bull.
    annual_rate: compounding yearly rate, e.g. 0.08 = +8%/yr. The web app's
    cones update on refresh."""
    if scenario not in {"bear", "base", "bull"}:
        return {"ok": False, "error": "scenario must be bear|base|bull"}
    if not -0.9 <= annual_rate <= 2.0:
        return {"ok": False, "error": "annual_rate outside sane range"}
    path = DATA_DIR / "outlook.json"
    data = _read_json(path, {})
    data.setdefault(series_key, {})[scenario] = {
        "annual_rate": annual_rate, "label": label}
    _write_json(path, data)
    return {"ok": True, "series_key": series_key,
            "scenarios": data[series_key]}


# ------------------------------------------------- MCP Apps chart UI (2026)

@mcp.resource("ui://vuyen/chart.html")
def chart_ui() -> str:
    """Self-contained interactive chart (MCP Apps pattern): hosts that
    support ui:// resources render it inline next to tool results."""
    lib = (WEB_DIR / "lightweight-charts.js").read_text()
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>body{{margin:0;background:#0d1117;color:#e6edf3;font-family:-apple-system,sans-serif}}
#c{{height:320px}}#s{{padding:6px 10px;font-size:12px;color:#8b949e}}</style>
</head><body><div id="c"></div><div id="s">Vũ Yên Research — gửi dữ liệu nến qua postMessage
{{jsonrpc:'2.0',method:'render',params:{{candles:[...]}}}}</div>
<script>{lib}</script>
<script>
const chart = LightweightCharts.createChart(document.getElementById('c'),
  {{layout:{{background:{{color:'#0d1117'}},textColor:'#8b949e'}},
    grid:{{vertLines:{{color:'#161b22'}},horzLines:{{color:'#161b22'}}}}}});
const series = chart.addCandlestickSeries(
  {{upColor:'#26a69a',downColor:'#ef5350',borderVisible:false,
    wickUpColor:'#26a69a',wickDownColor:'#ef5350'}});
window.addEventListener('message', (ev) => {{
  const m = ev.data;
  if (m && m.method === 'render' && m.params && m.params.candles) {{
    series.setData(m.params.candles);
    chart.timeScale().fitContent();
    document.getElementById('s').textContent =
      (m.params.title || 'VHM') + ' · ' + m.params.candles.length + ' phiên';
  }}
}});
</script></body></html>"""


if __name__ == "__main__":
    mcp.run()
