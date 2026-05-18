"""
ai/report.py 单元测试
来源：学生+AI
"""
import pytest
from unittest.mock import MagicMock


@pytest.fixture
def mock_openai_client():
    """模拟 OpenAI 客户端，返回 Markdown 格式报告。"""
    client = MagicMock()
    response = MagicMock()
    response.choices[0].message.content = (
        "# 数据分析报告\n\n"
        "## 数据概览\n本次分析共处理 1000 条记录。\n\n"
        "## 关键洞察\n发现 3 条异常洞察。\n\n"
        "## 总结\n数据质量良好，建议关注销售趋势。"
    )
    client.chat.completions.create.return_value = response
    return client


@pytest.fixture
def sample_insights():
    return [
        {"type": "anomaly", "severity": "high",
         "title": "列 Quantity 存在异常值",
         "detail": "检测到 10 个异常值，占比 10%"},
        {"type": "distribution", "severity": "medium",
         "title": "销售集中于 UK",
         "detail": "UK 贡献了 75% 的销售额"},
    ]


@pytest.fixture
def sample_df_info():
    return {
        "row_count": 1000,
        "column_count": 8,
        "numeric_stats": {"TotalAmount": {"mean": 22.5}},
        "date_range": {"start": "2021-01-01", "end": "2021-12-31"},
    }


# ── ReportGenerator ──────────────────────────────────────────

class TestReportGenerator:
    def test_generate_returns_dict(self, mock_openai_client, sample_df_info, sample_insights):
        from ai.report import ReportGenerator
        rg = ReportGenerator(mock_openai_client)
        result = rg.generate(sample_df_info, sample_insights, [])
        assert isinstance(result, dict)

    def test_generate_has_required_keys(self, mock_openai_client, sample_df_info, sample_insights):
        from ai.report import ReportGenerator
        rg = ReportGenerator(mock_openai_client)
        result = rg.generate(sample_df_info, sample_insights, [])
        assert "title" in result
        assert "content" in result
        assert "generated_at" in result

    def test_content_is_string(self, mock_openai_client, sample_df_info, sample_insights):
        from ai.report import ReportGenerator
        rg = ReportGenerator(mock_openai_client)
        result = rg.generate(sample_df_info, sample_insights, [])
        assert isinstance(result["content"], str)

    def test_content_contains_markdown(self, mock_openai_client, sample_df_info, sample_insights):
        from ai.report import ReportGenerator
        rg = ReportGenerator(mock_openai_client)
        result = rg.generate(sample_df_info, sample_insights, [])
        # mock 返回的内容包含 # 标题
        assert "#" in result["content"]

    def test_to_html_returns_string(self, mock_openai_client, sample_df_info, sample_insights):
        from ai.report import ReportGenerator
        rg = ReportGenerator(mock_openai_client)
        report = rg.generate(sample_df_info, sample_insights, [])
        html = rg.to_html(report)
        assert isinstance(html, str)

    def test_to_html_contains_html_tags(self, mock_openai_client, sample_df_info, sample_insights):
        from ai.report import ReportGenerator
        rg = ReportGenerator(mock_openai_client)
        report = rg.generate(sample_df_info, sample_insights, [])
        html = rg.to_html(report)
        assert "<h" in html  # Markdown # 标题 → HTML h 标签

    def test_openai_error_returns_fallback(self, sample_df_info, sample_insights):
        from ai.report import ReportGenerator
        client = MagicMock()
        client.chat.completions.create.side_effect = Exception("API timeout")
        rg = ReportGenerator(client)
        result = rg.generate(sample_df_info, sample_insights, [])
        # 失败时仍返回结构化报告（降级版本）
        assert isinstance(result, dict)
        assert "content" in result


# ── generate_detailed ─────────────────────────────────────

class TestGenerateDetailed:
    def test_generate_detailed_returns_dict(self, mock_openai_client, sample_df_info, sample_insights):
        from ai.report import ReportGenerator
        rg = ReportGenerator(mock_openai_client)
        result = rg.generate_detailed(sample_df_info, sample_insights, [])
        assert isinstance(result, dict)

    def test_generate_detailed_has_mode_field(self, mock_openai_client, sample_df_info, sample_insights):
        from ai.report import ReportGenerator
        rg = ReportGenerator(mock_openai_client)
        result = rg.generate_detailed(sample_df_info, sample_insights, [])
        assert result.get("mode") == "detailed"

    def test_generate_detailed_has_required_keys(self, mock_openai_client, sample_df_info, sample_insights):
        from ai.report import ReportGenerator
        rg = ReportGenerator(mock_openai_client)
        result = rg.generate_detailed(sample_df_info, sample_insights, [])
        for key in ("title", "content", "generated_at", "mode"):
            assert key in result, f"缺少键: {key}"

    def test_generate_detailed_content_longer_than_simple(
        self, mock_openai_client, sample_df_info, sample_insights
    ):
        from ai.report import ReportGenerator
        rg = ReportGenerator(mock_openai_client)
        simple   = rg.generate(sample_df_info, sample_insights, [])
        detailed = rg.generate_detailed(sample_df_info, sample_insights, [])
        # 详细报告内容应比简单报告更长
        assert len(detailed["content"]) > len(simple["content"])

    def test_generate_detailed_fallback_when_client_none(self, sample_df_info, sample_insights):
        from ai.report import ReportGenerator
        rg = ReportGenerator(None)
        result = rg.generate_detailed(sample_df_info, sample_insights, [])
        assert isinstance(result, dict)
        assert "content" in result
        assert result.get("mode") == "detailed"

    def test_generate_detailed_with_chat_history(self, mock_openai_client, sample_df_info, sample_insights):
        from ai.report import ReportGenerator
        history = [
            {"role": "user",      "content": "销售趋势如何？"},
            {"role": "assistant", "content": "整体呈上升趋势。"},
        ]
        rg = ReportGenerator(mock_openai_client)
        result = rg.generate_detailed(sample_df_info, sample_insights, history)
        assert isinstance(result["content"], str)
