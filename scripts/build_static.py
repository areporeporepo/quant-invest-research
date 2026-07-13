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
    for tk in ["VHM", "VIC", "VRE", "VPL", "VEF"]:
        data["candles"][tk] = get(f"/api/candles?ticker={tk}")["candles"][-420:]
        data["outlook"][tk] = get(f"/api/outlook?series={tk}")
    data["psm"] = get("/api/psm")
    data["outlook"]["psm:vu_yen_royal_island"] = get(
        "/api/outlook?series=psm:vu_yen_royal_island")
    data["events"] = get("/api/events")["events"]
    data["asof"] = data["candles"]["VHM"][-1]["time"]
    return data


LIVE_GETJSON = """async function getJSON(url) {
  // Static build: try LIVE data first, fall back to the embedded snapshot.
  if (url.startsWith('/api/candles')) {
    const tk = new URLSearchParams(url.split('?')[1]).get('ticker') || 'VHM';
    try {
      const now = Math.floor(Date.now() / 1000);
      const r = await fetch('https://services.entrade.com.vn/chart-api/v2/ohlcs/stock' +
        `?symbol=${tk}&resolution=1D&from=${now - 86400 * 800}&to=${now}`,
        { signal: AbortSignal.timeout(6000) });
      if (!r.ok) throw new Error(r.status);
      const d = await r.json();
      if (!d.c || !d.c.length) throw new Error('empty');
      window.__live = true;
      return { ticker: tk, candles: d.t.map((tt, i) => ({
        time: new Date(tt * 1000).toISOString().slice(0, 10),
        open: d.o[i], high: d.h[i], low: d.l[i], close: d.c[i], volume: d.v[i],
      })) };
    } catch (_) {
      window.__live = false;
      return { ticker: tk, candles: DATA.candles[tk] || [] };
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

    DOCS.mkdir(exist_ok=True)
    (DOCS / "index.html").write_text(html)
    for asset in ("manifest.json", "icon.png"):
        shutil.copy(WEB / asset, DOCS / asset)
    print(f"docs/index.html built ({len(html) // 1024} KB), as of {data['asof']}")


if __name__ == "__main__":
    build()
