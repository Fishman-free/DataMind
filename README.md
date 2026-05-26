# DataMind — 智能问数平台

> **赛博朋克风格 · 液态玻璃 UI · 自然语言问数 · SSE 流式响应 · 多 Agent 协作 · 零 API 依赖分析**

```
上传数据 → 自动清洗 → 质量评分 → 规则洞察 → 流式问答 → NL2Vis 图表工作台 → 一键报告（简洁/深度/叙事）
```

---

## 为什么选择 DataMind？

| 优势 | 说明 |
|------|------|
| **赛博朋克沉浸式 UI** | 液态玻璃卡片、全息旋转立方体、粒子星场、赛博视频背景，浏览器即震撼 |
| **SSE 流式响应** | 问答和报告均支持 Server-Sent Events 流式推送，消除 30-90s 空白等待，逐 token 实时渲染 |
| **零 API 消耗核心功能** | 数据清洗、统计分析、自动洞察、数据质量评分、可视化仪表盘全部本地运行，不调用任何外部 API |
| **多服务商 AI 接入** | 支持 OpenAI / DeepSeek / Kimi / 智谱 / 通义千问 / 硅基流动 / 豆包及任意兼容 OpenAI 格式的国内中转站，运行时一键切换，无需重启 |
| **优雅降级设计** | 无 API Key 时智能问答/报告自动切换模板模式，NL2Vis 图表/分析计划/数据叙事均内置规则 fallback，核心体验完整 |
| **全格式数据接入** | CSV（自动检测 UTF-8/GBK/Latin1 编码）、Excel、JSON，拖拽即上传 |
| **多轮上下文对话** | ChatSession 维护完整对话历史，支持追问和上下文引用，SSE 流式逐字输出 |
| **安全代码沙箱** | AI 生成的代码在白名单执行环境中运行，禁止 os/sys/subprocess 等危险调用 |
| **NL2Vis 图表工作台** | 自然语言描述图表需求，AI 生成 Plotly 交互图表，支持迭代修改和一键下载 PNG |
| **多 Agent 深度报告** | 4 个专注 Agent（StatisticsAgent / InsightAgent / QAAgent / SynthesisAgent）协作生成 ~3000 字深度分析报告 |
| **数据叙事引擎** | 将结构化报告转化为有起承转合的数据故事，含高亮数字卡片和核心结论 |
| **数据质量评分卡** | 5 维度加权评分（完整性/唯一性/一致性/时效性/准确性），0-100 综合分 + A/B/C/D 等级 |
| **智能分析计划** | AI 分析 Schema 并输出结构化分析清单，用户勾选确认后一键执行 |
| **247 个单元测试** | 11 个测试文件全模块覆盖，全部使用 MagicMock 模拟，不依赖真实 API 环境 |

---

## 技术流 — 核心创新点

DataMind 不仅是功能组合，更在架构设计层面做了多项技术突破。以下按数据流链路逐一拆解。

### 1. POST-body SSE 流式底座

传统 SSE 仅支持 `GET` 请求，无法携带 JSON body。DataMind 自研了基于 `fetch` + `ReadableStream` 的 **POST SSE** 模式：

```
POST /api/chat  {question: "..."}
     │
     ▼
Flask _sse_stream() 生成器 → yield {"type": "...", ...}
     │
     ▼
sse-handler.js  fetch() → response.body.getReader() → 逐 chunk 解析
```

**技术亮点：**

| 能力 | 实现方式 |
|------|---------|
| POST 请求体透传 | `fetch()` 替代 `EventSource`，POST body 携带完整问题上下文 |
| 跨 chunk 缓冲区拼接 | `processChunk()` 逐字节读取 → 按 `\n` 分割 → 未完成行自动保留至下一 chunk 拼接，防止 JSON 截断 |
| 事件路由派发 | `dispatch()` 按 `type` 字段分发 → `text_delta`/`code_complete`/`exec_result`/`chart`/`done`，各 handler 独立注册 |
| 连接生命周期管理 | `AbortController` 精确控制单连接取消，`_sendingLock` 防抖并发发送 |
| 120s 全局超时 | `setTimeout` + `AbortController.abort()`，防止僵尸连接 |
| 优雅降级 | SSE 不可用时自动回退到 `?stream=false` 同步模式 |

**SSE 事件时序（一次完整问答）：**

```
text_delta ×N  →  code_complete  →  heartbeat ×N  →  exec_result  →  chart(可选)  →  done  →  [DONE]
   逐字渲染          代码块出现        执行等待中          执行结果        图表渲染       流结束     流结束字面量
```

> 关键设计：代码执行在 `daemon thread` 中异步进行，主线程以 **1s 间隔轮询** `queue.Queue` 并推送 `heartbeat`，执行完毕后立即推送结果——既保证了流不中断，又避免了长时间阻塞。

### 2. 安全代码沙箱 + Plotly 原生图执行

AI 生成的 Python 代码必须既能安全执行，又能生成交互式图表。DataMind 的沙箱方案解决了「安全」与「能力」的矛盾：

**执行模型：**

```python
namespace = {
    "__builtins__": _SAFE_BUILTINS,  # 白名单内置函数（无 __import__）
    "df": df.copy(),                  # 只读副本
    "pd": pd, "np": np,              # 预加载免 import
    "px": plotly.express,            # Plotly Express API
    "go": plotly.graph_objects,      # Plotly 底层 API
}
exec(code, namespace)                # 受限执行
```

**三层安全防线：**

| 层级 | 机制 | 细节 |
|------|------|------|
| 1. Prompt 约束 | 系统提示词明确「禁止写 import 语句」 | AI 被告知 `px`/`go`/`pd`/`np` 已预加载 |
| 2. 代码净化前先校验 | `validate_code()` 检测 12 个黑名单关键词 **先于** 净化 | `import os` 被阻断 → `success: false`，而非净化后漏过 |
| 3. 全量 import 净化 | 正则 `^\s*(import\|from)\s+...$` 删除所有 import 行 | 防止沙盒中 `import plotly.express` 触发 `__import__ not found` |

**Plotly Figure 自动序列化：**

AI 代码产出 `go.Figure` 对象 → `hasattr(chart, "to_plotly_json")` 检测 → 自动调用 `.to_plotly_json()` 转为 JSON dict → 经 SSE `{"type": "chart"}` 推送前端 → `Plotly.react()` 渲染。整个过程对 AI 透明，无需它手动处理序列化。

### 3. NL2Vis 图表工作台双向状态同步

图表工作台与智能问答之间需要保持图表状态一致。DataMind 设计了一套 **事件驱动的双向同步机制**：

```
┌─────────────────┐         onChart 事件          ┌──────────────────┐
│   智能问答       │ ────── renderChart() ────────→ │  NL2Vis 图表工作台 │
│  (chat.js)      │ ←── updateChatChartFrom      │  (chart-workspace) │
│                 │     Workspace()              │                    │
│  _currentChart  │                              │  _currentChartData │
│  Data/Code 共享  │ ←──── 全局变量共享 ─────────→ │  _currentChartCode │
└─────────────────┘                              └──────────────────┘
```

**同步路径：**

| 方向 | 触发时机 | 机制 |
|------|---------|------|
| Chat → Workspace | SSE `chart` 事件触发 `onChart()` | 1. `renderChart(chartData)` 更新工作台 Plotly<br>2. `_currentChartData = chartData` 写入全局状态<br>3. `#chart-status` 显示「✓ 图表已同步自对话」 |
| Workspace → Chat | 快捷操作触发 `generateChart()` | 1. `window.updateChatChartFromWorkspace(chartData)`<br>2. 查找最后一个 `.exec-chart-inline` 元素<br>3. `Plotly.react()` 就地更新，不新增消息 |

**防抖与竞态保护：**

- `_sendingLock` 布尔锁：上一个请求 SSE 流完成前，禁止发送新消息
- `_activeSSEConnection.abort()`：新消息发送前取消旧连接，防止旧 `onChart` 回调覆盖新状态
- `renderChart()` 内置 `try/catch` + 格式兼容（`{data, layout}` / 裸数组 / 单对象三种格式均兼容）

### 4. 多 Agent 深度报告协作框架

深度报告模式采用 **4 个专业化 Agent 流水线**，每个 Agent 独立调用 LLM 并产出报告章节：

```
report_agents.py
    │
    ├─ StatisticsAgent    (max_tokens: 800)   数据特征统计描述
    ├─ InsightAgent       (max_tokens: 1000)  关键洞察深度解读（HIGH/MEDIUM/LOW 分级）
    ├─ QAAgent            (max_tokens: 700)   对话问答摘要（用户探索路径叙述化）
    └─ SynthesisAgent     (max_tokens: 800)   综合总结 + 3-5 条可执行业务建议
```

**技术特点：**

| 特点 | 说明 |
|------|------|
| 独立 Token 预算 | 每个 Agent 有独立的 `max_tokens`，防止单 Agent 过度消耗影响后续章节质量 |
| SSE 流式进度推送 | `agent_progress` 事件 → 前端渲染 Agent 进度条；`section` 事件 → 前端逐章追加内容 |
| 优雅降级 | 任意 Agent 失败 → `try/except` 捕获 → 自动输出模板占位章节 → 报告始终完整生成 |
| 上下文复用 | StatisticsAgent 的输出作为 InsightAgent 的输入上下文，形成分析管道 |

### 5. 数据叙事引擎 — 华尔街日报体

数据叙事（story mode）不是简单的报告改写，而是遵循新闻写作框架的深度创作：

**写作框架：华尔街日报体（Wall Street Journal Formula）**

```
1. 开篇钩子  →  用一个最震撼的数据发现抓住读者
2. 背景铺垫  →  解释数据来源和整体概况
3. 数据深潜  →  逐层展开关键洞察，每个发现用数据锚定
4. 结论启示  →  提出可执行的建议，呼应开头
```

**技术栈：**

| 环节 | 技术 |
|------|------|
| Prompt 工程 | 资深数据新闻记者人设 + 叙事弧线约束 + 每章 `body ≥ 3 句` + `highlight` 必填 |
| 输入优化 | 洞察→紧凑格式提取 `{title, detail, type, severity}`，数据截断从 1000 → 2000 字符，chat_history 10 轮 |
| 输出约束 | `max_tokens: 3000`（vs 旧版 1000），`temperature: 0.7` 增加创作多样性 |
| JSON 解析 | `_parse_json()` 容错解析（支持 tailing comma / 非标准引号），失败 → fallback |
| Fallback | 规则引擎从洞察中提取 `detail/title` → 组装叙事章节 + 核心结论 → 保证永远有输出 |

### 6. 零 API 依赖的质量评分卡

数据质量评分卡是纯本地计算的高阶分析能力：

```
5 维度加权评分模型：

完整性 (30%)    重复率 → 线性扣分
唯一性 (20%)    缺失率 → 加权累扣
一致性 (15%)    IQR 异常率 → 比例扣分
时效性 (15%)    最新日期距今 >7d/30d/90d → 逐级扣分
准确性 (20%)    类型转换失败 → 固定扣分
        │
        ▼
    综合分 (0-100) + A/B/C/D 等级 + 改进建议列表
```

**前端渲染：** SVG 环形仪表盘 + 5 维度柱状进度条 + 改进建议列表，全部本地运算，不消耗任何 API 额度。

### 7. 优雅降级 — 全功能无 Key 可用

每个依赖 AI 的功能都有独立的规则引擎 fallback：

| 功能 | AI 路径 | Fallback 路径 |
|------|---------|:---:|
| 智能问答 | GPT 流式生成代码 + 执行 | 不支持（需 API Key） |
| 分析报告（简洁） | GPT 润色 Markdown | 内置模板 + 数据占位替换 |
| 分析报告（深度） | 4 Agent 协作生成 | 每个 Agent 失败后独立降级 |
| NL2Vis 图表 | AI 生成 Plotly 代码 | 无 Key 隐藏入口 |
| 分析计划 | AI 分析 Schema | 规则引擎：日期列 → 趋势、数值列≥2 → 相关、有缺失 → 质量 |
| 数据叙事 | AI 新闻体创作 | 洞察 → 叙事骨架组装 |
| 数据质量评分 | — | 始终零 API 依赖 |

> 核心设计哲学：**「AI enhanced, not AI dependent」**——AI 是提升体验的加速器，不是系统的单点故障源。

### 8. 全数据集自适应引擎 — DataProfiler + 智能路由

DataMind 能识别 **6 种数据画像**，并为每种类型自动选择最合适的分析路径：

| 画像 | 识别规则 | 自适应内容 |
|------|---------|-----------|
| 零售型 (`retail`) | 含日期 + 客户 + 商品/金额列 | 月度趋势、Top 商品、RFM 分析、国家分布 |
| 时序型 (`temporal`) | 含日期列 + 数值列 | 时间趋势折线、数值分布、相关矩阵 |
| 数值型 (`numeric`) | 数值列 ≥ 4，分类列 ≤ 2 | 分布直方图、散点对、箱线图、相关矩阵 |
| 分类型 (`categorical`) | 分类列 ≥ 3 | 多列频次柱状图、交叉分析 |
| 地理型 (`geographic`) | 含国家/城市/省份列 | 地区分布、数值对比 |
| 混合型 (`mixed`) | 其余 | 通用图表组合 |

**自适应路由体现在 3 处：**
1. **快捷提问按钮** — 基于画像生成 4 条专属问题（而非固定模板）
2. **自适应仪表盘** — 6 个图表按画像动态切换；纯分类数据无数值列时全部替换为频次图
3. **系统提示词** — AI 获取当前数据集的精确列名和样本值，宽数据集（>25 列）自动截断防超限

**通用性保障：**
- 任意类型数据进入系统后，质量评分卡、智能问答、可视化仪表盘、报告、叙事功能均可正常使用
- 纯分类数据（无数值列）不会出现空白图表卡片，自动切换为类别频次柱状图
- 宽列数据集（100+ 列）系统提示词展示前 25 列 + 说明总数，避免 token 超限

---

### 9. SSE 前端工程化 — `sse-handler.js`

不依赖第三方库，约 200 行纯 JavaScript 实现的 SSE 客户端基础设施：

```javascript
createSSEConnection({ url, body, handlers, onError })
    │
    ├─ fetch(url, { method: 'POST', body: JSON.stringify(body), signal })
    ├─ reader.read() 递归泵 → processChunk(buffer + chunk)
    │   ├─ 按 \n 分割 → 逐行处理
    │   ├─ 行首 data: 检测 → JSON.parse → dispatch()
    │   ├─ [DONE] 字面量检测 → handlers.onDone()
    │   └─ 未完成行 → 保留到 buffer，等下一 chunk 拼接
    └─ 错误处理：AbortError → 静默 / 网络错误 → onError()
```

**关键设计决策：**

- **递归 `pump()` 而非 `while(true)`**：每次 `reader.read()` 返回后递归调用，保证微任务队列不阻塞 UI 渲染
- **Buffer 残留机制**：`JSON.parse` 失败的行 → 回退到 buffer → 下一 chunk 拼接后重试，解决大数据包跨 chunk 问题
- **事件驱动**：`dispatch()` 通过 `handlers[msg.type]` 回调路由，调用方无需关心 SSE 协议细节

---

## 目录

1. [技术流 — 核心创新点](#技术流--核心创新点)
1. [界面预览](#1-界面预览)
2. [功能概览](#2-功能概览)
3. [目录结构](#3-目录结构)
4. [环境准备](#4-环境准备)
5. [快速启动](#5-快速启动)
6. [使用说明](#6-使用说明)
   - [6.1 上传数据](#61-上传数据)
   - [6.2 数据概览页](#62-数据概览页)
   - [6.3 智能问答页（SSE 流式）](#63-智能问答页sse-流式)
   - [6.4 NL2Vis 图表工作台](#64-nl2vis-图表工作台)
   - [6.5 可视化仪表盘](#65-可视化仪表盘)
   - [6.6 分析报告页](#66-分析报告页)
   - [6.7 智能分析计划](#67-智能分析计划)
   - [6.8 数据质量评分卡](#68-数据质量评分卡)
   - [6.9 数据叙事引擎](#69-数据叙事引擎)
   - [6.10 右侧自动洞察面板](#610-右侧自动洞察面板)
7. [API 接口参考](#7-api-接口参考)
8. [配置说明](#8-配置说明)
9. [测试说明](#9-测试说明)
10. [版本历史](#10-版本历史)
11. [常见问题](#11-常见问题)
12. [技术架构](#12-技术架构)

---

## 1. 界面预览

### 视觉设计亮点

- **背景层**：粒子星场（80 颗星尘 + 径向渐变光晕）+ 脉冲同心环 + 电路网格 + 全息旋转 3D 线框立方体
- **赛博视频**：机械女孩 MP4 作为全屏背景，`mix-blend-mode: screen` 令暗色背景消融，人物以全息投影形式浮现
- **液态玻璃卡片**：`backdrop-filter: blur()` + `::before` 渐变遮罩边框，纯 CSS 实现
- **字体系统**：Instrument Serif（标题衬线）+ Barlow（正文）+ JetBrains Mono（代码）
- **配色**：纯黑 `#000` 底 + 电蓝 `#4D8AFF` / 青色 `#00E5FF` / 紫色 `#9B59FF` 三色高亮
- **拖拽上传遮罩**：全局拖拽监听，动态虚线边框动画，计数器防子元素误触发

---

## 2. 功能概览

| 功能模块 | 说明 | 需要 API Key |
|----------|------|:------------:|
| 数据上传（点击/拖拽） | CSV / Excel / JSON，自动检测编码，50 MB 限制 | 否 |
| 自动数据清洗（增强版） | 去重→**文本清洗**→**智能缺失值填充**→类型转换→无效过滤→**两档 IQR 异常标记**→特征工程 | 否 |
| 数据质量评分卡 🆕 | 5 维度加权评分（完整性 30%/唯一性 20%/一致性 15%/时效性 15%/准确性 20%），0-100 分 + A/B/C/D 等级 | 否 |
| 数据概览页 | 统计卡片 + 预处理摘要 + 前 50 行预览表格 | 否 |
| 自动洞察面板 | 趋势/异常/分布/相关/周期 5 类洞察，实时推送 | 否 |
| 可视化仪表盘 | 6 个 Plotly 交互图表 | 否 |
| 智能问答（多轮） 🆕 | 自然语言 → AI 流式生成代码 → 沙箱执行 → 文字 + 图表，SSE 逐 token 推送 | **是** |
| NL2Vis 图表工作台 🆕 | 自然语言描述 → Plotly 交互图表，支持迭代修改、复制代码、下载 PNG | 是（降级可用） |
| 智能分析计划 🆕 | AI 分析 Schema → 结构化分析清单，勾选确认后一键执行 | 是（降级可用） |
| 分析报告（简洁模式） | GPT 润色的结构化 Markdown 报告（含降级模板） | 是（降级可用） |
| 分析报告（深度模式） | 4 Agent 协作：数据统计 + 洞察解读 + 对话摘要 + 综合建议，~3000 字深度报告，SSE 流式推送 | 是（降级可用） |
| 数据叙事引擎 🆕 | 将报告转化为数据故事：故事标题 + 摘要 + 叙事段落（含高亮数字卡片） + 核心结论 | 是（降级可用） |

---

## 3. 目录结构

```
DataMind/
├── app.py                    # Flask 入口，注册蓝图，维护全局 app_state（含 quality_score）
├── config.py                 # 配置（API Key、端口、文件大小限制等）
├── requirements.txt          # Python 依赖清单
├── README.md                 # 本文档
│
├── data/                     # 数据层
│   ├── loader.py             # 读取 CSV / Excel / JSON，自动检测编码
│   ├── preprocessor.py       # Pipeline 清洗（5 步骤 + 特征工程）
│   ├── analyzer.py           # 统计分析（趋势/商品/RFM/相关/时段/国家）
│   ├── detector.py           # 异常检测（IQR / Z-Score / 趋势突变）
│   └── quality_scorer.py     # 🆕 数据质量评分卡（5 维度加权评分）
│
├── ai/                       # AI 智能体层
│   ├── chat.py               # 多轮对话管理（ChatSession），SSE 流式支持
│   ├── code_generator.py     # 自然语言 → Pandas 代码，安全沙箱执行
│   ├── insight.py            # 规则引擎自动洞察（零 API 依赖）
│   ├── report.py             # GPT 润色分析报告，Markdown → HTML，SSE 流式支持
│   ├── report_agents.py      # 多 Agent 框架（StatisticsAgent/InsightAgent/QAAgent/SynthesisAgent）
│   ├── chart_generator.py    # 🆕 NL2Vis 自然语言图表生成器
│   ├── plan_generator.py     # 🆕 智能分析计划生成器
│   └── storyteller.py        # 🆕 数据叙事引擎
│
├── routes/                   # Flask 路由层
│   ├── pages.py              # 页面路由（/, /analysis, /visualization, /report）
│   └── api.py                # REST API（/api/*，共 14 个端点），含 SSE 流式基础组件
│
├── templates/                # Jinja2 HTML 模板
│   ├── base.html             # 三栏布局基模板（含全部背景特效 DOM + SSE handler 引用）
│   ├── index.html            # 数据概览页（含质量评分卡 UI）
│   ├── analysis.html         # 智能问答页（两栏布局：对话 + 图表工作台）
│   ├── visualization.html    # 可视化仪表盘
│   └── report.html           # 分析报告页（含简洁/深度/叙事三模式 + SSE 流式渲染）
│
├── static/
│   ├── css/style.css         # 全量设计系统（含图表工作台/SSE 动画/质量评分卡样式）
│   ├── js/
│   │   ├── app.js            # 文件上传 + 拖拽 + 状态栏 + 洞察面板 + 质量评分渲染
│   │   ├── bg-effects.js     # 粒子星场 Canvas 动画
│   │   ├── chat.js           # 问答 UI（含 SSE 流式接收与渲染）
│   │   ├── charts.js         # 6 个 Plotly 图表渲染
│   │   ├── insights.js       # 洞察卡片渲染
│   │   ├── sse-handler.js    # 🆕 SSE 流式通用处理组件（fetch + ReadableStream）
│   │   └── chart-workspace.js # 🆕 NL2Vis 图表工作台（Plotly.react 渲染 + 快捷操作）
│   └── videos/
│       └── mech-girl.mp4     # 赛博朋克背景视频
│
├── datasets/                 # 上传文件保存目录
│
└── tests/                    # 单元测试（247 个用例，11 个测试文件，全 Mock）
    ├── test_loader.py
    ├── test_preprocessor.py
    ├── test_analyzer.py
    ├── test_detector.py
    ├── test_chat.py
    ├── test_code_generator.py
    ├── test_insight.py
    ├── test_report.py
    ├── test_report_agents.py
    ├── test_chart_generator.py  # 🆕
    ├── test_plan_generator.py   # 🆕
    ├── test_storyteller.py      # 🆕
    ├── test_quality_scorer.py   # 🆕
    └── test_api.py
```

---

## 4. 环境准备

### 4.1 Python 版本要求

```bash
# 要求 Python 3.10+，推荐 3.11
python --version
```

### 4.2 安装依赖

```bash
# 从 GitHub 克隆后，进入项目目录
cd DataMind
pip install -r requirements.txt
```

| 包 | 版本要求 | 用途 |
|----|---------|------|
| flask | ≥ 3.0 | Web 框架 |
| pandas | ≥ 2.0 | 数据处理核心 |
| numpy | ≥ 1.24 | 数值计算 |
| openai | ≥ 1.0 | 智能问答 + 报告生成 |
| plotly | ≥ 5.0 | 交互式图表（后端 JSON 序列化） |
| chardet | ≥ 5.0 | CSV 编码自动检测 |
| openpyxl | ≥ 3.1 | Excel 文件读写 |
| markdown | ≥ 3.5 | 报告 Markdown → HTML 转换 |
| pytest | ≥ 7.0 | 单元测试框架 |

### 4.3 配置 AI 服务（可选）

DataMind 支持任意兼容 **OpenAI Chat Completions API** 格式的服务商，包括国内中转站。

**不配置 API Key 时**，以下功能依然 100% 可用：
- 数据上传与自动清洗
- 数据概览（统计卡片 + 预处理摘要 + 数据预览）
- 自动洞察面板（全 5 类洞察）
- 可视化仪表盘（全 6 个图表）
- 分析报告（降级为内置模板版本）

**需要 API Key** 的功能：
- 智能问答（自然语言 → 代码 → 图表）
- GPT/大模型润色版分析报告

#### 方式一：界面配置（推荐，无需重启）

启动应用后，点击顶栏右侧 **⚙ CPU 图标** 打开 AI 服务配置面板：

1. 点击服务商卡片（OpenAI / DeepSeek / Kimi / 智谱 / 通义千问 / 硅基流动 / 豆包 / 自定义）
2. 填入对应的 API Key
3. 确认 Base URL 和模型名称
4. 点击「测试连接」验证
5. 点击「保存配置」即时生效

#### 方式二：环境变量（服务器部署推荐）

```bash
# Windows PowerShell
$env:AI_API_KEY  = "sk-..."
$env:AI_BASE_URL = "https://api.openai.com/v1"   # 或其他服务商地址
$env:AI_MODEL    = "gpt-4o-mini"

# macOS / Linux
export AI_API_KEY="sk-..."
export AI_BASE_URL="https://api.openai.com/v1"
export AI_MODEL="gpt-4o-mini"
```

#### 方式三：直接修改 `config.py`（仅限本地开发）

```python
AI_API_KEY  = "sk-..."
AI_BASE_URL = "https://api.openai.com/v1"
AI_MODEL    = "gpt-4o-mini"
```

#### 支持的服务商一览

| 服务商 | Base URL | 推荐模型 |
|--------|---------|---------|
| OpenAI | `https://api.openai.com/v1` | `gpt-4o-mini` |
| DeepSeek | `https://api.deepseek.com/v1` | `deepseek-chat` |
| Moonshot / Kimi | `https://api.moonshot.cn/v1` | `moonshot-v1-32k` |
| 智谱 GLM | `https://open.bigmodel.cn/api/paas/v4` | `glm-4-flash` |
| 通义千问 | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-plus` |
| 硅基流动 | `https://api.siliconflow.cn/v1` | `deepseek-ai/DeepSeek-V3` |
| 字节豆包 | `https://ark.cn-beijing.volces.com/api/v3` | `doubao-pro-32k` |
| **Ollama（本地免费）** | `http://localhost:11434/v1` | `qwen3:8b` |
| 自定义中转站 | 填写你的中转地址 | 按服务商支持填写 |

---

#### 方式四：Ollama 本地免费部署（无需 API Key，数据不出本机）

Ollama 允许在本机运行开源大模型，完全免费、无需联网、无需注册账号。

**前提条件**

1. 已安装 Ollama（[官网下载](https://ollama.com/download)，Windows/macOS/Linux 均支持）
2. 已拉取模型（在命令提示符/终端执行）：

```bash
ollama pull qwen3:8b     # 推荐，约 5 GB，16 GB 内存可用
ollama pull qwen3:4b     # 轻量版，约 2.6 GB，8 GB 内存可用
ollama pull qwen2.5:7b   # 备选，中文支持同样出色
```

**在 DataMind 中配置**

1. 启动 DataMind：`python app.py`
2. 点击顶栏 **⚙ 图标** 打开 AI 配置面板
3. 点击服务商卡片「**Ollama（本地免费）**」
4. Base URL 和 API Key 会**自动填入**（`http://localhost:11434/v1` 和 `ollama`），无需手动修改
5. 确认模型名与你拉取的一致（默认 `qwen3:8b`）
6. 点击「**测试连接**」，显示绿色"连接成功"后点「**保存配置**」

**验证 Ollama 服务正在运行**

```bash
# 查看已下载的模型列表
ollama list

# 若连接测试失败，手动启动服务
ollama serve
```

**已测试可用的 Qwen 模型**

| 模型 | 拉取命令 | 内存需求 | 特点 |
|------|---------|---------|------|
| `qwen3:4b` | `ollama pull qwen3:4b` | 8 GB | 轻量快速 |
| `qwen3:8b` | `ollama pull qwen3:8b` | 16 GB | 推荐，质量均衡 |
| `qwen3:14b` | `ollama pull qwen3:14b` | 32 GB | 更强推理 |
| `qwen2.5:7b` | `ollama pull qwen2.5:7b` | 16 GB | 上一代，稳定 |

> **注意**：Ollama 本地模型响应速度取决于硬件。有 NVIDIA GPU 时自动加速；纯 CPU 运行时，qwen3:8b 每次回答约需 15-60 秒。

---

## 5. 快速启动

```bash
# 从 GitHub 克隆后进入项目目录（如果已经在目录内则跳过）
cd DataMind
python app.py
```

控制台输出：

```
 * Running on http://0.0.0.0:5000
 * Debug mode: on
```

打开浏览器访问：**http://localhost:5000**

> 首次访问会加载 Google Fonts CDN（Instrument Serif / Barlow / JetBrains Mono），国内网络可能需要数秒。若字体加载慢，可将 `base.html` 中 Google Fonts `<link>` 替换为本地字体文件。

---

## 6. 使用说明

### 6.1 上传数据

**方式一：点击上传**

顶部导航栏点击「上传数据」按钮，选择文件（支持 CSV / Excel / JSON）。

**方式二：拖拽上传**

将文件直接拖入浏览器窗口任意位置，松开即上传。页面会显示全屏蓝色遮罩提示。

| 格式 | 编码支持 | 备注 |
|------|---------|------|
| CSV | UTF-8 / GBK / Latin1（自动检测） | 任意分隔符 |
| Excel (.xlsx) | — | 默认读取第一个 Sheet |
| JSON | records 格式 / columns 格式 | — |

文件大小上限：**50 MB**（可在 `config.py` 修改 `MAX_FILE_SIZE`）

上传成功后：
- 顶栏状态变为「已加载: 文件名」（青色高亮）
- 底部状态栏显示「X 条记录  Y 个字段」
- 右侧洞察面板自动填充 5 类分析结果
- 若当前在概览页，数据卡片自动刷新

---

### 6.2 数据概览页（`/`）

上传成功后展示四部分内容：

**① 数据质量评分卡 🆕**

零 API 消耗的自动质量评估：SVG 环形评分仪表盘（0-100 分 + A/B/C/D 等级）+ 5 维度柱状条 + 改进建议列表。详见 [6.8 数据质量评分卡](#68-数据质量评分卡)。

**② 统计卡片**

| 卡片 | 说明 |
|------|------|
| 总记录数 | 清洗后的有效行数 |
| 字段数 | 数据集列数 |
| 时间跨度 | 自动识别日期列的起止时间（无日期列显示 `—`） |
| 总销售额 | 自动识别金额列求和（无金额列显示 `—`） |

**③ 预处理摘要**

系统对数据执行 5 步 Pipeline 清洗，并逐步骤展示报告：

数据概览页展示 **7 步链式预处理 Pipeline** 的执行结果（可视化流程图，带实时统计）：

| 步骤 | 方法 | 内容 |
|------|------|------|
| **01 去重** | `drop_duplicates()` | 全行精确匹配去重，显示移除数量 |
| **02 文本清洗** | `.str.strip()` + 正则 | 去除所有文本列首尾空白符和 ASCII 控制字符（0x00–0x1f/0x7f） |
| **03 缺失值处理** | 偏态感知填充 | 数值列：`\|skew\| > 1.0` → 中位数，否则 → 均值；文本列：低基数（唯一值 ≤ 10，唯一率 ≤ 50%）→ 众数，否则 → "Unknown" |
| **04 类型转换** | 启发式检测 | 字符串 → datetime（前20行成功率 >70%）→ numeric → category（低基数列自动分类化） |
| **05 无效过滤** | 业务规则 | 删除 Quantity ≤ 0（退货/取消）或 UnitPrice < 0（错误定价）的行，跳过无相关列的数据集 |
| **06 异常标记** | 双档 IQR 法 | 轻度（×1.5）→ `_is_outlier`；极端（×3.0）→ `_is_extreme_outlier`，仅标记不删除，供下游决策 |
| **07 特征工程** | 派生特征 | 检测到日期列 → 生成 Year / Month / DayOfWeek / Hour；检测到数量+单价列 → 生成 TotalAmount |

> **Pipeline 实现**：`data/preprocessor.py` — `Preprocessor` 类，链式调用 `remove_duplicates().clean_text().handle_missing().convert_types().filter_invalid_records().filter_outliers().add_features()`

**④ 数据预览**

展示前 50 行数据的可横向滚动表格。

---

### 6.3 智能问答页（SSE 流式）（`/analysis`）

> 此功能需要配置 AI API Key

**操作步骤：**

1. 先上传数据文件
2. 在输入框用自然语言提问，按回车或点击「发送」
3. AI 以 **SSE 流式**逐 token 推送回答，实时渲染文字 + 代码 + 执行结果 + 图表

**SSE 流式体验：**
- 文字逐字出现在页面上，无需等待完整回答
- 代码生成完毕后自动执行，结果即时推送
- 若浏览器不支持 SSE，自动降级为同步模式

**示例问题（以 Online Retail 电商数据集为例）：**

```
月均销售额是多少？
Top 10 畅销商品有哪些，按销售额排序？
UK 客户的平均消费金额是多少？
画一个每月销售趋势的折线图
2011年11月销售额相比10月增长了多少百分比？
哪个国家的客户最多？
```

**多轮对话示例（支持上下文追问）：**

```
用户: Top 10 畅销商品是哪些？
AI:   （返回商品排名表）
用户: 这 10 个商品中，来自 UK 的销售额占比是多少？
AI:   （基于上文继续分析，无需重复指定数据集）
用户: 画个饼图展示一下
AI:   （生成并执行绘图代码，渲染 Plotly 交互图）
```

**界面元素说明：**

| 元素 | 功能 |
|------|------|
| 快捷提问按钮 | 预设 4 个常见问题，点击自动发送 |
| 发送按钮 | 提交问题（回车键等效） |
| 垃圾桶按钮 | 清空对话历史（不影响已上传数据集） |
| 「生成代码」区域 | 展示 AI 生成的 Python 代码，带语法高亮，支持一键复制 |
| 执行结果区域 | 展示代码运行的文字输出 |
| 动态图表区域 | Plotly 交互图表（可缩放/平移/下载） |

---

### 6.4 NL2Vis 图表工作台（`/analysis` 右侧面板）

> 此功能需要配置 AI API Key（无 Key 时隐藏入口）

用自然语言描述图表需求，AI 自动生成 Plotly 交互图表。位于智能问答页右侧，与对话区域形成两栏布局。

**操作步骤：**

1. 在图表工作台顶部的输入框用自然语言描述想要的图表
2. AI 生成并执行绘图代码，左侧自动渲染 Plotly 交互图表
3. 右侧展示 AI 解读文字 + 复制代码按钮 + 下载 PNG 按钮

**支持的图表类型：**

散点图、折线图、柱状图、饼图、面积图、热力图、箱线图、散点矩阵、桑基图、漏斗图、仪表盘、气泡图

**快捷操作按钮：**

| 按钮 | 预设指令 |
|------|---------|
| 改折线图 | 自动将当前图表转为折线图 |
| 按季度聚合 | 将月度数据合并为季度 |
| 只看 Top 5 | 过滤仅展示前 5 条数据 |
| 深色/浅色 | 切换图表主题 |

> 快捷操作本质是预设自然语言指令，点击后自动填入输入框并触发重新生成。

**迭代修改：** 生成图表后可在输入框中继续描述修改需求（如"把柱状图改成横向的""只显示 UK 的数据"），AI 会基于前一个图表进行修改。

---

### 6.5 可视化仪表盘（`/visualization`）

6 个预置 Plotly 交互图表，上传数据后自动加载：

| 图表 | 类型 | 内容 |
|------|------|------|
| 月度销售趋势 | 折线图 | 按月聚合的销售额变化曲线 |
| Top 10 畅销商品 | 横向柱状图 | 按销售额排序的前 10 名商品 |
| 国家销售分布 | 环形饼图 | 各国家/地区的销售额占比 |
| 相关性矩阵 | 热力图 | 数值列两两相关系数（-1 ～ 1） |
| 订单时间规律 | 柱状图 | 按星期几的订单量分布 |
| RFM 客户散点图 | 散点图 | 频次 × 金额，点颜色表示最近购买天数 |

**Plotly 图表交互操作：**

| 操作 | 方法 |
|------|------|
| 区域缩放 | 鼠标框选图表中的区域 |
| 平移 | 按住左键拖动 |
| 数据悬停提示 | 鼠标悬停在数据点/柱/扇形上 |
| 保存为图片 | 点击图表右上角相机图标（PNG 格式） |
| 重置视图 | 双击图表空白区域 |
| 显示/隐藏系列 | 点击图例中的对应项 |

---

### 6.6 分析报告页（`/report`）

页面顶部提供**报告模式切换**，选择后点击「生成分析报告」。深度模式下报告以 **SSE 流式**生成，逐个 Agent 推送进度和内容。

#### 简洁报告模式（默认）

适合快速查阅，约 10-30 秒生成：

**有 API Key**：GPT 将数据摘要、洞察结果、对话历史整合为结构化 Markdown 报告

**无 API Key（降级模式）**：系统使用内置模板立即生成基础报告（约 1 秒）

**报告结构：**

```markdown
# DataMind 数据分析报告
## 数据概览  |  ## 关键发现  |  ## 总结与建议
```

#### 深度报告模式（多 Agent 协作 + SSE 流式）

适合深入分析，生成 ~3000 字专业报告，SSE 流式推送约 30-90 秒：

**SSE 流式体验：**
- 报告生成开始 → 推送 `report_start` 事件
- 每个 Agent 启动 → 推送 `agent_progress` 事件（前端显示 Agent 进度条）
- 每个 Agent 完成 → 推送 `section` 事件（前端逐章渲染）
- 全部完成 → 推送 `report_done` 事件

**4 Agent 协作框架：**

| Agent | 职责 | Token 预算 |
|-------|------|:----------:|
| **StatisticsAgent** | 数据特征统计描述（字段类型、分布、偏态、数值范围） | 800 |
| **InsightAgent** | 关键洞察深度解读（HIGH/MEDIUM/LOW 分级，业务影响分析） | 1000 |
| **QAAgent** | 对话问答摘要（用户探索路径、AI 关键发现叙述化提炼） | 700 |
| **SynthesisAgent** | 综合总结与建议（执行摘要 + 3-5 条可执行业务建议） | 800 |

**报告结构：**

```markdown
# DataMind 深度数据分析报告
## 数据特征描述   ← StatisticsAgent
## 关键洞察       ← InsightAgent
## 对话分析摘要   ← QAAgent
## 总结与建议     ← SynthesisAgent
```

> 任意 Agent 失败时自动降级为模板输出，保证报告始终可生成。

#### 🆕 叙事模式（数据故事）

将结构化报告转化为有起承转合的数据故事（详见 [6.9 数据叙事引擎](#69-数据叙事引擎)）。

点击「下载 Markdown」将报告保存为 `.md` 文件到本地。

---

### 6.7 智能分析计划

> 此功能需要配置 AI API Key（无 Key 时使用规则引擎自动生成基础计划）

上传数据后，AI 分析数据 Schema 并输出结构化分析清单：

**操作步骤：**

1. 上传数据文件后，系统自动触发分析计划生成
2. 报告页顶部展示分析计划 Todo-list，每条含标题、分类和描述
3. 勾选需要执行的分析项（支持全选/取消全选）
4. 点击「执行选中」逐个运行分析，每个完成后推送结果

**降级方案：** 无 API Key 时，基于数据特征自动生成至少 3 条基础计划：
- 有日期列 → 趋势分析
- 数值列 ≥ 2 → 相关性分析
- 有缺失值 → 数据质量排查

---

### 6.8 数据质量评分卡

> 零 API 消耗，纯本地计算

上传数据后自动给出 0-100 的综合质量分，展示在数据概览页统计卡片下方。

**5 维度评分规则：**

| 维度 | 权重 | 满分条件 | 扣分规则 |
|------|:---:|------|------|
| 完整性 | 30% | 所有列缺失率为 0 | 各列缺失率 × 权重累扣 |
| 唯一性 | 20% | 无重复行 | 重复率 × 权重扣分 |
| 一致性 | 15% | 数值列无异常值 | 异常率 × 权重扣分 |
| 时效性 | 15% | 最新日期在 7 天内 | 距今 >7d/30d/90d 逐级扣分 |
| 准确性 | 20% | 类型转换全部正常 | 每列类型转换失败扣 5 分 |

**等级映射：** A (90-100) / B (75-89) / C (60-74) / D (<60)

**前端展示：**
- SVG 环形评分仪表盘（0-100 分 + A/B/C/D 等级）
- 5 维度柱状进度条（各项得分可视化）
- 改进建议列表（根据扣分项生成）

---

### 6.9 数据叙事引擎

> 此功能需要配置 AI API Key（无 Key 时基于洞察结果生成基础叙事）

将结构化分析报告转化为有起承转合的数据故事，而非信息罗列。

**操作步骤：**

1. 在报告页切换到「叙事」模式
2. 点击「生成分析报告」
3. AI 以数据新闻风格生成故事体报告

**展示格式：**

| 元素 | 说明 |
|------|------|
| 故事大标题 | 生动有力的主标题，概括数据核心发现 |
| 一句话摘要 | 用一句话讲述数据中最重要的事 |
| 叙事段落 | 自然段落形式的分析叙述，关键数字以高亮卡片展示 |
| 核心结论 | 3-5 条精炼的结论列表 |

**降级方案：** 无 API Key 时，基于规则引擎洞察结果自动组装为基础叙事体，保证始终可输出。

---

### 6.10 右侧自动洞察面板

每次成功上传数据后，右侧面板自动刷新，显示 5 类规则引擎洞察（**零 API 消耗**）：

| 类型 | 严重度标签 | 检测逻辑 | 示例 |
|------|-----------|---------|------|
| 趋势洞察 | 🔴 高 | 相邻月份销售额环比变化 > 20% | 「2011年11月销售额环比增长 47%」 |
| 异常洞察 | 🔴 高 | IQR 法检测数值列极端值 | 「Quantity 列检测到 23 个异常值（2.1%）」 |
| 分布洞察 | 🟠 中 | 类别列某一值占比 > 60% | 「82% 的订单来自 United Kingdom」 |
| 相关洞察 | 🔵 低 | 数值列两两 Pearson 相关系数 > 0.7 | 「Quantity 与 TotalAmount 强正相关（0.89）」 |
| 周期洞察 | 🔵 低 | 按星期统计订单量找峰值 | 「周四是一周中订单量最高的一天」 |

---

## 7. API 接口参考

所有接口均以 `/api` 为前缀，返回 JSON。

### GET /api/ping

```json
{"status": "ok", "message": "DataMind API is running"}
```

---

### POST /api/upload

**请求**：`multipart/form-data`，字段名 `file`

**响应（成功 200）**：
```json
{
  "status": "ok",
  "filename": "online_retail.csv",
  "row_count": 406829,
  "clean_rows": 397924,
  "column_count": 9
}
```

**响应（失败 400）**：
```json
{"error": "不支持的文件格式"}
```

---

### GET /api/data/summary

```json
{
  "row_count": 397924,
  "column_count": 9,
  "date_range": {"start": "2010-12-01", "end": "2011-12-09"},
  "numeric_stats": {
    "Quantity": {"mean": 12.06, "std": 248.69, "min": 1, "max": 80995},
    "UnitPrice": {"mean": 3.46, "std": 69.32, "min": 0.001, "max": 38970}
  }
}
```

---

### GET /api/data/preview?n=100

返回前 N 行记录列表（默认 100，最大 500）。

---

### GET /api/data/preprocess-report

```json
{
  "original_rows": 541909,
  "final_rows": 397924,
  "remove_duplicates": {"removed": 5268},
  "fill_missing": {"filled_columns": ["CustomerID"], "dropped_columns": []},
  "type_conversion": {"converted": ["InvoiceDate"]},
  "filter_invalid": {"removed": 10624},
  "outlier_detection": {"flagged": 8907},
  "feature_engineering": {"added": ["TotalAmount", "Hour", "DayOfWeek", "Month"]}
}
```

---

### GET /api/insights

```json
[
  {
    "type": "trend",
    "severity": "high",
    "title": "销售额出现显著增长",
    "detail": "2011年11月相比10月环比增长 47.2%，需关注是否为季节性因素。"
  }
]
```

---

### GET /api/analysis/\<method\>

| method | 可选参数 | 说明 |
|--------|---------|------|
| `summary_stats` | — | 描述性统计（均值/中位数/标准差/分位数） |
| `sales_trend` | `?freq=ME` | 销售趋势（ME=月 / W=周 / D=日） |
| `top_products` | `?n=10` | 畅销商品 Top N（按销售额降序） |
| `rfm_analysis` | — | RFM 客户价值分析（Recency/Frequency/Monetary） |
| `country_distribution` | — | 国家/地区销售额分布 |
| `correlation_matrix` | — | 数值列相关系数矩阵 |
| `time_pattern` | — | 按星期/小时的订单规律 |

---

### POST /api/chat

**请求**：
```json
{"question": "月均销售额是多少？"}
```

支持 URL 参数 `?stream=true`（默认）启用 SSE 流式响应，`?stream=false` 使用传统同步模式。

**SSE 流式响应（stream=true，默认）**：
```
data: {"type": "text_delta", "content": "月度"}\n\n
data: {"type": "text_delta", "content": "销售"}\n\n
data: {"type": "exec_result", "success": true, "result": 74570}\n\n
data: {"type": "chart", "data": {...}}\n\n
data: [DONE]\n\n
```

**同步响应（stream=false）**：
```json
{
  "answer": "根据数据，月均销售额约为 74,570 元...",
  "code": "monthly = df.groupby(df['InvoiceDate'].dt.to_period('M'))['TotalAmount'].sum()\nresult = monthly.mean()",
  "execution": {
    "success": true,
    "result": 74570.23,
    "chart": null
  }
}
```

---

### GET /api/chat/history

返回当前会话的完整对话历史列表。

---

### POST /api/chat/reset

重置对话历史，返回 `{"status": "ok"}`。

---

### POST /api/report/generate

**请求体（可选）**：
```json
{"mode": "simple"}    // 简洁模式（默认），单次 AI 调用
{"mode": "detailed"}  // 深度模式，4 Agent 协作 + SSE 流式推送
{"mode": "story"}     // 🆕 叙事模式，数据故事体报告
```

**SSE 流式响应（detailed 模式）**：
```
data: {"type": "report_start", "mode": "detailed"}\n\n
data: {"type": "agent_progress", "agent": "statistics", "status": "running"}\n\n
data: {"type": "section", "agent": "statistics", "content": "## 数据特征描述\n..."}\n\n
data: {"type": "agent_progress", "agent": "insight", "status": "running"}\n\n
data: {"type": "section", "agent": "insight", "content": "## 关键洞察\n..."}\n\n
data: {"type": "agent_progress", "agent": "qa", "status": "running"}\n\n
data: {"type": "section", "agent": "qa", "content": "## 对话分析摘要\n..."}\n\n
data: {"type": "agent_progress", "agent": "synthesis", "status": "running"}\n\n
data: {"type": "section", "agent": "synthesis", "content": "## 总结与建议\n..."}\n\n
data: [DONE]\n\n
```

**同步响应（simple/story 模式）**：
```json
{
  "title": "DataMind 数据分析报告",
  "content": "## 数据概览\n...",
  "html": "<h2>数据概览</h2>...",
  "generated_at": "2026-05-12 14:30:00",
  "mode": "simple"
}
```

---

### 🆕 POST /api/chart/generate

**请求**：
```json
{
  "description": "画一个月度销售趋势的折线图",
  "previous_chart": null
}
```

**响应（成功）**：
```json
{
  "success": true,
  "chart_data": { "data": [...], "layout": {...} },
  "code": "import plotly.graph_objects as go\n...",
  "explanation": "已生成月度销售趋势折线图..."
}
```

**响应（失败）**：
```json
{
  "success": false,
  "explanation": "无法生成图表：数据中没有找到日期列"
}
```

---

### 🆕 POST /api/plan/generate

**请求（可选）**：POST body 可为空，自动读取当前数据集。

**响应（成功）**：
```json
{
  "plans": [
    { "id": 1, "title": "月度销售趋势分析", "category": "趋势分析", "description": "..." },
    { "id": 2, "title": "Top 商品相关性", "category": "相关性", "description": "..." },
    { "id": 3, "title": "数据质量排查", "category": "数据质量", "description": "..." }
  ]
}
```

---

### 🆕 GET /api/data/quality

**响应（成功）**：
```json
{
  "score": 85,
  "grade": "B",
  "dimensions": {
    "completeness": { "score": 90, "weight": 0.30, "detail": "2 列存在缺失值" },
    "uniqueness": { "score": 95, "weight": 0.20, "detail": "重复率 0.5%" },
    "consistency": { "score": 78, "weight": 0.15, "detail": "检测到 156 个异常值" },
    "timeliness": { "score": 60, "weight": 0.15, "detail": "最新数据距今 45 天" },
    "accuracy": { "score": 100, "weight": 0.20, "detail": "所有列类型转换正常" }
  },
  "suggestions": ["建议检查 Quantity 列中的异常值", "数据时效性较低，建议更新"]
}
```

---

### 🆕 POST /api/report/story

**请求**：POST body 可为空，自动基于当前报告和洞察生成叙事。

**响应（成功）**：
```json
{
  "title": "从数据中浮现的故事：销售增长的秘密",
  "summary": "过去一年中，UK 市场贡献了 82% 的销售额，但11月的异常增长预示着什么？",
  "paragraphs": [
    { "text": "...叙事段落...", "highlights": [{"label": "总销售额", "value": "£8.5M"}] }
  ],
  "conclusions": ["UK 市场是绝对核心", "11月峰值需要关注库存准备", "..."]
}
```

---

## 8. 配置说明

编辑 `config.py` 修改以下参数：

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `AI_API_KEY` | `""` | API Key（优先读取环境变量，运行时可界面修改） |
| `AI_BASE_URL` | `https://api.openai.com/v1` | 服务商 Base URL，兼容所有 OpenAI 格式接口 |
| `AI_MODEL` | `"gpt-4o-mini"` | 使用的模型名称 |
| `UPLOAD_FOLDER` | `./datasets/` | 上传文件保存目录 |
| `MAX_FILE_SIZE` | `50 MB` | 最大上传文件大小（字节） |
| `ALLOWED_EXTENSIONS` | `csv, xlsx, json` | 允许上传的文件格式 |
| `SECRET_KEY` | `datamind-dev-secret-2026` | Flask Session 密钥（生产环境务必修改） |
| `DEBUG` | `true` | 调试模式（生产环境改为 `false`） |
| `HOST` | `0.0.0.0` | 监听地址 |
| `PORT` | `5000` | 监听端口 |

---

## 9. 测试说明

### 运行测试

```bash
# 运行全部测试（276 个用例）
python -m pytest tests/ -v

# 只运行特定模块
python -m pytest tests/test_api.py -v
python -m pytest tests/test_preprocessor.py -v

# 快速摘要（不显示详细用例）
python -m pytest tests/ -q
```

### 测试覆盖范围

| 测试文件 | 覆盖模块 | 用例数 |
|----------|----------|:------:|
| test_loader.py | data/loader.py | ~10 |
| test_preprocessor.py | data/preprocessor.py | 34 |
| test_analyzer.py | data/analyzer.py | ~25 |
| test_detector.py | data/detector.py | 21 |
| test_chat.py | ai/chat.py | 12 |
| test_code_generator.py | ai/code_generator.py | 19 |
| test_insight.py | ai/insight.py | 7 |
| test_report.py | ai/report.py | 13 |
| test_report_agents.py | ai/report_agents.py | 13 |
| test_chart_generator.py 🆕 | ai/chart_generator.py | ~15 |
| test_plan_generator.py 🆕 | ai/plan_generator.py | ~10 |
| test_storyteller.py 🆕 | ai/storyteller.py | ~10 |
| test_quality_scorer.py 🆕 | data/quality_scorer.py | ~15 |
| test_quality_timeliness.py 🆕 | data/quality_scorer.py（时效性专项） | 3 |
| test_api.py | routes/api.py（含 SSE/新端点） | ~43 |
| **合计** | | **276** |

> 所有测试均使用 `unittest.mock.MagicMock` 模拟 OpenAI API，无需真实 Key，CI 环境可直接运行。SSE 响应测试验证流式格式和事件类型完整性。

---

## 10. 版本历史

| 版本 | 日期 | 主要更新 |
|------|------|---------|
| **v1.0** | 2026-05 初 | 数据上传→自动清洗→规则洞察→自然语言问答→交互图表→一键报告 |
| **v2.0** | 2026-05 中 | 上线专家模式：多 Agent 协作框架（StatisticsAgent/InsightAgent/QAAgent/SynthesisAgent），深度报告模式，增强数据预处理（文本清洗/智能缺失值填充/两档 IQR 异常标记/特征工程），Ollama 本地免费部署支持 |
| **v3.0** | 2026-05 末 | SSE 流式响应底座（问答+报告流式推送），NL2Vis 图表工作台（自然语言→Plotly 交互图表），数据质量评分卡（5 维度加权评分），智能分析计划生成器，数据叙事引擎，测试覆盖扩至 247 用例 |
| **v3.1** | 2026-05-26 | **Bug 修复批次**：时效性进度条颜色修复（`--yellow`→`--amber`）、仪表盘图表尺寸错误修复（flex 样式重置 + 双重 resize）、散点图同步后不可见修复（剥离 plotly_dark 模板 + marker 可见性保障）、时效性未来日期负数文案修复。**通用性增强**：6 种画像专属建议问题、宽数据集（>25 列）系统提示词截断、纯分类数据自适应图表、DataProfiler 全模式覆盖。测试扩至 276 用例 |

---

## 11. 常见问题

**Q1：上传 CSV 后中文显示乱码？**

系统已内置自动编码检测（chardet），支持 UTF-8 / GBK / Latin1。若仍乱码，请用 Excel「另存为 CSV UTF-8（含 BOM）」格式后重新上传。

---

**Q2：智能问答返回 400 / API Key 错误？**

未配置 API Key，或 Key 格式不正确。参考第 4.3 节在界面配置面板填入 API Key，或通过环境变量 `AI_API_KEY` 设置后**重启应用**（`python app.py`）。

---

**Q3：可视化某个图表显示「暂无数据」？**

数据集缺少对应列。系统使用以下关键词模糊匹配（大小写不敏感）：

| 分析类型 | 识别关键词 |
|----------|-----------|
| 日期列 | date, time, invoice |
| 金额列 | amount, total, revenue, price |
| 数量列 | quantity, qty, count |
| 客户 ID | customerid, custid, client |
| 国家列 | country, region, area |

---

**Q4：如何分析非电商数据（气象/财务/医疗）？**

直接上传即可。系统自动检测列类型并应用通用策略。不能匹配的特定分析（如 RFM）会显示「暂无数据」，不影响其他功能（统计卡片、洞察面板、相关性矩阵、智能问答等仍完整可用）。

---

**Q5：报告生成等待很久没有响应？**

深度报告模式下，系统以 **SSE 流式**逐个 Agent 推送进度——每个 Agent 完成后对应章节立即渲染，无需等待全部完成。简洁模式下 OpenAI API 响应通常需要 10-30 秒。若超时或 API 调用失败，系统自动降级为内置模板报告立即返回。

---

**Q6：如何在生产环境部署？**

```bash
pip install gunicorn

# 设置生产环境变量
export FLASK_DEBUG=false
export AI_API_KEY=sk-...
export FLASK_SECRET_KEY=your-strong-secret-key

# 启动（4 个 worker 进程）
gunicorn -w 4 -b 0.0.0.0:5000 "app:create_app()"
```

---

**Q7：视频背景无法播放 / 一片黑色？**

确认 `static/videos/mech-girl.mp4` 文件存在且可被 Flask 静态文件服务访问。浏览器需支持 `autoplay` muted 视频（Chrome / Edge / Firefox 均支持）。由于视频使用 `mix-blend-mode: screen`，若文件损坏，背景仍正常显示（粒子 + 光晕效果）。

---

**Q8：修改了 JS/CSS 代码后浏览器页面没有变化？**

Flask 开发服务器已配置禁用静态文件缓存（`SEND_FILE_MAX_AGE_DEFAULT = 0`），重启服务器后普通刷新即可生效。若仍无效，按 `Ctrl+Shift+F5`（Windows）或 `Cmd+Shift+R`（macOS）强制刷新浏览器缓存。

---

**Q9：切换到其他页面后数据消失，提示「请先上传数据文件」？**

Flask 重启后内存状态会清空。但系统已实现持久化恢复机制：重启后访问任意需要数据的页面，会自动从 `datasets/.last_upload.json` 读取上次上传的文件路径并恢复状态。

若自动恢复失败（文件已被删除或路径变更），重新上传数据文件即可。

---

**Q10：生成报告后下载的 `.md` 文件是网站的 HTML，而不是分析内容？**

这是 **Base URL 配置错误**导致的。AI 请求打到了中转站的前端页面，服务器把网页 HTML 当成了 API 响应返回。

**解决步骤：**

1. **重启 Flask 服务器**（`Ctrl+C` 后重新执行 `python app.py`）
2. 打开浏览器访问 `http://localhost:5000`，点击顶栏 **⚙ 图标** 进入 AI 配置面板
3. 检查并修正 **Base URL**：末尾必须带 `/v1`（或服务商指定的 API 路径）

   | ❌ 错误示例 | ✅ 正确示例 |
   |---|---|
   | `https://stuhelperai.com` | `https://stuhelperai.com/v1` |
   | `https://api.openai.com` | `https://api.openai.com/v1` |
   | `https://api.deepseek.com` | `https://api.deepseek.com/v1` |

4. 点击「**测试连接**」，确认返回绿色"连接成功"后再点击「**保存配置**」
5. 重新上传数据文件，再点击「生成分析报告」

> **系统已内置自动检测**：配置面板保存时会校验 Base URL 格式，若不以 `/v1` 结尾会弹出警告。同时报告生成时若 AI 返回 HTML 内容，会自动降级到模板报告，不再把网页代码写入下载文件。

---

**Q11：智能问答返回了答案，但页面上只显示绿色「AI」徽章、看不到文字内容？**

极少数情况下浏览器缓存了旧版 `chat.js`。解决方法：

```
Ctrl+Shift+F5   （Windows/Linux 强制刷新）
Cmd+Shift+R     （macOS 强制刷新）
```

或在浏览器开发者工具（F12）→「Network」选项卡中勾选「Disable cache」后刷新页面。

---

**Q12：图表渲染完成后，「加载中」的转圈动画仍然显示在图表上方？**

此问题已在当前版本修复（各图表渲染前会先清空容器内容）。若仍出现，同样通过强制刷新浏览器缓存（`Ctrl+Shift+F5`）解决。

---

**Q13：AI 配置「测试连接」成功，但智能问答总是返回「执行成功，无返回值」，没有文字答案？**

可能原因及排查步骤：

1. **模型名称错误**：确认填写的模型名称与服务商支持的一致（如 `glm-4-flash` 而非 `glm4-flash`）
2. **问题触发了代码路径而非纯文字答案**：系统默认让 AI 生成并执行代码，「执行成功，无返回值」表示代码执行了但 `result` 为空（如 `print()` 语句）。尝试换一个更明确的问题，如「月均销售额是多少，给我一个数字」
3. **数据未上传**：确认顶栏状态显示「已加载: 文件名」，若显示「未上传」则先上传数据文件

---

**Q14：图表工作台/分析计划/数据叙事功能不可用？**

这三个功能依赖 AI API，但均内置降级方案：
- **图表工作台**：无 Key 时入口隐藏，有 Key 但生成失败时返回错误解释
- **分析计划**：无 Key 时自动使用规则引擎生成基础计划（至少 3 条）
- **数据叙事**：无 Key 时基于洞察结果自动生成基础叙事体
- **数据质量评分卡**：零 API 依赖，始终可用

---

## 12. 技术架构

### 分层架构

```
┌──────────────────────────────────────────────────────────────────┐
│  浏览器 (Bootstrap 5 · Plotly.js · marked.js · Canvas API)       │
│  Cinematic Space UI: 液态玻璃 · 粒子场 · 赛博视频 · 全息立方体     │
│  🆕 SSE EventSource → 流式接收问答/报告                           │
│  🆕 图表工作台 → Plotly.react() 渲染交互图表                       │
│  🆕 质量评分卡 → SVG 环形图 + 5 维度柱状条                          │
│  🆕 分析计划面板 → Todo-list 式分析任务列表                          │
│  🆕 数据故事 → 叙事体报告 + 高亮数字卡片                             │
└──────────────────────────┬───────────────────────────────────────┘
                           │  Fetch API + SSE
┌──────────────────────────▼───────────────────────────────────────┐
│  Flask  routes/pages.py  +  routes/api.py                        │
│  14 个 REST 端点  ·  app_state 内存缓存                            │
│  🆕 _sse_stream() 通用 SSE 流式组件                                │
└──────┬────────────────────────────────────────┬──────────────────┘
       │                                        │
┌──────▼──────────────┐              ┌──────────▼──────────────────┐
│  data/ 数据层        │              │  ai/ 智能体层                 │
│  loader.py          │              │  chat.py (SSE 流式多轮对话)    │
│  preprocessor.py    │              │  code_generator.py            │
│  analyzer.py        │              │  insight.py (零 API)          │
│  detector.py        │              │  report.py (SSE 流式报告)      │
│  🆕 quality_scorer  │              │  report_agents.py             │
│                     │              │  🆕 chart_generator.py         │
│                     │              │  🆕 plan_generator.py          │
│                     │              │  🆕 storyteller.py             │
└─────────────────────┘              └──────────┬───────────────────┘
                                                │
                                     ┌──────────▼──────────────────┐
                                     │  OpenAI / DeepSeek / Kimi    │
                                     │  智谱 / 通义千问 / 豆包       │
                                     │  （可选，全功能降级可用）      │
                                     └─────────────────────────────┘
```

### 前端 z-index 层级

```
z-index 9990  #drag-overlay          全局拖拽上传遮罩
z-index  100  .topbar / .statusbar   顶部导航 + 底部状态栏
z-index    2  .main-wrapper          侧边栏 + 主内容区 + 洞察面板（液态玻璃）
z-index    1  .mech-video-bg         机械女孩赛博视频背景
z-index    0  canvas / .bg-orbs /    粒子星场 + 星云光晕 + 电路网格 +
              .holo-cube-wrapper /   全息旋转立方体 + 脉冲同心环
              .ring-system
```

### 安全沙箱（代码执行）

AI 生成的 Python 代码在受限命名空间中执行：

**允许的对象**：`df`, `pd`, `np`, `len`, `range`, `sum`, `min`, `max`, `round`, `sorted`, `list`, `dict`, `zip`, `enumerate`

**黑名单关键词**（检测到即拒绝执行）：
```
os, sys, subprocess, open, __import__, eval, exec,
shutil, pathlib, socket, __builtins__, globals, locals
```

---

*DataMind v3.1 — 来源：学生 + AI*
