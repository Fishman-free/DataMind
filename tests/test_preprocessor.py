"""
data/preprocessor.py 单元测试
来源：学生+AI
"""
import pytest
import numpy as np
import pandas as pd


# ── 测试夹具 ───────────────────────────────────────────────

@pytest.fixture
def df_with_duplicates() -> pd.DataFrame:
    return pd.DataFrame({
        "a": [1, 2, 2, 3],
        "b": ["x", "y", "y", "z"],
    })


@pytest.fixture
def df_with_missing() -> pd.DataFrame:
    return pd.DataFrame({
        "num":  [1.0, np.nan, 3.0, np.nan],
        "text": ["hello", None, "world", None],
    })


@pytest.fixture
def df_high_missing() -> pd.DataFrame:
    """num2 列缺失率 75%，超过阈值。"""
    return pd.DataFrame({
        "num":  [1.0, 2.0, 3.0, 4.0],
        "num2": [np.nan, np.nan, np.nan, 5.0],
    })


@pytest.fixture
def df_with_dates() -> pd.DataFrame:
    return pd.DataFrame({
        "date_col": ["2021-01-01", "2021-06-15", "2022-03-20"],
        "value":    [100, 200, 300],
    })


@pytest.fixture
def df_with_outliers() -> pd.DataFrame:
    """value 列含明显异常值 9999。"""
    return pd.DataFrame({
        "value": [10, 12, 11, 13, 10, 9999, 11, 12],
    })


@pytest.fixture
def df_retail_like() -> pd.DataFrame:
    """模拟 Online Retail 数据集结构，用于测试特征工程。"""
    return pd.DataFrame({
        "InvoiceDate": pd.to_datetime(["2021-01-05 10:30", "2021-03-20 14:00", "2021-07-08 09:15"]),
        "Quantity":    [5, 3, 10],
        "UnitPrice":   [2.5, 8.0, 1.5],
    })


@pytest.fixture
def df_clean_simple() -> pd.DataFrame:
    return pd.DataFrame({
        "a": [1, 2, 3],
        "b": ["x", "y", "z"],
    })


# ── remove_duplicates ────────────────────────────────────

class TestRemoveDuplicates:
    def test_removes_duplicate_rows(self, df_with_duplicates):
        from data.preprocessor import Preprocessor
        result = Preprocessor(df_with_duplicates).remove_duplicates().df
        assert len(result) == 3

    def test_original_df_unchanged(self, df_with_duplicates):
        from data.preprocessor import Preprocessor
        original_len = len(df_with_duplicates)
        Preprocessor(df_with_duplicates).remove_duplicates()
        assert len(df_with_duplicates) == original_len

    def test_log_records_removed_count(self, df_with_duplicates):
        from data.preprocessor import Preprocessor
        p = Preprocessor(df_with_duplicates).remove_duplicates()
        report = p.get_report()
        assert report["remove_duplicates"]["removed"] == 1

    def test_no_duplicates_unchanged(self, df_clean_simple):
        from data.preprocessor import Preprocessor
        result = Preprocessor(df_clean_simple).remove_duplicates().df
        assert len(result) == 3


# ── handle_missing ────────────────────────────────────────

class TestHandleMissing:
    def test_numeric_filled_with_median(self, df_with_missing):
        from data.preprocessor import Preprocessor
        result = Preprocessor(df_with_missing).handle_missing().df
        assert result["num"].isna().sum() == 0
        # 中位数 = median([1.0, 3.0]) = 2.0
        assert result["num"].iloc[1] == pytest.approx(2.0)

    def test_text_filled_with_unknown(self, df_with_missing):
        from data.preprocessor import Preprocessor
        result = Preprocessor(df_with_missing).handle_missing().df
        assert result["text"].isna().sum() == 0
        assert result["text"].iloc[1] == "Unknown"

    def test_high_missing_rate_warning_in_log(self, df_high_missing):
        from data.preprocessor import Preprocessor
        p = Preprocessor(df_high_missing).handle_missing()
        report = p.get_report()
        # num2 缺失率 75%，应出现在警告列表
        warnings = report["handle_missing"].get("high_missing_cols", [])
        assert "num2" in warnings

    def test_no_missing_unchanged(self, df_clean_simple):
        from data.preprocessor import Preprocessor
        result = Preprocessor(df_clean_simple).handle_missing().df
        assert result.equals(df_clean_simple)


# ── convert_types ─────────────────────────────────────────

class TestConvertTypes:
    def test_date_string_converted_to_datetime(self, df_with_dates):
        from data.preprocessor import Preprocessor
        result = Preprocessor(df_with_dates).convert_types().df
        assert pd.api.types.is_datetime64_any_dtype(result["date_col"])

    def test_numeric_string_converted(self):
        from data.preprocessor import Preprocessor
        df = pd.DataFrame({"price": ["1.5", "2.0", "3.5"]})
        result = Preprocessor(df).convert_types().df
        assert pd.api.types.is_numeric_dtype(result["price"])

    def test_non_convertible_column_unchanged(self):
        from data.preprocessor import Preprocessor
        df = pd.DataFrame({"name": ["Alice", "Bob", "Charlie"]})
        result = Preprocessor(df).convert_types().df
        # 兼容 pandas 旧版 object 和新版 StringDtype
        assert pd.api.types.is_string_dtype(result["name"])
        assert not pd.api.types.is_numeric_dtype(result["name"])
        assert not pd.api.types.is_datetime64_any_dtype(result["name"])


# ── filter_outliers ───────────────────────────────────────

class TestFilterOutliers:
    def test_outlier_column_created(self, df_with_outliers):
        from data.preprocessor import Preprocessor
        result = Preprocessor(df_with_outliers).filter_outliers().df
        assert "value_is_outlier" in result.columns

    def test_extreme_value_flagged(self, df_with_outliers):
        from data.preprocessor import Preprocessor
        result = Preprocessor(df_with_outliers).filter_outliers().df
        # 9999 应被标记为异常
        outlier_rows = result[result["value_is_outlier"] == True]
        assert len(outlier_rows) >= 1
        assert 9999 in outlier_rows["value"].values

    def test_normal_values_not_flagged(self, df_with_outliers):
        from data.preprocessor import Preprocessor
        result = Preprocessor(df_with_outliers).filter_outliers().df
        normal_rows = result[result["value_is_outlier"] == False]
        assert 10 in normal_rows["value"].values

    def test_log_records_outlier_count(self, df_with_outliers):
        from data.preprocessor import Preprocessor
        p = Preprocessor(df_with_outliers).filter_outliers()
        report = p.get_report()
        assert report["filter_outliers"]["flagged"] >= 1


# ── add_features ──────────────────────────────────────────

class TestAddFeatures:
    def test_datetime_features_added(self, df_retail_like):
        from data.preprocessor import Preprocessor
        result = Preprocessor(df_retail_like).add_features().df
        for col in ["Year", "Month", "DayOfWeek", "Hour"]:
            assert col in result.columns, f"缺少列: {col}"

    def test_total_amount_added(self, df_retail_like):
        from data.preprocessor import Preprocessor
        result = Preprocessor(df_retail_like).add_features().df
        assert "TotalAmount" in result.columns
        # 第一行：5 * 2.5 = 12.5
        assert result["TotalAmount"].iloc[0] == pytest.approx(12.5)

    def test_no_date_no_crash(self, df_clean_simple):
        from data.preprocessor import Preprocessor
        # 没有日期列时不应报错
        result = Preprocessor(df_clean_simple).add_features().df
        assert isinstance(result, pd.DataFrame)


# ── run_all & get_report ──────────────────────────────────

class TestRunAll:
    def test_run_all_returns_dataframe(self, df_retail_like):
        from data.preprocessor import Preprocessor
        result = Preprocessor(df_retail_like).run_all()
        assert isinstance(result, pd.DataFrame)

    def test_run_all_chainable(self, df_with_duplicates):
        from data.preprocessor import Preprocessor
        # run_all 返回 df，不返回 self，所以单独测试链式
        p = Preprocessor(df_with_duplicates)
        df = p.run_all()
        assert isinstance(df, pd.DataFrame)

    def test_get_report_has_all_steps(self, df_retail_like):
        from data.preprocessor import Preprocessor
        p = Preprocessor(df_retail_like)
        p.run_all()
        report = p.get_report()
        for step in ["remove_duplicates", "handle_missing", "convert_types",
                     "filter_outliers", "add_features"]:
            assert step in report, f"报告缺少步骤: {step}"

    def test_get_report_total_rows(self, df_retail_like):
        from data.preprocessor import Preprocessor
        p = Preprocessor(df_retail_like)
        p.run_all()
        report = p.get_report()
        assert "original_rows" in report
        assert "final_rows" in report
        assert report["original_rows"] == 3

    def test_get_report_has_clean_text_step(self, df_retail_like):
        from data.preprocessor import Preprocessor
        p = Preprocessor(df_retail_like)
        p.run_all()
        report = p.get_report()
        assert "clean_text" in report, "报告缺少 clean_text 步骤"


# ── clean_text ────────────────────────────────────────────

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


# ── 改进的 handle_missing（偏态 + 低基数）──────────────────

class TestHandleMissingImproved:
    def test_normal_numeric_filled_with_mean(self):
        """正态分布列（skew ≈ 0）用均值填充。"""
        from data.preprocessor import Preprocessor
        df = pd.DataFrame({"val": [10.0, 11.0, 12.0, 13.0, np.nan]})
        result = Preprocessor(df).handle_missing().df
        assert result["val"].iloc[4] == pytest.approx(11.5)

    def test_skewed_numeric_filled_with_median(self):
        """高偏态列（skew > 1.0）用中位数填充。"""
        from data.preprocessor import Preprocessor
        df = pd.DataFrame({"val": [1.0, 1.0, 1.0, 1.0, 100.0, np.nan]})
        result = Preprocessor(df).handle_missing().df
        assert result["val"].iloc[5] == pytest.approx(1.0)

    def test_low_cardinality_text_filled_with_mode(self):
        """低基数文本列用众数填充。"""
        from data.preprocessor import Preprocessor
        df = pd.DataFrame({
            "status": ["active", "active", "active", "inactive", "inactive", None],
        })
        result = Preprocessor(df).handle_missing().df
        assert result["status"].iloc[5] == "active"


# ── 两档 IQR 异常标记 ────────────────────────────────────

class TestTwoTierIQR:
    def test_mild_outlier_column_created(self):
        """×1.5 IQR → _is_outlier 列存在。"""
        from data.preprocessor import Preprocessor
        df = pd.DataFrame({"value": [10, 12, 11, 13, 10, 9999, 11, 12]})
        result = Preprocessor(df).filter_outliers().df
        assert "value_is_outlier" in result.columns

    def test_extreme_outlier_column_created(self):
        """×3.0 IQR → _is_extreme_outlier 列存在。"""
        from data.preprocessor import Preprocessor
        df = pd.DataFrame({"value": [10, 12, 11, 13, 10, 9999, 11, 12]})
        result = Preprocessor(df).filter_outliers().df
        assert "value_is_extreme_outlier" in result.columns

    def test_extreme_outlier_flagged(self):
        """极端异常值（×3.0）被标记。"""
        from data.preprocessor import Preprocessor
        df = pd.DataFrame({"value": [10, 12, 11, 13, 10, 9999, 11, 12]})
        result = Preprocessor(df).filter_outliers().df
        extreme_rows = result[result["value_is_extreme_outlier"] == True]
        assert 9999 in extreme_rows["value"].values

    def test_mild_not_extreme_for_borderline(self):
        """轻度异常不被标记为极端异常。"""
        from data.preprocessor import Preprocessor
        # Q1=10, Q3=13, IQR=3; mild=10-4.5=5.5, extreme=10-9=1; upper mild=17.5, extreme=22
        # 值 20: 超 mild(17.5) 但不超 extreme(22) → mild True, extreme False
        df = pd.DataFrame({"val": [10, 10, 10, 13, 13, 13, 20]})
        result = Preprocessor(df).filter_outliers().df
        row_20 = result[result["val"] == 20]
        assert row_20["val_is_outlier"].iloc[0] == True
        assert row_20["val_is_extreme_outlier"].iloc[0] == False
