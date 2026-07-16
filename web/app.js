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
    legend_daily: (t, u) => `${t} theo ngày (${u}, dữ liệu thật)`,
    unit_thousand_vnd: 'nghìn VND', unit_points: 'điểm', unit_usd: 'USD',
    legend_events: 'sự kiện',
    bear: 'Kịch bản xấu', base: 'Cơ sở', bull: 'Tích cực',
    to2029: '→ 2029 (kịch bản giả định, không phải dự báo)',
    no_psm: 'chưa có dữ liệu USD/m²',
    seed_psm: 'data/psm.json đang trống — thêm dữ liệu để hiển thị biểu đồ này.',
    psm_status: (n) => `USD trên m² · ${n} điểm có nguồn dẫn`,
    cone_psm: 'vùng kịch bản → 2029 (giả định, không phải dự báo)',
    cone_all: 'nét đứt = kịch bản cơ sở từng dự án → 2029; xấu/tích cực cho dự án đang chọn',
    source: 'Nguồn', per_year: '%/năm',
    outlook_title: (l) => `Triển vọng ${l} → 2029 (kịch bản có lập luận)`,
    tab_sat: 'Vệ tinh',
    sat_vuyen: 'Vũ Yên', sat_catba: 'Cát Bà', sat_halong: 'Hạ Long Xanh',
    gif_caption_daily: (n) => `Time-lapse ${n} — mỗi khung = một ngày quang mây, Planet 3 m, phóng vào khu vực đang thay đổi.`,
    gif_pending: 'GIF cho khu vực này đang được dựng — quay lại sau ít phút.',
    pm_title: 'Số đo Planet 3 m (tỷ lệ % trên vùng ảnh phủ — so sánh %, không so sánh ha tuyệt đối)',
    pm_none: 'Chưa có số đo Planet cho khu vực này — routine hằng ngày sẽ bổ sung.',
    outlook_all: 'Triển vọng 2029 — tất cả dự án (USD/m², giả định)',
    outlook_hint: 'Chạm một dự án để xem lập luận và vẽ vùng kịch bản lên biểu đồ.',
    col_project: 'Dự án', col_bear: 'Xấu', col_base: 'Cơ sở', col_bull: 'Tích cực',
    ev_all: 'Tất cả', ev_vu_yen: 'Vũ Yên', ev_cat_ba: 'Cát Bà', ev_ha_long_xanh: 'Hạ Long Xanh', ev_vhm: 'VHM/Vingroup', ev_macro: 'Vĩ mô',
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
    legend_daily: (t, u) => `${t} daily (${u}, real data)`,
    unit_thousand_vnd: 'thousand VND', unit_points: 'points', unit_usd: 'USD',
    legend_events: 'events',
    bear: 'Bear', base: 'Base', bull: 'Bull',
    to2029: '→ 2029 (scenarios, not forecasts)',
    no_psm: 'no USD/m² data yet',
    seed_psm: 'data/psm.json is empty — seed it to light up this chart.',
    psm_status: (n) => `USD per m² · ${n} sourced points`,
    cone_psm: 'scenario cone → 2029 (assumptions, not forecasts)',
    cone_all: 'dashed = each project\'s base scenario → 2029; bear/bull for the selected one',
    source: 'Source', per_year: '%/yr',
    outlook_title: (l) => `${l} outlook → 2029 (reasoned scenarios)`,
    tab_sat: 'Satellite',
    sat_vuyen: 'Vũ Yên', sat_catba: 'Cát Bà', sat_halong: 'Hạ Long Xanh',
    gif_caption_daily: (n) => `${n} time-lapse — one frame per clear day, Planet 3 m, zoomed on the changing area.`,
    gif_pending: 'This site\'s GIF is still rendering — check back shortly.',
    pm_title: 'Planet 3 m metrics (% of covered area — compare shares, not absolute ha)',
    pm_none: 'No Planet metrics for this site yet — the daily routine will add them.',
    outlook_all: '2029 outlook — all projects (USD/m², assumptions)',
    outlook_hint: 'Tap a project to see its reasoning and draw its cone on the chart.',
    col_project: 'Project', col_bear: 'Bear', col_base: 'Base', col_bull: 'Bull',
    ev_all: 'All', ev_vu_yen: 'Vũ Yên', ev_cat_ba: 'Cát Bà', ev_ha_long_xanh: 'Hạ Long Xanh', ev_vhm: 'VHM/Vingroup', ev_macro: 'Macro',
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

/* Lightweight Charts v5 (2026 architecture): unified addSeries API,
   markers as a plugin, and an always-logarithmic price scale so long
   trends read as slope, not compounding illusion. */
const chart = LightweightCharts.createChart(chartEl, {
  layout: { background: { color: '#0d1117' }, textColor: '#8b949e' },
  grid: { vertLines: { color: '#161b22' }, horzLines: { color: '#161b22' } },
  crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
  timeScale: { borderColor: '#21262d', timeVisible: false },
  rightPriceScale: { borderColor: '#21262d',
                     mode: LightweightCharts.PriceScaleMode.Logarithmic },
  handleScroll: true, handleScale: true,
});

function applyMarkers(s, markers) {
  LightweightCharts.createSeriesMarkers(s, markers);
}
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
let outlooksCache = null;
let outlookKey = 'vu_yen_royal_island';

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
  const opts = ['all', 'vu_yen', 'cat_ba', 'ha_long_xanh', 'vhm', 'macro'].filter((k) => counts[k]);
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

function drawCone(cone, priceScaleId, only) {
  for (const [name, sc] of Object.entries(cone.scenarios)) {
    if (only && !only.includes(name)) continue;
    const line = chart.addSeries(LightweightCharts.LineSeries, {
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
  const candles = chart.addSeries(LightweightCharts.CandlestickSeries, {
    upColor: '#26a69a', downColor: '#ef5350', borderVisible: false,
    wickUpColor: '#26a69a', wickDownColor: '#ef5350',
  });
  candles.setData(data.candles);
  series.push(candles);

  const relevant = events.filter((e) =>
    e.relevance === 'macro' || e.relevance === 'vu_yen' || e.relevance === 'cat_ba' || e.relevance === 'ha_long_xanh' ||
    e.relevance === ticker.toLowerCase() ||
    (ticker === 'VHM' && e.relevance === 'vhm'));
  applyMarkers(candles, markersFromEvents(relevant, data.candles[0]?.time));
  drawCone(cone, 'right');

  chart.timeScale().fitContent();
  const unitKey = { 'thousand VND': 'unit_thousand_vnd', 'points': 'unit_points',
                    'USD': 'unit_usd' }[data.unit] || 'unit_thousand_vnd';
  legend([
    { color: '#26a69a', label: t('legend_daily', ticker, t(unitKey)) },
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
  if (!outlooksCache) {
    try { outlooksCache = await getJSON('/api/psm_outlooks'); } catch (_) {}
  }
  const allCones = (outlooksCache && outlooksCache.cones) || {};
  const legendItems = [];
  const allPoints = [];
  keys.forEach((k, i) => {
    const proj = psm.projects[k];
    const color = PROJECT_COLORS[i % PROJECT_COLORS.length];
    const line = chart.addSeries(LightweightCharts.LineSeries, {
      color, lineWidth: 2, priceScaleId: 'right',
      title: '', lastValueVisible: false, priceLineVisible: false,
      pointMarkersVisible: true,
    });
    line.setData(proj.points.map((p) => ({ time: p.time, value: p.value })));
    series.push(line);
    // Every line gets its own dashed base-case extension to 2029.
    const cone = allCones[k];
    if (cone && cone.scenarios && cone.scenarios.base) {
      const ext = chart.addSeries(LightweightCharts.LineSeries, {
        color, lineWidth: 1, lineStyle: LightweightCharts.LineStyle.Dashed,
        priceScaleId: 'right', lastValueVisible: false,
        priceLineVisible: false, crosshairMarkerVisible: false,
      });
      ext.setData([{ time: cone.anchor.date, value: cone.anchor.value },
                   ...cone.scenarios.base.path.map((p) => ({ time: p.time, value: p.value }))]);
      series.push(ext);
    }
    legendItems.push({ color, label: proj.label });
    proj.points.forEach((p) => allPoints.push({ ...p, project: proj.label }));
  });

  // Scenario cone anchored on Vũ Yên's latest curated point, if present.
  try {
    if (!allCones[outlookKey]) outlookKey = keys.find((k) => allCones[k]) || outlookKey;
    const cone = allCones[outlookKey];
    if (cone) {
      // Base extension already drawn per line; add bear/bull spread for
      // the selected project only.
      drawCone(cone, 'right', ['bear', 'bull']);
      legendItems.push({ color: '#8b949e',
        label: `${t('cone_all')} — ${cone.label || outlookKey}` });
      renderOutlookCard(cone);
    }
  } catch (_) { $('outlook').innerHTML = ''; }

  const vuYenEvents = events.filter((e) => ['vu_yen', 'cat_ba', 'ha_long_xanh', 'macro'].includes(e.relevance));
  // Price-affecting events get labels on the chart; macro context stays as
  // quiet dots so the sparse USD/m² series remains readable.
  if (series[0]) {
    const labelled = markersFromEvents(vuYenEvents.filter((e) => ['vu_yen', 'cat_ba', 'ha_long_xanh'].includes(e.relevance)), null, true);
    const dots = markersFromEvents(vuYenEvents.filter((e) => e.relevance !== 'vu_yen'), null, false);
    applyMarkers(series[0],
      [...labelled, ...dots].sort((a, b) => a.time.localeCompare(b.time)));
  }
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

function fmtUsd(v) { return '$' + Math.round(v).toLocaleString('en-US'); }

function val2029(cone, k) {
  const sc = cone.scenarios[k];
  if (!sc) return '';
  const yrs = yearsBetween(cone.anchor.date, '2029-12-31');
  return fmtUsd(cone.anchor.value * Math.pow(1 + sc.annual_rate, yrs));
}

function renderOutlookAll(cones) {
  const keys = Object.keys(cones);
  const rows = keys.map((k) => {
    const c = cones[k];
    const sel = k === outlookKey ? ' class="sel"' : '';
    return `<tr data-k="${k}"${sel}><td>${c.label || k}</td>` +
      `<td>${val2029(c, 'bear')}</td><td>${val2029(c, 'base')}</td>` +
      `<td>${val2029(c, 'bull')}</td></tr>`;
  }).join('');
  return `<h2>${t('outlook_all')}</h2>
  <div class="card" style="padding:6px 8px"><div style="overflow-x:auto">
  <table id="oltable"><tr><th>${t('col_project')}</th><th>${t('col_bear')}</th>
  <th>${t('col_base')}</th><th>${t('col_bull')}</th></tr>${rows}</table></div>
  <p style="padding:4px 4px 2px">${t('outlook_hint')}</p></div>`;
}

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
  $('outlook').innerHTML =
    (outlooksCache ? renderOutlookAll(outlooksCache.cones) : '') +
    `<h2>${t('outlook_title', cone.label || '')}</h2>` + cards.join('') +
    `<div class="card"><p>${t('voucher_note')}</p></div>`;
  if (outlooksCache) {
    [...document.querySelectorAll('#oltable tr[data-k]')].forEach((tr) => {
      tr.onclick = () => { outlookKey = tr.dataset.k; showPsm().catch(fail); };
    });
  }
}

/* ---------------- Satellite view ---------------- */

let satSite = 'vinhomes_vu_yen';
let planetMetricsCache = null;

// Every tracked project gets a Planet daily time-lapse (docs/media/<key>.gif).
const SAT_SITES = {
  vinhomes_vu_yen:    { label: 'Vũ Yên', ev: 'vu_yen', metricsKey: null },
  sun_cat_ba:         { label: 'Cát Bà', ev: 'cat_ba', gif: 'catba_lanbien.gif', metricsKey: 'sun_cat_ba' },
  ha_long_xanh:       { label: 'Hạ Long Xanh', ev: 'ha_long_xanh', metricsKey: 'ha_long_xanh' },
  green_paradise:     { label: 'Cần Giờ', ev: null, metricsKey: null },
  ocean_park_1:       { label: 'Ocean Park 1', ev: null, metricsKey: null },
  ocean_park_2:       { label: 'Ocean Park 2', ev: null, metricsKey: null },
  grand_park:         { label: 'Grand Park', ev: null, metricsKey: null },
  golden_avenue:      { label: 'Móng Cái', ev: null, metricsKey: null },
  vlasta_thuy_nguyen: { label: 'Vlasta', ev: null, metricsKey: null },
  vinhomes_imperia:   { label: 'Imperia', ev: null, metricsKey: null },
  the_minato:         { label: 'Minato', ev: null, metricsKey: null },
  meta_hyperion:      { label: '🌍 Meta Hyperion', ev: null, metricsKey: null },
  stargate_abilene:   { label: '🌍 Stargate TX', ev: null, metricsKey: null },
  palm_jebel_ali:     { label: '🌍 Palm Jebel Ali', ev: null, metricsKey: null },
  amazon_rainier:     { label: '🌍 AWS Rainier', ev: null, metricsKey: null },
  funan_techo:        { label: '🌍 Kênh Funan', ev: null, metricsKey: null },
};

function renderSatChips() {
  $('chips').innerHTML = Object.entries(SAT_SITES).map(([k, c]) =>
    `<button class="${satSite === k ? 'on' : ''}" data-s="${k}">${c.label}</button>`
  ).join('');
  [...$('chips').children].forEach((b) => {
    b.onclick = () => { satSite = b.dataset.s; showSat().catch(fail); };
  });
}

function gifPanel(file, cfg) {
  $('gifbox').innerHTML =
    `<img src="media/${file}" alt="" style="width:100%;border-radius:10px;` +
    `border:1px solid var(--border)" loading="lazy" ` +
    `onerror="this.style.display='none';this.nextElementSibling.textContent=t('gif_pending')">` +
    `<p style="color:var(--muted);font-size:12px;margin:6px 2px">${t('gif_caption_daily', cfg.label)}</p>`;
}

function pmRow(tag, m) {
  if (!m || m.error) return '';
  return `<div class="vals">${tag} ${m.acquired}: nước ${m.water_pct_of_covered}% · ` +
    `đất trống/xây ${m.bare_built_pct_of_covered}% · cây xanh ${m.veg_pct_of_covered}% ` +
    `(phủ ${m.window_ha} ha) — ${m.scene_id}</div>`;
}

async function showSat() {
  renderSatChips();
  clearSeries();
  $('outlook').innerHTML = '';
  legend([]);
  const cfg = SAT_SITES[satSite];
  setStatus(cfg.label);
  gifPanel(cfg.gif || (satSite + '.gif'), cfg);
  let html = '';
  if (cfg.metricsKey) {
    try {
      if (!planetMetricsCache) planetMetricsCache = await getJSON('/api/planet_metrics');
      const m = planetMetricsCache[cfg.metricsKey];
      if (m) html = `<b>${t('pm_title')}</b><br>` + pmRow('nền', m.baseline) + pmRow('nay', m.now);
    } catch (_) {}
  }
  setDetail(html || t('pm_none'));
  const evs = cfg.ev
    ? (await loadEvents()).filter((e) => e.relevance === cfg.ev) : [];
  renderEventList(evs);
}

/* ---------------- Tabs & ticker chips ---------------- */

const TICKERS = ['VHM', 'VIC', 'VRE', 'VPL', 'VEF', 'VNINDEX', 'NVDA', 'SPY'];

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
  $('tab-sat').classList.toggle('active', v === 'sat');
  const satMode = v === 'sat';
  $('chart').style.display = satMode ? 'none' : '';
  $('legend').style.display = satMode ? 'none' : '';
  if (!satMode) { chart.applyOptions({ leftPriceScale: { visible: false } }); $('gifbox').innerHTML = ''; }
  renderChips();
  (v === 'market' ? showMarket() : v === 'sat' ? showSat() : showPsm()).catch(fail);
}

function fail(e) {
  setStatus(t('error'));
  setDetail(`${t('failed')}: ${e.message}`);
}

function applyStaticText() {
  $('tab-market').textContent = t('tab_market');
  $('tab-psm').textContent = t('tab_psm');
  $('tab-sat').textContent = t('tab_sat');
  $('detail').textContent = t('tap_hint');
  document.querySelector('#events h2').textContent = t('events');
  $('disclaimer').textContent = t('disclaimer');
  $('lang').textContent = lang === 'vi' ? 'EN' : 'VI';
  document.documentElement.lang = lang;
}

$('tab-market').onclick = () => setView('market');
$('tab-psm').onclick = () => setView('psm');
$('tab-sat').onclick = () => setView('sat');
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
