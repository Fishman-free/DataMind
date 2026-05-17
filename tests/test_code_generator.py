"""
ai/code_generator.py 单元测试
来源：学生+AI
"""
import pytest
import numpy as np
import pandas as pd
from unittest.mock import MagicMock, patch


@pytest.fixture
def sample_df() -> pd.DataFrame:
    return pd.DataFrame({
        "Quantity":    [5, 3, 2, 10, 1],
        "UnitPrice":   [2.5, 1.0, 2.5, 8.0, 1.0],
        "TotalAmount": [12.5, 3.0, 5.0, 80.0, 1.0],
        "Country":     ["UK", "UK", "France", "UK", "Germany"],
    })


@pytest.fixture
def mock_openai_client():
    """模拟 OpenAI 客户端，返回包含 Python 代码的标准响应。"""
    client = MagicMock()
    response = MagicMock()
    response.choices[0].message.content = (
        "根据数据，各国销售额如下：\n\n"
        "```python\n"
        "result = df.groupby('Country')['TotalAmount'].sum().to_dict()\n"
        "```"
    )
    client.chat.completions.create.return_value = response
    return client


# ── validate_code ────────────────────────────────────────────

class TestValidateCode:
    def test_safe_code_returns_true(self):
        from ai.code_generator import CodeGenerator
        cg = CodeGenerator(MagicMock())
        assert cg.validate_code("result = df['TotalAmount'].sum()") is True

    def test_import_os_blocked(self):
        from ai.code_generator import CodeGenerator
        cg = CodeGenerator(MagicMock())
        assert cg.validate_code("import os\nos.system('rm -rf /')") is False

    def test_import_sys_blocked(self):
        from ai.code_generator import CodeGenerator
        cg = CodeGenerator(MagicMock())
        assert cg.validate_code("import sys") is False

    def test_subprocess_blocked(self):
        from ai.code_generator import CodeGenerator
        cg = CodeGenerator(MagicMock())
        assert cg.validate_code("import subprocess") is False

    def test_open_call_blocked(self):
        from ai.code_generator import CodeGenerator
        cg = CodeGenerator(MagicMock())
        assert cg.validate_code("f = open('secret.txt')") is False

    def test_eval_blocked(self):
        from ai.code_generator import CodeGenerator
        cg = CodeGenerator(MagicMock())
        assert cg.validate_code("eval('1+1')") is False

    def test_exec_blocked(self):
        from ai.code_generator import CodeGenerator
        cg = CodeGenerator(MagicMock())
        assert cg.validate_code("exec('x=1')") is False

    def test_pandas_code_allowed(self):
        from ai.code_generator import CodeGenerator
        cg = CodeGenerator(MagicMock())
        code = "result = df.groupby('Country')['TotalAmount'].sum().reset_index()"
        assert cg.validate_code(code) is True


# ── execute_safe ─────────────────────────────────────────────

class TestExecuteSafe:
    def test_returns_dict(self, sample_df):
        from ai.code_generator import CodeGenerator
        cg = CodeGenerator(MagicMock())
        result = cg.execute_safe("result = df['TotalAmount'].sum()", sample_df)
        assert isinstance(result, dict)

    def test_has_success_key(self, sample_df):
        from ai.code_generator import CodeGenerator
        cg = CodeGenerator(MagicMock())
        result = cg.execute_safe("result = df['TotalAmount'].sum()", sample_df)
        assert "success" in result

    def test_successful_execution(self, sample_df):
        from ai.code_generator import CodeGenerator
        cg = CodeGenerator(MagicMock())
        result = cg.execute_safe("result = df['TotalAmount'].sum()", sample_df)
        assert result["success"] is True
        assert abs(result["result"] - 101.5) < 0.01

    def test_syntax_error_returns_failure(self, sample_df):
        from ai.code_generator import CodeGenerator
        cg = CodeGenerator(MagicMock())
        result = cg.execute_safe("result = df[[[[[", sample_df)
        assert result["success"] is False
        assert "error" in result

    def test_runtime_error_returns_failure(self, sample_df):
        from ai.code_generator import CodeGenerator
        cg = CodeGenerator(MagicMock())
        result = cg.execute_safe("result = df['nonexistent_col'].sum()", sample_df)
        assert result["success"] is False

    def test_dangerous_code_blocked(self, sample_df):
        from ai.code_generator import CodeGenerator
        cg = CodeGenerator(MagicMock())
        result = cg.execute_safe("import os; result = os.getcwd()", sample_df)
        assert result["success"] is False
        assert "blocked" in result.get("error", "").lower()

    def test_no_result_variable_returns_none(self, sample_df):
        from ai.code_generator import CodeGenerator
        cg = CodeGenerator(MagicMock())
        result = cg.execute_safe("x = 1 + 1", sample_df)
        assert result["success"] is True
        assert result["result"] is None


# ── generate ─────────────────────────────────────────────────

class TestGenerate:
    def test_returns_dict(self, mock_openai_client, sample_df):
        from ai.code_generator import CodeGenerator
        cg = CodeGenerator(mock_openai_client)
        result = cg.generate("各国销售额是多少", [], {"row_count": 5}, sample_df)
        assert isinstance(result, dict)

    def test_has_required_keys(self, mock_openai_client, sample_df):
        from ai.code_generator import CodeGenerator
        cg = CodeGenerator(mock_openai_client)
        result = cg.generate("各国销售额", [], {"row_count": 5}, sample_df)
        assert "answer" in result
        assert "code" in result
        assert "success" in result

    def test_extracts_code_from_response(self, mock_openai_client, sample_df):
        from ai.code_generator import CodeGenerator
        cg = CodeGenerator(mock_openai_client)
        result = cg.generate("各国销售额", [], {"row_count": 5}, sample_df)
        # mock 响应中包含 groupby 代码
        assert "groupby" in result.get("code", "")

    def test_openai_error_returns_failure(self, sample_df):
        from ai.code_generator import CodeGenerator
        client = MagicMock()
        client.chat.completions.create.side_effect = Exception("API timeout")
        cg = CodeGenerator(client)
        result = cg.generate("问题", [], {}, sample_df)
        assert result["success"] is False
        assert "error" in result
