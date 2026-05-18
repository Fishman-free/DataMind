"""
数据预处理模块 — Pipeline 链式清洗。

处理顺序：去重 → 缺失值 → 类型转换 → 异常标记 → 特征工程

来源：学生+AI
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

# 缺失率超过此阈值的列只警告，不自动处理
_HIGH_MISSING_THRESHOLD = 0.5


def _fill_value_for_numeric(series: "pd.Series") -> float:
    """
    根据偏态系数选择填充值：
    - |skew| > 1.0 或 skew 为 NaN → 中位数（抗偏态）
    - |skew| <= 1.0 → 均值（分布对称时更准确）
    """
    try:
        skew = float(series.skew())
    except Exception:
        skew = float("nan")
    if pd.isna(skew) or abs(skew) > 1.0:
        return float(series.median())
    return float(series.mean())


def _fill_value_for_text(series: "pd.Series") -> str:
    """
    低基数分类列（n_unique<=10, n_total>=3, 唯一率<=50%）用众数；
    否则用 "Unknown"。
    """
    non_null = series.dropna()
    n_total = len(non_null)
    n_unique = non_null.nunique()
    if n_total >= 3 and n_unique <= 10 and (n_unique / n_total) <= 0.5:
        mode_vals = non_null.mode()
        if len(mode_vals) > 0:
            return str(mode_vals.iloc[0])
    return "Unknown"

# 检测是否为数量列（用于计算 TotalAmount）
_QTY_KEYWORDS   = {"quantity", "qty", "count", "数量"}
_PRICE_KEYWORDS = {"unitprice", "price", "unit_price", "单价", "价格"}


def _is_id_like_column(col: str) -> bool:
    """
    检测是否为 ID 标识类列（如 InvoiceNo / StockCode / CustomerID）。
    这类列不应被自动类型转换或 IQR 异常标记处理。

    规则：列名（去下划线/空格后小写）长度 > 4 且以 id / no / code 结尾。
    """
    normalized = col.lower().replace("_", "").replace(" ", "")
    if len(normalized) > 4:
        return normalized.endswith(("id", "no", "code"))
    return False


class Preprocessor:
    """
    链式数据预处理器。

    用法
    ----
    clean_df = Preprocessor(raw_df).run_all()

    或逐步调用：
    p = Preprocessor(raw_df)
    p.remove_duplicates().handle_missing().convert_types()
    report = p.get_report()
    """

    def __init__(self, df: pd.DataFrame) -> None:
        self.df: pd.DataFrame = df.copy()
        self._original_rows: int = len(df)
        # 每个步骤的日志存储为 {step_name: {key: value}}
        self._log: dict[str, dict[str, Any]] = {}

    # ── 步骤 1：去重 ──────────────────────────────────────

    def remove_duplicates(self) -> "Preprocessor":
        """全行去重，记录删除数量。"""
        before = len(self.df)
        self.df = self.df.drop_duplicates().reset_index(drop=True)
        removed = before - len(self.df)
        self._log["remove_duplicates"] = {"removed": removed, "before": before, "after": len(self.df)}
        return self

    # ── 步骤 1b：文本列清洗 ────────────────────────────────

    def clean_text(self) -> "Preprocessor":
        """
        清洗所有 object 类型列：
        - 去除首尾空格和 Tab
        - 去除 ASCII 控制字符（0x00-0x1f, 0x7f）
        NaN 值不受影响（pandas .str 方法对 NaN 安全）。
        """
        text_cols = list(self.df.select_dtypes(include=["object"]).columns)
        for col in text_cols:
            self.df[col] = self.df[col].str.strip()
            self.df[col] = self.df[col].str.replace(
                r"[\x00-\x1f\x7f]", "", regex=True
            )
        self._log["clean_text"] = {"cleaned_cols": text_cols}
        return self

    # ── 步骤 2：缺失值处理 ────────────────────────────────

    def handle_missing(self) -> "Preprocessor":
        """
        - 数值列：偏态 |skew| > 1.0 → 中位数；否则 → 均值；NaN skew → 中位数
        - 文本列：低基数分类（n_unique<=10, n_total>=3, 唯一率<=50%）→ 众数；否则 → "Unknown"
        - 缺失率 > 50% 的列：记录警告，仍然填充
        """
        filled: dict[str, int] = {}
        high_missing: list[str] = []

        for col in self.df.columns:
            missing_count = self.df[col].isna().sum()
            if missing_count == 0:
                continue

            # ID 标识类列（CustomerID 等）保留 NaN，供下游 dropna 处理
            if _is_id_like_column(col):
                continue

            missing_rate = missing_count / len(self.df)

            if missing_rate > _HIGH_MISSING_THRESHOLD:
                high_missing.append(col)
                # 高缺失率列仍然填充，但额外警告

            if pd.api.types.is_numeric_dtype(self.df[col]):
                fill_val = _fill_value_for_numeric(self.df[col].dropna())
                self.df[col] = self.df[col].fillna(fill_val)
            else:
                fill_val = _fill_value_for_text(self.df[col])
                self.df[col] = self.df[col].fillna(fill_val)

            filled[col] = int(missing_count)

        self._log["handle_missing"] = {
            "filled_cols": filled,
            "high_missing_cols": high_missing,
        }
        return self

    # ── 步骤 3：类型转换 ──────────────────────────────────

    def convert_types(self) -> "Preprocessor":
        """
        - 字符串列：尝试转为 datetime，再尝试转为 numeric
        - 已是 datetime/numeric 的列跳过
        """
        converted: dict[str, str] = {}

        for col in self.df.columns:
            if pd.api.types.is_datetime64_any_dtype(self.df[col]):
                continue
            if pd.api.types.is_numeric_dtype(self.df[col]):
                continue

            # ID 标识类列（InvoiceNo / StockCode）保持原始字符串，不转换
            if _is_id_like_column(col):
                continue

            # 尝试转 datetime
            sample = self.df[col].dropna().head(20).astype(str)
            if _looks_like_datetime(sample):
                converted_col = pd.to_datetime(self.df[col], errors="coerce")
                if converted_col.notna().sum() >= len(self.df[col].dropna()) * 0.7:
                    self.df[col] = converted_col
                    converted[col] = "datetime"
                    continue

            # 尝试转 numeric
            converted_col = pd.to_numeric(self.df[col], errors="coerce")
            if converted_col.notna().sum() >= len(self.df[col].dropna()) * 0.7:
                self.df[col] = converted_col
                converted[col] = "numeric"
                continue

            # 低基数文本列 → Categorical（n_unique <= 20 且唯一率 <= 50%）
            non_null = self.df[col].dropna()
            if len(non_null) >= 3:
                n_unique = non_null.nunique()
                ratio = n_unique / len(non_null)
                if n_unique <= 20 and ratio <= 0.5:
                    self.df[col] = self.df[col].astype("category")
                    converted[col] = "category"

        self._log["convert_types"] = {"converted": converted}
        return self

    # ── 步骤 4：异常值标记（IQR 法）─────────────────────────

    def filter_outliers(self) -> "Preprocessor":
        """
        对所有数值列用两档 IQR 法标记异常值：
        - 轻度（×1.5）：新增 <列名>_is_outlier（bool）
        - 极端（×3.0）：新增 <列名>_is_extreme_outlier（bool）
        不删除行，由用户决定如何处理。
        """
        flagged_total = 0
        detail: dict[str, int] = {}

        for col in self.df.select_dtypes(include=[np.number]).columns:
            # 跳过已是派生列
            if col.endswith("_is_outlier") or col.endswith("_is_extreme_outlier"):
                continue
            # 跳过 ID 标识类列（CustomerID 等，IQR 对其无意义）
            if _is_id_like_column(col):
                continue

            q1 = self.df[col].quantile(0.25)
            q3 = self.df[col].quantile(0.75)
            iqr = q3 - q1

            if iqr == 0:
                self.df[f"{col}_is_outlier"] = False
                self.df[f"{col}_is_extreme_outlier"] = False
                continue

            # 轻度异常：×1.5
            mild_lower = q1 - 1.5 * iqr
            mild_upper = q3 + 1.5 * iqr
            mild_mask = (self.df[col] < mild_lower) | (self.df[col] > mild_upper)
            self.df[f"{col}_is_outlier"] = mild_mask

            # 极端异常：×3.0
            extreme_lower = q1 - 3.0 * iqr
            extreme_upper = q3 + 3.0 * iqr
            extreme_mask = (self.df[col] < extreme_lower) | (self.df[col] > extreme_upper)
            self.df[f"{col}_is_extreme_outlier"] = extreme_mask

            n_flagged = int(mild_mask.sum())
            flagged_total += n_flagged
            if n_flagged > 0:
                detail[col] = n_flagged

        self._log["filter_outliers"] = {"flagged": flagged_total, "detail": detail}
        return self

    # ── 步骤 4b：过滤业务无效记录 ───────────────────────────

    def filter_invalid_records(self) -> "Preprocessor":
        """
        删除业务上无效的记录行：
        - Quantity ≤ 0（退货、取消订单）
        - UnitPrice < 0（错误定价）

        仅当 DataFrame 中存在对应列时生效，缺少相关列时静默跳过。
        """
        before = len(self.df)
        mask = pd.Series([True] * len(self.df), index=self.df.index)

        qty_col   = _find_col(self.df, _QTY_KEYWORDS)
        price_col = _find_col(self.df, _PRICE_KEYWORDS)

        if qty_col and pd.api.types.is_numeric_dtype(self.df[qty_col]):
            mask &= self.df[qty_col] > 0

        if price_col and pd.api.types.is_numeric_dtype(self.df[price_col]):
            mask &= self.df[price_col] >= 0

        self.df = self.df[mask].reset_index(drop=True)
        self._log["filter_invalid_records"] = {
            "removed": before - len(self.df),
            "before": before,
            "after": len(self.df),
        }
        return self

    # ── 步骤 5：特征工程 ──────────────────────────────────

    def add_features(self) -> "Preprocessor":
        """
        - 检测到 datetime 列 → 生成 Year / Month / DayOfWeek / Hour
        - 检测到数量列 + 单价列 → 生成 TotalAmount
        """
        added: list[str] = []

        # 日期特征
        date_cols = [c for c in self.df.columns if pd.api.types.is_datetime64_any_dtype(self.df[c])]
        if date_cols:
            dt = self.df[date_cols[0]]  # 取第一个日期列
            self.df["Year"]       = dt.dt.year
            self.df["Month"]      = dt.dt.month
            self.df["DayOfWeek"]  = dt.dt.dayofweek   # 0=Monday
            self.df["Hour"]       = dt.dt.hour
            added.extend(["Year", "Month", "DayOfWeek", "Hour"])

        # TotalAmount = Quantity × UnitPrice
        qty_col   = _find_col(self.df, _QTY_KEYWORDS)
        price_col = _find_col(self.df, _PRICE_KEYWORDS)
        if qty_col and price_col and "TotalAmount" not in self.df.columns:
            self.df["TotalAmount"] = self.df[qty_col] * self.df[price_col]
            added.append("TotalAmount")

        self._log["add_features"] = {"added": added}
        return self

    # ── run_all & get_report ──────────────────────────────

    def run_all(self) -> pd.DataFrame:
        """按标准顺序执行全部预处理步骤，返回清洁 DataFrame。"""
        return (
            self.remove_duplicates()
                .clean_text()           # 文本列空白/控制字符清洗
                .handle_missing()
                .convert_types()
                .filter_invalid_records()
                .filter_outliers()
                .add_features()
                .df
        )

    def get_report(self) -> dict[str, Any]:
        """返回预处理摘要，包含每步操作的统计信息。"""
        return {
            "original_rows": self._original_rows,
            "final_rows": len(self.df),
            **self._log,
        }


# ── 内部工具函数 ──────────────────────────────────────────

def _looks_like_datetime(sample: pd.Series) -> bool:
    """
    启发式判断字符串序列是否像日期格式。
    尝试转换前 20 个非空值，成功率 > 70% 则认为是日期列。
    """
    if len(sample) == 0:
        return False
    try:
        converted = pd.to_datetime(sample, errors="coerce")
        return converted.notna().mean() > 0.7
    except Exception:
        return False


def _find_col(df: pd.DataFrame, keywords: set[str]) -> str | None:
    """
    在 DataFrame 列名中查找与关键词匹配的列（大小写不敏感）。
    返回第一个匹配的列名，无匹配返回 None。
    """
    for col in df.columns:
        if col.lower().replace(" ", "") in keywords:
            return col
    return None
