import json
from unittest.mock import MagicMock

import pandas as pd

from ai.skill_router import SkillRouter, _extract_json


def _df():
    return pd.DataFrame({"region": ["A", "B"], "sales": [10, 20]})


def _client_returning(content: str):
    client = MagicMock()
    resp = MagicMock()
    resp.choices = [MagicMock()]
    resp.choices[0].message.content = content
    client.chat.completions.create.return_value = resp
    return client


def test_extract_json_variants():
    assert _extract_json('{"skill":"stats-skill"}')["skill"] == "stats-skill"
    assert _extract_json('```json\n{"skill":"viz-skill"}\n```')["skill"] == "viz-skill"
    assert _extract_json("noise {\"skill\":\"x\"} tail")["skill"] == "x"


def test_route_selects_known_skill():
    content = json.dumps({"skill": "stats-skill", "plan": {"metrics": ["mean"]}, "reason": "求均值"})
    router = SkillRouter(_client_returning(content), "gpt-4o-mini")
    route = router.route("销售额均值", _df())
    assert route["skill"] == "stats-skill" and route["plan"]["metrics"] == ["mean"]


def test_route_falls_back_on_bad_json():
    router = SkillRouter(_client_returning("抱歉我无法回答"), "gpt-4o-mini")
    route = router.route("天气如何", _df())
    assert route["skill"] == "fallback"


def test_route_falls_back_on_api_error():
    client = MagicMock()
    client.chat.completions.create.side_effect = Exception("timeout")
    router = SkillRouter(client, "gpt-4o-mini")
    assert router.route("x", _df())["skill"] == "fallback"


def test_explain_stream_yields_tokens():
    client = MagicMock()
    chunks = []
    for tok in ["销售", "额", "最高"]:
        ck = MagicMock(); ck.choices = [MagicMock()]; ck.choices[0].delta.content = tok
        chunks.append(ck)
    client.chat.completions.create.return_value = chunks
    router = SkillRouter(client, "gpt-4o-mini")
    out = "".join(router.explain_stream("q", "统计分析", _df(), "提示"))
    assert out == "销售额最高"
