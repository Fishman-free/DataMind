"""
routes/api.py 路由单元测试
使用 Flask 测试客户端，不依赖真实 OpenAI API。
来源：学生+AI
"""
import io
import pytest
import pandas as pd


# ── 测试夹具 ────────────────────────────────────────────────

@pytest.fixture
def app():
    """每次测试前重置 app_state 并删除持久化文件，保证测试隔离。"""
    import os, config as _cfg
    from app import create_app, app_state
    application = create_app()
    application.config["TESTING"] = True

    # 删除持久化文件，防止 _try_auto_reload 干扰"无数据"场景测试
    _last  = os.path.join(_cfg.UPLOAD_FOLDER, ".last_upload.json")
    _aicfg = os.path.join(_cfg.UPLOAD_FOLDER, ".ai_config.json")
    for f in (_last, _aicfg):
        if os.path.exists(f):
            os.remove(f)

    for key in list(app_state.keys()):
        app_state[key] = None
    yield application
    for key in list(app_state.keys()):
        app_state[key] = None


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def loaded_state(app):
    """预填充 app_state，模拟已上传并处理过数据的状态。"""
    from app import app_state
    from data.analyzer import Analyzer
    from data.detector import Detector
    from ai.chat import ChatSession
    from ai.insight import InsightEngine

    dates = pd.date_range("2021-01-01", periods=10, freq="W")
    df = pd.DataFrame({
        "InvoiceDate": dates,
        "Quantity":    [5, 3, 2, 10, 1, 4, 6, 3, 8, 2],
        "UnitPrice":   [2.5, 1.0, 2.5, 8.0, 1.0, 2.5, 0.5, 2.5, 8.0, 1.0],
        "TotalAmount": [12.5, 3.0, 5.0, 80.0, 1.0, 10.0, 3.0, 7.5, 64.0, 2.0],
        "Country":     ["UK"] * 7 + ["France"] * 2 + ["Germany"] * 1,
        "DayOfWeek":   [d.dayofweek for d in dates],
        "Hour":        [10] * 10,
    })

    analyzer = Analyzer(df)
    detector = Detector(df)

    app_state["df_raw"]            = df
    app_state["df_clean"]          = df
    app_state["preprocess_report"] = {
        "original_rows": 10, "final_rows": 10,
        "remove_duplicates": {"removed": 0},
        "handle_missing":    {"filled_cols": {}, "high_missing_cols": []},
        "convert_types":     {"converted": {}},
        "filter_invalid_records": {"removed": 0},
        "filter_outliers":   {"flagged": 0, "detail": {}},
        "add_features":      {"added": []},
    }
    app_state["analyzer"]      = analyzer
    app_state["detector"]      = detector
    app_state["insights"]      = InsightEngine(df, analyzer, detector).generate_all()
    app_state["chat_session"]  = ChatSession(analyzer.summary_stats())
    # code_generator / report_generator 保持 None（无 API Key）
    return app_state


# ── /api/ping ────────────────────────────────────────────────

class TestPing:
    def test_ping_returns_200(self, client):
        assert client.get("/api/ping").status_code == 200

    def test_ping_returns_ok(self, client):
        data = client.get("/api/ping").get_json()
        assert data["status"] == "ok"


# ── /api/upload ──────────────────────────────────────────────

class TestUpload:
    def _csv(self, content: str):
        return io.BytesIO(content.encode("utf-8"))

    def test_upload_valid_csv_returns_200(self, client):
        data = {"file": (self._csv("Quantity,UnitPrice\n5,2.5\n3,1.0\n"), "test.csv")}
        resp = client.post("/api/upload", data=data, content_type="multipart/form-data")
        assert resp.status_code == 200

    def test_upload_response_has_row_count(self, client):
        data = {"file": (self._csv("Quantity,UnitPrice\n5,2.5\n3,1.0\n"), "test.csv")}
        resp = client.post("/api/upload", data=data, content_type="multipart/form-data")
        body = resp.get_json()
        assert "row_count" in body

    def test_upload_no_file_returns_400(self, client):
        resp = client.post("/api/upload", data={}, content_type="multipart/form-data")
        assert resp.status_code == 400

    def test_upload_invalid_extension_returns_400(self, client):
        data = {"file": (io.BytesIO(b"data"), "test.txt")}
        resp = client.post("/api/upload", data=data, content_type="multipart/form-data")
        assert resp.status_code == 400

    def test_upload_populates_state(self, client, app):
        from app import app_state
        data = {"file": (self._csv("Quantity,UnitPrice\n5,2.5\n"), "state_test.csv")}
        client.post("/api/upload", data=data, content_type="multipart/form-data")
        assert app_state["df_clean"] is not None
        assert app_state["analyzer"] is not None


# ── /api/data/* ──────────────────────────────────────────────

class TestDataRoutes:
    def test_summary_no_data_returns_400(self, client):
        assert client.get("/api/data/summary").status_code == 400

    def test_summary_returns_200(self, client, loaded_state):
        resp = client.get("/api/data/summary")
        assert resp.status_code == 200

    def test_summary_has_row_count(self, client, loaded_state):
        data = client.get("/api/data/summary").get_json()
        assert "row_count" in data

    def test_preview_no_data_returns_400(self, client):
        assert client.get("/api/data/preview").status_code == 400

    def test_preview_returns_list(self, client, loaded_state):
        data = client.get("/api/data/preview").get_json()
        assert isinstance(data, list)

    def test_preview_n_param_limits_rows(self, client, loaded_state):
        data = client.get("/api/data/preview?n=3").get_json()
        assert len(data) <= 3

    def test_preprocess_report_returns_200(self, client, loaded_state):
        assert client.get("/api/data/preprocess-report").status_code == 200

    def test_preprocess_report_has_original_rows(self, client, loaded_state):
        data = client.get("/api/data/preprocess-report").get_json()
        assert "original_rows" in data


# ── /api/insights ────────────────────────────────────────────

class TestInsights:
    def test_no_data_returns_400(self, client):
        assert client.get("/api/insights").status_code == 400

    def test_returns_list(self, client, loaded_state):
        data = client.get("/api/insights").get_json()
        assert isinstance(data, list)


# ── /api/analysis/<method> ───────────────────────────────────

class TestAnalysis:
    def test_no_data_returns_400(self, client):
        assert client.get("/api/analysis/sales_trend").status_code == 400

    def test_unknown_method_returns_404(self, client, loaded_state):
        assert client.get("/api/analysis/no_such_method").status_code == 404

    def test_sales_trend(self, client, loaded_state):
        assert client.get("/api/analysis/sales_trend").status_code == 200

    def test_top_products(self, client, loaded_state):
        assert client.get("/api/analysis/top_products").status_code == 200

    def test_country_distribution(self, client, loaded_state):
        assert client.get("/api/analysis/country_distribution").status_code == 200

    def test_rfm_analysis(self, client, loaded_state):
        assert client.get("/api/analysis/rfm_analysis").status_code == 200

    def test_correlation_matrix(self, client, loaded_state):
        assert client.get("/api/analysis/correlation_matrix").status_code == 200

    def test_time_pattern(self, client, loaded_state):
        assert client.get("/api/analysis/time_pattern").status_code == 200

    def test_top_products_n_param(self, client, loaded_state):
        data = client.get("/api/analysis/top_products?n=3").get_json()
        assert isinstance(data, list)
        assert len(data) <= 3


# ── /api/chat/* ──────────────────────────────────────────────

class TestChat:
    def test_chat_no_data_returns_400(self, client):
        resp = client.post("/api/chat", json={"question": "测试"},
                           content_type="application/json")
        assert resp.status_code == 400

    def test_chat_no_ai_key_returns_400(self, client, loaded_state):
        # code_generator is None (no API key)
        resp = client.post("/api/chat", json={"question": "月均销售额"},
                           content_type="application/json")
        assert resp.status_code == 400

    def test_chat_empty_question_returns_400(self, client, loaded_state):
        resp = client.post("/api/chat", json={"question": ""},
                           content_type="application/json")
        assert resp.status_code == 400

    def test_chat_history_no_data_returns_400(self, client):
        assert client.get("/api/chat/history").status_code == 400

    def test_chat_history_returns_list(self, client, loaded_state):
        data = client.get("/api/chat/history").get_json()
        assert isinstance(data, list)

    def test_chat_reset_returns_200(self, client, loaded_state):
        assert client.post("/api/chat/reset").status_code == 200


# ── /api/report/generate ─────────────────────────────────────

class TestReport:
    def test_no_data_returns_400(self, client):
        assert client.post("/api/report/generate").status_code == 400

    def test_no_ai_key_uses_fallback(self, client, loaded_state):
        # 无 API Key 时使用降级模板，仍返回 200 + content
        resp = client.post("/api/report/generate")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "content" in data
        assert len(data["content"]) > 0
