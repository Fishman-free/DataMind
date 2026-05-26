/**
 * NL2Vis 图表工作台 — DataMind v2.0
 *
 * 管理自然语言图表生成、渲染和迭代修改。
 * Plotly.react() 渲染交互图表，支持代码复制和 PNG 下载。
 * 与 chat.js 的双向图表同步通过全局变量和 window 函数实现。
 *
 * 来源：学生+AI
 */

window._chartWorkspace = null;
window._currentChartData = null;
window._currentChartCode = '';

/**
 * 初始化图表工作台。
 */
function initChartWorkspace() {
    // 图表工作台使用普通 fetch，不依赖 SSE。只需检查基本功能。
    if (typeof fetch === 'undefined' || typeof Plotly === 'undefined') {
        document.getElementById('chart-ws-fallback').style.display = 'block';
        document.getElementById('chart-ws').style.display = 'none';
        return;
    }
    document.getElementById('chart-ws').style.display = 'block';
    document.getElementById('chart-ws-fallback').style.display = 'none';

    // 绑定输入框发送事件
    var input = document.getElementById('chart-input');
    input.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            generateChart();
        }
    });

    // 绑定发送按钮
    document.getElementById('chart-send-btn').addEventListener('click', generateChart);

    // 绑定快捷操作按钮
    var quickBtns = document.querySelectorAll('.chart-quick-btn');
    for (var i = 0; i < quickBtns.length; i++) {
        quickBtns[i].addEventListener('click', function () {
            var action = this.getAttribute('data-action');
            quickChartAction(action);
        });
    }
}

/**
 * 生成图表（发送自然语言描述到后端）。
 */
function generateChart() {
    var input = document.getElementById('chart-input');
    var description = input.value.trim();
    if (!description) return;

    var statusEl = document.getElementById('chart-status');
    statusEl.textContent = '正在生成...';
    statusEl.style.color = 'var(--blue)';

    var btn = document.getElementById('chart-send-btn');
    btn.disabled = true;

    fetch('/api/chart/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            description: description,
            previous_chart: _currentChartData,
        }),
    })
        .then(function (r) { return r.json(); })
        .then(function (data) {
            if (data.success && data.chart) {
                _currentChartData = data.chart;
                _currentChartCode = data.code || '';
                renderChart(data.chart);
                // 同步工作台图表到对话区的最新气泡
                if (typeof window.updateChatChartFromWorkspace === 'function') {
                    window.updateChatChartFromWorkspace(data.chart);
                }
                statusEl.textContent = '\u2713 ' + (data.explanation || '生成成功');
                statusEl.style.color = 'var(--green)';
            } else {
                _currentChartCode = '';
                var errMsg = data.explanation || '生成失败';
                // 语法错误 / 代码执行错误给出更友好的提示
                if (errMsg.indexOf('语法错误') >= 0) {
                    errMsg += '（AI 生成的代码有误，请简化描述或换种说法重试）';
                }
                statusEl.textContent = '\u2717 ' + errMsg;
                statusEl.style.color = 'var(--red)';
            }
            btn.disabled = false;
        })
        .catch(function (err) {
            _currentChartCode = '';
            statusEl.textContent = '\u2717 网络错误：' + err.message;
            statusEl.style.color = 'var(--red)';
            btn.disabled = false;
        });
}

/**
 * 快捷操作（预设指令）。
 * @param {string} action - 快捷操作 ID
 */
function quickChartAction(action) {
    var prompts = {
        'line': '改为折线图',
        'bar': '改为柱状图',
        'quarterly': '按季度聚合',
        'top5': '只显示 Top 5',
        'dark': '使用深色主题',
        'light': '使用浅色主题',
        'morandi': '使用莫兰迪色系配色，低饱和度灰调色',
    };
    var prompt = prompts[action] || action;
    document.getElementById('chart-input').value = prompt;
    _currentChartCode = '';
    generateChart();
}

/**
 * 在图表区域渲染 Plotly 图表。
 * 兼容两种格式：{data, layout} 标准格式 和 裸数组格式。
 * @param {object} chartData - Plotly JSON
 */
function renderChart(chartData) {
    var container = document.getElementById('chart-plot-area');
    if (typeof Plotly === 'undefined' || !container) return;
    try {
        // 兼容标准 {data, layout} 格式和裸数组格式（与 _injectChart 对齐）
        var traces, layout;
        if (chartData && chartData.data !== undefined) {
            traces = chartData.data || [];
            layout = chartData.layout || {};
        } else if (Array.isArray(chartData)) {
            traces = chartData;
            layout = {};
        } else {
            // 降级：将整个 chartData 当作 data 数组尝试
            traces = chartData ? [chartData] : [];
            layout = {};
        }
        // 剥离嵌入的 plotly 模板（防止 plotly_dark 模板覆盖透明背景），
        // 强制透明背景确保 scatter 等图表在暗色页面中正确显示。
        layout = _cleanChartLayout(layout);
        // 确保散点/折线等 trace 的 marker 可见性
        traces = _ensureMarkerVisibility(traces);
        Plotly.react(container, traces, layout, {
            responsive: true,
            displayModeBar: true,
            modeBarButtonsToRemove: ['lasso2d', 'select2d'],
        });
    } catch (e) {
        console.error('工作台图表渲染失败:', e);
    }
}

/**
 * 清理图表 layout：剥离嵌入的 template 对象，强制透明背景。
 * @param {object} layout - Plotly layout
 * @returns {object} 清理后的 layout
 */
function _cleanChartLayout(layout) {
    var cleaned = Object.assign({}, layout);
    // 移除 plotly 内嵌模板对象（可能覆盖背景色导致图表元素不可见）
    delete cleaned.template;
    // 强制透明背景以适配深色页面
    cleaned.paper_bgcolor = 'rgba(0,0,0,0)';
    cleaned.plot_bgcolor  = 'rgba(0,0,0,0)';
    return cleaned;
}

/**
 * 确保散点/折线图的 marker 有足够的可见性（大小 >= 5，不透明度 >= 0.7）。
 * @param {Array} traces - Plotly traces 数组
 * @returns {Array} 处理后的 traces
 */
function _ensureMarkerVisibility(traces) {
    if (!Array.isArray(traces)) return traces;
    return traces.map(function (trace) {
        if (!trace) return trace;
        var t = Object.assign({}, trace);
        if (t.type === 'scatter' || t.type === 'scattergl') {
            // 先继承原有 marker，再强制覆盖不可见项（避免 Object.assign 顺序导致默认被覆盖）
            var marker = Object.assign({}, t.marker || {});
            if (!Array.isArray(marker.color) && !marker.color) {
                marker.color = 'rgba(0,229,255,0.75)';
            }
            if (!marker.size || marker.size < 5) marker.size = 6;
            if (!marker.opacity || marker.opacity < 0.3) marker.opacity = 0.85;
            t.marker = marker;
        }
        return t;
    });
}

/**
 * 复制图表代码到剪贴板。
 */
function copyChartCode() {
    if (!_currentChartCode) {
        alert('暂无图表代码');
        return;
    }
    navigator.clipboard.writeText(_currentChartCode).then(function () {
        var statusEl = document.getElementById('chart-status');
        statusEl.textContent = '\u2713 代码已复制';
        statusEl.style.color = 'var(--green)';
    });
}

/**
 * 下载图表为 PNG。
 */
function downloadChartPNG() {
    var container = document.getElementById('chart-plot-area');
    if (!container || typeof Plotly === 'undefined') return;
    // 使用容器实际尺寸 × 2（Retina 级别输出），最小保证 800×500
    var w = Math.max(container.offsetWidth  || 0, 800);
    var h = Math.max(container.offsetHeight || 0, 500);
    Plotly.downloadImage(container, {
        format: 'png',
        width:  w,
        height: h,
        scale:  2,         // 2× 像素密度，导出高清图
        filename: 'datamind_chart',
    });
}
