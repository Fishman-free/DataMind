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


# ── _sanitize_code & print 捕获 ─────────────────────────────

class TestSanitizeCode:
    def test_import_pandas_stripped(self, sample_df):
        """验证 import pandas as pd 被移除且执行成功。"""
        from ai.code_generator import CodeGenerator
        cg = CodeGenerator(MagicMock())
        code = "import pandas as pd\nresult = df['TotalAmount'].sum()"
        result = cg.execute_safe(code, sample_df)
        assert result["success"] is True
        assert abs(result["result"] - 101.5) < 0.01

    def test_import_numpy_stripped(self, sample_df):
        """验证 import numpy as np 被移除。"""
        from ai.code_generator import CodeGenerator
        cg = CodeGenerator(MagicMock())
        code = "import numpy as np\nresult = np.sum(df['TotalAmount'].values)"
        result = cg.execute_safe(code, sample_df)
        assert result["success"] is True
        assert abs(result["result"] - 101.5) < 0.01

    def test_from_import_stripped(self, sample_df):
        """验证 from pandas import DataFrame 被移除。"""
        from ai.code_generator import CodeGenerator
        cg = CodeGenerator(MagicMock())
        code = "from pandas import DataFrame\nresult = len(df)"
        result = cg.execute_safe(code, sample_df)
        assert result["success"] is True
        assert result["result"] == 5

    def test_print_output_captured(self, sample_df):
        """验证 print 输出进入 stdout 字段。"""
        from ai.code_generator import CodeGenerator
        cg = CodeGenerator(MagicMock())
        code = "print('hello world')\nprint('foo bar')\nresult = 42"
        result = cg.execute_safe(code, sample_df)
        assert result["success"] is True
        assert result["result"] == 42
        assert result["stdout"] is not None
        assert "hello world" in result["stdout"]
        assert "foo bar" in result["stdout"]

    def test_stdout_none_when_no_print(self, sample_df):
        """验证无 print 时 stdout 为 None。"""
        from ai.code_generator import CodeGenerator
        cg = CodeGenerator(MagicMock())
        code = "result = df['TotalAmount'].sum()"
        result = cg.execute_safe(code, sample_df)
        assert result["success"] is True
        assert result["stdout"] is None


# ── execute_safe 超时控制 ──────────────────────────────────

class TestExecuteTimeout:
    def test_execute_timeout(self, sample_df):
        """验证超时代码返回 error。"""
        from ai.code_generator import CodeGenerator
        import config as _cfg
        cg = CodeGenerator(MagicMock())
        # 使用无限循环触发超时（CODE_EXEC_TIMEOUT 默认 30s，这里改为 1s）
        old_timeout = getattr(_cfg, "CODE_EXEC_TIMEOUT", 30)
        _cfg.CODE_EXEC_TIMEOUT = 1
        try:
            result = cg.execute_safe("while True: pass", sample_df)
            assert result["success"] is False
            assert "超时" in result.get("error", "")
        finally:
            _cfg.CODE_EXEC_TIMEOUT = old_timeout

    def test_fast_code_completes(self, sample_df):
        """验证正常快速代码不受超时控制影响。"""
        from ai.code_generator import CodeGenerator
        cg = CodeGenerator(MagicMock())
        result = cg.execute_safe("result = 42", sample_df)
        assert result["success"] is True
        assert result["result"] == 42


# ── 配置项验证 ────────────────────────────────────────────

class TestConfig:
    def test_max_tokens_config(self):
        """验证 AI_MAX_TOKENS 配置项存在且为整数。"""
        import config
        assert hasattr(config, "AI_MAX_TOKENS")
        assert isinstance(config.AI_MAX_TOKENS, int)
        assert config.AI_MAX_TOKENS > 0

    def test_request_timeout_config(self):
        """验证 AI_REQUEST_TIMEOUT 配置项存在且为正数。"""
        import config
        assert hasattr(config, "AI_REQUEST_TIMEOUT")
        assert isinstance(config.AI_REQUEST_TIMEOUT, (int, float))
        assert config.AI_REQUEST_TIMEOUT > 0

    def test_code_exec_timeout_config(self):
        """验证 CODE_EXEC_TIMEOUT 配置项存在且为整数。"""
        import config
        assert hasattr(config, "CODE_EXEC_TIMEOUT")
        assert isinstance(config.CODE_EXEC_TIMEOUT, int)
        assert config.CODE_EXEC_TIMEOUT > 0
