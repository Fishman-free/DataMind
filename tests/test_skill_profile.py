import pandas as pd
from skills.profile_skill.profile_skill import execute_profile_plan


def _df():
    return pd.DataFrame({"cat": ["A", "B", "A"], "val": [1, 2, 3]})


def test_profile_overview():
    r = execute_profile_plan(_df(), {"scope": "overview"})
    assert "项目" in r.evidence.columns and len(r.evidence) >= 4


def test_profile_schema():
    r = execute_profile_plan(_df(), {"scope": "schema"})
    assert "列名" in r.evidence.columns and len(r.evidence) == 2


def test_profile_quality_uses_context():
    ctx = {"quality_score": {"total_score": 88, "grade": "B",
            "dimensions": {"completeness": {"score": 90, "detail": "无缺失"}},
            "suggestions": ["保持"]}}
    r = execute_profile_plan(_df(), {"scope": "quality"}, ctx)
    assert "维度" in r.evidence.columns and "88" in r.answer
