/**
 * DataMind 智能问答组件 — chat.js
 * 来源：学生+AI
 */

// ── 活跃连接追踪 ──────────────────────────────────────────
var _activeSSEConnection = null;   // 当前活跃的 SSE 连接对象
var _sendingLock        = false;   // 发送防抖锁

// ── 页面初始化 ────────────────────────────────────────────
window.initAnalysisPage = async function () {
    await loadChatHistory();
};

// ── 历史记录加载 ──────────────────────────────────────────
async function loadChatHistory() {
    try {
        const res = await fetch("/api/chat/history");
        if (!res.ok) return;
        const history = await res.json();
        const messagesEl = document.getElementById("chat-messages");
        if (!messagesEl) return;
        history.forEach(msg => appendMessage(msg.role, msg.content));
    } catch (e) {
        console.error("加载历史失败:", e);
    }
}

// ── 发送消息 ──────────────────────────────────────────────
async function sendChatMessage() {
    // 防抖锁：上一次请求未完成前禁止发送
    if (_sendingLock) return;

    const input    = document.getElementById("chat-input");
    const question = (input?.value || "").trim();
    if (!question) return;

    // 中断上一个活跃的 SSE 连接
    if (_activeSSEConnection) {
        _activeSSEConnection.abort();
        _activeSSEConnection = null;
    }
    _sendingLock = true;

    input.value = "";
    appendMessage("user", question);
    setLoading(true);

    // SSE 流式路径（优先）
    if (typeof supportsSSE === 'function' && supportsSSE()) {
        var bubble = appendMessage("assistant", "");
        bubble._fullText = "";

        _activeSSEConnection = createSSEConnection('/api/chat', { question: question }, {
            onTextDelta: function (content) {
                bubble._fullText += content;
                var bodyEl = bubble.querySelector('.chat-msg-body');
                if (bodyEl && typeof marked !== 'undefined') {
                    bodyEl.innerHTML = marked.parse(bubble._fullText);
                } else if (bodyEl) {
                    bodyEl.textContent = bubble._fullText;
                }
                scrollToBottom();
            },
            onHeartbeat: function () {
                // 代码执行中，显示心跳指示器
                var existing = bubble.querySelector('.exec-result-inline');
                if (!existing) {
                    var div = document.createElement('div');
                    div.className = 'exec-result-inline';
                    div.innerHTML = '<span class="exec-heartbeat">代码执行中...</span>';
                    var anchor = bubble.querySelector('.chat-msg-body');
                    if (anchor) {
                        anchor.parentNode.insertBefore(div, anchor.nextSibling);
                    }
                }
            },
            onCodeComplete: function (code) {
                // 同步代码到图表工作台，供"复制代码"按钮使用
                if (typeof _currentChartCode !== 'undefined') _currentChartCode = code;
            },
            onExecResult: function (msg) {
                _injectExecResult(bubble, msg);
            },
            onChart: function (chartData) {
                _injectChart(bubble, chartData);
                // 同时推送到图表工作台，并同步全局状态
                if (typeof renderChart === 'function') {
                    renderChart(chartData);
                }
                window._currentChartData = chartData;  // 直接写入，无需判断
                // 更新工作台状态提示，告知图表已来自对话
                var statusEl = document.getElementById('chart-status');
                if (statusEl) {
                    statusEl.textContent = '\u2713 图表已同步自对话';
                    statusEl.style.color = 'var(--green)';
                }
            },
            onError: function (message) {
                var errDiv = document.createElement('div');
                errDiv.className = 'text-danger';
                errDiv.textContent = '错误：' + message;
                bubble.appendChild(errDiv);
                _activeSSEConnection = null;
                _sendingLock = false;
                setLoading(false);
            },
            onDone: function () {
                _activeSSEConnection = null;
                _sendingLock = false;
                setLoading(false);
                scrollToBottom();
            }
        });
        return;
    }

    // Fallback：同步 fetch 路径
    try {
        const res  = await fetch("/api/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ question }),
        });
        const data = await res.json();

        if (!res.ok) {
            appendMessage("error", data.error || "请求失败");
            return;
        }
        renderChatResponse(data);
    } catch (e) {
        appendMessage("error", "网络错误：" + e.message);
    } finally {
        setLoading(false);
    }
}

function renderChatResponse(data) {
    // 文字回答
    var bubble = null;
    if (data.answer) {
        bubble = appendMessage("assistant", data.answer);
    }
    // 执行结果内联注入 — 兼容平铺字段（后端实际格式）与 execution 嵌套格式
    var exec = data.execution || (Object.prototype.hasOwnProperty.call(data, "success") ? data : null);
    if (exec && bubble) {
        _injectExecResult(bubble, {
            success: exec.success,
            result: exec.result,
            stdout: exec.stdout,
            error: exec.error
        });
        if (exec.chart) {
            _injectChart(bubble, exec.chart);
        }
    }
}

function renderExecChart(chartData) {
    const container = document.getElementById("exec-chart");
    if (!container || !window.Plotly) return;
    container.style.display = "block";
    try {
        if (chartData.data && chartData.layout !== undefined) {
            Plotly.newPlot(container, chartData.data, chartData.layout || {}, { responsive: true });
        } else {
            Plotly.newPlot(container, chartData, {}, { responsive: true });
        }
    } catch (e) {
        console.error("图表渲染失败:", e);
    }
}

// ── 重置对话 ──────────────────────────────────────────────
async function resetChat() {
    // 中断活跃的 SSE 连接并重置防抖锁
    if (_activeSSEConnection) {
        _activeSSEConnection.abort();
        _activeSSEConnection = null;
    }
    _sendingLock = false;

    try {
        await fetch("/api/chat/reset", { method: "POST" });
        const messagesEl = document.getElementById("chat-messages");
        if (messagesEl) messagesEl.innerHTML = "";
        const codeEl   = document.getElementById("generated-code");
        const resultEl = document.getElementById("exec-result");
        const chartEl  = document.getElementById("exec-chart");
        if (codeEl)   codeEl.style.display   = "none";
        if (resultEl) resultEl.style.display  = "none";
        if (chartEl)  chartEl.style.display   = "none";
    } catch (e) {
        console.error("重置失败:", e);
    }
}

// ── 辅助函数 ──────────────────────────────────────────────
function appendMessage(role, content) {
    const container = document.getElementById("chat-messages");
    if (!container) return;

    const div = document.createElement("div");
    div.className = `chat-msg chat-msg-${role} mb-2`;

    const label = { user: "你", assistant: "AI", error: "错误" }[role] || role;
    const badgeClass = { user: "bg-primary", assistant: "bg-success", error: "bg-danger" }[role] || "bg-secondary";

    let bodyHtml = content;
    if (role === "assistant" && window.marked) {
        bodyHtml = marked.parse(content);
    }
    // 必须用 div（块级），用 span 会导致 marked 生成的 <p> 被浏览器弹出到外部，
    // 变成宽度为 0 的 flex 项，内容不可见。
    div.innerHTML = `
        <span class="badge ${badgeClass} me-2">${label}</span>
        <div class="chat-msg-body">${bodyHtml}</div>
    `;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
    return div;
}

function setLoading(on) {
    const btn     = document.getElementById("chat-send-btn");
    const spinner = document.getElementById("chat-spinner");
    if (btn)     btn.disabled             = on;
    if (spinner) spinner.style.display    = on ? "inline-block" : "none";

    // SSE path handles its own bubble, so skip typing-bubble for SSE
    if (on && typeof supportsSSE === 'function' && supportsSSE()) {
        return;
    }

    const container = document.getElementById("chat-messages");
    if (!container) return;
    if (on) {
        // 添加打字气泡
        const bubble = document.createElement("div");
        bubble.id        = "typing-bubble";
        bubble.className = "chat-msg chat-msg-assistant mb-2";
        bubble.innerHTML = `
            <span class="badge bg-success me-2">AI</span>
            <span class="chat-msg-body">
                <span class="typing-dots">
                    <span></span><span></span><span></span>
                </span>
            </span>`;
        container.appendChild(bubble);
        container.scrollTop = container.scrollHeight;
    } else {
        const bubble = document.getElementById("typing-bubble");
        if (bubble) bubble.remove();
    }
}

function scrollToBottom() {
    const container = document.getElementById("chat-messages");
    if (container) {
        container.scrollTop = container.scrollHeight;
    }
}

// ── 内联执行结果注入 ──────────────────────────────────────

/**
 * HTML 转义，防止 XSS。
 */
function _escapeHtml(str) {
    var div = document.createElement('div');
    div.appendChild(document.createTextNode(str));
    return div.innerHTML;
}

/**
 * 格式化代码执行结果为 HTML。
 * - 简单数值/字符串 → 高亮大字体显示
 * - list of dict → 迷你 HTML 表格
 * - dict → 键值对列表
 * - 其他 → JSON 格式化
 *
 * @param {*} result - 执行结果值
 * @returns {string} HTML 字符串
 */
function _formatResult(result) {
    if (result == null) return '';

    // 简单数值
    if (typeof result === 'number') {
        return '<div class="exec-result-number">' + _escapeHtml(String(result)) + '</div>';
    }
    // 字符串
    if (typeof result === 'string') {
        return '<div class="exec-result-text">' + _escapeHtml(result) + '</div>';
    }
    // 布尔值
    if (typeof result === 'boolean') {
        return '<div class="exec-result-number">' + (result ? 'true' : 'false') + '</div>';
    }
    // list of dict → 迷你表格
    if (Array.isArray(result) && result.length > 0 && typeof result[0] === 'object' && result[0] !== null) {
        var keys = Object.keys(result[0]);
        var html = '<table class="exec-result-table"><thead><tr>';
        for (var i = 0; i < keys.length; i++) {
            html += '<th>' + _escapeHtml(keys[i]) + '</th>';
        }
        html += '</tr></thead><tbody>';
        for (var r = 0; r < Math.min(result.length, 50); r++) {
            html += '<tr>';
            for (var k = 0; k < keys.length; k++) {
                var val = result[r][keys[k]];
                html += '<td>' + _escapeHtml(val != null ? String(val) : '') + '</td>';
            }
            html += '</tr>';
        }
        html += '</tbody></table>';
        if (result.length > 50) {
            html += '<div class="exec-result-note">（仅显示前 50 条，共 ' + result.length + ' 条）</div>';
        }
        return html;
    }
    // dict → 键值对列表
    if (typeof result === 'object' && !Array.isArray(result)) {
        var dictHtml = '<dl class="exec-result-dict">';
        var entries = Object.entries(result);
        for (var e = 0; e < entries.length; e++) {
            dictHtml += '<dt>' + _escapeHtml(String(entries[e][0])) + '</dt>';
            var valStr = entries[e][1] != null ? String(entries[e][1]) : '';
            dictHtml += '<dd>' + _escapeHtml(valStr) + '</dd>';
        }
        dictHtml += '</dl>';
        return dictHtml;
    }
    // 数组（非 dict）
    if (Array.isArray(result)) {
        return '<div class="exec-result-data">' + _escapeHtml(JSON.stringify(result, null, 2)) + '</div>';
    }
    return '<div class="exec-result-data">' + _escapeHtml(JSON.stringify(result, null, 2)) + '</div>';
}

/**
 * 在聊天气泡中内联渲染代码执行结果。
 * 查找气泡中最后一个 <pre> 代码块，在其后插入结果 div。
 *
 * @param {HTMLElement} bubble - 聊天气泡 DOM 元素
 * @param {object} msg - { success, result, stdout, error }
 */
function _injectExecResult(bubble, msg) {
    if (!bubble) return;

    // 找到气泡中最后一个 <pre> 代码块作为插入锚点
    var preEls = bubble.querySelectorAll('pre');
    var anchor = preEls.length > 0
        ? preEls[preEls.length - 1]
        : bubble.querySelector('.chat-msg-body');
    if (!anchor) return;

    // 移除已存在的旧结果
    var existing = bubble.querySelector('.exec-result-inline');
    if (existing) existing.remove();

    var div = document.createElement('div');
    div.className = 'exec-result-inline';

    if (msg.success) {
        var hasResult = msg.result != null;
        var hasStdout = msg.stdout && String(msg.stdout).trim();

        if (hasResult || hasStdout) {
            var html = '';
            if (hasStdout) {
                html += '<div class="exec-label">输出</div>';
                html += '<div class="exec-stdout">' + _escapeHtml(String(msg.stdout)) + '</div>';
            }
            if (hasResult) {
                html += (hasStdout
                    ? '<div class="exec-label" style="margin-top:6px">结果</div>'
                    : '<div class="exec-label">结果</div>');
                html += _formatResult(msg.result);
            }
            div.innerHTML = html;
        } else {
            div.innerHTML = '<span class="exec-no-output">执行成功，无返回值</span>';
        }
    } else if (msg.error) {
        div.innerHTML = '<div class="exec-error">' + _escapeHtml(msg.error) + '</div>';
    } else {
        return;
    }

    // 插入到 anchor 之后
    if (anchor.nextSibling) {
        anchor.parentNode.insertBefore(div, anchor.nextSibling);
    } else {
        anchor.parentNode.appendChild(div);
    }

    scrollToBottom();
}

/**
 * 在聊天气泡中内联渲染 Plotly 图表。
 * 查找 exec-result-inline 或最后一个 <pre> 作为锚点，在其后插入图表容器。
 *
 * @param {HTMLElement} bubble - 聊天气泡 DOM 元素
 * @param {object} chartData - Plotly 图表配置
 */
/**
 * 工作台图表 → 对话区同步。
 * - 若对话区有已有图表（.exec-chart-inline），就地更新最后一个；
 * - 若无已有图表，在对话区追加一条"工作台图表"系统消息。
 */
window.updateChatChartFromWorkspace = function (chartData) {
    if (!chartData || !window.Plotly) return;
    var container = document.getElementById('chat-messages');
    if (!container) return;

    var inlineCharts = container.querySelectorAll('.exec-chart-inline');
    if (inlineCharts.length > 0) {
        // 就地更新最后一个图表
        var lastChart = inlineCharts[inlineCharts.length - 1];
        try {
            var traces = (chartData.data !== undefined) ? (chartData.data || []) : [];
            var layout  = chartData.layout || {};
            Plotly.react(lastChart, traces, layout, { responsive: true });
            scrollToBottom();
        } catch (e) {
            console.error('工作台图表同步到对话失败:', e);
        }
    } else {
        // 无已有图表 → 新建一条系统消息展示工作台图表
        _appendWorkspaceChartMessage(chartData);
    }
};

/**
 * 在对话区追加一条"工作台图表同步"系统消息。
 * @param {object} chartData - Plotly 图表配置
 */
function _appendWorkspaceChartMessage(chartData) {
    var container = document.getElementById('chat-messages');
    if (!container) return;

    var bubble = document.createElement('div');
    bubble.className = 'message assistant';
    bubble.innerHTML =
        '<div class="chat-msg-body">' +
        '<p style="color:var(--cyan);font-size:0.82em;margin-bottom:6px">' +
        '<i class="bi bi-graph-up me-1"></i>工作台图表已同步至对话</p>' +
        '</div>';
    container.appendChild(bubble);
    _injectChart(bubble, chartData);
    scrollToBottom();
}

function _injectChart(bubble, chartData) {
    if (!bubble || !chartData || !window.Plotly) return;

    // 锚点优先选结果区，其次选最后一个代码块
    var anchor = bubble.querySelector('.exec-result-inline');
    if (!anchor) {
        var preEls = bubble.querySelectorAll('pre');
        anchor = preEls.length > 0
            ? preEls[preEls.length - 1]
            : bubble.querySelector('.chat-msg-body');
    }
    if (!anchor) return;

    // 移除已存在的旧图表
    var existing = bubble.querySelector('.exec-chart-inline');
    if (existing) existing.remove();

    var div = document.createElement('div');
    div.className = 'exec-chart-inline';

    if (anchor.nextSibling) {
        anchor.parentNode.insertBefore(div, anchor.nextSibling);
    } else {
        anchor.parentNode.appendChild(div);
    }

    try {
        if (chartData.data && chartData.layout !== undefined) {
            Plotly.newPlot(div, chartData.data, chartData.layout || {}, { responsive: true });
        } else {
            Plotly.newPlot(div, chartData, {}, { responsive: true });
        }
    } catch (e) {
        console.error("图表渲染失败:", e);
    }

    scrollToBottom();
}
