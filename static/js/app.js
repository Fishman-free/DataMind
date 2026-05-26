/**
 * DataMind 主交互逻辑 — app.js
 * 来源：学生+AI
 */

// ── 初始化入口 ─────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
    // 传统 input[type=file] 点击上传
    const fileInput = document.getElementById("file-upload");
    if (fileInput) {
        fileInput.addEventListener("change", e => {
            const file = e.target.files[0];
            if (file) uploadFile(file);
            e.target.value = "";   // 允许重复上传同一文件
        });
    }

    // 全局拖拽上传
    setupDragDrop();

    // AI 服务配置 Modal
    setupAISettings();
});

// ── 核心上传函数（file input 与拖拽共用） ──────────────────
async function uploadFile(file) {
    const statusEl = document.getElementById("dataset-status");
    if (!statusEl) return;

    // 文件类型预检
    const ext = file.name.split(".").pop().toLowerCase();
    if (!["csv", "xlsx", "json"].includes(ext)) {
        showDropError(`不支持的文件格式：.${ext}（仅接受 CSV / Excel / JSON）`);
        return;
    }

    statusEl.textContent = `上传中: ${file.name}…`;
    statusEl.classList.remove("loaded");

    const formData = new FormData();
    formData.append("file", file);

    try {
        const res  = await fetch("/api/upload", { method: "POST", body: formData });
        const data = await res.json();

        if (res.ok) {
            statusEl.textContent = `已加载: ${file.name}`;
            statusEl.classList.add("loaded");
            updateStatusBar(data.row_count, data.column_count || 0);
            loadInsights();
            fetchQualityScore();
            if (window.initOverviewPage) window.initOverviewPage();
        } else {
            statusEl.textContent = "上传失败";
            showDropError(data.error || "上传失败，请检查文件格式");
        }
    } catch (err) {
        statusEl.textContent = "网络错误";
        console.error(err);
    }
}

// ── 全局拖拽上传 ────────────────────────────────────────────
function setupDragDrop() {
    const overlay = document.getElementById("drag-overlay");
    if (!overlay) return;

    let dragCounter = 0;   // 计数器，解决子元素触发 dragleave 的问题

    // 只对文件类型的拖入显示 overlay
    document.addEventListener("dragenter", e => {
        if (!hasFiles(e)) return;
        e.preventDefault();
        dragCounter++;
        if (dragCounter === 1) {
            overlay.classList.add("active");
        }
    });

    document.addEventListener("dragover", e => {
        if (!hasFiles(e)) return;
        e.preventDefault();
        e.dataTransfer.dropEffect = "copy";
    });

    document.addEventListener("dragleave", e => {
        dragCounter--;
        if (dragCounter <= 0) {
            dragCounter = 0;
            overlay.classList.remove("active");
        }
    });

    document.addEventListener("drop", e => {
        e.preventDefault();
        dragCounter = 0;
        overlay.classList.remove("active");

        const file = e.dataTransfer.files[0];
        if (file) uploadFile(file);
    });
}

// 判断拖入物是否含有文件
function hasFiles(e) {
    if (!e.dataTransfer) return false;
    return Array.from(e.dataTransfer.types).includes("Files");
}

// 在 drag overlay 上短暂显示错误提示
function showDropError(msg) {
    const overlay = document.getElementById("drag-overlay");
    if (!overlay) { alert(msg); return; }

    const tip = overlay.querySelector(".drag-overlay-tip");
    if (tip) {
        tip.textContent = msg;
        tip.style.color = "var(--red, #ff4d6d)";
    }
    overlay.classList.add("active");
    setTimeout(() => {
        overlay.classList.remove("active");
        if (tip) { tip.textContent = "支持 CSV / Excel / JSON，最大 50 MB"; tip.style.color = ""; }
    }, 2200);
}

// ── 状态栏更新 ─────────────────────────────────────────────
function updateStatusBar(rows, cols) {
    const rowEl = document.getElementById("status-rows");
    const colEl = document.getElementById("status-cols");
    if (rowEl) rowEl.innerHTML = `<i class="bi bi-table me-1"></i>${rows.toLocaleString()} 条记录`;
    if (colEl) colEl.innerHTML = `<i class="bi bi-layout-three-columns me-1"></i>${cols} 个字段`;
}

// ── 洞察面板 ───────────────────────────────────────────────
async function loadInsights() {
    try {
        const res = await fetch("/api/insights");
        if (!res.ok) return;
        renderInsights(await res.json());
    } catch (err) {
        console.error("加载洞察失败:", err);
    }
}

function renderInsights(insights) {
    const container = document.getElementById("insight-container");
    if (!container) return;
    if (!insights?.length) {
        container.innerHTML = '<p class="text-muted small">暂未发现显著洞察</p>';
        return;
    }
    container.innerHTML = insights.map(renderInsightCard).join("");
}

function renderInsightCard(insight) {
    const icon = { high: "🔴", medium: "🟠", low: "🔵" }[insight.severity] || "⚪";
    return `
        <div class="insight-card ${insight.severity}">
            <div class="insight-title">${icon} ${insight.title}</div>
            <div class="insight-detail">${insight.detail}</div>
        </div>`;
}

// ════════════════════════════════════════════════════════════
//  AI 服务配置 Modal
// ════════════════════════════════════════════════════════════

/**
 * 服务商图标映射（Bootstrap Icons 类名）
 */
const PROVIDER_ICONS = {
    openai:       "bi-openai",
    deepseek:     "bi-water",
    moonshot:     "bi-moon-stars",
    zhipu:        "bi-diagram-3",
    qwen:         "bi-cloud-lightning",
    siliconflow:  "bi-layers",
    doubao:       "bi-chat-dots",
    ollama:       "bi-box-seam",
    custom:       "bi-wrench-adjustable",
};

function setupAISettings() {
    const backdrop  = document.getElementById("ai-settings-modal");
    const openBtn   = document.getElementById("btn-open-ai-settings");
    const closeBtn  = document.getElementById("btn-close-ai-settings");
    const dot       = document.getElementById("ai-settings-dot");
    if (!backdrop || !openBtn) return;

    // ── 打开 / 关闭 ──────────────────────────────────────
    function openModal()  { backdrop.classList.add("open"); backdrop.removeAttribute("aria-hidden"); }
    function closeModal() { backdrop.classList.remove("open"); backdrop.setAttribute("aria-hidden","true"); }

    openBtn.addEventListener("click", async () => {
        await loadCurrentConfig();
        openModal();
    });
    closeBtn.addEventListener("click", closeModal);
    backdrop.addEventListener("click", e => { if (e.target === backdrop) closeModal(); });
    document.addEventListener("keydown", e => { if (e.key === "Escape") closeModal(); });

    // ── 加载当前配置 ──────────────────────────────────────
    async function loadCurrentConfig() {
        try {
            const res  = await fetch("/api/config/ai");
            const data = await res.json();
            fillForm(data.current);
            buildProviderGrid(data.providers, data.current.base_url);
            refreshDot(data.current.api_key);
        } catch (e) {
            console.warn("无法加载 AI 配置:", e);
        }
    }

    function fillForm(current) {
        document.getElementById("ai-base-url").value = current.base_url || "";
        document.getElementById("ai-api-key").value  = current.api_key  || "";
        document.getElementById("ai-model").value    = current.model    || "";
    }

    // ── 构建服务商卡片 ────────────────────────────────────
    function buildProviderGrid(providers, currentUrl) {
        const grid = document.getElementById("ai-provider-grid");
        if (!grid) return;

        const modelList = document.getElementById("ai-model-list");
        grid.innerHTML  = "";

        Object.entries(providers).forEach(([id, p]) => {
            const card = document.createElement("div");
            card.className = "ai-provider-card";
            card.dataset.providerId = id;

            const iconClass = PROVIDER_ICONS[id] || "bi-cpu";
            const isActive  = p.base_url && p.base_url === currentUrl;
            if (isActive) card.classList.add("active");

            card.innerHTML = `
                <i class="bi ${iconClass} ai-provider-icon"></i>
                <span>${p.name}</span>`;

            card.addEventListener("click", () => {
                // 切换 active 样式
                grid.querySelectorAll(".ai-provider-card").forEach(c => c.classList.remove("active"));
                card.classList.add("active");

                // 填入 base_url
                if (id !== "custom") {
                    document.getElementById("ai-base-url").value = p.base_url;
                } else {
                    document.getElementById("ai-base-url").value = "";
                    document.getElementById("ai-base-url").focus();
                }

                // Ollama：API Key 自动填 "ollama"（任意字符串即可），并显示本地说明框
                const ollamaTips = document.getElementById("ollama-tips");
                if (id === "ollama") {
                    const keyInput = document.getElementById("ai-api-key");
                    if (!keyInput.value) keyInput.value = "ollama";
                    if (ollamaTips) ollamaTips.style.display = "block";
                } else {
                    if (ollamaTips) ollamaTips.style.display = "none";
                }

                // 更新模型建议列表
                if (modelList) {
                    modelList.innerHTML = (p.models || [])
                        .map(m => `<option value="${m}">`)
                        .join("");
                }
                // 自动填入第一个推荐模型
                if (p.models?.length) {
                    document.getElementById("ai-model").value = p.models[0];
                }
            });

            grid.appendChild(card);
        });
    }

    // ── API Key 显示 / 隐藏 ───────────────────────────────
    const keyInput  = document.getElementById("ai-api-key");
    const keyToggle = document.getElementById("ai-key-toggle");
    const keyEye    = document.getElementById("ai-key-eye");
    if (keyToggle) {
        keyToggle.addEventListener("click", () => {
            const isHidden = keyInput.type === "password";
            keyInput.type  = isHidden ? "text" : "password";
            keyEye.className = isHidden ? "bi bi-eye-slash" : "bi bi-eye";
        });
    }

    // ── 测试连接 ──────────────────────────────────────────
    document.getElementById("ai-btn-test")?.addEventListener("click", async () => {
        const payload = getFormPayload();
        if (!payload) return;

        setStatus("info", "正在测试连接……");
        setBtnsDisabled(true);

        try {
            const res  = await fetch("/api/config/ai/test", {
                method:  "POST",
                headers: { "Content-Type": "application/json" },
                body:    JSON.stringify(payload),
            });
            const data = await res.json();
            if (data.status === "ok") {
                setStatus("success", `✓ 连接成功  |  模型: ${data.model}  |  延迟: ${data.latency_ms} ms`);
            } else {
                setStatus("error", `✗ ${data.error}`);
            }
        } catch (e) {
            setStatus("error", `网络错误：${e.message}`);
        } finally {
            setBtnsDisabled(false);
        }
    });

    // ── 保存配置 ──────────────────────────────────────────
    document.getElementById("ai-btn-save")?.addEventListener("click", async () => {
        const payload = getFormPayload();
        if (!payload) return;

        setStatus("info", "正在保存……");
        setBtnsDisabled(true);

        try {
            const res  = await fetch("/api/config/ai", {
                method:  "POST",
                headers: { "Content-Type": "application/json" },
                body:    JSON.stringify(payload),
            });
            const data = await res.json();
            if (res.ok && data.status === "ok") {
                setStatus("success", "✓ 配置已保存，AI 服务已就绪");
                refreshDot(payload.api_key);
                updateAIStatusBar();
            } else {
                setStatus("error", `✗ ${data.error}`);
            }
        } catch (e) {
            setStatus("error", `网络错误：${e.message}`);
        } finally {
            setBtnsDisabled(false);
        }
    });

    // ── 辅助函数 ──────────────────────────────────────────
    function getFormPayload() {
        const api_key  = document.getElementById("ai-api-key")?.value.trim();
        const base_url = document.getElementById("ai-base-url")?.value.trim();
        const model    = document.getElementById("ai-model")?.value.trim();

        if (!api_key)  { setStatus("error", "请填写 API Key"); return null; }
        if (!base_url) { setStatus("error", "请填写 Base URL"); return null; }
        if (!model)    { setStatus("error", "请填写模型名称"); return null; }
        return { api_key, base_url, model };
    }

    function setStatus(type, msg) {
        const el = document.getElementById("ai-status-msg");
        if (!el) return;
        el.className = `ai-status-msg ${type}`;
        el.textContent = msg;
    }

    function setBtnsDisabled(disabled) {
        ["ai-btn-test", "ai-btn-save"].forEach(id => {
            const btn = document.getElementById(id);
            if (btn) btn.disabled = disabled;
        });
    }

    function refreshDot(apiKey) {
        if (!dot) return;
        dot.className = "ai-dot " + (apiKey ? "configured" : "unconfigured");
    }

    function updateAIStatusBar() {
        const el = document.getElementById("status-ai");
        if (el) el.innerHTML = `<i class="bi bi-robot me-1"></i>AI 已配置`;
    }

    // 页面加载时同步一次状态小圆点
    fetch("/api/config/ai")
        .then(r => r.json())
        .then(d => refreshDot(d.current?.api_key))
        .catch(() => {});
}

// ════════════════════════════════════════════════════════════
//  数据质量评分卡
// ════════════════════════════════════════════════════════════

/**
 * 获取并渲染数据质量评分卡。
 */
async function fetchQualityScore() {
    try {
        var resp = await fetch('/api/data/quality');
        if (!resp.ok) return;
        var data = await resp.json();
        renderQualityScore(data);
    } catch (e) {
        // 质量评分获取失败，静默处理
    }
}

/**
 * 渲染质量评分卡 UI。
 * @param {object} data - QualityScorer.score() 返回的数据
 */
function _safePct(v) {
    var n = Number(v);
    if (!Number.isFinite(n)) n = 0;
    n = Math.max(0, Math.min(100, n));
    return n;
}

function renderQualityScore(data) {
    var card = document.getElementById('quality-scorecard');
    if (!card) return;
    card.style.display = 'block';

    // 环形评分
    var score = _safePct(data.total_score);
    document.getElementById('quality-score').textContent = score;
    document.getElementById('quality-grade').textContent = '等级 ' + (data.grade || '--');

    // 环形进度条动画
    var circumference = 2 * Math.PI * 52; // ~327
    var dashOffset = circumference * (1 - score / 100);
    var ring = document.getElementById('quality-ring-fill');
    ring.setAttribute('stroke-dasharray', circumference);
    ring.setAttribute('stroke-dashoffset', dashOffset);

    // 根据等级设置颜色
    var colors = { 'A': '#34D399', 'B': '#4F9FFF', 'C': '#F59E0B', 'D': '#EF4444' };
    ring.setAttribute('stroke', colors[data.grade] || 'var(--blue)');

    // 5 维度柱状条
    var dimsContainer = document.getElementById('quality-dimensions');
    if (dimsContainer && data.dimensions) {
        var html = '';
        var dimNames = {
            'completeness': '完整性', 'uniqueness': '唯一性',
            'consistency': '一致性', 'timeliness': '时效性', 'accuracy': '准确性',
        };
        for (var key in data.dimensions) {
            var dim = data.dimensions[key] || {};
            var name = dimNames[key] || key;
            var dimScore = _safePct(dim.score);
            var barColor = dimScore >= 80 ? 'var(--green)' :
                           dimScore >= 60 ? 'var(--amber)' : 'var(--red)';
            html += '<div class="quality-dim-item">' +
                '<div class="quality-dim-label">' +
                    '<span>' + name + '</span>' +
                    '<span>' + dimScore + '</span>' +
                '</div>' +
                '<div class="quality-dim-bar-bg">' +
                    '<div class="quality-dim-bar-fill" style="width:' + dimScore +
                    '%;background:' + barColor + '"></div>' +
                '</div>' +
            '</div>';
        }
        dimsContainer.innerHTML = html;
    }

    // 改进建议
    var sugContainer = document.getElementById('quality-suggestions');
    if (sugContainer && data.suggestions) {
        sugContainer.innerHTML = data.suggestions.map(function (s) {
            return '<div class="quality-suggestion-item">' +
                '<i class="bi bi-exclamation-triangle me-2" style="color:var(--amber)"></i>' +
                s + '</div>';
        }).join('');
    }
}
