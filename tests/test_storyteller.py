"""数据叙事引擎单元测试。"""
import pytest
from unittest.mock import MagicMock, patch
import json

from ai.storyteller import Storyteller


class TestStoryteller:
    """Storyteller 单元测试。"""

    @pytest.fixture
    def sample_df_info(self):
        return {
            "column_count": 5,
            "row_count": 500,
            "numeric_stats": {
                "sales": {"mean": 150.5, "max": 500.0, "min": 10.0},
            },
        }

    @pytest.fixture
    def sample_insights(self):
        return [
            {"type": "trend", "severity": "high",
             "description": "销售额在 Q4 增长 45%"},
            {"type": "anomaly", "severity": "medium",
             "description": "3月份出现异常低值"},
        ]

    @pytest.fixture
    def mock_client(self):
        client = MagicMock()
        mock_response = MagicMock()
        mock_choice = MagicMock()
        story = {
            "title": "销售数据洞察：Q4 强势增长背后的故事",
            "subtitle": "一份基于 500 条交易记录的深度分析",
            "sections": [
                {
                    "heading": "整体概览",
                    "body": "数据集涵盖 500 条交易记录，呈现出一个明显的增长叙事。",
                    "highlight": "Q4 增长 45%",
                },
            ],
            "key_takeaways": ["Q4 是全年最佳季度", "建议加大 Q4 营销投入"],
        }
        mock_choice.message.content = json.dumps(story, ensure_ascii=False)
        mock_response.choices = [mock_choice]
        client.chat.completions.create.return_value = mock_response
        return client

    def test_tell_returns_structure(self, mock_client, sample_df_info, sample_insights):
        """应返回完整的叙事结构。"""
        st = Storyteller(mock_client)
        result = st.tell(sample_df_info, sample_insights, [], "")
        assert "title" in result
        assert "subtitle" in result
        assert "sections" in result
        assert "key_takeaways" in result

    def test_tell_sections_have_required_fields(self, mock_client, sample_df_info, sample_insights):
        """每个 section 应有 heading, body, highlight。"""
        st = Storyteller(mock_client)
        result = st.tell(sample_df_info, sample_insights, [], "")
        for section in result["sections"]:
            assert "heading" in section
            assert "body" in section

    def test_fallback_without_api_key(self, sample_df_info, sample_insights):
        """无 API Key 时应生成基础叙事。"""
        st = Storyteller(None)
        result = st.tell(sample_df_info, sample_insights, [], "report content")
        assert "title" in result
        assert len(result["sections"]) >= 1
        assert len(result["key_takeaways"]) >= 1

    def test_fallback_uses_report_content(self, sample_df_info, sample_insights):
        """Fallback 应利用报告内容生成叙事。"""
        st = Storyteller(None)
        report = "## 销售分析\n销售额在 Q4 增长了 45%。3月有异常低值。"
        result = st.tell(sample_df_info, sample_insights, [], report)
        assert len(result["sections"]) >= 1

    def test_tell_with_chat_history(self, mock_client, sample_df_info, sample_insights):
        """带对话历史应正常工作。"""
        st = Storyteller(mock_client)
        history = [
            {"role": "user", "content": "Q4 为什么增长？"},
            {"role": "assistant", "content": "因为促销活动..."},
        ]
        result = st.tell(sample_df_info, sample_insights, history, "")
        assert "title" in result

    def test_ai_error_falls_back(self, sample_df_info, sample_insights):
        """AI 调用异常应降级到 fallback。"""
        client = MagicMock()
        client.chat.completions.create.side_effect = RuntimeError("API error")
        st = Storyteller(client)
        result = st.tell(sample_df_info, sample_insights, [], "report")
        assert "title" in result
        assert len(result["sections"]) >= 1
