"""
ai/insight.py 单元测试
来源：学生+AI
"""
import pytest
import pandas as pd
from data.analyzer import Analyzer
from data.detector import Detector


@pytest.fixture
def df_rich() -> pd.DataFrame:
    """带完整特征列，能触发多种洞察的 DataFrame。"""
    dates = pd.date_range("2021-01-01", periods=20, freq="W")
    qty   = [5, 3, 2, 10, 1, 4, 6, 3, 8, 2, 5, 7, 4, 6, 3, 8, 5, 2, 9, 4]
    price = [2.5] * 20
    total = [q * p for q, p in zip(qty, price)]
    return pd.DataFrame({
        "InvoiceDate":           dates,
        "Quantity":              qty,
        "UnitPrice":             price,
        "TotalAmount":           total,
        "Country":               ["UK"] * 15 + ["France"] * 5,  # UK 占 75%
        "DayOfWeek":             [d.dayofweek for d in dates],
        "Hour":                  [10] * 20,
        # Quantity 有 2/20 = 10% 异常率（> 5% 阈值）
        "Quantity_is_outlier":   [False] * 18 + [True, True],
        "UnitPrice_is_outlier":  [False] * 20,
    })


@pytest.fixture
def df_minimal() -> pd.DataFrame:
    """最小 DataFrame，用于验证不崩溃。"""
    return pd.DataFrame({"a": [1, 2, 3], "b": [4.0, 5.0, 6.0]})


# ── InsightEngine ────────────────────────────────────────────

class TestInsightEngine:
    def test_returns_list(self, df_rich):
        from ai.insight import InsightEngine
        az  = Analyzer(df_rich)
        det = Detector(df_rich)
        result = InsightEngine(df_rich, az, det).generate_all()
        assert isinstance(result, list)

    def test_each_item_has_required_keys(self, df_rich):
        from ai.insight import InsightEngine
        az  = Analyzer(df_rich)
        det = Detector(df_rich)
        insights = InsightEngine(df_rich, az, det).generate_all()
        for item in insights:
            assert "type" in item
            assert "severity" in item
            assert "title" in item
            assert "detail" in item

    def test_severity_is_valid(self, df_rich):
        from ai.insight import InsightEngine
        az  = Analyzer(df_rich)
        det = Detector(df_rich)
        insights = InsightEngine(df_rich, az, det).generate_all()
        valid = {"high", "medium", "low"}
        for item in insights:
            assert item["severity"] in valid

    def test_type_is_valid(self, df_rich):
        from ai.insight import InsightEngine
        az  = Analyzer(df_rich)
        det = Detector(df_rich)
        insights = InsightEngine(df_rich, az, det).generate_all()
        valid = {"trend", "anomaly", "distribution", "correlation", "period"}
        for item in insights:
            assert item["type"] in valid

    def test_generates_anomaly_insight(self, df_rich):
        """Quantity 有 10% 异常率，应生成 anomaly 洞察。"""
        from ai.insight import InsightEngine
        az  = Analyzer(df_rich)
        det = Detector(df_rich)
        insights = InsightEngine(df_rich, az, det).generate_all()
        types = [i["type"] for i in insights]
        assert "anomaly" in types

    def test_generates_distribution_insight(self, df_rich):
        """UK 占 75%，应生成 distribution 洞察。"""
        from ai.insight import InsightEngine
        az  = Analyzer(df_rich)
        det = Detector(df_rich)
        insights = InsightEngine(df_rich, az, det).generate_all()
        types = [i["type"] for i in insights]
        assert "distribution" in types

    def test_no_crash_on_minimal_df(self, df_minimal):
        """最小 DataFrame 不应崩溃，返回空列表或少量洞察。"""
        from ai.insight import InsightEngine
        az  = Analyzer(df_minimal)
        det = Detector(df_minimal)
        result = InsightEngine(df_minimal, az, det).generate_all()
        assert isinstance(result, list)
