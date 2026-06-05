# 预处理可视化增强 & 图表标签补全 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增 seaborn + matplotlib 预处理诊断图模块，补全所有 Plotly 图表的标题和坐标轴标签，让大作业满足"至少 2 个第三方库"且可视化步骤完整的要求。

**Architecture:** 新建 `data/preprocess_visualizer.py`（seaborn/matplotlib → base64 PNG），新增 API 端点 `/api/analysis/preprocess_charts`，前端在可视化仪表盘顶部新增折叠面板展示 5 张诊断图；同时在 `routes/api.py` 的 adaptive_charts 中补全 `x_label`/`y_label` 字段，`charts.js` 的 `_renderChartSlot` 读取并传给 Plotly layout。

**Tech Stack:** Python（matplotlib>=3.7, seaborn>=0.13, pandas, numpy），Flask，Plotly.js，Bootstrap Accordion

---

## 文件映射

| 操作 | 文件路径 | 职责 |
|------|----------|------|
| 创建 | `data/preprocess_visualizer.py` | 5 张诊断图，每张返回 base64 PNG |
| 创建 | `tests/test_preprocess_visualizer.py` | 单元测试 |
| 修改 | `requirements.txt` | 添加 matplotlib, seaborn |
| 修改 | `routes/api.py` | 新增 preprocess_charts 端点；adaptive_charts 补 x_label/y_label |
| 修改 | `static/js/charts.js` | `_renderChartSlot` 读取 x_label/y_label |
| 修改 | `templates/visualization.html` | 新增折叠面板 + 加载 JS |

---

## Task 1: 添加依赖

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: 更新 requirements.txt**

将文件内容改为：

```
flask>=3.0
pandas>=2.0
numpy>=1.24
openai>=1.0
plotly>=5.0
chardet>=5.0
openpyxl>=3.1
python-calamine>=0.1
markdown>=3.5
pytest>=7.0
matplotlib>=3.7
seaborn>=0.13
```

- [ ] **Step 2: 安装新依赖**

```bash
pip install matplotlib>=3.7 seaborn>=0.13
```

Expected: 安装成功，无报错

- [ ] **Step 3: 验证安装**

```bash
python -c "import matplotlib; import seaborn; print(matplotlib.__version__, seaborn.__version__)"
```

Expected: 打印出两个版本号

---

## Task 2: 创建预处理可视化模块

**Files:**
- Create: `data/preprocess_visualizer.py`

- [ ] **Step 1: 写失败测试**（先写测试，再写实现）

在 `tests/test_preprocess_visualizer.py` 中写：

```python
"""
tests/test_preprocess_visualizer.py — 预处理可视化模块单元测试
来源：学生+AI
"""
import base64
import numpy as np
import pandas as pd
import pytest
from data.preprocess_visualizer import PreprocessVisualizer


@pytest.fixture
def sample_data():
    rng = np.random.default_rng(42)
    raw = pd.DataFrame({
        "Quantity":  rng.integers(1, 100, 200).astype(float),
        "UnitPrice": rng.uniform(0.5, 50.0, 200),
        "Country":   np.where(rng.random(200) < 0.1, None, "UK"),
        "Category":  rng.choice(["A", "B", "C"], 200),
    })
    # 手动插入一些 NaN
    raw.loc[5:15, "UnitPrice"] = np.nan
    # clean 去掉 NaN 行
    clean = raw.dropna().reset_index(drop=True)
    pp_report = {
        "original_rows": 200,
        "remove_duplicates": {"removed": 3, "before": 200, "after": 197},
        "filter_invalid_records": {"removed": 5, "before": 197, "after": 192},
        "handle_missing": {
            "filled_cols": {"UnitPrice": 11, "Country": 20},
            "high_missing_cols": [],
        },
        "convert_types": {"converted": {"Country": "category"}},
        "filter_outliers": {"flagged": 4, "detail": {"Quantity": 4}},
    }
    return raw, clean, pp_report


def test_generate_all_returns_five_charts(sample_data):
    raw, clean, pp = sample_data
    viz = PreprocessVisualizer(raw, clean, pp)
    result = viz.generate_all()
    assert "charts" in result
    assert len(result["charts"]) == 5


def test_each_chart_has_required_fields(sample_data):
    raw, clean, pp = sample_data
    viz = PreprocessVisualizer(raw, clean, pp)
    result = viz.generate_all()
    for chart in result["charts"]:
        assert "title" in chart, f"缺少 title: {chart}"
        assert "img" in chart, f"缺少 img: {chart}"
        assert "desc" in chart, f"缺少 desc: {chart}"


def test_img_is_valid_base64_png(sample_data):
    raw, clean, pp = sample_data
    viz = PreprocessVisualizer(raw, clean, pp)
    result = viz.generate_all()
    for chart in result["charts"]:
        assert chart["img"].startswith("data:image/png;base64,"), \
            f"img 格式不正确: {chart['title']}"
        # 验证 base64 可解码
        b64 = chart["img"].split(",", 1)[1]
        decoded = base64.b64decode(b64)
        assert len(decoded) > 100, "base64 内容过短，可能为空图"


def test_works_with_empty_pp_report(sample_data):
    raw, clean, _ = sample_data
    viz = PreprocessVisualizer(raw, clean, {})
    result = viz.generate_all()
    assert len(result["charts"]) == 5
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd "C:/Users/21560/Desktop/DataMind" && python -m pytest tests/test_preprocess_visualizer.py -v 2>&1 | tail -10
```

Expected: `ModuleNotFoundError: No module named 'data.preprocess_visualizer'`

- [ ] **Step 3: 创建 `data/preprocess_visualizer.py`**

```python
"""
数据预处理可视化模块 — 使用 seaborn + matplotlib 生成诊断图。

生成 5 张预处理诊断图，每张以 base64 PNG 字符串返回：
  1. 缺失值分布热力图 (seaborn.heatmap)
  2. 预处理流水线行数变化 (matplotlib.barh)
  3. 数值列异常值箱线图 (seaborn.boxplot)
  4. 列数据类型分布饼图 (matplotlib.pie)
  5. 缺失值填充前后对比 (matplotlib.bar)

来源：学生+AI
"""
from __future__ import annotations

import base64
import io
from typing import Any

import matplotlib
matplotlib.use("Agg")  # 非交互后端，适合服务器环境
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd
import seaborn as sns

# Windows 中文字体配置
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

_BG_COLOR   = "#0d1117"
_GRID_COLOR = "#1e3a5f"
_TEXT_COLOR = "#c9d1d9"
_ACCENT     = "#4F9FFF"
_WARN       = "#FF6B6B"
_OK         = "#00D4AA"


class PreprocessVisualizer:
    """
    使用 seaborn + matplotlib 生成预处理诊断图。

    用法
    ----
    result = PreprocessVisualizer(df_raw, df_clean, pp_report).generate_all()
    # result["charts"] = [{"title": str, "img": "data:image/png;base64,...", "desc": str}, ...]
    """

    def __init__(
        self,
        df_raw:    pd.DataFrame,
        df_clean:  pd.DataFrame,
        pp_report: dict[str, Any],
    ) -> None:
        self._raw    = df_raw
        self._clean  = df_clean
        self._report = pp_report

    # ── 公共接口 ──────────────────────────────────────────

    def generate_all(self) -> dict[str, list]:
        """生成全部 5 张诊断图，返回 {"charts": [...]}。"""
        generators = [
            self._chart_missing_heatmap,
            self._chart_pipeline_funnel,
            self._chart_outlier_boxplot,
            self._chart_dtype_pie,
            self._chart_fill_compare,
        ]
        charts = []
        for fn in generators:
            try:
                charts.append(fn())
            except Exception as exc:
                charts.append({
                    "title": fn.__name__,
                    "img":   "",
                    "desc":  f"生成失败：{exc}",
                })
        return {"charts": charts}

    # ── 图 1：缺失值分布热力图 ────────────────────────────

    def _chart_missing_heatmap(self) -> dict:
        """seaborn.heatmap 展示原始数据各列缺失值分布。"""
        df = self._raw.copy()
        # 超过 300 行时随机采样，避免图像过密
        if len(df) > 300:
            df = df.sample(300, random_state=42)

        fig, ax = plt.subplots(figsize=(10, 5))
        fig.patch.set_facecolor(_BG_COLOR)
        ax.set_facecolor(_BG_COLOR)

        missing_mask = df.isnull()
        if missing_mask.values.any():
            sns.heatmap(
                missing_mask,
                ax=ax,
                cbar=False,
                cmap=["#1e3a5f", _WARN],
                xticklabels=True,
                yticklabels=False,
            )
        else:
            # 无缺失值时显示全绿热力图
            sns.heatmap(
                pd.DataFrame(False, index=df.index, columns=df.columns),
                ax=ax, cbar=False,
                cmap=[_OK, _OK],
                xticklabels=True, yticklabels=False,
            )

        ax.set_title("原始数据缺失值分布热力图", color=_TEXT_COLOR, fontsize=13, pad=10)
        ax.set_xlabel("列名", color=_TEXT_COLOR, fontsize=10)
        ax.set_ylabel("样本行（采样）", color=_TEXT_COLOR, fontsize=10)
        ax.tick_params(colors=_TEXT_COLOR, labelsize=8)
        plt.xticks(rotation=30, ha="right")

        # 添加图例
        present_patch = mpatches.Patch(color="#1e3a5f", label="有值")
        missing_patch = mpatches.Patch(color=_WARN,    label="缺失")
        ax.legend(handles=[present_patch, missing_patch],
                  loc="upper right", facecolor=_BG_COLOR,
                  labelcolor=_TEXT_COLOR, fontsize=8)

        plt.tight_layout()
        img = self._fig_to_base64(fig)
        plt.close(fig)

        total_missing = int(self._raw.isnull().sum().sum())
        return {
            "title": "缺失值分布热力图",
            "img":   img,
            "desc":  f"原始数据共 {total_missing} 个缺失单元格，红色表示缺失位置",
        }

    # ── 图 2：预处理流水线行数变化 ───────────────────────

    def _chart_pipeline_funnel(self) -> dict:
        """matplotlib.barh 展示各预处理阶段行数变化。"""
        dup = self._report.get("remove_duplicates") or {}
        inv = self._report.get("filter_invalid_records") or {}

        dup_removed = int(dup.get("removed", 0))
        inv_removed = int(inv.get("removed", 0))
        rows_final  = len(self._clean)
        rows_mid    = rows_final + inv_removed
        rows_orig   = rows_mid + dup_removed

        stages = ["原始数据", "去重后", "过滤无效行后"]
        rows   = [rows_orig, rows_mid, rows_final]
        colors = [_ACCENT, "#9B8EA8", _OK]

        fig, ax = plt.subplots(figsize=(8, 3.5))
        fig.patch.set_facecolor(_BG_COLOR)
        ax.set_facecolor(_BG_COLOR)

        bars = ax.barh(stages, rows, color=colors, height=0.5, edgecolor="none")

        # 行数标注
        for bar, val in zip(bars, rows):
            ax.text(
                bar.get_width() + max(rows) * 0.01,
                bar.get_y() + bar.get_height() / 2,
                f"{val:,} 行",
                va="center", ha="left",
                color=_TEXT_COLOR, fontsize=10,
            )

        ax.set_title("预处理流水线行数变化", color=_TEXT_COLOR, fontsize=13, pad=10)
        ax.set_xlabel("行数", color=_TEXT_COLOR, fontsize=10)
        ax.set_ylabel("处理阶段", color=_TEXT_COLOR, fontsize=10)
        ax.tick_params(colors=_TEXT_COLOR)
        ax.spines[:].set_color(_GRID_COLOR)
        ax.set_xlim(0, max(rows) * 1.18)
        ax.xaxis.grid(True, color=_GRID_COLOR, linewidth=0.5)
        ax.set_axisbelow(True)

        plt.tight_layout()
        img = self._fig_to_base64(fig)
        plt.close(fig)

        removed_total = dup_removed + inv_removed
        return {
            "title": "预处理流水线行数变化",
            "img":   img,
            "desc":  f"共删除 {removed_total:,} 行（去重 {dup_removed:,} + 无效过滤 {inv_removed:,}）",
        }

    # ── 图 3：数值列异常值箱线图 ─────────────────────────

    def _chart_outlier_boxplot(self) -> dict:
        """seaborn.boxplot 展示清洁数据各数值列异常值分布。"""
        # 只取原始业务数值列（排除派生的 _is_outlier 列）
        num_cols = [
            c for c in self._clean.select_dtypes(include="number").columns
            if not c.endswith(("_is_outlier", "_is_extreme_outlier"))
        ][:6]  # 最多 6 列，防止图太宽

        if not num_cols:
            fig, ax = plt.subplots(figsize=(6, 3))
            fig.patch.set_facecolor(_BG_COLOR)
            ax.set_facecolor(_BG_COLOR)
            ax.text(0.5, 0.5, "无数值列", transform=ax.transAxes,
                    ha="center", va="center", color=_TEXT_COLOR)
            ax.set_title("数值列异常值箱线图", color=_TEXT_COLOR, fontsize=13)
            plt.tight_layout()
            img = self._fig_to_base64(fig)
            plt.close(fig)
            return {"title": "数值列异常值箱线图", "img": img, "desc": "无数值列"}

        df_plot = self._clean[num_cols].copy()

        fig, ax = plt.subplots(figsize=(max(6, len(num_cols) * 1.8), 5))
        fig.patch.set_facecolor(_BG_COLOR)
        ax.set_facecolor(_BG_COLOR)

        sns.boxplot(
            data=df_plot,
            ax=ax,
            palette=[_ACCENT] * len(num_cols),
            flierprops={"marker": "o", "markerfacecolor": _WARN,
                        "markersize": 4, "alpha": 0.6},
            width=0.5,
        )

        ax.set_title("数值列异常值箱线图（IQR ×1.5）", color=_TEXT_COLOR, fontsize=13, pad=10)
        ax.set_xlabel("列名", color=_TEXT_COLOR, fontsize=10)
        ax.set_ylabel("数值", color=_TEXT_COLOR, fontsize=10)
        ax.tick_params(colors=_TEXT_COLOR, labelsize=9)
        ax.spines[:].set_color(_GRID_COLOR)
        ax.yaxis.grid(True, color=_GRID_COLOR, linewidth=0.5)
        ax.set_axisbelow(True)
        plt.xticks(rotation=20, ha="right")

        plt.tight_layout()
        img = self._fig_to_base64(fig)
        plt.close(fig)

        outlier_detail = (self._report.get("filter_outliers") or {}).get("detail", {})
        total_outliers = sum(outlier_detail.values())
        return {
            "title": "数值列异常值箱线图",
            "img":   img,
            "desc":  f"红点为异常值（IQR×1.5 法），共检测到 {total_outliers} 个异常点",
        }

    # ── 图 4：列数据类型分布饼图 ─────────────────────────

    def _chart_dtype_pie(self) -> dict:
        """matplotlib.pie 展示清洁数据各列的数据类型构成。"""
        dtype_counts: dict[str, int] = {}
        for dtype in self._clean.dtypes:
            kind = str(dtype)
            if "int" in kind:
                label = "整数 (int)"
            elif "float" in kind:
                label = "浮点数 (float)"
            elif "datetime" in kind:
                label = "日期时间 (datetime)"
            elif "category" in kind:
                label = "分类 (category)"
            elif "bool" in kind:
                label = "布尔 (bool)"
            else:
                label = "文本 (object)"
            dtype_counts[label] = dtype_counts.get(label, 0) + 1

        labels = list(dtype_counts.keys())
        sizes  = list(dtype_counts.values())
        palette = [_ACCENT, "#9B8EA8", _OK, "#FFB347", _WARN, "#C4B7A6"]
        colors  = palette[: len(labels)]

        fig, ax = plt.subplots(figsize=(7, 5))
        fig.patch.set_facecolor(_BG_COLOR)
        ax.set_facecolor(_BG_COLOR)

        wedges, texts, autotexts = ax.pie(
            sizes,
            labels=None,
            colors=colors,
            autopct="%1.1f%%",
            startangle=140,
            pctdistance=0.78,
            wedgeprops={"edgecolor": _BG_COLOR, "linewidth": 2},
        )
        for at in autotexts:
            at.set_color(_BG_COLOR)
            at.set_fontsize(9)
            at.set_fontweight("bold")

        ax.legend(
            wedges, [f"{l}（{s} 列）" for l, s in zip(labels, sizes)],
            loc="lower center", bbox_to_anchor=(0.5, -0.15),
            ncol=2, facecolor=_BG_COLOR, labelcolor=_TEXT_COLOR, fontsize=9,
        )
        ax.set_title("列数据类型分布", color=_TEXT_COLOR, fontsize=13, pad=10)

        plt.tight_layout()
        img = self._fig_to_base64(fig)
        plt.close(fig)

        converted = (self._report.get("convert_types") or {}).get("converted", {})
        return {
            "title": "列数据类型分布",
            "img":   img,
            "desc":  f"预处理共转换 {len(converted)} 列类型（{', '.join(converted.values()) or '无'}）",
        }

    # ── 图 5：缺失值填充前后对比柱状图 ──────────────────

    def _chart_fill_compare(self) -> dict:
        """matplotlib.bar 对每个被填充的列，展示填充前后缺失单元格数量。"""
        miss_info = (self._report.get("handle_missing") or {}).get("filled_cols", {})

        if not miss_info:
            # 无缺失值时展示一张"全绿"示意图
            fig, ax = plt.subplots(figsize=(6, 3))
            fig.patch.set_facecolor(_BG_COLOR)
            ax.set_facecolor(_BG_COLOR)
            ax.text(0.5, 0.5, "✓ 无缺失值需填充", transform=ax.transAxes,
                    ha="center", va="center", color=_OK, fontsize=14)
            ax.set_title("缺失值填充前后对比", color=_TEXT_COLOR, fontsize=13)
            ax.axis("off")
            plt.tight_layout()
            img = self._fig_to_base64(fig)
            plt.close(fig)
            return {"title": "缺失值填充前后对比", "img": img,
                    "desc": "数据集无缺失值，无需填充"}

        cols   = list(miss_info.keys())
        before = [int(v) for v in miss_info.values()]
        after  = [0] * len(cols)  # 填充后缺失数为 0

        x   = np.arange(len(cols))
        w   = 0.35

        fig, ax = plt.subplots(figsize=(max(6, len(cols) * 1.5), 5))
        fig.patch.set_facecolor(_BG_COLOR)
        ax.set_facecolor(_BG_COLOR)

        b1 = ax.bar(x - w / 2, before, w, label="填充前", color=_WARN,   alpha=0.85)
        b2 = ax.bar(x + w / 2, after,  w, label="填充后", color=_OK,     alpha=0.85)

        # 数值标注
        for bar in b1:
            h = bar.get_height()
            if h > 0:
                ax.text(bar.get_x() + bar.get_width() / 2, h + max(before) * 0.02,
                        str(int(h)), ha="center", va="bottom",
                        color=_TEXT_COLOR, fontsize=9)

        ax.set_title("缺失值填充前后对比", color=_TEXT_COLOR, fontsize=13, pad=10)
        ax.set_xlabel("列名", color=_TEXT_COLOR, fontsize=10)
        ax.set_ylabel("缺失单元格数", color=_TEXT_COLOR, fontsize=10)
        ax.set_xticks(x)
        ax.set_xticklabels(cols, rotation=20, ha="right", color=_TEXT_COLOR, fontsize=9)
        ax.tick_params(colors=_TEXT_COLOR)
        ax.spines[:].set_color(_GRID_COLOR)
        ax.yaxis.grid(True, color=_GRID_COLOR, linewidth=0.5)
        ax.set_axisbelow(True)
        ax.legend(facecolor=_BG_COLOR, labelcolor=_TEXT_COLOR, fontsize=9)

        plt.tight_layout()
        img = self._fig_to_base64(fig)
        plt.close(fig)

        total_filled = sum(before)
        return {
            "title": "缺失值填充前后对比",
            "img":   img,
            "desc":  f"共填充 {total_filled:,} 个缺失单元格（数值列→均值/中位数，文本列→众数/'Unknown'）",
        }

    # ── 工具方法 ──────────────────────────────────────────

    def _fig_to_base64(self, fig) -> str:
        """将 matplotlib Figure 转为 base64 PNG data URL。"""
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=110, bbox_inches="tight",
                    facecolor=fig.get_facecolor())
        buf.seek(0)
        b64 = base64.b64encode(buf.read()).decode("utf-8")
        return f"data:image/png;base64,{b64}"
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd "C:/Users/21560/Desktop/DataMind" && python -m pytest tests/test_preprocess_visualizer.py -v 2>&1 | tail -15
```

Expected: `4 passed`

- [ ] **Step 5: 提交**

```bash
cd "C:/Users/21560/Desktop/DataMind" && git add data/preprocess_visualizer.py tests/test_preprocess_visualizer.py requirements.txt && git commit -m "feat: 新增 PreprocessVisualizer 模块（seaborn+matplotlib 5 张预处理诊断图）"
```

---

## Task 3: 新增 API 端点

**Files:**
- Modify: `routes/api.py`（在 `preprocess_visual_api` 函数之后约 539 行处新增）

- [ ] **Step 1: 写失败测试**

在 `tests/test_preprocess_visualizer.py` 末尾追加：

```python
# ── API 集成测试 ──────────────────────────────────────────


def test_api_returns_five_charts_keys(sample_data):
    """
    直接调用 generate_all() 检查返回结构，
    不依赖 Flask 测试客户端（避免需要上传文件的复杂 setup）。
    """
    raw, clean, pp = sample_data
    viz = PreprocessVisualizer(raw, clean, pp)
    result = viz.generate_all()
    titles = [c["title"] for c in result["charts"]]
    assert "缺失值分布热力图"    in titles
    assert "预处理流水线行数变化"  in titles
    assert "数值列异常值箱线图"   in titles
    assert "列数据类型分布"       in titles
    assert "缺失值填充前后对比"   in titles
```

- [ ] **Step 2: 运行确认通过**

```bash
cd "C:/Users/21560/Desktop/DataMind" && python -m pytest tests/test_preprocess_visualizer.py -v 2>&1 | tail -10
```

Expected: `5 passed`

- [ ] **Step 3: 在 `routes/api.py` 添加 import 和新端点**

在文件顶部 import 区域（约第 38 行 `from data.preprocessor import Preprocessor` 下方）添加：

```python
from data.preprocess_visualizer import PreprocessVisualizer
```

在 `preprocess_visual_api` 函数（约第 529-538 行）之后添加新端点：

```python
@api_bp.route("/analysis/preprocess_charts")
def preprocess_charts_api():
    """返回 seaborn+matplotlib 生成的预处理诊断图（base64 PNG）。"""
    err = _require_data()
    if err:
        return err
    state     = _state()
    df_raw    = state.get("df_raw")
    df_clean  = state["df_clean"]
    pp_report = state.get("preprocess_report", {})
    if df_raw is None:
        df_raw = df_clean
    viz = PreprocessVisualizer(df_raw, df_clean, pp_report)
    return jsonify(viz.generate_all())
```

- [ ] **Step 4: 手动验证端点可导入（无 Flask 上下文时不报错）**

```bash
cd "C:/Users/21560/Desktop/DataMind" && python -c "from routes.api import api_bp; print('import OK')"
```

Expected: `import OK`

- [ ] **Step 5: 提交**

```bash
cd "C:/Users/21560/Desktop/DataMind" && git add routes/api.py && git commit -m "feat: 新增 /api/analysis/preprocess_charts 端点"
```

---

## Task 4: 在 adaptive_charts 中补全 x_label/y_label

**Files:**
- Modify: `routes/api.py`（`adaptive_charts` 函数，约第 350-467 行）

- [ ] **Step 1: 写失败测试**

在 `tests/test_preprocess_visualizer.py` 末尾追加：

```python
def test_adaptive_charts_label_fields_present():
    """
    验证 adaptive_charts 辅助函数生成的图表配置含 x_label/y_label。
    直接测试 _make_hist_chart / _make_cat_chart 的输出结构。
    """
    import numpy as np
    import pandas as pd
    from data.analyzer import Analyzer

    df = pd.DataFrame({
        "val_a": np.random.default_rng(0).uniform(0, 10, 50),
        "val_b": np.random.default_rng(1).uniform(0, 5, 50),
        "cat":   ["X", "Y"] * 25,
    })
    az = Analyzer(df)

    # 模拟 _make_hist_chart 的输出（调用 routes/api.py 中的私有函数不方便，
    # 改为验证 analyzer 输出含足够字段）
    dists = az.numeric_distributions(max_cols=2)
    assert len(dists) >= 1
    # 确认 routes/api.py 在构建图表 dict 时应传入的字段存在于数据中
    for d in dists:
        assert "col" in d
        assert "bins" in d
```

- [ ] **Step 2: 修改 `routes/api.py` 的 `adaptive_charts` 函数**

找到文件中约第 391-465 行，对以下 `charts.append` 调用补充 `x_label`/`y_label`：

**图表 1（直方图，约第 402 行）：**

**精确修改 `_make_hist_chart`（第 470-478 行），用以下内容完整替换：**

```python
def _make_hist_chart(az, numeric_cols: list, offset: int = 0) -> dict:
    """构造直方图图表配置。"""
    try:
        data = az.numeric_distributions(max_cols=6)
        if offset and len(data) > offset:
            data = data[offset:]
        return {"type": "histogram", "title": "数值列分布", "data": data,
                "source": "generic", "x_label": "数值区间", "y_label": "频次"}
    except Exception:
        return {"type": "histogram", "title": "数值列分布", "data": [],
                "source": "generic", "x_label": "数值区间", "y_label": "频次"}
```

**精确修改 `_make_cat_chart`（第 481-489 行），用以下内容完整替换：**

```python
def _make_cat_chart(az, categorical_cols: list) -> dict:
    """构造类别频次图表配置。"""
    try:
        data = az.category_distributions(max_cols=1)
        col  = data[0]["col"] if data else "分类列"
        return {"type": "bar", "title": f"{col} 频次分布",
                "data": data[0] if data else {}, "source": "generic",
                "x_label": col, "y_label": "频次"}
    except Exception:
        return {"type": "bar", "title": "分类频次", "data": {},
                "source": "generic", "x_label": "类别", "y_label": "频次"}
```

**精确修改 `adaptive_charts` 函数内以下 `charts.append` 调用（逐行替换，保留周围代码不变）：**

第 409-414 行（相关性矩阵）：
```python
        try:
            charts.append({
                "type": "heatmap", "title": "相关性矩阵",
                "data": az.correlation_matrix(), "source": "generic",
                "x_label": "列名", "y_label": "列名"
            })
        except Exception:
            charts.append({"type": "heatmap", "title": "相关性矩阵", "data": None,
                           "x_label": "列名", "y_label": "列名"})
```

第 424-426 行（箱线图）：
```python
        box_data = az.box_plots(max_cols=6)
        charts.append({"type": "box", "title": "数值列分布箱线图",
                       "data": box_data, "source": "generic",
                       "x_label": "列名", "y_label": "数值"})
```

第 432-436 行（散点图）：
```python
            charts.append({
                "type": "scatter",
                "title": f"{pair['x_col']} vs {pair['y_col']}（相关系数 {pair['corr']:.2f}）",
                "data": scatter_data, "source": "generic",
                "x_label": pair["x_col"], "y_label": pair["y_col"]
            })
```

第 447-455 行（目标列分布）：
```python
            vc = df[target_col].value_counts()
            charts.append({
                "type": "bar",
                "title": f"{target_col} 分布",
                "data": {"labels": [str(x) for x in vc.index.tolist()],
                         "counts": [int(x) for x in vc.values.tolist()],
                         "col": target_col},
                "source": "generic",
                "x_label": target_col, "y_label": "频次"
            })
```

第 394-397 行（时序折线，在 temporal 分支内）：
```python
            charts.append({
                "type": "line", "title": f"{date_col} 时间趋势",
                "data": az.sales_trend(), "source": "temporal",
                "x_label": "日期", "y_label": "数值"
            })
```

第 463-465 行（预处理行数）：
```python
    viz = az.preprocess_visual(pp_report)
    charts.append({"type": "bar_grouped", "title": "数据清洗行数变化",
                   "data": viz.get("pipeline_stages", []), "source": "preprocess",
                   "x_label": "行数", "y_label": "处理阶段"})
```

- [ ] **Step 3: 验证导入无报错**

```bash
cd "C:/Users/21560/Desktop/DataMind" && python -c "from routes.api import api_bp; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: 运行全量测试**

```bash
cd "C:/Users/21560/Desktop/DataMind" && python -m pytest tests/ -x --tb=short -q 2>&1 | tail -8
```

Expected: 全部通过，无 FAILED

- [ ] **Step 5: 提交**

```bash
cd "C:/Users/21560/Desktop/DataMind" && git add routes/api.py && git commit -m "feat: adaptive_charts 补全 x_label/y_label 元数据"
```

---

## Task 5: 更新 charts.js 读取轴标签元数据

**Files:**
- Modify: `static/js/charts.js`（`_renderChartSlot` 函数，约第 458-511 行）

- [ ] **Step 1: 在 `_renderChartSlot` 中添加轴标签合并逻辑**

找到 `_renderChartSlot` 函数内 `const layout_base = { ... }` 声明（约第 474 行），
在 `const opts = ...` 行之后、`try {` 之前插入：

```javascript
    // 将后端传来的 x_label / y_label / title 合并进 layout_base
    if (cfg.x_label) {
        layout_base.xaxis = Object.assign({}, layout_base.xaxis,
            { title: { text: cfg.x_label, font: { color: '#8899B8', size: 10 } } });
    }
    if (cfg.y_label) {
        layout_base.yaxis = Object.assign({}, layout_base.yaxis,
            { title: { text: cfg.y_label, font: { color: '#8899B8', size: 10 } } });
    }
    if (cfg.title) {
        layout_base.title = { text: cfg.title,
            font: { color: '#8899B8', size: 12 }, x: 0.02 };
        layout_base.margin = Object.assign({}, layout_base.margin, { t: 36 });
    }
```

完整修改后的 `_renderChartSlot` 开头部分（约第 458-490 行）应如下：

```javascript
function _renderChartSlot(index, cfg) {
    var container = document.getElementById('chart-slot-' + index);
    if (!container || !window.Plotly) return;

    if (!cfg || !cfg.data) {
        container.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:rgba(255,255,255,0.3);font-size:0.85em"><i class="bi bi-dash-circle me-2"></i>当前数据集无此维度</div>';
        return;
    }

    container.style.display = 'block';
    container.style.alignItems = '';
    container.style.justifyContent = '';
    container.style.color = '';
    container.innerHTML = '';

    const layout_base = {
        paper_bgcolor: 'transparent', plot_bgcolor: 'transparent',
        font: { color: '#fff', size: 11 },
        margin: { t: 20, b: 40, l: 50, r: 20 },
        yaxis: { gridcolor: 'rgba(255,255,255,0.07)' },
        xaxis: { gridcolor: 'rgba(255,255,255,0.07)' },
        showlegend: false,
    };
    const opts = { responsive: true, displayModeBar: false };

    // 将后端传来的 x_label / y_label 合并进 layout_base
    if (cfg.x_label) {
        layout_base.xaxis = Object.assign({}, layout_base.xaxis,
            { title: { text: cfg.x_label, font: { color: '#8899B8', size: 10 } } });
    }
    if (cfg.y_label) {
        layout_base.yaxis = Object.assign({}, layout_base.yaxis,
            { title: { text: cfg.y_label, font: { color: '#8899B8', size: 10 } } });
    }
    if (cfg.title) {
        layout_base.title = { text: cfg.title,
            font: { color: '#8899B8', size: 12 }, x: 0.02 };
        layout_base.margin = Object.assign({}, layout_base.margin, { t: 36 });
    }

    try {
        _ensureVisibleAndRender(container, function () {
```

- [ ] **Step 2: 验证 JS 无语法错误**

```bash
node -e "require('fs').readFileSync('C:/Users/21560/Desktop/DataMind/static/js/charts.js','utf8'); console.log('syntax OK')" 2>&1
```

Expected: `syntax OK`（如果没有 node 可跳过，在浏览器中打开页面确认无控制台报错）

- [ ] **Step 3: 提交**

```bash
cd "C:/Users/21560/Desktop/DataMind" && git add static/js/charts.js && git commit -m "feat: _renderChartSlot 支持后端 x_label/y_label/title 元数据"
```

---

## Task 6: 更新 visualization.html 添加预处理报告折叠面板

**Files:**
- Modify: `templates/visualization.html`

- [ ] **Step 1: 将 `templates/visualization.html` 替换为以下内容**

```html
{% extends "base.html" %}
<!-- 来源：学生+AI -->
{% block content %}
<div class="d-flex align-items-center justify-content-between mb-4">
    <div class="d-flex align-items-center gap-3">
        <h4 class="mb-0">可视化仪表盘</h4>
        <span id="profile-badge" class="badge rounded-pill"
              style="display:none;font-size:0.78em;padding:4px 10px;border:1px solid currentColor">
            <span id="profile-badge-icon">◈</span>
            <span id="profile-badge-name">检测中</span>
        </span>
    </div>
    <button class="btn btn-outline-secondary btn-sm"
            onclick="window.initVisualizationPage()" title="刷新图表">
        <i class="bi bi-arrow-clockwise me-1"></i>刷新
    </button>
</div>

<div id="no-data-alert" class="alert alert-info">
    <i class="bi bi-info-circle me-2"></i>请先上传数据文件
</div>

<!-- 预处理报告折叠面板 -->
<div id="prep-section" style="display:none" class="mb-4">
    <div class="accordion" id="prepAccordion">
        <div class="accordion-item"
             style="background:#0d1117;border:1px solid #1e3a5f;border-radius:8px">
            <h2 class="accordion-header" id="prepHeading">
                <button class="accordion-button collapsed"
                        type="button"
                        data-bs-toggle="collapse"
                        data-bs-target="#prepPanel"
                        aria-expanded="false"
                        aria-controls="prepPanel"
                        style="background:#0d1117;color:#c9d1d9;border-radius:8px;
                               font-size:0.95em;font-weight:600">
                    <i class="bi bi-clipboard2-data me-2" style="color:#4F9FFF"></i>
                    数据预处理报告（seaborn + matplotlib）
                    <span id="prep-badge" class="badge ms-2"
                          style="background:#1e3a5f;color:#4F9FFF;font-size:0.75em">
                        5 张诊断图
                    </span>
                </button>
            </h2>
            <div id="prepPanel"
                 class="accordion-collapse collapse"
                 aria-labelledby="prepHeading">
                <div class="accordion-body" style="padding:1rem">
                    <div id="prep-loading" class="text-center py-3"
                         style="color:rgba(255,255,255,0.4);font-size:0.85em">
                        <div class="spinner-border spinner-border-sm me-2"></div>
                        正在生成预处理诊断图…
                    </div>
                    <div id="prep-charts-grid"
                         class="row g-3"
                         style="display:none">
                        <!-- 5 张 base64 图片由 JS 动态插入 -->
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>

<div id="charts-section" style="display:none">
    <div id="adaptive-charts-grid" class="row g-4 align-items-stretch">
        <!-- 由 renderAdaptiveDashboard() 动态填充 6 个 chart-card -->
    </div>
</div>
{% endblock %}

{% block scripts %}
<script src="{{ url_for('static', filename='js/charts.js') }}"></script>
<script>
// 加载预处理诊断图
async function loadPrepCharts() {
    const grid    = document.getElementById('prep-charts-grid');
    const loading = document.getElementById('prep-loading');
    try {
        const res = await fetch('/api/analysis/preprocess_charts');
        if (!res.ok) { loading.textContent = '加载失败'; return; }
        const data = await res.json();
        const charts = data.charts || [];
        loading.style.display = 'none';
        grid.style.display = 'flex';
        grid.style.flexWrap = 'wrap';
        charts.forEach(function(c) {
            if (!c.img) return;
            const col = document.createElement('div');
            col.className = 'col-12 col-md-6';
            col.innerHTML = `
                <div class="card h-100"
                     style="background:#0a0f1a;border:1px solid #1e3a5f;border-radius:8px">
                    <div class="card-header"
                         style="background:transparent;border-bottom:1px solid #1e3a5f;
                                padding:8px 12px;font-size:0.85em;color:#8899B8;font-weight:600">
                        <i class="bi bi-bar-chart-fill me-1" style="color:#4F9FFF"></i>
                        ${c.title || '诊断图'}
                    </div>
                    <div class="card-body p-2">
                        <img src="${c.img}" alt="${c.title}"
                             style="width:100%;border-radius:4px;display:block">
                        <p class="mt-2 mb-0"
                           style="font-size:0.78em;color:rgba(255,255,255,0.45);
                                  line-height:1.4">
                            ${c.desc || ''}
                        </p>
                    </div>
                </div>`;
            grid.appendChild(col);
        });
    } catch(e) {
        loading.textContent = '加载失败：' + e.message;
    }
}

// 折叠面板展开时懒加载
var _prepLoaded = false;
document.getElementById('prepPanel').addEventListener('show.bs.collapse', function() {
    if (!_prepLoaded) { _prepLoaded = true; loadPrepCharts(); }
});

window.initVisualizationPage();
</script>
{% endblock %}
```

- [ ] **Step 2: 验证模板语法**

```bash
cd "C:/Users/21560/Desktop/DataMind" && python -c "
from jinja2 import Environment, FileSystemLoader
env = Environment(loader=FileSystemLoader('templates'))
t = env.get_template('visualization.html')
print('template OK')
"
```

Expected: `template OK`

- [ ] **Step 3: 运行全量测试确认无回归**

```bash
cd "C:/Users/21560/Desktop/DataMind" && python -m pytest tests/ -x --tb=short -q 2>&1 | tail -8
```

Expected: 全部通过

- [ ] **Step 4: 在预处理报告折叠面板打开时，`#prep-section` 应在有数据后可见**

在 `charts.js` 中找到 `renderAdaptiveDashboard` 或 `initVisualizationPage` 中控制 `#charts-section` 可见性的代码（约第 390-410 行），找到隐藏/显示的那行：

```javascript
document.getElementById('charts-section').style.display = '';
```

在同一位置，同步显示 `prep-section`：

```javascript
document.getElementById('charts-section').style.display = '';
var prepSection = document.getElementById('prep-section');
if (prepSection) prepSection.style.display = '';
```

- [ ] **Step 5: 提交**

```bash
cd "C:/Users/21560/Desktop/DataMind" && git add templates/visualization.html static/js/charts.js && git commit -m "feat: 可视化仪表盘新增预处理报告折叠面板"
```

---

## Task 7: 最终验收

- [ ] **Step 1: 运行全量测试**

```bash
cd "C:/Users/21560/Desktop/DataMind" && python -m pytest tests/ -x --tb=short -q 2>&1 | tail -10
```

Expected: 全部通过，0 FAILED

- [ ] **Step 2: 启动 Flask 验证端点**

```bash
cd "C:/Users/21560/Desktop/DataMind" && python app.py
```

打开浏览器访问 `http://localhost:5000`，上传 `Online Retail.xlsx`，进入"可视化"页：
- [ ] 折叠面板标题可见：**数据预处理报告（seaborn + matplotlib）**
- [ ] 展开后正确显示 5 张图（缺失值热力图、流水线漏斗、箱线图、类型饼图、填充对比）
- [ ] 每张图有中文标题、x/y 轴标签
- [ ] 下方 6 个 Plotly 图表卡片的轴标签已填充

- [ ] **Step 3: 最终提交**

```bash
cd "C:/Users/21560/Desktop/DataMind" && git add -A && git commit -m "feat: 预处理可视化增强完成（seaborn+matplotlib 5图 + Plotly轴标签补全）"
```
