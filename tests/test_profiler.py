# tests/test_profiler.py
import pandas as pd
import numpy as np
import pytest
from data.profiler import DataProfiler

@pytest.fixture
def wine_df():
    rng = np.random.default_rng(42)
    data = {col: rng.uniform(0, 10, 50) for col in
            ["fixed acidity","volatile acidity","citric acid","residual sugar",
             "chlorides","free sulfur dioxide","total sulfur dioxide","density",
             "pH","sulphates","alcohol"]}
    data["quality"] = rng.integers(3, 9, 50)
    return pd.DataFrame(data)

@pytest.fixture
def retail_df():
    return pd.DataFrame({
        "InvoiceDate": pd.date_range("2021-01-01", periods=100, freq="D"),
        "CustomerID": range(100),
        "Description": ["Product"] * 100,
        "Quantity": [1] * 100,
        "UnitPrice": [9.99] * 100,
        "Country": ["UK"] * 100,
    })

@pytest.fixture
def categorical_df():
    return pd.DataFrame({
        "gender": ["M","F","F","M"] * 25,
        "education": ["高中","大学","研究生","高中"] * 25,
        "satisfaction": ["高","中","低","高"] * 25,
        "age": range(100),
    })

def test_wine_detected_as_numeric(wine_df):
    p = DataProfiler(wine_df)
    result = p.detect()
    assert result["mode"] == "numeric"
    assert result["display_name"] == "科学数值型"
    assert "alcohol" in result["numeric_cols"]
    assert result["target_col"] == "quality"
    assert result["has_date"] is False

def test_retail_detected_as_retail(retail_df):
    p = DataProfiler(retail_df)
    result = p.detect()
    assert result["mode"] == "retail"

def test_categorical_detected(categorical_df):
    p = DataProfiler(categorical_df)
    result = p.detect()
    assert result["mode"] in ("categorical", "mixed")
    assert "gender" in result["categorical_cols"]

def test_col_info_has_samples(wine_df):
    p = DataProfiler(wine_df)
    result = p.detect()
    assert "alcohol" in result["col_info"]
    assert len(result["col_info"]["alcohol"]["samples"]) == 3

def test_suggested_questions_nonempty(wine_df):
    p = DataProfiler(wine_df)
    result = p.detect()
    assert len(result["suggested_questions"]) >= 3

def test_description_nonempty(wine_df):
    p = DataProfiler(wine_df)
    result = p.detect()
    assert len(result["description"]) > 20
