import pandas as pd
from skills.distribution_skill.distribution_skill import execute_distribution_plan


def _df():
    return pd.DataFrame({"score": [1, 2, 2, 3, 3, 3, 4, 4, 5], "label": list("abcabcabc")})


def test_distribution_hist():
    r = execute_distribution_plan(_df(), {"column": "score", "kind": "hist", "bins": 5})
    assert r.chart is not None and "统计量" in r.evidence.columns


def test_distribution_box():
    r = execute_distribution_plan(_df(), {"column": "score", "kind": "box"})
    assert r.chart is not None


def test_distribution_non_numeric_safe():
    r = execute_distribution_plan(_df(), {"column": "label"})
    # label 被降级为数值列 score（safe_col prefer_numeric），仍应产出
    assert r.chart is not None
