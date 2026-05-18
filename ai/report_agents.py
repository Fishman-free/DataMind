"""
详细报告多 Agent 框架。

包含四个专注 Agent，各自承担报告的一个维度：
  - StatisticsAgent  : 数据特征统计描述
  - InsightAgent     : 关键洞察深度解读
  - QAAgent          : 对话问答摘要分析
  - SynthesisAgent   : 综合总结与建议

每个 Agent 都有降级方案（fallback），AI 调用失败时自动使用模板报告。

来源：学生+AI
"""
from __future__ import annotations

import json
from typing import Any


# ── 工具函数 ───────────────────────────────────────────────

def _extract_content(response: Any) -> str:
    """从 OpenAI 响应安全提取文本内容。"""
    try:
        return response.choices[0].message.content or ""
    except Exception:
        return ""


def _call_ai(client: Any, model: str, system: str, user: str,
             max_tokens: int = 1000) -> str:
    """
    调用 AI 并返回文本；失败时返回空字符串（调用方处理 fallback）。
    """
    if client is None:
        return ""
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user",   "content": user},
            ],
            temperature=0.3,
            max_tokens=max_tokens,
        )
        return _extract_content(resp)
    except Exception:
        return ""


# ── StatisticsAgent ───────────────────────────────────────

class StatisticsAgent:
    """
    数据特征统计描述 Agent。

    职责：将 summary_stats 转化为可读的数据概况章节，
    包含字段类型分布、数值范围、缺失率、时间跨度等。
    """

    SYSTEM = (
        "你是数据分析专家，专注于数据集统计特征描述。"
        "用简洁专业的中文将统计数据转化为结构清晰的 Markdown 章节，"
        "使用 ## 二级标题，数字保留 2 位小数，不使用 AI 口吻。"
    )

    def __init__(self, client: Any, model: str) -> None:
        self.client = client
        self.model = model

    def generate(self, df_info: dict[str, Any]) -> str:
        """生成数据特征统计章节。"""
        prompt = self._build_prompt(df_info)
        content = _call_ai(self.client, self.model, self.SYSTEM, prompt, max_tokens=800)
        if not content or content.lstrip().lower().startswith(("<!doctype", "<html")):
            return self._fallback(df_info)
        return content

    def _build_prompt(self, df_info: dict[str, Any]) -> str:
        rows    = df_info.get("row_count", "?")
        cols    = df_info.get("column_count", "?")
        dr      = df_info.get("date_range") or {}
        start   = dr.get("start", "未知")
        end     = dr.get("end", "未知")
        col_names = df_info.get("columns") or []
        num_cols  = df_info.get("numeric_cols") or []
        cat_cols  = [c for c in col_names if c not in num_cols]

        numeric_stats = ""
        if df_info.get("numeric_summary"):
            lines = []
            for col, stat in list(df_info["numeric_summary"].items())[:8]:
                mn  = stat.get("mean",   "?")
                std = stat.get("std",    "?")
                mn_v = stat.get("min",   "?")
                mx_v = stat.get("max",   "?")
                lines.append(f"  - {col}: 均值={mn:.2f}, 标准差={std:.2f}, 范围=[{mn_v:.2f}, {mx_v:.2f}]"
                              if all(isinstance(v, (int, float)) for v in [mn, std, mn_v, mx_v])
                              else f"  - {col}: 均值={mn}, 标准差={std}")
            numeric_stats = "\n".join(lines)

        return f"""请生成"数据特征描述"章节（## 开头），描述以下数据集的统计特征：

数据集规模：{rows} 行 × {cols} 列
时间跨度：{start} 至 {end}
数值字段（{len(num_cols)} 个）：{', '.join(str(c) for c in num_cols[:10])}
分类字段（{len(cat_cols)} 个）：{', '.join(str(c) for c in cat_cols[:10])}

数值字段统计摘要：
{numeric_stats or '（无数值摘要）'}

要求：3-5 段，每段 2-3 句，语言专业简洁，使用 Markdown 表格或列表增强可读性。"""

    def _fallback(self, df_info: dict[str, Any]) -> str:
        rows = df_info.get("row_count", "?")
        cols = df_info.get("column_count", "?")
        dr   = df_info.get("date_range") or {}
        start = dr.get("start", "")
        end   = dr.get("end", "")
        date_line = f"时间跨度 **{start}** 至 **{end}**，" if start and end else ""
        col_names = df_info.get("columns") or []
        col_line = "、".join(str(c) for c in col_names[:12]) + ("…" if len(col_names) > 12 else "")
        return f"""## 数据特征描述

本数据集共包含 **{rows}** 条记录，涵盖 **{cols}** 个字段。{date_line}
主要字段包括：{col_line}。

数据集结构完整，字段覆盖了业务所需的核心维度，可支撑销售趋势、客户行为等多维度分析。
"""


# ── InsightAgent ──────────────────────────────────────────

class InsightAgent:
    """
    关键洞察深度解读 Agent。

    职责：将 InsightEngine 自动检测的洞察列表深度展开，
    按重要性排序，结合业务背景解读每条洞察的含义与影响。
    """

    SYSTEM = (
        "你是业务数据分析专家，专注于从数据洞察中挖掘业务价值。"
        "用中文深度解读每条洞察的业务含义，语言专业但易于理解，"
        "避免重复罗列原始数值，聚焦于\"为什么重要\"和\"意味着什么\"。"
    )

    def __init__(self, client: Any, model: str) -> None:
        self.client = client
        self.model = model

    def generate(self, insights: list[dict[str, Any]]) -> str:
        """生成关键洞察深度解读章节。"""
        if not insights:
            return "## 关键洞察\n\n当前数据集未发现显著异常洞察。\n"
        prompt = self._build_prompt(insights)
        content = _call_ai(self.client, self.model, self.SYSTEM, prompt, max_tokens=1000)
        if not content or content.lstrip().lower().startswith(("<!doctype", "<html")):
            return self._fallback(insights)
        return content

    def _build_prompt(self, insights: list[dict[str, Any]]) -> str:
        lines = []
        for item in insights:
            sev    = item.get("severity", "info").upper()
            title  = item.get("title",  "未知洞察")
            detail = item.get("detail", "")
            lines.append(f"[{sev}] {title}：{detail}")
        insight_text = "\n".join(lines)

        return f"""请生成"关键洞察"章节（## 开头），深度解读以下自动检测到的数据洞察：

{insight_text}

要求：
1. 按严重程度（HIGH/MEDIUM/LOW）分组展示
2. 每条洞察用 2-3 句话解读其业务含义和影响
3. 使用 ### 三级标题区分严重程度组
4. 语言专业，关注业务影响而非纯数字描述"""

    def _fallback(self, insights: list[dict[str, Any]]) -> str:
        lines = []
        for item in insights:
            sev   = item.get("severity", "info").upper()
            title = item.get("title",  "")
            det   = item.get("detail", "")
            lines.append(f"- **[{sev}]** {title}：{det}")
        body = "\n".join(lines) if lines else "- 未发现显著异常"
        return f"## 关键洞察\n\n{body}\n"


# ── QAAgent ───────────────────────────────────────────────

class QAAgent:
    """
    对话问答摘要分析 Agent。

    职责：提取用户与 AI 对话中的核心问题和关键发现，
    形成"分析过程"章节，反映用户关注点和探索路径。
    """

    SYSTEM = (
        "你是对话分析专家，专注于从用户与 AI 的对话历史中提炼核心关注点。"
        "用中文总结用户提出的核心问题、AI 给出的关键发现，"
        "以叙事性文字（而非逐条列举）呈现整个分析探索过程。"
    )

    def __init__(self, client: Any, model: str) -> None:
        self.client = client
        self.model = model

    def generate(self, chat_history: list[dict[str, str]]) -> str:
        """生成对话分析摘要章节。"""
        user_msgs = [m["content"] for m in chat_history if m.get("role") == "user"]
        if not user_msgs:
            return "## 对话分析摘要\n\n本次分析未进行交互式问答探索。\n"
        prompt = self._build_prompt(chat_history, user_msgs)
        content = _call_ai(self.client, self.model, self.SYSTEM, prompt, max_tokens=700)
        if not content or content.lstrip().lower().startswith(("<!doctype", "<html")):
            return self._fallback(user_msgs)
        return content

    def _build_prompt(self, history: list[dict[str, str]],
                      user_msgs: list[str]) -> str:
        # 仅取前 10 轮对话，避免超 token
        pairs: list[str] = []
        i = 0
        for msg in history[:20]:
            role    = msg.get("role", "")
            content = msg.get("content", "")[:200]  # 截断超长内容
            if role == "user":
                pairs.append(f"用户问：{content}")
            elif role == "assistant":
                pairs.append(f"AI 答：{content}")
            i += 1
            if i >= 20:
                break
        dialog = "\n".join(pairs)

        return f"""请生成"对话分析摘要"章节（## 开头），总结以下用户与 AI 的分析对话：

{dialog}

要求：
1. 用叙事性文字（1-3 段）而非逐条列举
2. 提炼用户的核心关注点和分析思路
3. 总结 AI 发现的关键规律或答案
4. 语言流畅，体现数据探索的连贯性"""

    def _fallback(self, user_msgs: list[str]) -> str:
        q_lines = "\n".join(f"- {q}" for q in user_msgs[:8])
        return f"""## 对话分析摘要

本次分析中，用户围绕数据集提出了以下核心问题：

{q_lines}

通过交互式问答，分析逐步深入，帮助用户从多维度理解数据规律。
"""


# ── SynthesisAgent ────────────────────────────────────────

class SynthesisAgent:
    """
    综合总结与建议 Agent。

    职责：综合前三个 Agent 的输出，生成执行摘要和行动建议，
    是报告的最终输出部分。
    """

    SYSTEM = (
        "你是高级数据顾问，专注于将数据分析结论转化为可执行建议。"
        "用中文生成报告的总结与建议章节，语言简洁有力，"
        "每条建议明确说明\"做什么\"和\"预期效果\"，避免空洞的表述。"
    )

    def __init__(self, client: Any, model: str) -> None:
        self.client = client
        self.model = model

    def generate(
        self,
        stats_section: str,
        insight_section: str,
        qa_section: str,
        df_info: dict[str, Any],
    ) -> str:
        """生成综合总结与建议章节。"""
        prompt = self._build_prompt(stats_section, insight_section, qa_section, df_info)
        content = _call_ai(self.client, self.model, self.SYSTEM, prompt, max_tokens=800)
        if not content or content.lstrip().lower().startswith(("<!doctype", "<html")):
            return self._fallback(df_info)
        return content

    def _build_prompt(
        self,
        stats: str,
        insight: str,
        qa: str,
        df_info: dict[str, Any],
    ) -> str:
        rows = df_info.get("row_count", "?")
        return f"""请生成"总结与建议"章节（## 开头），综合以下三个分析模块的结论：

=== 数据特征描述摘要 ===
{stats[:500]}

=== 关键洞察摘要 ===
{insight[:500]}

=== 对话分析摘要 ===
{qa[:300]}

数据集规模：{rows} 条记录

要求：
1. 执行摘要（2-3 句话，点出最重要的 1-2 个发现）
2. 3-5 条具体可执行的业务建议（使用编号列表）
3. 每条建议格式：**[行动]**：[预期效果]
4. 语言简洁有力，避免重复前面章节的内容"""

    def _fallback(self, df_info: dict[str, Any]) -> str:
        rows = df_info.get("row_count", "?")
        return f"""## 总结与建议

本次分析共处理 **{rows}** 条记录，自动扫描了数据质量、分布特征与业务洞察。

**建议行动：**

1. **关注高严重度洞察**：优先处理标记为 HIGH 的异常，排查业务根因。
2. **深化时序分析**：利用时间维度特征，识别季节性规律与趋势拐点。
3. **客户分层运营**：结合 RFM 分析结果，制定差异化客户运营策略。
4. **数据质量持续监控**：建立数据质量检查机制，定期扫描缺失率和异常值。
5. **扩展分析维度**：引入更多业务维度数据，提升预测模型的准确性。
"""
