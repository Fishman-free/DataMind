import pandas as pd
import plotly.express as px
from skills._contract import (
    SkillResult, infer_schema, safe_col, safe_numeric_cols, fig_to_chart_dict,
)


def _df():
    return pd.DataFrame({"cat": ["A", "B", "A"], "val": [1, 2, 3], "price": [1.0, 2.5, 3.0]})


def test_infer_schema_types():
    schema = infer_schema(_df())
    assert schema["val"] == "number"
    assert schema["cat"].startswith("category/text")


def test_safe_col_falls_back_on_bad_name():
    assert safe_col(_df(), "missing", prefer_numeric=True) in ("val", "price")
    assert safe_col(_df(), "cat") == "cat"


def test_safe_col_downgrades_existing_non_numeric_when_numeric_required():
    # cat 存在但非数值，prefer_numeric=True 时应降级到数值列
    assert safe_col(_df(), "cat", prefer_numeric=True) in ("val", "price")
    # 但 prefer_numeric=False 时仍原样返回
    assert safe_col(_df(), "cat", prefer_numeric=False) == "cat"


def test_safe_numeric_cols_filters_and_defaults():
    assert safe_numeric_cols(_df(), ["val", "cat", "ghost"]) == ["val"]
    assert safe_numeric_cols(_df(), None) == ["val", "price"]


def test_fig_to_chart_dict_decodes_to_plain_json():
    fig = px.bar(_df(), x="cat", y="val")
    chart = fig_to_chart_dict(fig)
    assert isinstance(chart, dict) and "data" in chart and "layout" in chart
    assert "template" not in chart["layout"]
    assert chart["layout"]["paper_bgcolor"] == "rgba(0,0,0,0)"


def test_skill_result_defaults():
    r = SkillResult(answer="x", evidence=_df())
    assert r.chart is None and r.meta == {}
