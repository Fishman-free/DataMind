"""NL2Vis 图表生成器单元测试。"""
import pytest
from unittest.mock import MagicMock, patch
import pandas as pd
import numpy as np

from ai.chart_generator import ChartGenerator


class TestChartGenerator:
    """ChartGenerator 单元测试。"""

    @pytest.fixture
    def sample_df(self):
        """示例数据集。"""
        return pd.DataFrame({
            "month": ["Jan", "Feb", "Mar", "Apr"],
            "sales": [100, 200, 150, 300],
            "category": ["A", "B", "A", "B"],
        })

    @pytest.fixture
    def mock_client(self):
        """Mock OpenAI client。"""
        client = MagicMock()
        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = '''
```python
import plotly.graph_objects as go
chart = go.Figure(data=[go.Bar(x=["Jan","Feb","Mar","Apr"], y=[100,200,150,300])])
chart.update_layout(title="Monthly Sales", template="plotly_dark")
```
'''
        mock_response.choices = [mock_choice]
        client.chat.completions.create.return_value = mock_response
        return client

    def test_generate_returns_chart_json(self, mock_client, sample_df):
        """生成器应返回可序列化的 Plotly 图表 JSON。"""
        cg = ChartGenerator(mock_client)
        result = cg.generate("bar chart of monthly sales", sample_df)
        assert result["success"] is True
        assert "chart" in result
        assert "data" in result["chart"]  # Plotly JSON 结构

    def test_generate_with_previous_chart(self, mock_client, sample_df):
        """带 previous_chart 的迭代修改应正常工作。"""
        cg = ChartGenerator(mock_client)
        prev = {"data": [{"type": "bar"}], "layout": {}}
        result = cg.generate("change to line chart", sample_df, previous_chart=prev)
        assert result["success"] is True
        assert "chart" in result

    def test_sandbox_execution_error(self, mock_client, sample_df):
        """沙箱执行错误应返回 success=False 和错误信息。"""
        mock_client.chat.completions.create.return_value.choices[0].message.content = \
            "invalid python code!!!!"
        cg = ChartGenerator(mock_client)
        result = cg.generate("invalid chart", sample_df)
        assert result["success"] is False
        assert "explanation" in result

    def test_no_code_block(self, mock_client, sample_df):
        """无代码块的响应应优雅失败。"""
        mock_client.chat.completions.create.return_value.choices[0].message.content = \
            "I cannot create that chart."
        cg = ChartGenerator(mock_client)
        result = cg.generate("impossible chart", sample_df)
        assert result["success"] is False

    def test_chart_not_in_globals(self, mock_client, sample_df):
        """如果代码没定义 chart 变量，应返回错误。"""
        mock_client.chat.completions.create.return_value.choices[0].message.content = '''
```python
x = 1 + 1
```
'''
        cg = ChartGenerator(mock_client)
        result = cg.generate("no chart variable", sample_df)
        assert result["success"] is False
        assert "chart" in result.get("explanation", "").lower()

    def test_without_api_key(self, sample_df):
        """无 API Key 时 generate 直接返回报错，不抛出异常。"""
        cg = ChartGenerator(None)
        result = cg.generate("any chart", sample_df)
        assert result["success"] is False
        assert "explanation" in result

    def test_get_supported_chart_types(self):
        """应返回支持的图表类型列表。"""
        types = ChartGenerator.get_supported_chart_types()
        assert isinstance(types, list)
        assert len(types) >= 8
        assert "散点图" in types or "scatter" in str(types).lower()
