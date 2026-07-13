/* Vũ Yên Research — interactive charts (TradingView Lightweight Charts).
   Two views:
     Markets : real OHLC candles (DNSE) + event markers + 2026-29 scenario cone
     USD/m²  : curated project price-per-m² series + benchmark + cone
   All data comes from our own /api endpoints. */

const $ = (id) => document.getElementById(id);
const chartEl = $('chart');

const chart = LightweightCharts.createChart(chartEl, {
  layout: { background: { color: '#0d1117' }, textColor: '#8b949e' },
  grid: { vertLines: { color: '#161b22' }, horzLines: { color: '#161b22' } },
  crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
  timeScale: { borderColor: '#21262d', timeVisible: false },
  rightPriceScale: { borderColor: '#21262d' },
  handleScroll: true, handleScale: true,
});
new ResizeObserver(() => chart.resize(chartEl.clientWidth, chartEl.clientHeight))
  .observe(chartEl);

const CONE_STYLE = {
  bear: { color: '#ef5350' }, base: { color: '#8b949e' }, bull: { color: '#26a69a' },
};
const PROJECT_COLORS = ['#2f81f7', '#e3b341', '#26a69a', '#ef5350', '#b083f0',
                        '#f78166', '#79c0ff'];

let view = 'market';
let ticker = 'VHM';
let series = [];            // active chart series handles
let eventsCache = null;
let psmCache = null;

function clearSeries() {
  series.forEach((s) => chart.removeSeries(s));
  series = [];
}

function setStatus(t) { $('status').textContent = t; }
function setDetail(html) { $('detail').innerHTML = html; }

function legend(items) {
  $('legend').innerHTML = items.map((i) =>
    `<span><span class="dot" style="background:${i.color}"></span>${i.label}</span>`
  ).join('');
}

async function getJSON(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${url} -> ${r.status}`);
  return r.json();
}

async function loadEvents() {
  if (!eventsCache) eventsCache = (await getJSON('/api/events')).events;
  return eventsCache;
}

function renderEventList(events) {
  $('evlist').innerHTML = events.map((e, i) =>
    `<div class="ev" data-i="${i}"><span class="d">${e.date}</span>
     <span class="t">${e.title}<small>${e.detail || ''}</small></span></div>`
  ).join('');
  [...document.querySelectorAll('.ev')].forEach((el) => {
    el.onclick = () => {
      const e = events[+el.dataset.i];
      setDetail(`<b>${e.date} — ${e.title}</b><br>${e.detail || ''}` +
        (e.source ? `<br>Source: ${e.source}` : '') +
        (e.url ? `<br><a href="${e.url}" target="_blank" rel="noopener">${e.url}</a>` : ''));
      try {
        chart.timeScale().setVisibleRange({
          from: shiftDate(e.date, -120), to: shiftDate(e.date, 120),
        });
      } catch (_) { /* date outside data range */ }
    };
  });
}

function shiftDate(iso, days) {
  const d = new Date(iso);
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10);
}

function markersFromEvents(events, minTime) {
  return events
    .filter((e) => !minTime || e.date >= minTime)
    .map((e) => ({
      time: e.date, position: 'aboveBar', color: '#e3b341',
      shape: 'arrowDown', text: e.short || e.title.slice(0, 18),
    }));
}

function drawCone(cone, priceScaleId) {
  for (const [name, sc] of Object.entries(cone.scenarios)) {
    const line = chart.addLineSeries({
      color: CONE_STYLE[name]?.color || '#8b949e',
      lineWidth: name === 'base' ? 2 : 1,
      lineStyle: LightweightCharts.LineStyle.Dashed,
      priceScaleId: priceScaleId || 'right',
      lastValueVisible: false, priceLineVisible: false,
      crosshairMarkerVisible: false,
    });
    line.setData([{ time: cone.anchor.date, value: cone.anchor.value },
                  ...sc.path.map((p) => ({ time: p.time, value: p.value }))]);
    series.push(line);
  }
}

/* ---------------- Markets view ---------------- */

async function showMarket() {
  clearSeries();
  setStatus('loading ' + ticker + '…');
  const [data, events, cone] = await Promise.all([
    getJSON(`/api/candles?ticker=${ticker}`),
    loadEvents(),
    getJSON(`/api/outlook?series=${ticker}`),
  ]);
  const candles = chart.addCandlestickSeries({
    upColor: '#26a69a', downColor: '#ef5350', borderVisible: false,
    wickUpColor: '#26a69a', wickDownColor: '#ef5350',
  });
  candles.setData(data.candles);
  series.push(candles);

  const relevant = events.filter((e) =>
    e.relevance === 'macro' || e.relevance === 'vu_yen' ||
    e.relevance === ticker.toLowerCase() ||
    (ticker === 'VHM' && e.relevance === 'vhm'));
  candles.setMarkers(markersFromEvents(relevant, data.candles[0]?.time));
  drawCone(cone, 'right');

  chart.timeScale().fitContent();
  legend([
    { color: '#26a69a', label: `${ticker} daily (thousand VND, real/DNSE)` },
    { color: '#e3b341', label: 'events' },
    { color: '#ef5350', label: `bear ${pct(cone, 'bear')}` },
    { color: '#8b949e', label: `base ${pct(cone, 'base')}` },
    { color: '#26a69a', label: `bull ${pct(cone, 'bull')} → 2029 (scenarios, not forecasts)` },
  ]);
  renderEventList(relevant);
  setStatus(`${ticker} · last ${data.candles.at(-1).close} · ${data.candles.length} sessions`);

  candles.setData && chart.subscribeClick((param) => {
    if (!param.time) return;
    const hit = relevant.find((e) => e.date === param.time);
    if (hit) setDetail(`<b>${hit.date} — ${hit.title}</b><br>${hit.detail || ''}` +
      (hit.url ? `<br><a href="${hit.url}" target="_blank" rel="noopener">source</a>` : ''));
  });
}

function pct(cone, name) {
  const r = cone.scenarios[name]?.annual_rate;
  return r === undefined ? '' : `${(r * 100).toFixed(0)}%/yr`;
}

/* ---------------- USD/m² view ---------------- */

async function showPsm() {
  clearSeries();
  setStatus('loading USD/m²…');
  const [psm, events] = await Promise.all([
    psmCache ? Promise.resolve(psmCache) : getJSON('/api/psm'),
    loadEvents(),
  ]);
  psmCache = psm;
  const keys = Object.keys(psm.projects);
  if (!keys.length) {
    setStatus('no USD/m² data yet');
    setDetail('data/psm.json is empty — seed it to light up this chart.');
    legend([]);
    $('evlist').innerHTML = '';
    return;
  }
  const legendItems = [];
  const allPoints = [];
  keys.forEach((k, i) => {
    const proj = psm.projects[k];
    const color = PROJECT_COLORS[i % PROJECT_COLORS.length];
    const line = chart.addLineSeries({
      color, lineWidth: 2, priceScaleId: 'right',
      title: '', lastValueVisible: false, priceLineVisible: false,
      pointMarkersVisible: true,
    });
    line.setData(proj.points.map((p) => ({ time: p.time, value: p.value })));
    series.push(line);
    legendItems.push({ color, label: proj.label });
    proj.points.forEach((p) => allPoints.push({ ...p, project: proj.label }));
  });

  // Scenario cone anchored on Vũ Yên's latest curated point, if present.
  const vuYenKey = keys.find((k) => k.includes('vu_yen'));
  if (vuYenKey) {
    try {
      drawCone(await getJSON(`/api/outlook?series=psm:${vuYenKey}`), 'right');
      legendItems.push({ color: '#8b949e', label: 'scenario cone → 2029 (assumptions, not forecasts)' });
    } catch (_) { /* no cone without data */ }
  }

  const vuYenEvents = events.filter((e) => e.relevance === 'vu_yen' || e.relevance === 'macro');
  if (series[0]) series[0].setMarkers(markersFromEvents(vuYenEvents));
  chart.timeScale().fitContent();
  legend(legendItems);
  renderEventList(vuYenEvents);
  const fx = psm.fx ? ` · FX ${Math.round(psm.fx.vnd_per_usd)} VND/USD (${psm.fx.source})` : '';
  setStatus(`USD per m² · ${allPoints.length} sourced points${fx}`);

  chart.subscribeClick((param) => {
    if (!param.time || view !== 'psm') return;
    const hits = allPoints.filter((p) => p.time === param.time);
    if (hits.length) {
      setDetail(hits.map((h) =>
        `<b>${h.project}</b> — ${h.time}: $${h.value}/m² (${h.segment}, ${h.kind})` +
        (h.source ? `<br>Source: ${h.source}` : '') +
        (h.url ? ` — <a href="${h.url}" target="_blank" rel="noopener">link</a>` : '')
      ).join('<hr style="border-color:#21262d">'));
    }
  });
}

/* ---------------- Tabs & ticker chips ---------------- */

const TICKERS = ['VHM', 'VIC', 'VRE', 'VPL', 'VEF'];

function renderChips() {
  if (view === 'market') {
    $('chips').innerHTML = TICKERS.map((t) =>
      `<button class="${t === ticker ? 'on' : ''}" data-t="${t}">${t}</button>`).join('');
    [...$('chips').children].forEach((b) => {
      b.onclick = () => { ticker = b.dataset.t; renderChips(); showMarket().catch(fail); };
    });
  } else {
    $('chips').innerHTML = '';
  }
}

function setView(v) {
  view = v;
  $('tab-market').classList.toggle('active', v === 'market');
  $('tab-psm').classList.toggle('active', v === 'psm');
  renderChips();
  (v === 'market' ? showMarket() : showPsm()).catch(fail);
}

function fail(e) {
  setStatus('error');
  setDetail(`Failed to load: ${e.message}`);
}

$('tab-market').onclick = () => setView('market');
$('tab-psm').onclick = () => setView('psm');

setView('market');
/* Auto-refresh market data every 5 minutes while the app is open. */
setInterval(() => { if (view === 'market') showMarket().catch(() => {}); }, 300000);
