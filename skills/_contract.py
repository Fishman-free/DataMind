"""
技能层公共契约与工具。

提供：
  - SkillResult        统一返回结构（answer/evidence/chart/meta）
  - infer_schema       从 DataFrame 推断字段 schema（供路由器注入 LLM）
  - safe_col           计划列名安全校验/降级
  - safe_numeric_cols  计划数值列筛选/降级
  - fig_to_chart_dict  Plotly Figure → 前端可用 dict（复用 code_generator 的 bdata 解码）

来源：学生+AI
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd


@dataclass
class SkillResult:
    answer: str
    evidence: pd.DataFrame
    chart: dict | None = None
    meta: dict = field(default_factory=dict)


def infer_schema(df: pd.DataFrame) -> dict[str, str]:
    """推断字段类型，供路由 LLM 选择列。"""
    schema: dict[str, str] = {}
    for col in df.columns:
        if pd.api.types.is_numeric_dtype(df[col]):
            schema[str(col)] = "number"
        elif pd.api.types.is_datetime64_any_dtype(df[col]):
            schema[str(col)] = "date"
        else:
            sample = df[col].dropna().astype(str).head(5).tolist()
            schema[str(col)] = "category/text, examples=" + ",".join(sample)
    return schema


def safe_col(df: pd.DataFrame, value: Any, prefer_numeric: bool = False) -> str:
    """校验计划列名；非法时降级到第一个（数值）列。

    当 prefer_numeric=True 时，若指定列不存在或存在但非数值，均降级到首个数值列。
    """
    if value in df.columns:
        if not prefer_numeric or pd.api.types.is_numeric_dtype(df[value]):
            return str(value)
        # 存在但非数值，且调用方要求数值列 → 继续向下降级
    if prefer_numeric:
        nums = df.select_dtypes(include="number").columns
        if len(nums):
            return str(nums[0])
    return str(df.columns[0])


def safe_numeric_cols(df: pd.DataFrame, values: list | None, limit: int = 3) -> list[str]:
    """筛选计划中的有效数值列；空则取前 limit 个数值列。"""
    numeric = [str(c) for c in df.select_dtypes(include="number").columns]
    requested = [str(c) for c in (values or []) if c in df.columns and str(c) in numeric]
    return requested or numeric[:limit]


def fig_to_chart_dict(fig: Any) -> dict | None:
    """Plotly Figure → 前端可用 dict（复用 code_generator 的 bdata 解码 + 透明背景）。"""
    if fig is None:
        return None
    from ai.code_generator import _plotly_fig_to_dict
    chart = _plotly_fig_to_dict(fig)
    if isinstance(chart, dict) and isinstance(chart.get("layout"), dict):
        chart["layout"].pop("template", None)
        chart["layout"]["paper_bgcolor"] = "rgba(0,0,0,0)"
        chart["layout"]["plot_bgcolor"] = "rgba(0,0,0,0)"
    return chart
