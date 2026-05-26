"""
数据分析模块 — 7 种内置分析方法。

方法列表：
  summary_stats / sales_trend / top_products / rfm_analysis
  country_distribution / correlation_matrix / time_pattern

所有方法返回 JSON 可序列化的 Python 原生类型（dict / list / None），
方便 Flask API 直接 jsonify 返回给前端。

来源：学生+AI
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd

# ── 列名关键词映射（大小写不敏感，去除空格后匹配）───────────────
_DATE_KEYWORDS     = {"invoicedate", "date", "datetime", "time", "日期", "时间"}
_PRODUCT_KEYWORDS  = {"description", "productname", "itemname", "商品名", "商品描述"}
_CUSTOMER_KEYWORDS = {"customerid", "customer_id", "userid", "客户id", "客户编号"}
_COUNTRY_KEYWORDS  = {"country", "region", "国家", "地区"}
_AMOUNT_KEYWORDS   = {"totalamount", "total", "amount", "revenue", "销售额", "金额"}
_QTY_KEYWORDS      = {"quantity", "qty", "数量"}
_PRICE_KEYWORDS    = {"unitprice", "price", "unit_price", "单价", "价格"}

# 热力图星期标签
_DAY_LABELS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

# 非商品行描述关键词（邮费、手续费等，top_products 时过滤）
_NON_PRODUCT_KEYWORDS = frozenset({
    "postage", "manual", "bank charges", "dotcom", "cruk",
    "samples", "carriage", "amazon", "adjust", "discount",
    "lost", "damaged", "test",
})


def _is_id_col(col: str) -> bool:
    """
    检测是否为 ID 标识类列（InvoiceNo / StockCode / CustomerID 等）。
    相关性矩阵中应排除这类列。
    规则：列名归一化后长度 > 4 且以 id / no / code 结尾。
    """
    normalized = col.lower().replace("_", "").replace(" ", "")
    if len(normalized) > 4:
        return normalized.endswith(("id", "no", "code"))
    return False


def _find_col(df: pd.DataFrame, keywords: set[str]) -> str | None:
    """在列名中查找与关键词集合匹配的第一列（小写+去空格）。"""
    for col in df.columns:
        if col.lower().replace(" ", "").replace("_", "") in keywords:
            return col
    return None


def _safe_float(val: Any) -> float:
    """将 numpy 数值安全转为 Python float，避免 JSON 序列化报错。"""
    if pd.isna(val):
        return 0.0
    return float(val)


class Analyzer:
    """
    对清洁后的 DataFrame 执行各类统计分析。
    传入的 df 应已经过 Preprocessor.run_all() 处理。
    """

    def __init__(self, df: pd.DataFrame) -> None:
        self.df = df

    # ── 1. 描述性统计 ──────────────────────────────────────

    def summary_stats(self) -> dict[str, Any]:
        """
        返回数据集概览统计。

        返回结构
        --------
        {
            "row_count": int,
            "column_count": int,
            "numeric_stats": {col: {mean, median, std, min, max}},
            "missing_counts": {col: int},
            "date_range": {"start": str, "end": str} | None,
        }
        """
        numeric_stats: dict[str, dict] = {}
        for col in self.df.select_dtypes(include=[np.number]).columns:
            s = self.df[col]
            numeric_stats[col] = {
                "mean":   round(_safe_float(s.mean()), 4),
                "median": round(_safe_float(s.median()), 4),
                "std":    round(_safe_float(s.std()), 4),
                "min":    round(_safe_float(s.min()), 4),
                "max":    round(_safe_float(s.max()), 4),
            }

        missing_counts = {
            col: int(self.df[col].isna().sum())
            for col in self.df.columns
            if self.df[col].isna().sum() > 0
        }

        # 日期范围
        date_col = _find_col(self.df, _DATE_KEYWORDS)
        date_range = None
        if date_col and pd.api.types.is_datetime64_any_dtype(self.df[date_col]):
            date_range = {
                "start": str(self.df[date_col].min().date()),
                "end":   str(self.df[date_col].max().date()),
            }

        return {
            "row_count":     int(len(self.df)),
            "column_count":  int(len(self.df.columns)),
            "columns":       list(self.df.columns),
            "numeric_stats": numeric_stats,
            "missing_counts": missing_counts,
            "date_range":    date_range,
        }

    # ── 2. 销售趋势 ───────────────────────────────────────

    def sales_trend(self, freq: str = "M") -> dict[str, Any] | None:
        """
        按时间频率聚合销售额。

        Parameters
        ----------
        freq : str
            pandas resample 频率字符串，如 'M'(月) / 'W'(周) / 'D'(日)。

        Returns
        -------
        {"labels": [...], "values": [...]} 或 None（无日期/金额列时）。
        """
        date_col   = _find_col(self.df, _DATE_KEYWORDS)
        amount_col = _find_col(self.df, _AMOUNT_KEYWORDS)

        # 降级：尝试用 Quantity × UnitPrice 计算金额
        if amount_col is None:
            qty_col   = _find_col(self.df, _QTY_KEYWORDS)
            price_col = _find_col(self.df, _PRICE_KEYWORDS)
            if qty_col and price_col:
                amount_col = "__tmp_amount__"
                self.df = self.df.copy()
                self.df[amount_col] = self.df[qty_col] * self.df[price_col]

        if date_col is None or amount_col is None:
            return None
        if not pd.api.types.is_datetime64_any_dtype(self.df[date_col]):
            return None

        # pandas 2.2+ 弃用旧别名，统一做映射
        _FREQ_MAP = {"M": "ME", "Y": "YE", "Q": "QE", "A": "YE"}
        freq = _FREQ_MAP.get(freq.upper(), freq)

        grouped = (
            self.df.set_index(date_col)[amount_col]
            .resample(freq)
            .sum()
        )

        labels = [str(idx.date()) if hasattr(idx, "date") else str(idx) for idx in grouped.index]
        values = [round(_safe_float(v), 2) for v in grouped.values]

        return {"labels": labels, "values": values}

    # ── 3. 商品排行 ───────────────────────────────────────

    def top_products(self, n: int = 10, by: str = "amount") -> list[dict[str, Any]]:
        """
        返回销售额/销量 Top N 商品。

        Parameters
        ----------
        n   : 返回条数
        by  : 'amount'（销售额）或 'quantity'（销量）
        """
        product_col = _find_col(self.df, _PRODUCT_KEYWORDS)
        amount_col  = _find_col(self.df, _AMOUNT_KEYWORDS)
        qty_col     = _find_col(self.df, _QTY_KEYWORDS)

        # 没有商品列时回退到第一个文本列
        if product_col is None:
            text_cols = self.df.select_dtypes(include=["object"]).columns.tolist()
            product_col = text_cols[0] if text_cols else None

        if product_col is None:
            return []

        if by == "quantity" and qty_col:
            value_col = qty_col
        elif amount_col:
            value_col = amount_col
        elif qty_col:
            value_col = qty_col
        else:
            return []

        # 过滤邮费/手续费等非商品行
        df = self.df
        if product_col in df.columns:
            non_prod_mask = df[product_col].astype(str).str.lower().apply(
                lambda x: not any(kw in x for kw in _NON_PRODUCT_KEYWORDS)
            )
            df = df[non_prod_mask]

        grouped = (
            df.groupby(product_col)[value_col]
            .sum()
            .nlargest(n)
            .reset_index()
        )

        return [
            {"name": str(row[product_col]), "value": round(_safe_float(row[value_col]), 2)}
            for _, row in grouped.iterrows()
        ]

    # ── 4. RFM 客户分析 ───────────────────────────────────

    def rfm_analysis(self) -> dict[str, Any]:
        """
        计算 Recency / Frequency / Monetary 三维客户价值评分。

        要求列：CustomerID（或类似）、InvoiceDate（或类似）、TotalAmount（或类似）。
        缺少必要列时返回 {"error": "..."}.
        """
        customer_col = _find_col(self.df, _CUSTOMER_KEYWORDS)
        date_col     = _find_col(self.df, _DATE_KEYWORDS)
        amount_col   = _find_col(self.df, _AMOUNT_KEYWORDS)

        missing = []
        if customer_col is None: missing.append("CustomerID")
        if date_col is None:     missing.append("InvoiceDate")
        if amount_col is None:   missing.append("TotalAmount")
        if missing:
            return {"error": f"缺少必要列：{', '.join(missing)}"}

        df = self.df[[customer_col, date_col, amount_col]].dropna(subset=[customer_col])
        if len(df) == 0:
            return {"error": "CustomerID 列全为空值"}

        reference_date = df[date_col].max() + pd.Timedelta(days=1)

        rfm = (
            df.groupby(customer_col)
            .agg(
                recency  = (date_col,   lambda x: (reference_date - x.max()).days),
                frequency= (date_col,   "count"),
                monetary = (amount_col, "sum"),
            )
            .reset_index()
        )

        # 打分 1-5（qcut 分 5 档）
        try:
            rfm["r_score"] = pd.qcut(rfm["recency"],   5, labels=[5,4,3,2,1], duplicates="drop")
            rfm["f_score"] = pd.qcut(rfm["frequency"], 5, labels=[1,2,3,4,5], duplicates="drop")
            rfm["m_score"] = pd.qcut(rfm["monetary"],  5, labels=[1,2,3,4,5], duplicates="drop")
        except ValueError:
            # 数据量太少无法分 5 档时简化处理
            rfm["r_score"] = 3
            rfm["f_score"] = 3
            rfm["m_score"] = 3

        rfm["rfm_score"] = (
            rfm["r_score"].astype(int) +
            rfm["f_score"].astype(int) +
            rfm["m_score"].astype(int)
        )

        customers = [
            {
                # 将 float CustomerID（如 12347.0）转为整数字符串 "12347"
                "customer_id": (
                    str(int(float(row[customer_col])))
                    if pd.notna(row[customer_col])
                    else str(row[customer_col])
                ),
                "recency":     int(row["recency"]),
                "frequency":   int(row["frequency"]),
                "monetary":    round(_safe_float(row["monetary"]), 2),
                "r_score":     int(row["r_score"]),
                "f_score":     int(row["f_score"]),
                "m_score":     int(row["m_score"]),
                "rfm_score":   int(row["rfm_score"]),
            }
            for _, row in rfm.iterrows()
        ]

        return {
            "total_customers": len(customers),
            "customers": customers,
            "reference_date": str(reference_date.date()),
        }

    # ── 5. 国家/地区分布 ──────────────────────────────────

    def country_distribution(self) -> list[dict[str, Any]]:
        """
        返回各国销售额占比，按销售额降序排列。
        无 Country 列时返回空列表。
        """
        country_col = _find_col(self.df, _COUNTRY_KEYWORDS)
        amount_col  = _find_col(self.df, _AMOUNT_KEYWORDS)

        if country_col is None:
            return []

        value_col = amount_col if amount_col else None
        if value_col is None:
            qty_col   = _find_col(self.df, _QTY_KEYWORDS)
            value_col = qty_col

        if value_col is None:
            return []

        grouped = (
            self.df.groupby(country_col)[value_col]
            .sum()
            .sort_values(ascending=False)
            .reset_index()
        )

        total = grouped[value_col].sum()
        return [
            {
                "country":    str(row[country_col]),
                "value":      round(_safe_float(row[value_col]), 2),
                "percentage": round(_safe_float(row[value_col] / total * 100), 2),
            }
            for _, row in grouped.iterrows()
        ]

    # ── 6. 相关性矩阵 ─────────────────────────────────────

    def correlation_matrix(self) -> dict[str, Any]:
        """
        计算所有数值列的 Pearson 相关系数矩阵。

        返回 {"columns": [...], "matrix": [[float, ...]]}
        """
        # 过滤掉 _is_outlier 派生列和 ID 标识类列，只保留原始业务数值列
        num_cols = [
            c for c in self.df.select_dtypes(include=[np.number]).columns
            if not c.endswith("_is_outlier") and not _is_id_col(c)
        ]

        if len(num_cols) < 2:
            return {"columns": num_cols, "matrix": []}

        # 去掉方差为 0 的列（常数列），避免相关系数全为 NaN
        num_cols = [c for c in num_cols if self.df[c].std() > 0]

        if len(num_cols) < 2:
            return {"columns": num_cols, "matrix": []}

        corr = self.df[num_cols].corr(method="pearson")

        return {
            "columns": list(corr.columns),
            "matrix": [
                [round(_safe_float(v), 4) for v in row]
                for row in corr.values
            ],
        }

    # ── 7. 时段购买模式 ───────────────────────────────────

    def time_pattern(self) -> dict[str, Any] | None:
        """
        生成 DayOfWeek × Hour 的订单量热力图数据。

        要求 DayOfWeek 和 Hour 列（由 Preprocessor.add_features 生成）。
        无对应列时返回 None。
        """
        if "DayOfWeek" not in self.df.columns or "Hour" not in self.df.columns:
            return None

        pivot = (
            self.df.groupby(["DayOfWeek", "Hour"])
            .size()
            .unstack(fill_value=0)
        )

        # 补全 0-23 小时
        all_hours = list(range(24))
        for h in all_hours:
            if h not in pivot.columns:
                pivot[h] = 0
        pivot = pivot[sorted(pivot.columns)]

        # 补全 0-6 星期
        for d in range(7):
            if d not in pivot.index:
                pivot.loc[d] = 0
        pivot = pivot.sort_index()

        return {
            "days":   _DAY_LABELS,
            "hours":  [str(h) for h in all_hours],
            "matrix": [
                [int(v) for v in row]
                for row in pivot.values
            ],
        }

    # ── 通用分析方法（适用于任意数据集）────────────────────────

    def numeric_distributions(self, max_cols: int = 6) -> list[dict]:
        """
        返回 Top N 数值列的直方图数据。

        Returns: [{"col": str, "bins": list, "counts": list, "mean": float, "std": float}]
        """
        num_cols = list(self.df.select_dtypes(include="number").columns)[:max_cols]
        result = []
        for col in num_cols:
            series = self.df[col].dropna()
            if len(series) == 0:
                continue
            counts, bin_edges = np.histogram(series, bins=30)
            result.append({
                "col":    col,
                "bins":   [round(float(x), 4) for x in bin_edges[:-1]],
                "counts": [int(x) for x in counts],
                "mean":   round(float(series.mean()), 4),
                "std":    round(float(series.std()), 4),
            })
        return result

    def category_distributions(self, max_cols: int = 4,
                                max_categories: int = 20) -> list[dict]:
        """
        返回低基数类别列的频次数据。

        Returns: [{"col": str, "labels": list, "counts": list}]
        """
        cat_cols = [
            c for c in self.df.select_dtypes(include=["object", "category"]).columns
            if self.df[c].nunique() <= max_categories
        ][:max_cols]
        result = []
        for col in cat_cols:
            vc = self.df[col].value_counts()
            result.append({
                "col":    col,
                "labels": [str(x) for x in vc.index.tolist()],
                "counts": [int(x) for x in vc.values.tolist()],
            })
        return result

    def scatter_top_pairs(self, n_pairs: int = 3, sample_n: int = 500) -> list[dict]:
        """
        取相关性最高的 N 对数值列返回散点图数据（最多 sample_n 个采样点）。

        Returns: [{"x_col": str, "y_col": str, "x": list, "y": list, "corr": float}]
        """
        num_cols = list(self.df.select_dtypes(include="number").columns)
        if len(num_cols) < 2:
            return []
        corr_matrix = self.df[num_cols].corr().abs()
        pairs: list[tuple[float, str, str]] = []
        seen: set[frozenset] = set()
        for i, c1 in enumerate(num_cols):
            for c2 in num_cols[i + 1:]:
                key = frozenset([c1, c2])
                if key not in seen:
                    seen.add(key)
                    pairs.append((corr_matrix.loc[c1, c2], c1, c2))
        pairs.sort(reverse=True)
        result = []
        for corr_val, c1, c2 in pairs[:n_pairs]:
            sub = self.df[[c1, c2]].dropna()
            if len(sub) > sample_n:
                sub = sub.sample(sample_n, random_state=42)
            result.append({
                "x_col": c1,
                "y_col": c2,
                "x":     [round(float(v), 4) for v in sub[c1].tolist()],
                "y":     [round(float(v), 4) for v in sub[c2].tolist()],
                "corr":  round(float(corr_val), 4),
            })
        return result

    def box_plots(self, max_cols: int = 6) -> list[dict]:
        """
        返回数值列的箱线图统计数据。

        Returns: [{"col": str, "q1": float, "median": float, "q3": float,
                   "lower": float, "upper": float, "outliers": list}]
        """
        num_cols = list(self.df.select_dtypes(include="number").columns)[:max_cols]
        result = []
        for col in num_cols:
            series = self.df[col].dropna()
            if len(series) == 0:
                continue
            q1 = float(series.quantile(0.25))
            q3 = float(series.quantile(0.75))
            iqr = q3 - q1
            lower = q1 - 1.5 * iqr
            upper = q3 + 1.5 * iqr
            outliers = series[(series < lower) | (series > upper)].tolist()
            result.append({
                "col":      col,
                "q1":       round(q1, 4),
                "median":   round(float(series.median()), 4),
                "q3":       round(q3, 4),
                "lower":    round(lower, 4),
                "upper":    round(upper, 4),
                "outliers": [round(float(x), 4) for x in outliers[:50]],
            })
        return result

    def preprocess_visual(self, pp_report: dict) -> dict:
        """
        生成预处理可视化数据（行数阶段图 + 缺失值热力图）。

        Returns:
          {
            "pipeline_stages": [{"stage": str, "rows": int, "label": str}],
            "cells_filled": int,
            "missing_heatmap": [{"col": str, "missing_count": int, "missing_pct": float}]
          }
        """
        # ── 使用正确的 key 路径读取 pp_report ───────────────
        dup  = pp_report.get("remove_duplicates") or {}
        inv  = pp_report.get("filter_invalid_records") or {}
        miss = pp_report.get("handle_missing") or {}

        dup_removed = int(dup.get("removed", 0))
        inv_removed = int(inv.get("removed", 0))
        cells_filled = int(sum((miss.get("filled_cols") or {}).values()))

        rows_final     = len(self.df)
        rows_after_inv = rows_final + inv_removed
        rows_orig      = rows_after_inv + dup_removed

        # 各阶段行数（展示 Pipeline 中行数的变化趋势）
        pipeline_stages = [
            {"stage": "原始数据",  "rows": rows_orig,      "label": f"{rows_orig:,}"},
            {"stage": "去重后",    "rows": rows_after_inv,  "label": f"-{dup_removed:,}" if dup_removed else "无变化"},
            {"stage": "无效过滤后","rows": rows_final,      "label": f"-{inv_removed:,}" if inv_removed else "无变化"},
        ]

        missing_heatmap = []
        for col in self.df.columns:
            mc = int(self.df[col].isnull().sum())
            missing_heatmap.append({
                "col":           col,
                "missing_count": mc,
                "missing_pct":   round(mc / max(len(self.df), 1) * 100, 2),
            })

        return {
            "pipeline_stages": pipeline_stages,
            "cells_filled":    cells_filled,
            "missing_heatmap": missing_heatmap,
        }
