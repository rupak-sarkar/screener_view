// Utility to get element by id
function el(id) {
  return document.getElementById(id);
}

// Global state
const state = {
  rows: [],
  tickers: [],
  selectedTicker: null,
  showVolume: true
};

// CSV URL
const CSV_URL = "https://raw.githubusercontent.com/rupak-sarkar/screener_view/main/stock_data_with_indicators.csv";

// Initialize
function init() {
  Papa.parse(CSV_URL, {
    download: true,
    header: true,
    dynamicTyping: true,
    skipEmptyLines: true,
    complete: (results) => {
      state.rows = results.data;
      state.tickers = [...new Set(state.rows.map(r => r.Ticker))].sort();
      buildTickerSelector();
      if (state.tickers.length) {
        plotSelected(state.tickers[0]); // default first ticker
      }
      el("status").textContent = "Loaded " + state.tickers.length + " tickers";
    },
    error: (err) => {
      console.error("CSV load error:", err);
      el("status").textContent = "Failed to load CSV.";
    }
  });

  // Reset Scale button
  const resetBtn = el("resetScale");
  if (resetBtn) {
    resetBtn.addEventListener("click", () => {
      Plotly.relayout("chart", {
        "yaxis.autorange": true,
        "yaxis2.autorange": true
      });
    });
  }

  // Keyboard shortcut (R)
  document.addEventListener("keydown", (e) => {
    if (e.key.toLowerCase() === "r") {
      Plotly.relayout("chart", {
        "yaxis.autorange": true,
        "yaxis2.autorange": true
      });
    }
  });

  // Volume checkbox
  const volChk = el("showVolume");
  if (volChk) {
    state.showVolume = volChk.checked;
    volChk.addEventListener("change", (e) => {
      state.showVolume = e.target.checked;
      if (state.selectedTicker) plotSelected(state.selectedTicker);
    });
  }
}

// Build ticker selector
function buildTickerSelector() {
  const selector = el("tickers");
  if (!selector) {
    console.error("Missing #tickers element in DOM");
    return;
  }
  selector.innerHTML = "";
  state.tickers.forEach(ticker => {
    const btn = document.createElement("button");
    btn.textContent = ticker;
    btn.className = "ticker-btn";
    btn.onclick = () => plotSelected(ticker);
    selector.appendChild(btn);
  });
}

// Plot selected ticker
function plotSelected(ticker) {
  state.selectedTicker = ticker;
  const rows = state.rows.filter(r => r.Ticker === ticker);

  const x = rows.map(r => r.Date);
  const open = rows.map(r => r.Open);
  const high = rows.map(r => r.High);
  const low = rows.map(r => r.Low);
  const close = rows.map(r => r.Close);
  const vol = rows.map(r => r.Volume);

  const data = [];

  // Candlestick trace
  data.push({
    type: "candlestick",
    x,
    open,
    high,
    low,
    close,
    increasing: { line: { color: "#22d3ee" } },
    decreasing: { line: { color: "#ef4444" } },
    name: "Price",
    hovertemplate:
      "<b>Date:</b> %{x|%Y-%m-%d}<br>" +
      "Open: %{open}<br>" +
      "High: %{high}<br>" +
      "Low: %{low}<br>" +
      "Close: %{close}<br>" +
      "Δ%: %{((close-open)/open*100).toFixed(2)}%<extra></extra>"
  });

  // Volume trace
  if (state.showVolume) {
    data.push({
      type: "bar",
      x,
      y: vol,
      marker: { color: "#334155" },
      name: "Volume",
      yaxis: "y2",
      opacity: 0.6,
      hovertemplate: "Volume: %{y:,}<extra></extra>"
    });
  }

  // Layout
  let layout = {
    dragmode: "pan",
    showlegend: false,
    paper_bgcolor: "transparent",
    plot_bgcolor: "transparent",
    margin: { l: 60, r: 60, t: 20, b: 40 },
    xaxis: {
      rangeslider: { visible: false },
      gridcolor: "#1f2937",
      rangeselector: {
        buttons: [
          { count: 1, label: "1M", step: "month", stepmode: "backward" },
          { count: 3, label: "3M", step: "month", stepmode: "backward" },
          { count: 6, label: "6M", step: "month", stepmode: "backward" },
          { count: 1, label: "YTD", step: "year", stepmode: "todate" },
          { count: 1, label: "1Y", step: "year", stepmode: "backward" },
          { step: "all", label: "All" }
        ]
      }
    },
    yaxis: { gridcolor: "#1f2937", autorange: true },
    hovermode: "x unified"
  };

  if (state.showVolume) {
    layout.yaxis2 = {
      overlaying: "y",
      side: "right",
      autorange: true,
      showgrid: false
    };
  }

  Plotly.newPlot("chart", data, layout, { responsive: true });

  // Update header
  el("title").textContent = ticker;
  el("dateRange").textContent = x.length ? `${x[0]} → ${x[x.length - 1]}` : "";
}

// ✅ Run init only after DOM is ready
document.addEventListener("DOMContentLoaded", init);
