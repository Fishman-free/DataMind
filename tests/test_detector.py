"""
data/detector.py 单元测试
基于 Online Retail 真实数据结构设计 mock DataFrame。
来源：学生+AI
"""
import pytest
import numpy as np
import pandas as pd


# ── 测试夹具 ────────────────────────────────────────────────

@pytest.fixture
def df_with_outlier_cols() -> pd.DataFrame:
    """模拟 preprocessor.filter_outliers() 处理后的 DataFrame（含 _is_outlier 列）。"""
    return pd.DataFrame({
        "Quantity":              [5, 3, 2, 10, 1, 4, 6, 3, 8, 2],
        "UnitPrice":             [2.5, 1.0, 2.5, 8.0, 1.0, 2.5, 0.5, 2.5, 8.0, 1.0],
        "TotalAmount":           [12.5, 3.0, 5.0, 80.0, 1.0, 10.0, 3.0, 7.5, 64.0, 2.0],
        "Quantity_is_outlier":   [False] * 10,
        "UnitPrice_is_outlier":  [False, False, False, True, False, False, False, False, True, False],
        "TotalAmount_is_outlier":[False, False, False, True, False, False, False, False, True, False],
    })


@pytest.fixture
def df_no_outlier_cols() -> pd.DataFrame:
    """无 _is_outlier 列的 DataFrame。"""
    return pd.DataFrame({
        "a": [1, 2, 3],
        "b": [4.0, 5.0, 6.0],
    })


@pytest.fixture
def df_zscore_target() -> pd.DataFrame:
    """包含明显 Z-Score 异常值（3 个超出 2σ）的 DataFrame。"""
    normal = [10.0] * 47 + [100.0] * 3   # 最后3个是明显异常
    return pd.DataFrame({"value": normal})


@pytest.fixture
def df_with_trend() -> pd.DataFrame:
    """带日期列的时间序列，第 15 天有一个突变峰值。"""
    dates  = pd.date_range("2021-01-01", periods=30, freq="D")
    values = [100.0] * 14 + [200.0] + [100.0] * 15
    return pd.DataFrame({"InvoiceDate": dates, "TotalAmount": values})


# ── outlier_summary ──────────────────────────────────────────

class TestOutlierSummary:
    def test_returns_list(self, df_with_outlier_cols):
        from data.detector import Detector
        result = Detector(df_with_outlier_cols).outlier_summary()
        assert isinstance(result, list)

    def test_each_item_has_required_keys(self, df_with_outlier_cols):
        from data.detector import Detector
        result = Detector(df_with_outlier_cols).outlier_summary()
        for item in result:
            assert "col" in item
            assert "outlier_count" in item
            assert "outlier_rate" in item

    def test_correct_outlier_count(self, df_with_outlier_cols):
        from data.detector import Detector
        result = Detector(df_with_outlier_cols).outlier_summary()
        # UnitPrice 有 2 个异常
        unitprice_item = next((r for r in result if r["col"] == "UnitPrice"), None)
        assert unitprice_item is not None
        assert unitprice_item["outlier_count"] == 2

    def test_no_outlier_cols_returns_empty(self, df_no_outlier_cols):
        from data.detector import Detector
        result = Detector(df_no_outlier_cols).outlier_summary()
        assert result == []

    def test_outlier_rate_between_0_and_1(self, df_with_outlier_cols):
        from data.detector import Detector
        result = Detector(df_with_outlier_cols).outlier_summary()
        for item in result:
            assert 0.0 <= item["outlier_rate"] <= 1.0


# ── zscore_anomalies ────────────────────────────────────────

class TestZscoreAnomalies:
    def test_returns_dict(self, df_zscore_target):
        from data.detector import Detector
        result = Detector(df_zscore_target).zscore_anomalies("value")
        assert isinstance(result, dict)

    def test_has_required_keys(self, df_zscore_target):
        from data.detector import Detector
        result = Detector(df_zscore_target).zscore_anomalies("value")
        assert "col" in result
        assert "threshold" in result
        assert "anomaly_count" in result
        assert "anomalies" in result

    def test_detects_extreme_values(self, df_zscore_target):
        from data.detector import Detector
        # 3 个 100.0 在 10.0 均值数据中 Z-Score 远超 2.0
        result = Detector(df_zscore_target).zscore_anomalies("value", threshold=2.0)
        assert result["anomaly_count"] == 3

    def test_no_anomalies_on_uniform_data(self):
        from data.detector import Detector
        df = pd.DataFrame({"val": [10.0] * 20})
        result = Detector(df).zscore_anomalies("val")
        assert result["anomaly_count"] == 0

    def test_missing_col_returns_error(self, df_zscore_target):
        from data.detector import Detector
        result = Detector(df_zscore_target).zscore_anomalies("nonexistent")
        assert "error" in result


# ── trend_breaks ────────────────────────────────────────────

class TestTrendBreaks:
    def test_returns_dict(self, df_with_trend):
        from data.detector import Detector
        result = Detector(df_with_trend).trend_breaks("TotalAmount")
        assert isinstance(result, dict)

    def test_has_required_keys(self, df_with_trend):
        from data.detector import Detector
        result = Detector(df_with_trend).trend_breaks("TotalAmount")
        assert "col" in result
        assert "breaks" in result
        assert "labels" in result
        assert "values" in result
        assert "trend" in result

    def test_detects_spike(self, df_with_trend):
        from data.detector import Detector
        # 第 15 天值是 200，其余是 100，窗口 7 sigma 1.5 应检测到突变
        result = Detector(df_with_trend).trend_breaks("TotalAmount", window=7, sigma=1.5)
        assert result["break_count"] >= 1

    def test_no_date_col_returns_error(self, df_no_outlier_cols):
        from data.detector import Detector
        result = Detector(df_no_outlier_cols).trend_breaks("a")
        assert "error" in result

    def test_missing_col_returns_error(self, df_with_trend):
        from data.detector import Detector
        result = Detector(df_with_trend).trend_breaks("nonexistent")
        assert "error" in result

    def test_labels_and_values_same_length(self, df_with_trend):
        from data.detector import Detector
        result = Detector(df_with_trend).trend_breaks("TotalAmount")
        assert len(result["labels"]) == len(result["values"])
        assert len(result["labels"]) == len(result["trend"])


# ── run_all ──────────────────────────────────────────────────

class TestRunAll:
    def test_returns_dict(self, df_with_outlier_cols):
        from data.detector import Detector
        result = Detector(df_with_outlier_cols).run_all()
        assert isinstance(result, dict)

    def test_has_outlier_summary_key(self, df_with_outlier_cols):
        from data.detector import Detector
        result = Detector(df_with_outlier_cols).run_all()
        assert "outlier_summary" in result

    def test_has_zscore_key(self, df_with_outlier_cols):
        from data.detector import Detector
        result = Detector(df_with_outlier_cols).run_all()
        assert "zscore_anomalies" in result

    def test_has_trend_key(self, df_with_outlier_cols):
        from data.detector import Detector
        result = Detector(df_with_outlier_cols).run_all()
        assert "trend_breaks" in result

    def test_no_crash_on_minimal_df(self, df_no_outlier_cols):
        from data.detector import Detector
        result = Detector(df_no_outlier_cols).run_all()
        assert isinstance(result, dict)
