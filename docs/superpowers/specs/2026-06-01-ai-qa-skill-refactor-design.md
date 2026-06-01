# DataMind AI 问答「技能化」改造 — 设计规格

- 日期：2026-06-01
- 状态：已通过设计评审，待规格审查
- 作者：学生+AI

## 1. 背景与目标

### 1.1 缘起

期末项目要求（《高级 Python 程序设计》"智能问数"Web 程序）明确推荐把数据分析能力封装为
**AI 可调用的可复用 Skill**：

> 把"怎么分析数据"的步骤写入 `SKILL.md`，把稳定操作放入 `scripts/`。
> 大模型负责理解意图、选择脚本、解释结果；学生负责设计、验证和边界控制。
> 先用脚本做确定性分析，再由 LLM 解释结果。规则问答优先；复杂问题再交给 LLM。

参考 demo（`streamlit_viz_skill_demo`）给出了具体的「技能化」组织形式：

- 每个能力 = 一个文件夹：`SKILL.md`（LLM 面向的操作手册：触发条件 + 工作流 + JSON 输出规范）
  + 一个 Python 模块（确定性执行脚本）。
- 入口处有**技能注册表**（`SkillSpec`）与 **LLM 路由器**（`route_skill`）：LLM 先选 skill、
  再把自然语言转成 JSON 计划，本地脚本确定性执行。
- 未命中任何 skill 时有 **fallback** 兜底。

### 1.2 当前 DataMind 架构（Flask）

- 链路：用户提问 → `/chat` SSE 端点 → `ChatSession` 构建数据感知系统提示词 → LLM 流式返回
  **Python 代码** → `CodeGenerator` 提取/校验/沙箱执行 → 返回结果 + Plotly 图表。
- 特点：LLM **生成任意 Python 代码**，靠关键词黑名单 + 受限命名空间沙箱执行（"代码生成"范式）。

### 1.3 改造目标

把 AI 问答改造为参考 demo 的「技能化」组织形式，采用**增量式**策略：

- **技能层为主**：常见问数走确定性 skill（路由 → JSON 计划 → 脚本执行 → LLM 解释）。
- **代码生成兜底**：未被 skill 覆盖的复杂/自由问题，降级到现有代码生成沙箱（**完全保留、零改动**）。

### 1.4 非目标（YAGNI）

- 不切换 Web 框架（保留 Flask + SSE + Plotly 前端，不改用 Streamlit）。
- 不移除、不重写现有代码生成沙箱（`code_generator.py`）及其安全机制。
- 不重写已测试的分析逻辑（`data/analyzer.py`、`profiler.py` 等），只做**薄包装**。
- 本期不做跨 skill 的多步编排（一个问题命中一个 skill）。

## 2. 关键设计决策（已评审通过）

| 决策点 | 选择 | 理由 |
|---|---|---|
| 改造程度 | 增量式：技能层为主 + 代码生成兜底 | 贴合 PDF"规则优先、复杂交 LLM"，保留已测试能力，风险可控 |
| 技能粒度 | 细粒度 6 个：stats / viz / trend / correlation / distribution / profile | 覆盖更全，体现"多技能路由"，对应 PDF 创新分 |
| 目录与复用 | 顶层 `skills/` + 薄包装复用现有模块 | 符合 DRY；与 `.claude/skills/` 物理隔离 |
| 结论生成 | 两阶段：脚本跑数据 + LLM 二次解释（SSE 流式） | 贴合 PDF"先脚本后解释"，解释基于真实结果不编造 |

## 3. 目录结构与文件组织

新增顶层 `skills/`（运行时确定性技能，与 Claude Code 开发用的 `.claude/skills/` 物理隔离、命名不冲突）：

```text
DataMind/
├── skills/                       # ★新增：运行时技能注册表
│   ├── __init__.py               # SKILLS 注册表（SkillSpec）+ load_catalog()
│   ├── _contract.py              # SkillResult 数据类 + 公共计划校验工具
│   ├── stats_skill/
│   │   ├── __init__.py
│   │   ├── SKILL.md              # frontmatter(name/description) + JSON 计划规范 + 规则
│   │   └── stats_skill.py        # execute_stats_plan(df, plan) -> SkillResult
│   ├── viz_skill/         { __init__.py, SKILL.md, viz_skill.py }
│   ├── trend_skill/       { __init__.py, SKILL.md, trend_skill.py }
│   ├── correlation_skill/ { __init__.py, SKILL.md, correlation_skill.py }
│   ├── distribution_skill/{ __init__.py, SKILL.md, distribution_skill.py }
│   └── profile_skill/     { __init__.py, SKILL.md, profile_skill.py }
├── ai/
│   └── skill_router.py           # ★新增：LLM 路由 + JSON 计划生成 + 二次解释（~150 行）
└── tests/
    ├── test_skill_stats.py        # 每个 skill 一份确定性测试
    ├── test_skill_viz.py
    ├── test_skill_trend.py
    ├── test_skill_correlation.py
    ├── test_skill_distribution.py
    ├── test_skill_profile.py
    └── test_skill_router.py       # mock LLM 路由/兜底测试
```

**SRP**：每个 skill 文件夹单一职责，SKILL.md（声明：何时触发 + 输出什么）与 `*.py`（执行：稳定脚本）分离；
router 只管路由与解释，不含分析逻辑。
**DRY**：脚本薄包装现有已测试模块，不重写分析逻辑。

## 4. 运行时数据流与 `/chat` 集成

```text
用户提问
  │
  ▼  ① router.route(question, df_summary)            ← 第 1 次 LLM 调用
     注入所有 SKILL.md 目录，返回 {skill, plan, reason}
  │
  ├─ skill ∈ SKILLS（命中确定性技能）
  │     yield {type:"route", skill, reason, plan}
  │     result = SKILLS[skill].execute(df, plan)      ← 确定性脚本，零 LLM
  │     yield {type:"evidence", rows:[...]}
  │     yield {type:"chart", data: plotly_json}        （若有图）
  │     stream router.explain(question, evidence, answer_hint)  ← 第 2 次 LLM 调用（流式中文解释）
  │        → 多个 {type:"text_delta"}
  │
  └─ skill == "fallback"（未命中）
        走【现有代码生成路径】完全不变：
        LLM 流式 Python → extract_code → validate_code → execute_safe → chart
  │
  ▼  yield {type:"done"}
```

### 4.1 SSE 事件契约

- **复用**（前端现有渲染逻辑不动）：`text_delta`、`chart`、`error`、`done`、`heartbeat`、
  `code_complete`、`exec_result`。
- **新增**：
  - `{"type":"route", "skill": "...", "reason": "...", "plan": {...}}` — 路由结果徽章。
  - `{"type":"evidence", "rows": [...], "columns": [...]}` — 证据表。
- 前端未实现新事件处理时**优雅降级**（忽略未知 type，不报错）。

### 4.2 兜底零改动

`code_generator` 沙箱、`validate_code`、`execute_safe`、`extract_code` 原样保留，仅在
`skill == "fallback"` 时进入。失败/超时/路由异常也回退到该路径，保证鲁棒性。

## 5. 接口契约（接口隔离 ISP）

### 5.1 SkillResult（`skills/_contract.py`）

适配现有 Plotly 前端（图表为 JSON，而非 demo 的 matplotlib PNG）：

```python
from dataclasses import dataclass, field
import pandas as pd

@dataclass
class SkillResult:
    answer: str                       # 脚本算出的简短事实结论（解释前的占位/事实锚点）
    evidence: pd.DataFrame            # 证据表（前端表格渲染 + 回传给 explain）
    chart: dict | None = None         # Plotly figure JSON（fig.to_plotly_json()）
    meta: dict = field(default_factory=dict)  # title / x_label / y_label 等
```

每个 skill 暴露统一签名：`execute_<name>_plan(df: pd.DataFrame, plan: dict) -> SkillResult`。

### 5.2 SkillSpec 与注册表（`skills/__init__.py`）

```python
@dataclass(frozen=True)
class SkillSpec:
    name: str            # 路由标识，如 "stats-skill"
    title: str           # 中文展示名
    path: Path           # SKILL.md 路径
    execute: Callable[[pd.DataFrame, dict], SkillResult]

SKILLS: dict[str, SkillSpec] = { ... }   # 6 个 skill

def load_catalog() -> str:               # 拼接所有 SKILL.md，注入路由 system prompt
    ...
```

### 5.3 JSON 计划 schema（各 SKILL.md 定义）

| skill | plan 字段 |
|---|---|
| stats-skill | `metrics[]`(mean/median/variance/std/min/max/count), `columns[]`, `group_by`(or null), `title`, `answer` |
| viz-skill | `chart_type`(bar/line/scatter/pie), `x`, `y`, `agg`(sum/mean/count/none), `title`, `answer` |
| trend-skill | `date_col`, `value_col`, `agg`(sum/mean), `freq`(D/W/M), `title`, `answer` |
| correlation-skill | `columns[]`, `method`(pearson/spearman), `title`, `answer` |
| distribution-skill | `column`, `kind`(hist/box), `bins`, `title`, `answer` |
| profile-skill | `scope`(overview/schema/quality), `answer` |

所有脚本用公共校验工具（`_safe_col` / `_safe_numeric_cols`）**校验计划中的列名/参数**，
非法时安全降级（沿用 demo `_safe_col` 思路 + 现有 `code_generator` 的净化经验），不抛裸异常给用户。

### 5.4 SKILL.md 格式（镜像 demo）

```markdown
---
name: stats-skill
description: <英文触发场景，供路由匹配>
---

# <Skill 名>

<一句话定位：帮助程序选择分析参数，不写可执行代码>

Return JSON only. Do not wrap it in Markdown:
\`\`\`json
{ ...plan schema... }
\`\`\`

Rules:
- Only choose columns that appear in the provided schema.
- Do not output Python code.
- <skill 专属约束>
```

### 5.5 SkillRouter（`ai/skill_router.py`）

```python
class SkillRouter:
    def __init__(self, client): ...
    def route(self, question: str, df_summary: dict) -> dict:
        # 第 1 次 LLM 调用：注入 load_catalog()，返回 {skill, plan, reason}
        # 复用现有 JSON 提取容错（参考 plan_generator._parse_json）
    def explain_stream(self, question: str, skill_title: str,
                       evidence: pd.DataFrame, answer_hint: str):
        # 第 2 次 LLM 调用：基于证据表流式生成中文解释（generator，逐 token yield）
```

复用现有 OpenAI client（`state["code_generator"].client`）与 `config.AI_MODEL`，不新建客户端。

## 6. 复用映射（薄包装，不重写）

| skill | 复用的现有逻辑 | 补充 |
|---|---|---|
| stats | `analyzer.summary_stats` + pandas `groupby().agg` | 参考 demo `stats_skill` 的指标归一化 |
| viz | `chart_generator` 的 Plotly 序列化（`_sanitize_numpy` / `to_plotly_json`） | 按 chart_type 分发 px/go |
| trend | `analyzer.sales_trend(freq)` / `time_pattern` | 通用 date+value 重采样降级路径 |
| correlation | `analyzer.correlation_matrix` | 输出热力图 Plotly JSON |
| distribution | `analyzer.numeric_distributions` / `box_plots` / `category_distributions` | 按 kind 分发 |
| profile | `profiler.DataProfiler(df).detect()` | scope 投影到 overview/schema/quality |

> 注：`analyzer` 部分方法为 retail 数据专用（如 `sales_trend`、`top_products`、`rfm`）。
> skill 内对非 retail 数据提供**通用降级路径**（基于列类型推断 date/numeric/category）。
> 精确的方法签名与降级分支在实现计划阶段逐一核验。

## 7. 测试与验证策略（TDD）

- **每个 skill**（`test_skill_<name>.py`）：固定 `DataFrame` → 断言 `evidence` 形状/数值、
  `chart` 结构、**非法列名安全降级**。零 LLM 依赖，纯确定性。
- **router**（`test_skill_router.py`）：mock client 返回固定 JSON → 断言计划解析、skill 选择、
  `fallback` 分支、JSON 提取容错；`explain_stream` 用 mock 流验证逐 token 输出。
- **集成**：扩展 `tests/test_api.py`，mock router 命中/未命中两条 `/chat` 路径。
- **回归**：现有 305 测试全部保持通过（兜底路径不变）。
- **验证命令**：`python -m pytest tests/ -q`（声称完成前必须运行并确认输出）。

## 8. 代码来源标注

所有新增文件按项目约定在文件/函数级标注来源（`来源：学生` / `来源：AI` / `来源：学生+AI`），
符合期末项目学术诚信要求。

## 9. 风险与对策

| 风险 | 对策 |
|---|---|
| 路由 LLM 选错 skill | 计划校验 + 安全降级；选 fallback 时回退代码生成；`reason` 字段可观测 |
| 二次解释增加延迟 | 解释为 SSE 流式，首 token 即显示；脚本结果先于解释返回 |
| analyzer retail 专用方法在通用数据上失效 | skill 内通用降级路径 + 确定性测试覆盖非 retail 数据 |
| 前端不识别新 SSE 事件 | 未知 type 优雅忽略；新增渲染为增量、不破坏旧逻辑 |
| 现有能力回归 | 兜底路径零改动 + 全量 pytest 回归 |
