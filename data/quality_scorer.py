"""
数据质量评分卡模块。
对上传的数据集从 5 个维度自动评估质量：
  完整性（30%）、唯一性（20%）、一致性（15%）、时效性（15%）、准确性（20%）
综合分 0-100 + A/B/C/D 等级 + 改进建议列表，全部本地运算，零 API 依赖。

来源：学生+AI
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd


class QualityScorer:
    """数据质量评分器，输出 0-100 的综合质量分与 5 维度明细。"""

    @staticmethod
    def _safe_score(value: float, default: float = 0.0) -> float:
        """统一处理分值：finite 校验 + [0,100] clamp。"""
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            numeric = float(default)

        if not math.isfinite(numeric):
            numeric = float(default)

        return max(0.0, min(100.0, numeric))

    def _build_dimension(self, name: str, score: float, detail: str) -> dict:
        """构建标准维度对象，统一分值归一化。"""
        safe_score = self._safe_score(score)
        return {
            "score": round(safe_score, 1),
            "weight": self._WEIGHTS[name],
            "detail": detail,
        }

    # 维度权重
    _WEIGHTS = {
        "completeness": 0.30,   # 完整性
        "uniqueness":   0.20,   # 唯一性
        "consistency":  0.15,   # 一致性
        "timeliness":   0.15,   # 时效性
        "accuracy":     0.20,   # 准确性
    }

    _GRADE_THRESHOLDS = [
        (90, "A"),
        (75, "B"),
        (60, "C"),
    ]

    # ── 公共接口 ─────────────────────────────────────────

    def score(self, df_raw: pd.DataFrame, df_clean: pd.DataFrame,
              preprocess_report: dict) -> dict:
        """
        计算数据质量评分。

        Args:
            df_raw: 原始 DataFrame
            df_clean: 清洗后 DataFrame
            preprocess_report: 预处理报告

        Returns:
            {
                "total_score": int,       # 0-100 综合评分
                "grade": str,             # A/B/C/D 等级
                "dimensions": {           # 5 维度明细
                    "completeness":  {"score": int, "weight": float, "detail": str},
                    ...
                },
                "suggestions": [str, ...] # 改进建议列表
            }
        """
        if df_raw.empty:
            return {
                "total_score": 0,
                "grade": "D",
                "dimensions": self._score_dimensions(df_raw, df_clean, preprocess_report),
                "suggestions": ["数据集为空，无法评估质量"],
            }

        dimensions = self._score_dimensions(df_raw, df_clean, preprocess_report)
        total = self._calculate_total(dimensions)
        grade = self._grade(total)
        suggestions = self._generate_suggestions(dimensions)

        return {
            "total_score": round(total),
            "grade": grade,
            "dimensions": dimensions,
            "suggestions": suggestions,
        }

    # ── 维度评分 ─────────────────────────────────────────

    def _score_dimensions(self, df_raw: pd.DataFrame, df_clean: pd.DataFrame,
                          preprocess_report: dict) -> dict:
        """计算全部 5 个维度的得分。"""
        return {
            "completeness": self._score_completeness(df_raw),
            "uniqueness":   self._score_uniqueness(df_raw),
            "consistency":  self._score_consistency(df_clean),
            "timeliness":   self._score_timeliness(df_raw),
            "accuracy":     self._score_accuracy(preprocess_report),
        }

    def _score_completeness(self, df: pd.DataFrame) -> dict:
        """完整性：各列缺失率加权扣分（满分 100）。"""
        if len(df) == 0 or len(df.columns) == 0:
            return self._build_dimension("completeness", 0, "数据集为空")
        missing_rate = df.isnull().sum().sum() / (len(df) * len(df.columns))
        score = 100 - missing_rate * 100
        return self._build_dimension("completeness", score, f"整体缺失率 {missing_rate:.2%}")

    def _score_uniqueness(self, df: pd.DataFrame) -> dict:
        """唯一性：基于重复行比例扣分。"""
        if len(df) == 0:
            return self._build_dimension("uniqueness", 0, "数据集为空")
        dup_rate = df.duplicated().sum() / len(df)
        score = 100 - dup_rate * 100
        return self._build_dimension("uniqueness", score, f"重复行比例 {dup_rate:.2%}")

    def _score_consistency(self, df: pd.DataFrame) -> dict:
        """一致性：数值列异常值（IQR 法）比例扣分。"""
        num_cols = df.select_dtypes(include=[np.number]).columns
        if len(num_cols) == 0:
            return self._build_dimension("consistency", 100, "无数值列")
        total_outliers = 0
        total_values = 0
        for col in num_cols:
            series = df[col].dropna()
            if len(series) < 4:
                continue
            q1, q3 = series.quantile(0.25), series.quantile(0.75)
            iqr = q3 - q1
            if iqr == 0:
                continue
            lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
            outliers = ((series < lower) | (series > upper)).sum()
            total_outliers += outliers
            total_values += len(series)
        if total_values == 0:
            return self._build_dimension("consistency", 100, "无有效数值数据")
        outlier_rate = total_outliers / total_values
        score = 100 - outlier_rate * 100
        return self._build_dimension("consistency", score, f"异常值比例 {outlier_rate:.2%}（IQR 法）")

    def _score_timeliness(self, df: pd.DataFrame) -> dict:
        """时效性：最新日期距今越久扣分越多（>7d/30d/90d 逐级扣分）。"""
        date_cols = df.select_dtypes(include=["datetime64", "datetimetz"]).columns
        if len(date_cols) == 0:
            # 无日期列，给基准分 70
            return self._build_dimension("timeliness", 70, "无日期列，无法评估时效性")

        latest = df[date_cols[0]].max()
        if pd.isna(latest):
            return self._build_dimension("timeliness", 50, "日期列为空")

        latest_ts = pd.Timestamp(latest)
        if latest_ts.tzinfo is not None:
            now_ts = pd.Timestamp.now(tz=latest_ts.tz)
        else:
            now_ts = pd.Timestamp.now()
        days_ago = (now_ts - latest_ts).days

        if days_ago <= 7:
            score = 100
        elif days_ago <= 30:
            score = 85
        elif days_ago <= 90:
            score = 60
        else:
            score = 30

        return self._build_dimension("timeliness", score, f"最新日期距今 {days_ago} 天")

    def _score_accuracy(self, preprocess_report: dict) -> dict:
        """准确性：基于预处理报告中的类型转换成功率。"""
        report = preprocess_report or {}
        steps = report.get("steps", [])
        # 查找类型转换步骤
        conversion_failures = 0
        for step in steps:
            name = str(step.get("name", ""))
            if "类型转换" in name or "type" in name.lower():
                detail = step.get("detail", "")
                detail_text = "" if detail is None else str(detail)
                # 简单检测：detail 中是否提到失败或错误
                if "失败" in detail_text or "错误" in detail_text:
                    conversion_failures += 1
        # 无类型转换信息时给基准分 80
        if not any("类型转换" in str(s.get("name", "")) or "type" in str(s.get("name", "")).lower() for s in steps):
            return self._build_dimension("accuracy", 80, "无类型转换信息")
        score = 100 - conversion_failures * 20
        return self._build_dimension("accuracy", score, f"类型转换问题列数：{conversion_failures}")

    # ── 综合计算 ─────────────────────────────────────────

    def _calculate_total(self, dimensions: dict) -> float:
        """加权计算总分。"""
        total = 0.0
        for dim_name, dim_data in dimensions.items():
            total += dim_data["score"] * dim_data["weight"]
        return total

    def _grade(self, score: float) -> str:
        """分数 → 等级映射。"""
        for threshold, grade in self._GRADE_THRESHOLDS:
            if score >= threshold:
                return grade
        return "D"

    def _generate_suggestions(self, dimensions: dict) -> list[str]:
        """基于低分维度生成改进建议。"""
        suggestions = []
        tips = {
            "completeness": "建议：检查数据源完整性，补充缺失值或使用插值填充",
            "uniqueness":   "建议：使用去重操作清理重复记录",
            "consistency":  "建议：检查异常值来源，考虑使用 IQR 方法或 Z-score 过滤",
            "timeliness":   "建议：更新数据源，确保数据时效性",
            "accuracy":     "建议：检查数据类型定义，确保各列类型转换正确",
        }
        for dim_name, dim_data in dimensions.items():
            if dim_data["score"] < 70:
                suggestions.append(tips.get(dim_name, f"改进 {dim_name} 维度"))
        if not suggestions:
            suggestions.append("数据质量良好，无需特别改进")
        return suggestions
