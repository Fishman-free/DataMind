# DataMind 可视化可靠性与图像质量提升 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复仪表盘卡片尺寸/堆叠异常、质量卡“时效性”绿条缺失、智能问答散点图无点/残缺，并为 6 类图表建立统一“可见性守卫”。

**Architecture:** 采用最小侵入改造：前端图表渲染层增加容器/数据/可见性守卫，后端质量评分输出统一维度协议与 timeliness 兜底，AI 图表生成链路加入散点图硬约束与执行后有效点校验。通过“失败即降级+解释文案”避免残缺图。

**Tech Stack:** Flask, pandas, Plotly.js, vanilla JS, pytest

---

## 文件结构与职责

- `static/js/charts.js`（修改）
  - 自适应仪表盘渲染主入口
  - 新增统一图表守卫（数据合法性、容器可见性、渲染后 resize）
  - 各图类型 fallback 渲染

- `templates/visualization.html`（修改）
  - 图表网格容器结构与初始化调用位置

- `static/css/style.css`（修改）
  - chart card / slot 尺寸规则与响应式断点

- `data/quality_scorer.py`（修改）
  - 质量维度协议统一输出
  - `timeliness` 缺失时兜底策略

- `templates/index.html`（修改）
  - 质量卡维度渲染逻辑（clamp、缺失不跳过）

- `ai/chart_generator.py`（修改）
  - NL2Vis 生成提示词增强（dropna/to_numeric/有效点检测）
  - 执行后散点有效点校验与降级

- `ai/chat.py`（修改）
  - 智能问答生成图表的系统约束补充（同上）

- `tests/test_quality_timeliness.py`（新建）
  - timeliness 维度稳定输出测试

- `tests/test_chart_generator_scatter_guard.py`（新建）
  - 散点空点降级与解释文案测试

- `tests/test_adaptive_charts_contract.py`（新建）
  - 自适应图表返回结构完整性测试

---

## Task 1: 仪表盘尺寸与堆叠稳定化

**Files:**
- Modify: `static/js/charts.js`
- Modify: `templates/visualization.html`
- Modify: `static/css/style.css`
- Test: `tests/test_adaptive_charts_contract.py`

- [ ] **Step 1: 写失败测试（图表配置契约）**

```python
# tests/test_adaptive_charts_contract.py
import json


def test_adaptive_charts_contract(client_with_numeric_dataset):
    resp = client_with_numeric_dataset.get('/api/analysis/adaptive_charts')
    assert resp.status_code == 200
    charts = resp.get_json()
    assert isinstance(charts, list)
    assert len(charts) >= 6
    for cfg in charts[:6]:
        assert 'type' in cfg
        assert 'title' in cfg
        assert 'data' in cfg
```

- [ ] **Step 2: 运行测试确认基线**

Run: `python -m pytest tests/test_adaptive_charts_contract.py -v`
Expected: 若 fixture 缺失或返回结构不稳定，出现 FAIL（先暴露问题）。

- [ ] **Step 3: 实现最小前端稳定化改动**

在 `static/css/style.css` 增加（或合并到现有规则）：

```css
/* visualization chart card sizing guard */
#adaptive-charts-grid .chart-card {
  min-height: 360px;
  height: 100%;
  display: flex;
  flex-direction: column;
}
#adaptive-charts-grid .chart-card .card-body {
  flex: 1;
  min-height: 300px;
}
#adaptive-charts-grid [id^="chart-slot-"] {
  width: 100%;
  height: 300px;
}
@media (max-width: 1440px) {
  #adaptive-charts-grid [id^="chart-slot-"] { height: 260px; }
}
```

在 `static/js/charts.js` 增加 resize 守卫（复用到所有图）：

```javascript
function _safeResize(el) {
    if (!el || !window.Plotly) return;
    requestAnimationFrame(function () {
        try { Plotly.Plots.resize(el); } catch (_) {}
    });
}

function _ensureVisibleAndRender(el, renderFn) {
    if (!el) return;
    var rect = el.getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0) {
        setTimeout(function () { renderFn(); }, 80);
        return;
    }
    renderFn();
    _safeResize(el);
}
```

在每个 `_plot*` 末尾追加 `_safeResize(el)`，并在 `_renderChartSlot` 中用 `_ensureVisibleAndRender` 包裹渲染调用。

- [ ] **Step 4: 运行针对性测试**

Run: `python -m pytest tests/test_adaptive_charts_contract.py -v`
Expected: PASS

- [ ] **Step 5: 运行全量测试**

Run: `python -m pytest tests/ -x --tb=short -q`
Expected: 全部 PASS

- [ ] **Step 6: Commit**

```bash
git add static/js/charts.js templates/visualization.html static/css/style.css tests/test_adaptive_charts_contract.py
git commit -m "fix: 修复仪表盘卡片尺寸与图表渲染错位"
```

---

## Task 2: 质量卡 timeliness 维度稳定输出

**Files:**
- Modify: `data/quality_scorer.py`
- Modify: `templates/index.html`
- Test: `tests/test_quality_timeliness.py`

- [ ] **Step 1: 写失败测试（timeliness 不可缺失）**

```python
# tests/test_quality_timeliness.py
import pandas as pd
from data.quality_scorer import score_data_quality


def test_timeliness_dimension_always_present_without_date_column():
    df = pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})
    report = score_data_quality(df)
    dims = report.get("dimensions", [])
    keys = [d.get("key") for d in dims]
    assert "timeliness" in keys


def test_timeliness_score_clamped():
    df = pd.DataFrame({"date": ["2024-01-01", "bad", None]})
    report = score_data_quality(df)
    dims = {d.get("key"): d for d in report.get("dimensions", [])}
    t = dims["timeliness"]["score"]
    assert 0 <= t <= 100
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_quality_timeliness.py -v`
Expected: 现状大概率 FAIL（timeliness 缺失或异常）。

- [ ] **Step 3: 最小实现（后端协议 + 前端 clamp）**

在 `data/quality_scorer.py` 保证输出结构：

```python
def _clamp_score(v: float) -> float:
    return max(0.0, min(100.0, float(v)))

# dimensions 统一输出，必须包含 timeliness
dimensions = [
    {"key": "accuracy", "label": "准确性", "score": _clamp_score(acc)},
    {"key": "completeness", "label": "完整性", "score": _clamp_score(comp)},
    {"key": "consistency", "label": "一致性", "score": _clamp_score(cons)},
    {"key": "timeliness", "label": "时效性", "score": _clamp_score(time_score), "reason": time_reason},
    {"key": "uniqueness", "label": "唯一性", "score": _clamp_score(unique)},
]
```

在 `templates/index.html` 的质量维度渲染函数中：

```javascript
function _safePct(v) {
    var n = Number(v);
    if (!Number.isFinite(n)) n = 0;
    n = Math.max(0, Math.min(100, n));
    return n;
}

// 渲染每个维度时强制输出 bar
var score = _safePct(dim.score);
barFill.style.width = score + '%';
```

- [ ] **Step 4: 运行测试验证通过**

Run: `python -m pytest tests/test_quality_timeliness.py -v`
Expected: PASS

- [ ] **Step 5: 全量测试**

Run: `python -m pytest tests/ -x --tb=short -q`
Expected: 全部 PASS

- [ ] **Step 6: Commit**

```bash
git add data/quality_scorer.py templates/index.html tests/test_quality_timeliness.py
git commit -m "fix: 保证质量卡时效性维度稳定显示"
```

---

## Task 3: 智能问答散点图空点守卫与自动降级

**Files:**
- Modify: `ai/chart_generator.py`
- Modify: `ai/chat.py`
- Test: `tests/test_chart_generator_scatter_guard.py`

- [ ] **Step 1: 写失败测试（空点时降级）**

```python
# tests/test_chart_generator_scatter_guard.py
import pandas as pd
from ai.chart_generator import ChartGenerator


def test_scatter_fallback_when_no_valid_points(monkeypatch):
    df = pd.DataFrame({"x": [None, None], "y": [None, None]})
    cg = ChartGenerator()

    # mock: AI 返回 scatter 代码
    code = """
fig = px.scatter(df, x='x', y='y', title='scatter')
chart = fig
result = 'ok'
"""
    monkeypatch.setattr(cg, "_call_ai", lambda *args, **kwargs: code)
    out = cg.generate("画散点图", df)

    assert out["success"] is True
    # 期望已经降级或带解释
    assert "explanation" in out
    assert ("降级" in out["explanation"]) or ("有效点" in out["explanation"])
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_chart_generator_scatter_guard.py -v`
Expected: FAIL（现状无统一降级解释）。

- [ ] **Step 3: 最小实现（生成约束 + 执行后校验）**

在 `ai/chart_generator.py` 的 prompt 约束段增加：

```text
- 若生成 scatter，必须先对 x/y 列执行 to_numeric(errors='coerce')，并 dropna(subset=[x,y])
- 必须检查有效点数，若为 0 则改为箱线图或分布图，并在 result 文本解释原因
```

在 `_execute_chart_code` 后增加校验函数：

```python
def _scatter_has_points(chart_json: dict) -> bool:
    for tr in chart_json.get("data", []):
        if tr.get("type") == "scatter":
            x = tr.get("x") or []
            y = tr.get("y") or []
            if len(x) > 0 and len(y) > 0:
                return True
    return False
```

若 `scatter` 且无点，则生成降级图（最小策略：箱线图）并覆盖 `chart`，同时在 `explanation` 添加：

```python
"散点图有效点数为 0，已自动降级为箱线图以保证可见性。"
```

在 `ai/chat.py` 的系统提示词“操作规范”追加同样约束，保证问答链路一致。

- [ ] **Step 4: 运行测试验证通过**

Run: `python -m pytest tests/test_chart_generator_scatter_guard.py -v`
Expected: PASS

- [ ] **Step 5: 全量测试**

Run: `python -m pytest tests/ -x --tb=short -q`
Expected: 全部 PASS

- [ ] **Step 6: Commit**

```bash
git add ai/chart_generator.py ai/chat.py tests/test_chart_generator_scatter_guard.py
git commit -m "fix: 散点图空点自动降级并输出可解释文案"
```

---

## Task 4: 全图类型可见性守卫统一收口

**Files:**
- Modify: `static/js/charts.js`
- Test: `tests/test_adaptive_charts_contract.py`（复用）

- [ ] **Step 1: 补失败场景测试（空数据不应渲染残缺图）**

```python
def test_adaptive_charts_each_item_has_type_and_data_even_on_failure(client_with_numeric_dataset):
    resp = client_with_numeric_dataset.get('/api/analysis/adaptive_charts')
    assert resp.status_code == 200
    charts = resp.get_json()
    for cfg in charts[:6]:
        assert cfg.get('type') is not None
        assert 'data' in cfg
```

- [ ] **Step 2: 前端守卫实现**

在 `static/js/charts.js` 抽取：

```javascript
function _hasRenderableData(cfg) {
    if (!cfg) return false;
    if (cfg.type === 'scatter') {
        var d = Array.isArray(cfg.data) ? cfg.data[0] : null;
        return !!(d && Array.isArray(d.x) && Array.isArray(d.y) && d.x.length && d.y.length);
    }
    if (cfg.type === 'heatmap') {
        return !!(cfg.data && Array.isArray(cfg.data.matrix) && cfg.data.matrix.length);
    }
    if (cfg.type === 'histogram' || cfg.type === 'box') {
        return Array.isArray(cfg.data) && cfg.data.length > 0;
    }
    if (cfg.type === 'bar' || cfg.type === 'line' || cfg.type === 'bar_grouped') {
        return !!cfg.data;
    }
    return !!cfg.data;
}
```

在 `_renderChartSlot` 前置检查：

```javascript
if (!_hasRenderableData(cfg)) {
  container.innerHTML = '<div ...>当前图表无有效数据，已跳过渲染</div>';
  return;
}
```

- [ ] **Step 3: 运行测试**

Run: `python -m pytest tests/test_adaptive_charts_contract.py -v`
Expected: PASS

- [ ] **Step 4: 全量测试**

Run: `python -m pytest tests/ -x --tb=short -q`
Expected: 全部 PASS

- [ ] **Step 5: Commit**

```bash
git add static/js/charts.js tests/test_adaptive_charts_contract.py
git commit -m "fix: 增加全图类型可见性守卫与空态降级"
```

---

## Task 5: 回归验证矩阵执行与记录

**Files:**
- Modify: `docs/superpowers/specs/2026-05-26-visual-reliability-and-chart-quality-design.md`（追加验收记录段）

- [ ] **Step 1: 运行自动化全量测试**

Run: `python -m pytest tests/ -x --tb=short -q`
Expected: 全部 PASS

- [ ] **Step 2: 执行人工回归矩阵（4 数据集 × 6 图卡）**

验证清单（每个数据集都要打勾）：
- [ ] 主图元存在
- [ ] 轴标签清晰
- [ ] 标题完整
- [ ] 不溢出卡片
- [ ] 125% 缩放可读
- [ ] 智能问答散点图有点，或降级并有解释
- [ ] 质量卡“时效性”绿条存在

- [ ] **Step 3: 将结果写入设计文档“验收记录”小节**

```markdown
## 验收记录（YYYY-MM-DD）
- 测试命令：...
- 结果：...
- 数据集：numeric/retail/categorical/temporal
- 问题：无/有（列表）
```

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/specs/2026-05-26-visual-reliability-and-chart-quality-design.md
git commit -m "test: 完成可视化可靠性回归验收矩阵"
```

---

## 风险回退策略（执行时必须遵守）

1. 若布局修复引发零售模式图表错位：
   - 回退 CSS 断点，仅保留 `_safeResize + _ensureVisibleAndRender`。

2. 若散点降级影响用户感知：
   - 保留散点标题，副标题标注“已降级展示（有效点数不足）”。

3. 若 timeliness 计算在无日期数据集争议大：
   - 固定中性分（如 70）+ reason 字段，不参与总分权重（或低权重）。

---

## 计划自检（Spec Coverage）

- 规格 3.1（布局）：Task 1 覆盖
- 规格 3.2（时效性）：Task 2 覆盖
- 规格 3.3（散点图）：Task 3 覆盖
- 规格 3.4（全图清晰度）：Task 4 覆盖
- 规格 7（测试矩阵）：Task 5 覆盖

占位符检查：无 TBD/TODO/“稍后实现”。
类型一致性检查：`timeliness` key、`score` 字段、`adaptive_charts` 契约字段在各任务中一致。
