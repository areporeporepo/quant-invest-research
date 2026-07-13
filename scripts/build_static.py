"""Build docs/index.html — the static GitHub Pages build of the chart app.

Reads web/index.html + web/app.js (single source of truth), inlines the
chart library, embeds a data snapshot pulled from a locally running API
server, and swaps the fetch layer for a live-first one: candles are fetched
directly from the DNSE feed in the browser when CORS allows, falling back
to the embedded snapshot. Run:

    uvicorn app.main:app --port 8777 &   # needs the API up for the snapshot
    python scripts/build_static.py
"""

from __future__ import annotations

import json
import re
import shutil
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB, DOCS = ROOT / "web", ROOT / "docs"
BASE = "http://127.0.0.1:8777"
REPO_URL = "https://github.com/areporeporepo/quant-invest-research"


def get(path: str):
    with urllib.request.urlopen(BASE + path, timeout=60) as r:
        return json.load(r)


def snapshot() -> dict:
    data = {"candles": {}, "outlook": {}, "psm": None, "events": None}
    data["units"] = {}
    for tk in ["VHM", "VIC", "VRE", "VPL", "VEF", "VNINDEX", "NVDA", "SPY"]:
        resp = get(f"/api/candles?ticker={tk}")
        data["candles"][tk] = resp["candles"][-420:]
        data["units"][tk] = resp.get("unit", "thousand VND")
        data["outlook"][tk] = get(f"/api/outlook?series={tk}")
    data["psm"] = get("/api/psm")
    data["psm_outlooks"] = get("/api/psm_outlooks")
    data["outlook"]["psm:vu_yen_royal_island"] = get(
        "/api/outlook?series=psm:vu_yen_royal_island")
    data["events"] = get("/api/events")["events"]
    try:
        data["satellite"] = get("/satellite/portfolio")
    except Exception:
        data["satellite"] = None
    try:
        data["construction"] = get("/api/construction")
    except Exception:
        data["construction"] = None
    data["asof"] = data["candles"]["VHM"][-1]["time"]
    return data


LIVE_GETJSON = """async function getJSON(url) {
  // Static build: try LIVE data first, fall back to the embedded snapshot.
  if (url.startsWith('/api/candles')) {
    const tk = new URLSearchParams(url.split('?')[1]).get('ticker') || 'VHM';
    const emb = { ticker: tk, unit: (DATA.units || {})[tk] || 'thousand VND',
                  candles: DATA.candles[tk] || [] };
    // Yahoo blocks browser CORS: US tickers always use the embedded snapshot.
    if (emb.unit === 'USD') return emb;
    const kind = tk === 'VNINDEX' ? 'index' : 'stock';
    try {
      const now = Math.floor(Date.now() / 1000);
      const r = await fetch(`https://services.entrade.com.vn/chart-api/v2/ohlcs/${kind}` +
        `?symbol=${tk}&resolution=1D&from=${now - 86400 * 800}&to=${now}`,
        { signal: AbortSignal.timeout(6000) });
      if (!r.ok) throw new Error(r.status);
      const d = await r.json();
      if (!d.c || !d.c.length) throw new Error('empty');
      window.__live = true;
      return { ticker: tk, unit: emb.unit, candles: d.t.map((tt, i) => ({
        time: new Date(tt * 1000).toISOString().slice(0, 10),
        open: d.o[i], high: d.h[i], low: d.l[i], close: d.c[i], volume: d.v[i],
      })) };
    } catch (_) {
      window.__live = false;
      return emb;
    }
  }
  if (url.startsWith('/api/outlook')) {
    const s = new URLSearchParams(url.split('?')[1]).get('series') || 'VHM';
    const base = DATA.outlook[s] || DATA.outlook[s.toUpperCase()] || DATA.outlook.VHM;
    const anchor = window.__anchor;
    if (!anchor || s.startsWith('psm:')) return base;
    const out = { anchor, scenarios: {} };
    for (const [name, sc] of Object.entries(base.scenarios)) {
      const start = new Date(anchor.date), end = new Date('2029-12-31');
      const path = [];
      for (let d = new Date(start); d <= end; d.setDate(d.getDate() + 91)) {
        const years = (d - start) / 31557600000;
        path.push({ time: d.toISOString().slice(0, 10),
                    value: +(anchor.value * Math.pow(1 + sc.annual_rate, years)).toFixed(2) });
      }
      out.scenarios[name] = { ...sc, path };
    }
    return out;
  }
  if (url.startsWith('/api/construction')) return DATA.construction || { points: [] };
  if (url.startsWith('/api/psm_outlooks')) return DATA.psm_outlooks;
  if (url.startsWith('/api/psm')) return DATA.psm;
  if (url.startsWith('/api/events')) return { events: DATA.events };
  throw new Error('no data for ' + url);
}"""

BANNER_JS = """function banner() {
  const repo = '<a href="%(repo)s" target="_blank" rel="noopener">GitHub repo</a>';
  let vi, en;
  if (window.__live) {
    vi = `Nến cổ phiếu: <b>dữ liệu trực tiếp</b> từ DNSE · USD/m² và sự kiện: cập nhật ${DATA.asof} · mã nguồn: ${repo}.`;
    en = `Candles: <b>live</b> from DNSE · USD/m² and events as of ${DATA.asof} · source: ${repo}.`;
  } else {
    vi = `Ảnh chụp dữ liệu ngày <b>${DATA.asof}</b> — bản đầy đủ (vệ tinh + MCP) chạy từ ${repo}.`;
    en = `Data snapshot of <b>${DATA.asof}</b> — full app (satellite + MCP) runs from the ${repo}.`;
  }
  document.getElementById('banner').innerHTML = lang === 'vi' ? vi : en;
}
banner();
const _applyStaticText = applyStaticText;
applyStaticText = () => { _applyStaticText(); banner(); };""" % {"repo": REPO_URL}


def build() -> None:
    data = snapshot()
    html = (WEB / "index.html").read_text()
    app = (WEB / "app.js").read_text()

    m = re.search(r"async function getJSON\(url\) \{.*?\n\}", app, re.S)
    assert m, "getJSON not found in app.js"
    app = app[: m.start()] + LIVE_GETJSON + app[m.end():]

    # Capture the freshest close so stock cones re-anchor on live data.
    old = """  const [data, events, cone] = await Promise.all([
    getJSON(`/api/candles?ticker=${ticker}`),
    loadEvents(),
    getJSON(`/api/outlook?series=${ticker}`),
  ]);"""
    new = """  const data = await getJSON(`/api/candles?ticker=${ticker}`);
  const lastC = data.candles.at(-1);
  window.__anchor = lastC ? { date: lastC.time, value: lastC.close } : null;
  const [events, cone] = await Promise.all([
    loadEvents(),
    getJSON(`/api/outlook?series=${ticker}`),
  ]);"""
    assert old in app, "showMarket fetch block not found"
    app = app.replace(old, new)

    # localStorage can throw in sandboxed iframes (artifact hosting).
    app = app.replace("let lang = localStorage.getItem('lang') || 'vi';",
                      "let lang = 'vi'; try { lang = localStorage.getItem('lang') || 'vi'; } catch (_) {}")
    app = app.replace("localStorage.setItem('lang', lang);",
                      "try { localStorage.setItem('lang', lang); } catch (_) {}")
    app += "\n" + BANNER_JS + "\n"

    lib = (WEB / "lightweight-charts.js").read_text()
    html = html.replace('<script src="lightweight-charts.js"></script>',
                        "<script>\n" + lib + "\n</script>")
    html = html.replace('<script src="app.js"></script>',
                        "<script>\nconst DATA = " + json.dumps(
                            data, ensure_ascii=False, separators=(",", ":"))
                        + ";\n</script>\n<script>\n" + app + "\n</script>")
    html = html.replace("</style>", """  .banner { margin: 4px 14px 10px; padding: 8px 12px; background: var(--panel);
    border: 1px solid var(--border); border-radius: 10px; font-size: 12px; color: var(--muted); }
  .banner a { color: var(--accent); text-decoration: none; }
</style>""")
    html = html.replace("</header>",
                        '</header>\n  <div class="banner" id="banner"></div>')

    # --- AI/machine-readable layer -------------------------------------
    # AI browsers (ChatGPT, Claude, etc.) fetch raw HTML without running
    # JavaScript, so the numbers must exist as static markup too.
    html = html.replace(
        "<title>",
        '<meta name="description" content="Vũ Yên Research: USD/m² for '
        'Vinhomes Royal Island (Vũ Yên, Hải Phòng) vs comparables, VHM/Vingroup '
        'HOSE prices, dated events and reasoned 2027-2029 outlook scenarios. '
        'Machine-readable summary inside; full dataset at data.json.">\n<title>')
    html = html.replace("</footer>",
                        "</footer>\n" + machine_summary(data))

    DOCS.mkdir(exist_ok=True)
    (DOCS / "index.html").write_text(html)
    (DOCS / "data.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=1))
    (DOCS / "llms.txt").write_text(LLMS_TXT.format(asof=data["asof"]))
    for asset in ("manifest.json", "icon.png"):
        shutil.copy(WEB / asset, DOCS / asset)
    print(f"docs/index.html built ({len(html) // 1024} KB), as of {data['asof']}")


LLMS_TXT = """# Vũ Yên Research — AI access guide (static site)

Interactive charts for Vinhomes Royal Island (Vũ Yên island, Hải Phòng,
Việt Nam): USD per m² vs comparable projects, VHM/Vingroup HOSE stock
prices, dated events, and reasoned 2027-2029 outlook scenarios.

- ./data.json — full structured dataset (candles, USD/m² points with
  sources, events, outlook scenarios with rationale). Snapshot: {asof}.
- ./index.html — the chart app; contains a <section id="machine-summary">
  with the same key numbers as static HTML.
- Source repo (live API + satellite change detection + MCP server):
  https://github.com/areporeporepo/quant-invest-research

Prices: HOSE quotes in thousands of VND; USD/m² converted at yearly-average
FX. Scenario outlooks are stated assumptions, not forecasts. Research and
education only — not investment advice.
"""


def machine_summary(data: dict) -> str:
    """Static HTML digest of the key numbers for non-JS readers."""
    rows = []
    for key, proj in data["psm"]["projects"].items():
        first, last = proj["points"][0], proj["points"][-1]
        rows.append(
            f"<tr><td>{proj['label']}</td>"
            f"<td>{first['time'][:7]}: ${first['value']:.0f}</td>"
            f"<td>{last['time'][:7]}: ${last['value']:.0f}</td>"
            f"<td>{last.get('source', '')[:90]}</td></tr>")
    import datetime as dt
    proj_outlooks = []
    for key, cone in data.get("psm_outlooks", {}).get("cones", {}).items():
        anchor = cone["anchor"]
        a = dt.date.fromisoformat(anchor["date"][:10])
        scen = []
        for name in ("bull", "base", "bear"):
            sc = cone["scenarios"].get(name)
            if not sc:
                continue
            vals = []
            for y in (2027, 2028, 2029):
                yrs = (dt.date(y, 12, 31) - a).days / 365.25
                vals.append(f"{y}: ${anchor['value'] * (1 + sc['annual_rate']) ** yrs:,.0f}")
            scen.append(
                f"<li><b>{name} ({sc['annual_rate']:+.0%}/yr assumption)</b> — "
                f"{' · '.join(vals)} per m². {sc.get('rationale', sc.get('label', ''))}</li>")
        proj_outlooks.append(
            f"<h3>{cone.get('label', key)} (anchor {anchor['date'][:10]} at "
            f"${anchor['value']:,.0f}/m²)</h3><ul>{''.join(scen)}</ul>")
    events = "".join(
        f"<li>{e['date']} — {e['title']}: {e.get('detail', '')} "
        f"(source: {e.get('source', '')})</li>"
        for e in sorted(data["events"], key=lambda e: e["date"], reverse=True))
    closes = " · ".join(
        f"{tk} {c[-1]['close']} ({data.get('units', {}).get(tk, '')})"
        for tk, c in data["candles"].items())
    return f"""<section id="machine-summary" hidden aria-hidden="true">
<h1>Vũ Yên Research — machine-readable summary (as of {data['asof']})</h1>
<p>Educational research on Vinhomes Royal Island (Vũ Yên island, Hải Phòng,
Vietnam) and Vingroup-family HOSE stocks. Not investment advice. Full
structured data: <a href="data.json">data.json</a>.</p>
<h2>Latest HOSE closes (thousand VND, {data['asof']})</h2>
<p>{closes}</p>
<h2>USD per m² by project (first → latest sourced point)</h2>
<table><tr><th>Project</th><th>First</th><th>Latest</th><th>Latest source</th></tr>
{''.join(rows)}</table>
<p>FX: {data['psm']['fx']['vnd_per_usd']:.0f} VND/USD ({data['psm']['fx']['source']});
historical points converted at yearly-average FX.</p>
<h2>USD/m² outlook scenarios to 2029 — ALL projects (assumptions with reasoning, not forecasts)</h2>
{''.join(proj_outlooks)}
<p>Caveat: low-rise headline prices bundle vouchers, discounts and 0%-interest
support — effective prices sit below headline.</p>
<h2>Satellite land-cover change per site (Sentinel-2 NDVI, season-matched windows; scene IDs included for reproducibility)</h2>
<p>IMPORTANT: figures are GROSS vegetation-loss/gain over a ~4,100 ha window centred
on each site — they include farmland rotation and water-level change around the
project, not just construction. Treat as an activity screen, not measured
build-out.</p>
{satellite_html(data)}
<h2>Events (newest first)</h2>
<ul>{events}</ul>
</section>"""


def satellite_html(data: dict) -> str:
    sat = data.get("satellite") or {}
    sites = sat.get("sites") or {}
    if not sites:
        return "<p>No cached satellite findings.</p>"
    w = sat.get("windows", {})
    rows = []
    for k, v in sites.items():
        if v.get("ok"):
            rows.append(f"<li>{v['name']}: NDVI loss {v['cleared_ha']} ha, "
                        f"NDVI gain {v['revegetated_ha']} ha "
                        f"(scenes {v['scene_a']['id']} → {v['scene_b']['id']})</li>")
        else:
            rows.append(f"<li>{v['name']}: no result — {v.get('reason','')[:120]}</li>")
    return (f"<p>Windows: {w.get('a')} vs {w.get('b')}.</p><ul>"
            + "".join(rows) + "</ul>")


if __name__ == "__main__":
    build()
