# DataMind v2.0 创新增强设计规格

> 状态：已批准 | 日期：2026-05-25 | 基于 v1.0 增强

---

## 1. 概述

在 DataMind v1.0（数据上传→自动清洗→规则洞察→自然语言问答→交互图表→一键报告）的基础上，引入 4 大增强模块 + SSE 流式底座，提升产品的智能化水平和用户体验。

### 1.1 核心目标

| 目标 | 描述 |
|------|------|
| **体验丝滑** | SSE 流式响应消除 30-90s 空白等待 |
| **智能增强** | NL2Vis 图表工作台 + 分析计划 + 数据叙事 |
| **工程可维护** | 不改稳定模块（code_generator/analyzer），新功能独立文件 |

### 1.2 设计原则

- **不改稳定模块**：`code_generator.py`、`analyzer.py`、`detector.py`、`loader.py`、`insight.py` 不动
- **新增即插即用**：所有新功能通过独立模块 + 新增路由接入
- **降级全覆盖**：每个 AI 功能都有 fallback，无 API Key 时核心体验不降级
- **流式优先**：改造 `/api/chat` 和 `/api/report/generate` 为 SSE 流，但不破坏现有 API 契约

---

## 2. 架构概览

```
┌──────────────────────────────────────────────────────────────────┐
│                         浏览器 (Browser)                          │
│  SSE EventSource ← 流式接收报告/问答                              │
│  图表工作台 ← Plotly.react() 渲染交互图表                          │
│  分析计划面板 ← Todo-list 式分析任务列表                           │
│  数据质量评分卡 ← 环形图 + 5 维度柱状条                            │
│  数据故事 ← 叙事体报告 + 高亮数字卡片                               │
└──────────────────────────────┬───────────────────────────────────┘
                               │  Fetch API + SSE
┌──────────────────────────────▼───────────────────────────────────┐
│                     Flask routes/api.py                           │
│  /api/chat          → SSE 流（改造）                              │
│  /api/chart/generate → NL2Vis 自然语言图表（新增）                 │
│  /api/report/generate → SSE 流式报告（改造）                       │
│  /api/report/story   → 数据叙事（新增）                            │
│  /api/plan/generate  → 分析计划生成（新增）                        │
│  /api/data/quality   → 数据质量评分卡（新增）                       │
└──────┬────────────────────────────────────────────┬──────────────┘
       │                                            │
┌──────▼──────────────────────┐    ┌────────────────▼──────────────┐
│  ai/ 智能体层（扩展）         │    │  data/ 数据层（扩展）           │
│  chat.py           (改造)    │    │  preprocessor.py  (不变)       │
│  code_generator.py (不变)    │    │  quality_scorer.py (新增)      │
│  chart_generator.py (新增)   │    │  analyzer.py      (不变)       │
│  plan_generator.py  (新增)   │    │  detector.py      (不变)       │
│  storyteller.py     (新增)   │    │  loader.py        (不变)       │
│  report.py          (改造)   │    │                               │
│  report_agents.py   (改造)   │    │                               │
│  insight.py         (不变)   │    │                               │
└─────────────────────────────┘    └───────────────────────────────┘
```

### 2.1 文件变更清单

| 文件 | 操作 | 约行数 |
|------|------|:---:|
| `ai/chart_generator.py` | **新建** | ~150 |
| `ai/plan_generator.py` | **新建** | ~120 |
| `ai/storyteller.py` | **新建** | ~180 |
| `data/quality_scorer.py` | **新建** | ~200 |
| `static/js/chart-workspace.js` | **新建** | ~250 |
| `static/js/sse-handler.js` | **新建** | ~80 |
| `routes/api.py` | 改造 | +150 |
| `ai/chat.py` | 改造 | +30 |
| `ai/report.py` | 改造 | +40 |
| `ai/report_agents.py` | 改造 | +20 |
| `templates/report.html` | 改造 | +120 |
| `templates/analysis.html` | 改造 | +80 |
| `templates/index.html` | 改造 | +60 |
| `templates/base.html` | 改造 | +10 |
| `static/js/chat.js` | 改造 | +80 |
| `static/js/app.js` | 改造 | +40 |
| `static/css/style.css` | 改造 | +100 |

---

## 3. 模块详细设计

### 3.1 SSE 流式响应机制（底座）

**目的**：为流式问答、流式报告、渐进图表渲染提供统一基础设施。

**后端**：`routes/api.py` 新增通用 `_sse_stream()` 函数，包装 Flask `Response` + `stream_with_context`。

**SSE 消息格式**：
```
data: {"type": "text_delta", "content": "月度"}\n\n
data: {"type": "text_delta", "content": "销售"}\n\n
data: {"type": "exec_result", "success": true, "result": 74570}\n\n
data: {"type": "chart", "data": {...}}\n\n
data: {"type": "agent_progress", "agent": "insight", "status": "running"}\n\n
data: {"type": "section", "agent": "insight", "content": "## 关键洞察\n..."}\n\n
data: [DONE]\n\n
```

**降级策略**：前端检测 `fetch` + `ReadableStream` 是否可用，不可用时走现有同步接口。

**改造 `/api/chat`**：
1. OpenAI 调用改为 `stream=True`
2. 每收到 delta chunk → yield `{"type": "text_delta"}`
3. 流结束 → 提取完整代码 → 沙箱执行 → yield `{"type": "exec_result"}` + 可选 `{"type": "chart"}`
4. 最后 yield `done`

**改造 `/api/report/generate`（深度模式）**：
1. yield `{"type": "report_start", "mode": "detailed"}`
2. 每个 Agent 启动 → yield `{"type": "agent_progress", "agent": "xxx", "status": "running"}`
3. 每个 Agent 完成 → yield `{"type": "section", "agent": "xxx", "content": "..."}`
4. 全部完成 → yield `{"type": "report_done"}`

**前端通用模块** (`static/js/sse-handler.js`)：
- `createSSEConnection(url, body, handlers)` 工厂函数
- 用 `fetch` + `ReadableStream` 实现 POST SSE
- 按 SSE 协议逐行解析 data 行，dispatch 到对应 handler

---

### 3.2 NL2Vis 自然语言图表工作台

**目的**：用户用自然语言描述图表需求，系统生成 Plotly 交互图表，支持迭代修改。

**后端** (`ai/chart_generator.py`)：
- `ChartGenerator` 类，复用 `code_generator._SAFE_BUILTINS` 沙箱
- `generate(description, previous_chart=None)` 方法
- AI 系统提示要求输出 `go.Figure` 对象赋值给 `chart` 变量
- 使用 `plotly_dark` 模板匹配赛博朋克风格
- 沙箱执行代码后用 `to_plotly_json()` 序列化

**支持的图表类型**：散点图、折线图、柱状图、饼图、面积图、热力图、箱线图、散点矩阵、桑基图、漏斗图、仪表盘、气泡图

**路由**：`POST /api/chart/generate`

**前端** (`static/js/chart-workspace.js`)：
- 左栏：Plotly 交互图表渲染区（Plotly.react）
- 右栏：AI 解读文字 + 复制代码按钮 + 下载 PNG 按钮
- 顶部：自然语言输入框 + 发送按钮
- 底部：快捷操作按钮（改折线图/按季度聚合/只看 Top 5/深色浅色切换）
- 快捷操作本质是预设自然语言指令，点击后自动填入输入框并触发重新生成

**降级策略**：AI 调用失败或沙箱执行错误时，返回 `{"success": false, "explanation": "错误信息"}`，前端展示错误提示。

---

### 3.3 智能分析计划生成器

**目的**：上传数据后 AI 分析 Schema 并输出结构化分析清单，用户勾选确认后一键执行。

**后端** (`ai/plan_generator.py`)：
- `PlanGenerator` 类
- `generate(df_info, insights)` → `[{"id": 1, "title": "...", "category": "...", "description": "..."}]`
- 降级方案：基于数据特征自动生成至少 3 条基础计划（有日期列 → 趋势分析，数值列 ≥ 2 → 相关性，有缺失 → 质量排查）
- AI 返回 JSON 数组，含 markdown 代码块自动剥离

**路由**：`POST /api/plan/generate`

**前端**：
- 报告页顶部展示分析计划 Todo-list
- 用户可勾选/取消勾选，支持全选
- 点击「执行选中」逐个执行（每个完成推送结果）

---

### 3.4 数据质量评分卡

**目的**：上传数据后自动给出 0-100 的综合质量分，5 维度各自打分。

**后端** (`data/quality_scorer.py`)：
- `QualityScorer` 类
- `score(df_raw, df_clean, preprocess_report)` → 评分结果字典
- 5 维度评分规则：

| 维度 | 权重 | 满分条件 | 扣分规则 |
|------|:---:|------|------|
| 完整性 | 30% | 所有列缺失率为 0 | 各列缺失率 × 权重累扣 |
| 唯一性 | 20% | 无重复行 | 重复率 × 权重扣分 |
| 一致性 | 15% | 数值列无异常值 | 异常率 × 权重扣分 |
| 时效性 | 15% | 最新日期在 7 天内 | 距今 >7d/30d/90d 逐级扣分 |
| 准确性 | 20% | 类型转换全部正常 | 每列类型转换失败扣 5 分 |

- 等级映射：A (90-100) / B (75-89) / C (60-74) / D (<60)

**数据流**：在 `/api/upload` 的预处理完成后自动调用，评分结果存入 `app_state`。

**路由**：`GET /api/data/quality`

**前端**：
- 数据概览页统计卡片下方展示
- 环形评分仪表盘 + 5 维度柱状条 + 改进建议列表

---

### 3.5 数据叙事引擎

**目的**：将结构化报告转化为有起承转合的数据故事，而非信息罗列。

**后端** (`ai/storyteller.py`)：
- `Storyteller` 类
- `tell(df_info, insights, chat_history, report_content)` → 叙事结果字典
- AI 风格：参考数据新闻，生动的标题 + 自然段落 + 关键数字高亮
- 降级方案：基于 insights 生成基础叙事

**路由**：`POST /api/report/story`

**前端**：
- 报告页新增「叙事」模式选项卡
- 展示格式：故事大标题 + 一句话摘要 + 叙事段落（含高亮数字卡片） + 核心结论列表

---

## 4. 数据流

### 4.1 文件上传流程（增强后）

```
用户上传文件
  → load_file()                    # 不变
  → Preprocessor.run_all()         # 不变
  → Analyzer.summary_stats()       # 不变
  → Detector (不变)                # 不变
  → InsightEngine.generate_all()   # 不变
  → 🆕 QualityScorer.score()       # 新增：数据质量评分
  → 存入 app_state                 # 不变（+ quality_score 字段）
```

### 4.2 智能问答流程（增强后）

```
用户输入问题
  → POST /api/chat（SSE 改造）
  → ChatSession.get_context()
  → CodeGenerator.generate()      # 不变，但外层改为流式推送
    → OpenAI stream=True
    → yield text_delta ...        # 🆕 逐 token 推送
    → 提取完整代码
    → execute_safe()              # 不变
    → yield exec_result           # 🆕 推送执行结果
    → yield chart (if any)        # 🆕 推送图表
    → yield done
```

### 4.3 报告生成流程（增强后）

```
用户选择模式（简洁/深度/叙事）
  → 简洁模式：现有逻辑不变（追加 SSE wrap）
  → 深度模式：4 Agent 串行，每个完成后 SSE yield
  → 🆕 叙事模式：Storyteller.tell() →
    报告页渲染叙事体
```

---

## 5. 错误处理与降级矩阵

| 功能 | AI 失败 | 无 API Key | 沙箱执行失败 |
|------|---------|-----------|-------------|
| 流式问答 | 降级为同步模式 | 提示配置 Key | 返回 error 消息 |
| NL2Vis 图表 | 返回错误解释 | 隐藏入口 | 返回错误解释 |
| 分析计划 | fallback 基础计划 | fallback 基础计划 | N/A |
| 质量评分 | N/A（不依赖 AI） | N/A | N/A |
| 数据叙事 | fallback 基础叙事 | fallback 基础叙事 | N/A |
| 流式报告 | fallback 模板报告 | fallback 模板报告 | 各 Agent 独立降级 |

---

## 6. 测试策略

### 6.1 新增测试文件

| 测试文件 | 覆盖模块 | 预计用例 |
|----------|----------|:---:|
| `tests/test_chart_generator.py` | `ai/chart_generator.py` | ~15 |
| `tests/test_plan_generator.py` | `ai/plan_generator.py` | ~10 |
| `tests/test_storyteller.py` | `ai/storyteller.py` | ~10 |
| `tests/test_quality_scorer.py` | `data/quality_scorer.py` | ~15 |

### 6.2 改造测试文件

| 测试文件 | 改什么 |
|----------|--------|
| `tests/test_api.py` | 新增 4 个端点测试 + SSE 响应格式验证 |
| `tests/test_report.py` | 扩展现有测试覆盖流式报告 + 叙事模式 |

### 6.3 测试原则

- 全部使用 MagicMock 模拟 OpenAI API，不依赖真实 Key
- SSE 响应测试：收集所有 stream 事件，验证格式和内容
- 降级路径测试：Mock AI 异常，验证 fallback 输出非空

---

## 7. 实施顺序建议

| 阶段 | 模块 | 依赖 |
|------|------|------|
| **1** | SSE 流式底座 | 无（优先做，后续模块全部依赖） |
| **2** | 数据质量评分卡 | 无（纯 data 层，不依赖 AI） |
| **3** | NL2Vis 图表工作台 | 依赖阶段 1（SSE 可选，但默认带） |
| **4** | 分析计划生成器 | 无 |
| **5** | 数据叙事引擎 | 无 |
| **6** | 前端整合 + 测试 | 依赖阶段 1-5 |

---

## 8. 不做什么（YAGNI）

- **不做预测模型集成**（Prophet/StatsModels）：增加依赖且与核心定位偏差大，作为远期扩展方向
- **不做多用户系统**：属于平台化范畴，当前聚焦单用户功能增强
- **不做定时告警/邮件通知**：需要额外基础设施（Celery/Redis/SMTP），暂缓
- **不做图表模板市场**：没有多用户基础，模板市场没有价值
- **不做语音输入**：Web Speech API 兼容性差，ROI 低
