"""趋势分析技能：时间序列重采样趋势。来源：学生+AI"""
from __future__ import annotations

import pandas as pd
import plotly.express as px

from skills._contract import SkillResult, safe_col, fig_to_chart_dict

_FREQ_MAP = {"D": "D", "W": "W", "M": "ME", "Q": "QE", "Y": "YE"}


def _pick_date_col(df: pd.DataFrame, value) -> str:
    if value in df.columns:
        return str(value)
    for c in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[c]):
            return str(c)
    for c in df.columns:
        try:
            if pd.to_datetime(df[c], errors="coerce").notna().mean() > 0.8:
                return str(c)
        except Exception:
            continue
    return str(df.columns[0])


def execute_trend_plan(df: pd.DataFrame, plan: dict, context: dict | None = None) -> SkillResult:
    date_col = _pick_date_col(df, plan.get("date_col"))
    value_col = safe_col(df, plan.get("value_col"), prefer_numeric=True)
    agg = str(plan.get("agg", "sum")).lower()
    freq_key = str(plan.get("freq", "M")).upper()
    freq = _FREQ_MAP.get(freq_key, "ME")
    title = str(plan.get("title") or f"{value_col} 趋势")

    # 退化情形：无独立数值列时 value_col 降级后与 date_col 同名，无法做趋势
    if date_col == value_col:
        evidence = pd.DataFrame({"message": ["无可用于趋势分析的有效日期/数值数据。"]})
        return SkillResult(answer="无法计算趋势：缺少有效的日期或数值列。",
                           evidence=evidence, chart=None, meta={"title": title})

    work = df[[date_col, value_col]].copy()
    work[date_col] = pd.to_datetime(work[date_col], errors="coerce")
    work[value_col] = pd.to_numeric(work[value_col], errors="coerce")
    work = work.dropna()
    if work.empty:
        evidence = pd.DataFrame({"message": ["无可用于趋势分析的有效日期/数值数据。"]})
        return SkillResult(answer="无法计算趋势：缺少有效的日期或数值列。",
                           evidence=evidence, chart=None, meta={"title": title})

    series = work.set_index(date_col).resample(freq)[value_col]
    series = series.mean() if agg == "mean" else series.sum()
    evidence = series.reset_index().dropna()
    evidence.columns = [date_col, value_col]
    fig = px.line(evidence, x=date_col, y=value_col, title=title, markers=True)
    chart = fig_to_chart_dict(fig)
    return SkillResult(answer=f"已按 {freq_key} 频率对 {value_col} 做 {agg} 聚合趋势分析。",
                       evidence=evidence, chart=chart,
                       meta={"title": title, "x_label": date_col, "y_label": value_col})
