"""
ai/chat.py 单元测试
来源：学生+AI
"""
import pytest


@pytest.fixture
def session():
    from ai.chat import ChatSession
    summary = {
        "row_count": 1000,
        "column_count": 5,
        "numeric_stats": {"TotalAmount": {}, "Quantity": {}},
    }
    return ChatSession(summary)


# ── ChatSession ──────────────────────────────────────────────

class TestChatSession:
    def test_initial_history_empty(self, session):
        assert session.history == []

    def test_build_system_prompt_returns_string(self, session):
        result = session.build_system_prompt()
        assert isinstance(result, str)

    def test_build_system_prompt_contains_row_count(self, session):
        result = session.build_system_prompt()
        assert "1000" in result

    def test_build_system_prompt_contains_numeric_cols(self, session):
        result = session.build_system_prompt()
        assert "TotalAmount" in result

    def test_add_message_increments_history(self, session):
        session.add_message("user", "你好")
        assert len(session.history) == 1

    def test_add_message_stores_role_and_content(self, session):
        session.add_message("user", "这批数据有多少行？")
        msg = session.history[0]
        assert msg["role"] == "user"
        assert msg["content"] == "这批数据有多少行？"

    def test_get_context_starts_with_system(self, session):
        ctx = session.get_context()
        assert ctx[0]["role"] == "system"

    def test_get_context_includes_history(self, session):
        session.add_message("user", "q1")
        session.add_message("assistant", "a1")
        ctx = session.get_context()
        # system + 2 条历史 = 3
        assert len(ctx) == 3

    def test_reset_clears_history(self, session):
        session.add_message("user", "q1")
        session.reset()
        assert session.history == []

    def test_reset_preserves_summary(self, session):
        session.reset()
        assert session.df_summary["row_count"] == 1000

    def test_max_history_trims_oldest(self):
        from ai.chat import ChatSession
        s = ChatSession({}, max_history=4)
        for i in range(5):
            s.add_message("user", f"q{i}")
            s.add_message("assistant", f"a{i}")
        assert len(s.history) == 4

    def test_max_history_keeps_latest_messages(self):
        from ai.chat import ChatSession
        s = ChatSession({}, max_history=2)
        s.add_message("user", "old question")
        s.add_message("assistant", "old answer")
        s.add_message("user", "new question")
        s.add_message("assistant", "new answer")
        # max=2，保留最新的 2 条
        assert s.history[-1]["content"] == "new answer"
        assert s.history[-2]["content"] == "new question"
