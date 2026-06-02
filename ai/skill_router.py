"""
技能路由器：LLM 选择技能 + 生成 JSON 计划 + 基于证据二次解释。

第 1 次调用：route() 注入所有 SKILL.md，返回 {skill, plan, reason}。
第 2 次调用：explain_stream() 基于确定性脚本算出的证据表流式生成中文解释。

来源：学生+AI
"""
from __future__ import annotations

import json
import re
from typing import Any

import pandas as pd

from skills import SKILLS, load_catalog
from skills._contract import infer_schema


def _extract_json(text: str) -> dict | None:
    """从 LLM 回复中提取 JSON 对象（容错：裸 JSON / ```json``` / 文本夹带）。"""
    if not text:
        return None
    try:
        obj = json.loads(text.strip())
        if isinstance(obj, dict):
            return obj
    except (json.JSONDecodeError, AttributeError):
        pass
    m = re.search(r"```(?:json)?\s*\n(.*?)\n```", text, re.DOTALL)
    if m:
        try:
            obj = json.loads(m.group(1))
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            obj = json.loads(m.group(0))
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass
    return None


class SkillRouter:
    def __init__(self, client: Any, model: str) -> None:
        self.client = client
        self.model = model

    def _options(self) -> str:
        return " | ".join([*SKILLS.keys(), "fallback"])

    def route(self, question: str, df: pd.DataFrame) -> dict:
        """第 1 次 LLM 调用：选择技能并生成 JSON 计划。失败时返回 fallback。"""
        schema = infer_schema(df)
        sample = df.head(5).to_dict(orient="records")
        system = (
            "你是数据分析 skill 路由器。根据用户问题从本地 skills 中选择最合适的一个，"
            "并为该 skill 输出可执行 JSON 计划；没有任何 skill 适合时选择 fallback。"
            "不要写 Python 代码，不要输出 Markdown，只返回 JSON。\n\n"
            "返回格式：\n"
            f'{{"skill": "{self._options()}", "plan": {{...}}, "reason": "简短中文理由"}}'
            "\n\n可用 skills:\n\n" + load_catalog()
        )
        user = (
            f"字段 schema:\n{json.dumps(schema, ensure_ascii=False)}\n\n"
            f"数据样例:\n{json.dumps(sample, ensure_ascii=False, default=str)}\n\n"
            f"用户问题: {question}"
        )
        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "system", "content": system},
                          {"role": "user", "content": user}],
                temperature=0.1,
                max_tokens=600,
            )
            content = resp.choices[0].message.content or ""
            route = _extract_json(content)
        except Exception:
            route = None
        if not route or "skill" not in route:
            return {"skill": "fallback", "plan": {}, "reason": "路由失败，转代码生成兜底"}
        route.setdefault("plan", {})
        route.setdefault("reason", "")
        return route

    def explain_stream(self, question: str, skill_title: str,
                       evidence: pd.DataFrame, answer_hint: str):
        """第 2 次 LLM 调用：基于证据表流式生成中文解释（逐 token yield）。"""
        try:
            evidence_text = evidence.head(30).to_string(index=False)
        except Exception:
            evidence_text = str(evidence)
        system = (
            "你是数据分析助教。下面是确定性脚本基于真实数据算出的证据表。"
            "请用简洁中文解读结论，只依据证据表、不要编造数据、不要写代码。"
        )
        user = (
            f"用户问题：{question}\n使用的分析：{skill_title}\n"
            f"脚本结论：{answer_hint}\n证据表：\n{evidence_text}"
        )
        stream = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}],
            temperature=0.3, max_tokens=800, stream=True,
        )
        for chunk in stream:
            try:
                delta = chunk.choices[0].delta
                if delta and getattr(delta, "content", None):
                    yield delta.content
            except (AttributeError, IndexError):
                continue
