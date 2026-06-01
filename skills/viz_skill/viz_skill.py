"""数据可视化技能：按字段类型生成柱/折/散/饼图。来源：学生+AI"""
from __future__ import annotations

import pandas as pd
import plotly.express as px

from skills._contract import SkillResult, safe_col, fig_to_chart_dict


def execute_viz_plan(df: pd.DataFrame, plan: dict, context: dict | None = None) -> SkillResult:
    chart_type = str(plan.get("chart_type", "bar")).lower()
    x = safe_col(df, plan.get("x"))
    y = safe_col(df, plan.get("y"), prefer_numeric=True)
    agg = str(plan.get("agg", "sum")).lower()
    title = str(plan.get("title") or f"{y} by {x}")

    cols = [x] if x == y else [x, y]
    work = df[cols].dropna().copy()

    if chart_type == "scatter":
        work[x] = pd.to_numeric(work[x], errors="coerce")
        work[y] = pd.to_numeric(work[y], errors="coerce")
        evidence = work.dropna().head(500)
        fig = px.scatter(evidence, x=x, y=y, title=title, opacity=0.7,
                         color_discrete_sequence=["#00e5ff"])
    elif chart_type == "pie":
        work[y] = pd.to_numeric(work[y], errors="coerce")
        evidence = (work.groupby(x, dropna=False)[y].sum().reset_index()
                    .sort_values(y, ascending=False).head(20))
        fig = px.pie(evidence, names=x, values=y, title=title)
    else:
        work[y] = pd.to_numeric(work[y], errors="coerce")
        if agg == "mean":
            evidence = work.groupby(x, dropna=False)[y].mean().reset_index()
        elif agg == "count":
            evidence = work.groupby(x, dropna=False)[y].count().reset_index()
        else:
            evidence = work.groupby(x, dropna=False)[y].sum().reset_index()
        evidence = evidence.sort_values(y, ascending=False).head(20)
        if chart_type == "line":
            evidence = evidence.sort_values(x)
            fig = px.line(evidence, x=x, y=y, title=title, markers=True)
        else:
            fig = px.bar(evidence, x=x, y=y, title=title)

    chart = fig_to_chart_dict(fig)
    return SkillResult(answer=f"已生成 {title}。", evidence=evidence, chart=chart,
                       meta={"title": title, "x_label": x, "y_label": y})
