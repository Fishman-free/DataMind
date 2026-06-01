"""统计分析技能：描述统计 + 分组聚合。来源：学生+AI"""
from __future__ import annotations

import pandas as pd

from skills._contract import SkillResult, safe_numeric_cols

_SUPPORTED = {"mean", "median", "variance", "std", "min", "max", "count"}
_PANDAS_AGG = {"mean": "mean", "median": "median", "variance": "var",
               "std": "std", "min": "min", "max": "max", "count": "count"}
_INV = {v: k for k, v in _PANDAS_AGG.items()}


def _norm_metrics(values: list | None) -> list[str]:
    metrics = [str(m).lower() for m in (values or [])]
    metrics = [m for m in metrics if m in _SUPPORTED]
    return metrics or ["mean", "median", "variance"]


def execute_stats_plan(df: pd.DataFrame, plan: dict, context: dict | None = None) -> SkillResult:
    metrics = _norm_metrics(plan.get("metrics"))
    columns = safe_numeric_cols(df, plan.get("columns"))
    group_by = plan.get("group_by")
    if group_by not in df.columns:
        group_by = None
    title = str(plan.get("title") or "描述统计")

    work = df.copy()
    for c in columns:
        work[c] = pd.to_numeric(work[c], errors="coerce")
    aggs = [_PANDAS_AGG[m] for m in metrics]

    if group_by:
        grouped = work.groupby(group_by, dropna=False)[columns].agg(aggs)
        grouped.columns = [f"{c}_{_INV.get(a, a)}" for c, a in grouped.columns]
        evidence = grouped.reset_index().head(50)
        answer = f"已按 {group_by} 分组计算 {', '.join(columns)} 的 {', '.join(metrics)}。"
    else:
        evidence = work[columns].agg(aggs).T.reset_index()
        evidence = evidence.rename(columns={"index": "column", "var": "variance"})
        evidence = evidence.fillna("").head(50)
        answer = f"已计算 {', '.join(columns)} 的 {', '.join(metrics)}。"
    return SkillResult(answer=answer, evidence=evidence, chart=None, meta={"title": title})
