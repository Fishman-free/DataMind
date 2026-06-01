import pandas as pd
from skills.trend_skill.trend_skill import execute_trend_plan


def _df():
    dates = pd.date_range("2024-01-01", periods=60, freq="D")
    return pd.DataFrame({"day": dates, "amt": range(60)})


def test_trend_monthly_resample():
    r = execute_trend_plan(_df(), {"date_col": "day", "value_col": "amt", "agg": "sum", "freq": "M"})
    assert r.chart is not None
    assert len(r.evidence) >= 2  # 跨 2-3 个月


def test_trend_no_valid_data_safe():
    df = pd.DataFrame({"x": ["a", "b"], "y": ["p", "q"]})
    r = execute_trend_plan(df, {"date_col": "x", "value_col": "y"})
    assert r.chart is None and "message" in r.evidence.columns
