# DataMind AI 问答「技能化」改造 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 把 DataMind 的 AI 问答改造为参考 demo 的「技能化」组织形式——LLM 路由到确定性 skill（脚本执行）+ LLM 二次解释，未命中则降级到现有代码生成沙箱。

**架构：** 新增顶层 `skills/`（6 个确定性技能：stats/viz/trend/correlation/distribution/profile），每个 = `SKILL.md` + 脚本（薄包装现有 `data/analyzer.py`、`profiler.py` 等）。新增 `ai/skill_router.py` 做 LLM 路由 + JSON 计划 + 二次解释，集成进 `/chat` SSE。代码生成兜底（`code_generator.py`）**零改动**，仅在 `skill=="fallback"` 时进入。

**技术栈：** Flask + SSE + Plotly + pandas + OpenAI 兼容 API。

---

## 执行进度（2026-06-02 更新）

- 计划已通过审批，处于**逐任务执行中**。
- **任务 1（契约层）✅ 已完成**：5 测试通过，已 commit（`65950b7`）。
- **任务 2–12 待执行**，下一步从任务 2（stats-skill）开始。

---

## Context（为什么做这个改造）

期末项目要求把数据分析能力封装为 AI 可调用的可复用 Skill（`SKILL.md` + 稳定脚本），强调"规则问答优先、复杂交给 LLM""先脚本确定性分析、再 LLM 解释结果"。当前 DataMind 走"LLM 生成任意 Python 代码 + 沙箱执行"路径，与该范式不一致。本改造采用**增量式**：技能层为主、代码生成兜底，既对齐要求与参考 demo 的文件组织，又保留已测试能力。设计规格见 `docs/superpowers/specs/2026-06-01-ai-qa-skill-refactor-design.md`。

## 关键事实（探索已核实）

- 分析类名为 **`Analyzer`**（`data/analyzer.py:74`，`Analyzer(df)`），非 `DataAnalyzer`。
- `Analyzer` 的图表方法返回**框架中立纯数组**（非 Plotly 图），故 skill 需自行用 plotly 构图。
- 序列化复用 `ai/code_generator.py:340` 的 `_plotly_fig_to_dict(fig)`（含 plotly 5.x bdata 解码）。
- `plotly>=5.0` 为硬依赖（`requirements.txt:5`），可模块顶层 import。
- `routes/api.py`：`_state()` 含 `df_clean`/`analyzer`/`chat_session`/`code_generator`/`profile`/`quality_score`/`df_raw`/`preprocess_report`；client=`cg.client`，model=`config.AI_MODEL`；`_sse_stream`（api.py:50）把 dict 序列化为 `data: {json}\n\n`。
- 前端 `static/js/sse-handler.js:199` 按 `msg.type` 分发，**未知 type 静默忽略**（default 分支）→ 新增 `route`/`evidence` 事件天然向后兼容。`static/js/chat.js` 用 `_formatResult(rows)`（chat.js:286）把 list-of-dict 渲染为表格，`_injectChart` 渲染图。
- 测试无 conftest，全用 `MagicMock`；JSON 计划 mock 范式见 `tests/test_plan_generator.py:36`（`message.content = json.dumps(...)`）；SSE 流 mock 见 `tests/test_api.py:269`。
- `DataProfiler(df).detect()`（`data/profiler.py:50`）返回含 `col_info`/`display_name`/`numeric_cols` 等 14 键；`QualityScorer().score(df_raw, df_clean, preprocess_report)`（`quality_scorer.py:59`）返回 `{total_score, grade, dimensions, suggestions}`（已在上传时算好存于 `state["quality_score"]`）。

## 文件结构

| 文件 | 职责 |
|---|---|
| `skills/_contract.py`（创建） | `SkillResult` 数据类 + `infer_schema`/`safe_col`/`safe_numeric_cols`/`fig_to_chart_dict` 工具 |
| `skills/<name>_skill/SKILL.md`（创建 ×6） | LLM 面向：frontmatter + JSON 计划规范 + 规则 |
| `skills/<name>_skill/<name>_skill.py`（创建 ×6） | `execute_<name>_plan(df, plan, context=None) -> SkillResult` |
| `skills/<name>_skill/__init__.py`（创建 ×6） | 空包标记 |
| `skills/__init__.py`（创建） | `SkillSpec`/`SKILLS` 注册表 + `load_catalog()` |
| `ai/skill_router.py`（创建） | `SkillRouter`：`route()` + `explain_stream()` |
| `routes/api.py`（修改 `/chat`，655-767） | 先路由，命中走确定性 + 二次解释，未命中走现有代码生成兜底 |
| `static/js/sse-handler.js`（修改 199-238） | 新增 `route`/`evidence` 分发 |
| `static/js/chat.js`（修改 54-114 handlers） | 新增 `onRoute`/`onEvidence` 渲染 |
| `tests/test_skill_*.py`（创建 ×7） | 6 skill 确定性测试 + router 测试 |
| `tests/test_api.py`（修改） | 新增 `/chat` 命中/兜底两路径集成测试 |

---

### 任务 1：技能契约层 `_contract.py`

**文件：**
- 创建：`skills/__init__.py`（临时占位，仅含 docstring，任务 8 再填注册表）、`skills/_contract.py`
- 测试：`tests/test_skill_contract.py`

- [ ] **步骤 1：创建包占位** `skills/__init__.py`

```python
"""运行时确定性技能包。注册表在任务 8 填充。来源：学生+AI"""
```

- [ ] **步骤 2：编写失败测试** `tests/test_skill_contract.py`

```python
import pandas as pd
import plotly.express as px
from skills._contract import (
    SkillResult, infer_schema, safe_col, safe_numeric_cols, fig_to_chart_dict,
)


def _df():
    return pd.DataFrame({"cat": ["A", "B", "A"], "val": [1, 2, 3], "price": [1.0, 2.5, 3.0]})


def test_infer_schema_types():
    schema = infer_schema(_df())
    assert schema["val"] == "number"
    assert schema["cat"].startswith("category/text")


def test_safe_col_falls_back_on_bad_name():
    assert safe_col(_df(), "missing", prefer_numeric=True) in ("val", "price")
    assert safe_col(_df(), "cat") == "cat"


def test_safe_numeric_cols_filters_and_defaults():
    assert safe_numeric_cols(_df(), ["val", "cat", "ghost"]) == ["val"]
    assert safe_numeric_cols(_df(), None) == ["val", "price"]


def test_fig_to_chart_dict_decodes_to_plain_json():
    fig = px.bar(_df(), x="cat", y="val")
    chart = fig_to_chart_dict(fig)
    assert isinstance(chart, dict) and "data" in chart and "layout" in chart
    assert "template" not in chart["layout"]
    assert chart["layout"]["paper_bgcolor"] == "rgba(0,0,0,0)"


def test_skill_result_defaults():
    r = SkillResult(answer="x", evidence=_df())
    assert r.chart is None and r.meta == {}
```

- [ ] **步骤 3：运行验证失败**

运行：`python -m pytest tests/test_skill_contract.py -q`
预期：FAIL（`ModuleNotFoundError: skills._contract`）

- [ ] **步骤 4：实现** `skills/_contract.py`

```python
"""
技能层公共契约与工具。

提供：
  - SkillResult        统一返回结构（answer/evidence/chart/meta）
  - infer_schema       从 DataFrame 推断字段 schema（供路由器注入 LLM）
  - safe_col           计划列名安全校验/降级
  - safe_numeric_cols  计划数值列筛选/降级
  - fig_to_chart_dict  Plotly Figure → 前端可用 dict（复用 code_generator 的 bdata 解码）

来源：学生+AI
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd


@dataclass
class SkillResult:
    answer: str
    evidence: pd.DataFrame
    chart: dict | None = None
    meta: dict = field(default_factory=dict)


def infer_schema(df: pd.DataFrame) -> dict[str, str]:
    """推断字段类型，供路由 LLM 选择列。"""
    schema: dict[str, str] = {}
    for col in df.columns:
        if pd.api.types.is_numeric_dtype(df[col]):
            schema[str(col)] = "number"
        elif pd.api.types.is_datetime64_any_dtype(df[col]):
            schema[str(col)] = "date"
        else:
            sample = df[col].dropna().astype(str).head(5).tolist()
            schema[str(col)] = "category/text, examples=" + ",".join(sample)
    return schema


def safe_col(df: pd.DataFrame, value: Any, prefer_numeric: bool = False) -> str:
    """校验计划列名；非法时降级到第一个（数值）列。"""
    if value in df.columns:
        return str(value)
    if prefer_numeric:
        nums = df.select_dtypes(include="number").columns
        if len(nums):
            return str(nums[0])
    return str(df.columns[0])


def safe_numeric_cols(df: pd.DataFrame, values: list | None, limit: int = 3) -> list[str]:
    """筛选计划中的有效数值列；空则取前 limit 个数值列。"""
    numeric = [str(c) for c in df.select_dtypes(include="number").columns]
    requested = [str(c) for c in (values or []) if c in df.columns and str(c) in numeric]
    return requested or numeric[:limit]


def fig_to_chart_dict(fig: Any) -> dict | None:
    """Plotly Figure → 前端可用 dict（复用 code_generator 的 bdata 解码 + 透明背景）。"""
    if fig is None:
        return None
    from ai.code_generator import _plotly_fig_to_dict
    chart = _plotly_fig_to_dict(fig)
    if isinstance(chart, dict) and isinstance(chart.get("layout"), dict):
        chart["layout"].pop("template", None)
        chart["layout"]["paper_bgcolor"] = "rgba(0,0,0,0)"
        chart["layout"]["plot_bgcolor"] = "rgba(0,0,0,0)"
    return chart
```

- [ ] **步骤 5：运行验证通过**

运行：`python -m pytest tests/test_skill_contract.py -q`
预期：PASS（5 passed）

- [ ] **步骤 6：Commit**

```bash
git add skills/__init__.py skills/_contract.py tests/test_skill_contract.py
git commit -m "feat(skills): 技能契约层 SkillResult + 公共校验/序列化工具"
```

---

### 任务 2：stats-skill（描述统计 + 分组聚合）

**文件：**
- 创建：`skills/stats_skill/__init__.py`、`skills/stats_skill/SKILL.md`、`skills/stats_skill/stats_skill.py`
- 测试：`tests/test_skill_stats.py`

- [ ] **步骤 1：创建** `skills/stats_skill/__init__.py`（内容：`"""stats-skill 包。来源：学生+AI"""`）与 `skills/stats_skill/SKILL.md`

```markdown
---
name: stats-skill
description: Convert a data question into a descriptive-statistics plan for tabular data. Use when the user asks for mean, median, variance, std, min, max, count, or grouped descriptive statistics.
---

# Stats Skill

You help a Python program choose descriptive statistics, not write code.

Return JSON only. Do not wrap it in Markdown:
\`\`\`json
{
  "metrics": ["mean", "median", "variance"],
  "columns": ["numeric column name"],
  "group_by": "category column name or null",
  "title": "short Chinese title",
  "answer": "one short Chinese sentence about the intended analysis"
}
\`\`\`

Rules:
- `metrics` items must be among: mean, median, variance, std, min, max, count.
- `columns` should prefer numeric columns; only use names present in the schema.
- Use `group_by` only when comparing groups/categories/regions/months; otherwise null.
- Do not output Python code.
```

- [ ] **步骤 2：编写失败测试** `tests/test_skill_stats.py`

```python
import pandas as pd
from skills.stats_skill.stats_skill import execute_stats_plan


def _df():
    return pd.DataFrame({"region": ["A", "B", "A", "B"], "sales": [10, 20, 30, 40]})


def test_stats_overall_mean():
    r = execute_stats_plan(_df(), {"metrics": ["mean"], "columns": ["sales"]})
    assert "column" in r.evidence.columns
    row = r.evidence.iloc[0]
    assert abs(float(row["mean"]) - 25.0) < 1e-6


def test_stats_grouped():
    r = execute_stats_plan(_df(), {"metrics": ["mean"], "columns": ["sales"], "group_by": "region"})
    assert "region" in r.evidence.columns
    assert any("sales_mean" == c for c in r.evidence.columns)


def test_stats_bad_column_falls_back():
    r = execute_stats_plan(_df(), {"metrics": ["mean"], "columns": ["ghost"]})
    assert len(r.evidence) >= 1  # 不抛异常，降级到数值列
    assert r.chart is None
```

- [ ] **步骤 3：运行验证失败**

运行：`python -m pytest tests/test_skill_stats.py -q` → FAIL（模块不存在）

- [ ] **步骤 4：实现** `skills/stats_skill/stats_skill.py`

```python
"""统计分析技能：描述统计 + 分组聚合。来源：学生+AI"""
from __future__ import annotations

import pandas as pd

from skills._contract import SkillResult, safe_numeric_cols

_SUPPORTED = {"mean", "median", "variance", "std", "min", "max", "count"}
_PANDAS_AGG = {"mean": "mean", "median": "median", "variance": "var",
               "std": "std", "min": "min", "max": "max", "count": "count"}
_INV = {v: k for k, v in _PANDAS_AGG.items()}


def _norm_metrics(values: list | None) -> list[str]:
    metrics = [str(m).lower() for m in (values or [])]
    metrics = [m for m in metrics if m in _SUPPORTED]
    return metrics or ["mean", "median", "variance"]


def execute_stats_plan(df: pd.DataFrame, plan: dict, context: dict | None = None) -> SkillResult:
    metrics = _norm_metrics(plan.get("metrics"))
    columns = safe_numeric_cols(df, plan.get("columns"))
    group_by = plan.get("group_by")
    if group_by not in df.columns:
        group_by = None
    title = str(plan.get("title") or "描述统计")

    work = df.copy()
    for c in columns:
        work[c] = pd.to_numeric(work[c], errors="coerce")
    aggs = [_PANDAS_AGG[m] for m in metrics]

    if group_by:
        grouped = work.groupby(group_by, dropna=False)[columns].agg(aggs)
        grouped.columns = [f"{c}_{_INV.get(a, a)}" for c, a in grouped.columns]
        evidence = grouped.reset_index().head(50)
        answer = f"已按 {group_by} 分组计算 {', '.join(columns)} 的 {', '.join(metrics)}。"
    else:
        evidence = work[columns].agg(aggs).T.reset_index()
        evidence = evidence.rename(columns={"index": "column", "var": "variance"})
        evidence = evidence.fillna("").head(50)
        answer = f"已计算 {', '.join(columns)} 的 {', '.join(metrics)}。"
    return SkillResult(answer=answer, evidence=evidence, chart=None, meta={"title": title})
```

- [ ] **步骤 5：运行验证通过** `python -m pytest tests/test_skill_stats.py -q` → PASS

- [ ] **步骤 6：Commit**

```bash
git add skills/stats_skill tests/test_skill_stats.py
git commit -m "feat(skills): stats-skill 描述统计与分组聚合"
```

---

### 任务 3：viz-skill（柱/折/散/饼图）

**文件：** 创建 `skills/viz_skill/{__init__.py, SKILL.md, viz_skill.py}`；测试 `tests/test_skill_viz.py`

- [ ] **步骤 1：创建** `__init__.py`（`"""viz-skill 包。来源：学生+AI"""`）与 `SKILL.md`

```markdown
---
name: viz-skill
description: Convert a data question into a visualization plan (bar/line/scatter/pie) for tabular data. Use when the user asks to compare, rank, trend by category, relate two numbers, or visualize a breakdown.
---

# Viz Skill

You help a Python program choose a chart, not write code.

Return JSON only. Do not wrap it in Markdown:
\`\`\`json
{
  "chart_type": "bar | line | scatter | pie",
  "x": "column name",
  "y": "numeric column name",
  "agg": "sum | mean | count | none",
  "title": "short Chinese chart title",
  "answer": "one short Chinese sentence"
}
\`\`\`

Rules:
- bar = category comparison; line = ordered/temporal; scatter = numeric relationship; pie = share of total.
- For scatter, set `agg` to none and pick two numeric columns.
- Only choose columns present in the schema. Do not output Python code.
```

- [ ] **步骤 2：编写失败测试** `tests/test_skill_viz.py`

```python
import pandas as pd
from skills.viz_skill.viz_skill import execute_viz_plan


def _df():
    return pd.DataFrame({"cat": ["A", "B", "A", "B"], "val": [10, 20, 30, 40]})


def test_viz_bar_chart_built():
    r = execute_viz_plan(_df(), {"chart_type": "bar", "x": "cat", "y": "val", "agg": "sum"})
    assert isinstance(r.chart, dict) and "data" in r.chart
    assert len(r.evidence) == 2  # 两个类别聚合


def test_viz_scatter_keeps_points():
    df = pd.DataFrame({"a": [1, 2, 3, 4], "b": [2, 4, 6, 8]})
    r = execute_viz_plan(df, {"chart_type": "scatter", "x": "a", "y": "b", "agg": "none"})
    assert r.chart is not None and len(r.evidence) == 4


def test_viz_bad_columns_fallback():
    r = execute_viz_plan(_df(), {"chart_type": "bar", "x": "ghost", "y": "ghost"})
    assert r.chart is not None  # 不抛异常
```

- [ ] **步骤 3：运行验证失败** → FAIL

- [ ] **步骤 4：实现** `skills/viz_skill/viz_skill.py`

```python
"""数据可视化技能：按字段类型生成柱/折/散/饼图。来源：学生+AI"""
from __future__ import annotations

import pandas as pd
import plotly.express as px

from skills._contract import SkillResult, safe_col, fig_to_chart_dict


def execute_viz_plan(df: pd.DataFrame, plan: dict, context: dict | None = None) -> SkillResult:
    chart_type = str(plan.get("chart_type", "bar")).lower()
    x = safe_col(df, plan.get("x"))
    y = safe_col(df, plan.get("y"), prefer_numeric=True)
    agg = str(plan.get("agg", "sum")).lower()
    title = str(plan.get("title") or f"{y} by {x}")

    cols = [x] if x == y else [x, y]
    work = df[cols].dropna().copy()

    if chart_type == "scatter":
        work[x] = pd.to_numeric(work[x], errors="coerce")
        work[y] = pd.to_numeric(work[y], errors="coerce")
        evidence = work.dropna().head(500)
        fig = px.scatter(evidence, x=x, y=y, title=title, opacity=0.7,
                         color_discrete_sequence=["#00e5ff"])
    elif chart_type == "pie":
        work[y] = pd.to_numeric(work[y], errors="coerce")
        evidence = (work.groupby(x, dropna=False)[y].sum().reset_index()
                    .sort_values(y, ascending=False).head(20))
        fig = px.pie(evidence, names=x, values=y, title=title)
    else:
        work[y] = pd.to_numeric(work[y], errors="coerce")
        if agg == "mean":
            evidence = work.groupby(x, dropna=False)[y].mean().reset_index()
        elif agg == "count":
            evidence = work.groupby(x, dropna=False)[y].count().reset_index()
        else:
            evidence = work.groupby(x, dropna=False)[y].sum().reset_index()
        evidence = evidence.sort_values(y, ascending=False).head(20)
        if chart_type == "line":
            evidence = evidence.sort_values(x)
            fig = px.line(evidence, x=x, y=y, title=title, markers=True)
        else:
            fig = px.bar(evidence, x=x, y=y, title=title)

    chart = fig_to_chart_dict(fig)
    return SkillResult(answer=f"已生成 {title}。", evidence=evidence, chart=chart,
                       meta={"title": title, "x_label": x, "y_label": y})
```

- [ ] **步骤 5：运行验证通过** → PASS

- [ ] **步骤 6：Commit**

```bash
git add skills/viz_skill tests/test_skill_viz.py
git commit -m "feat(skills): viz-skill 柱/折/散/饼图生成"
```

---

### 任务 4：trend-skill（时间序列重采样趋势）

**文件：** 创建 `skills/trend_skill/{__init__.py, SKILL.md, trend_skill.py}`；测试 `tests/test_skill_trend.py`

- [ ] **步骤 1：创建** `__init__.py`（`"""trend-skill 包。来源：学生+AI"""`）与 `SKILL.md`

```markdown
---
name: trend-skill
description: Convert a data question into a time-series trend plan. Use when the user asks how a numeric value changes over time, monthly/weekly/daily trends, or seasonality.
---

# Trend Skill

You help a Python program plan a time-series trend, not write code.

Return JSON only. Do not wrap it in Markdown:
\`\`\`json
{
  "date_col": "date/time column name",
  "value_col": "numeric column name",
  "agg": "sum | mean",
  "freq": "D | W | M | Q | Y",
  "title": "short Chinese title",
  "answer": "one short Chinese sentence"
}
\`\`\`

Rules:
- `date_col` must be a date/time column; `value_col` must be numeric.
- `freq`: D=day, W=week, M=month, Q=quarter, Y=year.
- Only choose columns present in the schema. Do not output Python code.
```

- [ ] **步骤 2：编写失败测试** `tests/test_skill_trend.py`

```python
import pandas as pd
from skills.trend_skill.trend_skill import execute_trend_plan


def _df():
    dates = pd.date_range("2024-01-01", periods=60, freq="D")
    return pd.DataFrame({"day": dates, "amt": range(60)})


def test_trend_monthly_resample():
    r = execute_trend_plan(_df(), {"date_col": "day", "value_col": "amt", "agg": "sum", "freq": "M"})
    assert r.chart is not None
    assert len(r.evidence) >= 2  # 跨 2-3 个月


def test_trend_no_valid_data_safe():
    df = pd.DataFrame({"x": ["a", "b"], "y": ["p", "q"]})
    r = execute_trend_plan(df, {"date_col": "x", "value_col": "y"})
    assert r.chart is None and "message" in r.evidence.columns
```

- [ ] **步骤 3：运行验证失败** → FAIL

- [ ] **步骤 4：实现** `skills/trend_skill/trend_skill.py`

```python
"""趋势分析技能：时间序列重采样趋势。来源：学生+AI"""
from __future__ import annotations

import pandas as pd
import plotly.express as px

from skills._contract import SkillResult, safe_col, fig_to_chart_dict

_FREQ_MAP = {"D": "D", "W": "W", "M": "ME", "Q": "QE", "Y": "YE"}


def _pick_date_col(df: pd.DataFrame, value) -> str:
    if value in df.columns:
        return str(value)
    for c in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[c]):
            return str(c)
    for c in df.columns:
        try:
            if pd.to_datetime(df[c], errors="coerce").notna().mean() > 0.8:
                return str(c)
        except Exception:
            continue
    return str(df.columns[0])


def execute_trend_plan(df: pd.DataFrame, plan: dict, context: dict | None = None) -> SkillResult:
    date_col = _pick_date_col(df, plan.get("date_col"))
    value_col = safe_col(df, plan.get("value_col"), prefer_numeric=True)
    agg = str(plan.get("agg", "sum")).lower()
    freq_key = str(plan.get("freq", "M")).upper()
    freq = _FREQ_MAP.get(freq_key, "ME")
    title = str(plan.get("title") or f"{value_col} 趋势")

    work = df[[date_col, value_col]].copy()
    work[date_col] = pd.to_datetime(work[date_col], errors="coerce")
    work[value_col] = pd.to_numeric(work[value_col], errors="coerce")
    work = work.dropna()
    if work.empty:
        evidence = pd.DataFrame({"message": ["无可用于趋势分析的有效日期/数值数据。"]})
        return SkillResult(answer="无法计算趋势：缺少有效的日期或数值列。",
                           evidence=evidence, chart=None, meta={"title": title})

    series = work.set_index(date_col).resample(freq)[value_col]
    series = series.mean() if agg == "mean" else series.sum()
    evidence = series.reset_index().dropna()
    evidence.columns = [date_col, value_col]
    fig = px.line(evidence, x=date_col, y=value_col, title=title, markers=True)
    chart = fig_to_chart_dict(fig)
    return SkillResult(answer=f"已按 {freq_key} 频率对 {value_col} 做 {agg} 聚合趋势分析。",
                       evidence=evidence, chart=chart,
                       meta={"title": title, "x_label": date_col, "y_label": value_col})
```

- [ ] **步骤 5：运行验证通过** → PASS

- [ ] **步骤 6：Commit**

```bash
git add skills/trend_skill tests/test_skill_trend.py
git commit -m "feat(skills): trend-skill 时间序列趋势分析"
```

---

### 任务 5：correlation-skill（相关矩阵 + 热力图）

**文件：** 创建 `skills/correlation_skill/{__init__.py, SKILL.md, correlation_skill.py}`；测试 `tests/test_skill_correlation.py`

- [ ] **步骤 1：创建** `__init__.py`（`"""correlation-skill 包。来源：学生+AI"""`）与 `SKILL.md`

```markdown
---
name: correlation-skill
description: Convert a data question into a correlation plan among numeric columns. Use when the user asks about relationships, correlation, or which variables move together.
---

# Correlation Skill

You help a Python program plan a correlation analysis, not write code.

Return JSON only. Do not wrap it in Markdown:
\`\`\`json
{
  "columns": ["numeric column names, 2 or more"],
  "method": "pearson | spearman | kendall",
  "title": "short Chinese title",
  "answer": "one short Chinese sentence"
}
\`\`\`

Rules:
- Use only numeric columns present in the schema (2+).
- Default method is pearson. Do not output Python code.
```

- [ ] **步骤 2：编写失败测试** `tests/test_skill_correlation.py`

```python
import pandas as pd
from skills.correlation_skill.correlation_skill import execute_correlation_plan


def _df():
    return pd.DataFrame({"a": [1, 2, 3, 4], "b": [2, 4, 6, 8], "c": [9, 7, 5, 3]})


def test_correlation_matrix_and_chart():
    r = execute_correlation_plan(_df(), {"columns": ["a", "b", "c"], "method": "pearson"})
    assert r.chart is not None and "column" in r.evidence.columns
    # a 与 b 完全正相关
    arow = r.evidence.set_index("column").loc["a"]
    assert abs(float(arow["b"]) - 1.0) < 1e-6


def test_correlation_insufficient_numeric_safe():
    df = pd.DataFrame({"only": [1, 2, 3], "txt": ["x", "y", "z"]})
    r = execute_correlation_plan(df, {"columns": ["only"]})
    assert r.chart is None and "message" in r.evidence.columns
```

- [ ] **步骤 3：运行验证失败** → FAIL

- [ ] **步骤 4：实现** `skills/correlation_skill/correlation_skill.py`

```python
"""相关性分析技能：数值列相关矩阵 + 热力图。来源：学生+AI"""
from __future__ import annotations

import pandas as pd
import plotly.express as px

from skills._contract import SkillResult, safe_numeric_cols, fig_to_chart_dict


def execute_correlation_plan(df: pd.DataFrame, plan: dict, context: dict | None = None) -> SkillResult:
    method = str(plan.get("method", "pearson")).lower()
    if method not in ("pearson", "spearman", "kendall"):
        method = "pearson"
    columns = safe_numeric_cols(df, plan.get("columns"), limit=8)
    title = str(plan.get("title") or "相关性热力图")

    if len(columns) < 2:
        evidence = pd.DataFrame({"message": ["可用数值列不足 2 个，无法计算相关性。"]})
        return SkillResult(answer="可用数值列不足 2 个，无法计算相关性。",
                           evidence=evidence, chart=None, meta={"title": title})

    work = df[columns].apply(pd.to_numeric, errors="coerce")
    corr = work.corr(method=method).round(4)
    evidence = corr.reset_index().rename(columns={"index": "column"})
    fig = px.imshow(corr, text_auto=True, aspect="auto", title=title,
                    color_continuous_scale="RdBu_r", zmin=-1, zmax=1)
    chart = fig_to_chart_dict(fig)
    return SkillResult(answer=f"已用 {method} 方法计算 {len(columns)} 个数值列的相关性矩阵。",
                       evidence=evidence, chart=chart, meta={"title": title})
```

- [ ] **步骤 5：运行验证通过** → PASS

- [ ] **步骤 6：Commit**

```bash
git add skills/correlation_skill tests/test_skill_correlation.py
git commit -m "feat(skills): correlation-skill 相关矩阵与热力图"
```

---

### 任务 6：distribution-skill（直方图 / 箱线图）

**文件：** 创建 `skills/distribution_skill/{__init__.py, SKILL.md, distribution_skill.py}`；测试 `tests/test_skill_distribution.py`

- [ ] **步骤 1：创建** `__init__.py`（`"""distribution-skill 包。来源：学生+AI"""`）与 `SKILL.md`

```markdown
---
name: distribution-skill
description: Convert a data question into a distribution plan for one numeric column (histogram or box plot). Use when the user asks about distribution, spread, outliers, or the shape of a single numeric variable.
---

# Distribution Skill

You help a Python program plan a single-column distribution, not write code.

Return JSON only. Do not wrap it in Markdown:
\`\`\`json
{
  "column": "numeric column name",
  "kind": "hist | box",
  "bins": 30,
  "title": "short Chinese title",
  "answer": "one short Chinese sentence"
}
\`\`\`

Rules:
- `column` must be numeric and present in the schema.
- `kind`: hist=histogram, box=box plot. Do not output Python code.
```

- [ ] **步骤 2：编写失败测试** `tests/test_skill_distribution.py`

```python
import pandas as pd
from skills.distribution_skill.distribution_skill import execute_distribution_plan


def _df():
    return pd.DataFrame({"score": [1, 2, 2, 3, 3, 3, 4, 4, 5], "label": list("abcabcabc")})


def test_distribution_hist():
    r = execute_distribution_plan(_df(), {"column": "score", "kind": "hist", "bins": 5})
    assert r.chart is not None and "统计量" in r.evidence.columns


def test_distribution_box():
    r = execute_distribution_plan(_df(), {"column": "score", "kind": "box"})
    assert r.chart is not None


def test_distribution_non_numeric_safe():
    r = execute_distribution_plan(_df(), {"column": "label"})
    # label 被降级为数值列 score（safe_col prefer_numeric），仍应产出
    assert r.chart is not None
```

- [ ] **步骤 3：运行验证失败** → FAIL

- [ ] **步骤 4：实现** `skills/distribution_skill/distribution_skill.py`

```python
"""分布分析技能：直方图 / 箱线图。来源：学生+AI"""
from __future__ import annotations

import pandas as pd
import plotly.express as px

from skills._contract import SkillResult, safe_col, fig_to_chart_dict


def execute_distribution_plan(df: pd.DataFrame, plan: dict, context: dict | None = None) -> SkillResult:
    column = safe_col(df, plan.get("column"), prefer_numeric=True)
    kind = str(plan.get("kind", "hist")).lower()
    try:
        bins = int(plan.get("bins") or 30)
    except (TypeError, ValueError):
        bins = 30
    title = str(plan.get("title") or f"{column} 分布")

    series = pd.to_numeric(df[column], errors="coerce").dropna()
    if series.empty:
        evidence = pd.DataFrame({"message": [f"{column} 无有效数值，无法分析分布。"]})
        return SkillResult(answer=f"{column} 列无有效数值数据。",
                           evidence=evidence, chart=None, meta={"title": title})

    evidence = series.describe().round(4).reset_index()
    evidence.columns = ["统计量", column]
    if kind == "box":
        fig = px.box(series, y=series.name or column, title=title)
    else:
        fig = px.histogram(series, nbins=bins, title=title)
    chart = fig_to_chart_dict(fig)
    kind_cn = "箱线图" if kind == "box" else "直方图"
    return SkillResult(answer=f"已生成 {column} 的{kind_cn}分布。",
                       evidence=evidence, chart=chart, meta={"title": title, "x_label": column})
```

> 注：`px.box(series, ...)` 对单 Series 用 `series.name`；若为匿名 Series，`px.box(pd.DataFrame({column: series}), y=column)` 更稳——实现时若测试 `test_distribution_box` 失败，改用 `px.box(df[[column]].apply(pd.to_numeric, errors="coerce").dropna(), y=column, title=title)`。

- [ ] **步骤 5：运行验证通过** → PASS（若 box 报错按上注修正后再跑）

- [ ] **步骤 6：Commit**

```bash
git add skills/distribution_skill tests/test_skill_distribution.py
git commit -m "feat(skills): distribution-skill 直方图与箱线图"
```

---

### 任务 7：profile-skill（概览 / schema / 质量）

**文件：** 创建 `skills/profile_skill/{__init__.py, SKILL.md, profile_skill.py}`；测试 `tests/test_skill_profile.py`

- [ ] **步骤 1：创建** `__init__.py`（`"""profile-skill 包。来源：学生+AI"""`）与 `SKILL.md`

```markdown
---
name: profile-skill
description: Convert a data question into a dataset-profile plan (overview, schema, or quality). Use when the user asks what the dataset looks like, what columns/types exist, how many rows, or about data quality and missing values.
---

# Profile Skill

You help a Python program plan a dataset profile, not write code.

Return JSON only. Do not wrap it in Markdown:
\`\`\`json
{
  "scope": "overview | schema | quality",
  "answer": "one short Chinese sentence"
}
\`\`\`

Rules:
- overview = rows/cols/type summary; schema = per-column types/samples; quality = quality scores / missing values.
- Do not output Python code.
```

- [ ] **步骤 2：编写失败测试** `tests/test_skill_profile.py`

```python
import pandas as pd
from skills.profile_skill.profile_skill import execute_profile_plan


def _df():
    return pd.DataFrame({"cat": ["A", "B", "A"], "val": [1, 2, 3]})


def test_profile_overview():
    r = execute_profile_plan(_df(), {"scope": "overview"})
    assert "项目" in r.evidence.columns and len(r.evidence) >= 4


def test_profile_schema():
    r = execute_profile_plan(_df(), {"scope": "schema"})
    assert "列名" in r.evidence.columns and len(r.evidence) == 2


def test_profile_quality_uses_context():
    ctx = {"quality_score": {"total_score": 88, "grade": "B",
            "dimensions": {"completeness": {"score": 90, "detail": "无缺失"}},
            "suggestions": ["保持"]}}
    r = execute_profile_plan(_df(), {"scope": "quality"}, ctx)
    assert "维度" in r.evidence.columns and "88" in r.answer
```

- [ ] **步骤 3：运行验证失败** → FAIL

- [ ] **步骤 4：实现** `skills/profile_skill/profile_skill.py`

```python
"""数据画像技能：概览 / schema / 质量。来源：学生+AI"""
from __future__ import annotations

import pandas as pd

from skills._contract import SkillResult
from data.profiler import DataProfiler


def execute_profile_plan(df: pd.DataFrame, plan: dict, context: dict | None = None) -> SkillResult:
    scope = str(plan.get("scope", "overview")).lower()
    context = context or {}
    prof = context.get("profile") or DataProfiler(df).detect()

    if scope == "schema":
        rows = [{"列名": c, "类型": info.get("dtype", ""),
                 "唯一值": info.get("nunique", ""),
                 "样本": ", ".join(info.get("samples", [])[:3])}
                for c, info in prof.get("col_info", {}).items()]
        evidence = pd.DataFrame(rows) if rows else pd.DataFrame({"列名": list(map(str, df.columns))})
        answer = f"数据集含 {len(df)} 行 {len(df.columns)} 列，类型为「{prof.get('display_name', '')}」。"
        return SkillResult(answer=answer, evidence=evidence, meta={"title": "字段 Schema"})

    if scope == "quality":
        qs = context.get("quality_score")
        if qs:
            rows = [{"维度": k, "得分": v.get("score"), "说明": v.get("detail", "")}
                    for k, v in qs.get("dimensions", {}).items()]
            evidence = pd.DataFrame(rows)
            answer = (f"数据质量总分 {qs.get('total_score')}（{qs.get('grade')} 级）。"
                      + " ".join(qs.get("suggestions", [])[:2]))
        else:
            miss = df.isna().sum()
            evidence = miss[miss > 0].reset_index()
            evidence.columns = ["列", "缺失数"]
            if evidence.empty:
                evidence = pd.DataFrame({"列": ["(无缺失)"], "缺失数": [0]})
            answer = "（未预计算质量评分）已给出缺失值概览。"
        return SkillResult(answer=answer, evidence=evidence, meta={"title": "数据质量"})

    rows = [
        {"项目": "行数", "值": len(df)},
        {"项目": "列数", "值": len(df.columns)},
        {"项目": "画像类型", "值": prof.get("display_name", "")},
        {"项目": "数值列数", "值": len(prof.get("numeric_cols", []))},
        {"项目": "分类列数", "值": len(prof.get("categorical_cols", []))},
        {"项目": "含日期列", "值": "是" if prof.get("has_date") else "否"},
    ]
    evidence = pd.DataFrame(rows)
    answer = prof.get("description", "") or f"数据集含 {len(df)} 行 {len(df.columns)} 列。"
    return SkillResult(answer=answer, evidence=evidence, meta={"title": "数据概览"})
```

- [ ] **步骤 5：运行验证通过** → PASS

- [ ] **步骤 6：Commit**

```bash
git add skills/profile_skill tests/test_skill_profile.py
git commit -m "feat(skills): profile-skill 概览/schema/质量画像"
```

---

### 任务 8：技能注册表 `skills/__init__.py`

**文件：** 修改 `skills/__init__.py`；测试 `tests/test_skill_registry.py`

- [ ] **步骤 1：编写失败测试** `tests/test_skill_registry.py`

```python
from skills import SKILLS, load_catalog


def test_registry_has_six_skills():
    expected = {"stats-skill", "viz-skill", "trend-skill",
                "correlation-skill", "distribution-skill", "profile-skill"}
    assert expected.issubset(set(SKILLS.keys()))


def test_every_spec_executable_and_has_skillmd():
    for spec in SKILLS.values():
        assert callable(spec.execute)
        assert spec.path.exists()


def test_catalog_concatenates_skillmd():
    catalog = load_catalog()
    assert "stats-skill" in catalog and "viz-skill" in catalog
    assert "Return JSON only" in catalog
```

- [ ] **步骤 2：运行验证失败** → FAIL（`ImportError: cannot import name 'SKILLS'`）

- [ ] **步骤 3：实现** 覆盖 `skills/__init__.py`

```python
"""
运行时确定性技能注册表。

每个技能 = 一个子目录（SKILL.md + <name>_skill.py）。SkillRouter 注入所有
SKILL.md，由 LLM 选择技能并生成 JSON 计划，本地脚本确定性执行；未命中时
由 /chat 降级到代码生成兜底。

来源：学生+AI
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from skills._contract import SkillResult
from skills.stats_skill.stats_skill import execute_stats_plan
from skills.viz_skill.viz_skill import execute_viz_plan
from skills.trend_skill.trend_skill import execute_trend_plan
from skills.correlation_skill.correlation_skill import execute_correlation_plan
from skills.distribution_skill.distribution_skill import execute_distribution_plan
from skills.profile_skill.profile_skill import execute_profile_plan

_ROOT = Path(__file__).parent


@dataclass(frozen=True)
class SkillSpec:
    name: str
    title: str
    path: Path
    execute: Callable[..., SkillResult]


SKILLS: dict[str, SkillSpec] = {
    "stats-skill": SkillSpec("stats-skill", "统计分析",
                             _ROOT / "stats_skill" / "SKILL.md", execute_stats_plan),
    "viz-skill": SkillSpec("viz-skill", "数据可视化",
                           _ROOT / "viz_skill" / "SKILL.md", execute_viz_plan),
    "trend-skill": SkillSpec("trend-skill", "趋势分析",
                             _ROOT / "trend_skill" / "SKILL.md", execute_trend_plan),
    "correlation-skill": SkillSpec("correlation-skill", "相关性分析",
                                   _ROOT / "correlation_skill" / "SKILL.md", execute_correlation_plan),
    "distribution-skill": SkillSpec("distribution-skill", "分布分析",
                                    _ROOT / "distribution_skill" / "SKILL.md", execute_distribution_plan),
    "profile-skill": SkillSpec("profile-skill", "数据画像",
                               _ROOT / "profile_skill" / "SKILL.md", execute_profile_plan),
}


def load_catalog() -> str:
    """拼接所有 SKILL.md，注入路由 system prompt。"""
    docs = [f"## {spec.name}\n\n{spec.path.read_text(encoding='utf-8')}"
            for spec in SKILLS.values()]
    return "\n\n---\n\n".join(docs)
```

- [ ] **步骤 4：运行验证通过** `python -m pytest tests/test_skill_registry.py -q` → PASS

- [ ] **步骤 5：Commit**

```bash
git add skills/__init__.py tests/test_skill_registry.py
git commit -m "feat(skills): 技能注册表 SKILLS + load_catalog"
```

---

### 任务 9：技能路由器 `ai/skill_router.py`

**文件：** 创建 `ai/skill_router.py`；测试 `tests/test_skill_router.py`

- [ ] **步骤 1：编写失败测试** `tests/test_skill_router.py`

```python
import json
from unittest.mock import MagicMock

import pandas as pd

from ai.skill_router import SkillRouter, _extract_json


def _df():
    return pd.DataFrame({"region": ["A", "B"], "sales": [10, 20]})


def _client_returning(content: str):
    client = MagicMock()
    resp = MagicMock()
    resp.choices = [MagicMock()]
    resp.choices[0].message.content = content
    client.chat.completions.create.return_value = resp
    return client


def test_extract_json_variants():
    assert _extract_json('{"skill":"stats-skill"}')["skill"] == "stats-skill"
    assert _extract_json('```json\n{"skill":"viz-skill"}\n```')["skill"] == "viz-skill"
    assert _extract_json("noise {\"skill\":\"x\"} tail")["skill"] == "x"


def test_route_selects_known_skill():
    content = json.dumps({"skill": "stats-skill", "plan": {"metrics": ["mean"]}, "reason": "求均值"})
    router = SkillRouter(_client_returning(content), "gpt-4o-mini")
    route = router.route("销售额均值", _df())
    assert route["skill"] == "stats-skill" and route["plan"]["metrics"] == ["mean"]


def test_route_falls_back_on_bad_json():
    router = SkillRouter(_client_returning("抱歉我无法回答"), "gpt-4o-mini")
    route = router.route("天气如何", _df())
    assert route["skill"] == "fallback"


def test_route_falls_back_on_api_error():
    client = MagicMock()
    client.chat.completions.create.side_effect = Exception("timeout")
    router = SkillRouter(client, "gpt-4o-mini")
    assert router.route("x", _df())["skill"] == "fallback"


def test_explain_stream_yields_tokens():
    client = MagicMock()
    chunks = []
    for tok in ["销售", "额", "最高"]:
        ck = MagicMock(); ck.choices = [MagicMock()]; ck.choices[0].delta.content = tok
        chunks.append(ck)
    client.chat.completions.create.return_value = chunks
    router = SkillRouter(client, "gpt-4o-mini")
    out = "".join(router.explain_stream("q", "统计分析", _df(), "提示"))
    assert out == "销售额最高"
```

- [ ] **步骤 2：运行验证失败** → FAIL

- [ ] **步骤 3：实现** `ai/skill_router.py`

```python
"""
技能路由器：LLM 选择技能 + 生成 JSON 计划 + 基于证据二次解释。

第 1 次调用：route() 注入所有 SKILL.md，返回 {skill, plan, reason}。
第 2 次调用：explain_stream() 基于确定性脚本算出的证据表流式生成中文解释。

来源：学生+AI
"""
from __future__ import annotations

import json
import re
from typing import Any

import pandas as pd

from skills import SKILLS, load_catalog
from skills._contract import infer_schema


def _extract_json(text: str) -> dict | None:
    """从 LLM 回复中提取 JSON 对象（容错：裸 JSON / ```json``` / 文本夹带）。"""
    if not text:
        return None
    try:
        obj = json.loads(text.strip())
        if isinstance(obj, dict):
            return obj
    except (json.JSONDecodeError, AttributeError):
        pass
    m = re.search(r"```(?:json)?\s*\n(.*?)\n```", text, re.DOTALL)
    if m:
        try:
            obj = json.loads(m.group(1))
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            obj = json.loads(m.group(0))
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass
    return None


class SkillRouter:
    def __init__(self, client: Any, model: str) -> None:
        self.client = client
        self.model = model

    def _options(self) -> str:
        return " | ".join([*SKILLS.keys(), "fallback"])

    def route(self, question: str, df: pd.DataFrame) -> dict:
        """第 1 次 LLM 调用：选择技能并生成 JSON 计划。失败时返回 fallback。"""
        schema = infer_schema(df)
        sample = df.head(5).to_dict(orient="records")
        system = (
            "你是数据分析 skill 路由器。根据用户问题从本地 skills 中选择最合适的一个，"
            "并为该 skill 输出可执行 JSON 计划；没有任何 skill 适合时选择 fallback。"
            "不要写 Python 代码，不要输出 Markdown，只返回 JSON。\n\n"
            "返回格式：\n"
            f'{{"skill": "{self._options()}", "plan": {{...}}, "reason": "简短中文理由"}}'
            "\n\n可用 skills:\n\n" + load_catalog()
        )
        user = (
            f"字段 schema:\n{json.dumps(schema, ensure_ascii=False)}\n\n"
            f"数据样例:\n{json.dumps(sample, ensure_ascii=False, default=str)}\n\n"
            f"用户问题: {question}"
        )
        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "system", "content": system},
                          {"role": "user", "content": user}],
                temperature=0.1,
                max_tokens=600,
            )
            content = resp.choices[0].message.content or ""
            route = _extract_json(content)
        except Exception:
            route = None
        if not route or "skill" not in route:
            return {"skill": "fallback", "plan": {}, "reason": "路由失败，转代码生成兜底"}
        route.setdefault("plan", {})
        route.setdefault("reason", "")
        return route

    def explain_stream(self, question: str, skill_title: str,
                       evidence: pd.DataFrame, answer_hint: str):
        """第 2 次 LLM 调用：基于证据表流式生成中文解释（逐 token yield）。"""
        try:
            evidence_text = evidence.head(30).to_string(index=False)
        except Exception:
            evidence_text = str(evidence)
        system = (
            "你是数据分析助教。下面是确定性脚本基于真实数据算出的证据表。"
            "请用简洁中文解读结论，只依据证据表、不要编造数据、不要写代码。"
        )
        user = (
            f"用户问题：{question}\n使用的分析：{skill_title}\n"
            f"脚本结论：{answer_hint}\n证据表：\n{evidence_text}"
        )
        stream = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}],
            temperature=0.3, max_tokens=800, stream=True,
        )
        for chunk in stream:
            try:
                delta = chunk.choices[0].delta
                if delta and getattr(delta, "content", None):
                    yield delta.content
            except (AttributeError, IndexError):
                continue
```

- [ ] **步骤 4：运行验证通过** `python -m pytest tests/test_skill_router.py -q` → PASS

- [ ] **步骤 5：Commit**

```bash
git add ai/skill_router.py tests/test_skill_router.py
git commit -m "feat(ai): SkillRouter 路由+JSON计划+证据二次解释"
```

---

### 任务 10：`/chat` 集成（技能优先 + 代码生成兜底）

**文件：** 修改 `routes/api.py`（`/chat` 端点 655-767 与导入区）；测试 `tests/test_api.py`（新增）

**思路：** 把现有代码生成流提取为内部生成器 `_codegen_stream(messages)`（逻辑**逐行照搬**当前 718-757 行），新增技能路由前置分支。

- [ ] **步骤 1：编写失败测试** 追加到 `tests/test_api.py`

```python
def test_chat_skill_path(client, loaded_state, monkeypatch):
    """命中技能：路由返回 JSON 计划 → 确定性执行 → 证据/图/解释流。"""
    import routes.api as api
    import json as _json
    from unittest.mock import MagicMock

    # 1) 路由调用返回 JSON；2) explain_stream 返回 token chunks
    route_resp = MagicMock()
    route_resp.choices = [MagicMock()]
    route_resp.choices[0].message.content = _json.dumps(
        {"skill": "stats-skill", "plan": {"metrics": ["mean"], "columns": ["Quantity"]}, "reason": "均值"})
    tok = MagicMock(); tok.choices = [MagicMock()]; tok.choices[0].delta.content = "结论"
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = [route_resp, [tok]]
    mock_cg = MagicMock(); mock_cg.client = mock_client
    api.app_state["code_generator"] = mock_cg

    resp = client.post("/api/chat?stream=true", json={"question": "Quantity 均值"})
    body = resp.get_data(as_text=True)
    assert "\"type\": \"route\"" in body
    assert "\"type\": \"evidence\"" in body
    assert "结论" in body


def test_chat_fallback_path(client, loaded_state, monkeypatch):
    """未命中：路由返回 fallback → 走现有代码生成流。"""
    import routes.api as api
    from unittest.mock import MagicMock

    route_resp = MagicMock(); route_resp.choices = [MagicMock()]
    route_resp.choices[0].message.content = "无法路由"  # → fallback
    delta = MagicMock(); delta.choices = [MagicMock()]; delta.choices[0].delta.content = "普通回答"
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = [route_resp, [delta]]
    mock_cg = MagicMock(); mock_cg.client = mock_client
    mock_cg.extract_code.return_value = ""  # 无代码块
    mock_cg.validate_code.return_value = True
    api.app_state["code_generator"] = mock_cg

    resp = client.post("/api/chat?stream=true", json={"question": "你好"})
    body = resp.get_data(as_text=True)
    assert "普通回答" in body
```

- [ ] **步骤 2：运行验证失败**

运行：`python -m pytest tests/test_api.py::test_chat_skill_path -q` → FAIL

- [ ] **步骤 3：实现** — 在 `routes/api.py` 顶部导入区新增：

```python
from ai.skill_router import SkillRouter
from skills import SKILLS
```

- [ ] **步骤 4：实现** — 替换 `chat()` 中 `use_stream` 之后的 SSE 段（即当前 693-767 行的 `_chat_stream` 定义与 `return`）为下列结构（**`_codegen_stream` 内部逻辑与原 718-757 行一致**）：

```python
    router = SkillRouter(cg.client, config.AI_MODEL)
    skill_context = {
        "profile": state.get("profile"),
        "quality_score": state.get("quality_score"),
        "df_raw": state.get("df_raw"),
        "preprocess_report": state.get("preprocess_report"),
    }
    messages = list(context) + [{"role": "user", "content": question}]

    def _codegen_stream():
        """现有代码生成兜底流（逻辑照搬原实现）。"""
        full_text = ""
        stream = cg.client.chat.completions.create(
            model=config.AI_MODEL, messages=messages, temperature=0.2,
            max_tokens=config.AI_MAX_TOKENS, stream=True, timeout=config.AI_REQUEST_TIMEOUT,
        )
        for chunk in stream:
            try:
                delta = chunk.choices[0].delta
                if delta and getattr(delta, "content", None):
                    full_text += delta.content
                    yield {"type": "text_delta", "content": delta.content}
            except (AttributeError, IndexError):
                continue
        code = cg.extract_code(full_text)
        if code:
            if not cg.validate_code(code):
                yield {"type": "error", "message": "代码包含危险操作，已被拒绝执行"}
            else:
                yield {"type": "code_complete", "code": code}
                result_queue: queue.Queue = queue.Queue()

                def _run_code():
                    try:
                        result_queue.put(("ok", cg.execute_safe(code, df)))
                    except Exception as exc:
                        result_queue.put(("err", str(exc)))

                threading.Thread(target=_run_code, daemon=True).start()
                elapsed, exec_result = 0, None
                while elapsed < config.CODE_EXEC_TIMEOUT:
                    try:
                        status, data = result_queue.get(timeout=1.0)
                        if status == "ok":
                            exec_result = data
                        else:
                            yield {"type": "error", "message": f"代码执行异常：{data}"}
                        break
                    except queue.Empty:
                        elapsed += 1
                        yield {"type": "heartbeat"}
                if exec_result is None:
                    yield {"type": "error", "message": f"代码执行超时（{config.CODE_EXEC_TIMEOUT}s）"}
                else:
                    yield {"type": "exec_result", "success": exec_result["success"],
                           "result": exec_result.get("result"), "stdout": exec_result.get("stdout"),
                           "error": exec_result.get("error")}
                    if exec_result.get("chart"):
                        yield {"type": "chart", "data": exec_result["chart"]}
        if session:
            session.add_message("user", question)
            session.add_message("assistant", full_text)

    def _chat_stream():
        try:
            route = router.route(question, df)
            skill_name = str(route.get("skill", "fallback"))
            spec = SKILLS.get(skill_name)
            if spec is not None:
                yield {"type": "route", "skill": skill_name, "title": spec.title,
                       "reason": route.get("reason", ""), "plan": route.get("plan", {})}
                try:
                    result = spec.execute(df, route.get("plan", {}), skill_context)
                except Exception as exc:
                    yield {"type": "route", "skill": "fallback", "reason": f"技能执行失败：{exc}"}
                    yield from _codegen_stream()
                    yield {"type": "done"}
                    return
                yield {"type": "evidence",
                       "columns": [str(c) for c in result.evidence.columns],
                       "rows": _df_to_records(result.evidence, 50)}
                if result.chart:
                    yield {"type": "chart", "data": result.chart}
                full_text = ""
                for token in router.explain_stream(question, spec.title, result.evidence, result.answer):
                    full_text += token
                    yield {"type": "text_delta", "content": token}
                if not full_text:
                    full_text = result.answer
                    yield {"type": "text_delta", "content": result.answer}
                if session:
                    session.add_message("user", question)
                    session.add_message("assistant", full_text)
            else:
                yield from _codegen_stream()
        except Exception as exc:
            yield {"type": "error", "message": str(exc)}
        yield {"type": "done"}

    return _sse_stream(_chat_stream)
```

> 注：非流路径（`?stream=false`，原 685-691 行）保持不变。`queue`/`threading`/`config` 已在文件顶部导入（原实现即用）。

- [ ] **步骤 5：运行验证通过**

运行：`python -m pytest tests/test_api.py -q`
预期：PASS（含新增 2 测试 + 原有 chat 测试不回归）

- [ ] **步骤 6：Commit**

```bash
git add routes/api.py tests/test_api.py
git commit -m "feat(api): /chat 技能优先路由 + 代码生成兜底集成"
```

---

### 任务 11：前端渲染 `route` / `evidence` 事件

**文件：** 修改 `static/js/sse-handler.js`（switch 199-238）、`static/js/chat.js`（handlers 54-114 + 新增注入函数）

> 无前端单测框架；本任务靠任务 12 的手动端到端验证。未知事件已优雅降级，故此任务为体验增强。

- [ ] **步骤 1：** `static/js/sse-handler.js` 的 `switch (msg.type)` 内，`case 'chart':` 之后新增：

```javascript
        case 'route':
            if (handlers.onRoute) handlers.onRoute(msg);
            break;
        case 'evidence':
            if (handlers.onEvidence) handlers.onEvidence(msg);
            break;
```

- [ ] **步骤 2：** `static/js/chat.js` 的 `sendChatMessage()` handlers 对象（约 54-114）中新增两个回调：

```javascript
        onRoute: (msg) => {
            if (msg.skill === 'fallback') return;
            const badge = document.createElement('div');
            badge.className = 'skill-route-badge';
            badge.textContent = `🧩 已选择技能：${msg.title || msg.skill}` +
                (msg.reason ? ` · ${msg.reason}` : '');
            bubble.querySelector('.chat-msg-body')?.before(badge);
        },
        onEvidence: (msg) => {
            _injectEvidence(bubble, msg.rows || []);
        },
```

- [ ] **步骤 3：** `static/js/chat.js` 末尾新增注入函数（复用现有 `_formatResult` 的表格能力）：

```javascript
// 渲染技能证据表（复用 _formatResult 的 list-of-dict 表格）。来源：学生+AI
function _injectEvidence(bubble, rows) {
    if (!rows || !rows.length) return;
    const anchor = bubble.querySelector('.exec-result-inline')
        || bubble.querySelector('.chat-msg-body') || bubble;
    let box = bubble.querySelector('.skill-evidence-inline');
    if (!box) {
        box = document.createElement('div');
        box.className = 'skill-evidence-inline exec-result-inline';
        anchor.appendChild(box);
    }
    box.innerHTML = _formatResult(rows);
}
```

- [ ] **步骤 4：** （可选样式）`static/css/*.css` 或 `templates/base.html` 内联样式新增 `.skill-route-badge`（小号、青色徽章）。若时间紧可跳过，默认继承现有样式。

- [ ] **步骤 5：Commit**

```bash
git add static/js/sse-handler.js static/js/chat.js
git commit -m "feat(ui): 前端渲染 route 徽章与 evidence 证据表"
```

---

### 任务 12：全量回归 + 文档归档

**文件：** 修改 `README.md`（技术流章节新增技能化小节）、复制计划到 `docs/superpowers/plans/`

- [ ] **步骤 1：全量回归** `python -m pytest tests/ -q`
预期：原 305 + 新增（contract 5 / 6 skill / registry 3 / router 5 / api 2 ≈ 30+）全部 PASS

- [ ] **步骤 2：手动端到端验证**（见下方"验证"节）：上传任一数据集，分别问触发 6 个技能的问题与一个兜底问题，确认路由徽章、证据表、图表、流式解释、兜底代码均正常。

- [ ] **步骤 3：** 在 `README.md` 技术流章节新增"技能化问数架构"小节（≤200 字）：说明 `skills/` 目录、SKILL.md+脚本分离、路由→计划→脚本→解释链路、代码生成兜底。

- [ ] **步骤 4：** 归档计划：将本计划文件复制为 `docs/superpowers/plans/2026-06-01-ai-qa-skill-refactor.md`。

- [ ] **步骤 5：Commit**

```bash
git add README.md docs/superpowers/plans/2026-06-01-ai-qa-skill-refactor.md
git commit -m "docs: 技能化问数架构说明 + 实现计划归档"
```

---

## 验证（端到端）

1. **单测全绿**：`python -m pytest tests/ -q` → 全部 PASS（无回归）。
2. **启动应用**：`python app.py`（或既有启动方式），浏览器打开首页，上传 `datasets/Amazon_BestSelling_Books_500.csv` 或 `winequality-red.csv`。
3. **配置 AI**：在设置中填入 OpenAI 兼容 `AI_API_KEY`/`AI_BASE_URL`/`AI_MODEL`。
4. **逐技能问数**（确认出现 `🧩 已选择技能` 徽章 + 证据表 + 图 + 流式中文解释）：
   - stats：「各类别销量的均值和方差」
   - viz：「按类别比较销量并画柱状图」
   - trend：「销量随时间的月度趋势」（含日期列数据集）
   - correlation：「各数值字段之间的相关性」
   - distribution：「价格的分布情况」
   - profile：「这个数据集有什么特点 / 有哪些列 / 数据质量如何」
5. **兜底问数**：问一个无技能覆盖的复杂问题（如「帮我做一个自定义的多步加权计算」），确认降级到代码生成沙箱（出现 `code_complete`/`exec_result`），行为与改造前一致。
6. **随机数据集鲁棒性**：换用纯分类数据集（无数值列）再问 stats/correlation，确认安全降级不报错（证据表给出 message 提示而非 500）。

## 自检结论

- **规格覆盖**：设计规格 4 节（目录/数据流/契约/测试）全部落到任务 1–12；6 个 plan schema 对应任务 2–7；两阶段解释对应任务 9（`explain_stream`）+ 任务 10（集成）；兜底零改动对应任务 10 的 `_codegen_stream` 照搬。
- **类型一致性**：`SkillResult(answer/evidence/chart/meta)`、`execute_<name>_plan(df, plan, context=None)`、`SkillRouter.route()/explain_stream()`、`SKILLS`/`load_catalog()` 在各任务间签名一致；`fig_to_chart_dict` 复用 `code_generator._plotly_fig_to_dict`。
- **无占位符**：每个代码步骤含完整可执行代码；distribution 的 box 边界情形给出明确备选实现。
