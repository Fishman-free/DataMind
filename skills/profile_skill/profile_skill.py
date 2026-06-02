"""数据画像技能：概览 / schema / 质量。来源：学生+AI"""
from __future__ import annotations

import pandas as pd

from skills._contract import SkillResult
from data.profiler import DataProfiler


def execute_profile_plan(df: pd.DataFrame, plan: dict, context: dict | None = None) -> SkillResult:
    scope = str(plan.get("scope", "overview")).lower()
    context = context or {}
    prof = context.get("profile") or DataProfiler(df).detect()

    if scope == "schema":
        rows = [{"列名": c, "类型": info.get("dtype", ""),
                 "唯一值": info.get("nunique", ""),
                 "样本": ", ".join(info.get("samples", [])[:3])}
                for c, info in prof.get("col_info", {}).items()]
        evidence = pd.DataFrame(rows) if rows else pd.DataFrame({"列名": list(map(str, df.columns))})
        answer = f"数据集含 {len(df)} 行 {len(df.columns)} 列，类型为「{prof.get('display_name', '')}」。"
        return SkillResult(answer=answer, evidence=evidence, meta={"title": "字段 Schema"})

    if scope == "quality":
        qs = context.get("quality_score")
        if qs:
            rows = [{"维度": k, "得分": v.get("score"), "说明": v.get("detail", "")}
                    for k, v in qs.get("dimensions", {}).items()]
            evidence = pd.DataFrame(rows)
            answer = (f"数据质量总分 {qs.get('total_score')}（{qs.get('grade')} 级）。"
                      + " ".join(qs.get("suggestions", [])[:2]))
        else:
            miss = df.isna().sum()
            evidence = miss[miss > 0].reset_index()
            evidence.columns = ["列", "缺失数"]
            if evidence.empty:
                evidence = pd.DataFrame({"列": ["(无缺失)"], "缺失数": [0]})
            answer = "（未预计算质量评分）已给出缺失值概览。"
        return SkillResult(answer=answer, evidence=evidence, meta={"title": "数据质量"})

    # 默认：overview
    rows = [
        {"项目": "行数", "值": len(df)},
        {"项目": "列数", "值": len(df.columns)},
        {"项目": "画像类型", "值": prof.get("display_name", "")},
        {"项目": "数值列数", "值": len(prof.get("numeric_cols", []))},
        {"项目": "分类列数", "值": len(prof.get("categorical_cols", []))},
        {"项目": "含日期列", "值": "是" if prof.get("has_date") else "否"},
    ]
    evidence = pd.DataFrame(rows)
    answer = prof.get("description", "") or f"数据集含 {len(df)} 行 {len(df.columns)} 列。"
    return SkillResult(answer=answer, evidence=evidence, meta={"title": "数据概览"})
