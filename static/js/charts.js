/**
 * DataMind 图表渲染组件 — charts.js
 * Neural Night 深色主题 Plotly 图表
 * 来源：学生+AI
 */

// ── 暗色主题基础配置 ──────────────────────────────────────────
const _DARK_AXIS = {
    gridcolor:    "rgba(79,159,255,0.08)",
    linecolor:    "rgba(79,159,255,0.14)",
    tickcolor:    "rgba(79,159,255,0.14)",
    tickfont:     { color: "#8899B8", size: 11 },
    title:        { font: { color: "#8899B8", size: 11 } },
    zerolinecolor:"rgba(79,159,255,0.12)",
};

const _DARK_BASE = {
    paper_bgcolor: "transparent",
    plot_bgcolor:  "transparent",
    font:  { color: "#8899B8", family: "Outfit, Noto Sans SC, sans-serif", size: 11 },
    margin:{ t: 20, b: 50, l: 60, r: 20 },
    hoverlabel: {
        bgcolor:    "rgba(12,17,32,0.95)",
        bordercolor:"rgba(79,159,255,0.4)",
        font: { color: "#E8EEFF", size: 12 },
    },
    showlegend: false,
};

const _PLOTLY_CONFIG = {
    responsive: true,
    displaylogo: false,
    modeBarButtonsToRemove: ["select2d","lasso2d","autoScale2d"],
};

function _layout(extra) {
    return Object.assign({}, _DARK_BASE, extra);
}

// ── 页面入口 ──────────────────────────────────────────────────
window.initVisualizationPage = async function () {
    const res = await fetch("/api/data/summary");
    if (!res.ok) return;

    document.getElementById("no-data-alert").style.display   = "none";
    const section = document.getElementById("charts-section");
    section.style.display = "block";
    section.style.opacity = "0";
    requestAnimationFrame(() => {
        section.style.transition = "opacity .5s ease";
        section.style.opacity = "1";
    });

    await Promise.all([
        loadSalesTrend(),
        loadTopProducts(),
        loadCountryDistribution(),
        loadCorrelationMatrix(),
        loadTimePattern(),
        loadRFMAnalysis(),
    ]);
};

// ── 1. 月度销售趋势 ───────────────────────────────────────────
// 后端返回：{ labels: [...], values: [...] }
async function loadSalesTrend() {
    const el = document.getElementById("chart-sales-trend");
    if (!el) return;
    _showLoading(el);
    try {
        const res = await fetch("/api/analysis/sales_trend");
        if (!res.ok) { _showError(el, await res.json()); return; }
        renderSalesTrend(el, await res.json());
    } catch (e) { _showError(el, { error: e.message }); }
}

function renderSalesTrend(el, data) {
    if (!data?.labels?.length) { _showEmpty(el); return; }
    el.innerHTML = "";
    Plotly.newPlot(el, [{
        type: "scatter", mode: "lines+markers",
        x: data.labels,
        y: data.values,
        name: "销售额",
        line:   { color: "#4F9FFF", width: 2.5, shape: "spline" },
        marker: { size: 5, color: "#4F9FFF", line: { color: "#00D4FF", width: 1.5 } },
        fill: "tozeroy",
        fillcolor: "rgba(79,159,255,0.07)",
        hovertemplate: "%{x}<br>¥%{y:,.2f}<extra></extra>",
    }], _layout({
        xaxis: { ...Object.assign({}, _DARK_AXIS), title: { text: "时间", font: { color: "#8899B8" } } },
        yaxis: { ...Object.assign({}, _DARK_AXIS), title: { text: "销售额", font: { color: "#8899B8" } } },
        margin: { t: 16, b: 50, l: 70, r: 20 },
    }), _PLOTLY_CONFIG);
}

// ── 2. 畅销商品 ───────────────────────────────────────────────
// 后端返回：[{ name: str, value: float }]
async function loadTopProducts() {
    const el = document.getElementById("chart-top-products");
    if (!el) return;
    _showLoading(el);
    try {
        const res = await fetch("/api/analysis/top_products?n=10");
        if (!res.ok) { _showError(el, await res.json()); return; }
        renderTopProducts(el, await res.json());
    } catch (e) { _showError(el, { error: e.message }); }
}

function renderTopProducts(el, rows) {
    if (!rows?.length) { _showEmpty(el); return; }
    el.innerHTML = "";
    // 后端字段：name / value
    const names = rows.map(r => r.name  || r.product || r.Description || r.StockCode || "").reverse();
    const vals  = rows.map(r => r.value || r.revenue  || r.TotalAmount  || r.total    || 0).reverse();
    const colors = vals.map((_, i) =>
        `rgba(${Math.round(79 + (255-79)*i/vals.length)}, ${Math.round(159 + (179-159)*i/vals.length)}, 255, 0.85)`
    );
    Plotly.newPlot(el, [{
        type: "bar", orientation: "h",
        x: vals, y: names,
        marker: { color: colors, line: { width: 0 } },
        hovertemplate: "<b>%{y}</b><br>¥%{x:,.0f}<extra></extra>",
    }], _layout({
        xaxis: { ...Object.assign({}, _DARK_AXIS), title: { text: "销售额" } },
        yaxis: { ...Object.assign({}, _DARK_AXIS), tickfont: { size: 10, color: "#8899B8" } },
        margin: { t: 16, b: 50, l: 180, r: 20 },
    }), _PLOTLY_CONFIG);
}

// ── 3. 国家分布 ───────────────────────────────────────────────
// 后端返回：[{ country: str, value: float, percentage: float }]
async function loadCountryDistribution() {
    const el = document.getElementById("chart-country");
    if (!el) return;
    _showLoading(el);
    try {
        const res = await fetch("/api/analysis/country_distribution");
        if (!res.ok) { _showError(el, await res.json()); return; }
        renderCountryDistribution(el, await res.json());
    } catch (e) { _showError(el, { error: e.message }); }
}

function renderCountryDistribution(el, rows) {
    if (!rows?.length) { _showEmpty(el); return; }
    el.innerHTML = "";
    const labels = rows.map(r => r.country || r.Country || "");
    // 后端字段：value（原来找 revenue，已对齐）
    const values = rows.map(r => r.value || r.revenue || r.TotalAmount || r.total || 0);
    Plotly.newPlot(el, [{
        type: "pie", labels, values, hole: 0.38,
        textinfo: "percent+label", textfont: { size: 11, color: "#E8EEFF" },
        marker: {
            colors: ["#4F9FFF","#00D4FF","#A78BFA","#FFB347","#34D399","#FF5C6B",
                     "#60A5FA","#38BDF8","#818CF8","#FCD34D"],
            line: { color: "rgba(6,9,18,0.8)", width: 2 },
        },
        hovertemplate: "<b>%{label}</b><br>¥%{value:,.0f} (%{percent})<extra></extra>",
    }], _layout({ margin: { t: 16, b: 16, l: 16, r: 16 }, showlegend: false }), _PLOTLY_CONFIG);
}

// ── 4. 相关性矩阵 ─────────────────────────────────────────────
// 后端返回：{ columns: [...], matrix: [[...]] }
async function loadCorrelationMatrix() {
    const el = document.getElementById("chart-correlation");
    if (!el) return;
    _showLoading(el);
    try {
        const res = await fetch("/api/analysis/correlation_matrix");
        if (!res.ok) { _showError(el, await res.json()); return; }
        renderCorrelationMatrix(el, await res.json());
    } catch (e) { _showError(el, { error: e.message }); }
}

function renderCorrelationMatrix(el, data) {
    // 后端返回 { columns: [...], matrix: [[...]] }
    const columns = data?.columns;
    const z       = data?.matrix;
    if (!columns?.length || !z?.length) { _showEmpty(el); return; }
    el.innerHTML = "";
    Plotly.newPlot(el, [{
        type: "heatmap", x: columns, y: columns, z,
        colorscale: [
            [0,    "#FF5C6B"], [0.25, "#FF8A94"],
            [0.45, "#1A2540"], [0.55, "#1A2540"],
            [0.75, "#7AB8FF"], [1,    "#4F9FFF"],
        ],
        zmin: -1, zmax: 1,
        text: z.map(row => row.map(v => (typeof v === "number" ? v.toFixed(2) : "0.00"))),
        texttemplate: "%{text}",
        textfont: { size: 11, color: "#E8EEFF" },
        showscale: true,
        colorbar: {
            tickfont: { color: "#8899B8", size: 10 },
            outlinecolor: "transparent",
            bgcolor: "transparent",
        },
        hovertemplate: "%{x} × %{y}<br>r = %{z:.3f}<extra></extra>",
    }], _layout({
        xaxis: { ...Object.assign({}, _DARK_AXIS), tickangle: -30, tickfont: { size: 10 } },
        yaxis: { ...Object.assign({}, _DARK_AXIS), tickfont: { size: 10 } },
        margin: { t: 16, b: 80, l: 80, r: 70 },
    }), _PLOTLY_CONFIG);
}

// ── 5. 时间规律（7×24 热力图）────────────────────────────────
// 后端返回：{ days: [7], hours: [24], matrix: [[7 行 × 24 列]] }
async function loadTimePattern() {
    const el = document.getElementById("chart-time-pattern");
    if (!el) return;
    _showLoading(el);
    try {
        const res = await fetch("/api/analysis/time_pattern");
        if (!res.ok) { _showError(el, await res.json()); return; }
        renderTimePattern(el, await res.json());
    } catch (e) { _showError(el, { error: e.message }); }
}

function renderTimePattern(el, data) {
    if (!data?.days?.length || !data?.matrix?.length) { _showEmpty(el); return; }
    el.innerHTML = "";
    Plotly.newPlot(el, [{
        type: "heatmap",
        x: data.hours,
        y: data.days,
        z: data.matrix,
        colorscale: [
            [0,    "rgba(12,17,32,0.8)"],
            [0.2,  "#0D3560"],
            [0.5,  "#1A5EA8"],
            [0.75, "#4F9FFF"],
            [1,    "#00D4FF"],
        ],
        showscale: false,
        xgap: 1.5,
        ygap: 1.5,
        hovertemplate: "<b>%{y}</b> %{x}:00<br>%{z:,} 单<extra></extra>",
    }], _layout({
        xaxis: {
            ...Object.assign({}, _DARK_AXIS),
            title: { text: "小时", font: { color: "#8899B8" } },
            tickmode: "array",
            tickvals: ["0","3","6","9","12","15","18","21"],
            ticktext: ["0时","3时","6时","9时","12时","15时","18时","21时"],
        },
        yaxis: { ...Object.assign({}, _DARK_AXIS) },
        margin: { t: 16, b: 50, l: 55, r: 20 },
    }), _PLOTLY_CONFIG);
}

// ── 6. RFM 散点图 ─────────────────────────────────────────────
// 后端返回：{ total_customers: int, customers: [{...}], reference_date: str }
async function loadRFMAnalysis() {
    const el = document.getElementById("chart-rfm");
    if (!el) return;
    _showLoading(el);
    try {
        const res = await fetch("/api/analysis/rfm_analysis");
        if (!res.ok) { _showError(el, await res.json()); return; }
        renderRFMScatter(el, await res.json());
    } catch (e) { _showError(el, { error: e.message }); }
}

function renderRFMScatter(el, data) {
    // 后端返回 {total_customers, customers:[...], reference_date} 或错误 {error}
    const rows = data?.customers || (Array.isArray(data) ? data : []);
    if (!rows.length) { _showEmpty(el); return; }
    el.innerHTML = "";
    const x    = rows.map(r => r.frequency || 0);
    const y    = rows.map(r => r.monetary  || 0);
    const text = rows.map(r => `ID: ${r.customer_id || ""}<br>近 ${r.recency || 0} 天`);
    const rec  = rows.map(r => r.recency || 0);
    Plotly.newPlot(el, [{
        type: "scatter", mode: "markers",
        x, y, text,
        hovertemplate: "%{text}<br>频次 %{x}<br>消费 ¥%{y:,.0f}<extra></extra>",
        marker: {
            size: 6, opacity: .7,
            color: rec,
            colorscale: [
                [0, "#FF5C6B"], [0.4, "#FFB347"],
                [0.7, "#4F9FFF"], [1, "#00D4FF"],
            ],
            showscale: true,
            colorbar: {
                title: { text: "距今(天)", font: { size: 10, color: "#8899B8" } },
                tickfont: { size: 10, color: "#8899B8" },
                outlinecolor: "transparent",
            },
            line: { width: 0 },
        },
    }], _layout({
        xaxis: { ...Object.assign({}, _DARK_AXIS), title: { text: "购买频次" } },
        yaxis: { ...Object.assign({}, _DARK_AXIS), title: { text: "消费金额" } },
        margin: { t: 16, b: 55, l: 75, r: 75 },
    }), _PLOTLY_CONFIG);
}

// ── 工具函数 ──────────────────────────────────────────────────
function _showLoading(el) {
    el.innerHTML = `
        <div style="height:100%;display:flex;align-items:center;justify-content:center;color:var(--t3)">
            <div class="spinner-border me-2" style="width:20px;height:20px;border-width:2px;color:var(--blue)"></div>
            <span style="font-size:13px">加载中…</span>
        </div>`;
}
function _showError(el, err) {
    el.innerHTML = `
        <div style="height:100%;display:flex;align-items:center;justify-content:center">
            <span style="color:var(--red);font-size:13px">
                <i class="bi bi-exclamation-circle me-1"></i>${err?.error || "加载失败"}
            </span>
        </div>`;
}
function _showEmpty(el) {
    el.innerHTML = `
        <div style="height:100%;display:flex;align-items:center;justify-content:center;color:var(--t3);font-size:13px">
            <i class="bi bi-bar-chart me-2"></i>暂无数据
        </div>`;
}
