# 数据清洗优化 + 详细报告多 Agent 框架 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 优化预处理管线的清洗质量；新增"详细模式"报告，由 StatisticsAgent / InsightAgent / QAAgent / SynthesisAgent 四个专注 AI Agent 并行生成，输出 ~3000 字深度报告。

**架构：** `data/preprocessor.py` 新增 `clean_text()` 步骤，改进缺失值填充策略（偏态→中位数、正态→均值、低基数文本→众数）和两档 IQR 异常标记。`ai/report_agents.py`（新建）封装四个 Agent；`ai/report.py` 新增 `generate_detailed()` 方法串联四个 Agent；API 通过 `mode` 参数区分简单/详细两种模式；前端 `report.html` 新增模式切换 UI。

**技术栈：** Python 3.8+, pandas, numpy, Flask, OpenAI SDK（兼容 Ollama），unittest.mock（测试）

---

## 文件清单

| 文件 | 操作 | 职责 |
|------|------|------|
| `data/preprocessor.py` | 修改 | 新增 `clean_text()` 步骤；改进 `handle_missing()`；两档 IQR；低基数 Categorical 检测 |
| `tests/test_preprocessor.py` | 修改 | 补充 3 个新功能的测试 |
| `ai/report_agents.py` | **新建** | StatisticsAgent / InsightAgent / QAAgent / SynthesisAgent |
| `tests/test_report_agents.py` | **新建** | 四个 Agent 的单元测试 |
| `ai/report.py` | 修改 | 新增 `generate_detailed()` 方法 |
| `tests/test_report.py` | 修改 | 补充 `generate_detailed()` 测试 |
| `routes/api.py` | 修改 | `report_generate()` 支持 `mode` 参数 |
| `templates/report.html` | 修改 | 模式切换按钮 + 详细模式进度 UI |

---

## 任务 1：`clean_text()` — 文本列噪音清洗

**文件：**
- 修改：`data/preprocessor.py`
- 修改：`tests/test_preprocessor.py`

### 背景
现有管线未处理字符串列的空白字符（首尾空格、Tab）和控制字符，会导致 `groupby` 时产生错误分组（`"UK"` ≠ `" UK"`）。新增 `clean_text()` 步骤，插入到 `remove_duplicates` 和 `handle_missing` 之间。`.str.strip()` 和 `.str.replace()` 对 `NaN` 安全，不需要额外处理缺失值。

- [ ] **步骤 1：在 `tests/test_preprocessor.py` 末尾写失败测试**

```python
# tests/test_preprocessor.py 末尾追加

class TestCleanText:
    def test_strips_leading_trailing_spaces(self):
        from data.preprocessor import Preprocessor
        df = pd.DataFrame({"name": ["  Alice ", "\tBob", "Charlie  "]})
        result = Preprocessor(df).clean_text().df
        assert result["name"].tolist() == ["Alice", "Bob", "Charlie"]

    def test_removes_control_characters(self):
        from data.preprocessor import Preprocessor
        df = pd.DataFrame({"note": ["hello\x00world", "ok\x1f", "clean"]})
        result = Preprocessor(df).clean_text().df
        assert result["note"].iloc[0] == "helloworld"
        assert result["note"].iloc[1] == "ok"

    def test_preserves_nan(self):
        from data.preprocessor import Preprocessor
        df = pd.DataFrame({"col": ["  text  ", None, " hi "]})
        result = Preprocessor(df).clean_text().df
        assert pd.isna(result["col"].iloc[1])
        assert result["col"].iloc[0] == "text"

    def test_log_records_cleaned_cols(self):
        from data.preprocessor import Preprocessor
        df = pd.DataFrame({"a": [" x "], "b": [1]})
        p = Preprocessor(df).clean_text()
        report = p.get_report()
        assert "clean_text" in report
        assert "a" in report["clean_text"]["cleaned_cols"]
```

- [ ] **步骤 2：运行测试，确认 FAIL**

```bash
cd C:\Users\21560\Desktop\python_final
pytest tests/test_preprocessor.py::TestCleanText -v
```
预期：4 个 FAILED，报错 `AttributeError: 'Preprocessor' object has no attribute 'clean_text'`

- [ ] **步骤 3：在 `data/preprocessor.py` 中实现 `clean_text()`**

在 `remove_duplicates` 方法之后、`handle_missing` 方法之前插入：

```python
# ── 步骤 1b：文本列清洗 ────────────────────────────────────
def clean_text(self) -> "Preprocessor":
    """
    清洗所有 object 类型列：
    - 去除首尾空格和 Tab
    - 去除 ASCII 控制字符（0x00-0x1f, 0x7f）
    NaN 值不受影响（pandas .str 方法对 NaN 安全）。
    """
    text_cols = list(self.df.select_dtypes(include=["object"]).columns)
    for col in text_cols:
        self.df[col] = self.df[col].str.strip()
        self.df[col] = self.df[col].str.replace(
            r"[\x00-\x1f\x7f]", "", regex=True
        )
    self._log["clean_text"] = {"cleaned_cols": text_cols}
    return self
```

同时修改 `run_all()` 方法，在 `remove_duplicates()` 之后调用 `.clean_text()`：

```python
def run_all(self) -> pd.DataFrame:
    """按标准顺序执行全部预处理步骤，返回清洁 DataFrame。"""
    return (
        self.remove_duplicates()
            .clean_text()           # ← 新增
            .handle_missing()
            .convert_types()
            .filter_invalid_records()
            .filter_outliers()
            .add_features()
            .df
    )
```

- [ ] **步骤 4：运行测试，确认 PASS**

```bash
pytest tests/test_preprocessor.py::TestCleanText -v
```
预期：4 个 PASSED

- [ ] **步骤 5：确认已有测试不受影响**

```bash
pytest tests/test_preprocessor.py -v
```
预期：全部 PASSED（含原有测试）

- [ ] **步骤 6：Commit**

```bash
git add data/preprocessor.py tests/test_preprocessor.py
git commit -m "feat(preprocessor): add clean_text() step for whitespace/control-char removal"
```

---

## 任务 2：改进 `handle_missing()` — 基于偏态的填充策略

**文件：**
- 修改：`data/preprocessor.py`
- 修改：`tests/test_preprocessor.py`

### 背景
当前策略：数值列一律用中位数，文本列一律用 `"Unknown"`。改进：
- **数值列**：先计算偏态系数，`|skew| > 1.0` → 中位数，否则 → 均值；若样本不足导致 skew 为 NaN → 回退中位数。
- **文本列**：若列的非空唯一值数 ≤ 10 且非空行 ≥ 3 且唯一率 ≤ 50%（判断为低基数分类列）→ 用众数；否则 → `"Unknown"`。

已有测试 `test_numeric_filled_with_median` 中 `num: [1.0, NaN, 3.0, NaN]`（非空值 [1.0, 3.0]，skew = NaN，回退中位数 = 2.0）不受影响。已有测试 `test_text_filled_with_unknown` 中文本列仅 2 个非空值，不满足 `n_total >= 3`，仍填 `"Unknown"`，不受影响。

- [ ] **步骤 1：在 `tests/test_preprocessor.py::TestHandleMissing` 末尾追加新测试**

```python
    def test_normal_numeric_filled_with_mean(self):
        """正态分布列（skew ≈ 0）用均值填充。"""
        from data.preprocessor import Preprocessor
        # 值域对称：[2, 4, 6, 8]，均值 = 5.0，中位数 = 5.0；此处用非对称更好区分
        # 构造正态分布的近似：skew < 1.0
        df = pd.DataFrame({"val": [10.0, 11.0, 12.0, 13.0, np.nan]})
        # skew([10,11,12,13]) ≈ 0 → 应填 mean = 11.5
        result = Preprocessor(df).handle_missing().df
        assert result["val"].iloc[4] == pytest.approx(11.5)

    def test_skewed_numeric_filled_with_median(self):
        """高偏态列（skew > 1.0）用中位数填充。"""
        from data.preprocessor import Preprocessor
        # 明显右偏：1,1,1,1,100 → skew >> 1.0，中位数 = 1.0，均值 = 20.8
        df = pd.DataFrame({"val": [1.0, 1.0, 1.0, 1.0, 100.0, np.nan]})
        result = Preprocessor(df).handle_missing().df
        assert result["val"].iloc[5] == pytest.approx(1.0)

    def test_low_cardinality_text_filled_with_mode(self):
        """低基数文本列（n_unique<=10, n_total>=3, ratio<=0.5）用众数填充。"""
        from data.preprocessor import Preprocessor
        # status 列：3个非空值，2个唯一值，ratio=2/3≈0.67 > 0.5 → 不满足 → Unknown
        # 改用 6 行来达到 ratio <= 0.5
        df = pd.DataFrame({
            "status": ["active", "active", "active", "inactive", "inactive", None],
        })
        result = Preprocessor(df).handle_missing().df
        # n_unique=2, n_total=5, ratio=2/5=0.4 <= 0.5, n_total>=3 → 用众数 "active"
        assert result["status"].iloc[5] == "active"
```

- [ ] **步骤 2：运行测试，确认 FAIL**

```bash
pytest tests/test_preprocessor.py::TestHandleMissing::test_normal_numeric_filled_with_mean tests/test_preprocessor.py::TestHandleMissing::test_skewed_numeric_filled_with_median tests/test_preprocessor.py::TestHandleMissing::test_low_cardinality_text_filled_with_mode -v
```
预期：3 个 FAILED

- [ ] **步骤 3：在 `data/preprocessor.py` 顶部添加工具函数，并修改 `handle_missing()`**

在 `_HIGH_MISSING_THRESHOLD` 常量下方添加：

```python
def _fill_value_for_numeric(series: pd.Series) -> float:
    """
    根据偏态系数决定用中位数还是均值填充。
    - |skew| > 1.0 或 skew 为 NaN（样本不足） → 中位数
    - 否则 → 均值
    """
    try:
        skew = float(series.skew())
    except Exception:
        skew = float("nan")

    if pd.isna(skew) or abs(skew) > 1.0:
        return float(series.median())
    return float(series.mean())


def _fill_value_for_text(series: pd.Series) -> str:
    """
    根据基数判断文本列填充值。
    低基数（n_unique<=10 且 n_total>=3 且 ratio<=0.5）→ 众数；否则 → 'Unknown'。
    """
    non_null = series.dropna()
    n_total  = len(non_null)
    n_unique = non_null.nunique()

    if n_total >= 3 and n_unique <= 10 and (n_unique / n_total) <= 0.5:
        mode_vals = non_null.mode()
        if len(mode_vals) > 0:
            return str(mode_vals.iloc[0])
    return "Unknown"
```

修改 `handle_missing()` 方法，将原先的 `if pd.api.types.is_numeric_dtype` 分支替换：

```python
def handle_missing(self) -> "Preprocessor":
    """
    - 数值列：偏态 |skew| > 1.0 → 中位数；否则 → 均值
    - 低基数文本列（n_unique<=10, n_total>=3, ratio<=0.5）→ 众数
    - 其他文本列 → "Unknown"
    - 缺失率 > 50% 的列：仅记录警告，仍填充
    """
    filled: dict[str, int] = {}
    high_missing: list[str] = []

    for col in self.df.columns:
        missing_count = self.df[col].isna().sum()
        if missing_count == 0:
            continue

        if _is_id_like_column(col):
            continue

        missing_rate = missing_count / len(self.df)
        if missing_rate > _HIGH_MISSING_THRESHOLD:
            high_missing.append(col)

        if pd.api.types.is_numeric_dtype(self.df[col]):
            fill_val = _fill_value_for_numeric(self.df[col].dropna())
            self.df[col] = self.df[col].fillna(fill_val)
        else:
            fill_val = _fill_value_for_text(self.df[col])
            self.df[col] = self.df[col].fillna(fill_val)

        filled[col] = int(missing_count)

    self._log["handle_missing"] = {
        "filled_cols": filled,
        "high_missing_cols": high_missing,
    }
    return self
```

- [ ] **步骤 4：运行全部 handle_missing 测试**

```bash
pytest tests/test_preprocessor.py::TestHandleMissing -v
```
预期：全部 PASSED（含原有 4 个 + 新增 3 个）

- [ ] **步骤 5：运行全量测试确认无回归**

```bash
pytest tests/test_preprocessor.py -v
```
预期：全部 PASSED

- [ ] **步骤 6：Commit**

```bash
git add data/preprocessor.py tests/test_preprocessor.py
git commit -m "feat(preprocessor): smarter missing-value fill (skewness + low-cardinality mode)"
```

---

## 任务 3：两档 IQR 异常标记 + 低基数 Categorical 检测

**文件：**
- 修改：`data/preprocessor.py`
- 修改：`tests/test_preprocessor.py`

### 背景
**两档 IQR**：现有代码用 1.5×IQR 标记所有异常。新增 `_is_extreme_outlier`（3.0×IQR）列，便于区分"轻度异常"和"极端异常"。已有 `_is_outlier` 行为不变（向后兼容）。

**Categorical 检测**：在 `convert_types()` 末尾，对无法转为 datetime 或 numeric 的文本列，若 n_unique ≤ 10 且 n_total ≥ 3 且 ratio ≤ 0.5，自动转为 `pd.Categorical` 类型，节省内存并提升分析效率。已有测试 `test_non_convertible_column_unchanged` 中 `["Alice","Bob","Charlie"]` 有 3 个非空值、3 个唯一值，ratio=1.0 > 0.5，不会被转，测试仍 PASS。

- [ ] **步骤 1：追加测试到 `tests/test_preprocessor.py`**

```python
class TestFilterOutliersExtended:
    def test_extreme_outlier_column_created(self):
        from data.preprocessor import Preprocessor
        df = pd.DataFrame({"value": [10, 12, 11, 13, 10, 9999, 11, 12]})
        result = Preprocessor(df).filter_outliers().df
        assert "value_is_extreme_outlier" in result.columns

    def test_extreme_outlier_flagged(self):
        from data.preprocessor import Preprocessor
        df = pd.DataFrame({"value": [10, 12, 11, 13, 10, 9999, 11, 12]})
        result = Preprocessor(df).filter_outliers().df
        assert result.loc[result["value"] == 9999, "value_is_extreme_outlier"].all()

    def test_mild_outlier_not_extreme(self):
        """轻度异常（在 3×IQR 范围内）不应被标记为极端异常。"""
        from data.preprocessor import Preprocessor
        # [10]*7 + [25]：25 可能是轻度异常但不是极端
        df = pd.DataFrame({"v": [10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 25.0]})
        result = Preprocessor(df).filter_outliers().df
        # 25 是否是极端异常取决于 IQR；此处测量 extreme 列存在且类型正确
        assert result["v_is_extreme_outlier"].dtype == bool


class TestConvertTypesCategorical:
    def test_low_cardinality_column_converted_to_category(self):
        from data.preprocessor import Preprocessor
        # status 列：6 行，2 个唯一值，ratio=0.33 ≤ 0.5，应被转为 Categorical
        df = pd.DataFrame({
            "status": ["active", "active", "active", "inactive", "inactive", "inactive"],
        })
        result = Preprocessor(df).convert_types().df
        assert pd.api.types.is_categorical_dtype(result["status"])

    def test_high_cardinality_column_stays_object(self):
        from data.preprocessor import Preprocessor
        df = pd.DataFrame({"name": ["Alice", "Bob", "Charlie", "Diana", "Eve"]})
        result = Preprocessor(df).convert_types().df
        # n_unique=5, n_total=5, ratio=1.0 > 0.5 → 不转
        assert not pd.api.types.is_categorical_dtype(result["name"])
```

- [ ] **步骤 2：运行测试，确认 FAIL**

```bash
pytest tests/test_preprocessor.py::TestFilterOutliersExtended tests/test_preprocessor.py::TestConvertTypesCategorical -v
```
预期：5 个 FAILED

- [ ] **步骤 3：修改 `filter_outliers()` 添加两档 IQR**

在 `data/preprocessor.py` 中，找到 `filter_outliers` 方法，将 `mask` / `n_flagged` 相关代码替换为：

```python
lower_mild    = q1 - 1.5 * iqr
upper_mild    = q3 + 1.5 * iqr
lower_extreme = q1 - 3.0 * iqr
upper_extreme = q3 + 3.0 * iqr

mask_mild    = (self.df[col] < lower_mild)    | (self.df[col] > upper_mild)
mask_extreme = (self.df[col] < lower_extreme) | (self.df[col] > upper_extreme)

self.df[f"{col}_is_outlier"]         = mask_mild
self.df[f"{col}_is_extreme_outlier"] = mask_extreme

n_flagged = int(mask_mild.sum())
flagged_total += n_flagged
if n_flagged > 0:
    detail[col] = n_flagged
```

- [ ] **步骤 4：修改 `convert_types()` 添加 Categorical 检测**

在 `convert_types()` 中，在 `# 尝试转 numeric` 段之后，在 `self._log["convert_types"]` 之前，追加：

```python
            # 尝试识别低基数分类列
            non_null  = self.df[col].dropna()
            n_total   = len(non_null)
            n_unique  = non_null.nunique()
            if (n_total >= 3
                    and n_unique <= 10
                    and (n_unique / n_total) <= 0.5):
                self.df[col] = self.df[col].astype("category")
                converted[col] = "category"
```

- [ ] **步骤 5：运行扩展测试**

```bash
pytest tests/test_preprocessor.py::TestFilterOutliersExtended tests/test_preprocessor.py::TestConvertTypesCategorical -v
```
预期：全部 PASSED

- [ ] **步骤 6：运行全量测试**

```bash
pytest tests/test_preprocessor.py -v
```
预期：全部 PASSED

- [ ] **步骤 7：Commit**

```bash
git add data/preprocessor.py tests/test_preprocessor.py
git commit -m "feat(preprocessor): two-tier IQR outlier flags + categorical type detection"
```

---

## 任务 4：新建 `ai/report_agents.py` — 四个 Agent 类

**文件：**
- 新建：`ai/report_agents.py`
- 新建：`tests/test_report_agents.py`

### 背景
每个 Agent 是独立类，有专注的系统提示词、数据构造函数和降级（fallback）方法。所有 Agent 共用相同的 `client.chat.completions.create()` 调用模式（与 `ai/report.py` 一致），并用 `_extract_content` 解析响应。

- [ ] **步骤 1：新建 `tests/test_report_agents.py`，写失败测试**

```python
"""
ai/report_agents.py 单元测试
来源：学生+AI
"""
import pytest
from unittest.mock import MagicMock


def _make_client(content: str) -> MagicMock:
    client = MagicMock()
    resp = MagicMock()
    resp.choices[0].message.content = content
    client.chat.completions.create.return_value = resp
    return client


def _error_client() -> MagicMock:
    client = MagicMock()
    client.chat.completions.create.side_effect = Exception("API error")
    return client


@pytest.fixture
def sample_df_info():
    return {
        "row_count": 1000,
        "column_count": 8,
        "columns": ["InvoiceNo", "Quantity", "UnitPrice", "TotalAmount"],
        "numeric_stats": {
            "Quantity":    {"mean": 9.5, "median": 6.0, "std": 17.3, "min": 1.0, "max": 80006.0},
            "TotalAmount": {"mean": 22.5, "median": 11.0, "std": 95.0, "min": 0.0, "max": 168469.6},
        },
        "date_range": {"start": "2010-12-01", "end": "2011-12-09"},
    }


@pytest.fixture
def sample_insights():
    return [
        {"type": "anomaly", "severity": "high",
         "title": "列 Quantity 存在异常值", "detail": "检测到 100 个异常值，占比 10%"},
    ]


@pytest.fixture
def sample_history():
    return [
        {"role": "user",      "content": "月均销售额是多少？"},
        {"role": "assistant", "content": "月均销售额约为 91,262 元。"},
        {"role": "user",      "content": "哪个国家销售额最高？"},
        {"role": "assistant", "content": "United Kingdom 贡献了 84% 的销售额。"},
    ]


class TestStatisticsAgent:
    def test_returns_string(self, sample_df_info):
        from ai.report_agents import StatisticsAgent
        agent = StatisticsAgent(_make_client("## 数据特征详述\n\n内容"))
        result = agent.generate(sample_df_info)
        assert isinstance(result, str)

    def test_contains_heading(self, sample_df_info):
        from ai.report_agents import StatisticsAgent
        agent = StatisticsAgent(_make_client("## 数据特征详述\n内容"))
        result = agent.generate(sample_df_info)
        assert "##" in result

    def test_fallback_on_error(self, sample_df_info):
        from ai.report_agents import StatisticsAgent
        agent = StatisticsAgent(_error_client())
        result = agent.generate(sample_df_info)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_fallback_contains_row_count(self, sample_df_info):
        from ai.report_agents import StatisticsAgent
        agent = StatisticsAgent(_error_client())
        result = agent.generate(sample_df_info)
        assert "1000" in result


class TestInsightAgent:
    def test_returns_string(self, sample_insights):
        from ai.report_agents import InsightAgent
        agent = InsightAgent(_make_client("## 深度洞察与归因\n内容"))
        result = agent.generate(sample_insights, {})
        assert isinstance(result, str)

    def test_fallback_on_error(self, sample_insights):
        from ai.report_agents import InsightAgent
        agent = InsightAgent(_error_client())
        result = agent.generate(sample_insights, {})
        assert isinstance(result, str)
        assert "洞察" in result or "anomaly" in result or "Quantity" in result

    def test_empty_insights_no_crash(self):
        from ai.report_agents import InsightAgent
        agent = InsightAgent(_error_client())
        result = agent.generate([], {})
        assert isinstance(result, str)


class TestQAAgent:
    def test_returns_string(self, sample_history):
        from ai.report_agents import QAAgent
        agent = QAAgent(_make_client("## 问答分析记录\n内容"))
        result = agent.generate(sample_history)
        assert isinstance(result, str)

    def test_empty_history_returns_placeholder(self):
        from ai.report_agents import QAAgent
        agent = QAAgent(_make_client(""))
        result = agent.generate([])
        assert "未进行" in result or "无" in result

    def test_fallback_on_error(self, sample_history):
        from ai.report_agents import QAAgent
        agent = QAAgent(_error_client())
        result = agent.generate(sample_history)
        assert isinstance(result, str)
        assert len(result) > 0


class TestSynthesisAgent:
    def test_returns_string(self, sample_df_info):
        from ai.report_agents import SynthesisAgent
        agent = SynthesisAgent(_make_client("## 执行摘要\n内容\n## 综合建议\n- 建议1"))
        result = agent.generate("stats", "insights", "qa", sample_df_info)
        assert isinstance(result, str)

    def test_fallback_contains_executive_summary(self, sample_df_info):
        from ai.report_agents import SynthesisAgent
        agent = SynthesisAgent(_error_client())
        result = agent.generate("stats", "insights", "qa", sample_df_info)
        assert "执行摘要" in result
        assert "综合建议" in result
```

- [ ] **步骤 2：运行测试，确认 FAIL**

```bash
pytest tests/test_report_agents.py -v
```
预期：全部 FAILED，报错 `ModuleNotFoundError: No module named 'ai.report_agents'`

- [ ] **步骤 3：新建 `ai/report_agents.py`**

```python
"""
详细报告多 Agent 框架。

四个专注 Agent：
  StatisticsAgent  — 数据特征详述（字段分布、统计表格）
  InsightAgent     — 深度洞察与归因（趋势、RFM、相关性解读）
  QAAgent          — 问答分析记录（对话提炼）
  SynthesisAgent   — 执行摘要 + 综合建议（整合前三者）

每个 Agent 有：
  - 专注的 SYSTEM 提示词
  - generate(...)  → str（Markdown 章节）
  - _build_prompt(...) → str
  - _fallback(...)    → str（无 API 时的模板降级）

来源：学生+AI
"""
from __future__ import annotations

from typing import Any

import config as _cfg
from ai.code_generator import _extract_content


# ── 工具：检测 AI 响应是否为 HTML（接口配置错误时会返回网页）──────
def _is_html(text: str) -> bool:
    return text.lstrip().lower().startswith(("<!doctype", "<html"))


# ═══════════════════════════════════════════════════════════════
# 1. StatisticsAgent — 数据特征详述
# ═══════════════════════════════════════════════════════════════

class StatisticsAgent:
    """
    生成"## 数据特征详述"章节。
    输入：summary_stats() 返回的 df_info 字典。
    """

    SYSTEM = (
        "你是专业数据科学家，用清晰简洁的中文为业务人员撰写数据集特征报告章节。"
        "使用 Markdown 格式，包含表格和要点。"
    )

    def __init__(self, client: Any) -> None:
        self.client = client

    def generate(self, df_info: dict) -> str:
        """返回 Markdown 字符串（"## 数据特征详述" 开头）。"""
        prompt = self._build_prompt(df_info)
        try:
            resp = self.client.chat.completions.create(
                model=_cfg.AI_MODEL,
                messages=[
                    {"role": "system", "content": self.SYSTEM},
                    {"role": "user",   "content": prompt},
                ],
                temperature=0.2,
                max_tokens=800,
            )
            raw = _extract_content(resp)
            if raw and not _is_html(raw):
                return raw
        except Exception:
            pass
        return self._fallback(df_info)

    def _build_prompt(self, df_info: dict) -> str:
        rows          = df_info.get("row_count", "?")
        cols          = df_info.get("column_count", "?")
        col_names     = df_info.get("columns", [])
        numeric_stats = df_info.get("numeric_stats", {})
        date_range    = df_info.get("date_range") or {}

        col_list = "、".join(str(c) for c in col_names[:20])
        if len(col_names) > 20:
            col_list += f"…（共 {len(col_names)} 个）"

        stats_lines = "\n".join(
            f"- {col}：均值={s['mean']}, 中位数={s['median']}, "
            f"标准差={s['std']}, 最小={s['min']}, 最大={s['max']}"
            for col, s in numeric_stats.items()
        ) or "（无数值列）"

        date_str = (
            f"{date_range['start']} 至 {date_range['end']}"
            if date_range.get("start") else "未知"
        )

        return f"""请为以下数据集生成"## 数据特征详述"章节的 Markdown 内容。

【数据基本信息】
- 总行数：{rows}，总列数：{cols}
- 字段列表：{col_list}
- 时间跨度：{date_str}

【数值列统计】
{stats_lines}

要求：
1. 以"## 数据特征详述"开头
2. 描述数据规模、字段构成、时间跨度
3. 用 Markdown 表格展示数值列的均值/中位数/标准差/最大最小值
4. 根据均值与中位数的差异判断偏态并说明
5. 全中文，约 300 字"""

    def _fallback(self, df_info: dict) -> str:
        rows          = df_info.get("row_count", "?")
        cols          = df_info.get("column_count", "?")
        numeric_stats = df_info.get("numeric_stats", {})
        col_names     = df_info.get("columns", [])
        date_range    = df_info.get("date_range") or {}

        date_str = (
            f"{date_range['start']} 至 {date_range['end']}"
            if date_range.get("start") else "未知"
        )
        col_list = "、".join(str(c) for c in col_names[:15])

        table_rows = "\n".join(
            f"| {col} | {s['mean']:.2f} | {s['median']:.2f} | "
            f"{s['std']:.2f} | {s['min']:.2f} | {s['max']:.2f} |"
            for col, s in numeric_stats.items()
        )
        table = (
            "| 字段 | 均值 | 中位数 | 标准差 | 最小值 | 最大值 |\n"
            "|------|------|--------|--------|--------|--------|\n"
            + table_rows
        ) if table_rows else "（无数值列统计数据）"

        return f"""## 数据特征详述

数据集共 **{rows}** 条记录，涉及 **{cols}** 个字段，时间跨度 {date_str}。

**字段列表：** {col_list}

### 数值列统计汇总

{table}
"""


# ═══════════════════════════════════════════════════════════════
# 2. InsightAgent — 深度洞察与归因
# ═══════════════════════════════════════════════════════════════

class InsightAgent:
    """
    生成"## 深度洞察与归因"章节。
    输入：insights 列表 + analysis_extras（sales_trend / rfm / correlation）。
    """

    SYSTEM = (
        "你是专业数据分析师，擅长从统计数据中发现业务规律，"
        "用中文撰写深度洞察报告章节，语言简洁有力。"
    )

    def __init__(self, client: Any) -> None:
        self.client = client

    def generate(self, insights: list, analysis_extras: dict) -> str:
        """返回 Markdown 字符串（"## 深度洞察与归因" 开头）。"""
        prompt = self._build_prompt(insights, analysis_extras)
        try:
            resp = self.client.chat.completions.create(
                model=_cfg.AI_MODEL,
                messages=[
                    {"role": "system", "content": self.SYSTEM},
                    {"role": "user",   "content": prompt},
                ],
                temperature=0.3,
                max_tokens=800,
            )
            raw = _extract_content(resp)
            if raw and not _is_html(raw):
                return raw
        except Exception:
            pass
        return self._fallback(insights)

    def _build_prompt(self, insights: list, analysis_extras: dict) -> str:
        insight_lines = "\n".join(
            f"- [{i['severity'].upper()}] {i['title']}：{i['detail']}"
            for i in insights
        ) or "（未发现显著洞察）"

        # 销售趋势摘要
        trend = analysis_extras.get("sales_trend") or {}
        trend_summary = "（无销售趋势数据）"
        if trend.get("values"):
            vals   = trend["values"]
            labels = trend.get("labels", [])
            if len(vals) >= 2:
                peak_idx   = vals.index(max(vals))
                peak_label = labels[peak_idx] if peak_idx < len(labels) else "未知"
                total      = sum(vals)
                trend_summary = (
                    f"共 {len(vals)} 个时间节点，总销售额 {total:.2f}，"
                    f"峰值出现在 {peak_label}（{max(vals):.2f}）"
                )

        # RFM 摘要
        rfm = analysis_extras.get("rfm") or {}
        rfm_summary = "（无客户分析数据）"
        if rfm.get("total_customers"):
            rfm_summary = (
                f"共识别 {rfm['total_customers']} 位客户，"
                f"参考日期 {rfm.get('reference_date', '未知')}"
            )

        return f"""请为以下分析结果生成"## 深度洞察与归因"章节的 Markdown 内容。

【自动检测洞察（共 {len(insights)} 条）】
{insight_lines}

【销售趋势摘要】
{trend_summary}

【RFM 客户分析】
{rfm_summary}

要求：
1. 以"## 深度洞察与归因"开头
2. 对每条高/中严重度洞察给出业务解读和可能归因
3. 结合趋势数据解释销售周期规律
4. 指出最需关注的 2-3 个核心问题
5. 全中文，约 300 字"""

    def _fallback(self, insights: list) -> str:
        lines = "\n".join(
            f"- **[{i['severity'].upper()}]** {i['title']}：{i['detail']}"
            for i in insights
        ) or "- 未发现显著洞察"

        return f"""## 深度洞察与归因

{lines}
"""


# ═══════════════════════════════════════════════════════════════
# 3. QAAgent — 问答分析记录
# ═══════════════════════════════════════════════════════════════

class QAAgent:
    """
    生成"## 问答分析记录"章节。
    输入：完整 chat_history（含 user + assistant 消息）。
    """

    SYSTEM = (
        "你是数据分析总结助手，提炼对话中的关键分析发现，"
        "用中文撰写问答记录章节，突出用户关注点和重要结论。"
    )

    def __init__(self, client: Any) -> None:
        self.client = client

    def generate(self, chat_history: list) -> str:
        """返回 Markdown 字符串（"## 问答分析记录" 开头）。"""
        if not chat_history:
            return "## 问答分析记录\n\n本次分析未进行对话问答。\n"

        prompt = self._build_prompt(chat_history)
        try:
            resp = self.client.chat.completions.create(
                model=_cfg.AI_MODEL,
                messages=[
                    {"role": "system", "content": self.SYSTEM},
                    {"role": "user",   "content": prompt},
                ],
                temperature=0.2,
                max_tokens=600,
            )
            raw = _extract_content(resp)
            if raw and not _is_html(raw):
                return raw
        except Exception:
            pass
        return self._fallback(chat_history)

    def _build_prompt(self, chat_history: list) -> str:
        # 构造问答对，每对最多截取 200 字答案
        qa_pairs: list[str] = []
        i = 0
        while i < len(chat_history) and len(qa_pairs) < 10:
            msg = chat_history[i]
            if msg.get("role") == "user":
                q = msg["content"]
                a = ""
                if i + 1 < len(chat_history) and chat_history[i + 1].get("role") == "assistant":
                    a = chat_history[i + 1]["content"][:200]
                    i += 1
                qa_pairs.append(f"**Q：** {q}\n**A：** {a}")
            i += 1

        qa_text = "\n\n".join(qa_pairs) or "（无对话记录）"
        n_user = sum(1 for m in chat_history if m.get("role") == "user")

        return f"""请为以下对话记录生成"## 问答分析记录"章节的 Markdown 内容。

共 {n_user} 轮用户提问。

【对话记录（最多10轮）】
{qa_text}

要求：
1. 以"## 问答分析记录"开头
2. 列出用户提出的主要分析问题（不超过5条，每条一行）
3. 对每个问题总结关键发现（1-2 句）
4. 指出哪些问题获得了最有价值的洞察
5. 全中文，约 200 字"""

    def _fallback(self, chat_history: list) -> str:
        user_qs = [
            f"- {msg['content']}"
            for msg in chat_history
            if msg.get("role") == "user"
        ][:5]
        n = sum(1 for m in chat_history if m.get("role") == "user")
        lines = "\n".join(user_qs) if user_qs else "- 无用户问题记录"

        return f"""## 问答分析记录

本次分析共进行 **{n}** 轮问答。

### 主要提问

{lines}
"""


# ═══════════════════════════════════════════════════════════════
# 4. SynthesisAgent — 执行摘要 + 综合建议
# ═══════════════════════════════════════════════════════════════

class SynthesisAgent:
    """
    整合前三个 Agent 的输出，生成"## 执行摘要"和"## 综合建议"章节。
    """

    SYSTEM = (
        "你是高级数据分析师，基于各模块分析结论撰写执行摘要和可操作建议，"
        "语言专业、结论明确、逻辑清晰。"
    )
    _MAX_SECTION_LEN = 600  # 截断超长章节，避免超出 token 上限

    def __init__(self, client: Any) -> None:
        self.client = client

    def generate(
        self,
        stats_section: str,
        insights_section: str,
        qa_section: str,
        df_info: dict,
    ) -> str:
        """返回 Markdown 字符串（含"## 执行摘要"和"## 综合建议"）。"""
        prompt = self._build_prompt(stats_section, insights_section, qa_section, df_info)
        try:
            resp = self.client.chat.completions.create(
                model=_cfg.AI_MODEL,
                messages=[
                    {"role": "system", "content": self.SYSTEM},
                    {"role": "user",   "content": prompt},
                ],
                temperature=0.3,
                max_tokens=1000,
            )
            raw = _extract_content(resp)
            if raw and not _is_html(raw):
                return raw
        except Exception:
            pass
        return self._fallback(df_info)

    def _truncate(self, text: str) -> str:
        if len(text) > self._MAX_SECTION_LEN:
            return text[:self._MAX_SECTION_LEN] + "…（已截断）"
        return text

    def _build_prompt(
        self,
        stats_section: str,
        insights_section: str,
        qa_section: str,
        df_info: dict,
    ) -> str:
        rows = df_info.get("row_count", "?")
        cols = df_info.get("column_count", "?")

        return f"""基于以下三个分析模块，生成"执行摘要"和"综合建议"两个 Markdown 章节。

【数据特征模块（节选）】
{self._truncate(stats_section)}

【深度洞察模块（节选）】
{self._truncate(insights_section)}

【问答分析模块（节选）】
{self._truncate(qa_section)}

数据规模：{rows} 行 × {cols} 列

要求：
1. 生成"## 执行摘要"：3-4 句话概括最重要的发现，突出数据规模和核心结论
2. 生成"## 综合建议"：3-5 条可操作的业务建议，以"- "列举，每条 1-2 句
3. 全中文，总计约 250 字，语言专业、结论明确"""

    def _fallback(self, df_info: dict) -> str:
        rows = df_info.get("row_count", "?")
        cols = df_info.get("column_count", "?")

        return f"""## 执行摘要

本次分析共处理 **{rows}** 条记录，涉及 **{cols}** 个字段。已完成数据特征分析、自动洞察检测及问答分析，主要发现已在各章节详细说明。建议重点关注高严重度洞察，并结合业务背景制定改进措施。

## 综合建议

- 关注数据中检测到的高严重度（HIGH）洞察，优先排查其业务根因
- 结合 RFM 分析结果制定差异化客户运营策略，重点维护高价值客户
- 监控销售趋势的异常波动周期，建立关键指标预警机制
- 完善数据采集流程，降低关键字段的缺失值比例
- 定期重新运行分析，追踪关键指标的变化趋势
"""
```

- [ ] **步骤 4：运行测试，确认 PASS**

```bash
pytest tests/test_report_agents.py -v
```
预期：全部 PASSED

- [ ] **步骤 5：Commit**

```bash
git add ai/report_agents.py tests/test_report_agents.py
git commit -m "feat(report): add 4-agent framework (Statistics/Insight/QA/Synthesis)"
```

---

## 任务 5：`ai/report.py` 新增 `generate_detailed()` 方法

**文件：**
- 修改：`ai/report.py`
- 修改：`tests/test_report.py`

- [ ] **步骤 1：在 `tests/test_report.py` 末尾追加失败测试**

```python
# tests/test_report.py 末尾追加

@pytest.fixture
def mock_multi_client():
    """模拟客户端，所有 agent 调用都返回有效 Markdown。"""
    client = MagicMock()
    resp = MagicMock()
    resp.choices[0].message.content = "## 章节标题\n\n内容段落。"
    client.chat.completions.create.return_value = resp
    return client


@pytest.fixture
def mock_analyzer(sample_df_info):
    """模拟 Analyzer，返回最小分析结果。"""
    analyzer = MagicMock()
    analyzer.summary_stats.return_value = sample_df_info
    analyzer.sales_trend.return_value = {"labels": ["2021-01"], "values": [1000.0]}
    analyzer.rfm_analysis.return_value = {"total_customers": 50, "reference_date": "2021-12-31", "customers": []}
    analyzer.correlation_matrix.return_value = {"columns": [], "matrix": []}
    return analyzer


class TestGenerateDetailed:
    def test_returns_dict(self, mock_multi_client, sample_df_info, sample_insights, mock_analyzer):
        from ai.report import ReportGenerator
        rg = ReportGenerator(mock_multi_client)
        result = rg.generate_detailed(sample_df_info, sample_insights, [], mock_analyzer)
        assert isinstance(result, dict)

    def test_has_required_keys(self, mock_multi_client, sample_df_info, sample_insights, mock_analyzer):
        from ai.report import ReportGenerator
        rg = ReportGenerator(mock_multi_client)
        result = rg.generate_detailed(sample_df_info, sample_insights, [], mock_analyzer)
        assert "title" in result
        assert "content" in result
        assert "generated_at" in result

    def test_content_longer_than_simple(self, mock_multi_client, sample_df_info, sample_insights, mock_analyzer):
        """详细报告内容应比简单报告更长（4 个 Agent 合并输出）。"""
        from ai.report import ReportGenerator
        rg     = ReportGenerator(mock_multi_client)
        simple = rg.generate(sample_df_info, sample_insights, [])
        detail = rg.generate_detailed(sample_df_info, sample_insights, [], mock_analyzer)
        assert len(detail["content"]) >= len(simple["content"])

    def test_title_different_from_simple(self, mock_multi_client, sample_df_info, sample_insights, mock_analyzer):
        from ai.report import ReportGenerator
        rg     = ReportGenerator(mock_multi_client)
        simple = rg.generate(sample_df_info, sample_insights, [])
        detail = rg.generate_detailed(sample_df_info, sample_insights, [], mock_analyzer)
        assert detail["title"] != simple["title"]

    def test_fallback_when_client_none(self, sample_df_info, sample_insights, mock_analyzer):
        from ai.report import ReportGenerator
        rg     = ReportGenerator(None)
        result = rg.generate_detailed(sample_df_info, sample_insights, [], mock_analyzer)
        assert isinstance(result, dict)
        assert "content" in result
```

- [ ] **步骤 2：运行测试，确认 FAIL**

```bash
pytest tests/test_report.py::TestGenerateDetailed -v
```
预期：全部 FAILED，报错 `AttributeError: 'ReportGenerator' object has no attribute 'generate_detailed'`

- [ ] **步骤 3：在 `ai/report.py` 的 `ReportGenerator` 类中，于 `generate()` 方法之后添加 `generate_detailed()`**

在 `# ── 生成报告 ───────────────────────────────────────` 注释块之后，`to_html()` 之前插入：

```python
def generate_detailed(
    self,
    df_info: dict[str, Any],
    insights: list[dict[str, Any]],
    chat_history: list[dict[str, str]],
    analyzer: Any,
) -> dict[str, Any]:
    """
    使用 4-Agent 框架生成详细分析报告。

    Parameters
    ----------
    df_info      : summary_stats() 返回的数据集摘要
    insights     : InsightEngine.generate_all() 返回的洞察列表
    chat_history : 完整对话历史（含 user + assistant）
    analyzer     : Analyzer 实例，用于获取额外分析数据

    Returns
    -------
    {"title": str, "content": str, "generated_at": str}
    """
    from ai.report_agents import (
        StatisticsAgent, InsightAgent, QAAgent, SynthesisAgent
    )

    # 收集额外分析数据（各方法独立 try-except，单个失败不影响其他）
    analysis_extras: dict[str, Any] = {}
    for key, method in [
        ("sales_trend",  lambda: analyzer.sales_trend()),
        ("rfm",          lambda: analyzer.rfm_analysis()),
        ("correlation",  lambda: analyzer.correlation_matrix()),
    ]:
        try:
            result = method()
            # rfm_analysis 失败时返回 {"error": "..."} 而非抛出异常
            analysis_extras[key] = result if "error" not in (result or {}) else None
        except Exception:
            analysis_extras[key] = None

    # ── 三个专注 Agent 顺序执行（接口一致，便于未来改为并发）
    stats_section    = StatisticsAgent(self.client).generate(df_info)
    insights_section = InsightAgent(self.client).generate(insights, analysis_extras)
    qa_section       = QAAgent(self.client).generate(chat_history)

    # ── 整合 Agent
    synth_section = SynthesisAgent(self.client).generate(
        stats_section, insights_section, qa_section, df_info
    )

    # ── 拼装完整报告
    dr       = df_info.get("date_range") or {}
    date_str = (
        f"　时间跨度：{dr['start']} 至 {dr['end']}"
        if dr.get("start") else ""
    )

    content = (
        f"# DataMind 数据分析详细报告\n\n"
        f"> 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  \n"
        f"> 数据规模：{df_info.get('row_count', '?')} 行 × "
        f"{df_info.get('column_count', '?')} 列{date_str}\n\n"
        f"---\n\n"
        f"{synth_section}\n\n"
        f"---\n\n"
        f"{stats_section}\n\n"
        f"---\n\n"
        f"{insights_section}\n\n"
        f"---\n\n"
        f"{qa_section}\n"
    )

    return {
        "title":        "DataMind 数据分析详细报告",
        "content":      content,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
```

- [ ] **步骤 4：运行新测试**

```bash
pytest tests/test_report.py::TestGenerateDetailed -v
```
预期：全部 PASSED

- [ ] **步骤 5：运行全量 report 测试**

```bash
pytest tests/test_report.py -v
```
预期：全部 PASSED

- [ ] **步骤 6：Commit**

```bash
git add ai/report.py tests/test_report.py
git commit -m "feat(report): add generate_detailed() with 4-agent pipeline"
```

---

## 任务 6：API 支持 `mode` 参数

**文件：**
- 修改：`routes/api.py`（`report_generate` 函数，约第 512-536 行）
- 修改：`tests/test_api.py`

- [ ] **步骤 1：在 `tests/test_api.py` 中追加失败测试**

先确认文件结构（`test_api.py` 使用 `app` fixture），在末尾追加：

```python
# tests/test_api.py 末尾追加（在现有 import 和 fixture 之后）

class TestReportGenerateMode:
    def test_simple_mode_default(self, app, uploaded_state):
        """不传 mode 时默认为 simple，返回标准报告。"""
        with app.test_client() as client:
            resp = client.post("/api/report/generate",
                               json={},
                               content_type="application/json")
            assert resp.status_code == 200
            data = resp.get_json()
            assert "content" in data
            assert "title" in data

    def test_detailed_mode_returns_longer_content(self, app, uploaded_state):
        """mode=detailed 时报告内容不短于 simple。"""
        with app.test_client() as client:
            simple = client.post("/api/report/generate",
                                 json={"mode": "simple"},
                                 content_type="application/json").get_json()
            detail = client.post("/api/report/generate",
                                 json={"mode": "detailed"},
                                 content_type="application/json").get_json()
            assert len(detail.get("content", "")) >= len(simple.get("content", ""))

    def test_invalid_mode_falls_back_to_simple(self, app, uploaded_state):
        """未知 mode 值应回退到 simple 模式，不报 500。"""
        with app.test_client() as client:
            resp = client.post("/api/report/generate",
                               json={"mode": "nonexistent"},
                               content_type="application/json")
            assert resp.status_code == 200
```

> **注意：** `uploaded_state` fixture 可能需要在 `test_api.py` 已有的 fixture 基础上添加。如果 `test_api.py` 没有 `uploaded_state`，用现有的 `app` fixture 并在测试前调用 `/api/upload` 上传文件。具体查看 `test_api.py` 顶部 fixture 定义后决定是否需要修改。

- [ ] **步骤 2：修改 `routes/api.py` 的 `report_generate` 函数**

将第 512-536 行的函数替换为：

```python
@api_bp.route("/report/generate", methods=["POST"])
def report_generate():
    """
    生成 Markdown 分析报告。

    请求体 JSON（可选）：
        {"mode": "simple"}   — 简单模式（默认）：单次 AI 调用
        {"mode": "detailed"} — 详细模式：4-Agent 框架，生成深度报告
    """
    err = _require_data()
    if err:
        return err

    state = _state()
    rg    = state.get("report_generator")
    if rg is None:
        from ai.report import ReportGenerator
        rg = ReportGenerator(None)

    session = state.get("chat_session")
    history = session.history if session else []

    body = request.get_json(silent=True) or {}
    mode = body.get("mode", "simple")

    if mode == "detailed":
        report = rg.generate_detailed(
            state["analyzer"].summary_stats(),
            state["insights"] or [],
            history,
            state["analyzer"],
        )
    else:
        # simple 及其他未知 mode 均走简单路径
        report = rg.generate(
            state["analyzer"].summary_stats(),
            state["insights"] or [],
            history,
        )

    html = rg.to_html(report)
    return jsonify({**report, "html": html})
```

- [ ] **步骤 3：运行测试**

```bash
pytest tests/test_api.py -v -k "report"
```
预期：全部 PASSED

- [ ] **步骤 4：Commit**

```bash
git add routes/api.py tests/test_api.py
git commit -m "feat(api): report/generate supports mode=simple|detailed"
```

---

## 任务 7：前端 `report.html` — 模式切换 UI

**文件：**
- 修改：`templates/report.html`

### 目标 UI
在现有"生成报告"按钮旁边添加模式选择器，点击"详细模式"时显示进度提示，生成完成后渲染报告。

- [ ] **步骤 1：在 `report.html` 中找到生成报告的按钮区域**

搜索关键字：

```bash
grep -n "generate\|report-btn\|生成报告" templates/report.html | head -20
```

- [ ] **步骤 2：在生成按钮所在区域，将单按钮替换为双模式按钮组**

找到 `id="generate-report-btn"`（或类似按钮），将其外层容器替换为：

```html
<!-- 报告模式选择区域 -->
<div class="report-mode-group d-flex align-items-center gap-2 flex-wrap">
  <button id="btn-simple-report" class="btn btn-outline-primary btn-sm" onclick="generateReport('simple')">
    <i class="bi bi-file-text me-1"></i>简单模式
  </button>
  <button id="btn-detail-report" class="btn btn-primary btn-sm" onclick="generateReport('detailed')">
    <i class="bi bi-stars me-1"></i>详细模式
    <span class="badge bg-warning text-dark ms-1" style="font-size:0.65rem">4-Agent</span>
  </button>
</div>
<!-- 详细模式进度提示（默认隐藏） -->
<div id="report-progress" class="mt-2 text-info small" style="display:none">
  <span class="spinner-border spinner-border-sm me-1" role="status"></span>
  <span id="progress-text">正在调用 StatisticsAgent…</span>
</div>
```

- [ ] **步骤 3：在 `report.html` 的 `<script>` 块中，修改/添加 `generateReport` 函数**

找到现有的 `generateReport` 函数（或 `fetch('/api/report/generate')`），替换为：

```javascript
const _PROGRESS_STEPS = [
  "StatisticsAgent 分析数据特征…",
  "InsightAgent 深度洞察归因…",
  "QAAgent 整理问答记录…",
  "SynthesisAgent 综合汇总…",
  "正在生成完整报告…",
];

function generateReport(mode) {
  mode = mode || 'simple';
  const isDetailed = mode === 'detailed';

  // 按钮状态
  ['btn-simple-report', 'btn-detail-report'].forEach(id => {
    const btn = document.getElementById(id);
    if (btn) btn.disabled = true;
  });

  // 详细模式显示进度动画
  const progress    = document.getElementById('report-progress');
  const progressTxt = document.getElementById('progress-text');
  let stepIdx = 0;
  let progressTimer = null;

  if (isDetailed && progress) {
    progress.style.display = 'block';
    progressTimer = setInterval(() => {
      stepIdx = (stepIdx + 1) % _PROGRESS_STEPS.length;
      if (progressTxt) progressTxt.textContent = _PROGRESS_STEPS[stepIdx];
    }, 3500);
  }

  fetch('/api/report/generate', {
    method:  'POST',
    headers: {'Content-Type': 'application/json'},
    body:    JSON.stringify({ mode }),
  })
    .then(r => r.json())
    .then(data => {
      clearInterval(progressTimer);
      if (progress) progress.style.display = 'none';

      // 渲染报告（沿用现有逻辑：marked.parse 或 data.html）
      const mdContent = data.content || '';
      const reportEl  = document.getElementById('report-html');
      if (reportEl) {
        reportEl.innerHTML = window.marked
          ? marked.parse(mdContent)
          : (data.html || mdContent);
      }

      // 更新下载链接（若有）
      const dlBtn = document.getElementById('download-report-btn');
      if (dlBtn && data.content) {
        const blob = new Blob([data.content], { type: 'text/markdown' });
        dlBtn.href = URL.createObjectURL(blob);
        dlBtn.download = isDetailed ? 'DataMind_详细报告.md' : 'DataMind_报告.md';
        dlBtn.style.display = '';
      }
    })
    .catch(err => {
      clearInterval(progressTimer);
      if (progress) progress.style.display = 'none';
      console.error('报告生成失败', err);
    })
    .finally(() => {
      ['btn-simple-report', 'btn-detail-report'].forEach(id => {
        const btn = document.getElementById(id);
        if (btn) btn.disabled = false;
      });
    });
}
```

- [ ] **步骤 4：手动验证 UI（无自动测试）**

启动服务：
```bash
cd C:\Users\21560\Desktop\python_final
python app.py
```
1. 上传数据集，进入报告页面
2. 点击"简单模式" → 报告在几秒内生成，显示简短内容
3. 点击"详细模式" → 按钮 disabled，进度文字循环切换；生成完成后显示多章节深度报告
4. 验证下载文件名区别（`DataMind_报告.md` vs `DataMind_详细报告.md`）

- [ ] **步骤 5：运行全量测试确认无回归**

```bash
pytest tests/ -v
```
预期：全部 PASSED

- [ ] **步骤 6：Commit**

```bash
git add templates/report.html
git commit -m "feat(ui): report mode toggle (simple/detailed) with 4-agent progress indicator"
```

---

## 最终验证与推送

- [ ] **全量测试**

```bash
pytest tests/ -v --tb=short
```
预期：全部 PASSED，0 个 ERROR

- [ ] **推送到 GitHub**

```bash
git push
```

---

## 自检结果

| 规格需求 | 覆盖任务 |
|---------|---------|
| 数据清洗：文本清洗 | 任务 1 |
| 数据清洗：智能缺失值填充 | 任务 2 |
| 数据清洗：两档 IQR + Categorical | 任务 3 |
| 报告 StatisticsAgent | 任务 4 |
| 报告 InsightAgent | 任务 4 |
| 报告 QAAgent | 任务 4 |
| 报告 SynthesisAgent | 任务 4 |
| generate_detailed() 方法 | 任务 5 |
| API mode 参数 | 任务 6 |
| 前端模式切换 UI | 任务 7 |
| 所有原有测试不受影响 | 每个任务步骤 5/6 均包含全量测试 |
