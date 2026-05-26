# tests/test_analyzer_generic.py
import numpy as np
import pandas as pd
import pytest
from data.analyzer import Analyzer

@pytest.fixture
def num_df():
    rng = np.random.default_rng(0)
    return pd.DataFrame({
        "a": rng.uniform(0, 10, 100),
        "b": rng.uniform(0, 5, 100),
        "c": rng.uniform(1, 3, 100),
        "quality": rng.integers(3, 9, 100),
    })

@pytest.fixture
def cat_df():
    return pd.DataFrame({
        "color": ["red","blue","green"] * 34,
        "size":  ["S","M","L","XL"] * 25 + ["S","S"],
        "score": range(102),
    })

def test_numeric_distributions(num_df):
    az = Analyzer(num_df)
    result = az.numeric_distributions(max_cols=3)
    assert len(result) == 3
    assert "col" in result[0]
    assert "bins" in result[0]
    assert "counts" in result[0]
    assert len(result[0]["bins"]) == len(result[0]["counts"])

def test_category_distributions(cat_df):
    az = Analyzer(cat_df)
    result = az.category_distributions()
    assert len(result) >= 1
    assert "col" in result[0]
    assert "labels" in result[0]
    assert "counts" in result[0]

def test_scatter_top_pairs_returns_pairs(num_df):
    az = Analyzer(num_df)
    result = az.scatter_top_pairs(n_pairs=2)
    assert len(result) <= 2
    if result:
        assert "x_col" in result[0]
        assert "y_col" in result[0]
        assert len(result[0]["x"]) <= 500

def test_box_plots(num_df):
    az = Analyzer(num_df)
    result = az.box_plots(max_cols=4)
    assert len(result) >= 1
    assert "col" in result[0]
    assert "q1" in result[0]
    assert "median" in result[0]
    assert "q3" in result[0]

def test_preprocess_visual_no_crash(num_df):
    az = Analyzer(num_df)
    # 使用新格式的 pp_report（嵌套 key 结构）
    pp_report = {
        "remove_duplicates":       {"removed": 5, "before": 105, "after": 100},
        "handle_missing":          {"filled_cols": {"a": 2}, "high_missing_cols": []},
        "filter_invalid_records":  {"removed": 0, "before": 100, "after": 100},
    }
    result = az.preprocess_visual(pp_report)
    assert "pipeline_stages" in result
    assert "missing_heatmap" in result
    assert "cells_filled" in result
    # 验证 pipeline_stages 包含 3 个阶段
    assert len(result["pipeline_stages"]) == 3
    # 验证 cells_filled 正确（a 列填充 2 个）
    assert result["cells_filled"] == 2
