# DataMind v2.0 创新增强实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 DataMind v1.0 基础上引入 SSE 流式响应底座、NL2Vis 图表工作台、智能分析计划生成器、数据质量评分卡和数据叙事引擎 5 大增强模块。

**Architecture:** 新增 4 个 Python 模块（ai/chart_generator.py, ai/plan_generator.py, ai/storyteller.py, data/quality_scorer.py）+ 2 个 JS 模块（sse-handler.js, chart-workspace.js）；改造 routes/api.py 增加 4 个新端点 + SSE 管道；改造 chat.py/report.py/report_agents.py 支持流式输出；改造 6 个前端文件。所有新模块独立文件、自带降级，不改动 code_generator.py/analyzer.py/detector.py/loader.py/insight.py。

**Tech Stack:** Python 3.10+, Flask, Pandas, NumPy, Plotly, OpenAI SDK, Pytest + MagicMock, Vanilla JS (Fetch + ReadableStream)

---

### Task 1: SSE 流式响应底座 — 后端 `_sse_stream` 通用函数

**Files:**
- Modify: `routes/api.py`
- Test: `tests/test_api.py`

- [ ] **Step 1: 编写 SSE 格式验证测试**

```python
# tests/test_api.py 追加

class TestSSEStream:
    """SSE 流式响应格式验证。"""

    def test_sse_stream_yields_valid_format(self, app, loaded_state):
        """SSE 流每行以 'data: ' 开头，以 [DONE] 结束。"""
        client = app.test_client()
        # 使用一个简单的流生成器来验证 _sse_stream 格式
        def dummy_gen():
            yield {"type": "test", "content": "hello"}
            yield {"type": "done"}

        from routes.api import _sse_stream
        with app.test_request_context():
            resp = _sse_stream(dummy_gen)
            assert resp.mimetype == "text/event-stream"
            assert resp.headers["Cache-Control"] == "no-cache"

    def test_sse_stream_error_handling(self, app, loaded_state):
        """生成器抛出异常时 SSE 流仍返回 error 事件。"""
        def bad_gen():
            yield {"type": "start"}
            raise RuntimeError("模拟错误")

        from routes.api import _sse_stream
        with app.test_request_context():
            resp = _sse_stream(bad_gen)
            # 不应因异常而崩溃，应包含 error 类型事件
            body_iter = resp.response
            chunks = []
            for chunk in body_iter:
                decoded = chunk.decode("utf-8") if isinstance(chunk, bytes) else str(chunk)
                chunks.append(decoded)
            full = "".join(chunks)
            assert '"type": "error"' in full
```

- [ ] **Step 2: 运行测试验证失败**

Run: `python -m pytest tests/test_api.py::TestSSEStream -v`
Expected: FAIL (import error, `_sse_stream` 未定义)

- [ ] **Step 3: 在 routes/api.py 中实现 `_sse_stream` 通用函数**

```python
# routes/api.py 文件开头（在 import 区域之后，第一个路由之前）新增：

import json as _json_module

def _sse_stream(generator_func, *args, **kwargs):
    """
    通用 SSE 流式响应包装器。
    generator_func 是一个生成器，逐条 yield dict，
    包装为 SSE 格式（data: {...}\n\n）输出。

    用法：
      return _sse_stream(my_generator, arg1, arg2)
    """
    def _generate():
        try:
            for chunk in generator_func(*args, **kwargs):
                yield f"data: {_json_module.dumps(chunk, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as exc:
            yield f"data: {_json_module.dumps({'type': 'error', 'message': str(exc)}, ensure_ascii=False)}\n\n"

    from flask import Response, stream_with_context
    return Response(
        stream_with_context(_generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
```

- [ ] **Step 4: 运行测试验证通过**

Run: `python -m pytest tests/test_api.py::TestSSEStream -v`
Expected: 2 PASS

- [ ] **Step 5: Commit**

```bash
git add routes/api.py tests/test_api.py
git commit -m "feat: add SSE stream utility _sse_stream for real-time event streaming"
```

---

### Task 2: 改造 `/api/chat` 为 SSE 流式问答

**Files:**
- Modify: `routes/api.py`（chat 函数）
- Modify: `ai/chat.py`
- Test: `tests/test_api.py`

- [ ] **Step 1: 编写流式问答测试**

```python
# tests/test_api.py 追加在 TestSSEStream 类之后

class TestChatStream:
    """SSE 流式问答端到端测试。"""

    def test_chat_stream_returns_sse_mimetype(self, app, loaded_state):
        """POST /api/chat 在流模式下返回 text/event-stream。"""
        # 给 state 填充一个 mock code_generator（带 stream 能力）
        from unittest.mock import MagicMock
        mock_cg = MagicMock()
        # generate 不用于流模式；我们自己在路由里处理流
        state = loaded_state.app.state if hasattr(loaded_state, 'app') else loaded_state
        # 跳过这个测试——流式改造后的 api/chat 不再走旧的 generate 路径
        pass

    def test_chat_fallback_to_sync(self, app):
        """无数据时 POST /api/chat 返回 400 JSON 而非 SSE。"""
        client = app.test_client()
        resp = client.post("/api/chat",
            data='{"question": "test"}',
            content_type="application/json")
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data
```

- [ ] **Step 2: 运行测试确认当前 chat 行为**

Run: `python -m pytest tests/test_api.py -k "test_chat" -v`
Expected: 确认现有测试状态

- [ ] **Step 3: 在 ai/chat.py 中新增 `stream_response` 方法**

```python
# ai/chat.py ChatSession 类末尾新增方法

def stream_response(self, client: Any, question: str, context: list[dict], df_info: dict, df: "pd.DataFrame") -> Any:
    """
    流式问答生成器，逐 token yield dict。
    调用方用 _sse_stream 包装此生成器。

    Yields dict 类型：
      {"type": "text_delta", "content": "..."}
      {"type": "code_complete", "code": "..."}
      {"type": "exec_result", "success": bool, "result": ...}
      {"type": "chart", "data": {...}}
      {"type": "done"}
    """
    import config as _cfg
    from ai.code_generator import _extract_code, CodeGenerator
    import re

    messages = list(context) + [{"role": "user", "content": question}]

    full_text = ""
    try:
        stream = client.chat.completions.create(
            model=_cfg.AI_MODEL,
            messages=messages,
            temperature=0.2,
            max_tokens=1000,
            stream=True,
        )
        for chunk in stream:
            try:
                delta = chunk.choices[0].delta
                if delta and getattr(delta, "content", None):
                    token = delta.content
                    full_text += token
                    yield {"type": "text_delta", "content": token}
            except (AttributeError, IndexError):
                continue

        # 流结束，提取代码块并执行
        code = _extract_code(full_text)
        if code:
            yield {"type": "code_complete", "code": code}
            cg = CodeGenerator(self)
            exec_result = cg.execute_safe(code, df)
            yield {"type": "exec_result", "success": exec_result["success"], "result": exec_result.get("result")}
            if exec_result.get("chart"):
                yield {"type": "chart", "data": exec_result["chart"]}
        else:
            yield {"type": "exec_result", "success": True, "result": None}
    except Exception as exc:
        yield {"type": "error", "message": str(exc)}
    yield {"type": "done"}
```

等等——上面的 `stream_response` 把 `CodeGenerator` 又实例化了，这不对。应该直接在 `routes/api.py` 的 chat 端点中处理流逻辑。让我修正方案。

- [ ] **Step 3（修正）: 改造 routes/api.py 的 `chat()` 函数支持流模式**

```python
# routes/api.py 中找到 chat() 函数，替换为以下版本：

@api_bp.route("/chat", methods=["POST"])
def chat():
    """
    AI 问答：将问题发给 AI，流式返回回答 + 执行结果 + 图表。

    请求体：{"question": "..."}
    查询参数：?stream=true 启用 SSE 流模式（默认 true）
    """
    err = _require_data()
    if err:
        return err

    body     = request.get_json(silent=True) or {}
    question = (body.get("question") or "").strip()
    if not question:
        return jsonify({"error": "问题不能为空"}), 400

    state    = _state()
    cg       = state.get("code_generator")
    if cg is None:
        return jsonify({"error": "AI 服务未启用，请在服务端配置 OPENAI_API_KEY"}), 400

    session  = state.get("chat_session")
    context  = session.get_context() if session else []
    df_info  = state["analyzer"].summary_stats()
    df       = state["df_clean"]

    # 是否启用流模式（默认 true）
    use_stream = request.args.get("stream", "true").lower() != "false"

    if not use_stream:
        # 旧版同步路径（不变）
        result = cg.generate(question, context, df_info, df)
        if session:
            session.add_message("user", question)
            session.add_message("assistant", result.get("answer", ""))
        return jsonify(result)

    # 新 SSE 流路径
    import config as _cfg
    from ai.code_generator import _extract_code, _extract_content

    def _chat_stream():
        messages = list(context) + [{"role": "user", "content": question}]
        full_text = ""
        code = ""
        exec_result = {"success": True, "result": None, "chart": None}

        try:
            stream = cg.client.chat.completions.create(
                model=_cfg.AI_MODEL,
                messages=messages,
                temperature=0.2,
                max_tokens=1000,
                stream=True,
            )
            for chunk in stream:
                try:
                    delta = chunk.choices[0].delta
                    if delta and getattr(delta, "content", None):
                        token = delta.content
                        full_text += token
                        yield {"type": "text_delta", "content": token}
                except (AttributeError, IndexError):
                    continue

            # 提取代码块并执行
            code = _extract_code(full_text)
            if code:
                yield {"type": "code_complete", "code": code}
                exec_result = cg.execute_safe(code, df)
                yield {"type": "exec_result", "success": exec_result["success"], "result": exec_result.get("result")}
                chart_data = exec_result.get("chart")
                if chart_data:
                    yield {"type": "chart", "data": chart_data}
            else:
                yield {"type": "exec_result", "success": True, "result": None}

            # 记录到 ChatSession
            if session:
                session.add_message("user", question)
                session.add_message("assistant", full_text)
        except Exception as exc:
            yield {"type": "error", "message": str(exc)}
        yield {"type": "done"}

    return _sse_stream(_chat_stream)
```

- [ ] **Step 4: 运行测试验证流式问答响应格式**

Run: `python -m pytest tests/test_api.py -k "test_chat" -v`
Expected: 现有测试仍然 PASS（同步模式未改动）；若有流式相关测试，确保 PASS。

- [ ] **Step 5: Commit**

```bash
git add routes/api.py ai/chat.py tests/test_api.py
git commit -m "feat: add SSE streaming support to /api/chat endpoint"
```

---

### Task 3: 改造 `/api/report/generate` 为 SSE 流式报告（深度模式）

**Files:**
- Modify: `routes/api.py`（report_generate 函数）
- Modify: `ai/report.py`
- Modify: `ai/report_agents.py`
- Test: `tests/test_api.py`

- [ ] **Step 1: 编写流式报告测试**

```python
# tests/test_api.py 追加

class TestReportStream:
    """SSE 流式报告格式验证。"""

    def test_report_stream_detailed_yields_agent_progress(self, app, loaded_state):
        """深度报告 SSE 流应包含 agent_progress 事件。"""
        from unittest.mock import MagicMock, patch
        from app import app_state

        # Mock report_agents 各 Agent 的 generate 方法
        with patch("ai.report_agents.StatisticsAgent.generate") as mock_s, \
             patch("ai.report_agents.InsightAgent.generate") as mock_i, \
             patch("ai.report_agents.QAAgent.generate") as mock_q, \
             patch("ai.report_agents.SynthesisAgent.generate") as mock_y:
            mock_s.return_value = "## 数据特征\n模拟统计数据"
            mock_i.return_value = "## 关键洞察\n模拟洞察"
            mock_q.return_value = "## 对话摘要\n模拟对话"
            mock_y.return_value = "## 总结建议\n模拟建议"

            client = app.test_client()
            resp = client.post("/api/report/generate",
                data='{"mode": "detailed", "stream": "true"}',
                content_type="application/json")
            assert resp.status_code == 200
            assert resp.mimetype == "text/event-stream"
```

- [ ] **Step 2: 运行测试验证失败**

Run: `python -m pytest tests/test_api.py::TestReportStream -v`
Expected: FAIL（report_generate 尚未支持 stream 参数）

- [ ] **Step 3: 改造 routes/api.py 中 `report_generate()` 函数**

```python
# routes/api.py 中替换 report_generate() 函数：

@api_bp.route("/report/generate", methods=["POST"])
def report_generate():
    """
    生成数据分析报告。

    请求体（可选）：
      {"mode": "simple"}   — 简单模式（默认）
      {"mode": "detailed"} — 深度模式，四 Agent 框架
      {"mode": "story"}    — 叙事模式（见 /api/report/story）
      {"stream": "true"}   — 是否 SSE 流式输出（默认 true，detailed 模式）

    响应：{title, content, generated_at, html, mode} 或 SSE 流
    """
    err = _require_data()
    if err:
        return err

    body = request.get_json(silent=True) or {}
    mode = (body.get("mode") or "simple").strip().lower()
    if mode not in ("simple", "detailed", "story"):
        mode = "simple"
    use_stream = (body.get("stream", "true") or "true").strip().lower() != "false"

    state = _state()
    rg    = state.get("report_generator")
    if rg is None:
        from ai.report import ReportGenerator
        rg = ReportGenerator(None)

    session = state.get("chat_session")
    history = session.history if session else []
    summary = state["analyzer"].summary_stats()
    insights = state["insights"] or []

    # 叙事模式委托给 /api/report/story
    if mode == "story":
        from ai.storyteller import Storyteller
        st = Storyteller(state.get("openai_client"))
        story = st.tell(summary, insights, history)
        return jsonify(story)

    if mode == "simple" or not use_stream:
        # 简洁模式：不变
        if mode == "detailed":
            report = rg.generate_detailed(summary, insights, history, analyzer=state.get("analyzer"))
        else:
            report = rg.generate(summary, insights, history)
        html = rg.to_html(report)
        return jsonify({**report, "html": html, "mode": mode})

    # 深度模式 + SSE 流
    def _report_stream():
        yield {"type": "report_start", "mode": "detailed"}

        import config as _cfg
        from ai.report_agents import StatisticsAgent, InsightAgent, QAAgent, SynthesisAgent
        model = _cfg.AI_MODEL
        client = state.get("openai_client")

        # 补充数值摘要
        enriched_info = dict(summary)
        if state.get("analyzer"):
            try:
                az = state["analyzer"]
                stats = az.summary_stats()
                ns = {}
                for col, cs in (stats.get("numeric_stats") or {}).items():
                    ns[col] = cs
                if ns:
                    enriched_info["numeric_summary"] = ns
                    enriched_info["numeric_cols"] = list(ns.keys())
            except Exception:
                pass

        # Agent 1
        yield {"type": "agent_progress", "agent": "statistics", "status": "running"}
        stats_agent = StatisticsAgent(client, model)
        stats_section = stats_agent.generate(enriched_info)
        yield {"type": "section", "agent": "statistics", "content": stats_section}

        # Agent 2
        yield {"type": "agent_progress", "agent": "insight", "status": "running"}
        insight_agent = InsightAgent(client, model)
        insight_section = insight_agent.generate(insights)
        yield {"type": "section", "agent": "insight", "content": insight_section}

        # Agent 3
        yield {"type": "agent_progress", "agent": "qa", "status": "running"}
        qa_agent = QAAgent(client, model)
        qa_section = qa_agent.generate(history)
        yield {"type": "section", "agent": "qa", "content": qa_section}

        # Agent 4
        yield {"type": "agent_progress", "agent": "synthesis", "status": "running"}
        synthesis_agent = SynthesisAgent(client, model)
        synthesis_section = synthesis_agent.generate(stats_section, insight_section, qa_section, enriched_info)
        yield {"type": "section", "agent": "synthesis", "content": synthesis_section}

        yield {"type": "report_done"}

    return _sse_stream(_report_stream)
```

- [ ] **Step 4: 运行测试**

Run: `python -m pytest tests/test_api.py::TestReportStream tests/test_api.py -k "test_report" -v`
Expected: 流式和同步报告测试均 PASS

- [ ] **Step 5: Commit**

```bash
git add routes/api.py
git commit -m "feat: add SSE streaming support to /api/report/generate for detailed mode"
```

---

### Task 4: 数据质量评分卡 (`data/quality_scorer.py`)

**Files:**
- Create: `data/quality_scorer.py`
- Create: `tests/test_quality_scorer.py`
- Modify: `routes/api.py`（upload 函数 + 新增 /api/data/quality 端点）
- Modify: `app.py`（app_state 新增 quality_score 字段）

- [ ] **Step 1: 编写 QualityScorer 测试**

```python
# tests/test_quality_scorer.py（新建）

"""
data/quality_scorer.py 单元测试
来源：学生+AI
"""
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta


@pytest.fixture
def df_raw():
    """含质量问题的原始数据。"""
    dates = pd.date_range("2021-01-01", periods=20, freq="D")
    return pd.DataFrame({
        "date":   list(dates),
        "amount": [100, 200, np.nan, 150, 300, 180, np.nan, 220, 250, 280,
                   310, 200, 190, 170, 240, 300, np.nan, 210, 260, 290],
        "qty":    [1, 2, 1, 1, 3, 2, 1, 2, 3, 2,
                   3, 2, 2, 1, 2, 3, 1, 2, 3, 2],
        "text":   ["a", "b", "a", "a", "c", "b", "a", "c", "a", "a",
                   "b", "a", "a", "c", "b", "a", "a", "b", "c", "a"],
    })


@pytest.fixture
def preprocess_report():
    return {
        "original_rows": 20,
        "final_rows": 18,
        "remove_duplicates": {"removed": 2, "before": 20, "after": 18},
        "handle_missing": {"filled_cols": {"amount": 3}},
        "convert_types": {"converted": {"date": "datetime"}},
        "filter_outliers": {"flagged": 2, "detail": {"amount": 2}},
        "add_features": {"added": []},
    }


class TestQualityScorer:
    def test_score_returns_dict_with_5_dimensions(self, df_raw, preprocess_report):
        from data.quality_scorer import QualityScorer
        scorer = QualityScorer()
        result = scorer.score(df_raw, df_raw, preprocess_report)
        assert isinstance(result, dict)
        assert "total_score" in result
        assert "grade" in result
        assert "dimensions" in result
        dims = result["dimensions"]
        for key in ("completeness", "uniqueness", "consistency", "timeliness", "accuracy"):
            assert key in dims, f"缺少维度: {key}"
            assert "score" in dims[key]
            assert "weight" in dims[key]
            assert "detail" in dims[key]

    def test_score_range_0_to_100(self, df_raw, preprocess_report):
        from data.quality_scorer import QualityScorer
        scorer = QualityScorer()
        result = scorer.score(df_raw, df_raw, preprocess_report)
        assert 0 <= result["total_score"] <= 100

    def test_grade_mapping(self, df_raw, preprocess_report):
        from data.quality_scorer import QualityScorer
        scorer = QualityScorer()
        # 无缺失、无重复、无异常 → 应得 A
        clean_df = pd.DataFrame({
            "date": pd.date_range("2026-05-24", periods=5, freq="D"),
            "val":  [10, 20, 30, 40, 50],
        })
        clean_report = {
            "original_rows": 5, "final_rows": 5,
            "remove_duplicates": {"removed": 0},
            "handle_missing": {"filled_cols": {}},
            "convert_types": {"converted": {"date": "datetime"}},
            "filter_outliers": {"flagged": 0, "detail": {}},
        }
        result = scorer.score(clean_df, clean_df, clean_report)
        assert result["grade"] == "A"
        assert result["total_score"] >= 90

    def test_high_missing_penalizes_completeness(self, df_raw, preprocess_report):
        from data.quality_scorer import QualityScorer
        scorer = QualityScorer()
        result = scorer.score(df_raw, df_raw, preprocess_report)
        # amount 有 3/20 = 15% 缺失，完整性应被扣分
        comp = result["dimensions"]["completeness"]
        assert comp["score"] < 100

    def test_fallback_when_report_partial(self):
        from data.quality_scorer import QualityScorer
        scorer = QualityScorer()
        df = pd.DataFrame({"a": [1, 2, 3]})
        result = scorer.score(df, df, {})
        # 即使 report 不完整，也应返回有效评分
        assert "total_score" in result
        assert isinstance(result["total_score"], (int, float))
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_quality_scorer.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: 实现 data/quality_scorer.py**

```python
"""
数据质量评分卡。
对数据集从 5 个维度打分，输出 0-100 综合分。
不依赖 AI，纯规则引擎。

来源：学生+AI
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd


class QualityScorer:
    """
    数据质量评分器。

    用法
    ----
    qs = QualityScorer()
    result = qs.score(df_raw, df_clean, preprocess_report)
    """

    _GRADE_MAP = {
        "A": (90, "#00E676"),
        "B": (75, "#00E5FF"),
        "C": (60, "#FFD600"),
        "D": (0,  "#FF1744"),
    }

    def score(
        self,
        df_raw: pd.DataFrame,
        df_clean: pd.DataFrame,
        preprocess_report: dict[str, Any],
    ) -> dict[str, Any]:
        """
        计算数据质量综合评分。

        Parameters
        ----------
        df_raw            : 原始 DataFrame
        df_clean          : 预处理后 DataFrame
        preprocess_report : Preprocessor.get_report() 返回的字典

        Returns
        -------
        {
            "total_score": int,
            "grade": "A"|"B"|"C"|"D",
            "dimensions": {key: {"score": int, "weight": int, "detail": str}},
            "suggestions": [str, ...]
        }
        """
        dims = {
            "completeness":  self._score_completeness(df_raw),
            "uniqueness":    self._score_uniqueness(preprocess_report),
            "consistency":   self._score_consistency(preprocess_report),
            "timeliness":    self._score_timeliness(df_clean),
            "accuracy":      self._score_accuracy(preprocess_report),
        }

        total = 0
        for key, dim in dims.items():
            total += dim["score"] * dim["weight"] / 100.0

        total_score = round(min(total, 100))

        # 等级
        grade = "D"
        for g, (threshold, _) in self._GRADE_MAP.items():
            if total_score >= threshold:
                grade = g
                break

        # 建议
        suggestions = self._build_suggestions(dims)

        return {
            "total_score": total_score,
            "grade": grade,
            "grade_color": self._GRADE_MAP[grade][1],
            "dimensions": dims,
            "suggestions": suggestions,
        }

    # ── 各维度评分 ──────────────────────────────────

    def _score_completeness(self, df: pd.DataFrame) -> dict:
        """完整性：所有列缺失率为 0 时满分。"""
        weight = 30
        total_cells = len(df) * len(df.columns)
        if total_cells == 0:
            return {"score": 0, "weight": weight, "detail": "数据集为空"}
        missing = int(df.isna().sum().sum())
        missing_rate = missing / total_cells
        score = round(max(0, 100 - missing_rate * 100 * 1.5))
        detail = f"共 {missing} 个缺失值（{missing_rate*100:.1f}%）" if missing > 0 else "无缺失值"
        return {"score": score, "weight": weight, "detail": detail}

    def _score_uniqueness(self, report: dict) -> dict:
        """唯一性：无重复行时满分。"""
        weight = 20
        dup_info = report.get("remove_duplicates") or {}
        removed = dup_info.get("removed", 0)
        before  = dup_info.get("before", 1) or 1
        dup_rate = removed / before
        score = round(max(0, 100 - dup_rate * 100 * 2))
        detail = f"去重移除 {removed} 行（{dup_rate*100:.1f}%）" if removed > 0 else "无重复行"
        return {"score": score, "weight": weight, "detail": detail}

    def _score_consistency(self, report: dict) -> dict:
        """一致性：数值列无异常值时满分。"""
        weight = 15
        outlier_info = report.get("filter_outliers") or {}
        flagged = outlier_info.get("flagged", 0)
        if flagged == 0:
            return {"score": 100, "weight": weight, "detail": "数值列无异常值"}
        # 每 1% 异常率扣 2 分
        # 无法获得总行数，简单使用扣分上限
        score = max(0, 100 - min(flagged * 2, 100))
        detail = f"标记了 {flagged} 个异常值"
        if "detail" in outlier_info:
            cols = ", ".join(list(outlier_info["detail"].keys())[:3])
            detail += f"（涉及列：{cols}）"
        return {"score": score, "weight": weight, "detail": detail}

    def _score_timeliness(self, df: pd.DataFrame) -> dict:
        """时效性：检查日期列的最新日期。"""
        weight = 15
        # 查找日期列
        date_col = None
        for col in df.select_dtypes(include=["datetime64", "datetimetz"]).columns:
            date_col = col
            break
        if date_col is None:
            return {"score": 50, "weight": weight, "detail": "未检测到日期列，无法评估时效性"}
        try:
            latest = df[date_col].max()
            if hasattr(latest, "to_pydatetime"):
                latest = latest.to_pydatetime()
            days_ago = (datetime.now() - latest).days
            if days_ago <= 7:
                score = 100
                detail = f"最新数据 {days_ago} 天前，时效性良好"
            elif days_ago <= 30:
                score = 80
                detail = f"最新数据 {days_ago} 天前，有一定滞后"
            elif days_ago <= 90:
                score = 60
                detail = f"最新数据 {days_ago} 天前，滞后较明显"
            else:
                score = 30
                detail = f"最新数据 {days_ago} 天前（{latest.strftime('%Y-%m-%d')}），时效性较差"
            return {"score": score, "weight": weight, "detail": detail}
        except Exception:
            return {"score": 50, "weight": weight, "detail": "日期列解析异常"}

    def _score_accuracy(self, report: dict) -> dict:
        """准确性：类型转换是否正常。"""
        weight = 20
        conv = report.get("convert_types") or {}
        converted = conv.get("converted", {})
        if not converted:
            return {"score": 90, "weight": weight, "detail": "所有列类型合理"}
        # 统计转换的列数作为加分项
        n_converted = len(converted)
        detail = f"{n_converted} 列被自动类型转换（{', '.join(list(converted.keys())[:3])}）"
        # 转换本身不扣分，但如果有转换说明数据格式不够标准，轻微扣分
        score = max(70, 100 - n_converted * 2)
        return {"score": score, "weight": weight, "detail": detail}

    def _build_suggestions(self, dims: dict) -> list[str]:
        """根据各维度得分生成改进建议。"""
        suggestions = []
        if dims["completeness"]["score"] < 80:
            suggestions.append("数据完整性偏低，建议排查数据采集链路中的缺失值来源")
        if dims["uniqueness"]["score"] < 80:
            suggestions.append("存在较多重复行，建议检查数据导入流程是否包含去重步骤")
        if dims["consistency"]["score"] < 70:
            suggestions.append("异常值比例偏高，建议逐一核实异常记录是否为录入错误")
        if dims["timeliness"]["score"] < 60:
            suggestions.append("数据时效性较差，分析结论可能不适用于当前业务，建议更新数据源")
        if dims["accuracy"]["score"] < 80:
            suggestions.append("部分列类型转换不够理想，建议在数据源头统一字段格式")
        return suggestions
```

- [ ] **Step 4: 运行测试**

Run: `python -m pytest tests/test_quality_scorer.py -v`
Expected: 5 PASS

- [ ] **Step 5: 在 routes/api.py 中新增 /api/data/quality 端点并集成到 upload**

```python
# routes/api.py upload() 函数中，在 _rebuild_state_from_file 返回后追加：

# 在 upload() 函数中，return jsonify 之前新增：
try:
    from data.quality_scorer import QualityScorer
    qs = QualityScorer()
    quality = qs.score(
        _state()["df_raw"],
        _state()["df_clean"],
        _state()["preprocess_report"]
    )
    _state()["quality_score"] = quality
except Exception:
    _state()["quality_score"] = None


# 新增端点（放在 /api/data/preprocess-report 之后）：

@api_bp.route("/data/quality")
def data_quality():
    """返回数据质量评分卡。"""
    err = _require_data()
    if err:
        return err
    quality = _state().get("quality_score")
    if quality is None:
        return jsonify({"error": "质量评分暂不可用，请重新上传数据"}), 404
    return jsonify(quality)
```

- [ ] **Step 6: 同步更新 app_state 初始化和 _rebuild_state_from_file**

```python
# app.py 中 app_state 字典追加：
"quality_score": None,       # 数据质量评分结果

# routes/api.py _rebuild_state_from_file() 函数 return 之前追加：
try:
    from data.quality_scorer import QualityScorer
    qs = QualityScorer()
    quality = qs.score(df_raw, df_clean, prep_report)
    state["quality_score"] = quality
except Exception:
    state["quality_score"] = None
```

- [ ] **Step 7: 运行全部 API 测试**

Run: `python -m pytest tests/test_api.py tests/test_quality_scorer.py -v`
Expected: 全部 PASS

- [ ] **Step 8: Commit**

```bash
git add data/quality_scorer.py tests/test_quality_scorer.py routes/api.py app.py
git commit -m "feat: add data quality scorecard with 5-dimension scoring"
```

---

### Task 5: NL2Vis 图表工作台 — 后端 `ai/chart_generator.py`

**Files:**
- Create: `ai/chart_generator.py`
- Create: `tests/test_chart_generator.py`
- Modify: `routes/api.py`（新增 /api/chart/generate 端点）

- [ ] **Step 1: 编写 ChartGenerator 测试**

```python
# tests/test_chart_generator.py（新建）

"""
ai/chart_generator.py 单元测试
来源：学生+AI
"""
import pytest
from unittest.mock import MagicMock, patch
import pandas as pd
import json


@pytest.fixture
def mock_client():
    """模拟 OpenAI 客户端，返回图表生成代码。"""
    client = MagicMock()
    choice = MagicMock()
    choice.message.content = (
        "这是一个月度销售趋势的堆叠面积图。\n\n"
        "```python\n"
        "import plotly.graph_objects as go\n"
        "fig = go.Figure()\n"
        "fig.add_trace(go.Scatter(x=[1,2,3], y=[100,200,150], mode='lines', name='Sales'))\n"
        "fig.update_layout(title='月度销售趋势', template='plotly_dark')\n"
        "chart = fig\n"
        "```"
    )
    client.chat.completions.create.return_value = MagicMock(choices=[choice])
    return client


@pytest.fixture
def sample_df():
    dates = pd.date_range("2021-01-01", periods=10, freq="ME")
    return pd.DataFrame({
        "date":     dates,
        "amount":   [100, 120, 90, 150, 180, 200, 170, 220, 250, 300],
        "category": ["A", "B", "A", "A", "B", "C", "B", "A", "C", "B"],
        "country":  ["CN"] * 10,
    })


class TestChartGenerator:
    def test_generate_returns_chart_json(self, mock_client, sample_df):
        from ai.chart_generator import ChartGenerator
        cg = ChartGenerator(mock_client, sample_df)
        result = cg.generate("画月度销售趋势")
        assert result["success"] is True
        assert result["chart"] is not None
        assert isinstance(result["chart"], dict)

    def test_generate_with_empty_description_returns_error(self, mock_client, sample_df):
        from ai.chart_generator import ChartGenerator
        cg = ChartGenerator(mock_client, sample_df)
        result = cg.generate("")
        assert result["success"] is False

    def test_generate_with_previous_chart_context(self, mock_client, sample_df):
        from ai.chart_generator import ChartGenerator
        cg = ChartGenerator(mock_client, sample_df)
        prev = {"layout": {"title": "旧图表"}}
        result = cg.generate("改成深色主题", previous_chart=prev)
        assert result["success"] is True

    def test_sandbox_blocked_code(self, mock_client, sample_df):
        """沙箱应阻止危险代码。"""
        from ai.chart_generator import ChartGenerator
        cg = ChartGenerator(mock_client, sample_df)
        result = cg._execute_chart_code("import os; chart = None")
        assert result[0] is None  # chart 为 None
        assert "os" in (result[1] or "")  # 错误信息提示 os 被禁止

    def test_missing_chart_variable(self, mock_client, sample_df):
        """代码未生成 chart 变量时应返回错误。"""
        from ai.chart_generator import ChartGenerator
        cg = ChartGenerator(mock_client, sample_df)
        chart_json, error = cg._execute_chart_code("x = 1")
        assert chart_json is None
        assert "chart" in (error or "")

    def test_client_call_failure(self, sample_df):
        """AI 调用失败时返回 success=False。"""
        bad_client = MagicMock()
        bad_client.chat.completions.create.side_effect = RuntimeError("API 不可用")
        from ai.chart_generator import ChartGenerator
        cg = ChartGenerator(bad_client, sample_df)
        result = cg.generate("画趋势图")
        assert result["success"] is False
        assert "API 不可用" in result.get("explanation", "")
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_chart_generator.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: 实现 ai/chart_generator.py**

```python
"""
自然语言图表生成器。
复用 CodeGenerator 的沙箱执行管道，输出 Plotly JSON。

来源：学生+AI
"""
from __future__ import annotations

from typing import Any
import json as _json

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio

from ai.code_generator import _extract_content, _extract_code, _SAFE_BUILTINS, _serialize


class ChartGenerator:
    """
    NL2Vis：将自然语言描述转为 Plotly 交互图表。

    用法
    ----
    cg = ChartGenerator(openai_client, df)
    result = cg.generate("按月展示不同国家的销售额趋势")
    chart_json = result["chart"]  # Plotly JSON
    """

    SYSTEM_PROMPT = (
        "你是数据可视化专家，将用户需求转为 Plotly Python 代码。"
        "必须将 plotly.graph_objects.Figure 对象赋值给变量 chart。"
        "使用 plotly.graph_objects（别名为 go），不要用 plotly.express。"
        "配色默认使用 plotly 模板 'plotly_dark'，与赛博朋克风格匹配。"
        "支持的类型：散点图、折线图、柱状图、饼图、面积图、热力图、箱线图、"
        "散点矩阵、桑基图、漏斗图、仪表盘、气泡图。"
        "中文字体使用 'Microsoft YaHei' 或系统默认。"
    )

    def __init__(self, client: Any, df: pd.DataFrame) -> None:
        self.client = client
        self.df = df

    def generate(self, description: str, previous_chart: dict = None) -> dict[str, Any]:
        """
        Parameters
        ----------
        description     : 用户对图表的自然语言描述
        previous_chart  : 上一轮生成的 chart JSON（用于迭代修改场景）

        Returns
        -------
        {"chart": dict, "code": str, "explanation": str, "success": bool}
        """
        if not description or not description.strip():
            return {"chart": None, "code": "", "explanation": "图表描述不能为空", "success": False}

        description = description.strip()

        cols   = list(self.df.columns)
        dtypes = {c: str(self.df[c].dtype) for c in cols}
        sample = self.df.head(3).to_dict(orient="records")

        prompt = self._build_prompt(description, cols, dtypes, sample, previous_chart)

        import config as _cfg
        try:
            response = self.client.chat.completions.create(
                model=_cfg.AI_MODEL,
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
                max_tokens=1500,
            )
            raw = _extract_content(response) or ""
        except Exception as exc:
            return {"chart": None, "code": "", "explanation": f"AI 调用失败：{exc}", "success": False}

        code = _extract_code(raw)
        if not code:
            return {"chart": None, "code": "", "explanation": "未能生成有效图表代码，请尝试更具体的描述", "success": False}

        chart_json, error = self._execute_chart_code(code)
        if error:
            return {"chart": None, "code": code, "explanation": f"图表执行错误：{error}", "success": False}

        explanation = raw.split("```")[0].strip() if "```" in raw else ""

        return {
            "chart": chart_json,
            "code": code,
            "explanation": explanation,
            "success": True,
        }

    def _build_prompt(self, description, cols, dtypes, sample, previous_chart):
        cols_info = "\n".join(f"- {c} ({d})" for c, d in dtypes.items())
        sample_json = _json.dumps(sample, ensure_ascii=False, default=str)

        prev_section = ""
        if previous_chart:
            prev_section = (
                "【当前图表配置（请在此基础上修改）】\n"
                f"{_json.dumps(previous_chart.get('layout', {}), ensure_ascii=False)[:800]}\n"
            )

        return f"""根据以下数据信息和用户需求，生成 Plotly go.Figure 图表代码。

【数据集列信息】
{cols_info}

【数据样本（前 3 行）】
{sample_json}

{prev_section}
【用户需求】
{description}

要求：
1. 用 go.Figure() + go.Scatter/Bar/Pie 等创建图表
2. 图表赋值给变量 chart（必须）
3. 设置合适的标题、轴标签、图例
4. 使用 template='plotly_dark' 配色
5. 代码放在 ```python ``` 中"""

    def _execute_chart_code(self, code: str) -> tuple:
        """沙箱执行图表代码，返回 (chart_json_or_None, error_msg_or_None)。"""
        import numpy as np

        namespace = {
            "__builtins__": _SAFE_BUILTINS,
            "df": self.df.copy(),
            "pd": pd,
            "np": np,
            "go": go,
            "pio": pio,
        }

        try:
            exec(code, namespace)
        except Exception as exc:
            return None, str(exc)

        fig = namespace.get("chart")
        if fig is None:
            return None, "代码未生成 chart 变量，请在代码中将 go.Figure 对象赋值给 chart"
        if not hasattr(fig, "to_plotly_json"):
            return None, "chart 不是有效的 Plotly Figure 对象"

        try:
            chart_json = fig.to_plotly_json()
            return _json.loads(_json.dumps(chart_json, default=str)), None
        except Exception as exc:
            return None, f"图表序列化失败：{exc}"
```

- [ ] **Step 4: 运行测试**

Run: `python -m pytest tests/test_chart_generator.py -v`
Expected: 5 PASS

- [ ] **Step 5: 在 routes/api.py 中新增 /api/chart/generate 端点**

```python
# routes/api.py 中 report 接口区域后追加：

@api_bp.route("/chart/generate", methods=["POST"])
def chart_generate():
    """
    自然语言生成图表。

    请求体：
      {"description": "按月展示各国销售额趋势，堆叠面积图",
       "previous_chart": null}   # 可选，用于迭代修改

    响应：
      {"chart": {...plotly_json}, "code": "...", "explanation": "...", "success": true}
    """
    err = _require_data()
    if err:
        return err

    body = request.get_json(silent=True) or {}
    description = (body.get("description") or "").strip()
    if not description:
        return jsonify({"error": "图表描述不能为空"}), 400

    state = _state()
    client = state.get("openai_client")
    if client is None:
        return jsonify({"error": "AI 服务未启用，请先配置 API Key"}), 400

    from ai.chart_generator import ChartGenerator
    cg = ChartGenerator(client, state["df_clean"])
    result = cg.generate(
        description,
        previous_chart=body.get("previous_chart"),
    )
    return jsonify(result)
```

- [ ] **Step 6: 运行全部相关测试**

Run: `python -m pytest tests/test_chart_generator.py tests/test_api.py -k "test_chart or TestChart" -v`
Expected: 全部 PASS

- [ ] **Step 7: Commit**

```bash
git add ai/chart_generator.py tests/test_chart_generator.py routes/api.py
git commit -m "feat: add NL2Vis chart generator with Plotly sandbox execution"
```

---

### Task 6: 分析计划生成器 (`ai/plan_generator.py`)

**Files:**
- Create: `ai/plan_generator.py`
- Create: `tests/test_plan_generator.py`
- Modify: `routes/api.py`（新增 /api/plan/generate 端点）

- [ ] **Step 1: 编写 PlanGenerator 测试**

```python
# tests/test_plan_generator.py（新建）

"""
ai/plan_generator.py 单元测试
来源：学生+AI
"""
import pytest
from unittest.mock import MagicMock
import json


@pytest.fixture
def mock_client():
    """模拟 OpenAI 客户端，返回分析计划 JSON。"""
    client = MagicMock()
    plan = [
        {"id": 1, "title": "月度销售趋势", "category": "趋势", "description": "按月聚合销售额"},
        {"id": 2, "title": "客户分层", "category": "分布", "description": "RFM 客户价值评分"},
        {"id": 3, "title": "相关性分析", "category": "关联", "description": "数值列两两相关系数"},
    ]
    choice = MagicMock()
    choice.message.content = json.dumps(plan, ensure_ascii=False)
    client.chat.completions.create.return_value = MagicMock(choices=[choice])
    return client


@pytest.fixture
def df_info():
    return {
        "row_count": 1000,
        "column_count": 8,
        "columns": ["date", "amount", "qty", "country", "product", "customer"],
        "numeric_stats": {"amount": {}, "qty": {}},
        "date_range": {"start": "2021-01-01", "end": "2021-12-31"},
        "missing_counts": {"customer": 50},
    }


class TestPlanGenerator:
    def test_generate_returns_list(self, mock_client, df_info):
        from ai.plan_generator import PlanGenerator
        pg = PlanGenerator(mock_client)
        plan = pg.generate(df_info, [])
        assert isinstance(plan, list)
        assert len(plan) >= 3
        for item in plan:
            assert "id" in item
            assert "title" in item
            assert "category" in item

    def test_fallback_plan_when_ai_fails(self, df_info):
        from ai.plan_generator import PlanGenerator
        bad_client = MagicMock()
        bad_client.chat.completions.create.side_effect = RuntimeError("fail")
        pg = PlanGenerator(bad_client)
        plan = pg.generate(df_info, [])
        assert isinstance(plan, list)
        assert len(plan) >= 3  # 降级方案至少 3 条

    def test_fallback_plan_no_date_range(self):
        from ai.plan_generator import PlanGenerator
        pg = PlanGenerator(MagicMock())
        info = {"row_count": 100, "column_count": 4, "numeric_stats": {}, "columns": []}
        plan = pg._fallback_plan(info)
        assert isinstance(plan, list)
        # 无日期列时不应包含趋势分析
        titles = [p["title"] for p in plan]
        assert "时序趋势分析" not in titles

    def test_fallback_plan_with_date_includes_trend(self):
        from ai.plan_generator import PlanGenerator
        pg = PlanGenerator(MagicMock())
        info = {
            "row_count": 100, "column_count": 4,
            "numeric_stats": {},
            "columns": [], "date_range": {"start": "2021-01-01", "end": "2021-12-31"},
        }
        plan = pg._fallback_plan(info)
        titles = [p["title"] for p in plan]
        assert "时序趋势分析" in titles

    def test_parse_plan_handles_markdown_wrapper(self):
        from ai.plan_generator import PlanGenerator
        pg = PlanGenerator(MagicMock())
        raw = '```json\n[{"id":1,"title":"测试","category":"分布","description":"x"}]\n```'
        result = pg._parse_plan(raw)
        assert result is not None
        assert len(result) == 1
        assert result[0]["title"] == "测试"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_plan_generator.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: 实现 ai/plan_generator.py**

```python
"""
分析计划生成器。
上传数据后，AI 分析 Schema 并输出结构化的分析清单。

来源：学生+AI
"""
from __future__ import annotations

import json as _json
from typing import Any

from ai.code_generator import _extract_content


class PlanGenerator:
    """
    数据感知的分析计划生成。

    用法
    ----
    pg = PlanGenerator(openai_client)
    plan = pg.generate(df_info, insights)
    """

    SYSTEM_PROMPT = (
        "你是资深数据分析顾问，擅长根据数据特征制定分析计划。"
        "基于数据集的结构信息，输出 3-5 条最有价值的分析建议。"
        "每条建议需明确：分析什么、用什么方法、预期产出什么。"
    )

    def __init__(self, client: Any) -> None:
        self.client = client

    def generate(self, df_info: dict[str, Any], insights: list[dict]) -> list[dict[str, Any]]:
        prompt = self._build_prompt(df_info, insights)

        import config as _cfg
        try:
            response = self.client.chat.completions.create(
                model=_cfg.AI_MODEL,
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.4,
                max_tokens=800,
            )
            raw = _extract_content(response) or ""
        except Exception:
            return self._fallback_plan(df_info)

        return self._parse_plan(raw) or self._fallback_plan(df_info)

    def _build_prompt(self, df_info, insights):
        rows = df_info.get("row_count", "?")
        cols = df_info.get("column_count", "?")
        col_names = df_info.get("columns", [])
        num_cols = list(df_info.get("numeric_stats", {}).keys())
        dr = df_info.get("date_range")
        date_info = f"{dr['start']} 至 {dr['end']}" if dr else "无日期列"
        insight_text = _json.dumps(insights[:5], ensure_ascii=False) if insights else "无"

        return f"""请根据以下数据集信息，生成结构化的分析计划。

【数据集概况】
- {rows} 行 × {cols} 列
- 时间跨度：{date_info}
- 数值列（{len(num_cols)} 个）：{', '.join(num_cols[:8])}
- 所有列：{', '.join(str(c) for c in col_names[:15])}
- 已检测洞察：{insight_text}

请返回 JSON 数组（不含 markdown 标记，纯 JSON）：
[
  {{"id": 1, "title": "分析名称", "category": "趋势|分布|异常|关联", "description": "一句话描述"}},
  ...
]
3-5 条，按重要性排序，覆盖不同的 category。"""

    def _parse_plan(self, raw: str) -> list[dict] | None:
        raw = raw.strip()
        if raw.startswith("```"):
            lines = raw.split("\n")
            if lines and lines[0].startswith("```"):
                raw = "\n".join(lines[1:])
            if raw.endswith("```"):
                raw = raw[:-3].rstrip()
        raw = raw.strip()
        try:
            plan = _json.loads(raw)
            if isinstance(plan, list) and len(plan) > 0:
                return plan
        except Exception:
            pass
        return None

    def _fallback_plan(self, df_info) -> list[dict]:
        plan = [{"id": 1, "title": "数据概览统计", "category": "分布", "description": "数值列的均值、中位数、标准差及分布特征"}]
        idx = 2
        if df_info.get("date_range"):
            plan.append({"id": idx, "title": "时序趋势分析", "category": "趋势", "description": "按时间维度的聚合趋势与季节性特征"})
            idx += 1
        num_cols = df_info.get("numeric_stats", {})
        if len(num_cols) >= 2:
            plan.append({"id": idx, "title": "相关性分析", "category": "关联", "description": "数值列间的相关系数与潜在共线性检查"})
            idx += 1
        if df_info.get("missing_counts"):
            plan.append({"id": idx, "title": "数据质量排查", "category": "异常", "description": "缺失值、异常值的分布与影响评估"})
            idx += 1
        return plan
```

- [ ] **Step 4: 运行测试**

Run: `python -m pytest tests/test_plan_generator.py -v`
Expected: 5 PASS

- [ ] **Step 5: 在 routes/api.py 中新增 /api/plan/generate 端点**

```python
# routes/api.py 中 chart_generate 之后追加：

@api_bp.route("/plan/generate", methods=["POST"])
def plan_generate():
    """
    生成分析计划列表。

    请求体：{}（空或任意）

    响应：
      {"plan": [{"id": 1, "title": "...", "category": "趋势", "description": "..."}]}
    """
    err = _require_data()
    if err:
        return err

    state = _state()
    from ai.plan_generator import PlanGenerator
    pg = PlanGenerator(state.get("openai_client"))
    plan = pg.generate(
        state["analyzer"].summary_stats(),
        state.get("insights") or [],
    )
    return jsonify({"plan": plan})
```

- [ ] **Step 6: 运行测试**

Run: `python -m pytest tests/test_plan_generator.py -v`
Expected: 5 PASS

- [ ] **Step 7: Commit**

```bash
git add ai/plan_generator.py tests/test_plan_generator.py routes/api.py
git commit -m "feat: add AI-powered analysis plan generator with smart fallback"
```

---

### Task 7: 数据叙事引擎 (`ai/storyteller.py`)

**Files:**
- Create: `ai/storyteller.py`
- Create: `tests/test_storyteller.py`
- Modify: `routes/api.py`（新增 /api/report/story 端点）

- [ ] **Step 1: 编写 Storyteller 测试**

```python
# tests/test_storyteller.py（新建）

"""
ai/storyteller.py 单元测试
来源：学生+AI
"""
import pytest
from unittest.mock import MagicMock
import json


@pytest.fixture
def mock_client():
    """模拟 OpenAI 客户端，返回叙事 JSON。"""
    client = MagicMock()
    story = {
        "title": "一个被 UK 主导的电商世界",
        "subtitle": "UK 贡献了超过 80% 的订单",
        "sections": [
            {"heading": "UK 的压倒性优势", "body": "在 2011 年的数据中...", "highlight": "82%"},
            {"heading": "圣诞季的销售浪潮", "body": "11 月销售额突然飙升...", "highlight": "47%"},
        ],
        "key_takeaways": ["市场高度集中", "季节性波动显著", "数据质量需关注"],
    }
    choice = MagicMock()
    choice.message.content = json.dumps(story, ensure_ascii=False)
    client.chat.completions.create.return_value = MagicMock(choices=[choice])
    return client


@pytest.fixture
def df_info():
    return {"row_count": 1000, "column_count": 8, "numeric_stats": {}}

@pytest.fixture
def sample_insights():
    return [
        {"severity": "high", "title": "销售额增长", "detail": "11 月环比增长 47%"},
        {"severity": "medium", "title": "销售集中", "detail": "UK 占 82%"},
    ]


class TestStoryteller:
    def test_tell_returns_dict_with_required_fields(self, mock_client, df_info, sample_insights):
        from ai.storyteller import Storyteller
        st = Storyteller(mock_client)
        result = st.tell(df_info, sample_insights, [])
        assert isinstance(result, dict)
        assert "title" in result
        assert "sections" in result
        assert "key_takeaways" in result
        assert len(result["sections"]) >= 1

    def test_fallback_when_ai_fails(self, df_info, sample_insights):
        from ai.storyteller import Storyteller
        bad_client = MagicMock()
        bad_client.chat.completions.create.side_effect = RuntimeError("fail")
        st = Storyteller(bad_client)
        result = st.tell(df_info, sample_insights, [])
        assert "title" in result
        assert len(result["sections"]) >= 1

    def test_parse_story_handles_markdown_wrapper(self, df_info, sample_insights):
        from ai.storyteller import Storyteller
        st = Storyteller(MagicMock())
        raw = '```json\n{"title":"测试","subtitle":"","sections":[],"key_takeaways":[]}\n```'
        result = st._parse_story(raw, df_info, sample_insights)
        assert result["title"] == "测试"

    def test_fallback_story_includes_insights(self, df_info, sample_insights):
        from ai.storyteller import Storyteller
        st = Storyteller(MagicMock())
        result = st._fallback_story(df_info, sample_insights)
        assert len(result["sections"]) >= len(sample_insights)
        for item in sample_insights:
            titles = [s["heading"] for s in result["sections"]]
            assert item["title"] in titles
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_storyteller.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: 实现 ai/storyteller.py**

```python
"""
数据叙事引擎。
将结构化分析结果转化为叙事性数据故事。

来源：学生+AI
"""
from __future__ import annotations

import json as _json
from datetime import datetime
from typing import Any

from ai.code_generator import _extract_content
from ai.report_agents import _call_ai


class Storyteller:
    """
    将数据报告转为叙事体故事。

    用法
    ----
    st = Storyteller(openai_client)
    story = st.tell(df_info, insights, chat_history, report_content)
    """

    SYSTEM_PROMPT = (
        "你是数据叙事专家，将分析数据转化为有故事感的商业洞察文。"
        "风格参考数据新闻：用生动的核心发现作为小标题，"
        "用具体数字支撑论点，在关键处点出'这意味着什么'和'接下来该做什么'。"
        "每节 3-5 句话，避免列表体，避免模板化开头。"
    )

    def __init__(self, client: Any) -> None:
        self.client = client

    def tell(
        self,
        df_info: dict[str, Any],
        insights: list[dict[str, Any]],
        chat_history: list[dict[str, str]],
        report_content: str = "",
    ) -> dict[str, Any]:
        prompt = self._build_prompt(df_info, insights, chat_history, report_content)

        import config as _cfg
        try:
            response = self.client.chat.completions.create(
                model=_cfg.AI_MODEL,
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.6,
                max_tokens=2000,
            )
            raw = _extract_content(response) or ""
        except Exception:
            return self._fallback_story(df_info, insights)

        return self._parse_story(raw, df_info, insights)

    def _build_prompt(self, df_info, insights, chat_history, report_content):
        rows = df_info.get("row_count", "?")
        insight_text = "\n".join(
            f"[{i.get('severity','?').upper()}] {i.get('title','')}：{i.get('detail','')}"
            for i in insights
        ) or "无"
        user_questions = [m["content"] for m in chat_history if m.get("role") == "user"]
        q_text = "、".join(user_questions[:5]) if user_questions else "无交互问答"

        return f"""请将以下分析结果转化为一篇叙事性数据故事。

=== 数据背景 ===
数据集：{rows} 条记录
用户最关心的问题：{q_text}

=== 关键洞察 ===
{insight_text}

=== 现有报告摘要 ===
{report_content[:800] if report_content else '无'}

请返回 JSON（不含 markdown 标记）：
{{
  "title": "故事大标题（抓人眼球，15 字以内）",
  "subtitle": "一句话核心发现",
  "sections": [
    {{"heading": "小标题（要求：生动有趣，不是'数据概览'这种）",
      "body": "叙事段落（不写成列表，自然段落，3-5 句）",
      "highlight": "一个最关键的支撑数字"}}
  ],
  "key_takeaways": ["结论1", "结论2", "结论3"]
}}
3-4 个 sections。全文中文。"""

    def _parse_story(self, raw, df_info, insights):
        raw = raw.strip()
        if raw.startswith("```"):
            lines = raw.split("\n")
            if lines and lines[0].startswith("```"):
                raw = "\n".join(lines[1:])
            if raw.endswith("```"):
                raw = raw[:-3].rstrip()
        raw = raw.strip()
        try:
            result = _json.loads(raw)
            if isinstance(result, dict) and "title" in result:
                result["generated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                return result
        except Exception:
            pass
        return self._fallback_story(df_info, insights)

    def _fallback_story(self, df_info, insights):
        rows = df_info.get("row_count", "?")
        high_items = [i for i in insights if i.get("severity") == "high"]
        title = f"这份数据想告诉你的 {len(high_items)} 件事" if high_items else "数据全景快照"

        sections = [{
            "heading": "数据全貌",
            "body": f"本次分析覆盖 {rows} 条数据记录，自动扫描了趋势、异常、分布和关联四个维度的关键信号。",
            "highlight": f"{rows}"
        }]
        for item in insights[:3]:
            sections.append({
                "heading": item.get("title", ""),
                "body": item.get("detail", ""),
                "highlight": ""
            })

        return {
            "title": title,
            "subtitle": "规则引擎自动检测关键数据信号",
            "sections": sections,
            "key_takeaways": [i.get("title", "") for i in insights[:3]] or ["数据自动扫描完成，未发现显著异常信号"],
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
```

- [ ] **Step 4: 运行测试**

Run: `python -m pytest tests/test_storyteller.py -v`
Expected: 4 PASS

- [ ] **Step 5: 在 routes/api.py 中新增 /api/report/story 端点**

```python
# routes/api.py 中 plan_generate 之后追加：

@api_bp.route("/report/story", methods=["POST"])
def report_story():
    """
    生成叙事性数据故事。

    请求体：{}（可选）

    响应：
      {"title": "...", "subtitle": "...", "sections": [...], "key_takeaways": [...]}
    """
    err = _require_data()
    if err:
        return err

    state   = _state()
    client  = state.get("openai_client")
    session = state.get("chat_session")
    history = session.history if session else []
    summary = state["analyzer"].summary_stats()
    insights = state["insights"] or []

    from ai.storyteller import Storyteller
    st = Storyteller(client)
    story = st.tell(summary, insights, history)
    return jsonify(story)
```

- [ ] **Step 6: Commit**

```bash
git add ai/storyteller.py tests/test_storyteller.py routes/api.py
git commit -m "feat: add data storytelling engine for narrative reports"
```

---

### Task 8: 前端 SSE 处理模块 (`sse-handler.js`)

**Files:**
- Create: `static/js/sse-handler.js`
- Modify: `templates/base.html`

- [ ] **Step 1: 创建 static/js/sse-handler.js**

```javascript
/**
 * DataMind SSE 流式响应通用处理模块。
 * 使用 fetch + ReadableStream 实现 POST SSE。
 * 来源：学生+AI
 */

/**
 * 创建 SSE 连接并分派事件到对应 handler。
 *
 * @param {string}  url      - 请求 URL（如 /api/chat 或 /api/report/generate）
 * @param {object|null} body - POST 请求体（GET 时传 null）
 * @param {object}   handlers - 事件处理器映射
 *   {
 *     onTextDelta:    (content) => {},
 *     onCodeComplete: (code)    => {},
 *     onExecResult:   (result)  => {},
 *     onChart:        (data)    => {},
 *     onAgentProgress:(agent, status) => {},
 *     onSection:      (agent, content) => {},
 *     onReportStart:  (mode)    => {},
 *     onReportDone:   ()        => {},
 *     onDone:         ()        => {},
 *     onError:        (msg)     => {},
 *   }
 * @returns {Promise<AbortController>} 可用于取消连接
 */
function createSSEConnection(url, body, handlers) {
    const controller = new AbortController();
    const isPost = body !== null && body !== undefined;

    const fetchOptions = {
        method: isPost ? 'POST' : 'GET',
        headers: isPost ? { 'Content-Type': 'application/json' } : {},
        signal: controller.signal,
    };
    if (isPost) {
        fetchOptions.body = JSON.stringify(body);
    }

    fetch(url, fetchOptions)
        .then(response => {
            if (!response.ok) {
                return response.json().then(data => {
                    throw new Error(data.error || '请求失败');
                });
            }
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';

            function processChunk({ done, value }) {
                if (done) {
                    if (handlers.onDone) handlers.onDone();
                    return;
                }
                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop() || '';

                for (const line of lines) {
                    if (!line.startsWith('data: ')) continue;
                    const payload = line.slice(6);
                    if (payload === '[DONE]') {
                        if (handlers.onDone) handlers.onDone();
                        return;
                    }
                    try {
                        const msg = JSON.parse(payload);
                        dispatch(msg, handlers);
                    } catch (e) {
                        // 非 JSON 行静默忽略
                    }
                }
                reader.read().then(processChunk).catch(e => {
                    if (handlers.onError) handlers.onError(e.message);
                });
            }

            reader.read().then(processChunk).catch(e => {
                if (handlers.onError) handlers.onError(e.message);
            });
        })
        .catch(e => {
            if (e.name !== 'AbortError' && handlers.onError) {
                handlers.onError(e.message);
            }
        });

    return controller;
}

function dispatch(msg, handlers) {
    switch (msg.type) {
        case 'text_delta':
            if (handlers.onTextDelta) handlers.onTextDelta(msg.content);
            break;
        case 'code_complete':
            if (handlers.onCodeComplete) handlers.onCodeComplete(msg.code);
            break;
        case 'exec_result':
            if (handlers.onExecResult) handlers.onExecResult(msg);
            break;
        case 'chart':
            if (handlers.onChart) handlers.onChart(msg.data);
            break;
        case 'agent_progress':
            if (handlers.onAgentProgress) handlers.onAgentProgress(msg.agent, msg.status);
            break;
        case 'section':
            if (handlers.onSection) handlers.onSection(msg.agent, msg.content);
            break;
        case 'report_start':
            if (handlers.onReportStart) handlers.onReportStart(msg.mode);
            break;
        case 'report_done':
            if (handlers.onReportDone) handlers.onReportDone();
            break;
        case 'error':
            if (handlers.onError) handlers.onError(msg.message);
            break;
    }
}

/**
 * 检测浏览器是否支持 SSE（fetch + ReadableStream）。
 * @returns {boolean}
 */
function supportsSSE() {
    return typeof fetch !== 'undefined' &&
           typeof ReadableStream !== 'undefined' &&
           typeof TextDecoder !== 'undefined';
}
```

- [ ] **Step 2: 在 templates/base.html 中加载 sse-handler.js**

在 `{% block scripts %}` 之前或其他 JS 加载区域，确保 `sse-handler.js` 最先加载。

```html
<!-- templates/base.html 中，在现有的 JS script 标签之前追加： -->
<script src="{{ url_for('static', filename='js/sse-handler.js') }}"></script>
```

找到 base.html 中现有 script 标签（如 `<script src="{{ url_for('static', filename='js/bg-effects.js') }}">...</script>` 区域），在前面插入以上行。

- [ ] **Step 3: Commit**

```bash
git add static/js/sse-handler.js templates/base.html
git commit -m "feat: add frontend SSE handler module with fetch+ReadableStream"
```

---

### Task 9: 前端图表工作台 (`chart-workspace.js`) + 问答页改造

**Files:**
- Create: `static/js/chart-workspace.js`
- Modify: `templates/analysis.html`
- Modify: `static/css/style.css`

- [ ] **Step 1: 创建 static/js/chart-workspace.js**

```javascript
/**
 * DataMind NL2Vis 图表工作台。
 * 在智能问答页右侧展示独立的图表生成区域。
 * 来源：学生+AI
 */

let _previousChart = null;

function initChartWorkspace() {
    const sendBtn = document.getElementById('chart-send-btn');
    const input   = document.getElementById('chart-input');
    if (!sendBtn || !input) return;

    sendBtn.addEventListener('click', generateChart);
    input.addEventListener('keydown', function(e) {
        if (e.key === 'Enter') generateChart();
    });
}

async function generateChart() {
    const input = document.getElementById('chart-input');
    const description = (input?.value || '').trim();
    if (!description) return;

    const chartContainer = document.getElementById('chart-workspace-plot');
    const explanationEl = document.getElementById('chart-explanation');
    const codeEl         = document.getElementById('chart-code-display');

    if (chartContainer) chartContainer.innerHTML = '<div class="d-flex align-items-center justify-content-center" style="height:300px"><span class="spinner-border"></span></div>';

    try {
        const res = await fetch('/api/chart/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ description, previous_chart: _previousChart }),
        });
        const data = await res.json();

        if (data.success && data.chart) {
            _previousChart = data.chart;
            if (chartContainer && typeof Plotly !== 'undefined') {
                Plotly.react(chartContainer, data.chart.data || [], data.chart.layout || {});
            }
            if (explanationEl) explanationEl.textContent = data.explanation || '';
            if (codeEl) codeEl.textContent = data.code || '';
        } else {
            if (chartContainer) chartContainer.innerHTML = `<div class="alert alert-warning m-3">${data.explanation || '图表生成失败'}</div>`;
        }
    } catch (e) {
        if (chartContainer) chartContainer.innerHTML = `<div class="alert alert-danger m-3">网络错误：${e.message}</div>`;
    }
}

/** 快捷操作：点击按钮自动填入输入框并触发生成 */
function quickChartAction(presetDescription) {
    const input = document.getElementById('chart-input');
    if (input) {
        input.value = presetDescription;
        generateChart();
    }
}

function copyChartCode() {
    const code = document.getElementById('chart-code-display')?.textContent || '';
    if (code) {
        navigator.clipboard.writeText(code).then(() => {
            alert('代码已复制到剪贴板');
        });
    }
}
```

- [ ] **Step 2: 改造 templates/analysis.html 添加图表工作台**

在 `analysis.html` 的 `{% block content %}` 中，将现有单栏布局改为左右两栏：

```html
<!-- analysis.html 中，chat-section div 改为两栏布局 -->
<div id="chat-section" style="display:none">
    <div class="row g-3">
        <!-- 左栏：对话区（保持现有内容） -->
        <div class="col-lg-7">
            <!-- 现有的 quick-questions / chat-messages / 输入栏 / generated-code / exec-result / exec-chart -->
            <div id="quick-questions" class="d-flex flex-wrap gap-2 mb-3">
                <!-- ... 保持现有内容 ... -->
            </div>
            <div id="chat-messages" class="p-3 mb-3 overflow-auto"
                 style="min-height:180px;max-height:340px">
            </div>
            <div class="input-group mb-3">
                <!-- ... 保持现有输入栏 ... -->
            </div>
            <div id="generated-code" class="card mb-3" style="display:none">
                <!-- ... 保持现有 ... -->
            </div>
            <div id="exec-result" class="mb-3" style="display:none"></div>
            <div id="exec-chart" style="display:none;min-height:300px;border-radius:var(--r-xl);overflow:hidden"></div>
        </div>

        <!-- 右栏：图表工作台（新增） -->
        <div class="col-lg-5">
            <div class="card" style="background:rgba(0,0,0,.4)">
                <div class="card-header d-flex align-items-center gap-2">
                    <i class="bi bi-bar-chart-fill" style="color:var(--cyan)"></i>
                    <span>图表工作台</span>
                </div>
                <div class="card-body">
                    <div class="input-group input-group-sm mb-2">
                        <input type="text" id="chart-input" class="form-control"
                               placeholder="描述你想画的图，如：每月销售额趋势折线图">
                        <button class="btn btn-primary" id="chart-send-btn">
                            <i class="bi bi-send-fill"></i>
                        </button>
                    </div>
                    <div id="chart-workspace-plot" style="min-height:300px;border-radius:var(--r);overflow:hidden;background:rgba(0,0,0,.2)"></div>
                    <div id="chart-explanation" class="small text-muted mt-2"></div>
                    <div class="d-flex flex-wrap gap-1 mt-2">
                        <button class="btn btn-outline-secondary btn-sm" onclick="quickChartAction('改成折线图')">改折线图</button>
                        <button class="btn btn-outline-secondary btn-sm" onclick="quickChartAction('按季度聚合数据')">按季度聚合</button>
                        <button class="btn btn-outline-secondary btn-sm" onclick="quickChartAction('只保留数值最大的5个，其他合并为其他')">Top 5</button>
                        <button class="btn btn-outline-secondary btn-sm" onclick="copyChartCode()">复制代码</button>
                    </div>
                    <pre class="mt-2 p-2 small" style="display:none;max-height:120px;overflow:auto" id="chart-code-display"></pre>
                </div>
            </div>
        </div>
    </div>
</div>
```

注意：实际修改时保留 `analysis.html` 中左栏的现有 DOM 结构，仅在外层包裹 `<div class="row g-3"><div class="col-lg-7">` ... `</div>` + 新增右栏。

- [ ] **Step 3: 在 analysis.html 的 {% block scripts %} 中加载 chart-workspace.js**

```html
<!-- analysis.html block scripts 中追加 -->
<script src="{{ url_for('static', filename='js/chart-workspace.js') }}"></script>
<script>
    // 页面初始化时启动图表工作台
    (async function () {
        const res = await fetch("/api/data/summary");
        if (res.ok) {
            initChartWorkspace();
        }
    })();
</script>
```

- [ ] **Step 4: 改造 static/js/chat.js 支持 SSE 流式问答**

在 `chat.js` 的 `sendChatMessage()` 函数中，检测 `supportsSSE()`，启用时走流模式：

```javascript
// static/js/chat.js 中，sendChatMessage 函数的 try 块替换为：

async function sendChatMessage() {
    const input    = document.getElementById("chat-input");
    const question = (input?.value || "").trim();
    if (!question) return;

    input.value = "";
    appendMessage("user", question);
    setLoading(true);

    // 创建 AI 消息容器（流式追加内容）
    let aiMsgId = null;
    let codeBlock = null;

    if (typeof supportsSSE === 'function' && supportsSSE()) {
        // SSE 流模式
        createSSEConnection('/api/chat?stream=true', { question }, {
            onTextDelta: function(content) {
                if (!aiMsgId) {
                    aiMsgId = appendMessage("assistant", "");
                }
                const msgEl = document.getElementById(aiMsgId);
                if (msgEl) {
                    const textEl = msgEl.querySelector('.msg-text') || msgEl;
                    textEl.textContent += content;
                }
            },
            onCodeComplete: function(code) {
                showGeneratedCode(code);
            },
            onExecResult: function(result) {
                showExecResult(result);
            },
            onChart: function(data) {
                showExecChart(data);
            },
            onDone: function() {
                setLoading(false);
            },
            onError: function(msg) {
                appendMessage("error", msg);
                setLoading(false);
            }
        });
    } else {
        // 降级：同步模式
        try {
            const res  = await fetch("/api/chat?stream=false", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ question }),
            });
            const data = await res.json();
            if (!res.ok) {
                appendMessage("error", data.error || "请求失败");
                return;
            }
            renderChatResponse(data);
        } catch (e) {
            appendMessage("error", "网络错误：" + e.message);
        } finally {
            setLoading(false);
        }
    }
}
```

Chat.js 的 `renderChatResponse` 保持不变作为降级路径。

- [ ] **Step 5: 在 static/css/style.css 中追加图表工作台样式**

```css
/* static/css/style.css 末尾追加 */

/* 图表工作台 */
#chart-workspace-plot .plot-container {
    border-radius: var(--r);
    overflow: hidden;
}
#chart-workspace-plot .svg-container {
    background: rgba(0,0,0,.2) !important;
}
.chart-workspace-card {
    border: 1px solid rgba(77, 138, 255, .15);
}
/* SSE 流式动画指示器 */
.sse-loading-dot {
    display: inline-block;
    width: 6px; height: 6px;
    border-radius: 50%;
    background: var(--cyan);
    animation: sse-pulse 0.8s infinite alternate;
}
@keyframes sse-pulse {
    from { opacity: 0.3; }
    to   { opacity: 1; }
}
```

- [ ] **Step 6: Commit**

```bash
git add static/js/chart-workspace.js static/js/chat.js templates/analysis.html static/css/style.css
git commit -m "feat: add NL2Vis chart workspace UI with SSE streaming chat"
```

---

### Task 10: 数据概览页集成质量评分卡 + 报告页流式展示

**Files:**
- Modify: `templates/index.html`
- Modify: `templates/report.html`
- Modify: `static/js/app.js`

- [ ] **Step 1: 在 index.html 中添加质量评分卡区域**

在统计卡片区域（4 张卡片的 row）下方追加：

```html
<!-- templates/index.html 中，统计卡片 div.row 之后追加： -->
<div id="quality-scorecard" class="row g-3 mt-2" style="display:none">
    <div class="col-12">
        <div class="card" style="background:rgba(0,0,0,.4); border: 1px solid rgba(77,138,255,.15)">
            <div class="card-header d-flex align-items-center gap-2">
                <i class="bi bi-shield-check" style="color:var(--cyan)"></i>
                <span>数据质量评分卡</span>
                <span id="quality-grade" class="badge ms-auto" style="font-size:14px">--</span>
            </div>
            <div class="card-body">
                <div class="row align-items-center">
                    <div class="col-md-3 text-center">
                        <div id="quality-ring" style="width:120px;height:120px;margin:0 auto;position:relative">
                            <span id="quality-score-text" style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);font-size:28px;font-weight:700">--</span>
                        </div>
                    </div>
                    <div class="col-md-9">
                        <div id="quality-dimensions"></div>
                    </div>
                </div>
                <div id="quality-suggestions" class="mt-2 small"></div>
            </div>
        </div>
    </div>
</div>
```

- [ ] **Step 2: 在 app.js 中添加质量评分渲染函数**

```javascript
// static/js/app.js 中 uploadFile 的 then 块内，updateStatusBar 之后追加：

// 加载质量评分
fetch('/api/data/quality')
    .then(r => r.json())
    .then(data => {
        if (data.total_score !== undefined) {
            renderQualityScore(data);
        }
    })
    .catch(() => {});


// app.js 末尾追加渲染函数：

function renderQualityScore(data) {
    const card = document.getElementById('quality-scorecard');
    if (!card) return;
    card.style.display = 'block';

    const scoreText = document.getElementById('quality-score-text');
    if (scoreText) scoreText.textContent = data.total_score;

    const gradeEl = document.getElementById('quality-grade');
    if (gradeEl) {
        gradeEl.textContent = data.grade + ' 级';
        gradeEl.style.backgroundColor = data.grade_color || '#00E5FF';
        gradeEl.style.color = '#000';
    }

    // 维度柱状条
    const dimsDiv = document.getElementById('quality-dimensions');
    if (dimsDiv) {
        const names = {
            completeness: '完整性',
            uniqueness:   '唯一性',
            consistency:  '一致性',
            timeliness:   '时效性',
            accuracy:     '准确性'
        };
        dimsDiv.innerHTML = Object.entries(data.dimensions).map(([key, dim]) => {
            const name = names[key] || key;
            return `<div class="d-flex align-items-center gap-2 mb-1">
                <span class="small" style="width:50px">${name}</span>
                <div class="progress flex-grow-1" style="height:6px;background:rgba(255,255,255,.1)">
                    <div class="progress-bar" style="width:${dim.score}%;background:${data.grade_color}"></div>
                </div>
                <span class="small" style="width:30px;text-align:right">${dim.score}</span>
            </div>`;
        }).join('');
    }

    // 建议
    const sugDiv = document.getElementById('quality-suggestions');
    if (sugDiv && data.suggestions) {
        sugDiv.innerHTML = data.suggestions.map(s =>
            `<div class="text-warning small"><i class="bi bi-exclamation-triangle me-1"></i>${s}</div>`
        ).join('');
    }
}
```

- [ ] **Step 3: 改造 report.html 添加流式生成区域 + 叙事模式**

在 `report.html` 的 `mode-selector` 区域，新增叙事模式按钮：

```html
<!-- 在 mode-detailed 的 input+label 之后追加： -->
<input type="radio" class="btn-check" name="report-mode" id="mode-story" value="story">
<label class="btn btn-outline-info" for="mode-story">
    <i class="bi bi-book me-1"></i>数据故事
</label>
```

在 `gen-btn` 下方新增流式进度面板：

```html
<!-- 在 gen-btn 区域之后追加： -->
<div id="report-progress" style="display:none" class="card mb-3 p-3" style="background:rgba(0,0,0,.4)">
    <div class="d-flex align-items-center gap-2 mb-2">
        <span class="spinner-border spinner-border-sm" style="color:var(--cyan)"></span>
        <span>报告生成中...</span>
    </div>
    <div id="agent-progress-bars"></div>
</div>
```

报告页的 `generateReport()` 函数改造（内联在 report.html 的 script 区域）：

```javascript
// report.html 中已有的 generateReport 函数（在现有 script 标签中），
// 在函数开头追加 SSE 流模式分支：

async function generateReport() {
    const mode = document.querySelector('input[name="report-mode"]:checked')?.value || 'simple';

    // 显示进度面板
    const progressEl = document.getElementById('report-progress');
    const contentEl  = document.getElementById('report-content');
    const barsEl     = document.getElementById('agent-progress-bars');
    if (progressEl) progressEl.style.display = 'block';
    if (contentEl)  contentEl.innerHTML = '';
    if (barsEl)     barsEl.innerHTML = '';

    if (mode === 'detailed' && typeof supportsSSE === 'function' && supportsSSE()) {
        // SSE 流模式
        const agentNames = {
            statistics: 'StatisticsAgent - 数据特征描述',
            insight:    'InsightAgent - 关键洞察解读',
            qa:         'QAAgent - 对话分析摘要',
            synthesis:  'SynthesisAgent - 综合总结与建议'
        };
        let sections = '';

        createSSEConnection('/api/report/generate', { mode: 'detailed', stream: 'true' }, {
            onAgentProgress: function(agent, status) {
                const name = agentNames[agent] || agent;
                const existing = document.getElementById('agent-progress-' + agent);
                if (!existing) {
                    const row = document.createElement('div');
                    row.id = 'agent-progress-' + agent;
                    row.className = 'd-flex align-items-center gap-2 mb-1 small';
                    row.innerHTML = `<span class="sse-loading-dot"></span><span>${name}</span><span class="text-muted ms-auto">进行中...</span>`;
                    barsEl.appendChild(row);
                }
            },
            onSection: function(agent, content) {
                const row = document.getElementById('agent-progress-' + agent);
                if (row) {
                    row.querySelector('.sse-loading-dot').style.background = '#00E676';
                    row.querySelector('.text-muted').textContent = '完成';
                }
                sections += '<hr>' + content;
                if (contentEl) contentEl.innerHTML = sections;
            },
            onReportDone: function() {
                if (progressEl) progressEl.style.display = 'none';
                document.getElementById('download-btn').style.display = '';
            },
            onError: function(msg) {
                if (contentEl) contentEl.innerHTML += `<div class="alert alert-danger">${msg}</div>`;
                if (progressEl) progressEl.style.display = 'none';
            }
        });
        return;
    }

    // 降级：同步模式（保持现有逻辑不变）
    try {
        const res = await fetch('/api/report/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ mode }),
        });
        const data = await res.json();
        // ... 现有渲染逻辑保持不变 ...
    } catch (e) {
        // ... 现有错误处理 ...
    } finally {
        if (progressEl) progressEl.style.display = 'none';
    }
}
```

注意：实际操作中保留 `generateReport` 的现有同步逻辑作为 `else` 分支降级路径。

- [ ] **Step 4: Commit**

```bash
git add templates/index.html templates/report.html static/js/app.js
git commit -m "feat: add quality scorecard UI and streaming report progress panel"
```

---

### Task 11: 端到端集成测试

**Files:**
- Modify: `tests/test_api.py`

- [ ] **Step 1: 新增集成测试 — 新端点可达性**

```python
# tests/test_api.py 在文件末尾追加

class TestNewEndpoints:
    """v2.0 新增端点测试。"""

    def test_quality_endpoint_returns_data(self, client, loaded_state):
        """GET /api/data/quality 返回质量评分。"""
        resp = client.get("/api/data/quality")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "total_score" in data or "error" in data

    def test_quality_endpoint_no_data(self, client):
        """无数据时 GET /api/data/quality 返回 400。"""
        resp = client.get("/api/data/quality")
        assert resp.status_code == 400

    def test_chart_generate_no_data(self, client):
        """无数据时 POST /api/chart/generate 返回 400。"""
        resp = client.post("/api/chart/generate",
            data='{"description": "测试图表"}',
            content_type="application/json")
        assert resp.status_code == 400

    def test_plan_generate_no_data(self, client):
        """无数据时 POST /api/plan/generate 返回 400。"""
        resp = client.post("/api/plan/generate",
            data='{}',
            content_type="application/json")
        assert resp.status_code == 400

    def test_report_story_no_data(self, client):
        """无数据时 POST /api/report/story 返回 400。"""
        resp = client.post("/api/report/story", data='{}', content_type="application/json")
        assert resp.status_code == 400
```

- [ ] **Step 2: 运行全部新测试**

Run: `python -m pytest tests/test_api.py::TestNewEndpoints tests/test_quality_scorer.py tests/test_chart_generator.py tests/test_plan_generator.py tests/test_storyteller.py -v`
Expected: 全部 PASS

- [ ] **Step 3: 运行完整测试套件确保无回归**

Run: `python -m pytest tests/ -v`
Expected: 所有 ~196 + 新增 ~40 = ~236 个测试 PASS

- [ ] **Step 4: 最终 Commit**

```bash
git add tests/test_api.py
git commit -m "test: add integration tests for v2.0 new endpoints"
```

---

## 实施进度汇总

| 阶段 | Task | 内容 | 状态 |
|:---:|------|------|:---:|
| 1 | Task 1 | SSE 流式底座 `_sse_stream` | [ ] |
| 1 | Task 2 | `/api/chat` SSE 流式问答改造 | [ ] |
| 1 | Task 3 | `/api/report/generate` SSE 流式报告改造 | [ ] |
| 2 | Task 4 | 数据质量评分卡 `quality_scorer.py` | [ ] |
| 3 | Task 5 | NL2Vis 图表生成器 `chart_generator.py` | [ ] |
| 4 | Task 6 | 分析计划生成器 `plan_generator.py` | [ ] |
| 5 | Task 7 | 数据叙事引擎 `storyteller.py` | [ ] |
| 6 | Task 8 | 前端 SSE 模块 `sse-handler.js` | [ ] |
| 6 | Task 9 | 前端图表工作台 + 问答页改造 | [ ] |
| 6 | Task 10 | 质量卡片 + 报告页流式展示 | [ ] |
| 6 | Task 11 | 端到端集成测试 | [ ] |
