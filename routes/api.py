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
  POST /api/chart/generate            自然语言图表生成（NL2Vis）
  GET  /api/analysis/<method>         调用内置分析方法
  POST /api/chat                      AI 问答（代码生成+执行）
  GET  /api/chat/history              对话历史
  POST /api/chat/reset                重置对话
  POST /api/report/generate           生成 Markdown 分析报告
  POST /api/report/story              生成数据叙事故事
  POST /api/plan/generate            生成智能分析计划清单

来源：学生+AI
"""
from __future__ import annotations

import json
import os
import queue
import threading
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
    state["chat_session"]      = ChatSession.restore_from_disk(summary)

    # 质量评分
    from data.quality_scorer import QualityScorer
    scorer = QualityScorer()
    state["quality_score"] = scorer.score(df_raw, df_clean, prep_report)

    # 集成数据画像
    try:
        from data.profiler import DataProfiler
        profile = DataProfiler(df_clean).detect()
        df_summary = summary
        df_summary["col_info"]            = profile["col_info"]
        df_summary["profile_mode"]        = profile["mode"]
        df_summary["profile_mode_name"]   = profile["display_name"]
        df_summary["suggested_questions"] = profile["suggested_questions"]
        df_summary["description"]         = profile["description"]
        df_summary["target_col"]          = profile["target_col"]
        state["profile"]                  = profile
    except Exception:
        pass  # 画像检测失败不影响核心功能

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


# ── 通用化分析接口 ─────────────────────────────────────────────

@api_bp.route("/analysis/data_profile")
def data_profile():
    """返回数据画像（6种模式 + 列信息 + 建议问题 + 自描述）。"""
    err = _require_data()
    if err:
        return err
    state = _state()
    profile = state.get("profile")
    if profile is None:
        from data.profiler import DataProfiler
        profile = DataProfiler(state["df_clean"]).detect()
        state["profile"] = profile
    return jsonify(profile)


@api_bp.route("/analysis/adaptive_charts")
def adaptive_charts():
    """
    按数据画像返回 6 个自适应图表配置。
    每个配置包含 type/title/data，由前端 Plotly 渲染。
    """
    err = _require_data()
    if err:
        return err
    state     = _state()
    df        = state["df_clean"]
    az        = state["analyzer"]
    profile   = state.get("profile") or {}
    mode      = profile.get("mode", "mixed")
    pp_report = state.get("preprocess_report", {})

    charts: list[dict] = []

    if mode == "retail":
        _methods = ["sales_trend", "top_products", "country_distribution",
                    "correlation_matrix", "time_pattern", "rfm_analysis"]
        for m in _methods:
            try:
                data = getattr(az, m)()
                charts.append({"method": m, "data": data, "source": "retail"})
            except Exception as e:
                charts.append({"method": m, "data": None, "error": str(e), "source": "retail"})
        return jsonify(charts)

    # 通用路径：按画像选择图表
    numeric_cols     = profile.get("numeric_cols", [])
    categorical_cols = profile.get("categorical_cols", [])
    target_col       = profile.get("target_col")
    date_col         = profile.get("date_col")

    # 图表1：时序折线 or 数值分布
    if mode == "temporal" and date_col:
        try:
            charts.append({
                "type": "line", "title": f"{date_col} 时间趋势",
                "data": az.sales_trend(), "source": "temporal"
            })
        except Exception:
            charts.append(_make_hist_chart(az, numeric_cols))
    else:
        charts.append(_make_hist_chart(az, numeric_cols))

    # 图表2：相关性矩阵
    try:
        charts.append({
            "type": "heatmap", "title": "相关性矩阵",
            "data": az.correlation_matrix(), "source": "generic"
        })
    except Exception:
        charts.append({"type": "heatmap", "title": "相关性矩阵", "data": None})

    # 图表3：箱线图
    box_data = az.box_plots(max_cols=6)
    charts.append({"type": "box", "title": "数值列分布箱线图",
                   "data": box_data, "source": "generic"})

    # 图表4：散点图 or 类别频次
    if len(numeric_cols) >= 2:
        scatter_data = az.scatter_top_pairs(n_pairs=1)
        if scatter_data:
            pair = scatter_data[0]
            charts.append({
                "type": "scatter",
                "title": f"{pair['x_col']} vs {pair['y_col']}（相关系数 {pair['corr']:.2f}）",
                "data": scatter_data, "source": "generic"
            })
        else:
            charts.append(_make_cat_chart(az, categorical_cols))
    else:
        charts.append(_make_cat_chart(az, categorical_cols))

    # 图表5：目标列分布 or 类别列
    if target_col:
        try:
            vc = df[target_col].value_counts()
            charts.append({
                "type": "bar",
                "title": f"{target_col} 分布",
                "data": {"labels": [str(x) for x in vc.index.tolist()],
                         "counts": [int(x) for x in vc.values.tolist()],
                         "col": target_col},
                "source": "generic"
            })
        except Exception:
            charts.append(_make_cat_chart(az, categorical_cols))
    elif categorical_cols:
        charts.append(_make_cat_chart(az, categorical_cols))
    else:
        charts.append(_make_hist_chart(az, numeric_cols, offset=1))

    # 图表6：预处理前后对比
    viz = az.preprocess_visual(pp_report)
    charts.append({"type": "bar_grouped", "title": "数据清洗前后对比",
                   "data": viz["before_after"], "source": "preprocess"})

    return jsonify(charts)


def _make_hist_chart(az, numeric_cols: list, offset: int = 0) -> dict:
    """构造直方图图表配置。"""
    try:
        data = az.numeric_distributions(max_cols=6)
        if offset and len(data) > offset:
            data = data[offset:]
        return {"type": "histogram", "title": "数值列分布", "data": data, "source": "generic"}
    except Exception:
        return {"type": "histogram", "title": "数值列分布", "data": [], "source": "generic"}


def _make_cat_chart(az, categorical_cols: list) -> dict:
    """构造类别频次图表配置。"""
    try:
        data = az.category_distributions(max_cols=1)
        col  = data[0]["col"] if data else "分类列"
        return {"type": "bar", "title": f"{col} 频次分布",
                "data": data[0] if data else {}, "source": "generic"}
    except Exception:
        return {"type": "bar", "title": "分类频次", "data": {}, "source": "generic"}


@api_bp.route("/analysis/suggested_questions")
def suggested_questions():
    """返回 4 个基于真实数据的建议问题。"""
    err = _require_data()
    if err:
        return err
    state   = _state()
    profile = state.get("profile") or {}
    qs      = profile.get("suggested_questions", [
        "这份数据有哪些主要特征？",
        "哪些列有异常值？",
        "数值列的分布情况如何？",
        "列之间的相关性如何？",
    ])
    return jsonify(qs)


@api_bp.route("/data/download-clean")
def download_clean():
    """下载清洗后的 DataFrame 为 CSV 文件。"""
    err = _require_data()
    if err:
        return err
    import io
    state = _state()
    df    = state["df_clean"]
    buf   = io.StringIO()
    df.to_csv(buf, index=False, encoding="utf-8-sig")
    buf.seek(0)
    from flask import Response
    return Response(
        buf.getvalue().encode("utf-8-sig"),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=cleaned_data.csv"},
    )


@api_bp.route("/analysis/preprocess_visual")
def preprocess_visual_api():
    """返回预处理可视化数据（前后对比 + 缺失值热力图）。"""
    err = _require_data()
    if err:
        return err
    state     = _state()
    az        = state["analyzer"]
    pp_report = state.get("preprocess_report", {})
    return jsonify(az.preprocess_visual(pp_report))


# ── 图表生成接口 ──────────────────────────────────────────────

@api_bp.route("/chart/generate", methods=["POST"])
def chart_generate():
    """
    NL2Vis 自然语言图表生成。

    请求体：
      {"description": "...", "previous_chart": {...} }

    响应：{success, chart, explanation}
    """
    err = _require_data()
    if err:
        return err

    body = request.get_json(silent=True) or {}
    description = (body.get("description") or "").strip()
    if not description:
        return jsonify({"error": "图表描述不能为空"}), 400

    state = _state()

    from ai.chart_generator import ChartGenerator
    cg = ChartGenerator(state.get("openai_client"))
    try:
        result = cg.generate(
            description,
            state["df_clean"],
            previous_chart=body.get("previous_chart"),
        )
        return jsonify(result)
    except Exception as exc:
        return jsonify({"success": False, "explanation": f"图表服务异常：{exc}"}), 500


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
                max_tokens=config.AI_MAX_TOKENS,
                stream=True,
                timeout=config.AI_REQUEST_TIMEOUT,
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

            # 提取代码块并在后台线程中执行，避免阻塞 SSE 流
            code = cg.extract_code(full_text)
            if code:
                if not cg.validate_code(code):
                    yield {"type": "error", "message": "代码包含危险操作，已被拒绝执行"}
                else:
                    yield {"type": "code_complete", "code": code}
                    result_queue: queue.Queue = queue.Queue()

                    def _run_code():
                        try:
                            exec_result = cg.execute_safe(code, df)
                            result_queue.put(("ok", exec_result))
                        except Exception as exc:
                            result_queue.put(("err", str(exc)))

                    t = threading.Thread(target=_run_code, daemon=True)
                    t.start()

                    # 轮询队列，每 1s 发送心跳，最长等待 60s
                    elapsed = 0
                    exec_result = None
                    while elapsed < config.CODE_EXEC_TIMEOUT:
                        try:
                            status, data = result_queue.get(timeout=1.0)
                            if status == "ok":
                                exec_result = data
                            else:
                                yield {"type": "error", "message": f"代码执行异常：{data}"}
                            break
                        except queue.Empty:
                            elapsed += 1
                            yield {"type": "heartbeat"}

                    if exec_result is None:
                        yield {"type": "error", "message": f"代码执行超时（{config.CODE_EXEC_TIMEOUT}s）"}
                    else:
                        yield {"type": "exec_result", "success": exec_result["success"], "result": exec_result.get("result"), "stdout": exec_result.get("stdout"), "error": exec_result.get("error")}
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


@api_bp.route("/report/story", methods=["POST"])
def report_story():
    """
    生成数据叙事。

    请求体（可选）：
      {"report_content": "..."}  — 已有报告 Markdown 内容

    响应：{title, subtitle, sections, key_takeaways}
    """
    err = _require_data()
    if err:
        return err

    body = request.get_json(silent=True) or {}
    state = _state()

    from ai.storyteller import Storyteller
    st = Storyteller(state.get("openai_client"))
    summary = state["analyzer"].summary_stats()
    insights = state["insights"] or []
    session = state.get("chat_session")
    history = session.history if session else []
    report_content = body.get("report_content", "")

    story = st.tell(summary, insights, history, report_content)
    return jsonify(story)


# ── 分析计划接口 ──────────────────────────────────────────────

@api_bp.route("/plan/generate", methods=["POST"])
def plan_generate():
    """
    生成智能分析计划。

    响应：[{"id": int, "title": str, "category": str, "description": str}, ...]
    """
    err = _require_data()
    if err:
        return err

    state = _state()
    from ai.plan_generator import PlanGenerator

    pg = PlanGenerator(state.get("openai_client"))
    summary = state["analyzer"].summary_stats()
    insights = state["insights"] or []
    plan = pg.generate(summary, insights)
    return jsonify(plan)
