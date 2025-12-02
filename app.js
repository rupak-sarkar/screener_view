
// ===== Helpers =====
function el(id) { return document.getElementById(id); }

// ===== Global state =====
const state = {
  rows: [],
  tickers: [],
  selectedTicker: null,
  showVolume: true,
  selectedFlag: 'ALL', // 'ALL' | 'ANY' | specific string
  up20Filter: 'ALL',   // NEW: 'ALL' | 'TRUE' | 'FALSE'
  upTrueFilter: 'ALL', // NEW: 'ALL' | 'TRUE' | 'FALSE'
  flags: []
};

// ===== CSV source =====
const CSV_URL = "stock_data_with_indicators.csv";

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
    computeTickers();
    setupSearchDropdown(true);
    el('status').textContent = `Filter: ${state.selectedFlag} — ${state.tickers.length} tickers`;
  });

  // NEW: Up_20 filter dropdown
  const up20Sel = el('up20Select');
  up20Sel.addEventListener('change', (e) => {
    state.up20Filter = e.target.value;
    computeTickers();
    setupSearchDropdown(true);
  });

  // NEW: Up_True filter dropdown
  const upTrueSel = el('upTrueSelect');
  upTrueSel.addEventListener('change', (e) => {
    state.upTrueFilter = e.target.value;
    computeTickers();
    setupSearchDropdown(true);
  });
}

// ===== BB_Flag helpers =====
function getBBFlag(row) {
  return row['BB_Flag'] ?? row['BB\\_Flag'] ?? row['BB Flag'] ?? null;
}

// ===== Date parsing helper =====
function parseDate(d) {
  if (!d) return null;
  if (d instanceof Date && !isNaN(d)) return d;
  const s = String(d).trim();
  const norm = s.replace(/\//g, '-');
  const isoMatch = norm.match(/^(\d{4})-(\d{1,2})-(\d{1,2})$/);
  if (isoMatch) {
    const y = +isoMatch[1], m = +isoMatch[2], dd = +isoMatch[3];
    return new Date(y, m - 1, dd);
  }
  return new Date(s);
}

// ===== Populate BB_Flag dropdown =====
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

// ===== Compute tickers: last 7 calendar days from today =====
function computeTickers() {
  const allTickers = [...new Set(state.rows.map(r => r.Ticker))].filter(Boolean);
  const out = [];

  const now = new Date();
  const cutoff = new Date(now);
  cutoff.setDate(cutoff.getDate() - 7);

  const inLast7Days = (row) => {
    const dt = parseDate(row.Date);
    return dt && dt >= cutoff && dt <= now;
  };

  for (const tk of allTickers) {
    const recentRows = state.rows.filter(r => r.Ticker === tk && inLast7Days(r));

    // NEW: Apply up_20 filter
    if (state.up20Filter !== 'ALL') {
      const hasUp20 = recentRows.some(r => String(r.up_20).toLowerCase() === 'true');
      if (state.up20Filter === 'TRUE' && !hasUp20) continue;
      if (state.up20Filter === 'FALSE' && hasUp20) continue;
    }

    // NEW: Apply up_true filter
    if (state.upTrueFilter !== 'ALL') {
      const hasUpTrue = recentRows.some(r => String(r.up_true).toLowerCase() === 'true');
      if (state.upTrueFilter === 'TRUE' && !hasUpTrue) continue;
      if (state.upTrueFilter === 'FALSE' && hasUpTrue) continue;
    }

    // Existing BB_Flag logic
    if (state.selectedFlag === 'ALL') {
      out.push(tk);
      continue;
    }

    if (state.selectedFlag === 'ANY') {
      const hasNonBlank = recentRows.some(r => {
        const v = getBBFlag(r);
        return v && String(v).trim() !== '';
      });
      if (hasNonBlank) out.push(tk);
      continue;
    }

    const matchFlag = recentRows.some(r => {
      const v = getBBFlag(r);
      return v && String(v).trim() === state.selectedFlag;
    });
    if (matchFlag) out.push(tk);
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

document.addEventListener('DOMContentLoaded', init);
