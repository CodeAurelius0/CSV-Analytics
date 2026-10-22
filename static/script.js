/**
 * script.js — CSV Analytics Platform (Telemetry UI)
 * Handles: file upload, drag/drop, API calls, chart rendering,
 *          sidebar navigation, dark/light theme, recent runs table,
 *          schema/preview reveal, report downloads.
 */

const app = (() => {
  let _filename     = null;
  let _origName     = '';
  let _uploadData   = null;
  let _analysisData = null;
  let _runs         = [];       // [{name, size, rows, status, time, filename}]

  const PLOTLY_CFG = {
    responsive: true,
    displayModeBar: true,
    modeBarButtonsToRemove: ['lasso2d', 'select2d', 'autoScale2d'],
    displaylogo: false,
    toImageButtonOptions: { format: 'png', scale: 2 },
  };

  // ──────────────────────────────────────────
  //  Theme
  // ──────────────────────────────────────────
  const html     = document.documentElement;
  const themeBtn = document.getElementById('theme-btn');

  function applyTheme(theme) {
    html.setAttribute('data-theme', theme);
    localStorage.setItem('csv-theme', theme);
    const icon = themeBtn.querySelector('i');
    icon.className = theme === 'dark' ? 'bi bi-moon-fill' : 'bi bi-brightness-high-fill';
  }

  applyTheme(localStorage.getItem('csv-theme') || 'dark');

  themeBtn.addEventListener('click', () => {
    applyTheme(html.getAttribute('data-theme') === 'dark' ? 'light' : 'dark');
  });

  // ──────────────────────────────────────────
  //  Sidebar Toggle
  // ──────────────────────────────────────────
  const sidebar        = document.getElementById('sidebar');
  const sidebarToggle  = document.getElementById('sidebar-toggle');

  sidebarToggle.addEventListener('click', () => sidebar.classList.toggle('open'));

  // Close on mobile when clicking outside
  document.addEventListener('click', (e) => {
    if (window.innerWidth <= 900 &&
        sidebar.classList.contains('open') &&
        !sidebar.contains(e.target) &&
        e.target !== sidebarToggle) {
      sidebar.classList.remove('open');
    }
  });

  // ──────────────────────────────────────────
  //  Nav — OVERVIEW page sections
  // ──────────────────────────────────────────
  document.querySelectorAll('.nav-item[data-section]').forEach((link) => {
    link.addEventListener('click', (e) => {
      e.preventDefault();
      const sec = link.dataset.section;

      if (sec === 'overview') {
        // Go back to the overview upload page
        showAppPage('page-overview');
        document.querySelectorAll('.nav-item').forEach(l => l.classList.remove('active'));
        link.classList.add('active');
        document.getElementById('bc-page').textContent = 'overview';
        return;
      }

      // Dashboard section
      showAppPage('page-dashboard');
      activateDashSection('section-' + sec, link);
      document.getElementById('bc-page').textContent = sec;
      if (window.innerWidth <= 900) sidebar.classList.remove('open');
    });
  });

  function activateDashSection(sectionId, clickedLink) {
    document.querySelectorAll('.dash-section').forEach(s => s.classList.remove('active'));
    const target = document.getElementById(sectionId);
    if (target) target.classList.add('active');

    document.querySelectorAll('.nav-item').forEach(l => l.classList.remove('active'));
    if (clickedLink) clickedLink.classList.add('active');

    setTimeout(() => window.dispatchEvent(new Event('resize')), 100);
  }

  function showAppPage(id) {
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    const el = document.getElementById(id);
    if (el) el.classList.add('active');
  }

  // ──────────────────────────────────────────
  //  File Upload — drop zone + file input
  // ──────────────────────────────────────────
  const dropZone   = document.getElementById('drop-zone');
  const fileInput  = document.getElementById('file-input');
  const browseBtn  = document.getElementById('browse-btn');
  const browseBtn2 = document.getElementById('browse-btn-2');
  const importBtn  = document.getElementById('import-csv-btn');
  const errBox     = document.getElementById('upload-error');

  // All "open file picker" triggers
  [browseBtn, browseBtn2, importBtn].forEach(btn => {
    btn?.addEventListener('click', (e) => { e.stopPropagation(); fileInput.click(); });
  });

  fileInput.addEventListener('change', () => {
    if (fileInput.files.length) handleFile(fileInput.files[0]);
  });

  dropZone.addEventListener('click', () => fileInput.click());

  ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(ev =>
    dropZone.addEventListener(ev, (e) => { e.preventDefault(); e.stopPropagation(); })
  );

  window.addEventListener('dragover', e => e.preventDefault());
  window.addEventListener('drop', e => e.preventDefault());

  ['dragenter', 'dragover'].forEach(ev =>
    dropZone.addEventListener(ev, () => dropZone.classList.add('dragover'))
  );
  ['dragleave', 'drop'].forEach(ev =>
    dropZone.addEventListener(ev, () => dropZone.classList.remove('dragover'))
  );

  dropZone.addEventListener('drop', (e) => {
    const files = e.dataTransfer.files;
    if (files.length) handleFile(files[0]);
  });

  dropZone.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.key === ' ') fileInput.click();
  });

  function showError(msg) {
    errBox.textContent = msg;
    errBox.classList.remove('hidden');
    setTimeout(() => errBox.classList.add('hidden'), 7000);
  }

  // ──────────────────────────────────────────
  //  Handle File
  // ──────────────────────────────────────────
  function handleFile(file) {
    const name = file.name.toLowerCase();
    if (!name.endsWith('.csv') && !name.endsWith('.xlsx') && !name.endsWith('.xls')) {
      showError('⚠ Please upload a valid CSV or Excel file (.csv, .xlsx, .xls).');
      return;
    }
    if (file.size > 50 * 1024 * 1024) {
      showError('⚠ File too large. Maximum allowed size is 50 MB.');
      return;
    }
    errBox.classList.add('hidden');
    startUpload(file);
  }

  function advanceStep(stepId) {
    const el = document.getElementById(stepId);
    if (!el) return;
    document.querySelectorAll('.step').forEach(s => {
      if (s.classList.contains('active') && s !== el) s.classList.replace('active', 'done');
    });
    el.classList.add('active');
  }

  // ──────────────────────────────────────────
  //  Upload & Analyze
  // ──────────────────────────────────────────
  async function startUpload(file) {
    // Switch to loading page
    showAppPage('page-loading');
    setStatusBusy(true);
    document.getElementById('loading-heading').textContent = 'Uploading ' + file.name + '…';
    document.getElementById('loading-sub').textContent = 'Sending file to server…';
    advanceStep('step-upload');

    const formData = new FormData();
    formData.append('file', file);

    let uploadData;
    try {
      const res = await fetch('/upload', { method: 'POST', body: formData });
      uploadData = await res.json();
    } catch (err) {
      showAppPage('page-overview');
      setStatusBusy(false);
      showError('Network error during upload: ' + err.message);
      return;
    }

    if (uploadData.error) {
      showAppPage('page-overview');
      setStatusBusy(false);
      showError(uploadData.error);
      return;
    }

    _filename   = uploadData.filename;
    _origName   = uploadData.original_name;
    _uploadData = uploadData;

    // Update topbar dataset pill
    document.getElementById('pill-dataset-val').textContent = _origName;

    advanceStep('step-clean');
    document.getElementById('loading-heading').textContent = 'Analyzing data…';
    document.getElementById('loading-sub').textContent = 'Cleaning and detecting column patterns…';

    setTimeout(() => advanceStep('step-detect'),  600);
    setTimeout(() => advanceStep('step-charts'),  1400);
    setTimeout(() => advanceStep('step-insights'), 2200);

    let analysis;
    try {
      const res = await fetch('/analyze/' + _filename);
      analysis = await res.json();
    } catch (err) {
      showAppPage('page-overview');
      setStatusBusy(false);
      showError('Analysis request failed: ' + err.message);
      return;
    }

    if (analysis.error) {
      showAppPage('page-overview');
      setStatusBusy(false);
      showError('Analysis error: ' + analysis.error);
      return;
    }

    _analysisData = analysis;

    await new Promise(r => setTimeout(r, 400));

    // ── Render the overview page with the new run info ──
    addRunToTable(uploadData);
    renderSchemaBlock(uploadData, analysis);

    // ── Render the full dashboard ──
    renderDashboard(uploadData, analysis);

    setStatusBusy(false);

    // Go back to overview page (which now shows the table + schema)
    showAppPage('page-overview');
  }

  // ──────────────────────────────────────────
  //  Status dot
  // ──────────────────────────────────────────
  function setStatusBusy(busy) {
    const dot = document.getElementById('status-dot');
    if (dot) {
      dot.className = 'status-dot' + (busy ? ' busy' : '');
      dot.title = busy ? 'analyzing…' : 'idle';
    }
  }

  // ──────────────────────────────────────────
  //  Recent Runs Table
  // ──────────────────────────────────────────
  function formatBytes(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  }

  function timeAgo(date) {
    const diff = (Date.now() - date) / 1000;
    if (diff < 60)   return 'just now';
    if (diff < 3600) return Math.floor(diff / 60) + ' min ago';
    if (diff < 86400) return Math.floor(diff / 3600) + ' hrs ago';
    return Math.floor(diff / 86400) + ' days ago';
  }

  function addRunToTable(uploadData) {
    const run = {
      name:     uploadData.original_name,
      size:     uploadData.memory_mb + ' MB',
      rows:     Number(uploadData.rows_estimate).toLocaleString(),
      status:   'ready',
      time:     Date.now(),
      filename: uploadData.filename,
    };
    _runs.unshift(run);
    renderRunsTable();
  }

  function renderRunsTable() {
    const tbody   = document.getElementById('runs-tbody');
    const meta    = document.getElementById('runs-meta');

    meta.textContent = _runs.length + ' run' + (_runs.length !== 1 ? 's' : '') + ' recorded in memory';

    if (_runs.length === 0) {
      tbody.innerHTML = `<tr class="empty-row">
        <td colspan="6">
          <span class="empty-hint"><i class="bi bi-upload"></i> Please Upload CSV File</span>
        </td>
      </tr>`;
      return;
    }

    tbody.innerHTML = _runs.map((run, i) => `
      <tr data-run-index="${i}">
        <td>
          <span class="file-dot ${run.status === 'ready' ? 'ready' : 'error'}"></span>
          <strong style="color:var(--text);font-weight:500;">${escHtml(run.name)}</strong>
        </td>
        <td style="font-family:var(--font-mono)">${escHtml(run.size)}</td>
        <td style="font-family:var(--font-mono)">${run.rows}</td>
        <td>
          <span class="badge-status badge-${run.status === 'ready' ? 'ready' : 'error'}">
            ${run.status === 'ready' ? 'Ready' : 'Error'}
          </span>
        </td>
        <td style="color:var(--text-muted)">${timeAgo(run.time)}</td>
        <td>
          <button class="action-link" onclick="app.loadRun(${i})">Load</button>
          <button class="action-link" onclick="app.inspectRun(${i})">Inspect</button>
        </td>
      </tr>
    `).join('');
  }

  // ──────────────────────────────────────────
  //  Schema & Preview Block (overview page)
  // ──────────────────────────────────────────
  function renderSchemaBlock(uploadData, analysis) {
    const block = document.getElementById('schema-block');
    block.classList.remove('hidden');

    // Meta text
    const meta = document.getElementById('schema-meta-row');
    meta.textContent =
      `Target preview: ${escHtml(uploadData.original_name)}` +
      ` (First 10 of ${Number(uploadData.rows_estimate).toLocaleString()} records)`;

    // Preview table
    renderPreviewTable(
      uploadData.preview,
      uploadData.columns,
      uploadData.dtypes,
      document.getElementById('preview-table-wrap')
    );

    // Schema hint
    document.getElementById('schema-hint').textContent =
      `Displaying sample top rows · ${uploadData.columns.length} columns detected`;
  }

  // ──────────────────────────────────────────
  //  Preview Table (overview schema view)
  // ──────────────────────────────────────────
  function renderPreviewTable(rows, columns, dtypes, container) {
    if (!rows || rows.length === 0 || !container) return;

    const thead = `<thead><tr>
      <th class="row-num">#</th>
      ${columns.map(c => `
        <th>
          <span class="col-name">${escHtml(c)}</span>
          <span class="col-type">${escHtml((dtypes && dtypes[c]) || '')}</span>
        </th>`).join('')}
    </tr></thead>`;

    const tbody = `<tbody>${rows.map((row, idx) => `
      <tr>
        <td class="row-num">${idx + 1}</td>
        ${columns.map(c => `<td title="${escHtml(String(row[c] ?? ''))}">${escHtml(String(row[c] ?? ''))}</td>`).join('')}
      </tr>`).join('')}</tbody>`;

    container.innerHTML = `<table class="data-table">${thead}${tbody}</table>`;
  }

  // ──────────────────────────────────────────
  //  Dashboard Rendering
  // ──────────────────────────────────────────
  function renderDashboard(uploadData, analysis) {
    renderDatasetInfo(uploadData);
    renderKPIs(analysis.kpis);
    renderHealthCard(analysis.clean_report);
    renderDashPreviewTable(uploadData.preview, uploadData.columns, uploadData.dtypes);
    renderCharts(analysis.charts, analysis.mapped_columns);
    renderStatistics(analysis.statistics);
    renderInsights(analysis.insights);
    updateSidebarNav(analysis.mapped_columns);
  }

  // Dataset info chips in dashboard
  function renderDatasetInfo(uploadData) {
    const container = document.getElementById('dataset-info-row');
    const chips = [
      { label: 'File Name',      value: uploadData.original_name },
      { label: 'Est. Rows',      value: Number(uploadData.rows_estimate).toLocaleString() },
      { label: 'Columns',        value: uploadData.columns.length },
      { label: 'File Size',      value: uploadData.memory_mb + ' MB' },
      { label: 'Duplicate Rows', value: uploadData.duplicates },
    ];
    container.innerHTML = chips.map(c => `
      <div class="info-chip">
        <span class="chip-label">${c.label}</span>
        <span class="chip-value">${escHtml(String(c.value))}</span>
      </div>
    `).join('');
  }

  // KPI cards
  function renderKPIs(kpis) {
    const grid = document.getElementById('kpi-grid');
    grid.innerHTML = kpis.map(kpi => `
      <div class="kpi-card" style="--kpi-color:${kpi.color}">
        <div class="kpi-icon"><i class="bi ${kpi.icon}"></i></div>
        <div class="kpi-label">${escHtml(kpi.label)}</div>
        <div class="kpi-value">${escHtml(kpi.value)}</div>
      </div>
    `).join('');
  }

  // Health card
  function renderHealthCard(report) {
    const score = report.health_score;
    const color = score >= 85 ? 'var(--green)' : score >= 65 ? 'var(--amber)' : 'var(--red)';

    const rows = [
      ['Original Rows',          report.original_rows.toLocaleString()],
      ['Duplicate Rows Removed', report.duplicate_rows.toLocaleString()],
      ['Missing Values Before',  report.missing_before.toLocaleString()],
      ['Missing Values After',   report.missing_after.toLocaleString()],
      ['Columns Removed',        report.cols_removed],
      ['Final Rows',             report.final_rows.toLocaleString()],
    ];

    const suggestions = report.actions_taken.length
      ? report.actions_taken
      : ['Dataset looks clean — no major issues detected!'];

    document.getElementById('health-card').innerHTML = `
      <div class="health-score-wrap">
        <div class="health-score-number" style="color:${color}">${score}</div>
        <div class="health-score-label">/ 100 Health</div>
      </div>
      <div class="health-details">
        ${rows.map(([label, val]) => `
          <div class="health-row">
            <span>${escHtml(label)}</span>
            <span class="badge-val">${escHtml(String(val))}</span>
          </div>
        `).join('')}
      </div>
      <div class="health-actions">
        <p style="font-size:0.65rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.6px;margin-bottom:0.3rem;font-weight:700;">
          Cleaning Actions Taken
        </p>
        ${suggestions.map(s => `
          <div class="suggestion-item">
            <i class="bi bi-check-circle-fill"></i>
            <span>${escHtml(s)}</span>
          </div>
        `).join('')}
      </div>
    `;
  }

  // Dashboard preview table (different container from schema)
  function renderDashPreviewTable(rows, columns, dtypes) {
    const container = document.getElementById('dash-preview-table-wrap');
    if (!rows || rows.length === 0 || !container) return;

    const thead = `<thead><tr>
      ${columns.map(c => `<th>${escHtml(c)}</th>`).join('')}
    </tr></thead>`;

    const tbody = `<tbody>${rows.map(row => `
      <tr>
        ${columns.map(c => `<td title="${escHtml(String(row[c] ?? ''))}">${escHtml(String(row[c] ?? ''))}</td>`).join('')}
      </tr>`).join('')}</tbody>`;

    container.innerHTML = `<table class="data-table">${thead}${tbody}</table>`;
  }

  // ── Charts ──
  const CHART_MAP = [
    { key: 'sales_by_category',    section: 'sales',      label: 'Sales by Category' },
    { key: 'sales_donut',          section: 'sales',      label: 'Sales Distribution' },
    { key: 'sales_box',            section: 'sales',      label: 'Sales Box Plot' },
    { key: 'sales_histogram',      section: 'sales',      label: 'Sales Histogram' },
    { key: 'monthly_trend',        section: 'timeseries', label: 'Monthly Trend' },
    { key: 'quarterly_sales',      section: 'timeseries', label: 'Quarterly Sales' },
    { key: 'yearly_trend',         section: 'timeseries', label: 'Yearly Trend' },
    { key: 'rolling_average',      section: 'timeseries', label: 'Rolling Average' },
    { key: 'profit_by_category',   section: 'profit',     label: 'Profit by Category' },
    { key: 'profit_trend',         section: 'profit',     label: 'Monthly Profit Trend' },
    { key: 'discount_vs_profit',   section: 'profit',     label: 'Discount vs Profit' },
    { key: 'top_customers',        section: 'customers',  label: 'Top Customers' },
    { key: 'customer_frequency',   section: 'customers',  label: 'Order Frequency' },
    { key: 'top_products',         section: 'products',   label: 'Top Products',        full: true },
    { key: 'worst_products',       section: 'products',   label: 'Bottom Products',     full: true },
    { key: 'abc_analysis',         section: 'products',   label: 'ABC Segmentation' },
    { key: 'sales_by_region',      section: 'regional',   label: 'Sales by Region' },
    { key: 'region_treemap',       section: 'regional',   label: 'Region Treemap' },
    { key: 'correlation_matrix',   section: 'statistics', label: 'Correlation Matrix',  full: true },
    { key: 'scatter_matrix',       section: 'statistics', label: 'Scatter Matrix',      full: true },
    { key: 'distributions',        section: 'statistics', label: 'Distributions',       full: true },
    { key: 'box_plots',            section: 'statistics', label: 'Box Plots (Outlier Detection)', full: true },
    { key: 'missing_values',       section: 'statistics', label: 'Missing Values' },
    { key: 'categorical_frequency',section: 'statistics', label: 'Category Frequency' },
  ];

  function renderCharts(charts, mappedCols) {
    ['sales','timeseries','profit','customers','products','regional','statistics'].forEach(s => {
      const el = document.getElementById('charts-' + s);
      if (el) el.innerHTML = '';
    });

    const sectionsWithCharts = new Set();

    CHART_MAP.forEach(({ key, section, label, full }) => {
      const chartJson = charts[key];
      if (!chartJson) return;

      const containerId = `chart-${key}`;
      const gridId      = `charts-${section}`;
      const grid        = document.getElementById(gridId);
      if (!grid) return;

      const card = document.createElement('div');
      card.className = `chart-card${full ? ' full-width' : ''}`;
      card.id = containerId;
      grid.appendChild(card);
      sectionsWithCharts.add(section);

      try {
        const figure = JSON.parse(chartJson);

        // Override layout for dark/light theming
        figure.layout = figure.layout || {};
        figure.layout.paper_bgcolor = 'rgba(0,0,0,0)';
        figure.layout.plot_bgcolor  = 'rgba(0,0,0,0)';
        figure.layout.font = { family: 'Inter, system-ui, sans-serif', size: 11, color: '#9999a8' };
        figure.layout.margin = figure.layout.margin || { t: 40, r: 20, b: 40, l: 50 };

        Plotly.newPlot(containerId, figure.data, figure.layout, PLOTLY_CFG);
      } catch (err) {
        card.innerHTML = `<p style="color:var(--text-muted);padding:1rem;font-size:0.78rem;">Chart render failed: ${escHtml(err.message)}</p>`;
      }
    });

    const alwaysVisible = ['overview', 'statistics', 'insights'];
    document.querySelectorAll('.nav-item[data-section]').forEach(link => {
      const sec = link.dataset.section;
      if (alwaysVisible.includes(sec)) {
        link.classList.remove('disabled');
      } else {
        link.classList.toggle('disabled', !sectionsWithCharts.has(sec));
      }
    });

    setTimeout(() => window.dispatchEvent(new Event('resize')), 600);
  }

  // Statistics table
  function renderStatistics(stats) {
    const container = document.getElementById('stats-content');
    if (!stats || Object.keys(stats).length === 0) {
      container.innerHTML = `<p style="color:var(--text-muted);font-size:0.78rem;">No numeric columns found.</p>`;
      return;
    }

    const statKeys = [
      ['count','Count'], ['mean','Mean'], ['median','Median'], ['std','Std Dev'],
      ['variance','Variance'], ['min','Min'], ['max','Max'],
      ['q1','Q1 (25%)'], ['q3','Q3 (75%)'], ['iqr','IQR'],
      ['p5','P5'], ['p95','P95'], ['skewness','Skewness'], ['kurtosis','Kurtosis'],
    ];

    const columns = Object.keys(stats);

    const headerRow = `<tr>
      <th>Statistic</th>
      ${columns.map(c => `<th>${escHtml(c)}</th>`).join('')}
    </tr>`;

    const rows = statKeys.map(([key, label]) => `
      <tr>
        <td>${label}</td>
        ${columns.map(c => `<td>${stats[c][key] !== undefined ? stats[c][key] : '—'}</td>`).join('')}
      </tr>
    `).join('');

    container.innerHTML = `
      <div class="glass-card mb-3">
        <h3 class="card-title"><i class="bi bi-table"></i> Descriptive Statistics</h3>
        <div class="table-wrap">
          <table class="stats-table">
            <thead>${headerRow}</thead>
            <tbody>${rows}</tbody>
          </table>
        </div>
      </div>
    `;
  }

  // Insights
  function renderInsights(insights) {
    const grid = document.getElementById('insights-grid');
    if (!insights || insights.length === 0) {
      grid.innerHTML = `<p style="color:var(--text-muted);font-size:0.78rem;">No insights generated.</p>`;
      return;
    }

    grid.innerHTML = insights.map(ins => `
      <div class="insight-card">
        <div class="insight-section-label">
          <i class="bi ${ins.icon || 'bi-lightbulb-fill'}"></i>
          ${escHtml(ins.section)}
        </div>
        <div class="insight-row">
          <div class="insight-row-label">📊 Observation</div>
          <div class="insight-row-text">${escHtml(ins.observation)}</div>
        </div>
        <div class="insight-row">
          <div class="insight-row-label">💡 Insight</div>
          <div class="insight-row-text">${escHtml(ins.insight)}</div>
        </div>
        <div class="insight-row">
          <div class="insight-row-label">✅ Recommendation</div>
          <div class="insight-row-text">${escHtml(ins.recommendation)}</div>
        </div>
        ${ins.risk ? `
        <div class="insight-row insight-risk">
          <div class="insight-row-label">⚠ Potential Risk</div>
          <div class="insight-row-text">${escHtml(ins.risk)}</div>
        </div>` : ''}
      </div>
    `).join('');
  }

  // Sidebar nav visibility
  function updateSidebarNav(mappedCols) {
    ['nav-overview', 'nav-statistics', 'nav-insights'].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.classList.remove('disabled');
    });
  }

  // ──────────────────────────────────────────
  //  Go to Dashboard from schema footer
  // ──────────────────────────────────────────
  function goToDashboard() {
    if (!_analysisData) return;
    showAppPage('page-dashboard');
    activateDashSection('section-overview', document.getElementById('nav-overview'));
    document.getElementById('bc-page').textContent = 'overview';
  }

  // ──────────────────────────────────────────
  //  Load / Inspect run from table
  // ──────────────────────────────────────────
  function loadRun(index) {
    const run = _runs[index];
    if (!run) return;
    // Just go to dashboard — data is already rendered
    goToDashboard();
  }

  function inspectRun(index) {
    const run = _runs[index];
    if (!run) return;
    // Go to statistics section
    showAppPage('page-dashboard');
    activateDashSection('section-statistics', document.getElementById('nav-statistics'));
    document.getElementById('bc-page').textContent = 'statistics';
  }

  // ──────────────────────────────────────────
  //  Report Download
  // ──────────────────────────────────────────
  function downloadReport(format) {
    if (!_filename) {
      alert('Please upload a dataset first.');
      return;
    }
    window.location.href = `/download/${format}/${_filename}`;
  }

  // ──────────────────────────────────────────
  //  Reset
  // ──────────────────────────────────────────
  function reset() {
    _filename     = null;
    _origName     = '';
    _uploadData   = null;
    _analysisData = null;
    _runs         = [];

    fileInput.value = '';
    document.getElementById('pill-dataset-val').textContent = 'none active';
    document.getElementById('bc-page').textContent = 'overview';

    // Hide schema block, reset runs table
    document.getElementById('schema-block').classList.add('hidden');
    renderRunsTable();

    // Reset nav
    document.querySelectorAll('.nav-item').forEach(l => l.classList.add('disabled'));
    const ov = document.getElementById('nav-overview');
    if (ov) { ov.classList.remove('disabled'); ov.classList.add('active'); }

    setStatusBusy(false);
    showAppPage('page-overview');
  }

  // ──────────────────────────────────────────
  //  Utility
  // ──────────────────────────────────────────
  function escHtml(str) {
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  // Public API
  return { downloadReport, reset, goToDashboard, loadRun, inspectRun };
})();
