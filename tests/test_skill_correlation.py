import pandas as pd
from skills.correlation_skill.correlation_skill import execute_correlation_plan


def _df():
    return pd.DataFrame({"a": [1, 2, 3, 4], "b": [2, 4, 6, 8], "c": [9, 7, 5, 3]})


def test_correlation_matrix_and_chart():
    r = execute_correlation_plan(_df(), {"columns": ["a", "b", "c"], "method": "pearson"})
    assert r.chart is not None and "column" in r.evidence.columns
    # a 与 b 完全正相关
    arow = r.evidence.set_index("column").loc["a"]
    assert abs(float(arow["b"]) - 1.0) < 1e-6


def test_correlation_insufficient_numeric_safe():
    df = pd.DataFrame({"only": [1, 2, 3], "txt": ["x", "y", "z"]})
    r = execute_correlation_plan(df, {"columns": ["only"]})
    assert r.chart is None and "message" in r.evidence.columns
