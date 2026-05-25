"""
数据画像检测模块。

自动识别数据集类型（retail/temporal/numeric/categorical/geographic/mixed），
生成数据自描述、全列信息和建议问题，供 AI 系统提示词和自适应仪表盘使用。

来源：学生+AI
"""
from __future__ import annotations

import re
from typing import Any

import pandas as pd


# ── 关键词库 ──────────────────────────────────────────────────

_DATE_KEYWORDS   = re.compile(r"date|time|日期|时间|year|month|day|week", re.I)
_CUSTOMER_KWORDS = re.compile(r"customer|client|user|userid|客户|用户", re.I)
_PRODUCT_KWORDS  = re.compile(r"product|item|sku|description|商品|产品|物品", re.I)
_AMOUNT_KWORDS   = re.compile(r"price|amount|revenue|sales|total|金额|价格|销售", re.I)
_GEO_KEYWORDS    = re.compile(r"country|province|city|region|state|国家|省|城市|地区", re.I)

_MODE_NAMES = {
    "retail":      "零售交易型",
    "temporal":    "时间序列型",
    "numeric":     "科学数值型",
    "categorical": "分类调查型",
    "geographic":  "地理分布型",
    "mixed":       "混合型",
}

_MODE_ICONS = {
    "retail":      "🛒",
    "temporal":    "📈",
    "numeric":     "🔬",
    "categorical": "📊",
    "geographic":  "🌍",
    "mixed":       "◈",
}


class DataProfiler:
    """检测 DataFrame 的数据画像，驱动自适应分析和前端渲染。"""

    def __init__(self, df: pd.DataFrame) -> None:
        self._df = df

    def detect(self) -> dict[str, Any]:
        df = self._df
        cols = list(df.columns)

        numeric_cols     = list(df.select_dtypes(include="number").columns)
        datetime_cols    = list(df.select_dtypes(include=["datetime", "datetimetz"]).columns)
        object_cols      = list(df.select_dtypes(include=["str", "object", "category"]).columns)
        categorical_cols = [c for c in object_cols if df[c].nunique() <= 50]

        date_col     = self._find_col(cols, _DATE_KEYWORDS, datetime_cols)
        customer_col = self._find_col(cols, _CUSTOMER_KWORDS)
        product_col  = self._find_col(cols, _PRODUCT_KWORDS)
        amount_col   = self._find_col(cols, _AMOUNT_KWORDS, numeric_cols)
        geo_col      = self._find_col(cols, _GEO_KEYWORDS)

        has_date      = date_col is not None
        has_geography = geo_col is not None
        has_customer  = customer_col is not None

        target_col = self._detect_target(numeric_cols, cols)

        mode = self._classify_mode(
            numeric_cols, categorical_cols, has_date,
            has_geography, has_customer, product_col, amount_col
        )

        col_info = self._build_col_info()

        return {
            "mode":               mode,
            "display_name":       _MODE_NAMES[mode],
            "icon":               _MODE_ICONS[mode],
            "numeric_cols":       numeric_cols,
            "categorical_cols":   categorical_cols,
            "date_col":           date_col,
            "target_col":         target_col,
            "amount_col":         amount_col,
            "geo_col":            geo_col,
            "has_date":           has_date,
            "has_geography":      has_geography,
            "has_customer":       has_customer,
            "col_info":           col_info,
            "suggested_questions": self._suggest_questions(
                mode, numeric_cols, categorical_cols, date_col, target_col
            ),
            "description":        self._describe(
                mode, numeric_cols, categorical_cols, date_col, target_col
            ),
        }

    def _find_col(self, cols: list[str], pattern: re.Pattern,
                  candidates: list[str] | None = None) -> str | None:
        search_cols = candidates if candidates is not None else cols
        for c in search_cols:
            if pattern.search(str(c)):
                return c
        return None

    def _detect_target(self, numeric_cols: list[str], all_cols: list[str]) -> str | None:
        target_kw = re.compile(r"quality|label|target|score|class|output|result|grade", re.I)
        for c in numeric_cols:
            if target_kw.search(str(c)):
                return c
        if numeric_cols and numeric_cols[-1] == all_cols[-1]:
            return numeric_cols[-1]
        return None

    def _classify_mode(self, numeric_cols, categorical_cols, has_date,
                       has_geography, has_customer, product_col, amount_col) -> str:
        if has_date and has_customer and (product_col or amount_col):
            return "retail"
        if has_date and numeric_cols:
            return "temporal"
        if has_geography and numeric_cols:
            return "geographic"
        if len(numeric_cols) >= 4 and len(categorical_cols) <= 2:
            return "numeric"
        if len(categorical_cols) >= 3:
            return "categorical"
        return "mixed"

    def _build_col_info(self) -> dict[str, dict]:
        df = self._df
        info: dict[str, dict] = {}
        for col in df.columns:
            samples = df[col].dropna().head(3).tolist()
            info[str(col)] = {
                "dtype":   str(df[col].dtype),
                "samples": [str(s) for s in samples],
                "nunique": int(df[col].nunique()),
            }
        return info

    def _suggest_questions(self, mode: str, numeric_cols: list[str],
                           categorical_cols: list[str], date_col: str | None,
                           target_col: str | None) -> list[str]:
        qs: list[str] = []

        if mode == "retail":
            return ["月均销售额是多少？", "Top 10 畅销商品有哪些？",
                    "各国家销售额占比如何？", "画一个月度销售趋势折线图"]

        if mode == "temporal" and date_col:
            qs.append(f"按 {date_col} 展示数值趋势")

        if target_col and numeric_cols:
            qs.append(f"哪些特征与 {target_col} 相关性最高？")

        if numeric_cols:
            qs.append(f"{numeric_cols[0]} 列的分布情况如何？")
            if len(numeric_cols) >= 2:
                qs.append(f"画 {numeric_cols[0]} 和 {numeric_cols[1]} 的散点图")

        if categorical_cols:
            qs.append(f"{categorical_cols[0]} 列的频次分布是什么？")

        if len(qs) < 4 and numeric_cols:
            qs.append("哪些列存在异常值？")

        return qs[:4]

    def _describe(self, mode: str, numeric_cols: list[str],
                  categorical_cols: list[str], date_col: str | None,
                  target_col: str | None) -> str:
        df   = self._df
        rows = len(df)
        cols = len(df.columns)
        mode_name = _MODE_NAMES[mode]

        parts = [f"这是一个包含 {rows:,} 条记录、{cols} 个字段的{mode_name}数据集。"]

        if numeric_cols:
            parts.append(
                f"数值型字段 {len(numeric_cols)} 个（{', '.join(numeric_cols[:4])}"
                f"{'等' if len(numeric_cols) > 4 else ''}）。"
            )

        if categorical_cols:
            parts.append(f"类别型字段 {len(categorical_cols)} 个（{', '.join(categorical_cols[:3])}）。")

        if date_col:
            try:
                date_series = pd.to_datetime(df[date_col], errors="coerce").dropna()
                if len(date_series) > 0:
                    parts.append(
                        f"时间跨度从 {date_series.min().date()} 到 {date_series.max().date()}。"
                    )
            except Exception:
                pass

        if target_col:
            try:
                tmin = df[target_col].min()
                tmax = df[target_col].max()
                parts.append(f"目标列 {target_col}（范围 {tmin}–{tmax}）。")
            except Exception:
                pass

        missing = int(df.isnull().sum().sum())
        if missing == 0:
            parts.append("数据无缺失值。")
        else:
            pct = missing / (rows * len(df.columns)) * 100
            parts.append(f"共有 {missing} 个缺失值（占比 {pct:.1f}%）。")

        return "".join(parts)
