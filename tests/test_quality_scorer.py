"""数据质量评分卡单元测试。"""
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from data.quality_scorer import QualityScorer


class TestQualityScorer:
    """QualityScorer 单元测试。"""

    @pytest.fixture
    def perfect_df(self):
        """完美的数据集：无缺失、无重复、无异常、日期新鲜。"""
        return pd.DataFrame({
            "id": [1, 2, 3, 4, 5],
            "name": ["A", "B", "C", "D", "E"],
            "value": [10.0, 20.0, 30.0, 40.0, 50.0],
            "date": pd.date_range(end=datetime.now(), periods=5, freq="D"),
        })

    @pytest.fixture
    def messy_df(self):
        """脏数据：有缺失、重复、异常值、旧日期。"""
        return pd.DataFrame({
            "id": [1, 2, 2, 4, 5],
            "name": ["A", None, "C", "D", None],
            "value": [10.0, 999.0, 30.0, np.nan, 50.0],
            "date": pd.to_datetime(["2020-01-01", "2020-01-02", "2020-01-03", "2020-01-04", "2020-01-05"]),
        })

    def test_perfect_score(self, perfect_df):
        """完美数据集应获得高分（A 级）。"""
        scorer = QualityScorer()
        result = scorer.score(perfect_df, perfect_df, {"original_rows": 5, "final_rows": 5})
        assert result["total_score"] >= 90
        assert result["grade"] == "A"

    def test_messy_score(self, messy_df):
        """脏数据应获得较低分。"""
        scorer = QualityScorer()
        result = scorer.score(messy_df, messy_df, {"original_rows": 5, "final_rows": 3})
        assert result["total_score"] < 80

    def test_all_dimensions_present(self, perfect_df):
        """评分结果应包含全部 5 个维度。"""
        scorer = QualityScorer()
        result = scorer.score(perfect_df, perfect_df, {"original_rows": 5, "final_rows": 5})
        dimensions = result["dimensions"]
        expected_dims = {"completeness", "uniqueness", "consistency", "timeliness", "accuracy"}
        assert set(dimensions.keys()) == expected_dims

    def test_dimension_score_range(self, perfect_df):
        """每个维度分应在 0-100 范围内。"""
        scorer = QualityScorer()
        result = scorer.score(perfect_df, perfect_df, {"original_rows": 5, "final_rows": 5})
        for dim_name, dim_data in result["dimensions"].items():
            assert 0 <= dim_data["score"] <= 100, f"{dim_name} score {dim_data['score']} out of range"

    def test_grade_mapping(self):
        """等级映射：A(90-100), B(75-89), C(60-74), D(<60)。"""
        scorer = QualityScorer()
        # 用 monkey-patching 方式测试等级映射
        assert scorer._grade(95) == "A"
        assert scorer._grade(80) == "B"
        assert scorer._grade(65) == "C"
        assert scorer._grade(40) == "D"

    def test_completeness_perfect(self, perfect_df):
        """无缺失值 → 完整性满分 100。"""
        scorer = QualityScorer()
        dims = scorer._score_dimensions(perfect_df, perfect_df, {})
        assert dims["completeness"]["score"] == 100

    def test_completeness_with_missing(self, messy_df):
        """有缺失值 → 完整性扣分。"""
        scorer = QualityScorer()
        dims = scorer._score_dimensions(messy_df, messy_df, {})
        assert dims["completeness"]["score"] < 100

    def test_uniqueness_with_duplicates(self):
        """有重复行 → 唯一性扣分。"""
        scorer = QualityScorer()
        dup_df = pd.DataFrame({
            "a": [1, 2, 2, 1],
            "b": [3, 4, 4, 3],
        })
        dims = scorer._score_dimensions(dup_df, dup_df, {})
        assert dims["uniqueness"]["score"] < 100

    def test_empty_dataframe(self):
        """空 DataFrame 应安全处理。"""
        scorer = QualityScorer()
        empty = pd.DataFrame()
        result = scorer.score(empty, empty, {"original_rows": 0, "final_rows": 0})
        assert result["total_score"] == 0
        assert result["grade"] == "D"

    def test_result_structure(self, perfect_df):
        """验证返回结构完整性。"""
        scorer = QualityScorer()
        result = scorer.score(perfect_df, perfect_df, {"original_rows": 5, "final_rows": 5})
        assert "total_score" in result
        assert "grade" in result
        assert "dimensions" in result
        assert "suggestions" in result
        assert isinstance(result["suggestions"], list)
