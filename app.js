
// ===== Helpers =====
function el(id) { return document.getElementById(id); }

// ===== Global state =====
const state = {
  rows: [],
  tickers: [],
  selectedTicker: null,
  showVolume: true,
  selectedFlag: 'ALL', // 'ALL' | 'ANY' | specific string
  flags: []
};

// ===== CSV source =====
// Use either the remote RAW or the local file (keep one active)
const CSV_URL = "https://raw.githubusercontent.com/rupak-sarkar/screener_view/main/stock_data_with_indicators.csv";
// const CSV_URL = "stock_data_with_indicators.csv";

// ===== Theme switching =====
function setTheme(isDark) {
  const root = document.documentElement;
  if (isDark) {
    root.style.setProperty('--bg', '#0f172a');
    root.style.setProperty('--panel', '#111827');
    root.style.setProperty('--muted', '#64748b');
    root.style.setProperty('--text', '#e5e7eb');
    root.style.setProperty('--accent', '#22d3ee');
    root.style.setProperty('--border', '#1f2937');
    el('themeLabel').textContent = 'Dark Mode';
  } else {
    root.style.setProperty('--bg', '#ffffff');
    root.style.setProperty('--panel', '#f3f4f6');
    root.style.setProperty('--muted', '#6b7280');
    root.style.setProperty('--text', '#1f2937');
    root.style.setProperty('--accent', '#22d3ee');
    root.style.setProperty('--border', '#d1d5db');
    el('themeLabel').textContent = 'Light Mode';
  }
}

// ===== Init =====
function init() {
  const themeSwitch = el('themeSwitch');
  if (themeSwitch) themeSwitch.addEventListener('change', e => setTheme(e.target.checked));
  setTheme(false); // default Light

  el('foldBtn').addEventListener('click', () => el('app').classList.toggle('collapsed'));

  Papa.parse(CSV_URL, {
    download: true,
    header: true,
    dynamicTyping: true,
    skipEmptyLines: true,
    complete: (results) => {
      state.rows = results.data;
      populateFlags();
      computeTickers();
      setupSearchDropdown();
      el('status').textContent = `Loaded ${state.tickers.length} tickers`;
    },
    error: (err) => {
      console.error('CSV load error:', err);
      el('status').textContent = 'Failed to load CSV.';
    }
  });

  const volChk = el('showVolume');
  if (volChk) {
    state.showVolume = volChk.checked;
    volChk.addEventListener('change', (e) => {
      state.showVolume = e.target.checked;
      if (state.selectedTicker) plotSelected(state.selectedTicker);
    });
  }

  const flagSel = el('bbFlagSelect');
  flagSel.addEventListener('change', (e) => {
    state.selectedFlag = e.target.value;        // 'ALL' | 'ANY' | specific
    computeTickers();                            // recompute based on selected flag
    setupSearchDropdown(true);                   // refresh dropdown, clear search
    el('status').textContent = `Filter: ${state.selectedFlag} — ${state.tickers.length} tickers`;
  });
}

// ===== BB_Flag helpers =====
function getBBFlag(row) {
  return row['BB_Flag'] ?? row['BB\\_Flag'] ?? row['BB Flag'] ?? null;
}
function populateFlags() {
  const set = new Set();
  for (const r of state.rows) {
    const v = getBBFlag(r);
    if (v && String(v).trim()) set.add(String(v).trim());
  }
  state.flags = Array.from(set).sort();

  const sel = el('bbFlagSelect');
  sel.innerHTML = '<option value="ALL">All tickers</option><option value="ANY">Any (non‑blank)</option>';
  for (const f of state.flags) {
    const o = document.createElement('option');
    o.value = f; o.textContent = f;
    sel.appendChild(o);
  }
}
function computeTickers() {
  const allTickers = [...new Set(state.rows.map(r => r.Ticker))].filter(Boolean);
  const out = [];
  for (const tk of allTickers) {
    const rows = state.rows
      .filter(r => r.Ticker === tk)
      .sort((a,b) => String(a.Date).localeCompare(String(b.Date)));
    const last7 = rows.slice(-7);

    if (state.selectedFlag === 'ALL') { out.push(tk); continue; }
    if (state.selectedFlag === 'ANY') {
      if (last7.some(r => { const v = getBBFlag(r); return v && String(v).trim(); })) out.push(tk);
      continue;
    }
    // Specific flag selected: must appear in the last 7 rows
    if (last7.some(r => { const v = getBBFlag(r); return v && String(v).trim() === state.selectedFlag; })) out.push(tk);
  }
  state.tickers = out.sort();
}

// ===== Search dropdown =====
function setupSearchDropdown(reset=false) {
  const input = el('search');
  const dropdown = el('searchDropdown');
  if (!input || !dropdown) return;
  if (reset) input.value = '';

  const renderList = (items) => {
    dropdown.innerHTML = '';
    items.forEach(tk => {
      const item = document.createElement('div');
      item.className = 'dropdown-item';
      item.textContent = tk;
      item.addEventListener('mousedown', () => {
        input.value = tk;
        plotSelected(tk);
        dropdown.hidden = true;
      });
      dropdown.appendChild(item);
    });
  };

  const show = () => { dropdown.hidden = false; };
  const hide = () => { dropdown.hidden = true; };

  input.addEventListener('focus', () => { renderList(state.tickers); show(); });
  input.addEventListener('input', () => {
    const q = input.value.trim().toUpperCase();
    const filtered = q ? state.tickers.filter(t => t.toUpperCase().includes(q)) : state.tickers;
    renderList(filtered); show();
  });
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      const tk = input.value.trim();
      if (tk && state.tickers.includes(tk)) { plotSelected(tk); hide(); input.blur(); }
    }
  });
  input.addEventListener('blur', () => setTimeout(hide, 150));
}

// ===== Formatting helpers =====
const fmt = {
  n: (v,d=2) => (v==null||isNaN(v)?'–':Number(v).toFixed(d)),
  pct: v => (v==null||isNaN(v)?'–':(v>0?'+':'')+v.toFixed(2)+'%'),
  vol: v => (v==null?'–':Intl.NumberFormat().format(v)),
  date: s => (s?String(s):'–')
};
function updateInfoStrip(i, s) {
  const deltaPct = ((s.close[i] - s.open[i]) / s.open[i]) * 100;
  el('m_date').textContent   = fmt.date(s.x[i]);
  el('m_open').textContent   = fmt.n(s.open[i]);
  el('m_high').textContent   = fmt.n(s.high[i]);
  el('m_low').textContent    = fmt.n(s.low[i]);
  el('m_close').textContent  = fmt.n(s.close[i]);
  el('m_delta').textContent  = fmt.pct(deltaPct);
  el('m_vol').textContent    = fmt.vol(s.vol[i]);
  el('m_sma22').textContent  = fmt.n(s.sma22[i]);
  el('m_sma52').textContent  = fmt.n(s.sma52[i]);
  el('m_sma200').textContent = fmt.n(s.sma200[i]);
  el('m_bbu').textContent    = fmt.n(s.bbU[i]);
  el('m_bbl').textContent    = fmt.n(s.bbL[i]);
  el('m_rsi').textContent    = fmt.n(s.rsi14[i]);
}
function col(rows, a, b) { return rows.map(r => r[a] ?? r[b] ?? null); }

// ===== Plot =====
function plotSelected(ticker) {
  state.selectedTicker = ticker;

  const rows = state.rows.filter(r => r.Ticker === ticker);
  const x = rows.map(r => r.Date);
  const open  = rows.map(r => r.Open);
  const high  = rows.map(r => r.High);
  const low   = rows.map(r => r.Low);
  const close = rows.map(r => r.Close);
  const vol   = rows.map(r => r.Volume);

  // Indicators
  const sma200 = col(rows, 'SMA_200');
  const sma52  = col(rows, 'SMA_52');
  const sma22  = col(rows, 'SMA_22');
  const bbU    = col(rows, 'BB_upper', 'BB_Upper');
  const bbL    = col(rows, 'BB_lower', 'BB_Lower');
  const rsi14  = col(rows, 'RSI_14');

  const series = { x, open, high, low, close, vol, sma22, sma52, sma200, bbU, bbL, rsi14 };
  const data = [];

  // (A) Invisible helper trace to guarantee hover events (no visual change)
  data.push({
    type: 'scatter',
    x,
    y: close,
    mode: 'lines',
    opacity: 0,
    hoverinfo: 'x',
    hovertemplate: '%{x}',
    name: '',
    showlegend: false,
    xaxis: 'x',
    yaxis: 'y'
  });

  // (B) Candlestick (solid green/red), tooltips suppressed (we use info strip instead)
  data.push({
    type: 'candlestick', x, open, high, low, close,
    increasing: { line: { color: '#16a34a', width: 1 }, fillcolor: '#16a34a' },
    decreasing: { line: { color: '#dc2626', width: 1 }, fillcolor: '#dc2626' },
    name: 'Price', xaxis: 'x', yaxis: 'y', hoverinfo: 'skip'
  });

  // Volume overlay
  if (state.showVolume) {
    data.push({
      type: 'bar', x, y: vol, marker: { color: '#94a3b8' }, name: 'Volume',
      yaxis: 'y2', xaxis: 'x', opacity: 0.6, hoverinfo: 'skip'
    });
  }

  // SMA lines
  if (sma200.some(v => v != null)) data.push({ type: 'scatter', mode: 'lines', x, y: sma200, line: { color: '#000000', width: 1.5 }, name: 'SMA 200', xaxis: 'x', yaxis: 'y', hoverinfo: 'skip' });
  if (sma52 .some(v => v != null)) data.push({ type: 'scatter', mode: 'lines', x, y: sma52 , line: { color: '#dc2626', width: 1.5 }, name: 'SMA 52',  xaxis: 'x', yaxis: 'y', hoverinfo: 'skip' });
  if (sma22 .some(v => v != null)) data.push({ type: 'scatter', mode: 'lines', x, y: sma22 , line: { color: '#16a34a', width: 1.5 }, name: 'SMA 22',  xaxis: 'x', yaxis: 'y', hoverinfo: 'skip' });

  // Bollinger Band shading
  if (bbU.some(v => v != null) && bbL.some(v => v != null)) {
    data.push({ type: 'scatter', mode: 'lines', x, y: bbL, line: { color: '#cbd5e1', width: 1 }, name: 'BB Lower', xaxis: 'x', yaxis: 'y', hoverinfo: 'skip' });
    data.push({ type: 'scatter', mode: 'lines', x, y: bbU, line: { color: '#cbd5e1', width: 1 }, name: 'BB Upper', xaxis: 'x', yaxis: 'y', hoverinfo: 'skip', fill: 'tonexty', fillcolor: 'rgba(148,163,184,0.25)' });
  }

  // RSI subplot
  if (rsi14.some(v => v != null)) {
    data.push({ type: 'scatter', mode: 'lines', x, y: rsi14, line: { color: '#0ea5e9', width: 1.5 }, name: 'RSI(14)', xaxis: 'x2', yaxis: 'y3', hoverinfo: 'skip' });
    const rsiAbove = rsi14.map(v => (v != null && v > 70 ? v : null));
    const rsiBelow = rsi14.map(v => (v != null && v < 30 ? v : null));
    data.push({ type: 'scatter', mode: 'markers', x, y: rsiAbove, marker: { color: '#dc2626', size: 5 }, name: '>70', showlegend: false, xaxis: 'x2', yaxis: 'y3', hoverinfo: 'skip' });
    data.push({ type: 'scatter', mode: 'markers', x, y: rsiBelow, marker: { color: '#16a34a', size: 5 }, name: '<30', showlegend: false, xaxis: 'x2', yaxis: 'y3', hoverinfo: 'skip' });
  }

  // Layout (preserved) + spikelines
  const layout = {
    dragmode: 'zoom',
    hovermode: 'x',           // good for spikelines without unified tooltip
    showlegend: true,
    legend: { orientation: 'h', y: 1.02, x: 0 },
    paper_bgcolor: 'transparent',
    plot_bgcolor: 'transparent',
    margin: { l: 60, r: 60, t: 20, b: 40 },

    xaxis:  { domain: [0, 1], rangeslider: { visible: false } },
    yaxis:  { domain: [0.35, 1], autorange: true },
    yaxis2: { overlaying: 'y', side: 'right', autorange: true, showgrid: false },
    xaxis2: { domain: [0, 1], matches: 'x' },
    yaxis3: { domain: [0, 0.3], range: [0, 100], title: 'RSI(14)' },

    shapes: [
      { type: 'line', xref: 'paper', x0: 0, x1: 1, yref: 'y3', y0: 70, y1: 70, line: { color: '#dc2626', width: 1, dash: 'dot' } },
      { type: 'line', xref: 'paper', x0: 0, x1: 1, yref: 'y3', y0: 30, y1: 30, line: { color: '#16a34a', width: 1, dash: 'dot' } }
    ]
  };

  // Thin hairlines (spikelines) on all axes; robust with spikedistance
  const spikeProps = {
    showspikes: true,
    spikemode: 'across',
    spikesnap: 'cursor',
    spikecolor: '#64748b',    // slate-500
    spikethickness: 0.7,
    spikedistance: -1         // show spikes even when not near a point
  };
  layout.xaxis  = Object.assign({}, layout.xaxis  || {}, spikeProps);
  layout.yaxis  = Object.assign({}, layout.yaxis  || {}, spikeProps);
  layout.xaxis2 = Object.assign({}, layout.xaxis2 || {}, spikeProps);
  layout.yaxis2 = Object.assign({}, layout.yaxis2 || {}, spikeProps);
  layout.yaxis3 = Object.assign({}, layout.yaxis3 || {}, spikeProps);

  // Render
  Plotly.newPlot('chart', data, layout, { responsive: true, scrollZoom: true, displayModeBar: true });

  // Info strip behavior
  el('title').textContent = ticker;
  el('dateRange').textContent = x.length ? `${x[0]} → ${x[x.length - 1]}` : '';

  const chartDiv = el('chart');
  chartDiv.on('plotly_hover', (event) => {
    if (!event?.points?.length) return;
    const i = event.points[0].pointIndex;
    updateInfoStrip(i, series);
  });

  // Initialize info strip to last candle
  if (x.length) updateInfoStrip(x.length - 1, series);
}

// Start
document.addEventListener('DOMContentLoaded', init);
