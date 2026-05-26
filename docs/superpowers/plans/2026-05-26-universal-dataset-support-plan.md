# DataMind 全数据集通用化 + 图表同步修复 实现计划

> **面向 AI 代理的工作者：** 使用 superpowers:subagent-driven-development 逐任务执行。步骤使用复选框（`- [ ]`）语法跟踪进度。

**目标：** 让 DataMind 五大模块对任意 CSV/Excel/JSON 数据集完整运行，修复图表双向同步，新增预处理可视化与清洗数据导出。

**架构：** DataProfiler 新模块检测数据画像（6种模式）→ 驱动 Analyzer/InsightEngine/ChatSession/前端仪表盘 按画像自适应；Loader 修复 CSV 分隔符嗅探；Chart sync 通过 window 全局 API 解决跨脚本状态共享。

**技术栈：** Python/Flask、pandas（csv.Sniffer）、Plotly.js、vanilla JS（window globals）、pytest

---

## 文件清单

| 文件 | 操作 | 职责 |
|------|------|------|
| `data/loader.py` | 修改 | 修复 CSV 分隔符自动嗅探 |
| `data/profiler.py` | 新建 | DataProfiler：6种画像检测、自描述生成、建议问题 |
| `data/analyzer.py` | 修改 | 新增通用分析方法（distributions/scatter/box/radar/preprocess_visual） |
| `ai/chat.py` | 修改 | 系统提示词注入全列信息+语义映射提示 |
| `ai/insight.py` | 修改 | 新增3类通用洞察（偏态/集中度/目标相关） |
| `routes/api.py` | 修改 | 新增5个端点（data_profile/adaptive_charts/suggested_questions/download_clean/preprocess_visual） |
| `static/js/chart-workspace.js` | 修改 | 修复 let→window，暴露 setWorkspaceChart API |
| `static/js/chat.js` | 修改 | 使用 window.setWorkspaceChart；Workspace→Chat 补全（无chart时新增消息） |
| `templates/index.html` | 修改 | 新增数据自描述卡片、预处理可视化区、下载按钮、自适应统计卡 |
| `static/js/overview.js` | 修改 | 渲染数据自描述、预处理图表、下载按钮 |
| `templates/visualization.html` | 修改 | 动态 chart-slot 结构 + 画像徽章 |
| `static/js/charts.js` | 修改 | 自适应仪表盘渲染（8种图类型） |
| `templates/analysis.html` | 修改 | 快捷提问按钮动态加载 |
| `tests/test_profiler.py` | 新建 | DataProfiler 单元测试 |
| `tests/test_loader_sep.py` | 新建 | CSV 分隔符检测测试 |
| `tests/test_analyzer_generic.py` | 新建 | 通用分析方法测试 |
| `tests/test_chart_sync.py` | 新建 | 图表同步端到端测试（略） |

---

## 任务 1：修复 CSV 分隔符嗅探

**文件：**
- 修改：`data/loader.py`
- 测试：`tests/test_loader_sep.py`

- [ ] **步骤 1：编写失败测试**

```python
# tests/test_loader_sep.py
import pytest
import pandas as pd
from data.loader import load_file
import tempfile, os

def _write_csv(content: str, suffix=".csv") -> str:
    f = tempfile.NamedTemporaryFile(mode="w", suffix=suffix, delete=False, encoding="utf-8")
    f.write(content)
    f.close()
    return f.name

def test_semicolon_separator():
    """分号分隔符 CSV 应正确解析为多列"""
    path = _write_csv("a;b;c\n1;2;3\n4;5;6\n")
    try:
        df = load_file(path)
        assert list(df.columns) == ["a", "b", "c"]
        assert len(df) == 2
    finally:
        os.unlink(path)

def test_tab_separator():
    path = _write_csv("x\ty\n10\t20\n")
    try:
        df = load_file(path)
        assert list(df.columns) == ["x", "y"]
    finally:
        os.unlink(path)

def test_comma_separator_unchanged():
    path = _write_csv("name,age\nAlice,30\nBob,25\n")
    try:
        df = load_file(path)
        assert list(df.columns) == ["name", "age"]
    finally:
        os.unlink(path)
```

- [ ] **步骤 2：运行测试验证失败**

```bash
cd C:\Users\21560\Desktop\DataMind
python -m pytest tests/test_loader_sep.py -v
```
预期：`FAILED test_semicolon_separator` —— `AssertionError: assert ['a;b;c'] == ['a', 'b', 'c']`

- [ ] **步骤 3：实现分隔符嗅探**

在 `data/loader.py` 顶部加 `import csv`，然后替换 `_read_csv` 函数：

```python
import csv  # 在现有 import 旁添加

def _detect_separator(file_path: str, encoding: str) -> str:
    """用 csv.Sniffer 自动检测分隔符，候选集: , ; \\t |"""
    try:
        with open(file_path, encoding=encoding, errors="replace") as f:
            sample = f.read(8192)
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        return dialect.delimiter
    except csv.Error:
        return ","


def _read_csv(file_path: str) -> pd.DataFrame:
    """
    读取 CSV，自动检测编码和分隔符。
    编码优先级：chardet → utf-8 → gbk → latin1
    分隔符：csv.Sniffer 自动嗅探（, ; \\t |），失败回退逗号
    """
    encodings = [_detect_encoding(file_path), "utf-8", "gbk", "latin1"]
    seen: set[str] = set()
    unique_encodings = [e for e in encodings if not (e in seen or seen.add(e))]  # type: ignore

    last_err: Exception = Exception("unknown")
    for enc in unique_encodings:
        try:
            sep = _detect_separator(file_path, enc)
            return pd.read_csv(file_path, encoding=enc, sep=sep)
        except (UnicodeDecodeError, LookupError) as e:
            last_err = e
            continue

    raise UnicodeDecodeError(
        "utf-8", b"", 0, 1,
        f"无法解析文件编码，尝试了 {unique_encodings}。原始错误：{last_err}",
    )
```

- [ ] **步骤 4：运行测试验证通过**

```bash
python -m pytest tests/test_loader_sep.py -v
```
预期：3 个测试全部 PASS

- [ ] **步骤 5：Commit**

```bash
git add data/loader.py tests/test_loader_sep.py
git commit -m "fix: CSV 分隔符自动嗅探，支持 ; \\t | 分隔的数据集"
```

---

## 任务 2：新建 DataProfiler 模块

**文件：**
- 新建：`data/profiler.py`
- 测试：`tests/test_profiler.py`

- [ ] **步骤 1：编写失败测试**

```python
# tests/test_profiler.py
import pandas as pd
import pytest
from data.profiler import DataProfiler

@pytest.fixture
def wine_df():
    """模拟葡萄酒数据集（12数值列）"""
    import numpy as np
    rng = np.random.default_rng(42)
    data = {col: rng.uniform(0, 10, 50) for col in
            ["fixed acidity","volatile acidity","citric acid","residual sugar",
             "chlorides","free sulfur dioxide","total sulfur dioxide","density",
             "pH","sulphates","alcohol"]}
    data["quality"] = rng.integers(3, 9, 50)
    return pd.DataFrame(data)

@pytest.fixture
def retail_df():
    """模拟零售数据集"""
    return pd.DataFrame({
        "InvoiceDate": pd.date_range("2021-01-01", periods=100, freq="D"),
        "CustomerID": range(100),
        "Description": ["Product"] * 100,
        "Quantity": [1] * 100,
        "UnitPrice": [9.99] * 100,
        "Country": ["UK"] * 100,
    })

@pytest.fixture
def categorical_df():
    return pd.DataFrame({
        "gender": ["M","F","F","M"] * 25,
        "education": ["高中","大学","研究生","高中"] * 25,
        "satisfaction": ["高","中","低","高"] * 25,
        "age": range(100),
    })

def test_wine_detected_as_numeric(wine_df):
    p = DataProfiler(wine_df)
    result = p.detect()
    assert result["mode"] == "numeric"
    assert result["display_name"] == "科学数值型"
    assert "alcohol" in result["numeric_cols"]
    assert result["target_col"] == "quality"
    assert result["has_date"] is False

def test_retail_detected_as_retail(retail_df):
    p = DataProfiler(retail_df)
    result = p.detect()
    assert result["mode"] == "retail"

def test_categorical_detected(categorical_df):
    p = DataProfiler(categorical_df)
    result = p.detect()
    assert result["mode"] in ("categorical", "mixed")
    assert "gender" in result["categorical_cols"]

def test_col_info_has_samples(wine_df):
    p = DataProfiler(wine_df)
    result = p.detect()
    assert "alcohol" in result["col_info"]
    assert len(result["col_info"]["alcohol"]["samples"]) == 3

def test_suggested_questions_nonempty(wine_df):
    p = DataProfiler(wine_df)
    result = p.detect()
    assert len(result["suggested_questions"]) >= 3

def test_description_nonempty(wine_df):
    p = DataProfiler(wine_df)
    result = p.detect()
    assert len(result["description"]) > 20
```

- [ ] **步骤 2：运行测试验证失败**

```bash
python -m pytest tests/test_profiler.py -v
```
预期：`ModuleNotFoundError: No module named 'data.profiler'`

- [ ] **步骤 3：实现 DataProfiler**

新建 `data/profiler.py`：

```python
"""
数据画像检测模块。

自动识别数据集类型（retail/temporal/numeric/categorical/geographic/mixed），
生成数据自描述、全列信息和建议问题，供 AI 系统提示词和自适应仪表盘使用。

来源：学生+AI
"""
from __future__ import annotations

import re
from typing import Any

import pandas as pd


# ── 关键词库 ──────────────────────────────────────────────────

_DATE_KEYWORDS   = re.compile(r"date|time|日期|时间|year|month|day|week", re.I)
_CUSTOMER_KWORDS = re.compile(r"customer|client|user|userid|客户|用户", re.I)
_PRODUCT_KWORDS  = re.compile(r"product|item|sku|description|商品|产品|物品", re.I)
_AMOUNT_KWORDS   = re.compile(r"price|amount|revenue|sales|total|金额|价格|销售", re.I)
_GEO_KEYWORDS    = re.compile(r"country|province|city|region|state|国家|省|城市|地区", re.I)

_MODE_NAMES = {
    "retail":      "零售交易型",
    "temporal":    "时间序列型",
    "numeric":     "科学数值型",
    "categorical": "分类调查型",
    "geographic":  "地理分布型",
    "mixed":       "混合型",
}

_MODE_ICONS = {
    "retail":      "🛒",
    "temporal":    "📈",
    "numeric":     "🔬",
    "categorical": "📊",
    "geographic":  "🌍",
    "mixed":       "◈",
}


class DataProfiler:
    """检测 DataFrame 的数据画像，驱动自适应分析和前端渲染。"""

    def __init__(self, df: pd.DataFrame) -> None:
        self._df = df

    # ── 公开接口 ──────────────────────────────────────────────

    def detect(self) -> dict[str, Any]:
        """
        检测数据画像，返回完整画像字典。

        Returns
        -------
        dict with keys:
          mode, display_name, icon, numeric_cols, categorical_cols,
          date_col, target_col, has_date, has_geography, has_customer,
          col_info, suggested_questions, description
        """
        df = self._df
        cols = list(df.columns)

        # ── 列分类 ──
        numeric_cols     = list(df.select_dtypes(include="number").columns)
        datetime_cols    = list(df.select_dtypes(include=["datetime", "datetimetz"]).columns)
        object_cols      = list(df.select_dtypes(include=["object", "category"]).columns)

        # 字符串列中低基数（≤50唯一值）视为类别列
        categorical_cols = [c for c in object_cols if df[c].nunique() <= 50]

        # 关键字匹配
        date_col     = self._find_col(cols, _DATE_KEYWORDS, datetime_cols)
        customer_col = self._find_col(cols, _CUSTOMER_KWORDS)
        product_col  = self._find_col(cols, _PRODUCT_KWORDS)
        amount_col   = self._find_col(cols, _AMOUNT_KWORDS, numeric_cols)
        geo_col      = self._find_col(cols, _GEO_KEYWORDS)

        has_date     = date_col is not None
        has_geography = geo_col is not None
        has_customer  = customer_col is not None

        # 自动检测目标列（最后一列数值列 or 名为 quality/label/target/score）
        target_col = self._detect_target(numeric_cols, cols)

        # ── 画像分类 ──
        mode = self._classify_mode(
            numeric_cols, categorical_cols, has_date,
            has_geography, has_customer, product_col, amount_col
        )

        # ── 列信息（注入 AI 系统提示词）──
        col_info = self._build_col_info()

        return {
            "mode":               mode,
            "display_name":       _MODE_NAMES[mode],
            "icon":               _MODE_ICONS[mode],
            "numeric_cols":       numeric_cols,
            "categorical_cols":   categorical_cols,
            "date_col":           date_col,
            "target_col":         target_col,
            "amount_col":         amount_col,
            "geo_col":            geo_col,
            "has_date":           has_date,
            "has_geography":      has_geography,
            "has_customer":       has_customer,
            "col_info":           col_info,
            "suggested_questions": self._suggest_questions(
                mode, numeric_cols, categorical_cols, date_col, target_col
            ),
            "description":        self._describe(
                mode, numeric_cols, categorical_cols, date_col, target_col
            ),
        }

    # ── 内部方法 ──────────────────────────────────────────────

    def _find_col(self, cols: list[str], pattern: re.Pattern,
                  candidates: list[str] | None = None) -> str | None:
        """在列名中用正则匹配第一个符合条件的列。"""
        search_cols = candidates if candidates is not None else cols
        for c in search_cols:
            if pattern.search(str(c)):
                return c
        return None

    def _detect_target(self, numeric_cols: list[str], all_cols: list[str]) -> str | None:
        """检测目标列：优先匹配名称关键字，其次取最后一个数值列。"""
        target_kw = re.compile(r"quality|label|target|score|class|output|result|grade", re.I)
        for c in numeric_cols:
            if target_kw.search(str(c)):
                return c
        # 最后一列为数值型时视为潜在目标
        if numeric_cols and numeric_cols[-1] == all_cols[-1]:
            return numeric_cols[-1]
        return None

    def _classify_mode(self, numeric_cols, categorical_cols, has_date,
                       has_geography, has_customer, product_col, amount_col) -> str:
        """按优先级规则分类数据画像。"""
        # 零售：有日期 + 客户 + 产品/金额
        if has_date and has_customer and (product_col or amount_col):
            return "retail"
        # 时间序列：有日期 + 数值列
        if has_date and numeric_cols:
            return "temporal"
        # 地理：有地理列
        if has_geography and numeric_cols:
            return "geographic"
        # 科学数值：≥4 数值列，类别列少
        if len(numeric_cols) >= 4 and len(categorical_cols) <= 2:
            return "numeric"
        # 分类调查：≥3 类别列
        if len(categorical_cols) >= 3:
            return "categorical"
        return "mixed"

    def _build_col_info(self) -> dict[str, dict]:
        """构建全列信息（类型 + 3个样本值），注入 AI 系统提示词。"""
        df = self._df
        info: dict[str, dict] = {}
        for col in df.columns:
            samples = df[col].dropna().head(3).tolist()
            info[str(col)] = {
                "dtype":   str(df[col].dtype),
                "samples": [str(s) for s in samples],
                "nunique": int(df[col].nunique()),
            }
        return info

    def _suggest_questions(self, mode: str, numeric_cols: list[str],
                           categorical_cols: list[str], date_col: str | None,
                           target_col: str | None) -> list[str]:
        """根据数据画像生成 4 个建议问题。"""
        qs: list[str] = []

        if mode == "retail":
            return ["月均销售额是多少？", "Top 10 畅销商品有哪些？",
                    "各国家销售额占比如何？", "画一个月度销售趋势折线图"]

        if mode == "temporal" and date_col:
            qs.append(f"按 {date_col} 展示数值趋势")

        if target_col and numeric_cols:
            qs.append(f"哪些特征与 {target_col} 相关性最高？")

        if numeric_cols:
            qs.append(f"{numeric_cols[0]} 列的分布情况如何？")
            if len(numeric_cols) >= 2:
                qs.append(f"画 {numeric_cols[0]} 和 {numeric_cols[1]} 的散点图")

        if categorical_cols:
            qs.append(f"{categorical_cols[0]} 列的频次分布是什么？")

        if len(qs) < 4 and numeric_cols:
            qs.append("哪些列存在异常值？")

        return qs[:4]

    def _describe(self, mode: str, numeric_cols: list[str],
                  categorical_cols: list[str], date_col: str | None,
                  target_col: str | None) -> str:
        """生成数据集自然语言自描述（规则引擎，零 API）。"""
        df   = self._df
        rows = len(df)
        cols = len(df.columns)
        mode_name = _MODE_NAMES[mode]

        parts = [f"这是一个包含 {rows:,} 条记录、{cols} 个字段的{mode_name}数据集。"]

        if numeric_cols:
            parts.append(
                f"数值型字段 {len(numeric_cols)} 个（{', '.join(numeric_cols[:4])}"
                f"{'等' if len(numeric_cols) > 4 else ''}）。"
            )

        if categorical_cols:
            parts.append(f"类别型字段 {len(categorical_cols)} 个（{', '.join(categorical_cols[:3])}）。")

        if date_col:
            try:
                date_series = pd.to_datetime(df[date_col], errors="coerce").dropna()
                if len(date_series) > 0:
                    parts.append(
                        f"时间跨度从 {date_series.min().date()} 到 {date_series.max().date()}。"
                    )
            except Exception:
                pass

        if target_col:
            try:
                tmin = df[target_col].min()
                tmax = df[target_col].max()
                parts.append(f"目标列 {target_col}（范围 {tmin}–{tmax}）。")
            except Exception:
                pass

        missing = int(df.isnull().sum().sum())
        if missing == 0:
            parts.append("数据无缺失值。")
        else:
            pct = missing / (rows * len(df.columns)) * 100
            parts.append(f"共有 {missing} 个缺失值（占比 {pct:.1f}%）。")

        return "".join(parts)
```

- [ ] **步骤 4：运行测试验证通过**

```bash
python -m pytest tests/test_profiler.py -v
```
预期：6 个测试全部 PASS

- [ ] **步骤 5：Commit**

```bash
git add data/profiler.py tests/test_profiler.py
git commit -m "feat: 新增 DataProfiler，支持 6 种数据画像自动检测"
```

---

## 任务 3：Analyzer 扩展通用分析方法

**文件：**
- 修改：`data/analyzer.py`
- 测试：`tests/test_analyzer_generic.py`

- [ ] **步骤 1：编写失败测试**

```python
# tests/test_analyzer_generic.py
import numpy as np
import pandas as pd
import pytest
from data.analyzer import Analyzer

@pytest.fixture
def num_df():
    rng = np.random.default_rng(0)
    return pd.DataFrame({
        "a": rng.uniform(0, 10, 100),
        "b": rng.uniform(0, 5, 100),
        "c": rng.uniform(1, 3, 100),
        "quality": rng.integers(3, 9, 100),
    })

@pytest.fixture
def cat_df():
    return pd.DataFrame({
        "color": ["red","blue","green"] * 34,
        "size":  ["S","M","L","XL"] * 25 + ["S","S"],
        "score": range(102),
    })

def test_numeric_distributions(num_df):
    az = Analyzer(num_df)
    result = az.numeric_distributions(max_cols=3)
    assert len(result) == 3
    assert "col" in result[0]
    assert "bins" in result[0]
    assert "counts" in result[0]
    assert len(result[0]["bins"]) == len(result[0]["counts"])

def test_category_distributions(cat_df):
    az = Analyzer(cat_df)
    result = az.category_distributions()
    assert len(result) >= 1
    assert "col" in result[0]
    assert "labels" in result[0]
    assert "counts" in result[0]

def test_scatter_top_pairs_returns_pairs(num_df):
    az = Analyzer(num_df)
    result = az.scatter_top_pairs(n_pairs=2)
    assert len(result) <= 2
    if result:
        assert "x_col" in result[0]
        assert "y_col" in result[0]
        assert len(result[0]["x"]) <= 500

def test_box_plots(num_df):
    az = Analyzer(num_df)
    result = az.box_plots(max_cols=4)
    assert len(result) >= 1
    assert "col" in result[0]
    assert "q1" in result[0]
    assert "median" in result[0]
    assert "q3" in result[0]

def test_preprocess_visual_no_crash(num_df):
    az = Analyzer(num_df)
    # 模拟预处理报告
    pp_report = {"duplicates_removed": 5, "missing_filled": 2,
                 "missing_dropped_cols": 0, "outliers_flagged": 3}
    result = az.preprocess_visual(pp_report)
    assert "before_after" in result
    assert "missing_heatmap" in result
```

- [ ] **步骤 2：运行测试确认失败**

```bash
python -m pytest tests/test_analyzer_generic.py -v
```
预期：`AttributeError: 'Analyzer' object has no attribute 'numeric_distributions'`

- [ ] **步骤 3：在 analyzer.py 末尾追加新方法**

在 `data/analyzer.py` 的 `Analyzer` 类末尾添加以下方法（在最后一个方法后、类定义结束前）：

```python
    # ── 通用分析方法（适用于任意数据集）────────────────────────

    def numeric_distributions(self, max_cols: int = 6) -> list[dict]:
        """
        返回 Top N 数值列的直方图数据。

        Returns: [{"col": str, "bins": list, "counts": list, "mean": float, "std": float}]
        """
        import numpy as np
        num_cols = list(self._df.select_dtypes(include="number").columns)[:max_cols]
        result = []
        for col in num_cols:
            series = self._df[col].dropna()
            if len(series) == 0:
                continue
            counts, bin_edges = np.histogram(series, bins=30)
            result.append({
                "col":    col,
                "bins":   [round(float(x), 4) for x in bin_edges],
                "counts": [int(x) for x in counts],
                "mean":   round(float(series.mean()), 4),
                "std":    round(float(series.std()), 4),
            })
        return result

    def category_distributions(self, max_cols: int = 4,
                                max_categories: int = 20) -> list[dict]:
        """
        返回低基数类别列的频次数据。

        Returns: [{"col": str, "labels": list, "counts": list}]
        """
        cat_cols = [
            c for c in self._df.select_dtypes(include=["object", "category"]).columns
            if self._df[c].nunique() <= max_categories
        ][:max_cols]
        result = []
        for col in cat_cols:
            vc = self._df[col].value_counts()
            result.append({
                "col":    col,
                "labels": [str(x) for x in vc.index.tolist()],
                "counts": [int(x) for x in vc.values.tolist()],
            })
        return result

    def scatter_top_pairs(self, n_pairs: int = 3, sample_n: int = 500) -> list[dict]:
        """
        取相关性最高的 N 对数值列返回散点图数据（最多 sample_n 个采样点）。

        Returns: [{"x_col": str, "y_col": str, "x": list, "y": list, "corr": float}]
        """
        num_cols = list(self._df.select_dtypes(include="number").columns)
        if len(num_cols) < 2:
            return []
        corr_matrix = self._df[num_cols].corr().abs()
        pairs: list[tuple[float, str, str]] = []
        seen: set[frozenset] = set()
        for i, c1 in enumerate(num_cols):
            for c2 in num_cols[i + 1:]:
                key = frozenset([c1, c2])
                if key not in seen:
                    seen.add(key)
                    pairs.append((corr_matrix.loc[c1, c2], c1, c2))
        pairs.sort(reverse=True)
        result = []
        for corr_val, c1, c2 in pairs[:n_pairs]:
            sub = self._df[[c1, c2]].dropna()
            if len(sub) > sample_n:
                sub = sub.sample(sample_n, random_state=42)
            result.append({
                "x_col": c1,
                "y_col": c2,
                "x":     [round(float(v), 4) for v in sub[c1].tolist()],
                "y":     [round(float(v), 4) for v in sub[c2].tolist()],
                "corr":  round(float(corr_val), 4),
            })
        return result

    def box_plots(self, max_cols: int = 6) -> list[dict]:
        """
        返回数值列的箱线图统计数据。

        Returns: [{"col": str, "q1": float, "median": float, "q3": float,
                   "lower": float, "upper": float, "outliers": list}]
        """
        num_cols = list(self._df.select_dtypes(include="number").columns)[:max_cols]
        result = []
        for col in num_cols:
            series = self._df[col].dropna()
            if len(series) == 0:
                continue
            q1 = float(series.quantile(0.25))
            q3 = float(series.quantile(0.75))
            iqr = q3 - q1
            lower = q1 - 1.5 * iqr
            upper = q3 + 1.5 * iqr
            outliers = series[(series < lower) | (series > upper)].tolist()
            result.append({
                "col":      col,
                "q1":       round(q1, 4),
                "median":   round(float(series.median()), 4),
                "q3":       round(q3, 4),
                "lower":    round(lower, 4),
                "upper":    round(upper, 4),
                "outliers": [round(float(x), 4) for x in outliers[:50]],
            })
        return result

    def preprocess_visual(self, pp_report: dict) -> dict:
        """
        生成预处理可视化数据（前后对比 + 缺失值热力图）。

        Returns:
          {
            "before_after": [{"step": str, "before": int, "after": int}],
            "missing_heatmap": [{"col": str, "missing_count": int, "missing_pct": float}]
          }
        """
        rows_orig = len(self._df) + pp_report.get("duplicates_removed", 0)
        rows_clean = len(self._df)

        before_after = [
            {
                "step":   "去重",
                "before": rows_orig,
                "after":  rows_clean,
                "removed": pp_report.get("duplicates_removed", 0),
            },
            {
                "step":   "缺失值处理",
                "before": pp_report.get("missing_filled", 0) + pp_report.get("missing_dropped_cols", 0),
                "after":  0,
                "removed": pp_report.get("missing_filled", 0),
            },
        ]

        missing_heatmap = []
        for col in self._df.columns:
            mc = int(self._df[col].isnull().sum())
            missing_heatmap.append({
                "col":          col,
                "missing_count": mc,
                "missing_pct":  round(mc / max(len(self._df), 1) * 100, 2),
            })

        return {
            "before_after":   before_after,
            "missing_heatmap": missing_heatmap,
        }
```

- [ ] **步骤 4：运行测试验证通过**

```bash
python -m pytest tests/test_analyzer_generic.py -v
```
预期：5 个测试全部 PASS

- [ ] **步骤 5：Commit**

```bash
git add data/analyzer.py tests/test_analyzer_generic.py
git commit -m "feat: Analyzer 新增通用分析方法（distributions/scatter/box/preprocess_visual）"
```

---

## 任务 4：ChatSession 全列语义感知重写

**文件：**
- 修改：`ai/chat.py`

- [ ] **步骤 1：替换 `build_system_prompt` 方法**

在 `ai/chat.py` 中，将 `build_system_prompt` 方法完整替换为：

```python
    def build_system_prompt(self) -> str:
        """
        根据数据集摘要和数据画像动态构建系统提示词。

        包含：数据画像名称、完整列信息（名称+类型+样本值）、语义映射提示、操作规范。
        """
        rows      = self.df_summary.get("row_count", "未知")
        cols_count = self.df_summary.get("column_count", "未知")
        mode_name  = self.df_summary.get("profile_mode_name", "数据集")

        # 构建完整列信息表（用于语义映射）
        col_info: dict = self.df_summary.get("col_info", {})
        if col_info:
            col_lines = []
            for col_name, info in col_info.items():
                samples_str = ", ".join(info.get("samples", [])[:3])
                col_lines.append(f"  - {col_name} ({info.get('dtype','')})：样本值 [{samples_str}]")
            col_table = "\n".join(col_lines)
        else:
            # 降级：只展示数值列
            num_cols = list(self.df_summary.get("numeric_stats", {}).keys())
            col_table = "  - " + "\n  - ".join(num_cols) if num_cols else "  （无）"

        return f"""你是一个专业的数据分析助手，帮助用户分析已上传的数据集。

【数据集信息】
- 类型：{mode_name}
- 行数：{rows}
- 列数：{cols_count}

【完整列信息（使用精确列名编写代码）】
{col_table}

【操作规范】
1. 变量名固定为 df（已在执行环境中提供），**计算结果必须赋值给 result 变量**
2. **禁止写任何 import 语句**。以下库已在环境中预加载，直接使用：
   - pd（pandas）、np（numpy）、px（plotly.express）、go（plotly.graph_objects）
3. **使用上方列表中的精确列名**，禁止翻译或猜测列名。
   例如：用户说"酒精浓度"→ 使用列名 `alcohol`；用户说"销售金额"→ 使用列名 `UnitPrice` 或 `Quantity`
4. 如果问题适合可视化，将 Plotly Figure 赋值给 chart 变量：
   ```python
   fig = px.bar(df, x='colA', y='colB', title='标题')
   chart = fig
   result = df.groupby('colA')['colB'].sum()
   ```
5. 代码放在 ```python ... ``` 块中，自然语言解释放在代码块外
6. 代码执行完毕后，用自然语言解释结论（如"根据分析，alcohol 均值为 10.4，质量评分与酒精浓度相关系数为 0.48"）
7. 如需输出中间信息请使用 print()，语言优先中文"""
```

- [ ] **步骤 2：更新调用方，传入 profile 信息**

在 `routes/api.py` 的 `upload()` 函数中，`_rebuild_state_from_file` 内，确保 `df_summary` 包含画像信息。找到 `_rebuild_state_from_file` 函数并在返回 `df_summary` 前追加：

```python
# 在 _rebuild_state_from_file 末尾（return 前）添加：
try:
    from data.profiler import DataProfiler
    profile = DataProfiler(df_clean).detect()
    df_summary["col_info"]            = profile["col_info"]
    df_summary["profile_mode"]        = profile["mode"]
    df_summary["profile_mode_name"]   = profile["display_name"]
    df_summary["suggested_questions"] = profile["suggested_questions"]
    df_summary["description"]         = profile["description"]
    df_summary["target_col"]          = profile["target_col"]
    state["profile"]                  = profile
except Exception:
    pass  # 画像检测失败不影响核心功能
```

- [ ] **步骤 3：手动验证**

启动 Flask，上传 `winequality-red.csv`，在智能问答页发送"alcohol 列的平均值是多少"。AI 的系统提示词中应出现 `alcohol (float64)：样本值 [...]`，AI 应能生成 `df['alcohol'].mean()` 而不是猜测列名。

- [ ] **步骤 4：Commit**

```bash
git add ai/chat.py routes/api.py
git commit -m "feat: ChatSession 全列语义感知，系统提示词注入精确列名和数据画像"
```

---

## 任务 5：新增 5 个 API 端点

**文件：**
- 修改：`routes/api.py`

- [ ] **步骤 1：在 routes/api.py 的 `insights` 端点之后添加以下 5 个端点**

```python
@api_bp.route("/analysis/data_profile")
def data_profile():
    """返回数据画像（6种模式 + 列信息 + 建议问题 + 自描述）。"""
    err = _require_data()
    if err:
        return err
    state = _state()
    profile = state.get("profile")
    if profile is None:
        from data.profiler import DataProfiler
        profile = DataProfiler(state["df_clean"]).detect()
        state["profile"] = profile
    return jsonify(profile)


@api_bp.route("/analysis/adaptive_charts")
def adaptive_charts():
    """
    按数据画像返回 6 个自适应图表配置。
    每个配置包含 type/title/data，由前端 Plotly 渲染。
    """
    err = _require_data()
    if err:
        return err
    state  = _state()
    df     = state["df_clean"]
    az     = state["analyzer"]
    profile = state.get("profile") or {}
    mode   = profile.get("mode", "mixed")
    pp_report = state.get("preprocess_report", {})

    charts: list[dict] = []

    if mode == "retail":
        # 保留原有零售图表
        _methods = ["sales_trend", "top_products", "country_distribution",
                    "correlation_matrix", "time_pattern", "rfm_analysis"]
        for m in _methods:
            try:
                data = getattr(az, m)()
                charts.append({"method": m, "data": data, "source": "retail"})
            except Exception as e:
                charts.append({"method": m, "data": None, "error": str(e), "source": "retail"})
        return jsonify(charts)

    # 通用路径：按画像选择图表
    numeric_cols     = profile.get("numeric_cols", [])
    categorical_cols = profile.get("categorical_cols", [])
    target_col       = profile.get("target_col")
    date_col         = profile.get("date_col")

    # 图表 1：数值分布直方图（或时序折线）
    if mode == "temporal" and date_col:
        try:
            charts.append({
                "type": "line", "title": f"{date_col} 时间趋势",
                "data": az.sales_trend(), "source": "temporal"
            })
        except Exception:
            charts.append(_make_hist_chart(az, numeric_cols))
    else:
        charts.append(_make_hist_chart(az, numeric_cols))

    # 图表 2：相关性矩阵（任意数值型数据集通用）
    try:
        charts.append({
            "type": "heatmap", "title": "相关性矩阵",
            "data": az.correlation_matrix(), "source": "generic"
        })
    except Exception:
        charts.append({"type": "heatmap", "title": "相关性矩阵", "data": None})

    # 图表 3：箱线图
    box_data = az.box_plots(max_cols=6)
    charts.append({"type": "box", "title": "数值列分布箱线图",
                   "data": box_data, "source": "generic"})

    # 图表 4：散点图（最高相关对）或类别频次
    if len(numeric_cols) >= 2:
        scatter_data = az.scatter_top_pairs(n_pairs=1)
        if scatter_data:
            pair = scatter_data[0]
            charts.append({
                "type": "scatter",
                "title": f"{pair['x_col']} vs {pair['y_col']}（相关系数 {pair['corr']:.2f}）",
                "data": scatter_data, "source": "generic"
            })
        else:
            charts.append(_make_cat_chart(az, categorical_cols))
    else:
        charts.append(_make_cat_chart(az, categorical_cols))

    # 图表 5：目标列分布 or 类别列
    if target_col:
        try:
            vc = df[target_col].value_counts()
            charts.append({
                "type": "bar",
                "title": f"{target_col} 分布",
                "data": {"labels": [str(x) for x in vc.index.tolist()],
                         "counts": [int(x) for x in vc.values.tolist()],
                         "col": target_col},
                "source": "generic"
            })
        except Exception:
            charts.append(_make_cat_chart(az, categorical_cols))
    elif categorical_cols:
        charts.append(_make_cat_chart(az, categorical_cols))
    else:
        charts.append(_make_hist_chart(az, numeric_cols, offset=1))

    # 图表 6：预处理前后对比
    viz = az.preprocess_visual(pp_report)
    charts.append({"type": "bar_grouped", "title": "数据清洗前后对比",
                   "data": viz["before_after"], "source": "preprocess"})

    return jsonify(charts)


def _make_hist_chart(az, numeric_cols: list, offset: int = 0) -> dict:
    """构造直方图图表配置，offset 用于选取不同列。"""
    try:
        data = az.numeric_distributions(max_cols=6)
        if offset and len(data) > offset:
            data = data[offset:]
        return {"type": "histogram", "title": "数值列分布", "data": data, "source": "generic"}
    except Exception:
        return {"type": "histogram", "title": "数值列分布", "data": [], "source": "generic"}


def _make_cat_chart(az, categorical_cols: list) -> dict:
    """构造类别频次图表配置。"""
    try:
        data = az.category_distributions(max_cols=1)
        col  = data[0]["col"] if data else "分类列"
        return {"type": "bar", "title": f"{col} 频次分布", "data": data[0] if data else {}, "source": "generic"}
    except Exception:
        return {"type": "bar", "title": "分类频次", "data": {}, "source": "generic"}


@api_bp.route("/analysis/suggested_questions")
def suggested_questions():
    """返回 4 个基于真实数据的建议问题。"""
    err = _require_data()
    if err:
        return err
    state   = _state()
    profile = state.get("profile") or {}
    qs      = profile.get("suggested_questions", [
        "这份数据有哪些主要特征？",
        "哪些列有异常值？",
        "数值列的分布情况如何？",
        "列之间的相关性如何？",
    ])
    return jsonify(qs)


@api_bp.route("/data/download-clean")
def download_clean():
    """下载清洗后的 DataFrame 为 CSV 文件。"""
    err = _require_data()
    if err:
        return err
    import io
    state = _state()
    df    = state["df_clean"]
    buf   = io.StringIO()
    df.to_csv(buf, index=False, encoding="utf-8-sig")
    buf.seek(0)
    from flask import Response
    return Response(
        buf.getvalue().encode("utf-8-sig"),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=cleaned_data.csv"},
    )


@api_bp.route("/analysis/preprocess_visual")
def preprocess_visual_api():
    """返回预处理可视化数据（前后对比 + 缺失值热力图）。"""
    err = _require_data()
    if err:
        return err
    state     = _state()
    az        = state["analyzer"]
    pp_report = state.get("preprocess_report", {})
    return jsonify(az.preprocess_visual(pp_report))
```

- [ ] **步骤 2：手动测试端点**

```bash
# 启动 Flask，上传数据后：
curl http://localhost:5000/api/analysis/data_profile
curl http://localhost:5000/api/analysis/suggested_questions
curl http://localhost:5000/api/data/download-clean -o cleaned_data.csv
```

验证：`data_profile` 返回正确 mode，`suggested_questions` 返回 4 个问题，`download-clean` 成功下载 CSV。

- [ ] **步骤 3：Commit**

```bash
git add routes/api.py
git commit -m "feat: 新增 5 个通用化 API 端点（data_profile/adaptive_charts/suggested_questions/download_clean/preprocess_visual）"
```

---

## 任务 6：修复图表双向同步

**文件：**
- 修改：`static/js/chart-workspace.js`
- 修改：`static/js/chat.js`

### Bug A 修复：`let` → `window` 全局状态

- [ ] **步骤 1：修改 chart-workspace.js 变量声明**

将 `chart-workspace.js` 第 11-13 行：
```javascript
let _chartWorkspace = null;
let _currentChartData = null;
let _currentChartCode = '';
```
替换为：
```javascript
window._chartWorkspace = null;
window._currentChartData = null;
window._currentChartCode = '';
```

同时在该文件中，所有对 `_currentChartData`、`_currentChartCode` 的赋值都已通过 `window.` 前缀或直接赋值（脚本顶层 var 等效），无需额外修改其他引用（浏览器全局作用域中直接访问 `_currentChartData` 等同于 `window._currentChartData`）。

- [ ] **步骤 2：修改 chat.js 使用 window setter**

在 `chat.js` 的 `onChart` 回调中，将：
```javascript
if (typeof _currentChartData !== 'undefined') _currentChartData = chartData;
```
替换为：
```javascript
window._currentChartData = chartData;  // 直接写入，无需判断
```

### Bug B 修复：Workspace→Chat 无图表时新增同步消息

- [ ] **步骤 3：更新 updateChatChartFromWorkspace**

在 `chat.js` 中，将整个 `window.updateChatChartFromWorkspace` 函数替换为：

```javascript
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
```

- [ ] **步骤 4：浏览器验证同步**

1. 启动 Flask，上传数据集
2. 在 NL2Vis 工作台输入描述生成图表 → 图表应**同时**出现在右侧工作台和左侧对话区（新增系统消息）
3. 在对话区发问生成图表 → 图表应**同时**出现在对话气泡和右侧工作台

- [ ] **步骤 5：Commit**

```bash
git add static/js/chart-workspace.js static/js/chat.js
git commit -m "fix: 修复图表双向同步（let→window 全局状态 + Workspace→Chat 补全消息）"
```

---

## 任务 7：数据概览页增强（自描述 + 预处理可视化 + 下载 + 自适应统计卡）

**文件：**
- 修改：`templates/index.html`
- 修改：`static/js/overview.js`（或在 index.html script 块中）

- [ ] **步骤 1：在 index.html 的「预处理摘要」section 之前插入数据自描述卡片**

找到 `<!-- 预处理摘要 -->` 注释，在其前面插入：

```html
<!-- 数据自描述卡片 -->
<div id="data-description-card" class="card mb-4" style="display:none">
    <div class="card-header d-flex align-items-center gap-2">
        <span id="profile-icon" style="font-size:1.1em">◈</span>
        <span id="profile-display-name" style="color:var(--cyan)">数据集类型检测中…</span>
    </div>
    <div class="card-body">
        <p id="data-description-text" class="mb-2" style="color:rgba(255,255,255,0.8);line-height:1.7"></p>
    </div>
</div>
```

- [ ] **步骤 2：在「预处理摘要」card-header 右侧添加下载按钮**

找到预处理摘要的 `card-header`，将其改为：

```html
<div class="card-header d-flex align-items-center justify-content-between">
    <span class="d-flex align-items-center gap-2">
        <i class="bi bi-gear" style="color:var(--cyan)"></i>
        预处理摘要
    </span>
    <button id="download-clean-btn" class="btn btn-outline-secondary btn-sm"
            onclick="downloadCleanData()" title="下载清洗后的数据">
        <i class="bi bi-download me-1"></i>下载清洗数据 CSV
    </button>
</div>
```

- [ ] **步骤 3：在预处理摘要 card-body 末尾添加可视化区域**

在 `<div class="prep-timeline px-4 py-2" id="prep-timeline"></div>` 之后：

```html
<!-- 预处理可视化 -->
<div id="preprocess-viz" class="px-4 pb-3" style="display:none">
    <div class="row g-3 mt-1">
        <div class="col-12 col-md-6">
            <div style="font-size:0.8em;color:var(--blue);margin-bottom:4px">
                <i class="bi bi-bar-chart-steps me-1"></i>清洗前后数据量对比
            </div>
            <div id="chart-preprocess-ba" style="height:160px"></div>
        </div>
        <div class="col-12 col-md-6">
            <div style="font-size:0.8em;color:var(--cyan);margin-bottom:4px">
                <i class="bi bi-table me-1"></i>各列缺失率
            </div>
            <div id="chart-missing-heatmap" style="height:160px"></div>
        </div>
    </div>
</div>
```

- [ ] **步骤 4：修改统计卡片显示逻辑（自适应内容）**

将 `stat-daterange` 卡片的标题和 `stat-revenue` 卡片的标题改为可动态替换：

```html
<!-- 第3个指标卡 - 改为动态标签 -->
<div class="metric-card" style="--accent-line: linear-gradient(90deg,#00D4FF,#0EA5E9)">
    <div class="metric-icon" style="background:rgba(0,212,255,.12);color:#00D4FF">
        <i id="stat-col3-icon" class="bi bi-calendar-range"></i>
    </div>
    <div>
        <div class="metric-value" id="stat-col3" style="font-size:1rem">—</div>
        <div class="metric-label" id="stat-col3-label">时间跨度</div>
    </div>
</div>
<!-- 第4个指标卡 - 改为动态标签 -->
<div class="metric-card" style="--accent-line: linear-gradient(90deg,#FFB347,#FF8C00)">
    <div class="metric-icon" style="background:rgba(255,179,71,.13);color:#FFB347">
        <i id="stat-col4-icon" class="bi bi-currency-dollar"></i>
    </div>
    <div>
        <div class="metric-value" id="stat-col4" style="font-size:1.4rem">—</div>
        <div class="metric-label" id="stat-col4-label">总销售额</div>
    </div>
</div>
```

- [ ] **步骤 5：在 index.html script 块添加新 JS 函数**

在 `{% block scripts %}` 末尾添加：

```javascript
// ── 数据自描述 ─────────────────────────────────────────────
async function loadDataProfile() {
    try {
        const r = await fetch('/api/analysis/data_profile');
        if (!r.ok) return;
        const p = await r.json();

        // 数据自描述卡片
        const card = document.getElementById('data-description-card');
        if (card) {
            document.getElementById('profile-icon').textContent = p.icon || '◈';
            document.getElementById('profile-display-name').textContent =
                (p.display_name || '混合型') + '数据集';
            document.getElementById('data-description-text').textContent =
                p.description || '';
            card.style.display = '';
        }

        // 自适应统计卡（第3、4卡）
        _updateAdaptiveStatCards(p);

    } catch(e) { /* 静默失败 */ }
}

function _updateAdaptiveStatCards(profile) {
    const mode = profile.mode || 'mixed';
    const col3Label = document.getElementById('stat-col3-label');
    const col3Val   = document.getElementById('stat-col3');
    const col3Icon  = document.getElementById('stat-col3-icon');
    const col4Label = document.getElementById('stat-col4-label');
    const col4Val   = document.getElementById('stat-col4');
    const col4Icon  = document.getElementById('stat-col4-icon');
    if (!col3Label) return;

    if (mode === 'numeric' || mode === 'categorical') {
        col3Label.textContent = '数值列数';
        col3Icon.className    = 'bi bi-123';
        col3Val.textContent   = (profile.numeric_cols || []).length || '—';

        const targetCol = profile.target_col;
        col4Label.textContent = targetCol ? `${targetCol} 均值` : '类别列数';
        col4Icon.className    = targetCol ? 'bi bi-bullseye' : 'bi bi-tags';
        col4Val.textContent   = '—';  // 实际值从 summary 获取
    } else if (mode === 'geographic') {
        col3Label.textContent = '数值列数';
        col3Icon.className    = 'bi bi-123';
        col3Val.textContent   = (profile.numeric_cols || []).length || '—';
        col4Label.textContent = '地理列';
        col4Icon.className    = 'bi bi-geo-alt';
        col4Val.textContent   = profile.geo_col || '—';
    }
    // retail / temporal 保持原样（时间跨度 + 总销售额）
}

// ── 预处理可视化 ───────────────────────────────────────────
async function loadPreprocessViz() {
    if (typeof Plotly === 'undefined') return;
    try {
        const r = await fetch('/api/analysis/preprocess_visual');
        if (!r.ok) return;
        const viz = await r.json();

        // 清洗前后对比图
        const baData = viz.before_after || [];
        if (baData.length > 0) {
            const steps   = baData.map(d => d.step);
            const removed = baData.map(d => d.removed || 0);
            Plotly.newPlot('chart-preprocess-ba', [{
                type: 'bar', x: steps, y: removed,
                marker: { color: ['rgba(79,159,255,0.8)', 'rgba(0,212,255,0.8)'] },
                text: removed.map(v => v > 0 ? v + ' 行' : '无变化'),
                textposition: 'auto',
            }], {
                paper_bgcolor: 'transparent', plot_bgcolor: 'transparent',
                font: { color: '#fff', size: 11 },
                margin: { t: 10, b: 30, l: 40, r: 10 },
                yaxis: { gridcolor: 'rgba(255,255,255,0.08)' },
                showlegend: false,
            }, { responsive: true, displayModeBar: false });
        }

        // 缺失率热力图（横向条形图）
        const missing = (viz.missing_heatmap || []).filter(d => d.missing_count > 0);
        if (missing.length > 0) {
            const cols = missing.map(d => d.col);
            const pcts = missing.map(d => d.missing_pct);
            Plotly.newPlot('chart-missing-heatmap', [{
                type: 'bar', orientation: 'h',
                x: pcts, y: cols,
                marker: { color: pcts.map(p => p > 10 ? 'rgba(255,76,76,0.8)' : 'rgba(79,255,140,0.8)') },
                text: pcts.map(p => p.toFixed(1) + '%'),
                textposition: 'auto',
            }], {
                paper_bgcolor: 'transparent', plot_bgcolor: 'transparent',
                font: { color: '#fff', size: 10 },
                margin: { t: 10, b: 20, l: 100, r: 30 },
                xaxis: { title: '缺失率 (%)', gridcolor: 'rgba(255,255,255,0.08)' },
            }, { responsive: true, displayModeBar: false });
        } else {
            // 无缺失值 → 显示绿色提示
            document.getElementById('chart-missing-heatmap').innerHTML =
                '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:var(--green)">' +
                '<i class="bi bi-check-circle me-2"></i>所有列均无缺失值</div>';
        }

        document.getElementById('preprocess-viz').style.display = '';
    } catch(e) { /* 静默失败 */ }
}

// ── 下载清洗后数据 ─────────────────────────────────────────
function downloadCleanData() {
    window.location.href = '/api/data/download-clean';
}
```

- [ ] **步骤 6：在 `initOverviewPage()` 或数据加载成功回调中调用新函数**

找到 overview.js（或 index.html script 块）中数据加载成功后的回调，在现有调用末尾追加：

```javascript
loadDataProfile();
loadPreprocessViz();
```

- [ ] **步骤 7：浏览器验证**

上传 `winequality-red.csv`（分号分隔）：
- [ ] 数据自描述卡片显示"科学数值型数据集"及自动生成的描述
- [ ] 第3卡显示"数值列数: 12"而非"—"
- [ ] 预处理区有两个 Plotly 图表
- [ ] "下载清洗数据 CSV"按钮可下载包含12列的 CSV

- [ ] **步骤 8：Commit**

```bash
git add templates/index.html
git commit -m "feat: 数据概览页新增自描述卡片、预处理可视化图表、下载清洗数据按钮、自适应统计卡"
```

---

## 任务 8：自适应可视化仪表盘

**文件：**
- 修改：`templates/visualization.html`
- 修改：`static/js/charts.js`

- [ ] **步骤 1：重写 visualization.html 为动态 slot 结构**

将 `templates/visualization.html` 的 `{% block content %}` 完整替换为：

```html
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

<div id="charts-section" style="display:none">
    <div id="adaptive-charts-grid" class="row g-4">
        <!-- 由 renderAdaptiveDashboard() 动态填充 6 个 chart-card -->
    </div>
</div>
{% endblock %}
```

- [ ] **步骤 2：在 charts.js 中新增自适应渲染函数**

在 `static/js/charts.js` 的 `window.initVisualizationPage` 函数中，**增加自适应逻辑**：

将原来的函数改为：

```javascript
window.initVisualizationPage = async function () {
    var noDataAlert   = document.getElementById('no-data-alert');
    var chartsSection = document.getElementById('charts-section');
    if (!noDataAlert || !chartsSection) return;

    // 检查是否有数据
    try {
        const ping = await fetch('/api/data/summary');
        if (!ping.ok) {
            noDataAlert.style.display = '';
            chartsSection.style.display = 'none';
            return;
        }
    } catch(e) {
        noDataAlert.style.display = '';
        chartsSection.style.display = 'none';
        return;
    }

    noDataAlert.style.display = 'none';
    chartsSection.style.display = '';

    // 获取数据画像
    let profile = {};
    try {
        const r = await fetch('/api/analysis/data_profile');
        if (r.ok) profile = await r.json();
    } catch(e) {}

    // 更新画像徽章
    _updateProfileBadge(profile);

    // 零售模式：保持原有渲染逻辑
    if (profile.mode === 'retail') {
        _renderRetailDashboard();
        return;
    }

    // 通用模式：自适应渲染
    await _renderAdaptiveDashboard(profile);
};

function _updateProfileBadge(profile) {
    var badge     = document.getElementById('profile-badge');
    var badgeIcon = document.getElementById('profile-badge-icon');
    var badgeName = document.getElementById('profile-badge-name');
    if (!badge) return;
    const modeColors = {
        retail:      '#FFB347',
        temporal:    'var(--blue)',
        numeric:     'var(--cyan)',
        categorical: 'var(--purple)',
        geographic:  'var(--green)',
        mixed:       'rgba(255,255,255,0.6)',
    };
    const color = modeColors[profile.mode] || 'var(--blue)';
    badge.style.color         = color;
    badge.style.borderColor   = color;
    badge.style.display       = '';
    if (badgeIcon) badgeIcon.textContent = profile.icon || '◈';
    if (badgeName) badgeName.textContent = profile.display_name || '混合型';
}

async function _renderAdaptiveDashboard(profile) {
    var grid = document.getElementById('adaptive-charts-grid');
    if (!grid) return;

    // 显示加载骨架
    grid.innerHTML = Array(6).fill(0).map((_, i) =>
        `<div class="col-12 col-xl-6">
            <div class="card chart-card">
                <div class="card-header" style="color:rgba(255,255,255,0.4)">
                    <i class="bi bi-hourglass-split me-2"></i>加载中…
                </div>
                <div class="card-body p-1">
                    <div id="chart-slot-${i}" style="height:290px;display:flex;align-items:center;justify-content:center;color:rgba(255,255,255,0.2)">
                        <i class="bi bi-bar-chart" style="font-size:2rem"></i>
                    </div>
                </div>
            </div>
        </div>`
    ).join('');

    // 获取自适应图表数据
    let charts = [];
    try {
        const r = await fetch('/api/analysis/adaptive_charts');
        if (r.ok) charts = await r.json();
    } catch(e) {
        grid.innerHTML = '<div class="col-12"><div class="alert alert-warning">图表加载失败，请刷新重试。</div></div>';
        return;
    }

    // 渲染每个图表 slot
    charts.forEach(function(cfg, i) {
        _updateSlotHeader(i, cfg.title || '图表');
        _renderChartSlot(i, cfg);
    });
}

function _updateSlotHeader(index, title) {
    // 更新第 index 个 card-header 的标题文字
    var slot = document.getElementById('chart-slot-' + index);
    if (!slot) return;
    var header = slot.closest('.card')?.querySelector('.card-header');
    if (header) header.innerHTML = `<i class="bi bi-graph-up me-2" style="color:var(--cyan)"></i>${title}`;
}

function _renderChartSlot(index, cfg) {
    var container = document.getElementById('chart-slot-' + index);
    if (!container || !window.Plotly) return;

    if (!cfg || !cfg.data) {
        container.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:rgba(255,255,255,0.3);font-size:0.85em"><i class="bi bi-dash-circle me-2"></i>当前数据集无此维度</div>';
        return;
    }

    const layout_base = {
        paper_bgcolor: 'transparent', plot_bgcolor: 'transparent',
        font: { color: '#fff', size: 11 },
        margin: { t: 20, b: 40, l: 50, r: 20 },
        yaxis: { gridcolor: 'rgba(255,255,255,0.07)' },
        xaxis: { gridcolor: 'rgba(255,255,255,0.07)' },
        showlegend: false,
    };
    const opts = { responsive: true, displayModeBar: false };

    try {
        switch (cfg.type) {
            case 'histogram':
                _plotHistogram(container, cfg.data, layout_base, opts); break;
            case 'heatmap':
                _plotHeatmap(container, cfg.data, layout_base, opts); break;
            case 'scatter':
                _plotScatter(container, cfg.data, layout_base, opts); break;
            case 'bar':
                _plotBar(container, cfg.data, layout_base, opts); break;
            case 'bar_grouped':
                _plotBarGrouped(container, cfg.data, layout_base, opts); break;
            case 'box':
                _plotBox(container, cfg.data, layout_base, opts); break;
            case 'line':
                _plotLine(container, cfg.data, layout_base, opts); break;
            default:
                // 原有零售图表：data/layout 格式
                if (cfg.data && cfg.data.data) {
                    Plotly.react(container, cfg.data.data, { ...layout_base, ...(cfg.data.layout || {}) }, opts);
                }
        }
    } catch(e) {
        console.error('图表渲染失败 slot', index, e);
        container.innerHTML = '<div style="text-align:center;padding:20px;color:rgba(255,255,255,0.3);font-size:0.82em">图表渲染失败</div>';
    }
}

function _plotHistogram(el, data, layout, opts) {
    if (!Array.isArray(data) || data.length === 0) return;
    const traces = data.map(d => ({
        type: 'bar', name: d.col,
        x: d.bins ? d.bins.slice(0, -1).map((v, i) => ((v + d.bins[i+1]) / 2).toFixed(2)) : [],
        y: d.counts || [],
        opacity: 0.8,
    }));
    Plotly.react(el, traces, { ...layout, barmode: 'overlay' }, opts);
}

function _plotHeatmap(el, data, layout, opts) {
    if (!data || !data.columns) return;
    Plotly.react(el, [{
        type: 'heatmap', z: data.matrix, x: data.columns, y: data.columns,
        colorscale: [[0,'#1e3a5f'],[0.5,'#4F9FFF'],[1,'#00D4FF']],
        text: (data.matrix || []).map(row => row.map(v => (v || 0).toFixed(2))),
        texttemplate: '%{text}', showscale: false,
    }], layout, opts);
}

function _plotScatter(el, data, layout, opts) {
    if (!Array.isArray(data) || data.length === 0) return;
    const d = data[0];
    Plotly.react(el, [{
        type: 'scatter', mode: 'markers',
        x: d.x, y: d.y, name: `${d.x_col} vs ${d.y_col}`,
        marker: { color: 'rgba(79,159,255,0.6)', size: 5 },
    }], { ...layout, xaxis: { ...layout.xaxis, title: d.x_col }, yaxis: { ...layout.yaxis, title: d.y_col } }, opts);
}

function _plotBar(el, data, layout, opts) {
    if (!data || !data.labels) return;
    Plotly.react(el, [{
        type: 'bar', x: data.labels, y: data.counts,
        marker: { color: 'rgba(0,212,255,0.75)' },
    }], layout, opts);
}

function _plotBarGrouped(el, data, layout, opts) {
    if (!Array.isArray(data) || data.length === 0) return;
    const steps   = data.map(d => d.step);
    const removed = data.map(d => d.removed || 0);
    Plotly.react(el, [{
        type: 'bar', x: steps, y: removed,
        marker: { color: removed.map(v => v > 0 ? 'rgba(255,120,80,0.8)' : 'rgba(0,212,100,0.8)') },
        text: removed.map(v => v > 0 ? `${v} 行` : '无变化'),
        textposition: 'auto',
    }], layout, opts);
}

function _plotBox(el, data, layout, opts) {
    if (!Array.isArray(data) || data.length === 0) return;
    const traces = data.map(d => ({
        type: 'box', name: d.col,
        q1: [d.q1], median: [d.median], q3: [d.q3],
        lowerfence: [d.lower], upperfence: [d.upper],
        mean: [d.median],
        fillcolor: 'rgba(79,159,255,0.3)',
        line: { color: 'var(--blue)' },
    }));
    Plotly.react(el, traces, layout, opts);
}

function _plotLine(el, data, layout, opts) {
    if (!data) return;
    // 使用原有 sales_trend 数据格式
    if (data.data && data.layout) {
        Plotly.react(el, data.data, { ...layout, ...(data.layout || {}) }, opts);
    }
}

// 零售模式：复用原有6个图表渲染
function _renderRetailDashboard() {
    // 恢复原有 6 个静态 chart-card HTML，然后调用原渲染逻辑
    var grid = document.getElementById('adaptive-charts-grid');
    if (!grid) return;
    grid.innerHTML = `
        <div class="col-12 col-xl-6"><div class="card chart-card"><div class="card-header"><i class="bi bi-graph-up-arrow me-2" style="color:var(--blue)"></i>月度销售趋势</div><div class="card-body p-1"><div id="chart-sales-trend" style="height:290px"></div></div></div></div>
        <div class="col-12 col-xl-6"><div class="card chart-card"><div class="card-header"><i class="bi bi-trophy me-2" style="color:var(--amber)"></i>Top 10 畅销商品</div><div class="card-body p-1"><div id="chart-top-products" style="height:290px"></div></div></div></div>
        <div class="col-12 col-xl-6"><div class="card chart-card"><div class="card-header"><i class="bi bi-globe me-2" style="color:var(--cyan)"></i>国家销售分布</div><div class="card-body p-1"><div id="chart-country" style="height:290px"></div></div></div></div>
        <div class="col-12 col-xl-6"><div class="card chart-card"><div class="card-header"><i class="bi bi-grid-3x3 me-2" style="color:var(--purple)"></i>相关性矩阵</div><div class="card-body p-1"><div id="chart-correlation" style="height:290px"></div></div></div></div>
        <div class="col-12 col-xl-6"><div class="card chart-card"><div class="card-header"><i class="bi bi-clock me-2" style="color:var(--green)"></i>订单时间规律</div><div class="card-body p-1"><div id="chart-time-pattern" style="height:290px"></div></div></div></div>
        <div class="col-12 col-xl-6"><div class="card chart-card"><div class="card-header"><i class="bi bi-people me-2" style="color:var(--red)"></i>RFM 客户分布</div><div class="card-body p-1"><div id="chart-rfm" style="height:290px"></div></div></div></div>
    `;
    // 触发原有渲染（原 charts.js 中已存在的零售图表函数）
    if (typeof _initRetailCharts === 'function') _initRetailCharts();
    else _loadAllRetailCharts();  // 原有逻辑入口
}
```

- [ ] **步骤 3：浏览器验证**

上传 `winequality-red.csv`：
- [ ] 页面顶部显示"🔬 科学数值型"徽章
- [ ] 6 个图表均有内容（直方图、相关矩阵、箱线图、散点图、quality 分布、清洗对比）

上传 Online Retail CSV：
- [ ] 页面顶部显示"🛒 零售交易型"徽章
- [ ] 原有 6 张零售图表正常显示

- [ ] **步骤 4：Commit**

```bash
git add templates/visualization.html static/js/charts.js
git commit -m "feat: 可视化仪表盘自适应改造，按数据画像渲染 6 类图表"
```

---

## 任务 9：动态快捷提问按钮

**文件：**
- 修改：`templates/analysis.html`

- [ ] **步骤 1：替换硬编码快捷提问按钮**

找到 `templates/analysis.html` 中的快捷提问区域，将整个 `div#quick-questions` 替换为：

```html
<div id="quick-questions" class="d-flex flex-wrap gap-2 mb-3">
    <span class="quick-q-label">快捷提问：</span>
    <!-- 由 loadSuggestedQuestions() 动态注入 -->
    <button class="quick-q-btn" onclick="quickAsk('这份数据有哪些主要特征？')">数据特征</button>
    <button class="quick-q-btn" onclick="quickAsk('哪些列有异常值？')">异常值</button>
    <button class="quick-q-btn" onclick="quickAsk('数值列的分布情况如何？')">分布情况</button>
    <button class="quick-q-btn" onclick="quickAsk('列之间的相关性如何？')">相关性</button>
</div>
```

- [ ] **步骤 2：在 analysis.html script 块末尾添加动态加载函数**

```javascript
// 页面加载时动态替换快捷提问按钮
async function loadSuggestedQuestions() {
    try {
        const r = await fetch('/api/analysis/suggested_questions');
        if (!r.ok) return;
        const qs = await r.json();
        if (!Array.isArray(qs) || qs.length === 0) return;

        var container = document.getElementById('quick-questions');
        if (!container) return;

        var label = container.querySelector('.quick-q-label');
        container.innerHTML = '';
        if (label) container.appendChild(label);

        qs.forEach(function(q) {
            var btn = document.createElement('button');
            btn.className = 'quick-q-btn';
            btn.textContent = q.length > 12 ? q.slice(0, 12) + '…' : q;
            btn.title = q;
            btn.onclick = function() { quickAsk(q); };
            container.appendChild(btn);
        });
    } catch(e) { /* 保留默认按钮 */ }
}

// 在现有初始化调用末尾追加
document.addEventListener('DOMContentLoaded', function() {
    loadSuggestedQuestions();
});
```

- [ ] **步骤 3：验证**

上传 `winequality-red.csv`，智能问答页的快捷按钮应显示：
"哪些特征与 quality 相关性最高？"、"fixed acidity 列的分布情况如何？" 等基于真实列名的问题。

- [ ] **步骤 4：Commit**

```bash
git add templates/analysis.html
git commit -m "feat: 快捷提问按钮根据数据画像动态生成"
```

---

## 任务 10：InsightEngine 通用洞察扩展

**文件：**
- 修改：`ai/insight.py`

- [ ] **步骤 1：在 InsightEngine 类末尾添加 3 个通用洞察方法**

在 `ai/insight.py` 中找到 `generate` 方法，在其中增加对新方法的调用：

```python
# 在 generate() 中已有的 insights.extend(...) 后面追加：
insights.extend(self._numeric_skew_insights())
insights.extend(self._category_concentration_insights())
if self._df_summary.get("target_col"):
    insights.extend(self._target_correlation_insights(self._df_summary["target_col"]))
```

然后在类末尾添加这 3 个方法：

```python
    def _numeric_skew_insights(self) -> list[dict]:
        """检测偏态系数 > 1.5 的数值列，生成分布偏态洞察。"""
        from scipy import stats as _stats  # 按需导入
        results = []
        try:
            num_cols = self._df.select_dtypes(include="number").columns
            for col in num_cols:
                series = self._df[col].dropna()
                if len(series) < 10:
                    continue
                skewness = float(_stats.skew(series))
                if abs(skewness) > 1.5:
                    direction = "右偏（正偏）" if skewness > 0 else "左偏（负偏）"
                    results.append({
                        "type":     "distribution",
                        "severity": "medium",
                        "title":    f"{col} 分布严重偏态",
                        "detail":   f"列 {col} 的偏态系数为 {skewness:.2f}（{direction}），"
                                    f"均值 {series.mean():.2f} 远离中位数 {series.median():.2f}。",
                    })
        except ImportError:
            pass  # scipy 未安装时跳过
        except Exception:
            pass
        return results[:2]  # 最多返回 2 条

    def _category_concentration_insights(self) -> list[dict]:
        """检测类别列中最高频率类别占比 > 60% 的情况。"""
        results = []
        cat_cols = [c for c in self._df.select_dtypes(include=["object", "category"]).columns
                    if self._df[c].nunique() <= 50]
        for col in cat_cols:
            vc  = self._df[col].value_counts(normalize=True)
            top = float(vc.iloc[0]) if len(vc) > 0 else 0
            if top > 0.6:
                results.append({
                    "type":     "category",
                    "severity": "medium",
                    "title":    f"{col} 分布高度集中",
                    "detail":   f"列 {col} 中 \"{vc.index[0]}\" 占比 {top*100:.1f}%，"
                                f"数据分布存在明显不均衡。",
                })
        return results[:2]

    def _target_correlation_insights(self, target_col: str) -> list[dict]:
        """找出与目标列相关性 > 0.3 的特征，生成预测特征洞察。"""
        results = []
        try:
            num_cols = [c for c in self._df.select_dtypes(include="number").columns
                        if c != target_col]
            if not num_cols or target_col not in self._df.columns:
                return []
            corr = self._df[num_cols + [target_col]].corr()[target_col].drop(target_col)
            strong = corr[corr.abs() > 0.3].sort_values(key=abs, ascending=False)
            if len(strong) > 0:
                top_features = ", ".join(
                    f"{col}({val:.2f})" for col, val in strong.head(3).items()
                )
                results.append({
                    "type":     "correlation",
                    "severity": "high",
                    "title":    f"发现 {target_col} 的强相关预测特征",
                    "detail":   f"与目标列 {target_col} 相关系数 > 0.3 的特征：{top_features}。"
                                f"这些特征可能对预测 {target_col} 有较强参考价值。",
                })
        except Exception:
            pass
        return results
```

- [ ] **步骤 2：确认 generate() 中的调用位置正确**

确保 `_df_summary` 中有 `target_col`（任务 4 中已添加到 `df_summary`）。

- [ ] **步骤 3：验证（上传葡萄酒数据集）**

数据概览右侧洞察面板应出现：
- "发现 quality 的强相关预测特征（alcohol: 0.48）"
- 某些列的偏态洞察

- [ ] **步骤 4：Commit**

```bash
git add ai/insight.py
git commit -m "feat: InsightEngine 新增3类通用洞察（偏态/集中度/目标相关性）"
```

---

## 任务 11：全量测试 + 验证

- [ ] **步骤 1：运行全量测试套件**

```bash
python -m pytest tests/ -x --tb=short -q
```

预期：全部 PASS（或仅原有已知失败测试）。

- [ ] **步骤 2：用 4 类数据集端到端验证**

```
测试集 1（numeric）：  winequality-red.csv（12数值列，分号分隔）
测试集 2（retail）：   Online Retail.csv（原测试集，逗号分隔）
测试集 3（categorical）：任意调查问卷 CSV（≥3 类别列）
测试集 4（temporal）：  任意有日期列的时间序列 CSV
```

对每个数据集验证：
- [ ] 上传成功，字段数正确（非"1"）
- [ ] 数据自描述卡片显示正确画像
- [ ] 可视化仪表盘 6 张图均有内容
- [ ] 快捷提问按钮与数据集内容匹配
- [ ] 智能问答可正确使用列名
- [ ] NL2Vis 工作台生成图表后同步到对话区

- [ ] **步骤 3：最终 Commit**

```bash
git add .
git commit -m "feat: DataMind 全数据集通用化完成 + 图表双向同步修复"
```
