/**
 * app.js
 * ──────
 * Portfolio ML Frontend — All interactive logic
 */

/* ── State ────────────────────────────────────────────────────── */
const state = {
  selectedStocks: [],   // [{symbol, name, exchange}]
  weights: {},          // {symbol: 0-100 (percent)}
  charts: {},           // Chart.js instances (keyed by canvas id)
};

/* ── DOM Refs ─────────────────────────────────────────────────── */
const $search        = () => document.getElementById('stockSearch');
const $dropdown      = () => document.getElementById('searchDropdown');
const $selectedArea  = () => document.getElementById('selectedStocks');
const $noStocksHint  = () => document.getElementById('noStocksHint');
const $sliders       = () => document.getElementById('weightSliders');
const $weightTotal   = () => document.getElementById('weightTotal');
const $runBtn        = () => document.getElementById('runBtn');
const $progressWrap  = () => document.getElementById('progressWrap');
const $progressFill  = () => document.getElementById('progressFill');
const $progressLabel = () => document.getElementById('progressLabel');
const $progressPct   = () => document.getElementById('progressPct');
const $errorBox      = () => document.getElementById('errorBox');
const $errorMsg      = () => document.getElementById('errorMsg');
const $results       = () => document.getElementById('results');

/* ── Colour Palette ───────────────────────────────────────────── */
const PALETTE = [
  '#63b3ff','#a78bfa','#4ade80','#f5c842','#f87171',
  '#fb923c','#34d399','#c084fc','#38bdf8','#e879f9',
];

const CHART_DEFAULTS = {
  color: '#64748b',
  font: { family: 'Inter, sans-serif', size: 12 },
};
Chart.defaults.color = CHART_DEFAULTS.color;
Chart.defaults.font  = CHART_DEFAULTS.font;

/* ═══════════════════════════════════════════════════════════════
   STOCK SEARCH
   ═══════════════════════════════════════════════════════════════ */

let _debounceTimer = null;

$search().addEventListener('input', () => {
  clearTimeout(_debounceTimer);
  const q = $search().value.trim();
  if (q.length < 1) { closeDropdown(); return; }
  _debounceTimer = setTimeout(() => fetchSearch(q), 320);
});

$search().addEventListener('keydown', (e) => {
  if (e.key === 'Escape') closeDropdown();
});

document.addEventListener('click', (e) => {
  if (!document.getElementById('stockSearch').contains(e.target) &&
      !document.getElementById('searchDropdown').contains(e.target)) {
    closeDropdown();
  }
});

async function fetchSearch(q) {
  try {
    const res = await fetch(`/api/stocks/search?q=${encodeURIComponent(q)}`);
    const data = await res.json();
    renderDropdown(data);
  } catch (e) {
    console.warn('Search error:', e);
  }
}

function renderDropdown(items) {
  const dd = $dropdown();
  if (!items || items.length === 0) { dd.innerHTML = '<div class="dropdown-item"><span class="ticker-name" style="color:var(--text-muted)">No results found</span></div>'; }
  else {
    dd.innerHTML = items.map(item => `
      <div class="dropdown-item" onclick="selectStock(${JSON.stringify(item).replace(/"/g, '&quot;')})">
        <span class="ticker-symbol">${escHtml(item.symbol)}</span>
        <span class="ticker-name">${escHtml(item.name || item.symbol)}</span>
        <span class="ticker-exchange">${escHtml(item.exchange || item.type || '')}</span>
      </div>
    `).join('');
  }
  dd.classList.add('open');
}

function closeDropdown() {
  $dropdown().classList.remove('open');
  $dropdown().innerHTML = '';
}

function selectStock(item) {
  const sym = item.symbol;
  if (state.selectedStocks.find(s => s.symbol === sym)) {
    closeDropdown(); $search().value = ''; return;
  }
  if (state.selectedStocks.length >= 15) {
    alert('Maximum 15 stocks supported.'); return;
  }
  state.selectedStocks.push(item);
  // Equal weight by default
  const eqW = parseFloat((100 / state.selectedStocks.length).toFixed(2));
  state.selectedStocks.forEach(s => { state.weights[s.symbol] = eqW; });
  closeDropdown();
  $search().value = '';
  renderSelectedTags();
  renderSliders();
}

function removeStock(sym) {
  state.selectedStocks = state.selectedStocks.filter(s => s.symbol !== sym);
  delete state.weights[sym];
  if (state.selectedStocks.length > 0) {
    const eqW = parseFloat((100 / state.selectedStocks.length).toFixed(2));
    state.selectedStocks.forEach(s => { state.weights[s.symbol] = eqW; });
  }
  renderSelectedTags();
  renderSliders();
}

function renderSelectedTags() {
  const area = $selectedArea();
  const hint = $noStocksHint();
  if (state.selectedStocks.length === 0) {
    area.innerHTML = '';
    hint.style.display = 'block';
    return;
  }
  hint.style.display = 'none';
  area.innerHTML = state.selectedStocks.map(stock => `
    <div class="stock-tag">
      <span>${escHtml(stock.symbol)}</span>
      <button class="tag-remove" onclick="removeStock('${escHtml(stock.symbol)}')" title="Remove">✕</button>
    </div>
  `).join('');
}

/* ═══════════════════════════════════════════════════════════════
   WEIGHT SLIDERS
   ═══════════════════════════════════════════════════════════════ */

function renderSliders() {
  const container = $sliders();
  if (state.selectedStocks.length === 0) {
    container.innerHTML = '<div style="color:var(--text-muted);font-size:0.8rem;">Select stocks first to configure weights.</div>';
    updateWeightTotal();
    return;
  }

  container.innerHTML = state.selectedStocks.map((stock, i) => {
    const w = state.weights[stock.symbol] ?? (100 / state.selectedStocks.length);
    const color = PALETTE[i % PALETTE.length];
    return `
      <div class="weight-row">
        <div class="weight-label" style="color:${color}" title="${escHtml(stock.symbol)}">${escHtml(stock.symbol)}</div>
        <input type="range" id="slider_${stock.symbol}" min="0" max="100" step="0.1"
               value="${w.toFixed(1)}"
               oninput="onSliderChange('${stock.symbol}', this.value)"
               style="accent-color: ${color}">
        <div class="weight-value" id="wval_${stock.symbol}">${w.toFixed(1)}%</div>
      </div>
    `;
  }).join('');
  updateWeightTotal();
}

function onSliderChange(sym, val) {
  state.weights[sym] = parseFloat(val);
  document.getElementById(`wval_${sym}`).textContent = parseFloat(val).toFixed(1) + '%';
  updateWeightTotal();
}

function updateWeightTotal() {
  const total = Object.values(state.weights).reduce((a,b) => a+b, 0);
  const el = $weightTotal();
  el.textContent = total.toFixed(1) + '%';
  if (Math.abs(total - 100) < 0.5) { el.className = 'weight-total ok'; }
  else if (Math.abs(total - 100) < 5) { el.className = 'weight-total warn'; }
  else { el.className = 'weight-total error'; }
}

function normalizeWeights() {
  const n = state.selectedStocks.length;
  if (n === 0) return;
  const total = Object.values(state.weights).reduce((a,b) => a+b, 0);
  if (total <= 0) {
    state.selectedStocks.forEach(s => { state.weights[s.symbol] = 100/n; });
  } else {
    state.selectedStocks.forEach(s => { state.weights[s.symbol] = (state.weights[s.symbol] / total) * 100; });
  }
  renderSliders();
}

/* ═══════════════════════════════════════════════════════════════
   RUN ANALYSIS
   ═══════════════════════════════════════════════════════════════ */

async function runAnalysis() {
  if (state.selectedStocks.length < 2) {
    showError('Please select at least 2 stocks.'); return;
  }

  const startDate = document.getElementById('startDate').value;
  const endDate   = document.getElementById('endDate').value;
  if (!startDate || !endDate || startDate >= endDate) {
    showError('Invalid date range. End date must be after start date.'); return;
  }

  // Normalize weights to fractions summing to 1
  normalizeWeights();
  const total = Object.values(state.weights).reduce((a,b)=>a+b,0);
  const weightsFrac = {};
  state.selectedStocks.forEach(s => { weightsFrac[s.symbol] = state.weights[s.symbol] / 100; });

  const body = {
    tickers: state.selectedStocks.map(s => s.symbol),
    start_date: startDate,
    end_date: endDate,
    weights: weightsFrac,
    risk_free_rate: parseFloat(document.getElementById('riskFreeRate').value) / 100,
    n_simulations: parseInt(document.getElementById('nSimulations').value),
    n_synthetic: parseInt(document.getElementById('nSynthetic').value),
  };

  // UI: loading state
  hideError();
  setLoading(true);
  $results().classList.remove('visible');

  try {
    setProgress(5, 'Connecting to Yahoo Finance…');
    await delay(200);
    setProgress(15, 'Fetching historical price data…');

    const res = await fetch('/api/run-analysis', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });

    setProgress(55, 'Running optimisation & ML models…');
    await delay(200);

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.error || `Server error: ${res.status}`);
    }

    const data = await res.json();
    setProgress(85, 'Rendering results…');
    await delay(100);

    renderResults(data);
    setProgress(100, 'Done!');
    await delay(300);

    $results().classList.add('visible');
    $results().scrollIntoView({ behavior: 'smooth', block: 'start' });

  } catch (err) {
    showError(err.message || 'Analysis failed. Check the console for details.');
    console.error(err);
  } finally {
    setLoading(false);
  }
}

/* ═══════════════════════════════════════════════════════════════
   RENDER RESULTS
   ═══════════════════════════════════════════════════════════════ */

function renderResults(d) {
  renderInfoStrip(d);
  renderMetrics(d.current_portfolio);
  renderAssetTable(d.stocks, d.current_portfolio);
  renderOptTable(d.optimization, d.current_portfolio, d.stocks);
  renderMLTable(d.ml_predictions);
  renderEFChart(d.monte_carlo, d.current_portfolio, d.optimization);
  renderPieChart(d.optimization.max_sharpe.weights, d.stocks);
  renderPriceChart(d.price_history, d.stocks);
  renderCorrChart(d.correlation_matrix);
  renderStrategyChart(d.optimization, d.current_portfolio, d.stocks);
}

/* ── Info Strip ─────────────────────────────────────────────── */
function renderInfoStrip(d) {
  const strip = document.getElementById('infoStrip');
  strip.innerHTML = `
    <div class="info-item"><span class="key">Stocks:</span><span class="val">${d.stocks.join(', ')}</span></div>
    <div class="info-item"><span class="key">Period:</span><span class="val">${d.date_range.start} → ${d.date_range.end}</span></div>
    <div class="info-item"><span class="key">Trading Days:</span><span class="val">${d.data_points}</span></div>
    <div class="info-item"><span class="key">MC Simulations:</span><span class="val">${d.monte_carlo.n_simulations.toLocaleString()}</span></div>
  `;
}

/* ── Metric Cards ───────────────────────────────────────────── */
function renderMetrics(cp) {
  const grid = document.getElementById('metricsGrid');
  const cards = [
    { label:'Portfolio Return (Ann.)', value: pct(cp.return), cls:'', sub: 'Annualised expected return' },
    { label:'Portfolio Risk (Std Dev)', value: pct(cp.std),   cls:'', sub: 'Annualised standard deviation' },
    { label:'Portfolio Variance',       value: fmt4(cp.variance), cls:'green', sub: 'σ² = wᵀ Σ w' },
    { label:'Sharpe Ratio',            value: fmt3(cp.sharpe), cls: cp.sharpe > 1 ? 'green' : cp.sharpe > 0.5 ? 'gold' : '', sub: 'Risk-adjusted return' },
  ];
  grid.innerHTML = cards.map(c => `
    <div class="metric-card">
      <div class="metric-label">${c.label}</div>
      <div class="metric-value ${c.cls}">${c.value}</div>
      <div class="metric-sub">${c.sub}</div>
    </div>
  `).join('');
}

/* ── Asset Table ────────────────────────────────────────────── */
function renderAssetTable(stocks, cp) {
  const wrap = document.getElementById('assetTable');
  const rows = stocks.map((s,i) => {
    const w = cp.weights[s] ?? 0;
    const r = cp.asset_returns[s] ?? 0;
    const barW = Math.round(w * 100);
    return `<tr>
      <td><span style="color:${PALETTE[i%PALETTE.length]};font-weight:600;font-family:'JetBrains Mono',monospace">${escHtml(s)}</span></td>
      <td class="mono">${pct(r)}</td>
      <td>
        <div style="display:flex;align-items:center;gap:10px;">
          <div style="flex:1;height:4px;background:var(--bg-3);border-radius:2px;overflow:hidden">
            <div style="width:${barW}%;height:100%;background:${PALETTE[i%PALETTE.length]};border-radius:2px;"></div>
          </div>
          <span class="mono">${pct(w)}</span>
        </div>
      </td>
    </tr>`;
  }).join('');

  wrap.innerHTML = `<table>
    <thead><tr><th>Ticker</th><th>Ann. Return</th><th>Portfolio Weight</th></tr></thead>
    <tbody>${rows}</tbody>
  </table>`;
}

/* ── Optimization Table ────────────────────────────────────── */
function renderOptTable(opt, cp, stocks) {
  const wrap = document.getElementById('optTable');
  const strategies = [
    { key:'current',      label:'Current Portfolio',    badge:'badge-current', data:{return:cp.return,std:cp.std,sharpe:cp.sharpe,weights:cp.weights} },
    { key:'min_variance', label:'Min Variance',          badge:'badge-minvar',  data:opt.min_variance },
    { key:'max_return',   label:'Max Return',            badge:'badge-maxret',  data:opt.max_return },
    { key:'max_sharpe',   label:'Max Sharpe (Tangency)', badge:'badge-maxsh',   data:opt.max_sharpe },
  ];

  const rows = strategies.map(s => {
    const wCells = stocks.map(st => `<td class="mono">${pct(s.data.weights?.[st] ?? 0)}</td>`).join('');
    return `<tr>
      <td><span class="badge-strategy ${s.badge}">${s.label}</span></td>
      <td class="mono">${pct(s.data.return)}</td>
      <td class="mono">${pct(s.data.std)}</td>
      <td class="mono" style="color:var(--gold)">${fmt3(s.data.sharpe)}</td>
      ${wCells}
    </tr>`;
  }).join('');

  const stockHeaders = stocks.map(s => `<th>${escHtml(s)}</th>`).join('');
  wrap.innerHTML = `<table>
    <thead><tr><th>Strategy</th><th>Return</th><th>Risk</th><th>Sharpe</th>${stockHeaders}</tr></thead>
    <tbody>${rows}</tbody>
  </table>`;
}

/* ── ML Predictions Table ──────────────────────────────────── */
function renderMLTable(preds) {
  const wrap = document.getElementById('mlTable');
  if (!preds || preds.length === 0) {
    wrap.innerHTML = '<div style="padding:20px;color:var(--text-muted);font-size:0.85rem;">ML predictions not available (insufficient data).</div>';
    return;
  }
  const rows = preds.map(p => `<tr>
    <td style="font-weight:600;color:var(--purple)">${escHtml(p.model)}</td>
    <td class="mono">${pct(p.return)}</td>
    <td class="mono">${pct(p.std)}</td>
    <td class="mono" style="color:var(--gold)">${fmt3(p.sharpe)}</td>
  </tr>`).join('');
  wrap.innerHTML = `<table>
    <thead><tr><th>Model</th><th>Pred. Return</th><th>Pred. Risk</th><th>Pred. Sharpe</th></tr></thead>
    <tbody>${rows}</tbody>
  </table>`;
}

/* ═══════════════════════════════════════════════════════════════
   CHARTS
   ═══════════════════════════════════════════════════════════════ */

function destroyChart(id) {
  if (state.charts[id]) { state.charts[id].destroy(); delete state.charts[id]; }
}

/* ── Efficient Frontier Scatter ─────────────────────────────── */
function renderEFChart(mc, cp, opt) {
  destroyChart('efChart');
  const ctx = document.getElementById('efChart').getContext('2d');

  // Colour scatter by Sharpe
  const sharpes = mc.scatter.map(p => p.sharpe);
  const minS = Math.min(...sharpes), maxS = Math.max(...sharpes);

  const scatter = {
    label: `MC Portfolios (${mc.n_simulations.toLocaleString()})`,
    data: mc.scatter.map(p => ({ x: p.x, y: p.y, sharpe: p.sharpe })),
    backgroundColor: mc.scatter.map(p => {
      const t = (p.sharpe - minS) / (maxS - minS + 1e-9);
      return `hsla(${200 + t*100}, 80%, 60%, 0.55)`;
    }),
    pointRadius: 2.5,
    pointHoverRadius: 5,
    type: 'scatter',
  };

  const makePoint = (label, portfolio, color, size=10) => ({
    label,
    data: [{ x: portfolio.std, y: portfolio.return }],
    backgroundColor: color,
    pointRadius: size,
    pointHoverRadius: size + 3,
    type: 'scatter',
    borderColor: '#fff',
    borderWidth: 2,
  });

  state.charts['efChart'] = new Chart(ctx, {
    type: 'scatter',
    data: { datasets: [
      scatter,
      makePoint('Current Portfolio',    cp, '#a78bfa', 11),
      makePoint('Min Variance',          mc.min_risk,   '#63b3ff', 11),
      makePoint('Max Sharpe (MC)',       mc.max_sharpe,  '#4ade80', 12),
      makePoint('Max Sharpe (Optimised)', opt.max_sharpe, '#f5c842', 12),
    ]},
    options: {
      responsive: true,
      plugins: {
        legend: { labels: { boxWidth: 12, font: { size: 11 } } },
        tooltip: {
          callbacks: {
            label: (ctx) => {
              const p = ctx.raw;
              const sharpeStr = p.sharpe !== undefined ? `  Sharpe: ${p.sharpe.toFixed(3)}` : '';
              return [`  Risk: ${(p.x*100).toFixed(2)}%`, `  Return: ${(p.y*100).toFixed(2)}%`, sharpeStr].filter(Boolean);
            }
          }
        }
      },
      scales: {
        x: { title: { display: true, text: 'Risk (Std Dev)', color: '#64748b' }, grid: { color: 'rgba(255,255,255,0.04)' } },
        y: { title: { display: true, text: 'Expected Return', color: '#64748b' }, grid: { color: 'rgba(255,255,255,0.04)' } },
      },
    }
  });
}

/* ── Weight Pie ─────────────────────────────────────────────── */
function renderPieChart(weights, stocks) {
  destroyChart('pieChart');
  const ctx = document.getElementById('pieChart').getContext('2d');
  const labels = stocks.filter(s => (weights[s] ?? 0) > 0.001);
  const values = labels.map(s => parseFloat((weights[s] * 100).toFixed(2)));

  state.charts['pieChart'] = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels,
      datasets: [{
        data: values,
        backgroundColor: labels.map((_, i) => PALETTE[i % PALETTE.length] + 'cc'),
        borderColor: labels.map((_, i) => PALETTE[i % PALETTE.length]),
        borderWidth: 2,
        hoverOffset: 8,
      }]
    },
    options: {
      responsive: true,
      plugins: {
        legend: { position: 'right', labels: { boxWidth: 12, font: { size: 11 } } },
        tooltip: {
          callbacks: { label: (ctx) => ` ${ctx.label}: ${ctx.parsed.toFixed(2)}%` }
        }
      },
      cutout: '55%',
    }
  });
}

/* ── Price History Line ─────────────────────────────────────── */
function renderPriceChart(history, stocks) {
  destroyChart('priceChart');
  if (!history || history.length === 0) return;

  const ctx = document.getElementById('priceChart').getContext('2d');
  const labels = history.map(row => row.date || row['Date'] || '');

  const datasets = stocks.map((sym, i) => ({
    label: sym,
    data: history.map(row => {
      const v = row[sym];
      return v !== undefined && v !== null ? parseFloat(v.toFixed(2)) : null;
    }),
    borderColor: PALETTE[i % PALETTE.length],
    backgroundColor: 'transparent',
    borderWidth: 2,
    pointRadius: 0,
    tension: 0.3,
    spanGaps: true,
  }));

  state.charts['priceChart'] = new Chart(ctx, {
    type: 'line',
    data: { labels, datasets },
    options: {
      responsive: true,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { labels: { boxWidth: 12, font: { size: 11 } } },
        tooltip: { callbacks: { label: (c) => ` ${c.dataset.label}: ${c.parsed.y?.toFixed(1)}` } },
      },
      scales: {
        x: {
          ticks: {
            maxTicksLimit: 10,
            callback: (val, idx) => { const d = labels[idx]; return d?.slice(0,7) || ''; },
          },
          grid: { color: 'rgba(255,255,255,0.03)' },
        },
        y: {
          title: { display: true, text: 'Indexed Price (Base=100)', color: '#64748b' },
          grid: { color: 'rgba(255,255,255,0.03)' },
        }
      }
    }
  });
}

/* ── Correlation Heatmap ────────────────────────────────────── */
function renderCorrChart(corrData) {
  destroyChart('corrChart');
  const ctx = document.getElementById('corrChart').getContext('2d');
  const { labels, data } = corrData;
  const n = labels.length;

  // Flatten into scatter-like bubble data
  const chartData = [];
  for (let i = 0; i < n; i++) {
    for (let j = 0; j < n; j++) {
      chartData.push({ x: j, y: i, v: data[i][j] });
    }
  }

  state.charts['corrChart'] = new Chart(ctx, {
    type: 'scatter',
    data: {
      datasets: [{
        data: chartData,
        backgroundColor: chartData.map(p => {
          const v = p.v;
          if (v >= 0) return `rgba(99,179,255,${(v*0.85).toFixed(2)})`;
          return `rgba(248,113,113,${(Math.abs(v)*0.85).toFixed(2)})`;
        }),
        pointRadius: chartData.map(() => {
          const sz = Math.min(24, Math.max(10, 220 / (n+1)));
          return sz;
        }),
        pointStyle: 'rect',
        hoverRadius: 0,
      }]
    },
    options: {
      responsive: true,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (ctx) => {
              const p = ctx.raw;
              return ` ${labels[p.y]} ↔ ${labels[p.x]}: ${p.v.toFixed(3)}`;
            }
          }
        }
      },
      scales: {
        x: {
          min: -0.5, max: n - 0.5,
          ticks: {
            stepSize: 1,
            callback: (val) => labels[val] || '',
            font: { size: 10 },
            maxRotation: 30,
          },
          grid: { display: false },
        },
        y: {
          min: -0.5, max: n - 0.5,
          reverse: true,
          ticks: { stepSize: 1, callback: (val) => labels[val] || '', font: { size: 10 } },
          grid: { display: false },
        }
      }
    }
  });
}

/* ── Strategy Bar Chart ─────────────────────────────────────── */
function renderStrategyChart(opt, cp, stocks) {
  destroyChart('strategyChart');
  const ctx = document.getElementById('strategyChart').getContext('2d');

  const strategies = [
    { label: 'Current',      weights: cp.weights,             color: '#a78bfa' },
    { label: 'Min Variance', weights: opt.min_variance.weights, color: '#63b3ff' },
    { label: 'Max Return',   weights: opt.max_return.weights,   color: '#f5c842' },
    { label: 'Max Sharpe',   weights: opt.max_sharpe.weights,   color: '#4ade80' },
  ];

  const datasets = strategies.map(s => ({
    label: s.label,
    data: stocks.map(stock => parseFloat(((s.weights[stock] ?? 0) * 100).toFixed(2))),
    backgroundColor: s.color + 'bb',
    borderColor: s.color,
    borderWidth: 1.5,
    borderRadius: 4,
  }));

  state.charts['strategyChart'] = new Chart(ctx, {
    type: 'bar',
    data: { labels: stocks, datasets },
    options: {
      responsive: true,
      plugins: {
        legend: { labels: { boxWidth: 12, font: { size: 11 } } },
        tooltip: { callbacks: { label: (c) => ` ${c.dataset.label}: ${c.parsed.y?.toFixed(1)}%` } },
      },
      scales: {
        y: {
          title: { display: true, text: 'Weight (%)', color: '#64748b' },
          grid: { color: 'rgba(255,255,255,0.04)' },
        },
        x: { grid: { display: false } }
      }
    }
  });
}

/* ═══════════════════════════════════════════════════════════════
   UI HELPERS
   ═══════════════════════════════════════════════════════════════ */

function setLoading(on) {
  const btn = $runBtn();
  if (on) {
    btn.disabled = true;
    btn.innerHTML = '<div class="spinner"></div> Analysing…';
    $progressWrap().classList.add('visible');
  } else {
    btn.disabled = false;
    btn.innerHTML = `<svg width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><polygon points="5,3 19,12 5,21"/></svg> Run Portfolio Analysis`;
    setTimeout(() => $progressWrap().classList.remove('visible'), 800);
  }
}

function setProgress(pct, label) {
  $progressFill().style.width = pct + '%';
  $progressPct().textContent = pct + '%';
  $progressLabel().textContent = label;
}

function showError(msg) {
  $errorMsg().textContent = msg;
  $errorBox().classList.add('visible');
}

function hideError() { $errorBox().classList.remove('visible'); }

function delay(ms) { return new Promise(r => setTimeout(r, ms)); }

function escHtml(str) {
  return String(str ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function pct(v) {
  if (v === null || v === undefined || isNaN(v)) return '—';
  return (v * 100).toFixed(2) + '%';
}

function fmt3(v) {
  if (v === null || v === undefined || isNaN(v)) return '—';
  return parseFloat(v).toFixed(3);
}

function fmt4(v) {
  if (v === null || v === undefined || isNaN(v)) return '—';
  return parseFloat(v).toFixed(5);
}

/* ── Set today as maxDate for date pickers ─────────────────── */
(function () {
  const today = new Date().toISOString().slice(0, 10);
  document.getElementById('endDate').max = today;
})();
