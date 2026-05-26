"""
页面路由蓝图 — 渲染 HTML 模板。
来源：学生
"""
from flask import Blueprint, render_template

pages_bp = Blueprint("pages", __name__)


@pages_bp.route("/")
def index():
    """数据概览页：统计卡片 + 质量评分卡 + 预处理摘要 + 数据预览表格。"""
    return render_template("index.html")


@pages_bp.route("/analysis")
def analysis():
    """智能问答页：双栏布局（对话区 + NL2Vis 图表工作台），SSE 流式问答。"""
    return render_template("analysis.html")


@pages_bp.route("/visualization")
def visualization():
    """可视化仪表盘：6 个 Plotly 交互图表（趋势/商品/分布/相关性/时段/RFM）。"""
    return render_template("visualization.html")


@pages_bp.route("/report")
def report():
    """分析报告页：简洁/深度/叙事三种模式，支持 SSE 流式推送和 Markdown 下载。"""
    return render_template("report.html")
