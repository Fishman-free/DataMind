"""
数据叙事引擎。
将结构化分析报告转化为有起承转合的数据故事，而非信息罗列。
参考数据新闻风格：生动的标题 + 自然段落 + 关键数字高亮。
"""
from __future__ import annotations

import json
import re
from typing import Any


class Storyteller:
    """数据叙事引擎：AI 生成 + 规则降级。"""

    _SYSTEM_PROMPT = """你是一个资深数据记者。将数据分析结果转化为引人入胜的数据故事。

返回严格 JSON 格式（不要 markdown 包裹）：
{
  "title": "故事大标题（吸引人但准确）",
  "subtitle": "一句话摘要",
  "sections": [
    {
      "heading": "章节标题",
      "body": "叙事段落（2-4句，自然流畅）",
      "highlight": "关键数字（可选，如 Q4增长45%）"
    }
  ],
  "key_takeaways": ["核心结论1", "核心结论2", "核心结论3"]
}

风格要求：
- 标题生动有吸引力（参考数据新闻标题）
- 段落自然流畅，像在讲故事而非罗列数据
- 关键数字用 highlight 突出显示
- key_takeaways 是 3-5 条可执行的建议或结论
- section 数量 3-5 个
- 全部使用中文
"""

    def __init__(self, client: Any = None):
        self._client = client

    def tell(self, df_info: dict, insights: list[dict],
             chat_history: list[dict] | None = None,
             report_content: str = "") -> dict:
        """
        生成数据故事。

        Args:
            df_info: 数据集摘要
            insights: 洞察列表
            chat_history: 对话历史
            report_content: 已有报告内容（Markdown）

        Returns:
            {"title": str, "subtitle": str, "sections": [...], "key_takeaways": [...]}
        """
        if self._client is not None:
            try:
                story = self._call_ai(df_info, insights, chat_history, report_content)
                if story:
                    return story
            except Exception:
                pass

        return self._fallback(df_info, insights, report_content)

    def _call_ai(self, df_info: dict, insights: list[dict],
                 chat_history: list[dict] | None, report_content: str) -> dict | None:
        """调用 AI 生成数据故事。"""
        import config as _cfg

        # 构建上下文
        parts = [f"数据集信息：\n{json.dumps(df_info, ensure_ascii=False, default=str)[:1000]}"]
        if insights:
            parts.append(f"关键洞察：\n{json.dumps(insights[:5], ensure_ascii=False)[:800]}")
        if chat_history:
            qa_text = "\n".join(
                f"Q: {m.get('content', '')}" if m.get("role") == "user"
                else f"A: {m.get('content', '')}"
                for m in chat_history[-6:]
            )
            parts.append(f"用户对话：\n{qa_text[:500]}")
        if report_content:
            parts.append(f"分析报告：\n{report_content[:1500]}")

        user_prompt = "\n\n".join(parts)

        try:
            resp = self._client.chat.completions.create(
                model=_cfg.AI_MODEL,
                messages=[
                    {"role": "system", "content": self._SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.6,
                max_tokens=1000,
            )
            content = resp.choices[0].message.content or ""
            return self._parse_json(content)
        except Exception:
            return None

    def _parse_json(self, text: str) -> dict | None:
        """从 AI 响应中提取 JSON 对象。"""
        for attempt in [
            lambda t: json.loads(t.strip()),
            lambda t: json.loads(re.search(r"```(?:json)?\s*\n(.*?)\n```", t, re.DOTALL).group(1)),
            lambda t: json.loads(re.search(r"\{.*\}", t, re.DOTALL).group(0)),
        ]:
            try:
                result = attempt(text)
                if isinstance(result, dict) and "title" in result:
                    return result
            except (json.JSONDecodeError, AttributeError):
                continue
        return None

    def _fallback(self, df_info: dict, insights: list[dict],
                  report_content: str = "") -> dict:
        """基于数据特征生成基础叙事。"""
        row_count = df_info.get("row_count", 0)
        col_count = df_info.get("column_count", 0)

        # 从洞察中提取关键信息
        insight_texts = [i.get("description", "") for i in (insights or [])[:3]]
        high_insights = [i for i in (insights or []) if i.get("severity") == "high"]

        title = f"数据分析报告：{col_count} 个维度 x {row_count} 条记录"
        subtitle = f"涵盖 {row_count} 条数据记录的全面分析"

        sections = [
            {
                "heading": "数据集概览",
                "body": f"本次分析基于包含 {row_count} 条记录、{col_count} 个维度的数据集。"
                       f"通过对数据的多维度探索，我们发现了若干有价值的模式和洞察。",
                "highlight": f"{row_count} 条记录",
            },
        ]

        if insight_texts:
            sections.append({
                "heading": "关键发现",
                "body": "、".join(insight_texts) + "。这些发现揭示了数据中隐藏的规律和趋势。",
                "highlight": insight_texts[0][:30] if insight_texts[0] else "",
            })

        if report_content:
            # 从报告中提取第一个 ## 标题作为额外章节
            headings = re.findall(r"##\s+(.+)\n", report_content)
            if headings:
                sections.append({
                    "heading": headings[0],
                    "body": f"报告中详细分析了 {headings[0]} 的相关内容，"
                            f"为决策提供了数据支撑。",
                    "highlight": "",
                })

        key_takeaways = []
        if high_insights:
            key_takeaways.append(high_insights[0].get("description", "关注高优先级洞察"))
        if row_count > 100:
            key_takeaways.append(f"建议对 {row_count} 条记录建立定期监控")
        key_takeaways.append("基于数据发现制定下一步行动计划")

        return {
            "title": title,
            "subtitle": subtitle,
            "sections": sections,
            "key_takeaways": key_takeaways[:5],
        }
