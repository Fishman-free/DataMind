"""
页面路由蓝图 — 渲染 HTML 模板。
来源：学生+AI
"""
from flask import Blueprint, render_template, current_app

from routes.api import _try_auto_reload as _auto_reload


def _dataset_context():
    """
    为所有页面模板提供统一的数据集状态上下文。

    如果数据集已加载，注入 filename / row_count / column_count，
    使服务端渲染的 HTML 直接显示"已加载: xxx"，无需等待 JavaScript 恢复。

    首次访问时触发 auto-reload（服务重启后从磁盘恢复数据集）。

    Returns:
        dict: 模板上下文变量
    """
    state = current_app.state  # type: ignore[attr-defined]
    df = state.get("df_clean")

    # 服务重启后 df_clean 为空，尝试从磁盘自动恢复
    if df is None:
        _auto_reload()
        df = state.get("df_clean")

    if df is not None and len(df) > 0:
        return {
            "dataset_loaded": True,
            "dataset_filename": state.get("filename", "数据集"),
            "dataset_row_count": len(df),
            "dataset_column_count": len(df.columns),
        }
    return {
        "dataset_loaded": False,
        "dataset_filename": None,
        "dataset_row_count": 0,
        "dataset_column_count": 0,
    }


pages_bp = Blueprint("pages", __name__)


@pages_bp.route("/")
def index():
    """数据概览页：统计卡片 + 质量评分卡 + 预处理摘要 + 数据预览表格。"""
    return render_template("index.html", **_dataset_context())


@pages_bp.route("/analysis")
def analysis():
    """智能问答页：双栏布局（对话区 + NL2Vis 图表工作台），SSE 流式问答。"""
    return render_template("analysis.html", **_dataset_context())


@pages_bp.route("/visualization")
def visualization():
    """可视化仪表盘：6 个 Plotly 交互图表（趋势/商品/分布/相关性/时段/RFM）。"""
    return render_template("visualization.html", **_dataset_context())


@pages_bp.route("/report")
def report():
    """分析报告页：简洁/深度/叙事三种模式，支持 SSE 流式推送和 Markdown 下载。"""
    return render_template("report.html", **_dataset_context())
