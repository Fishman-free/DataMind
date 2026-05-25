"""
自动洞察引擎。

基于规则 + 统计阈值，从 Analyzer / Detector 结果中提炼人类可读的洞察卡片。
不依赖 LLM API，速度快、零成本、结果可解释。

洞察类型：
  trend        — 销售趋势（MoM 增长/下跌）
  anomaly      — 异常值警告
  distribution — 地区/类别集中度
  correlation  — 数值列强相关提示
  period       — 购买高峰时段

每条洞察格式：
  {"type": str, "severity": "high"|"medium"|"low", "title": str, "detail": str}

来源：学生+AI
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pandas as pd

if TYPE_CHECKING:
    from data.analyzer import Analyzer
    from data.detector import Detector

# ── 阈值常量 ──────────────────────────────────────────────────
_GROWTH_HIGH   = 0.50   # MoM 增幅 ≥ 50% → high
_GROWTH_MED    = 0.20   # MoM 增幅 ≥ 20% → medium
_OUTLIER_HIGH  = 0.10   # 异常率 ≥ 10% → high
_OUTLIER_MED   = 0.05   # 异常率 ≥ 5%  → medium
_CONC_HIGH     = 0.80   # 第一名占比 ≥ 80% → high
_CONC_MED      = 0.60   # 第一名占比 ≥ 60% → medium
_CORR_HIGH     = 0.85   # |相关系数| ≥ 0.85 → high
_CORR_MED      = 0.70   # |相关系数| ≥ 0.70 → medium

_DAY_NAMES = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


class InsightEngine:
    """
    自动洞察生成器。

    用法
    ----
    engine = InsightEngine(clean_df, Analyzer(clean_df), Detector(clean_df))
    insights = engine.generate_all()  # -> list[dict]
    """

    def __init__(self, df: pd.DataFrame, analyzer: "Analyzer", detector: "Detector",
                 df_summary: dict | None = None) -> None:
        self.df          = df
        self._df         = df          # 别名，供通用洞察方法使用
        self.analyzer    = analyzer
        self.detector    = detector
        self._df_summary = df_summary  # 可选，用于目标相关性洞察

    def generate_all(self) -> list[dict[str, Any]]:
        """执行全部洞察规则，返回洞察卡片列表。"""
        insights: list[dict[str, Any]] = []
        for method in (
            self._trend_insights,
            self._anomaly_insights,
            self._distribution_insights,
            self._correlation_insights,
            self._period_insights,
        ):
            try:
                insights.extend(method())
            except Exception:
                # 单个规则失败不影响其他规则
                pass
        insights.extend(self._numeric_skew_insights())
        insights.extend(self._category_concentration_insights())
        target_col = self._df_summary.get("target_col") if self._df_summary else None
        if target_col:
            insights.extend(self._target_correlation_insights(target_col))
        return insights

    # ── 1. 趋势洞察 ───────────────────────────────────

    def _trend_insights(self) -> list[dict]:
        result = self.analyzer.sales_trend(freq="ME")
        if not result or len(result.get("values", [])) < 2:
            return []

        labels = result["labels"]
        values = result["values"]
        insights = []

        for i in range(1, len(values)):
            prev = values[i - 1]
            curr = values[i]
            if prev == 0:
                continue
            growth = (curr - prev) / prev
            if abs(growth) < _GROWTH_MED:
                continue

            direction = "增长" if growth > 0 else "下跌"
            pct       = f"{abs(growth) * 100:.1f}%"
            severity  = "high" if abs(growth) >= _GROWTH_HIGH else "medium"

            insights.append({
                "type":     "trend",
                "severity": severity,
                "title":    f"销售额{direction}明显：{labels[i]}",
                "detail":   f"{labels[i]} 销售额较上期{direction} {pct}，"
                            f"由 {values[i-1]:.2f} 变为 {curr:.2f}",
            })

        return insights[:3]  # 最多返回 3 条趋势洞察

    # ── 2. 异常洞察 ───────────────────────────────────

    def _anomaly_insights(self) -> list[dict]:
        summary = self.detector.outlier_summary()
        insights = []

        for item in summary:
            rate = item["outlier_rate"]
            if rate < _OUTLIER_MED:
                continue

            severity = "high" if rate >= _OUTLIER_HIGH else "medium"
            insights.append({
                "type":     "anomaly",
                "severity": severity,
                "title":    f"列 {item['col']} 存在异常值",
                "detail":   f"{item['col']} 中检测到 {item['outlier_count']} 个异常值，"
                            f"占比 {rate * 100:.1f}%（IQR 法）",
            })

        return insights

    # ── 3. 分布洞察 ───────────────────────────────────

    def _distribution_insights(self) -> list[dict]:
        dist = self.analyzer.country_distribution()
        if not dist:
            return []

        top      = dist[0]
        top_pct  = top["percentage"] / 100.0
        if top_pct < _CONC_MED:
            return []

        severity = "high" if top_pct >= _CONC_HIGH else "medium"
        return [{
            "type":     "distribution",
            "severity": severity,
            "title":    f"销售高度集中于 {top['country']}",
            "detail":   f"{top['country']} 贡献了 {top['percentage']:.1f}% 的销售额，"
                        f"市场集中度{'极高' if severity == 'high' else '较高'}",
        }]

    # ── 4. 相关性洞察 ─────────────────────────────────

    def _correlation_insights(self) -> list[dict]:
        corr = self.analyzer.correlation_matrix()
        columns = corr.get("columns", [])
        matrix  = corr.get("matrix", [])
        if len(columns) < 2:
            return []

        insights = []
        seen: set[frozenset] = set()

        for i, row in enumerate(matrix):
            for j, val in enumerate(row):
                if i == j:
                    continue
                pair = frozenset({columns[i], columns[j]})
                if pair in seen:
                    continue
                seen.add(pair)

                if abs(val) < _CORR_MED:
                    continue

                severity  = "high" if abs(val) >= _CORR_HIGH else "medium"
                direction = "正相关" if val > 0 else "负相关"
                insights.append({
                    "type":     "correlation",
                    "severity": severity,
                    "title":    f"{columns[i]} 与 {columns[j]} 强{direction}",
                    "detail":   f"Pearson 相关系数 = {val:.3f}，二者存在{'强' if severity == 'high' else '中等'}{direction}关系",
                })

        return insights[:3]  # 最多 3 条

    # ── 5. 周期洞察 ───────────────────────────────────

    def _period_insights(self) -> list[dict]:
        pattern = self.analyzer.time_pattern()
        if not pattern:
            return []

        matrix = pattern["matrix"]   # shape: 7 × 24

        # 各星期总订单量
        day_totals  = [sum(row) for row in matrix]
        peak_day    = day_totals.index(max(day_totals))

        # 各小时总订单量
        hour_totals = [sum(matrix[d][h] for d in range(7)) for h in range(24)]
        peak_hour   = hour_totals.index(max(hour_totals))

        return [{
            "type":     "period",
            "severity": "low",
            "title":    f"购买高峰：{_DAY_NAMES[peak_day]} {peak_hour:02d}:00",
            "detail":   f"订单量在 {_DAY_NAMES[peak_day]} 最多，"
                        f"一天中 {peak_hour:02d}:00 前后是高峰时段",
        }]

    # ── 6. 偏态分布洞察 ────────────────────────────────

    def _numeric_skew_insights(self) -> list[dict]:
        """检测偏态系数 > 1.5 的数值列，生成分布偏态洞察。"""
        try:
            from scipy import stats as _stats
        except ImportError:
            return []
        results = []
        try:
            num_cols = self._df.select_dtypes(include="number").columns
            for col in num_cols:
                series = self._df[col].dropna()
                if len(series) < 10:
                    continue
                skewness = float(_stats.skew(series))
                if abs(skewness) > 1.5:
                    direction = "右偏（正偏）" if skewness > 0 else "左偏（负偏）"
                    results.append({
                        "type":     "distribution",
                        "severity": "medium",
                        "title":    f"{col} 分布严重偏态",
                        "detail":   f"列 {col} 的偏态系数为 {skewness:.2f}（{direction}），"
                                    f"均值 {series.mean():.2f} 远离中位数 {series.median():.2f}。",
                    })
        except Exception:
            pass
        return results[:2]  # 最多返回 2 条

    # ── 7. 类别集中度洞察 ──────────────────────────────

    def _category_concentration_insights(self) -> list[dict]:
        """检测类别列中最高频率类别占比 > 60% 的情况。"""
        results = []
        try:
            cat_cols = [c for c in self._df.select_dtypes(include=["object", "category"]).columns
                        if self._df[c].nunique() <= 50]
            for col in cat_cols:
                vc  = self._df[col].value_counts(normalize=True)
                top = float(vc.iloc[0]) if len(vc) > 0 else 0
                if top > 0.6:
                    results.append({
                        "type":     "distribution",
                        "severity": "medium",
                        "title":    f"{col} 分布高度集中",
                        "detail":   f"列 {col} 中 \"{vc.index[0]}\" 占比 {top*100:.1f}%，"
                                    f"数据分布存在明显不均衡。",
                    })
        except Exception:
            pass
        return results[:2]

    # ── 8. 目标相关性洞察 ──────────────────────────────

    def _target_correlation_insights(self, target_col: str) -> list[dict]:
        """找出与目标列相关性 > 0.3 的特征，生成预测特征洞察。"""
        results = []
        try:
            num_cols = [c for c in self._df.select_dtypes(include="number").columns
                        if c != target_col]
            if not num_cols or target_col not in self._df.columns:
                return []
            corr = self._df[num_cols + [target_col]].corr()[target_col].drop(target_col)
            strong = corr[corr.abs() > 0.3].sort_values(key=abs, ascending=False)
            if len(strong) > 0:
                top_features = ", ".join(
                    f"{col}({val:.2f})" for col, val in strong.head(3).items()
                )
                results.append({
                    "type":     "correlation",
                    "severity": "high",
                    "title":    f"发现 {target_col} 的强相关预测特征",
                    "detail":   f"与目标列 {target_col} 相关系数 > 0.3 的特征：{top_features}。"
                                f"这些特征可能对预测 {target_col} 有较强参考价值。",
                })
        except Exception:
            pass
        return results
