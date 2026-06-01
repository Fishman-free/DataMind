"""
tests/test_preprocess_visualizer.py — 预处理可视化模块单元测试
来源：学生+AI
"""
import base64
import numpy as np
import pandas as pd
import pytest
from data.preprocess_visualizer import PreprocessVisualizer


@pytest.fixture
def sample_data():
    rng = np.random.default_rng(42)
    raw = pd.DataFrame({
        "Quantity":  rng.integers(1, 100, 200).astype(float),
        "UnitPrice": rng.uniform(0.5, 50.0, 200),
        "Country":   np.where(rng.random(200) < 0.1, None, "UK"),
        "Category":  rng.choice(["A", "B", "C"], 200),
    })
    raw.loc[5:15, "UnitPrice"] = np.nan
    clean = raw.dropna().reset_index(drop=True)
    pp_report = {
        "original_rows": 200,
        "remove_duplicates": {"removed": 3, "before": 200, "after": 197},
        "filter_invalid_records": {"removed": 5, "before": 197, "after": 192},
        "handle_missing": {
            "filled_cols": {"UnitPrice": 11, "Country": 20},
            "high_missing_cols": [],
        },
        "convert_types": {"converted": {"Country": "category"}},
        "filter_outliers": {"flagged": 4, "detail": {"Quantity": 4}},
    }
    return raw, clean, pp_report


def test_generate_all_returns_five_charts(sample_data):
    raw, clean, pp = sample_data
    viz = PreprocessVisualizer(raw, clean, pp)
    result = viz.generate_all()
    assert "charts" in result
    assert len(result["charts"]) == 5


def test_each_chart_has_required_fields(sample_data):
    raw, clean, pp = sample_data
    viz = PreprocessVisualizer(raw, clean, pp)
    result = viz.generate_all()
    for chart in result["charts"]:
        assert "title" in chart, f"缺少 title: {chart}"
        assert "img" in chart, f"缺少 img: {chart}"
        assert "desc" in chart, f"缺少 desc: {chart}"


def test_img_is_valid_base64_png(sample_data):
    raw, clean, pp = sample_data
    viz = PreprocessVisualizer(raw, clean, pp)
    result = viz.generate_all()
    for chart in result["charts"]:
        assert chart["img"].startswith("data:image/png;base64,"), \
            f"img 格式不正确: {chart['title']}"
        b64 = chart["img"].split(",", 1)[1]
        decoded = base64.b64decode(b64)
        assert len(decoded) > 100, "base64 内容过短，可能为空图"


def test_works_with_empty_pp_report(sample_data):
    raw, clean, _ = sample_data
    viz = PreprocessVisualizer(raw, clean, {})
    result = viz.generate_all()
    assert len(result["charts"]) == 5


def test_api_returns_five_charts_keys(sample_data):
    raw, clean, pp = sample_data
    viz = PreprocessVisualizer(raw, clean, pp)
    result = viz.generate_all()
    titles = [c["title"] for c in result["charts"]]
    assert "缺失值分布热力图"    in titles
    assert "预处理流水线行数变化"  in titles
    assert "数值列异常值箱线图"   in titles
    assert "列数据类型分布"       in titles
    assert "缺失值填充前后对比"   in titles
