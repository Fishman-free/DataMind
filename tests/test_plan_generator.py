"""分析计划生成器单元测试。"""
import pytest
from unittest.mock import MagicMock, patch
import pandas as pd
import numpy as np

from ai.plan_generator import PlanGenerator


class TestPlanGenerator:
    """PlanGenerator 单元测试。"""

    @pytest.fixture
    def sample_df_info(self):
        """示例数据集信息。"""
        return {
            "column_count": 5,
            "row_count": 100,
            "columns": {
                "date": "datetime64",
                "sales": "float64",
                "quantity": "int64",
                "category": "object",
                "region": "object",
            },
        }

    @pytest.fixture
    def sample_insights(self):
        """示例洞察列表。"""
        return [
            {"type": "trend", "description": "销售额呈上升趋势", "severity": "high"},
            {"type": "anomaly", "description": "3月有异常峰值", "severity": "medium"},
        ]

    @pytest.fixture
    def mock_client(self):
        """Mock OpenAI client。"""
        import json

        client = MagicMock()
        mock_response = MagicMock()
        mock_choice = MagicMock()
        plan = [
            {
                "id": 1,
                "title": "销售趋势分析",
                "category": "趋势",
                "description": "分析销售数据的时间趋势",
            },
            {
                "id": 2,
                "title": "类别对比",
                "category": "对比",
                "description": "对比不同品类的销售表现",
            },
            {
                "id": 3,
                "title": "异常排查",
                "category": "质量",
                "description": "排查数据中的异常值",
            },
        ]
        mock_choice.message.content = json.dumps(plan, ensure_ascii=False)
        mock_response.choices = [mock_choice]
        client.chat.completions.create.return_value = mock_response
        return client

    def test_generate_returns_list(self, mock_client, sample_df_info, sample_insights):
        """应返回分析计划列表。"""
        pg = PlanGenerator(mock_client)
        result = pg.generate(sample_df_info, sample_insights)
        assert isinstance(result, list)
        assert len(result) >= 1

    def test_plan_items_have_required_fields(
        self, mock_client, sample_df_info, sample_insights
    ):
        """每个计划项应有 id, title, category, description。"""
        pg = PlanGenerator(mock_client)
        result = pg.generate(sample_df_info, sample_insights)
        for item in result:
            assert "id" in item
            assert "title" in item
            assert "category" in item
            assert "description" in item

    def test_fallback_without_api_key(self, sample_df_info, sample_insights):
        """无 API Key 时应返回基于数据特征的 fallback 计划。"""
        pg = PlanGenerator(None)
        result = pg.generate(sample_df_info, sample_insights)
        assert isinstance(result, list)
        assert len(result) >= 3  # fallback 至少生成 3 条

    def test_fallback_has_date_trend_when_date_column(self):
        """有日期列时 fallback 应包含趋势分析。"""
        pg = PlanGenerator(None)
        info = {"columns": {"date": "datetime64", "value": "float64"}}
        result = pg.generate(info, [])
        categories = [item["category"] for item in result]
        assert "趋势" in categories

    def test_fallback_has_correlation_when_numeric_columns(self):
        """有多个数值列时 fallback 应包含相关性分析。"""
        pg = PlanGenerator(None)
        info = {"columns": {"a": "float64", "b": "float64", "c": "int64"}}
        result = pg.generate(info, [])
        categories = [item["category"] for item in result]
        assert any("相关" in c or "关联" in c or "对比" in c for c in categories)

    def test_ai_error_falls_back(self, sample_df_info, sample_insights):
        """AI 调用异常时应降级到 fallback。"""
        client = MagicMock()
        client.chat.completions.create.side_effect = RuntimeError("API error")
        pg = PlanGenerator(client)
        result = pg.generate(sample_df_info, sample_insights)
        assert isinstance(result, list)
        assert len(result) >= 3
