"""
REST API 路由蓝图 — DataMind 后端接口。

接口清单：
  GET  /api/ping                      健康检查
  POST /api/upload                    上传并处理数据文件
  GET  /api/data/summary              数据集概览统计
  GET  /api/data/preview              前 N 行数据预览
  GET  /api/data/preprocess-report    预处理步骤摘要
  GET  /api/data/quality              数据质量评分卡
  GET  /api/insights                  自动洞察列表
  GET  /api/analysis/<method>         调用内置分析方法
  POST /api/chat                      AI 问答（代码生成+执行）
  GET  /api/chat/history              对话历史
  POST /api/chat/reset                重置对话
  POST /api/report/generate           生成 Markdown 分析报告

来源：学生+AI
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from flask import Blueprint, Response, current_app, jsonify, request, stream_with_context

import config
from data.loader import UnsupportedFormatError, load_file
from data.preprocessor import Preprocessor
from data.analyzer import Analyzer
from data.detector import Detector
from ai.chat import ChatSession
from ai.insight import InsightEngine

api_bp = Blueprint("api", __name__)


# ── SSE 流式响应通用包装器 ────────────────────────────────────

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
                yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
        except GeneratorExit:
            raise
        except Exception as exc:
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"

    return Response(
        stream_with_context(_generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )

# ── 持久化文件路径 ─────────────────────────────────────────────
_LAST_UPLOAD_FILE = os.path.join(config.UPLOAD_FOLDER, ".last_upload.json")
_AI_CONFIG_FILE   = os.path.join(config.UPLOAD_FOLDER, ".ai_config.json")


# ── 内部工具 ──────────────────────────────────────────────────

def _state() -> dict[str, Any]:
    """返回 Flask app.state 全局状态字典。"""
    return current_app.state  # type: ignore[attr-defined]


def _save_last_upload(save_path: str) -> None:
    """持久化最近上传的文件路径，供服务重启后自动恢复。"""
    try:
        os.makedirs(os.path.dirname(_LAST_UPLOAD_FILE), exist_ok=True)
        with open(_LAST_UPLOAD_FILE, "w", encoding="utf-8") as f:
            json.dump({"path": save_path}, f)
    except Exception:
        pass


def _save_ai_config(api_key: str, base_url: str, model: str) -> None:
    """持久化 AI 配置，供服务重启后自动恢复。"""
    try:
        os.makedirs(os.path.dirname(_AI_CONFIG_FILE), exist_ok=True)
        with open(_AI_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump({"api_key": api_key, "base_url": base_url, "model": model}, f)
    except Exception:
        pass


def _try_restore_ai_config() -> None:
    """从磁盘恢复 AI 配置（服务重启后 code_generator 为 None 时调用）。"""
    state = _state()
    if state.get("code_generator") is not None:
        return
    # 优先使用环境变量中的 API Key
    api_key  = config.AI_API_KEY
    base_url = config.AI_BASE_URL
    model    = config.AI_MODEL
    # 若环境变量无 Key，尝试读取持久化配置
    if not api_key and os.path.exists(_AI_CONFIG_FILE):
        try:
            with open(_AI_CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
            api_key  = saved.get("api_key", "")
            base_url = saved.get("base_url", config.AI_BASE_URL)
            model    = saved.get("model", config.AI_MODEL)
        except Exception:
            pass
    if api_key:
        try:
            _apply_ai_config(api_key, base_url, model)
        except Exception:
            pass


def _rebuild_state_from_file(save_path: str) -> dict:
    """从已存在的文件重建全局状态，返回 {summary, prep_report}。"""
    df_raw       = load_file(save_path)
    preprocessor = Preprocessor(df_raw)
    df_clean     = preprocessor.run_all()
    prep_report  = preprocessor.get_report()
    analyzer     = Analyzer(df_clean)
    detector     = Detector(df_clean)
    insights     = InsightEngine(df_clean, analyzer, detector).generate_all()
    summary      = analyzer.summary_stats()

    state = _state()
    state["df_raw"]            = df_raw
    state["df_clean"]          = df_clean
    state["preprocess_report"] = prep_report
    state["analyzer"]          = analyzer
    state["detector"]          = detector
    state["insights"]          = insights
    state["chat_session"]      = ChatSession(summary)

    # 质量评分
    from data.quality_scorer import QualityScorer
    scorer = QualityScorer()
    state["quality_score"] = scorer.score(df_raw, df_clean, prep_report)

    return {"summary": summary, "prep_report": prep_report}


def _try_auto_reload() -> None:
    """服务重启后自动从最近上传的文件重建状态。"""
    if not os.path.exists(_LAST_UPLOAD_FILE):
        return
    try:
        with open(_LAST_UPLOAD_FILE, "r", encoding="utf-8") as f:
            saved = json.load(f)
        save_path = saved.get("path", "")
        if save_path and os.path.exists(save_path):
            _rebuild_state_from_file(save_path)
            _try_restore_ai_config()
    except Exception:
        pass


def _require_data():
    """数据未上传时尝试自动重载；仍无数据则返回 400。"""
    if _state().get("df_clean") is None:
        _try_auto_reload()
    if _state().get("df_clean") is None:
        return jsonify({"error": "请先上传数据文件"}), 400
    return None


def _df_to_records(df: pd.DataFrame, n: int = 100) -> list[dict]:
    """将 DataFrame 转为 JSON 可序列化的记录列表。"""
    subset = df.head(n).copy()
    # datetime 列转字符串
    for col in subset.select_dtypes(include=["datetime64", "datetimetz"]).columns:
        subset[col] = subset[col].astype(str)
    # 用 JSON round-trip 统一处理 numpy 类型和 NaN
    return json.loads(subset.to_json(orient="records", date_format="iso", default_handler=str))


# ── 健康检查 ──────────────────────────────────────────────────

@api_bp.route("/ping")
def ping():
    """健康检查：确认服务正常运行。"""
    return jsonify({"status": "ok", "message": "DataMind API is running"})


# ── 文件上传 ──────────────────────────────────────────────────

@api_bp.route("/upload", methods=["POST"])
def upload():
    """
    上传数据文件，触发预处理→分析→洞察流水线。

    表单字段：file（multipart/form-data）
    """
    if "file" not in request.files:
        return jsonify({"error": "未找到上传文件字段 'file'"}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "文件名为空"}), 400

    ext = Path(file.filename).suffix.lower().lstrip(".")
    if ext not in config.ALLOWED_EXTENSIONS:
        return jsonify({"error": f"不支持的文件格式：.{ext}，"
                                  f"支持：{', '.join(config.ALLOWED_EXTENSIONS)}"}), 400

    # 保存到 datasets 目录
    os.makedirs(config.UPLOAD_FOLDER, exist_ok=True)
    save_path = os.path.join(config.UPLOAD_FOLDER, file.filename)
    file.save(save_path)

    try:
        # 重建状态（读取→预处理→分析→洞察）
        result      = _rebuild_state_from_file(save_path)
        summary     = result["summary"]
        prep_report = result["prep_report"]

        # 初始化 AI 客户端（有 API Key 时）
        _try_restore_ai_config()

        # 持久化文件路径，供服务重启后自动恢复
        _save_last_upload(save_path)

        return jsonify({
            "status":       "ok",
            "filename":     file.filename,
            "row_count":    prep_report["original_rows"],
            "clean_rows":   prep_report["final_rows"],
            "column_count": summary["column_count"],
            "quality_grade": _state()["quality_score"]["grade"],
        })

    except UnsupportedFormatError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": f"处理文件时出错：{exc}"}), 500


# ── 数据接口 ──────────────────────────────────────────────────

@api_bp.route("/data/summary")
def data_summary():
    """返回数据集概览统计（Analyzer.summary_stats）。"""
    err = _require_data()
    if err:
        return err
    return jsonify(_state()["analyzer"].summary_stats())


@api_bp.route("/data/preview")
def data_preview():
    """返回前 n 行数据（默认 100）。"""
    err = _require_data()
    if err:
        return err
    n = request.args.get("n", 100, type=int)
    return jsonify(_df_to_records(_state()["df_clean"], n))


@api_bp.route("/data/preprocess-report")
def preprocess_report():
    """返回预处理步骤摘要。"""
    err = _require_data()
    if err:
        return err
    return jsonify(_state()["preprocess_report"])


@api_bp.route("/data/quality")
def data_quality():
    """返回数据质量评分卡。"""
    err = _require_data()
    if err:
        return err
    state = _state()
    qs = state.get("quality_score")
    if qs is None:
        # 按需计算
        from data.quality_scorer import QualityScorer
        scorer = QualityScorer()
        qs = scorer.score(
            state["df_raw"],
            state["df_clean"],
            state.get("preprocess_report", {}),
        )
        state["quality_score"] = qs
    return jsonify(qs)


# ── 洞察接口 ──────────────────────────────────────────────────

@api_bp.route("/insights")
def insights():
    """返回自动洞察列表。"""
    err = _require_data()
    if err:
        return err
    return jsonify(_state()["insights"] or [])


# ── 分析接口 ──────────────────────────────────────────────────

_SUPPORTED_METHODS = frozenset({
    "summary_stats", "sales_trend", "top_products",
    "rfm_analysis", "country_distribution",
    "correlation_matrix", "time_pattern",
})


@api_bp.route("/analysis/<method>")
def analysis(method: str):
    """
    调用内置分析方法。

    支持：summary_stats / sales_trend / top_products / rfm_analysis /
          country_distribution / correlation_matrix / time_pattern

    可选查询参数：
      sales_trend  : freq=ME|W|D（默认 ME）
      top_products : n=<int>（默认 10）
    """
    err = _require_data()
    if err:
        return err

    if method not in _SUPPORTED_METHODS:
        return jsonify({"error": f"未知分析方法：{method}"}), 404

    az = _state()["analyzer"]

    if method == "sales_trend":
        result = az.sales_trend(freq=request.args.get("freq", "ME"))
    elif method == "top_products":
        result = az.top_products(n=request.args.get("n", 10, type=int))
    elif method == "summary_stats":
        result = az.summary_stats()
    elif method == "rfm_analysis":
        result = az.rfm_analysis()
    elif method == "country_distribution":
        result = az.country_distribution()
    elif method == "correlation_matrix":
        result = az.correlation_matrix()
    else:  # time_pattern
        result = az.time_pattern()

    return jsonify(result)


# ── 对话接口 ──────────────────────────────────────────────────

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
    def _chat_stream():
        messages = list(context) + [{"role": "user", "content": question}]
        full_text = ""

        try:
            stream = cg.client.chat.completions.create(
                model=config.AI_MODEL,
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

            # 提取代码块并执行（先做安全检查）
            code = cg.extract_code(full_text)
            if code:
                if not cg.validate_code(code):
                    yield {"type": "error", "message": "代码包含危险操作，已被拒绝执行"}
                else:
                    yield {"type": "code_complete", "code": code}
                    exec_result = cg.execute_safe(code, df)
                    yield {"type": "exec_result", "success": exec_result["success"], "result": exec_result.get("result")}
                    chart_data = exec_result.get("chart")
                    if chart_data:
                        yield {"type": "chart", "data": chart_data}

            # 记录到 ChatSession
            if session:
                session.add_message("user", question)
                session.add_message("assistant", full_text)
        except Exception as exc:
            yield {"type": "error", "message": str(exc)}
        yield {"type": "done"}

    return _sse_stream(_chat_stream)


@api_bp.route("/chat/history")
def chat_history():
    """返回当前对话历史列表。"""
    err = _require_data()
    if err:
        return err
    session = _state().get("chat_session")
    return jsonify(session.history if session else [])


@api_bp.route("/chat/reset", methods=["POST"])
def chat_reset():
    """重置对话历史（保留数据集信息）。"""
    err = _require_data()
    if err:
        return err
    session = _state().get("chat_session")
    if session:
        session.reset()
    return jsonify({"status": "ok"})


# ── AI 配置接口 ───────────────────────────────────────────────

def _init_ai_client(api_key: str, base_url: str) -> Any:
    """
    用给定的 api_key / base_url 创建 OpenAI 兼容客户端。
    所有支持 OpenAI 接口格式的服务商（包括国内中转站）均可复用。
    """
    from openai import OpenAI
    return OpenAI(api_key=api_key, base_url=base_url)


def _apply_ai_config(api_key: str, base_url: str, model: str) -> None:
    """更新 config 模块变量并重建 AI 组件。"""
    import config as _cfg
    from ai.code_generator import CodeGenerator
    from ai.report import ReportGenerator

    _cfg.AI_API_KEY   = api_key
    _cfg.AI_BASE_URL  = base_url
    _cfg.AI_MODEL     = model
    # 向后兼容字段同步
    _cfg.OPENAI_API_KEY = api_key
    _cfg.OPENAI_MODEL   = model

    state  = _state()
    client = _init_ai_client(api_key, base_url)
    state["openai_client"]    = client
    state["code_generator"]   = CodeGenerator(client)
    state["report_generator"] = ReportGenerator(client)
    # 持久化 AI 配置，供服务重启后自动恢复
    _save_ai_config(api_key, base_url, model)


@api_bp.route("/config/ai", methods=["GET"])
def get_ai_config():
    """
    返回当前 AI 服务配置及所有预置服务商列表。

    响应：
      {
        "current": {"api_key": "sk-...", "base_url": "...", "model": "..."},
        "providers": { <provider_id>: {"name", "base_url", "models"}, ... }
      }
    """
    import config as _cfg
    return jsonify({
        "current": {
            "api_key":  _cfg.AI_API_KEY,
            "base_url": _cfg.AI_BASE_URL,
            "model":    _cfg.AI_MODEL,
        },
        "providers": _cfg.AI_PROVIDERS,
    })


@api_bp.route("/config/ai", methods=["POST"])
def set_ai_config():
    """
    更新 AI 服务配置并重建客户端。

    请求体：
      {"api_key": "sk-...", "base_url": "https://...", "model": "gpt-4o-mini"}

    响应：{"status": "ok"} 或 {"error": "..."}
    """
    body    = request.get_json(silent=True) or {}
    api_key = (body.get("api_key") or "").strip()
    base_url = (body.get("base_url") or "https://api.openai.com/v1").strip()
    model   = (body.get("model") or "gpt-4o-mini").strip()

    if not api_key:
        return jsonify({"error": "API Key 不能为空"}), 400
    if not base_url:
        return jsonify({"error": "Base URL 不能为空"}), 400
    # 常见错误：填了网站首页地址而不是 API 端点（应以 /v1 结尾）
    if not base_url.rstrip("/").endswith(("/v1", "/v1beta", "/api")):
        return jsonify({
            "error": (
                f"Base URL 格式可能有误：'{base_url}' 通常应以 /v1 结尾，"
                "例如 https://api.openai.com/v1 或 https://your-proxy.com/v1"
            )
        }), 400

    try:
        _apply_ai_config(api_key, base_url, model)
        return jsonify({"status": "ok"})
    except Exception as exc:
        return jsonify({"error": f"配置失败：{exc}"}), 500


@api_bp.route("/config/ai/test", methods=["POST"])
def test_ai_config():
    """
    用当前（或临时提供的）配置发送一条最小 Chat 请求，验证连通性。

    请求体（可选，不传则使用已保存配置）：
      {"api_key": "...", "base_url": "...", "model": "..."}

    响应：
      {"status": "ok",    "model": "gpt-4o-mini", "latency_ms": 312}
      {"status": "error", "error": "Invalid API key"}
    """
    import time, config as _cfg

    body     = request.get_json(silent=True) or {}
    api_key  = (body.get("api_key")  or _cfg.AI_API_KEY).strip()
    base_url = (body.get("base_url") or _cfg.AI_BASE_URL).strip()
    model    = (body.get("model")    or _cfg.AI_MODEL).strip()

    if not api_key:
        return jsonify({"status": "error", "error": "请先填写 API Key"}), 400

    try:
        client = _init_ai_client(api_key, base_url)
        t0 = time.time()
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=8,
            temperature=0,
        )
        latency = round((time.time() - t0) * 1000)

        # 防御性取字段：部分国内服务商响应结构与标准 OpenAI 存在细微差异，
        # 不能假设 resp 一定是 ChatCompletion 对象。
        resp_model = _safe_get_model(resp, model)
        return jsonify({
            "status":     "ok",
            "model":      resp_model,
            "latency_ms": latency,
        })
    except Exception as exc:
        return jsonify({"status": "error", "error": str(exc)}), 200


def _safe_get_model(resp: Any, fallback: str) -> str:
    """从响应对象中安全提取模型名，兼容非标准响应结构。"""
    try:
        val = getattr(resp, "model", None)
        return str(val) if val else fallback
    except Exception:
        return fallback


# ── 报告接口 ──────────────────────────────────────────────────

@api_bp.route("/report/generate", methods=["POST"])
def report_generate():
    """
    生成数据分析报告。

    请求体（可选）：
      {"mode": "simple"}   — 简单模式（默认），使用单 AI 调用生成精简报告
      {"mode": "detailed"} — 深度模式，使用四 Agent 框架生成 ~3000 字深度报告
      {"stream": "true"}   — 是否 SSE 流式输出（默认 true，detailed 模式）

    响应：{title, content, generated_at, html, mode} 或 SSE 流
    """
    err = _require_data()
    if err:
        return err

    body = request.get_json(silent=True) or {}
    mode = (body.get("mode") or "simple").strip().lower()
    if mode not in ("simple", "detailed"):
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

    # 简洁模式 或 明确关闭流：使用同步 JSON 路径
    if mode == "simple" or not use_stream:
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

        # Agent 1: Statistics
        yield {"type": "agent_progress", "agent": "statistics", "status": "running"}
        try:
            stats_agent = StatisticsAgent(client, model)
            stats_section = stats_agent.generate(enriched_info)
        except Exception as e:
            yield {"type": "agent_error", "agent": "statistics", "message": str(e)}
            stats_section = f"## 数据特征统计\n\n数据特征统计生成失败：{e}"
        yield {"type": "section", "agent": "statistics", "content": stats_section}

        # Agent 2: Insight
        yield {"type": "agent_progress", "agent": "insight", "status": "running"}
        try:
            insight_agent = InsightAgent(client, model)
            insight_section = insight_agent.generate(insights)
        except Exception as e:
            yield {"type": "agent_error", "agent": "insight", "message": str(e)}
            insight_section = f"## 关键洞察\n\n关键洞察生成失败：{e}"
        yield {"type": "section", "agent": "insight", "content": insight_section}

        # Agent 3: QA
        yield {"type": "agent_progress", "agent": "qa", "status": "running"}
        try:
            qa_agent = QAAgent(client, model)
            qa_section = qa_agent.generate(history)
        except Exception as e:
            yield {"type": "agent_error", "agent": "qa", "message": str(e)}
            qa_section = f"## 对话问答摘要\n\n对话问答摘要生成失败：{e}"
        yield {"type": "section", "agent": "qa", "content": qa_section}

        # Agent 4: Synthesis
        yield {"type": "agent_progress", "agent": "synthesis", "status": "running"}
        try:
            synthesis_agent = SynthesisAgent(client, model)
            synthesis_section = synthesis_agent.generate(stats_section, insight_section, qa_section, enriched_info)
        except Exception as e:
            yield {"type": "agent_error", "agent": "synthesis", "message": str(e)}
            synthesis_section = f"## 总结与建议\n\n总结与建议生成失败：{e}"
        yield {"type": "section", "agent": "synthesis", "content": synthesis_section}

        yield {"type": "report_done"}

    return _sse_stream(_report_stream)
