/**
 * NL2Vis 图表工作台 — DataMind v2.0
 *
 * 管理自然语言图表生成、渲染和迭代修改。
 * Plotly.react() 渲染交互图表，支持代码复制和 PNG 下载。
 */

let _chartWorkspace = null;
let _currentChartData = null;
let _currentChartCode = '';

/**
 * 初始化图表工作台。
 */
function initChartWorkspace() {
    if (!supportsSSE()) {
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
                // 保存代码（从 explanation 中提取，实际应由后端返回）
                statusEl.textContent = '\u2713 ' + (data.explanation || '生成成功');
                statusEl.style.color = 'var(--green)';
            } else {
                _currentChartCode = '';
                statusEl.textContent = '\u2717 ' + (data.explanation || '生成失败');
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
    };
    var prompt = prompts[action] || action;
    document.getElementById('chart-input').value = prompt;
    _currentChartCode = '';
    generateChart();
}

/**
 * 在图表区域渲染 Plotly 图表。
 * @param {object} chartData - Plotly JSON
 */
function renderChart(chartData) {
    var container = document.getElementById('chart-plot-area');
    if (typeof Plotly !== 'undefined') {
        Plotly.react(container, chartData.data || [], chartData.layout || {}, {
            responsive: true,
            displayModeBar: true,
            modeBarButtonsToRemove: ['lasso2d', 'select2d'],
        });
    }
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
    if (typeof Plotly !== 'undefined') {
        Plotly.downloadImage(container, {
            format: 'png',
            width: 1200,
            height: 800,
            filename: 'datamind_chart',
        });
    }
}
