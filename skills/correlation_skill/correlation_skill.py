"""相关性分析技能：数值列相关矩阵 + 热力图。来源：学生+AI"""
from __future__ import annotations

import pandas as pd
import plotly.express as px

from skills._contract import SkillResult, safe_numeric_cols, fig_to_chart_dict


def execute_correlation_plan(df: pd.DataFrame, plan: dict, context: dict | None = None) -> SkillResult:
    method = str(plan.get("method", "pearson")).lower()
    if method not in ("pearson", "spearman", "kendall"):
        method = "pearson"
    columns = safe_numeric_cols(df, plan.get("columns"), limit=8)
    title = str(plan.get("title") or "相关性热力图")

    if len(columns) < 2:
        evidence = pd.DataFrame({"message": ["可用数值列不足 2 个，无法计算相关性。"]})
        return SkillResult(answer="可用数值列不足 2 个，无法计算相关性。",
                           evidence=evidence, chart=None, meta={"title": title})

    work = df[columns].apply(pd.to_numeric, errors="coerce")
    corr = work.corr(method=method).round(4)
    evidence = corr.reset_index().rename(columns={"index": "column"})
    fig = px.imshow(corr, text_auto=True, aspect="auto", title=title,
                    color_continuous_scale="RdBu_r", zmin=-1, zmax=1)
    chart = fig_to_chart_dict(fig)
    return SkillResult(answer=f"已用 {method} 方法计算 {len(columns)} 个数值列的相关性矩阵。",
                       evidence=evidence, chart=chart, meta={"title": title})
