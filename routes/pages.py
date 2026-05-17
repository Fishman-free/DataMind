"""
页面路由蓝图 — 渲染 HTML 模板。
来源：学生
"""
from flask import Blueprint, render_template

pages_bp = Blueprint("pages", __name__)


@pages_bp.route("/")
def index():
    return render_template("index.html")


@pages_bp.route("/analysis")
def analysis():
    return render_template("analysis.html")


@pages_bp.route("/visualization")
def visualization():
    return render_template("visualization.html")


@pages_bp.route("/report")
def report():
    return render_template("report.html")
