# Quant Investment Research API

A small, honest **backend service** for researching an asset the way a quant
would: pull **verifiable market data**, compute **quant indicators**, and layer
in **satellite / alternative data** to cross-check the story on the ground.

The worked example is **Vinhomes** (Vingroup's real-estate arm, ticker **`VHM`**
on the Ho Chi Minh Stock Exchange), with the physical anchor site being
**Vinhomes Royal Island on Vũ Yên Island, Hải Phòng** — but every ticker and
site is configurable.

> ⚠️ **Not financial advice.** This is an educational/research tool. It reports
> what the numbers *are* — it does **not** tell you whether to buy, sell, or
> whether "now is a good/bad time." It cannot, and it won't. Personalized advice
> requires a licensed professional who knows your full situation. See
> [Responsible use](#responsible-use).

---

## Why this exists

You asked, in effect: *"What's the best way to invest right now?"* The honest
answer is that no tool — and no one who doesn't know your finances, horizon, and
risk tolerance — can responsibly answer that for you. What a tool *can* do is
give you the **framework and the evidence** a professional would use, so you can
reason for yourself. That's what this backend is.

## What it does

| Layer | What you get | Source |
|-------|--------------|--------|
| **Market data** | REAL daily closes for HOSE/HNX tickers (default: `VHM`), **no API key needed** | DNSE public chart API; Alpha Vantage / Finnhub optional |
| **Quant indicators** | Total return, annualized volatility, Sharpe ratio, max drawdown, SMA/EMA, RSI, trend label | Computed locally, pure Python |
| **Alt-data (satellite)** | REAL Sentinel-2 imagery of the Vũ Yên construction footprint — 10 m crops via keyless COG reads, with scene ID / timestamp / cloud cover for verifiability | Earth Search STAC + AWS Open Data (**no key**); Sentinel Hub optional |

## Quick start

```bash
cd quant-invest-research
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Serves REAL data out of the box — no API keys required:
#   prices:    DNSE public chart API (HOSE/HNX)
#   satellite: public Sentinel-2 STAC catalogue on AWS
uvicorn app.main:app --reload
# open http://127.0.0.1:8000/docs
```

Optional providers (Alpha Vantage / Finnhub / Sentinel Hub) take keys via env:

```bash
cp .env.example .env      # then edit .env — never commit it
```

For fully-offline pipeline testing set `PRICE_PROVIDER=stub` (synthetic,
clearly labelled `is_real_data: false`).

### Endpoints

- `GET /snapshot?ticker=VHM` — full quant snapshot from real HOSE data
- `GET /satellite/sites` — verifiable coordinates of tracked sites
- `GET /satellite/image?site=vinhomes_vu_yen&date_from=2026-04-01&date_to=2026-07-01` — real Sentinel-2 true-colour JPEG, cropped to the site at 10 m resolution (`crop=false` for the whole tile). Response headers `X-Scene-Id` / `X-Scene-Datetime` / `X-Cloud-Cover` identify the exact public scene so anyone can verify it.
- `GET /health`, `GET /` — service info

## About the API keys you offered

Please **do not paste keys into chat or commit them.** The service only ever
reads them from environment variables (`.env`, which is git-ignored). You keep
control of your own credentials. Free tiers are enough to start:

- **Market data:** [Alpha Vantage](https://www.alphavantage.co/support/#api-key) or [Finnhub](https://finnhub.io/register)
- **Satellite:** [Sentinel Hub](https://www.sentinel-hub.com/) (Sentinel-2, free tier)

> Note on Vietnamese equities: the default `dnse` provider covers HOSE/HNX
> with no key. Global vendors (Alpha Vantage/Finnhub) have thin Vietnam
> coverage — if they return nothing for `VHM`, that's a coverage gap, not a
> bug. DNSE quotes HOSE prices in thousands of VND.

## Reading the numbers (quick quant glossary)

- **Annualized volatility** — how much the price bounces around per year. Higher = riskier/more uncertain.
- **Sharpe ratio** — return earned per unit of risk, above the risk-free rate. Higher is better; it says nothing about *future* returns.
- **Max drawdown** — the worst peak-to-trough drop in the window. How bad it has historically felt to hold.
- **RSI (14)** — momentum oscillator, 0–100. Conventionally >70 "overbought", <30 "oversold". A heuristic, not a signal.
- **SMA/EMA + trend** — moving-average relationships summarizing whether price is above/below its recent averages.

All of these are **descriptive of the past**. None of them predict the future,
and none of them constitute advice.

## Satellite / alternative data

For a property developer, construction *is* the fundamental. Comparing satellite
images of Vũ Yên Island across dates lets you see land clearing, new roads, and
rising buildings — a real-world check on whether delivery is on pace with what
management reports. Coordinates in `app/satellite.py` are approximate centroids
and are meant to be **verified against public maps** before you rely on them.

## AI-native access (MCP)

As of 2026 the way AI assistants interact with an app is the **Model Context
Protocol**. This repo ships an MCP server over the same data the web app
renders — so Claude can *read* the research (snapshots, signals, group
comparison, USD/m² points, events, outlooks) and *edit* the curated datasets
(add sourced price points, add events, tune scenario assumptions). Edits land
in `data/*.json` and appear in the app on refresh: one source of truth, two
front-ends — humans get charts, AIs get tools.

```bash
# Claude Code
claude mcp add vuyen -- python -m app.mcp_server
# Claude Desktop: add the same command to claude_desktop_config.json
```

Following Anthropic's **MCP Apps** pattern (Jan 2026), the server also
exposes the chart as a `ui://vuyen/chart.html` resource that MCP Apps-capable
hosts can render inline. A machine-readable guide lives at `/llms.txt`.

## Interactive chart app (mobile-first, tiếng Việt)

`uvicorn app.main:app` then open `/` — a Vietnamese-first (EN toggle),
dark-theme, TradingView-powered PWA designed for iPhone: real HOSE candles
with event markers, USD/m² per project with source citations on tap, and
2026–2029 bear/base/bull scenario cones. Add to Home Screen on iOS for the
native-app feel.

## Testing

```bash
pytest -q          # pure, offline unit tests for the indicator math
```

## Responsible use

- Research and education only. **Not** investment advice or a recommendation.
- Nothing here says whether to invest, or whether the timing is good or bad.
- Data may be synthetic (stub), delayed, or incomplete — verify independently.
- Past performance and historical indicators do not predict future results.
- For decisions about your money, consult a licensed financial professional.

## Project layout

```
quant-invest-research/
├── app/
│   ├── config.py          # env-only configuration (no secrets in code)
│   ├── data_providers.py  # market data: stub | alphavantage | finnhub
│   ├── indicators.py      # pure quant math (tested)
│   ├── analysis.py        # assemble a snapshot
│   ├── satellite.py       # Sentinel Hub alt-data + verifiable coordinates
│   └── main.py            # FastAPI app
├── tests/test_indicators.py
├── requirements.txt
├── .env.example
└── README.md
```
