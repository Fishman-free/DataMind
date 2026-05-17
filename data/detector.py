"""
异常检测模块。

对预处理后的 DataFrame 执行多维度异常分析：
  1. outlier_summary   — 汇总 IQR 标记列（由 Preprocessor 添加）
  2. zscore_anomalies  — Z-Score 数值异常检测
  3. trend_breaks      — 时间序列突变点检测（滚动均值偏差法）
  4. run_all           — 自动推断并执行全部检测，返回综合报告

所有方法返回 JSON 可序列化的 Python 原生类型。

来源：学生+AI
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from data.analyzer import _find_col, _safe_float, _DATE_KEYWORDS, _AMOUNT_KEYWORDS


class Detector:
    """
    对清洁后的 DataFrame 执行异常检测。
    传入的 df 应已经过 Preprocessor.run_all() 处理。
    """

    def __init__(self, df: pd.DataFrame) -> None:
        self.df = df

    # ── 1. IQR 标记汇总 ───────────────────────────────────

    def outlier_summary(self) -> list[dict[str, Any]]:
        """
        汇总由 Preprocessor.filter_outliers() 添加的 <col>_is_outlier 列。

        Returns
        -------
        [{"col": str, "outlier_count": int, "outlier_rate": float}]
        无 _is_outlier 列时返回空列表。
        """
        result = []
        n_total = len(self.df)

        for col in self.df.columns:
            if not col.endswith("_is_outlier"):
                continue
            base_col  = col[: -len("_is_outlier")]
            n_outlier = int(self.df[col].sum())
            result.append({
                "col":           base_col,
                "outlier_count": n_outlier,
                "outlier_rate":  round(n_outlier / n_total, 4) if n_total > 0 else 0.0,
            })
        return result

    # ── 2. Z-Score 异常检测 ────────────────────────────────

    def zscore_anomalies(
        self, col: str, threshold: float = 3.0
    ) -> dict[str, Any]:
        """
        对指定列执行 Z-Score 异常检测。

        Parameters
        ----------
        col       : 目标列名
        threshold : Z-Score 绝对值阈值（默认 3.0）

        Returns
        -------
        {"col", "threshold", "anomaly_count", "anomalies": [{"index", "value", "zscore"}]}
        {"error": "..."} 当列不存在或非数值时。
        """
        if col not in self.df.columns:
            return {"error": f"列不存在：{col}"}

        series = self.df[col]
        if not pd.api.types.is_numeric_dtype(series):
            return {"error": f"列 {col} 非数值类型"}

        mean = series.mean()
        std  = series.std()

        # 常数列（std=0）无异常
        if std == 0 or pd.isna(std):
            return {
                "col":           col,
                "threshold":     threshold,
                "anomaly_count": 0,
                "anomalies":     [],
            }

        zscores = (series - mean) / std
        mask    = zscores.abs() >= threshold

        anomalies = [
            {
                "index":  int(idx),
                "value":  round(_safe_float(self.df.loc[idx, col]), 4),
                "zscore": round(_safe_float(zscores[idx]), 4),
            }
            for idx in self.df.index[mask]
        ]

        return {
            "col":           col,
            "threshold":     threshold,
            "anomaly_count": len(anomalies),
            "anomalies":     anomalies,
        }

    # ── 3. 时间序列突变检测 ────────────────────────────────

    def trend_breaks(
        self, col: str, window: int = 7, sigma: float = 2.0
    ) -> dict[str, Any]:
        """
        在日期聚合的时间序列中，用滚动均值 ± sigma×滚动标准差检测突变点。

        Parameters
        ----------
        col    : 目标数值列（按日求和）
        window : 滚动窗口天数（默认 7）
        sigma  : 偏差倍数阈值（默认 2.0）

        Returns
        -------
        {"col", "window", "break_count", "breaks", "labels", "values", "trend"}
        {"error": "..."} 当缺少日期列或目标列时。
        """
        date_col = _find_col(self.df, _DATE_KEYWORDS)
        if date_col is None:
            return {"error": "缺少日期列，无法进行趋势分析"}

        if col not in self.df.columns:
            return {"error": f"列不存在：{col}"}

        if not pd.api.types.is_numeric_dtype(self.df[col]):
            return {"error": f"列 {col} 非数值类型"}

        # 按日聚合
        series = (
            self.df.set_index(date_col)[col]
            .resample("D")
            .sum()
        )

        rolling_mean = series.rolling(window=window, min_periods=1).mean()
        rolling_std  = series.rolling(window=window, min_periods=1).std().fillna(0)

        upper      = rolling_mean + sigma * rolling_std
        lower      = rolling_mean - sigma * rolling_std
        break_mask = (series > upper) | (series < lower)

        breaks = [
            {
                "date":     str(idx.date()),
                "value":    round(_safe_float(series[idx]), 2),
                "expected": round(_safe_float(rolling_mean[idx]), 2),
            }
            for idx in series.index[break_mask]
        ]

        return {
            "col":         col,
            "window":      window,
            "break_count": len(breaks),
            "breaks":      breaks,
            "labels":      [str(idx.date()) for idx in series.index],
            "values":      [round(_safe_float(v), 2) for v in series.values],
            "trend":       [round(_safe_float(v), 2) for v in rolling_mean.values],
        }

    # ── 4. 综合报告 ───────────────────────────────────────

    def run_all(self) -> dict[str, Any]:
        """
        执行全部检测，自动推断目标列。

        Returns
        -------
        {
            "outlier_summary": [...],
            "zscore_anomalies": {col: result},
            "trend_breaks": result | None,
        }
        """
        report: dict[str, Any] = {}

        # 1. IQR 汇总
        report["outlier_summary"] = self.outlier_summary()

        # 2. Z-Score：对业务数值列逐一检测（排除派生列和 ID 类列）
        zscore_results: dict[str, Any] = {}
        for col in self.df.select_dtypes(include=[np.number]).columns:
            if col.endswith("_is_outlier"):
                continue
            normalized = col.lower().replace("_", "").replace(" ", "")
            if len(normalized) > 4 and normalized.endswith(("id", "no", "code")):
                continue
            zscore_results[col] = self.zscore_anomalies(col)
        report["zscore_anomalies"] = zscore_results

        # 3. 趋势突变：对金额列（或 TotalAmount）分析
        amount_col = _find_col(self.df, _AMOUNT_KEYWORDS)
        if amount_col:
            report["trend_breaks"] = self.trend_breaks(amount_col)
        else:
            report["trend_breaks"] = None

        return report
