/**
 * DataMind 智能问答组件 — chat.js
 * 来源：学生+AI
 */

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
    const input    = document.getElementById("chat-input");
    const question = (input?.value || "").trim();
    if (!question) return;

    input.value = "";
    appendMessage("user", question);
    setLoading(true);

    // SSE 流式路径（优先）
    if (typeof supportsSSE === 'function' && supportsSSE()) {
        var bubble = appendMessage("assistant", "");
        bubble._fullText = "";
        var codeBlock = null;
        var execResult = null;

        var conn = createSSEConnection('/api/chat', { question: question }, {
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
            onCodeComplete: function (code) {
                var codeEl = document.getElementById("generated-code");
                var pre    = document.getElementById("code-block");
                if (codeEl && pre) {
                    pre.textContent = code;
                    if (window.hljs) hljs.highlightElement(pre);
                    codeEl.style.display = "block";
                }
            },
            onExecResult: function (msg) {
                var resultEl = document.getElementById("exec-result");
                if (!resultEl) return;
                if (msg.success) {
                    resultEl.innerHTML = msg.result != null
                        ? '<pre class="bg-light p-2 rounded small">' + JSON.stringify(msg.result, null, 2) + '</pre>'
                        : '<span class="text-muted small">执行成功，无返回值</span>';
                    resultEl.style.display = "block";
                } else if (msg.error) {
                    resultEl.innerHTML = '<div class="alert alert-danger small py-1">' + msg.error + '</div>';
                    resultEl.style.display = "block";
                }
            },
            onChart: function (chartData) {
                renderExecChart(chartData);
                // 同时推送到图表工作台
                if (typeof renderChart === 'function') {
                    renderChart(chartData);
                }
            },
            onError: function (message) {
                bubble.innerHTML += '<div class="text-danger">错误：' + message + '</div>';
            },
            onDone: function () {
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
    if (data.answer) {
        appendMessage("assistant", data.answer);
    }
    // 生成的代码块
    if (data.code) {
        const codeEl = document.getElementById("generated-code");
        const pre    = document.getElementById("code-block");
        if (codeEl && pre) {
            pre.textContent = data.code;
            if (window.hljs) hljs.highlightElement(pre);
            codeEl.style.display = "block";
        }
    }
    // 执行结果 — 兼容平铺字段（后端实际格式）与 execution 嵌套格式
    const exec = data.execution || (Object.prototype.hasOwnProperty.call(data, "success") ? data : null);
    if (exec) {
        const resultEl = document.getElementById("exec-result");
        if (resultEl) {
            if (exec.success) {
                resultEl.innerHTML = exec.result != null
                    ? `<pre class="bg-light p-2 rounded small">${JSON.stringify(exec.result, null, 2)}</pre>`
                    : "<span class='text-muted small'>执行成功，无返回值</span>";
                resultEl.style.display = "block";
            } else if (exec.error) {
                resultEl.innerHTML = `<div class="alert alert-danger small py-1">${exec.error}</div>`;
                resultEl.style.display = "block";
            }
        }
        // Plotly 图表
        if (exec.chart) {
            renderExecChart(exec.chart);
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
