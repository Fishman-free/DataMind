"""
ai/report_agents.py 单元测试
来源：学生+AI
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


# ── 测试夹具 ───────────────────────────────────────────────

@pytest.fixture
def mock_client():
    """模拟 OpenAI 客户端，返回固定文本。"""
    client = MagicMock()
    choice = MagicMock()
    choice.message.content = "## 模拟章节\n\n这是 AI 返回的测试内容。\n"
    client.chat.completions.create.return_value = MagicMock(choices=[choice])
    return client


@pytest.fixture
def df_info():
    return {
        "row_count":    1000,
        "column_count": 8,
        "columns":      ["InvoiceNo", "StockCode", "Quantity", "UnitPrice", "CustomerID", "Country", "InvoiceDate", "TotalAmount"],
        "numeric_cols": ["Quantity", "UnitPrice", "TotalAmount"],
        "date_range":   {"start": "2021-01-01", "end": "2021-12-31"},
        "numeric_summary": {
            "Quantity":    {"mean": 9.5, "std": 17.3, "min": 1.0, "max": 80995.0},
            "UnitPrice":   {"mean": 3.1, "std":  9.2, "min": 0.0, "max":  38970.0},
            "TotalAmount": {"mean": 22.0, "std": 309.0, "min": 0.0, "max": 168469.0},
        },
    }


@pytest.fixture
def sample_insights():
    return [
        {"severity": "high",   "title": "大量负数销售额", "detail": "共 9288 行 UnitPrice 为负"},
        {"severity": "medium", "title": "季节性高峰",    "detail": "11 月销售额环比增长 89%"},
        {"severity": "low",    "title": "少量缺失值",    "detail": "CustomerID 缺失率 24.9%"},
    ]


@pytest.fixture
def sample_history():
    return [
        {"role": "user",      "content": "各国销售额如何分布？"},
        {"role": "assistant", "content": "UK 占比最高，约 83%。"},
        {"role": "user",      "content": "哪些产品最畅销？"},
        {"role": "assistant", "content": "WORLD WAR 2 GLIDERS 销量最高。"},
    ]


# ── StatisticsAgent ───────────────────────────────────────

class TestStatisticsAgent:
    def test_generate_returns_string(self, mock_client, df_info):
        from ai.report_agents import StatisticsAgent
        agent = StatisticsAgent(mock_client, "gpt-4o-mini")
        result = agent.generate(df_info)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_generate_uses_ai_content(self, mock_client, df_info):
        from ai.report_agents import StatisticsAgent
        agent = StatisticsAgent(mock_client, "gpt-4o-mini")
        result = agent.generate(df_info)
        assert "模拟章节" in result

    def test_fallback_when_client_none(self, df_info):
        from ai.report_agents import StatisticsAgent
        agent = StatisticsAgent(None, "gpt-4o-mini")
        result = agent.generate(df_info)
        # client=None → _call_ai 返回 "" → 使用 fallback
        assert "## 数据特征描述" in result
        assert "1000" in result

    def test_fallback_when_ai_returns_html(self, df_info):
        from ai.report_agents import StatisticsAgent
        client = MagicMock()
        choice = MagicMock()
        choice.message.content = "<!DOCTYPE html><html><body>Error</body></html>"
        client.chat.completions.create.return_value = MagicMock(choices=[choice])
        agent = StatisticsAgent(client, "gpt-4o-mini")
        result = agent.generate(df_info)
        assert "## 数据特征描述" in result


# ── InsightAgent ──────────────────────────────────────────

class TestInsightAgent:
    def test_generate_returns_string(self, mock_client, sample_insights):
        from ai.report_agents import InsightAgent
        agent = InsightAgent(mock_client, "gpt-4o-mini")
        result = agent.generate(sample_insights)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_fallback_when_empty_insights(self):
        from ai.report_agents import InsightAgent
        agent = InsightAgent(None, "gpt-4o-mini")
        result = agent.generate([])
        assert "## 关键洞察" in result
        assert "未发现" in result

    def test_fallback_with_insights_when_client_none(self, sample_insights):
        from ai.report_agents import InsightAgent
        agent = InsightAgent(None, "gpt-4o-mini")
        result = agent.generate(sample_insights)
        assert "## 关键洞察" in result
        assert "HIGH" in result or "MEDIUM" in result or "LOW" in result


# ── QAAgent ───────────────────────────────────────────────

class TestQAAgent:
    def test_generate_returns_string(self, mock_client, sample_history):
        from ai.report_agents import QAAgent
        agent = QAAgent(mock_client, "gpt-4o-mini")
        result = agent.generate(sample_history)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_fallback_when_empty_history(self):
        from ai.report_agents import QAAgent
        agent = QAAgent(None, "gpt-4o-mini")
        result = agent.generate([])
        assert "## 对话分析摘要" in result
        assert "未进行" in result

    def test_fallback_with_history_when_client_none(self, sample_history):
        from ai.report_agents import QAAgent
        agent = QAAgent(None, "gpt-4o-mini")
        result = agent.generate(sample_history)
        assert "## 对话分析摘要" in result
        assert "各国销售额" in result


# ── SynthesisAgent ────────────────────────────────────────

class TestSynthesisAgent:
    def test_generate_returns_string(self, mock_client, df_info):
        from ai.report_agents import SynthesisAgent
        agent = SynthesisAgent(mock_client, "gpt-4o-mini")
        result = agent.generate("## 数据特征", "## 洞察", "## 对话", df_info)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_fallback_when_client_none(self, df_info):
        from ai.report_agents import SynthesisAgent
        agent = SynthesisAgent(None, "gpt-4o-mini")
        result = agent.generate("", "", "", df_info)
        assert "## 总结与建议" in result
        assert "1000" in result

    def test_accepts_all_sections(self, mock_client, df_info):
        from ai.report_agents import SynthesisAgent
        agent = SynthesisAgent(mock_client, "gpt-4o-mini")
        result = agent.generate(
            "## 数据特征描述\n内容...",
            "## 关键洞察\n内容...",
            "## 对话摘要\n内容...",
            df_info,
        )
        assert isinstance(result, str)
        assert len(result) > 0
