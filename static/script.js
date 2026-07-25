/**
 * script.js — Universal CSV Analytics Platform
 * Handles: file upload, drag/drop, API calls, chart rendering,
 *          sidebar navigation, dark/light theme, report downloads.
 */

// ─────────────────────────────────────────────
//  Global App State
// ─────────────────────────────────────────────
const app = (() => {
  let _filename   = null;   // server-side file ID
  let _origName   = "";     // user-facing original filename
  let _analysisData = null; // last analysis response
  const PLOTLY_CFG = {
    responsive: true,
    displayModeBar: true,
    modeBarButtonsToRemove: ["lasso2d", "select2d", "autoScale2d"],
    displaylogo: false,
    toImageButtonOptions: { format: "png", scale: 2 },
  };

  // ──────────────────────────────────────────
  //  Theme
  // ──────────────────────────────────────────
  const html = document.documentElement;
  const themeBtn = document.getElementById("theme-btn");

  function applyTheme(theme) {
    html.setAttribute("data-theme", theme);
    localStorage.setItem("uca-theme", theme);
    const icon = themeBtn.querySelector("i");
    icon.className = theme === "dark" ? "bi bi-brightness-high-fill" : "bi bi-moon-fill";
  }

  applyTheme(localStorage.getItem("uca-theme") || "dark");

  themeBtn.addEventListener("click", () => {
    applyTheme(html.getAttribute("data-theme") === "dark" ? "light" : "dark");
    // Plotly charts handle transparent backgrounds — no forced redraw needed.
  });

  // ──────────────────────────────────────────
  //  Sidebar Navigation
  // ──────────────────────────────────────────
  const sidebar     = document.getElementById("sidebar");
  const sidebarToggle = document.getElementById("sidebar-toggle");

  sidebarToggle.addEventListener("click", () => {
    sidebar.classList.toggle("open");
  });

  document.querySelectorAll(".nav-item[data-section]").forEach((link) => {
    link.addEventListener("click", (e) => {
      e.preventDefault();
      const targetId = "section-" + link.dataset.section;
      activateSection(targetId, link);
      if (window.innerWidth <= 900) sidebar.classList.remove("open");
    });
  });

  function activateSection(sectionId, clickedLink) {
    // Hide all sections
    document.querySelectorAll(".dash-section").forEach((s) => s.classList.remove("active"));
    // Show target
    const target = document.getElementById(sectionId);
    if (target) target.classList.add("active");

    // Update nav active state
    document.querySelectorAll(".nav-item").forEach((l) => l.classList.remove("active"));
    if (clickedLink) clickedLink.classList.add("active");

    // Force Plotly to calculate correct widths for the newly visible charts
    setTimeout(() => window.dispatchEvent(new Event("resize")), 100);
  }

  // ──────────────────────────────────────────
  //  Page Management
  // ──────────────────────────────────────────
  function showPage(id) {
    document.querySelectorAll(".page").forEach((p) => p.classList.remove("active"));
    document.getElementById(id).classList.add("active");
  }

  // ──────────────────────────────────────────
  //  Drag & Drop Upload
  // ──────────────────────────────────────────
  const dropZone  = document.getElementById("drop-zone");
  const fileInput = document.getElementById("file-input");
  const browseBtn = document.getElementById("browse-btn");
  const errBox    = document.getElementById("upload-error");

  browseBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    fileInput.click();
  });

  fileInput.addEventListener("change", () => {
    if (fileInput.files.length) handleFile(fileInput.files[0]);
  });

  dropZone.addEventListener("click", () => fileInput.click());

  ["dragenter", "dragover", "dragleave", "drop"].forEach((ev) =>
    dropZone.addEventListener(ev, (e) => { e.preventDefault(); e.stopPropagation(); })
  );

  // Prevent default behavior globally so missing the dropzone doesn't download the file
  window.addEventListener("dragover", (e) => e.preventDefault());
  window.addEventListener("drop", (e) => e.preventDefault());

  ["dragenter", "dragover"].forEach((ev) =>
    dropZone.addEventListener(ev, () => dropZone.classList.add("dragover"))
  );
  ["dragleave", "drop"].forEach((ev) =>
    dropZone.addEventListener(ev, () => dropZone.classList.remove("dragover"))
  );

  dropZone.addEventListener("drop", (e) => {
    const files = e.dataTransfer.files;
    if (files.length) handleFile(files[0]);
  });

  // Keyboard accessibility for drop zone
  dropZone.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") fileInput.click();
  });

  function showError(msg) {
    errBox.textContent = msg;
    errBox.classList.remove("hidden");
    setTimeout(() => errBox.classList.add("hidden"), 6000);
  }

  // ──────────────────────────────────────────
  //  Upload & Analyze Flow
  // ──────────────────────────────────────────
  function handleFile(file) {
    const name = file.name.toLowerCase();
    if (!name.endsWith(".csv") && !name.endsWith(".xlsx") && !name.endsWith(".xls")) {
      showError("⚠ Please upload a valid CSV or Excel file (.csv, .xlsx, .xls).");
      return;
    }
    if (file.size > 50 * 1024 * 1024) {
      showError("⚠ File too large. Maximum allowed size is 50 MB.");
      return;
    }
    errBox.classList.add("hidden");
    startUpload(file);
  }

  function advanceStep(stepId) {
    const el = document.getElementById(stepId);
    if (el) {
      document.querySelectorAll(".step").forEach((s) => {
        if (s.classList.contains("active") && s !== el) s.classList.replace("active", "done");
      });
      el.classList.add("active");
    }
  }

  async function startUpload(file) {
    showPage("page-loading");
    advanceStep("step-upload");
    document.getElementById("loading-heading").textContent = "Uploading " + file.name + "…";

    const formData = new FormData();
    formData.append("file", file);

    let uploadData;
    try {
      const res = await fetch("/upload", { method: "POST", body: formData });
      uploadData = await res.json();
    } catch (err) {
      showPage("page-upload");
      showError("Network error during upload: " + err.message);
      return;
    }

    if (uploadData.error) {
      showPage("page-upload");
      showError(uploadData.error);
      return;
    }

    _filename = uploadData.filename;
    _origName = uploadData.original_name;

    // Render preview immediately (from upload response)
    renderDatasetInfo(uploadData);
    renderPreviewTable(uploadData.preview, uploadData.columns);

    advanceStep("step-clean");
    document.getElementById("loading-heading").textContent = "Analyzing data…";
    document.getElementById("loading-sub").textContent =
      "Cleaning data and detecting column patterns…";

    // Staggered step UI for UX feel
    setTimeout(() => advanceStep("step-detect"), 600);
    setTimeout(() => advanceStep("step-charts"), 1400);
    setTimeout(() => advanceStep("step-insights"), 2400);

    let analysis;
    try {
      const res = await fetch("/analyze/" + _filename);
      analysis = await res.json();
    } catch (err) {
      showPage("page-upload");
      showError("Analysis request failed: " + err.message);
      return;
    }

    if (analysis.error) {
      showPage("page-upload");
      showError("Analysis error: " + analysis.error);
      return;
    }

    _analysisData = analysis;

    // Small delay so loading steps animate visibly
    await new Promise((r) => setTimeout(r, 500));

    renderDashboard(uploadData, analysis);
    showPage("page-dashboard");

    // Update topbar
    document.getElementById("topbar-title").innerHTML =
      `<i class="bi bi-check-circle-fill" style="color:var(--green)"></i>&nbsp; ${_origName}`;
  }

  // ──────────────────────────────────────────
  //  Dashboard Rendering
  // ──────────────────────────────────────────
  function renderDatasetInfo(uploadData) {
    const container = document.getElementById("dataset-info-row");
    const chips = [
      { label: "File Name",      value: uploadData.original_name },
      { label: "Est. Rows",      value: Number(uploadData.rows_estimate).toLocaleString() },
      { label: "Columns",        value: uploadData.columns.length },
      { label: "File Size",      value: uploadData.memory_mb + " MB" },
      { label: "Duplicate Rows", value: uploadData.duplicates },
    ];
    container.innerHTML = chips.map((c) => `
      <div class="info-chip">
        <span class="chip-label">${c.label}</span>
        <span class="chip-value">${c.value}</span>
      </div>
    `).join("");
  }

  function renderDashboard(uploadData, analysis) {
    renderKPIs(analysis.kpis);
    renderHealthCard(analysis.clean_report);
    renderCharts(analysis.charts, analysis.mapped_columns);
    renderStatistics(analysis.statistics);
    renderInsights(analysis.insights);
    updateSidebarNav(analysis.mapped_columns);
  }

  // ── KPI Cards ──
  function renderKPIs(kpis) {
    const grid = document.getElementById("kpi-grid");
    grid.innerHTML = kpis.map((kpi) => `
      <div class="glass-card kpi-card" style="--kpi-color:${kpi.color}">
        <div class="kpi-icon"><i class="bi ${kpi.icon}"></i></div>
        <div class="kpi-label">${kpi.label}</div>
        <div class="kpi-value">${kpi.value}</div>
      </div>
    `).join("");
  }

  // ── Health Card ──
  function renderHealthCard(report) {
    const score = report.health_score;
    const color = score >= 85 ? "var(--green)" : score >= 65 ? "var(--amber)" : "var(--red)";

    const rows = [
      ["Original Rows",        report.original_rows.toLocaleString()],
      ["Duplicate Rows Removed", report.duplicate_rows.toLocaleString()],
      ["Missing Values Before", report.missing_before.toLocaleString()],
      ["Missing Values After",  report.missing_after.toLocaleString()],
      ["Columns Removed",      report.cols_removed],
      ["Final Rows",           report.final_rows.toLocaleString()],
    ];

    const suggestions = report.actions_taken.length
      ? report.actions_taken
      : ["Dataset looks clean — no major issues detected!"];

    document.getElementById("health-card").innerHTML = `
      <div class="health-score-wrap">
        <div class="health-score-number" style="color:${color}">${score}</div>
        <div class="health-score-label">/ 100 Health</div>
      </div>
      <div class="health-details">
        ${rows.map(([label, val]) => `
          <div class="health-row">
            <span>${label}</span>
            <span class="badge-val">${val}</span>
          </div>
        `).join("")}
      </div>
      <div class="health-actions">
        <p style="font-size:0.78rem;color:var(--text-muted);text-transform:uppercase;
                  letter-spacing:0.5px;margin-bottom:0.35rem;font-weight:600;">
          Cleaning Actions Taken
        </p>
        ${suggestions.map((s) => `
          <div class="suggestion-item">
            <i class="bi bi-check-circle-fill"></i>
            <span>${s}</span>
          </div>
        `).join("")}
      </div>
    `;
  }

  // ── Preview Table ──
  function renderPreviewTable(rows, columns) {
    if (!rows || rows.length === 0) return;
    const wrap = document.getElementById("preview-table-wrap");
    const thead = `<thead><tr>${columns.map((c) => `<th>${c}</th>`).join("")}</tr></thead>`;
    const tbody = `<tbody>${rows.map((row) =>
      `<tr>${columns.map((c) => `<td title="${row[c] ?? ""}">${row[c] ?? "<em style='color:var(--text-muted)'>null</em>"}</td>`).join("")}</tr>`
    ).join("")}</tbody>`;
    wrap.innerHTML = `<table class="data-table">${thead}${tbody}</table>`;
  }

  // ── Charts ──
  // Mapping: chart_key → { containerId, section, sectionNavId, label }
  const CHART_MAP = [
    // Sales
    { key: "sales_by_category",   section: "sales",      label: "Sales by Category" },
    { key: "sales_donut",         section: "sales",      label: "Sales Distribution" },
    { key: "sales_box",           section: "sales",      label: "Sales Box Plot" },
    { key: "sales_histogram",     section: "sales",      label: "Sales Histogram" },
    // Time Series
    { key: "monthly_trend",       section: "timeseries", label: "Monthly Trend" },
    { key: "quarterly_sales",     section: "timeseries", label: "Quarterly Sales" },
    { key: "yearly_trend",        section: "timeseries", label: "Yearly Trend" },
    { key: "rolling_average",     section: "timeseries", label: "Rolling Average" },
    // Profit
    { key: "profit_by_category",  section: "profit",     label: "Profit by Category" },
    { key: "profit_trend",        section: "profit",     label: "Monthly Profit Trend" },
    { key: "discount_vs_profit",  section: "profit",     label: "Discount vs Profit" },
    // Customers
    { key: "top_customers",       section: "customers",  label: "Top Customers" },
    { key: "customer_frequency",  section: "customers",  label: "Order Frequency" },
    // Products
    { key: "top_products",        section: "products",   label: "Top Products", full: true },
    { key: "worst_products",      section: "products",   label: "Bottom Products", full: true },
    { key: "abc_analysis",        section: "products",   label: "ABC Segmentation" },
    // Regional
    { key: "sales_by_region",     section: "regional",   label: "Sales by Region" },
    { key: "region_treemap",      section: "regional",   label: "Region Treemap" },
    // Statistics (generic)
    { key: "correlation_matrix",  section: "statistics", label: "Correlation Matrix", full: true },
    { key: "scatter_matrix",      section: "statistics", label: "Scatter Matrix", full: true },
    { key: "distributions",       section: "statistics", label: "Distributions", full: true },
    { key: "box_plots",           section: "statistics", label: "Box Plots (Outlier Detection)", full: true },
    { key: "missing_values",      section: "statistics", label: "Missing Values" },
    { key: "categorical_frequency", section: "statistics", label: "Category Frequency" },
  ];

  function renderCharts(charts, mappedCols) {
    // Clear all chart containers
    ["sales", "timeseries", "profit", "customers", "products", "regional", "statistics"]
      .forEach((s) => {
        const el = document.getElementById("charts-" + s);
        if (el) el.innerHTML = "";
      });

    const sectionsWithCharts = new Set();

    CHART_MAP.forEach(({ key, section, label, full }) => {
      const chartJson = charts[key];
      if (!chartJson) return;

      const containerId = `chart-${key}`;
      const gridId      = `charts-${section}`;
      const grid        = document.getElementById(gridId);
      if (!grid) return;

      const card = document.createElement("div");
      card.className = `chart-card${full ? " full-width" : ""}`;
      card.id = containerId;
      grid.appendChild(card);
      sectionsWithCharts.add(section);

      try {
        const figure = JSON.parse(chartJson);
        Plotly.newPlot(containerId, figure.data, figure.layout, PLOTLY_CFG);
      } catch (err) {
        card.innerHTML = `<p style="color:var(--text-muted);padding:1rem;">Chart render failed: ${err.message}</p>`;
      }
    });

    // Enable nav items that have charts; disable the rest (except always-visible ones)
    const alwaysVisible = ["overview", "statistics", "insights"];
    document.querySelectorAll(".nav-item[data-section]").forEach((link) => {
      const sec = link.dataset.section;
      if (alwaysVisible.includes(sec)) {
        link.classList.remove("disabled");
      } else {
        if (sectionsWithCharts.has(sec)) {
          link.classList.remove("disabled");
        } else {
          link.classList.add("disabled");
        }
      }
    });

    // Force Plotly resize after layout settles
    setTimeout(() => window.dispatchEvent(new Event("resize")), 600);
  }

  // ── Statistics Table ──
  function renderStatistics(stats) {
    const container = document.getElementById("stats-content");
    if (!stats || Object.keys(stats).length === 0) {
      container.innerHTML = `<p style="color:var(--text-muted)">No numeric columns found.</p>`;
      return;
    }

    const statKeys = [
      ["count","Count"], ["mean","Mean"], ["median","Median"], ["std","Std Dev"],
      ["variance","Variance"], ["min","Min"], ["max","Max"],
      ["q1","Q1 (25%)"], ["q3","Q3 (75%)"], ["iqr","IQR"],
      ["p5","P5"], ["p95","P95"], ["skewness","Skewness"], ["kurtosis","Kurtosis"],
    ];

    const columns = Object.keys(stats);
    const headerRow = `<tr>
      <th>Statistic</th>
      ${columns.map((c) => `<th>${c}</th>`).join("")}
    </tr>`;

    const rows = statKeys.map(([key, label]) => `
      <tr>
        <td>${label}</td>
        ${columns.map((c) => `<td>${stats[c][key] !== undefined ? stats[c][key] : "—"}</td>`).join("")}
      </tr>
    `).join("");

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

  // ── AI Insights ──
  function renderInsights(insights) {
    const grid = document.getElementById("insights-grid");
    if (!insights || insights.length === 0) {
      grid.innerHTML = `<p style="color:var(--text-muted)">No insights generated.</p>`;
      return;
    }

    grid.innerHTML = insights.map((ins) => `
      <div class="insight-card">
        <div class="insight-section-label">
          <i class="bi ${ins.icon || 'bi-lightbulb-fill'}"></i>
          ${ins.section}
        </div>

        <div class="insight-row">
          <div class="insight-row-label">📊 Observation</div>
          <div class="insight-row-text">${ins.observation}</div>
        </div>
        <div class="insight-row">
          <div class="insight-row-label">💡 Insight</div>
          <div class="insight-row-text">${ins.insight}</div>
        </div>
        <div class="insight-row">
          <div class="insight-row-label">✅ Recommendation</div>
          <div class="insight-row-text">${ins.recommendation}</div>
        </div>
        ${ins.risk ? `
        <div class="insight-row insight-risk">
          <div class="insight-row-label">⚠ Potential Risk</div>
          <div class="insight-row-text">${ins.risk}</div>
        </div>` : ""}
      </div>
    `).join("");
  }

  // ── Sidebar Nav Visibility ──
  function updateSidebarNav(mappedCols) {
    // These sections map to their required column keys
    const sectionRequirements = {
      sales:      ["Sales"],
      timeseries: ["Date", "Sales"],
      profit:     ["Profit"],
      customers:  ["Customer"],
      products:   ["Product"],
      regional:   ["Region"],
    };
    // Sections are enabled/disabled in renderCharts based on actual charts returned.
    // Here we can also enable overview/statistics/insights unconditionally.
    ["nav-overview", "nav-statistics", "nav-insights"].forEach((id) => {
      const el = document.getElementById(id);
      if (el) el.classList.remove("disabled");
    });
  }

  // ── Report Download ──
  function downloadReport(format) {
    if (!_filename) {
      alert("Please upload a dataset first.");
      return;
    }
    window.location.href = `/download/${format}/${_filename}`;
  }

  // ── Reset App ──
  function reset() {
    _filename     = null;
    _origName     = "";
    _analysisData = null;
    fileInput.value = "";
    document.getElementById("topbar-title").innerHTML =
      `<i class="bi bi-upload"></i>&nbsp; Upload a CSV to begin analysis`;
    document.querySelectorAll(".nav-item").forEach((l) => {
      l.classList.remove("active", "disabled");
    });
    document.getElementById("nav-overview").classList.add("active");
    activateSection("section-overview", null);
    showPage("page-upload");
  }

  // Expose public API
  return { downloadReport, reset };
})();
