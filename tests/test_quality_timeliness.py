"""质量评分时效性稳定性测试。"""

import math

import pandas as pd

from data.quality_scorer import QualityScorer


def test_timeliness_dimension_always_exists_without_datetime_column():
    """无日期列时也必须包含 timeliness 维度。"""
    df = pd.DataFrame({
        "id": [1, 2, 3],
        "name": ["A", "B", "C"],
        "value": [10, 20, 30],
    })

    result = QualityScorer().score(df, df, {"steps": []})

    assert "timeliness" in result["dimensions"]


def test_all_dimension_scores_are_finite_and_in_0_100_range():
    """所有维度分值都应是有限数值且落在 [0, 100]。"""
    df_raw = pd.DataFrame(index=range(3))
    df_clean = df_raw.copy()

    result = QualityScorer().score(
        df_raw,
        df_clean,
        {"steps": [{"name": "类型转换", "detail": None}]},
    )

    for dim in result["dimensions"].values():
        score = float(dim["score"])
        assert math.isfinite(score)
        assert 0 <= score <= 100
