/* Vũ Yên Research — interactive charts (TradingView Lightweight Charts).
   Two views:
     Markets : real OHLC candles (DNSE) + event markers + 2026-29 scenario cone
     USD/m²  : curated project price-per-m² series + benchmark + cone
   All data comes from our own /api endpoints. */

const $ = (id) => document.getElementById(id);
const chartEl = $('chart');

/* ---------------- i18n: Vietnamese-first, EN toggle ---------------- */

const I18N = {
  vi: {
    tab_market: 'Thị trường', tab_psm: 'USD / m²',
    loading: 'đang tải…', error: 'lỗi',
    tap_hint: 'Chạm vào điểm đánh dấu hoặc sự kiện để xem chi tiết và nguồn.',
    events: 'Sự kiện', sessions: 'phiên', last: 'giá cuối',
    legend_daily: (t) => `${t} theo ngày (nghìn VND, dữ liệu thật/DNSE)`,
    legend_events: 'sự kiện',
    bear: 'Kịch bản xấu', base: 'Cơ sở', bull: 'Tích cực',
    to2029: '→ 2029 (kịch bản giả định, không phải dự báo)',
    no_psm: 'chưa có dữ liệu USD/m²',
    seed_psm: 'data/psm.json đang trống — thêm dữ liệu để hiển thị biểu đồ này.',
    psm_status: (n) => `USD trên m² · ${n} điểm có nguồn dẫn`,
    cone_psm: 'vùng kịch bản → 2029 (giả định, không phải dự báo)',
    source: 'Nguồn', per_year: '%/năm',
    outlook_title: 'Triển vọng USD/m² Vũ Yên → 2029 (kịch bản có lập luận)',
    ev_all: 'Tất cả', ev_vu_yen: 'Vũ Yên', ev_vhm: 'VHM/Vingroup', ev_macro: 'Vĩ mô',
    voucher_note: 'Lưu ý: giá niêm yết thấp tầng thường kèm voucher, chiết khấu và hỗ trợ ' +
      'lãi suất 0% — giá thực trả thấp hơn niêm yết, nên đà tăng có thể bị phóng đại.',
    assumption: 'giả định',
    disclaimer: 'Chỉ phục vụ nghiên cứu và học tập — không phải lời khuyên đầu tư. ' +
      'Vùng kịch bản là giả định minh hoạ, không phải dự báo. Dữ liệu cổ phiếu: ' +
      'DNSE (nghìn VND). Điểm USD/m² được tuyển chọn từ nguồn công khai; chạm vào ' +
      'từng điểm để xem trích dẫn.',
    failed: 'Không tải được',
  },
  en: {
    tab_market: 'Markets', tab_psm: 'USD / m²',
    loading: 'loading…', error: 'error',
    tap_hint: 'Tap a marker or an event to see details and its source.',
    events: 'Events', sessions: 'sessions', last: 'last',
    legend_daily: (t) => `${t} daily (thousand VND, real/DNSE)`,
    legend_events: 'events',
    bear: 'Bear', base: 'Base', bull: 'Bull',
    to2029: '→ 2029 (scenarios, not forecasts)',
    no_psm: 'no USD/m² data yet',
    seed_psm: 'data/psm.json is empty — seed it to light up this chart.',
    psm_status: (n) => `USD per m² · ${n} sourced points`,
    cone_psm: 'scenario cone → 2029 (assumptions, not forecasts)',
    source: 'Source', per_year: '%/yr',
    outlook_title: 'Vũ Yên USD/m² outlook → 2029 (reasoned scenarios)',
    ev_all: 'All', ev_vu_yen: 'Vũ Yên', ev_vhm: 'VHM/Vingroup', ev_macro: 'Macro',
    voucher_note: 'Note: low-rise headline prices usually bundle vouchers, discounts and ' +
      '0%-interest support — effective prices are below headline, so gains may be overstated.',
    assumption: 'assumption',
    disclaimer: 'Research & education only — not investment advice. Scenario ' +
      'cones are illustrative assumptions, not forecasts. Stock data: DNSE ' +
      'public feed (thousand VND). USD/m² points are curated from public ' +
      'sources; tap any point for its citation.',
    failed: 'Failed to load',
  },
};

let lang = localStorage.getItem('lang') || 'vi';
const t = (key, ...args) => {
  const v = (I18N[lang] || I18N.vi)[key];
  return typeof v === 'function' ? v(...args) : (v ?? key);
};

function evTitle(e) { return (lang === 'vi' && e.title_vi) ? e.title_vi : e.title; }
function evDetail(e) { return (lang === 'vi' && e.detail_vi) ? e.detail_vi : (e.detail || ''); }
function evShort(e) { return (lang === 'vi' && e.short_vi) ? e.short_vi : (e.short || evTitle(e).slice(0, 18)); }

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

let view = 'psm';
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

let evFilter = 'all';

function renderEventFilter(events, rerender) {
  const counts = { all: events.length };
  events.forEach((e) => { counts[e.relevance] = (counts[e.relevance] || 0) + 1; });
  const opts = ['all', 'vu_yen', 'vhm', 'macro'].filter((k) => counts[k]);
  $('evfilter').innerHTML = opts.map((k) =>
    `<option value="${k}" ${k === evFilter ? 'selected' : ''}>${t('ev_' + k)} (${counts[k]})</option>`
  ).join('');
  $('evfilter').onchange = () => { evFilter = $('evfilter').value; rerender(); };
}

function renderEventList(allEvents) {
  renderEventFilter(allEvents, () => renderEventList(allEvents));
  // Newest first — the most recent catalysts matter most.
  const events = allEvents
    .filter((e) => evFilter === 'all' || e.relevance === evFilter)
    .slice()
    .sort((a, b) => b.date.localeCompare(a.date));
  $('evlist').innerHTML = events.map((e, i) =>
    `<div class="ev" data-i="${i}"><span class="d">${e.date}</span>
     <span class="t">${evTitle(e)}<small>${evDetail(e)}</small></span></div>`
  ).join('');
  [...document.querySelectorAll('.ev')].forEach((el) => {
    el.onclick = () => {
      const e = events[+el.dataset.i];
      setDetail(`<b>${e.date} — ${evTitle(e)}</b><br>${evDetail(e)}` +
        (e.source ? `<br>${t('source')}: ${e.source}` : '') +
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

function markersFromEvents(events, minTime, withText = true) {
  return events
    .filter((e) => !minTime || e.date >= minTime)
    .map((e) => ({
      time: e.date, position: 'aboveBar', color: '#e3b341',
      shape: withText ? 'arrowDown' : 'circle',
      text: withText ? evShort(e) : undefined,
      size: withText ? 1 : 0.6,
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
  $('outlook').innerHTML = '';
  setStatus(t('loading'));
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
    { color: '#26a69a', label: t('legend_daily', ticker) },
    { color: '#e3b341', label: t('legend_events') },
    { color: '#ef5350', label: `${t('bear')} ${pct(cone, 'bear')}` },
    { color: '#8b949e', label: `${t('base')} ${pct(cone, 'base')}` },
    { color: '#26a69a', label: `${t('bull')} ${pct(cone, 'bull')} ${t('to2029')}` },
  ]);
  renderEventList(relevant);
  setStatus(`${ticker} · ${t('last')} ${data.candles.at(-1).close} · ${data.candles.length} ${t('sessions')}`);

  candles.setData && chart.subscribeClick((param) => {
    if (!param.time) return;
    const hit = relevant.find((e) => e.date === param.time);
    if (hit) setDetail(`<b>${hit.date} — ${evTitle(hit)}</b><br>${evDetail(hit)}` +
      (hit.url ? `<br><a href="${hit.url}" target="_blank" rel="noopener">${t('source').toLowerCase()}</a>` : ''));
  });
}

function pct(cone, name) {
  const r = cone.scenarios[name]?.annual_rate;
  return r === undefined ? '' : `${(r * 100).toFixed(0)}${t('per_year')}`;
}

/* ---------------- USD/m² view ---------------- */

async function showPsm() {
  clearSeries();
  setStatus(t('loading'));
  const [psm, events] = await Promise.all([
    psmCache ? Promise.resolve(psmCache) : getJSON('/api/psm'),
    loadEvents(),
  ]);
  psmCache = psm;
  const keys = Object.keys(psm.projects);
  if (!keys.length) {
    setStatus(t('no_psm'));
    setDetail(t('seed_psm'));
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
  const vuYenKey = keys.find((k) => k.includes('vu_yen_royal_island')) ||
                   keys.find((k) => k.includes('vu_yen'));
  if (vuYenKey) {
    try {
      const cone = await getJSON(`/api/outlook?series=psm:${vuYenKey}`);
      drawCone(cone, 'right');
      legendItems.push({ color: '#8b949e', label: t('cone_psm') });
      renderOutlookCard(cone);
    } catch (_) { $('outlook').innerHTML = ''; }
  }

  const vuYenEvents = events.filter((e) => e.relevance === 'vu_yen' || e.relevance === 'macro');
  // Quiet dots on the sparse USD/m² chart — labels live in the list below.
  if (series[0]) series[0].setMarkers(markersFromEvents(vuYenEvents, null, false));
  chart.timeScale().fitContent();
  legend(legendItems);
  renderEventList(vuYenEvents);
  const fx = psm.fx ? ` · ${Math.round(psm.fx.vnd_per_usd)} VND/USD` : '';
  setStatus(t('psm_status', allPoints.length) + fx);

  chart.subscribeClick((param) => {
    if (!param.time || view !== 'psm') return;
    const hits = allPoints.filter((p) => p.time === param.time);
    if (hits.length) {
      setDetail(hits.map((h) =>
        `<b>${h.project}</b> — ${h.time}: $${h.value}/m² (${h.segment}, ${h.kind})` +
        (h.source ? `<br>${t('source')}: ${h.source}` : '') +
        (h.url ? ` — <a href="${h.url}" target="_blank" rel="noopener">link</a>` : '')
      ).join('<hr style="border-color:#21262d">'));
    }
  });
}

/* ---------------- Outlook reasoning card ---------------- */

function yearsBetween(a, b) { return (new Date(b) - new Date(a)) / 31557600000; }

function renderOutlookCard(cone) {
  if (!cone || !cone.scenarios) { $('outlook').innerHTML = ''; return; }
  const order = ['bull', 'base', 'bear'];
  const anchor = cone.anchor;
  const yearEnds = ['2027-12-31', '2028-12-31', '2029-12-31'];
  const cards = order.filter((k) => cone.scenarios[k]).map((k) => {
    const sc = cone.scenarios[k];
    const label = (lang === 'vi' && sc.label_vi) ? sc.label_vi : sc.label;
    const why = (lang === 'vi' && sc.rationale_vi) ? sc.rationale_vi : (sc.rationale || '');
    const vals = yearEnds.map((d) => {
      const v = anchor.value * Math.pow(1 + sc.annual_rate, yearsBetween(anchor.date, d));
      return `${d.slice(0, 4)}: $${Math.round(v).toLocaleString('en-US')}`;
    }).join(' · ');
    const pctTxt = `${sc.annual_rate > 0 ? '+' : ''}${(sc.annual_rate * 100).toFixed(0)}${t('per_year')}`;
    return `<div class="card">
      <b><span class="dot" style="background:${CONE_STYLE[k]?.color}"></span>${label} (${pctTxt} ${t('assumption')})</b>
      <div class="vals">${vals} /m²</div>
      ${why ? `<p>${why}</p>` : ''}
    </div>`;
  });
  $('outlook').innerHTML = `<h2>${t('outlook_title')}</h2>` + cards.join('') +
    `<div class="card"><p>${t('voucher_note')}</p></div>`;
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
  setStatus(t('error'));
  setDetail(`${t('failed')}: ${e.message}`);
}

function applyStaticText() {
  $('tab-market').textContent = t('tab_market');
  $('tab-psm').textContent = t('tab_psm');
  $('detail').textContent = t('tap_hint');
  document.querySelector('#events h2').textContent = t('events');
  $('disclaimer').textContent = t('disclaimer');
  $('lang').textContent = lang === 'vi' ? 'EN' : 'VI';
  document.documentElement.lang = lang;
}

$('tab-market').onclick = () => setView('market');
$('tab-psm').onclick = () => setView('psm');
$('lang').onclick = () => {
  lang = lang === 'vi' ? 'en' : 'vi';
  localStorage.setItem('lang', lang);
  applyStaticText();
  setView(view);
};

applyStaticText();
setView('psm');
/* Auto-refresh market data every 5 minutes while the app is open. */
setInterval(() => { if (view === 'market') showMarket().catch(() => {}); }, 300000);
