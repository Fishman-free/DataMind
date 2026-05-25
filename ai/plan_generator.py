"""
智能分析计划生成器。
分析数据集 Schema 和洞察结果，自动生成结构化的分析任务清单。
AI 不可用时使用规则引擎降级生成基础计划。
"""
from __future__ import annotations

import json
import re
from typing import Any


class PlanGenerator:
    """分析计划生成器：AI + 规则降级。"""

    _SYSTEM_PROMPT = """你是一个数据分析专家。根据数据集信息和已有洞察，生成结构化的分析计划。

返回 JSON 数组格式（严格 JSON，不要 markdown 包裹）：
[
  {"id": 1, "title": "...", "category": "...", "description": "..."},
  ...
]

category 取：趋势、对比、分布、关联、异常、预测、质量、概览
最多生成 6 条计划，按分析价值排序。
"""

    def __init__(self, client: Any = None):
        self._client = client

    def generate(self, df_info: dict, insights: list[dict]) -> list[dict]:
        """
        生成分析计划清单。

        Args:
            df_info: 数据集摘要（含 columns 信息或 numeric_stats）
            insights: 已生成的洞察列表

        Returns:
            [{"id": int, "title": str, "category": str, "description": str}, ...]
        """
        if self._client is not None:
            try:
                plan = self._call_ai(df_info, insights)
                if plan:
                    return plan
            except Exception:
                pass

        # 降级：基于数据特征自动生成
        return self._fallback(df_info, insights)

    def _call_ai(self, df_info: dict, insights: list[dict]) -> list[dict] | None:
        """调用 AI 生成分析计划。"""
        import config as _cfg

        user_prompt = (
            f"数据集信息：\n{json.dumps(df_info, ensure_ascii=False, default=str)}\n\n"
            f"已有洞察：\n{json.dumps(insights[:5], ensure_ascii=False)}"
        )

        try:
            resp = self._client.chat.completions.create(
                model=_cfg.AI_MODEL,
                messages=[
                    {"role": "system", "content": self._SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                max_tokens=600,
            )
            content = resp.choices[0].message.content or ""
            return self._parse_json(content)
        except Exception:
            return None

    def _parse_json(self, text: str) -> list[dict] | None:
        """从 AI 响应中提取 JSON 数组。"""
        # 尝试直接解析
        try:
            result = json.loads(text.strip())
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            pass
        # 尝试提取 markdown 代码块中的 JSON
        match = re.search(r"```(?:json)?\s*\n(.*?)\n```", text, re.DOTALL)
        if match:
            try:
                result = json.loads(match.group(1))
                if isinstance(result, list):
                    return result
            except json.JSONDecodeError:
                pass
        # 尝试提取 [ ... ] 数组
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if match:
            try:
                result = json.loads(match.group(0))
                if isinstance(result, list):
                    return result
            except json.JSONDecodeError:
                pass
        return None

    def _fallback(self, df_info: dict, insights: list[dict]) -> list[dict]:
        """基于数据特征自动生成基础分析计划。

        支持两种 df_info 格式：
        1. 测试 mock 格式：{"columns": {"col": "dtype", ...}}
        2. 实际 summary_stats 格式：{"numeric_stats": {...}, "date_range": {...}, ...}
        """
        plan = []
        plan_id = 1

        # 统一提取列类型信息
        columns = df_info.get("columns") or {}
        if not columns:
            # 从实际 summary_stats 格式推导
            numeric_stats = df_info.get("numeric_stats") or {}
            missing_counts = df_info.get("missing_counts") or {}
            has_date_range = bool(df_info.get("date_range"))
            for col in numeric_stats:
                columns[col] = "float64"
            for col in missing_counts:
                if col not in columns:
                    columns[col] = "object"
            if has_date_range:
                columns["_date_col"] = "datetime64"

        # 检查数据类型
        has_date = any(
            "date" in str(t).lower() or "time" in str(t).lower()
            for t in columns.values()
        )
        num_cols = [
            c
            for c, t in columns.items()
            if any(x in str(t).lower() for x in ("int", "float", "number"))
        ]
        cat_cols = [
            c
            for c, t in columns.items()
            if "object" in str(t).lower()
            or "category" in str(t).lower()
            or "string" in str(t).lower()
        ]

        # 有日期列 → 趋势分析
        if has_date and num_cols:
            plan.append(
                {
                    "id": plan_id,
                    "title": f"{num_cols[0]} 随时间变化趋势",
                    "category": "趋势",
                    "description": f"分析 {num_cols[0]} 的时间序列趋势，识别周期性模式",
                }
            )
            plan_id += 1

        # 有多个数值列 → 相关性分析
        if len(num_cols) >= 2:
            plan.append(
                {
                    "id": plan_id,
                    "title": f"{num_cols[0]} 与 {num_cols[1]} 相关性分析",
                    "category": "关联",
                    "description": f"计算 {num_cols[0]} 与 {num_cols[1]} 之间的相关系数",
                }
            )
            plan_id += 1

        # 有分类列 → 分组对比
        if cat_cols and num_cols:
            plan.append(
                {
                    "id": plan_id,
                    "title": f"按 {cat_cols[0]} 分组对比 {num_cols[0]}",
                    "category": "对比",
                    "description": f"按 {cat_cols[0]} 维度对 {num_cols[0]} 进行分组统计分析",
                }
            )
            plan_id += 1

        # 有洞察 → 异常排查
        if insights:
            plan.append(
                {
                    "id": plan_id,
                    "title": "数据异常排查",
                    "category": "异常",
                    "description": "基于已发现的数据异常或离群点进行深入排查",
                }
            )
            plan_id += 1

        # 数值列统计分析
        if num_cols:
            plan.append(
                {
                    "id": plan_id,
                    "title": "数值指标分布分析",
                    "category": "分布",
                    "description": f"分析 {', '.join(num_cols[:3])} 等数值指标的分布情况",
                }
            )
            plan_id += 1

        # 如果还不够 3 条，补充概览
        if len(plan) < 3:
            plan.append(
                {
                    "id": plan_id,
                    "title": "数据集全貌概览",
                    "category": "概览",
                    "description": "对数据集进行全面的描述性统计分析",
                }
            )
            plan_id += 1

        return plan
