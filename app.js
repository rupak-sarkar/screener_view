/*  Ticker Candles - GitHub Pages

    - Streams ./stock_data_with_indicators.csv

    - Groups by Ticker

    - Interactive slicer + Plotly candlestick + optional volume

*/
const CSV_URL = "./stock_data_with_indicators.csv"; // This is correct

const el = (id) => document.getElementById(id);

const state = {
  tickers: [], // unique tickers
  byTicker: new Map(), // ticker -> [{Date,Open,High,Low,Close,Volume}, ...sorted]
  selected: null,
  showVolume: true,
};

// ---- Parse CSV (streaming) --------------------------------------------------
function loadCSV() {
  return new Promise((resolve, reject) => {
    Papa.parse(CSV_URL, {
      download: true,
      header: true,
      dynamicTyping: true, // numbers become Number
      skipEmptyLines: true,
      worker: false,
      chunk: (chunk) => {
        const rows = chunk.data;
        for (const r of rows) {
          const tkr = (r.Ticker || "").trim();

          // Filter out rows missing core OHLC or Date
          const hasOHLC =
            isFinite(r.Open) &&
            isFinite(r.High) &&
            isFinite(r.Low) &&
            isFinite(r.Close);

          if (!tkr || !r.Date || !hasOHLC) continue;

          const rec = {
            Date: new Date(r.Date), // expects YYYY-MM-DD
            Open: +r.Open,
            High: +r.High,
            Low: +r.Low,
            Close: +r.Close,
            Volume: isFinite(r.Volume) ? +r.Volume : null,
          };

          if (!state.byTicker.has(tkr)) state.byTicker.set(tkr, []);
          state.byTicker.get(tkr).push(rec);
        }
      },
      complete: () => {
        // sort each ticker by date ascending and collect list
        for (const [tkr, arr] of state.byTicker.entries()) {
          arr.sort((a, b) => a.Date - b.Date);
        }
        state.tickers = [...state.byTicker.keys()].sort();
        resolve();
      },
      error: (err) => reject(err),
    });
  });
}

// ---- UI: build slicer & search ---------------------------------------------
function buildSlicer() {
  const wrap = el("tickers");
  wrap.innerHTML = "";
  for (const t of state.tickers) {
    const div = document.createElement("div");
    div.className = "ticker";
    div.textContent = t;
    div.dataset.ticker = t;
    div.addEventListener("click", () => selectTicker(t));
    wrap.appendChild(div);
  }

  // live filter
  el("search").addEventListener("input", (e) => {
    const q = e.target.value.trim().toLowerCase();
    for (const child of wrap.children) {
      child.style.display = child.textContent.toLowerCase().includes(q)
        ? ""
        : "none";
    }
  });

  // show/hide volume
  const chk = el("showVolume");
  chk.addEventListener("change", () => {
    state.showVolume = chk.checked;
    plotSelected();
  });
}

// ---- Select ticker + plot ---------------------------------------------------
function selectTicker(ticker) {
  state.selected = ticker;

  // update active style
  for (const child of el("tickers").children) {
    child.classList.toggle("active", child.dataset.ticker === ticker);
  }

  plotSelected();
}

function plotSelected() {
  const t = state.selected;
  if (!t) return;

  const rows = state.byTicker.get(t) || [];
  const x = rows.map((r) => r.Date);
  const open = rows.map((r) => r.Open);
  const high = rows.map((r) => r.High);
  const low = rows.map((r) => r.Low);
  const close = rows.map((r) => r.Close);
  const vol = rows.map((r) => r.Volume ?? null);

  // compute range text
  const first = rows[0]?.Date;
  const last = rows[rows.length - 1]?.Date;

  el("title").textContent = `${t} — Candlestick`;
  el("dateRange").textContent =
    first && last
      ? `${fmtDate(first)} → ${fmtDate(last)} (${rows.length} bars)`
      : "";

  const candleTrace = {
    type: "candlestick",
    x,
    open,
    high,
    low,
    close,
    increasing: { line: { color: "#22d3ee" } },
    decreasing: { line: { color: "#ef4444" } },
    name: "Price",
  };

  const data = [candleTrace];
  let layout = {};

  if (state.showVolume) {
    data.push({
      type: "bar",
      x,
      y: vol,
      marker: { color: "#334155" },
      name: "Volume",
      yaxis: "y2",
      opacity: 0.6,
    });

    // safe volume axis range
    const volVals = vol.filter((v) => v != null);
    const maxVol = volVals.length ? Math.max(...volVals) : 1;

    layout = {
      dragmode: "pan",
      showlegend: false,
      paper_bgcolor: "transparent",
      plot_bgcolor: "transparent",
      margin: { l: 60, r: 60, t: 20, b: 40 },
      xaxis: { rangeslider: { visible: false }, gridcolor: "#1f2937" },
      yaxis: { gridcolor: "#1f2937" },
      yaxis2: {
        overlaying: "y",
        side: "right",
        range: [0, maxVol * 4],
        showgrid: false,
      },
    };
  } else {
    layout = {
      dragmode: "pan",
      showlegend: false,
      paper_bgcolor: "transparent",
      plot_bgcolor: "transparent",
      margin: { l: 60, r: 60, t: 20, b: 40 },
      xaxis: { rangeslider: { visible: false }, gridcolor: "#1f2937" },
      yaxis: { gridcolor: "#1f2937" },
    };
  }

  Plotly.newPlot("chart", data, layout, { responsive: true });
}

const fmtDate = (d) => d.toISOString().slice(0, 10);

// ---- Boot -------------------------------------------------------------------
async function init() {
  try {
    el("status").textContent = "Loading CSV…";
    await loadCSV();
    buildSlicer();
    el("status").textContent = `Loaded ${state.tickers.length} tickers`;

    // Auto-select first ticker
    if (state.tickers.length) {
      selectTicker(state.tickers[0]);
    }
  } catch (err) {
    console.error(err);
    el("status").textContent = `Failed to load CSV: ${err?.message || err}`;
  }
}

init();
 
