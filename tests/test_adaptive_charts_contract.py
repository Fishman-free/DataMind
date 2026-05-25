"""
自适应图表契约测试。
来源：学生+AI
"""
import os
import pytest
import pandas as pd


@pytest.fixture
def app():
    import config as _cfg
    from app import create_app, app_state

    application = create_app()
    application.config["TESTING"] = True

    _last = os.path.join(_cfg.UPLOAD_FOLDER, ".last_upload.json")
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
    from app import app_state
    from data.analyzer import Analyzer
    from data.detector import Detector
    from ai.chat import ChatSession
    from ai.insight import InsightEngine

    dates = pd.date_range("2021-01-01", periods=10, freq="W")
    df = pd.DataFrame({
        "InvoiceDate": dates,
        "Quantity": [5, 3, 2, 10, 1, 4, 6, 3, 8, 2],
        "UnitPrice": [2.5, 1.0, 2.5, 8.0, 1.0, 2.5, 0.5, 2.5, 8.0, 1.0],
        "TotalAmount": [12.5, 3.0, 5.0, 80.0, 1.0, 10.0, 3.0, 7.5, 64.0, 2.0],
        "Country": ["UK"] * 7 + ["France"] * 2 + ["Germany"] * 1,
        "DayOfWeek": [d.dayofweek for d in dates],
        "Hour": [10] * 10,
    })

    analyzer = Analyzer(df)
    detector = Detector(df)

    app_state["df_raw"] = df
    app_state["df_clean"] = df
    app_state["preprocess_report"] = {
        "original_rows": 10, "final_rows": 10,
        "remove_duplicates": {"removed": 0},
        "handle_missing": {"filled_cols": {}, "high_missing_cols": []},
        "convert_types": {"converted": {}},
        "filter_invalid_records": {"removed": 0},
        "filter_outliers": {"flagged": 0, "detail": {}},
        "add_features": {"added": []},
    }
    app_state["analyzer"] = analyzer
    app_state["detector"] = detector
    app_state["insights"] = InsightEngine(df, analyzer, detector).generate_all()
    app_state["chat_session"] = ChatSession(analyzer.summary_stats())
    return app_state


def test_adaptive_charts_contract(client, loaded_state):
    resp = client.get('/api/analysis/adaptive_charts')
    assert resp.status_code == 200

    charts = resp.get_json()
    assert isinstance(charts, list)
    assert len(charts) >= 6

    for cfg in charts[:6]:
        assert 'type' in cfg
        assert 'title' in cfg
        assert 'data' in cfg


def test_adaptive_charts_contract_without_data_returns_400(client):
    resp = client.get('/api/analysis/adaptive_charts')
    assert resp.status_code == 400

    payload = resp.get_json()
    assert isinstance(payload, dict)
    assert payload.get('error')
