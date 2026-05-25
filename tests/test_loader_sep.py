# tests/test_loader_sep.py
import pytest
import pandas as pd
from data.loader import load_file
import tempfile, os

def _write_csv(content: str, suffix=".csv") -> str:
    f = tempfile.NamedTemporaryFile(mode="w", suffix=suffix, delete=False, encoding="utf-8")
    f.write(content)
    f.close()
    return f.name

def test_semicolon_separator():
    """分号分隔符 CSV 应正确解析为多列"""
    path = _write_csv("a;b;c\n1;2;3\n4;5;6\n")
    try:
        df = load_file(path)
        assert list(df.columns) == ["a", "b", "c"]
        assert len(df) == 2
    finally:
        os.unlink(path)

def test_tab_separator():
    path = _write_csv("x\ty\n10\t20\n")
    try:
        df = load_file(path)
        assert list(df.columns) == ["x", "y"]
    finally:
        os.unlink(path)

def test_comma_separator_unchanged():
    path = _write_csv("name,age\nAlice,30\nBob,25\n")
    try:
        df = load_file(path)
        assert list(df.columns) == ["name", "age"]
    finally:
        os.unlink(path)
