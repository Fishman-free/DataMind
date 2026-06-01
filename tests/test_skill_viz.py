import pandas as pd
from skills.viz_skill.viz_skill import execute_viz_plan


def _df():
    return pd.DataFrame({"cat": ["A", "B", "A", "B"], "val": [10, 20, 30, 40]})


def test_viz_bar_chart_built():
    r = execute_viz_plan(_df(), {"chart_type": "bar", "x": "cat", "y": "val", "agg": "sum"})
    assert isinstance(r.chart, dict) and "data" in r.chart
    assert len(r.evidence) == 2  # 两个类别聚合


def test_viz_scatter_keeps_points():
    df = pd.DataFrame({"a": [1, 2, 3, 4], "b": [2, 4, 6, 8]})
    r = execute_viz_plan(df, {"chart_type": "scatter", "x": "a", "y": "b", "agg": "none"})
    assert r.chart is not None and len(r.evidence) == 4


def test_viz_bad_columns_fallback():
    r = execute_viz_plan(_df(), {"chart_type": "bar", "x": "ghost", "y": "ghost"})
    assert r.chart is not None  # 不抛异常
