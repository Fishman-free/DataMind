import pandas as pd
from skills.stats_skill.stats_skill import execute_stats_plan


def _df():
    return pd.DataFrame({"region": ["A", "B", "A", "B"], "sales": [10, 20, 30, 40]})


def test_stats_overall_mean():
    r = execute_stats_plan(_df(), {"metrics": ["mean"], "columns": ["sales"]})
    assert "column" in r.evidence.columns
    row = r.evidence.iloc[0]
    assert abs(float(row["mean"]) - 25.0) < 1e-6


def test_stats_grouped():
    r = execute_stats_plan(_df(), {"metrics": ["mean"], "columns": ["sales"], "group_by": "region"})
    assert "region" in r.evidence.columns
    assert any("sales_mean" == c for c in r.evidence.columns)


def test_stats_bad_column_falls_back():
    r = execute_stats_plan(_df(), {"metrics": ["mean"], "columns": ["ghost"]})
    assert len(r.evidence) >= 1  # 不抛异常，降级到数值列
    assert r.chart is None
