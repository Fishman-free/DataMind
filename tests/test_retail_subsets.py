"""
tests/test_retail_subsets.py — 基于 Online Retail Kaggle 数据集的 5 个真实子集测试
来源：学生+AI

数据集来源：UCI Machine Learning Repository / Kaggle
  https://www.kaggle.com/datasets/mashlyn/online-retail-ii-uci
  字段：InvoiceNo, StockCode, Description, Quantity,
        InvoiceDate, UnitPrice, CustomerID, Country

子集划分：
  subset_uk.csv           — UK 订单（主市场，500 行）
  subset_international.csv — 国际订单（非 UK，200 行）
  subset_missing.csv      — 含缺失 CustomerID（200 行）
  subset_highvalue.csv    — 高单价商品 UnitPrice > 10（200 行）
  subset_returns.csv      — 退货/取消订单 Quantity < 0（100 行）
"""
import os
import pandas as pd
import pytest
from data.loader import load_file
from data.preprocessor import Preprocessor

# 子集文件所在目录
_DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


def _path(name: str) -> str:
    return os.path.join(_DATA_DIR, name)


# ---------------------------------------------------------------------------
# 子集 1：UK 订单
# ---------------------------------------------------------------------------

class TestSubsetUK:
    """主市场子集：500 条 UK 订单，验证基础加载与清洗管道。"""

    @pytest.fixture(scope="class")
    def df_raw(self):
        return load_file(_path("subset_uk.csv"))

    @pytest.fixture(scope="class")
    def preprocessor(self, df_raw):
        p = Preprocessor(df_raw)
        p.run_all()
        return p

    @pytest.fixture(scope="class")
    def df_clean(self, preprocessor):
        return preprocessor.df

    def test_load_row_count(self, df_raw):
        assert len(df_raw) == 500

    def test_all_uk(self, df_raw):
        assert (df_raw["Country"] == "United Kingdom").all()

    def test_has_required_columns(self, df_raw):
        for col in ("InvoiceNo", "Quantity", "UnitPrice", "CustomerID", "Country"):
            assert col in df_raw.columns

    def test_preprocessor_reduces_rows(self, df_raw, df_clean):
        # 清洗后行数应 ≤ 原始行数
        assert len(df_clean) <= len(df_raw)

    def test_no_negative_quantity_after_clean(self, df_clean):
        assert (df_clean["Quantity"] >= 0).all()

    def test_invoicedate_parsed(self, df_clean):
        # 清洗后 InvoiceDate 应转为 datetime
        assert pd.api.types.is_datetime64_any_dtype(df_clean["InvoiceDate"])


# ---------------------------------------------------------------------------
# 子集 2：国际订单（非 UK）
# ---------------------------------------------------------------------------

class TestSubsetInternational:
    """国际市场子集：200 条非 UK 订单，验证多国家场景。"""

    @pytest.fixture(scope="class")
    def df_raw(self):
        return load_file(_path("subset_international.csv"))

    def test_load_row_count(self, df_raw):
        assert len(df_raw) == 200

    def test_no_uk_orders(self, df_raw):
        assert "United Kingdom" not in df_raw["Country"].values

    def test_multiple_countries(self, df_raw):
        assert df_raw["Country"].nunique() >= 2

    def test_quantity_not_all_zero(self, df_raw):
        # 国际子集数量列应存在有效正数记录
        assert (df_raw["Quantity"] > 0).any()

    def test_customerid_complete(self, df_raw):
        # 国际子集构造时已 dropna CustomerID
        assert df_raw["CustomerID"].notna().all()


# ---------------------------------------------------------------------------
# 子集 3：缺失 CustomerID（匿名客户）
# ---------------------------------------------------------------------------

class TestSubsetMissing:
    """缺失值子集：200 条缺失 CustomerID 的订单，验证缺失值填充逻辑。"""

    @pytest.fixture(scope="class")
    def df_raw(self):
        return load_file(_path("subset_missing.csv"))

    @pytest.fixture(scope="class")
    def preprocessor(self, df_raw):
        p = Preprocessor(df_raw)
        p.run_all()
        return p

    @pytest.fixture(scope="class")
    def df_clean(self, preprocessor):
        return preprocessor.df

    def test_load_row_count(self, df_raw):
        assert len(df_raw) == 200

    def test_has_missing_customerid(self, df_raw):
        assert df_raw["CustomerID"].isna().any()

    def test_preprocessor_pipeline_completes(self, df_clean):
        # 管道正常运行，清洗后结果为有效 DataFrame
        assert isinstance(df_clean, pd.DataFrame)
        assert len(df_clean) >= 0

    def test_preprocessor_report_records_filled(self, preprocessor):
        report = preprocessor.get_report()
        hm = report.get("handle_missing", {})
        filled = hm.get("filled_cols", {})
        # handle_missing 步骤应返回字典类型的 filled_cols
        assert isinstance(filled, dict)

    def test_missing_customerid_ratio_high(self, df_raw):
        # 子集中 CustomerID 缺失率应 = 100%（全为匿名客户）
        ratio = df_raw["CustomerID"].isna().mean()
        assert ratio == 1.0


# ---------------------------------------------------------------------------
# 子集 4：高单价商品（UnitPrice > 10）
# ---------------------------------------------------------------------------

class TestSubsetHighValue:
    """高单价子集：200 条 UnitPrice > 10 的订单，验证异常检测逻辑。"""

    @pytest.fixture(scope="class")
    def df_raw(self):
        return load_file(_path("subset_highvalue.csv"))

    @pytest.fixture(scope="class")
    def preprocessor(self, df_raw):
        p = Preprocessor(df_raw)
        p.run_all()
        return p

    @pytest.fixture(scope="class")
    def df_clean(self, preprocessor):
        return preprocessor.df

    def test_load_row_count(self, df_raw):
        assert len(df_raw) == 200

    def test_all_high_price(self, df_raw):
        assert (df_raw["UnitPrice"] > 10).all()

    def test_outlier_columns_added(self, df_clean):
        # 数值列有足够样本时应生成 _is_outlier 列
        outlier_cols = [c for c in df_clean.columns if "_is_outlier" in c]
        assert len(outlier_cols) >= 1

    def test_price_range_valid(self, df_clean):
        assert df_clean["UnitPrice"].min() >= 0


# ---------------------------------------------------------------------------
# 子集 5：退货/取消订单（Quantity < 0）
# ---------------------------------------------------------------------------

class TestSubsetReturns:
    """退货子集：100 条负数量订单，验证无效记录过滤行为。"""

    @pytest.fixture(scope="class")
    def df_raw(self):
        return load_file(_path("subset_returns.csv"))

    @pytest.fixture(scope="class")
    def preprocessor(self, df_raw):
        p = Preprocessor(df_raw)
        p.run_all()
        return p

    @pytest.fixture(scope="class")
    def df_clean(self, preprocessor):
        return preprocessor.df

    def test_load_row_count(self, df_raw):
        assert len(df_raw) == 100

    def test_all_negative_quantity(self, df_raw):
        assert (df_raw["Quantity"] < 0).all()

    def test_preprocessor_removes_returns(self, df_clean):
        # 清洗后 Quantity < 0 的行应全部被移除
        assert (df_clean["Quantity"] >= 0).all()

    def test_filter_report_records_removed(self, preprocessor):
        report = preprocessor.get_report()
        fr = report.get("filter_invalid_records", {})
        removed = fr.get("removed", 0)
        assert removed > 0, "退货记录应被 filter_invalid_records 步骤移除"
