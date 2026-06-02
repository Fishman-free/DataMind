"""分布分析技能：直方图 / 箱线图。来源：学生+AI"""
from __future__ import annotations

import pandas as pd
import plotly.express as px

from skills._contract import SkillResult, safe_col, fig_to_chart_dict


def execute_distribution_plan(df: pd.DataFrame, plan: dict, context: dict | None = None) -> SkillResult:
    column = safe_col(df, plan.get("column"), prefer_numeric=True)
    kind = str(plan.get("kind", "hist")).lower()
    try:
        bins = int(plan.get("bins") or 30)
    except (TypeError, ValueError):
        bins = 30
    title = str(plan.get("title") or f"{column} 分布")

    series = pd.to_numeric(df[column], errors="coerce").dropna()
    if series.empty:
        evidence = pd.DataFrame({"message": [f"{column} 无有效数值，无法分析分布。"]})
        return SkillResult(answer=f"{column} 列无有效数值数据。",
                           evidence=evidence, chart=None, meta={"title": title})

    evidence = series.describe().round(4).reset_index()
    evidence.columns = ["统计量", column]
    plot_df = series.rename(column).to_frame()
    if kind == "box":
        fig = px.box(plot_df, y=column, title=title)
    else:
        fig = px.histogram(plot_df, x=column, nbins=bins, title=title)
    chart = fig_to_chart_dict(fig)
    kind_cn = "箱线图" if kind == "box" else "直方图"
    return SkillResult(answer=f"已生成 {column} 的{kind_cn}分布。",
                       evidence=evidence, chart=chart, meta={"title": title, "x_label": column})
