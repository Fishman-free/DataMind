"""
分析报告生成器。

调用 OpenAI 将结构化分析数据润色为连贯的 Markdown 报告。
数据真实性由代码保证，GPT 只负责"讲故事"。

报告结构：
  数据概览 → 预处理摘要 → 关键洞察 → 对话分析记录 → 总结与建议

来源：学生+AI
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

import markdown


class ReportGenerator:
    """
    分析报告生成器。

    用法
    ----
    rg = ReportGenerator(openai_client)
    report = rg.generate(df_info, insights, chat_history)
    html   = rg.to_html(report)
    """

    def __init__(self, client: Any) -> None:
        """
        Parameters
        ----------
        client : OpenAI() 实例（或 Mock）
        """
        self.client = client

    # ── 生成报告 ───────────────────────────────────────

    def generate(
        self,
        df_info: dict[str, Any],
        insights: list[dict[str, Any]],
        chat_history: list[dict[str, str]],
    ) -> dict[str, Any]:
        """
        生成 Markdown 分析报告。

        Parameters
        ----------
        df_info      : summary_stats() 返回的数据集摘要
        insights     : InsightEngine.generate_all() 返回的洞察列表
        chat_history : 对话历史（可选，用于报告中的"分析过程"章节）

        Returns
        -------
        {"title": str, "content": str, "generated_at": str}
        """
        prompt = self._build_report_prompt(df_info, insights, chat_history)

        import config as _cfg
        from ai.code_generator import _extract_content
        try:
            response = self.client.chat.completions.create(
                model=_cfg.AI_MODEL,
                messages=[
                    {"role": "system", "content": "你是专业数据分析师，将提供的分析结果整理为结构清晰的 Markdown 报告，语言简洁专业。"},
                    {"role": "user",   "content": prompt},
                ],
                temperature=0.3,
                max_tokens=2000,
            )
            # 防御性解析；内容为空或为 HTML（接口配置错误）时走降级模板
            raw = _extract_content(response)
            is_html = raw.lstrip().lower().startswith(("<!doctype", "<html"))
            content = (raw if raw and not is_html
                       else self._fallback_report(df_info, insights))
        except Exception as exc:
            # 降级：用结构化数据生成基础报告，不依赖 GPT
            content = self._fallback_report(df_info, insights)

        return {
            "title":        "DataMind 数据分析报告",
            "content":      content,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    # ── Markdown → HTML ────────────────────────────────

    def to_html(self, report: dict[str, Any]) -> str:
        """
        将报告 content（Markdown）转为 HTML 字符串。

        Parameters
        ----------
        report : generate() 返回的报告字典

        Returns
        -------
        HTML 字符串（含 <h1>...<p> 等标签）
        """
        md_content = report.get("content", "")
        return markdown.markdown(
            md_content,
            extensions=["tables", "fenced_code", "nl2br"],
        )

    # ── 内部方法 ───────────────────────────────────────

    def _build_report_prompt(
        self,
        df_info: dict[str, Any],
        insights: list[dict[str, Any]],
        chat_history: list[dict[str, str]],
    ) -> str:
        """构建报告生成提示词。"""
        rows   = df_info.get("row_count", "?")
        cols   = df_info.get("column_count", "?")
        dr     = df_info.get("date_range") or {}
        start  = dr.get("start", "未知")
        end    = dr.get("end", "未知")

        # 洞察摘要
        insight_lines = "\n".join(
            f"- [{item['severity'].upper()}] {item['title']}：{item['detail']}"
            for item in insights
        ) or "（未发现显著洞察）"

        # 对话摘要（只取用户问题）
        chat_lines = "\n".join(
            f"- {msg['content']}"
            for msg in chat_history
            if msg.get("role") == "user"
        ) or "（本次未进行对话分析）"

        return f"""请根据以下数据分析结果，生成一份专业的 Markdown 分析报告。

【数据集概况】
- 记录总数：{rows}
- 字段数：{cols}
- 时间跨度：{start} 至 {end}

【自动检测洞察】
{insight_lines}

【对话分析记录】
{chat_lines}

报告要求：
1. 包含 # 一级标题
2. 使用 ## 分节：数据概览 / 关键发现 / 对话摘要 / 总结建议
3. 每节 2-4 句话，数据准确，语言简洁
4. 全中文"""

    def _fallback_report(
        self,
        df_info: dict[str, Any],
        insights: list[dict[str, Any]],
    ) -> str:
        """GPT 调用失败时的降级报告（纯模板）。"""
        rows = df_info.get("row_count", "?")
        cols = df_info.get("column_count", "?")

        # 时间范围
        dr    = df_info.get("date_range") or {}
        start = dr.get("start", "")
        end   = dr.get("end", "")
        date_line = f"时间跨度 **{start}** 至 **{end}**，" if start and end else ""

        # 列名列表
        col_names = df_info.get("columns") or []
        col_line = (
            "数据集字段：" + "、".join(str(c) for c in col_names[:12])
            + ("…" if len(col_names) > 12 else "")
        ) if col_names else ""

        # 洞察
        insight_section = "\n".join(
            f"- **[{i['severity'].upper()}]** {i['title']}：{i['detail']}"
            for i in insights
        ) or "- 未发现显著异常"

        return f"""# DataMind 数据分析报告

## 数据概览

本次分析共处理 **{rows}** 条记录，涉及 **{cols}** 个字段。{date_line}{col_line}

## 关键发现

{insight_section}

## 总结与建议

以上为本次数据自动扫描结果，建议结合业务背景对关键洞察做深入分析。
"""
