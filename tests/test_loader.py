"""
data/loader.py 单元测试
来源：学生+AI
"""
import os
import json
import pytest
import pandas as pd

# ── 测试夹具：在临时目录生成测试文件 ──────────────────────────

@pytest.fixture
def sample_df() -> pd.DataFrame:
    """标准测试 DataFrame（3 行 3 列）。"""
    return pd.DataFrame({
        "name":  ["Alice", "Bob", "Charlie"],
        "score": [90, 85, 92],
        "city":  ["Beijing", "Shanghai", "Guangzhou"],
    })


@pytest.fixture
def csv_file(tmp_path, sample_df) -> str:
    """写入临时 CSV 文件，返回文件路径。"""
    path = str(tmp_path / "test.csv")
    sample_df.to_csv(path, index=False, encoding="utf-8")
    return path


@pytest.fixture
def excel_file(tmp_path, sample_df) -> str:
    """写入临时 Excel 文件，返回文件路径。"""
    path = str(tmp_path / "test.xlsx")
    sample_df.to_excel(path, index=False)
    return path


@pytest.fixture
def json_file(tmp_path, sample_df) -> str:
    """写入临时 JSON 文件（records 格式），返回文件路径。"""
    path = str(tmp_path / "test.json")
    sample_df.to_json(path, orient="records", force_ascii=False)
    return path


@pytest.fixture
def gbk_csv_file(tmp_path) -> str:
    """写入 GBK 编码的 CSV 文件，包含中文字符。"""
    path = str(tmp_path / "gbk_test.csv")
    df = pd.DataFrame({"商品": ["苹果", "香蕉"], "价格": [5.5, 3.2]})
    df.to_csv(path, index=False, encoding="gbk")
    return path


# ── 正常功能测试 ───────────────────────────────────────────

class TestLoadCsv:
    def test_returns_dataframe(self, csv_file):
        from data.loader import load_file
        df = load_file(csv_file)
        assert isinstance(df, pd.DataFrame)

    def test_correct_rows(self, csv_file, sample_df):
        from data.loader import load_file
        df = load_file(csv_file)
        assert len(df) == len(sample_df)

    def test_correct_columns(self, csv_file, sample_df):
        from data.loader import load_file
        df = load_file(csv_file)
        assert list(df.columns) == list(sample_df.columns)

    def test_correct_values(self, csv_file):
        from data.loader import load_file
        df = load_file(csv_file)
        assert df["name"].iloc[0] == "Alice"
        assert df["score"].iloc[1] == 85


class TestLoadExcel:
    def test_returns_dataframe(self, excel_file):
        from data.loader import load_file
        df = load_file(excel_file)
        assert isinstance(df, pd.DataFrame)

    def test_correct_shape(self, excel_file, sample_df):
        from data.loader import load_file
        df = load_file(excel_file)
        assert df.shape == sample_df.shape


class TestLoadJson:
    def test_returns_dataframe(self, json_file):
        from data.loader import load_file
        df = load_file(json_file)
        assert isinstance(df, pd.DataFrame)

    def test_correct_rows(self, json_file, sample_df):
        from data.loader import load_file
        df = load_file(json_file)
        assert len(df) == len(sample_df)


class TestEncodingDetection:
    def test_gbk_csv_reads_correctly(self, gbk_csv_file):
        """自动检测 GBK 编码，不应抛异常且列名正确。"""
        from data.loader import load_file
        df = load_file(gbk_csv_file)
        assert isinstance(df, pd.DataFrame)
        assert "商品" in df.columns
        assert "苹果" in df["商品"].values


# ── 异常处理测试 ───────────────────────────────────────────

class TestErrors:
    def test_unsupported_extension_raises(self, tmp_path):
        from data.loader import load_file, UnsupportedFormatError
        bad_file = str(tmp_path / "data.txt")
        with open(bad_file, "w") as f:
            f.write("hello")
        with pytest.raises(UnsupportedFormatError):
            load_file(bad_file)

    def test_nonexistent_file_raises(self):
        from data.loader import load_file
        with pytest.raises(FileNotFoundError):
            load_file("/nonexistent/path/data.csv")

    def test_empty_csv_returns_empty_dataframe(self, tmp_path):
        """空 CSV（只有表头）应返回空 DataFrame，不报错。"""
        from data.loader import load_file
        path = str(tmp_path / "empty.csv")
        with open(path, "w") as f:
            f.write("col1,col2\n")
        df = load_file(path)
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 0
        assert list(df.columns) == ["col1", "col2"]
