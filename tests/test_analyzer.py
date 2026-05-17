"""
data/analyzer.py 单元测试
基于 Online Retail 真实数据结构设计 mock DataFrame。
来源：学生+AI
"""
import pytest
import numpy as np
import pandas as pd


# ── 测试夹具：模拟 preprocessor 处理后的 Online Retail 数据 ──────

@pytest.fixture
def retail_df() -> pd.DataFrame:
    """
    模拟 Online Retail 经过 preprocessor.run_all() 后的结构。
    包含 TotalAmount / Year / Month / DayOfWeek / Hour 派生列。
    """
    dates = pd.to_datetime([
        "2021-01-05 10:00", "2021-01-10 14:00", "2021-01-20 09:00",
        "2021-02-03 11:00", "2021-02-15 16:00", "2021-03-01 10:00",
        "2021-03-20 08:00", "2021-04-05 15:00", "2021-04-18 13:00",
        "2021-05-02 10:00",
    ])
    return pd.DataFrame({
        "InvoiceNo":   [f"INV{i:03d}" for i in range(10)],
        "StockCode":   ["A001", "A002", "A001", "B001", "A002", "A001", "B002", "A001", "B001", "A002"],
        "Description": ["Apple", "Banana", "Apple", "Book", "Banana", "Apple", "Pen", "Apple", "Book", "Banana"],
        "Quantity":    [5, 3, 2, 10, 1, 4, 6, 3, 8, 2],
        "InvoiceDate": dates,
        "UnitPrice":   [2.5, 1.0, 2.5, 8.0, 1.0, 2.5, 0.5, 2.5, 8.0, 1.0],
        "CustomerID":  [101, 102, 101, 103, 102, 104, 103, 101, 102, 105],
        "Country":     ["UK", "UK", "France", "UK", "Germany", "France", "UK", "UK", "Germany", "UK"],
        "TotalAmount": [12.5, 3.0, 5.0, 80.0, 1.0, 10.0, 3.0, 7.5, 64.0, 2.0],
        "Year":        [d.year for d in dates],
        "Month":       [d.month for d in dates],
        "DayOfWeek":   [d.dayofweek for d in dates],
        "Hour":        [d.hour for d in dates],
    })


@pytest.fixture
def no_date_df() -> pd.DataFrame:
    """无日期列的 DataFrame，用于测试降级处理。"""
    return pd.DataFrame({
        "value": [10, 20, 30, 40],
        "category": ["A", "B", "A", "B"],
    })


@pytest.fixture
def no_customer_df() -> pd.DataFrame:
    """缺少 CustomerID，用于测试 RFM 降级处理。"""
    return pd.DataFrame({
        "Quantity":    [1, 2, 3],
        "UnitPrice":   [5.0, 6.0, 7.0],
        "TotalAmount": [5.0, 12.0, 21.0],
    })


# ── summary_stats ─────────────────────────────────────────

class TestSummaryStats:
    def test_returns_dict(self, retail_df):
        from data.analyzer import Analyzer
        result = Analyzer(retail_df).summary_stats()
        assert isinstance(result, dict)

    def test_contains_row_count(self, retail_df):
        from data.analyzer import Analyzer
        result = Analyzer(retail_df).summary_stats()
        assert result["row_count"] == 10

    def test_contains_column_count(self, retail_df):
        from data.analyzer import Analyzer
        result = Analyzer(retail_df).summary_stats()
        assert result["column_count"] == len(retail_df.columns)

    def test_contains_numeric_stats(self, retail_df):
        from data.analyzer import Analyzer
        result = Analyzer(retail_df).summary_stats()
        assert "numeric_stats" in result
        # TotalAmount 应在数值统计中
        assert "TotalAmount" in result["numeric_stats"]

    def test_numeric_stats_has_mean(self, retail_df):
        from data.analyzer import Analyzer
        result = Analyzer(retail_df).summary_stats()
        stats = result["numeric_stats"]["TotalAmount"]
        assert "mean" in stats
        assert "median" in stats
        assert "std" in stats
        assert "min" in stats
        assert "max" in stats

    def test_contains_missing_info(self, retail_df):
        from data.analyzer import Analyzer
        result = Analyzer(retail_df).summary_stats()
        assert "missing_counts" in result


# ── sales_trend ───────────────────────────────────────────

class TestSalesTrend:
    def test_returns_dict(self, retail_df):
        from data.analyzer import Analyzer
        result = Analyzer(retail_df).sales_trend()
        assert isinstance(result, dict)

    def test_has_labels_and_values(self, retail_df):
        from data.analyzer import Analyzer
        result = Analyzer(retail_df).sales_trend()
        assert "labels" in result
        assert "values" in result

    def test_labels_and_values_same_length(self, retail_df):
        from data.analyzer import Analyzer
        result = Analyzer(retail_df).sales_trend()
        assert len(result["labels"]) == len(result["values"])

    def test_monthly_groups_correct(self, retail_df):
        from data.analyzer import Analyzer
        # 'M' 会被内部映射为 'ME'（pandas 2.2+ 新别名）
        result = Analyzer(retail_df).sales_trend(freq="ME")
        # 数据跨 5 个月（1~5月），应有 5 个分组
        assert len(result["labels"]) == 5

    def test_no_date_returns_none(self, no_date_df):
        from data.analyzer import Analyzer
        result = Analyzer(no_date_df).sales_trend()
        assert result is None

    def test_values_are_positive(self, retail_df):
        from data.analyzer import Analyzer
        result = Analyzer(retail_df).sales_trend()
        assert all(v >= 0 for v in result["values"])


# ── top_products ──────────────────────────────────────────

class TestTopProducts:
    def test_returns_list(self, retail_df):
        from data.analyzer import Analyzer
        result = Analyzer(retail_df).top_products(n=3)
        assert isinstance(result, list)

    def test_length_capped_at_n(self, retail_df):
        from data.analyzer import Analyzer
        result = Analyzer(retail_df).top_products(n=3)
        assert len(result) <= 3

    def test_each_item_has_name_and_value(self, retail_df):
        from data.analyzer import Analyzer
        result = Analyzer(retail_df).top_products(n=3)
        for item in result:
            assert "name" in item
            assert "value" in item

    def test_sorted_descending(self, retail_df):
        from data.analyzer import Analyzer
        result = Analyzer(retail_df).top_products(n=5)
        values = [item["value"] for item in result]
        assert values == sorted(values, reverse=True)

    def test_apple_high_ranked(self, retail_df):
        """Apple 出现次数最多，应在 Top 3。"""
        from data.analyzer import Analyzer
        result = Analyzer(retail_df).top_products(n=3)
        names = [item["name"] for item in result]
        assert "Apple" in names


# ── rfm_analysis ──────────────────────────────────────────

class TestRfmAnalysis:
    def test_returns_dict(self, retail_df):
        from data.analyzer import Analyzer
        result = Analyzer(retail_df).rfm_analysis()
        assert isinstance(result, dict)

    def test_has_customers_list(self, retail_df):
        from data.analyzer import Analyzer
        result = Analyzer(retail_df).rfm_analysis()
        assert "customers" in result

    def test_customer_count_correct(self, retail_df):
        from data.analyzer import Analyzer
        result = Analyzer(retail_df).rfm_analysis()
        # retail_df 有 5 个唯一客户 (101~105)
        assert result["total_customers"] == 5

    def test_each_customer_has_rfm_scores(self, retail_df):
        from data.analyzer import Analyzer
        result = Analyzer(retail_df).rfm_analysis()
        for customer in result["customers"][:3]:
            assert "recency" in customer
            assert "frequency" in customer
            assert "monetary" in customer

    def test_missing_columns_returns_error(self, no_customer_df):
        from data.analyzer import Analyzer
        result = Analyzer(no_customer_df).rfm_analysis()
        assert "error" in result


# ── country_distribution ──────────────────────────────────

class TestCountryDistribution:
    def test_returns_list(self, retail_df):
        from data.analyzer import Analyzer
        result = Analyzer(retail_df).country_distribution()
        assert isinstance(result, list)

    def test_each_item_has_country_and_value(self, retail_df):
        from data.analyzer import Analyzer
        result = Analyzer(retail_df).country_distribution()
        for item in result:
            assert "country" in item
            assert "value" in item
            assert "percentage" in item

    def test_percentages_sum_to_100(self, retail_df):
        from data.analyzer import Analyzer
        result = Analyzer(retail_df).country_distribution()
        total_pct = sum(item["percentage"] for item in result)
        assert abs(total_pct - 100.0) < 0.1

    def test_sorted_descending(self, retail_df):
        from data.analyzer import Analyzer
        result = Analyzer(retail_df).country_distribution()
        values = [item["value"] for item in result]
        assert values == sorted(values, reverse=True)

    def test_no_country_col_returns_empty(self, no_date_df):
        from data.analyzer import Analyzer
        result = Analyzer(no_date_df).country_distribution()
        assert result == []


# ── correlation_matrix ────────────────────────────────────

class TestCorrelationMatrix:
    def test_returns_dict(self, retail_df):
        from data.analyzer import Analyzer
        result = Analyzer(retail_df).correlation_matrix()
        assert isinstance(result, dict)

    def test_has_columns_and_matrix(self, retail_df):
        from data.analyzer import Analyzer
        result = Analyzer(retail_df).correlation_matrix()
        assert "columns" in result
        assert "matrix" in result

    def test_diagonal_is_one(self, retail_df):
        from data.analyzer import Analyzer
        result = Analyzer(retail_df).correlation_matrix()
        matrix = result["matrix"]
        for i, row in enumerate(matrix):
            assert abs(row[i] - 1.0) < 1e-6

    def test_symmetric(self, retail_df):
        from data.analyzer import Analyzer
        result = Analyzer(retail_df).correlation_matrix()
        matrix = result["matrix"]
        for i in range(len(matrix)):
            for j in range(len(matrix[i])):
                assert abs(matrix[i][j] - matrix[j][i]) < 1e-6


# ── time_pattern ──────────────────────────────────────────

class TestTimePattern:
    def test_returns_dict(self, retail_df):
        from data.analyzer import Analyzer
        result = Analyzer(retail_df).time_pattern()
        assert isinstance(result, dict)

    def test_has_required_keys(self, retail_df):
        from data.analyzer import Analyzer
        result = Analyzer(retail_df).time_pattern()
        assert "days" in result
        assert "hours" in result
        assert "matrix" in result

    def test_days_length_is_7(self, retail_df):
        from data.analyzer import Analyzer
        result = Analyzer(retail_df).time_pattern()
        assert len(result["days"]) == 7

    def test_no_date_cols_returns_none(self, no_date_df):
        from data.analyzer import Analyzer
        result = Analyzer(no_date_df).time_pattern()
        assert result is None
