"""
数据文件读取模块
支持 CSV / Excel (.xlsx) / JSON，自动检测编码。
来源：学生+AI
"""
from __future__ import annotations

import csv
import os
from pathlib import Path

import chardet
import pandas as pd


# ── 自定义异常 ────────────────────────────────────────────

class UnsupportedFormatError(ValueError):
    """文件格式不在支持列表中时抛出。"""


# ── 内部工具函数 ──────────────────────────────────────────

def _detect_encoding(file_path: str) -> str:
    """
    用 chardet 检测文件编码。
    检测失败（置信度 < 0.6）时回退到 utf-8。
    """
    with open(file_path, "rb") as f:
        raw = f.read(min(os.path.getsize(file_path), 100_000))  # 最多读 100KB 用于检测
    result = chardet.detect(raw)
    confidence = result.get("confidence") or 0
    encoding = result.get("encoding") or "utf-8"
    return encoding if confidence >= 0.6 else "utf-8"


def _detect_separator(file_path: str, encoding: str) -> str:
    """用 csv.Sniffer 自动检测分隔符，候选集: , ; \\t |"""
    try:
        with open(file_path, encoding=encoding, errors="replace") as f:
            sample = f.read(8192)
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        return dialect.delimiter
    except csv.Error:
        return ","


def _read_csv(file_path: str) -> pd.DataFrame:
    """
    读取 CSV，自动检测编码和分隔符。
    编码优先级：chardet → utf-8 → gbk → latin1
    分隔符：csv.Sniffer 自动嗅探（, ; \\t |），失败回退逗号
    """
    encodings = [_detect_encoding(file_path), "utf-8", "gbk", "latin1"]
    seen: set[str] = set()
    unique_encodings = [e for e in encodings if not (e in seen or seen.add(e))]  # type: ignore[func-returns-value]

    last_err: Exception = Exception("unknown")
    for enc in unique_encodings:
        try:
            sep = _detect_separator(file_path, enc)
            return pd.read_csv(file_path, encoding=enc, sep=sep)
        except (UnicodeDecodeError, LookupError) as e:
            last_err = e
            continue

    raise UnicodeDecodeError(
        "utf-8", b"", 0, 1,
        f"无法解析文件编码，尝试了 {unique_encodings}。原始错误：{last_err}",
    )


def _read_excel(file_path: str) -> pd.DataFrame:
    """
    读取 Excel（.xlsx / .xls）。
    优先使用 calamine 引擎（Rust 实现，比 openpyxl 快 5x）；
    calamine 不可用时自动降级为 openpyxl。
    """
    try:
        return pd.read_excel(file_path, engine="calamine")
    except ImportError:
        return pd.read_excel(file_path, engine="openpyxl")


def _read_json(file_path: str) -> pd.DataFrame:
    """
    读取 JSON 文件。
    支持 records 格式 [{...}, ...] 和 columns 格式（pandas 默认）。
    """
    try:
        return pd.read_json(file_path, encoding="utf-8")
    except ValueError:
        # 尝试 records 格式
        import json
        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return pd.DataFrame(data)
        raise


# ── 公开接口 ──────────────────────────────────────────────

_READERS = {
    ".csv":  _read_csv,
    ".xlsx": _read_excel,
    ".xls":  _read_excel,
    ".json": _read_json,
}


def load_file(file_path: str) -> pd.DataFrame:
    """
    根据文件后缀自动选择读取方式，返回统一的 DataFrame。

    Parameters
    ----------
    file_path : str
        数据文件的绝对或相对路径。

    Returns
    -------
    pd.DataFrame
        读取到的数据表，列名保持原文件列名。

    Raises
    ------
    FileNotFoundError
        文件路径不存在。
    UnsupportedFormatError
        文件后缀不在支持列表（.csv / .xlsx / .xls / .json）中。
    """
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"文件不存在：{file_path}")

    suffix = path.suffix.lower()
    reader = _READERS.get(suffix)

    if reader is None:
        supported = ", ".join(_READERS.keys())
        raise UnsupportedFormatError(
            f"不支持的文件格式：{suffix}。支持的格式：{supported}"
        )

    return reader(str(path))
