"""
DataMind — 智能问数平台
Flask 应用入口，注册蓝图并维护全局状态。
来源：学生
"""
from flask import Flask
import config

# ── 全局状态（单用户场景，存储当前数据集的运行时对象）──────────
# 上传数据后由 /api/upload 接口填充；其他接口读取此状态
app_state: dict = {
    "df_raw": None,             # 原始 DataFrame
    "df_clean": None,           # 预处理后 DataFrame
    "preprocess_report": None,  # 预处理摘要字典
    "analyzer": None,           # Analyzer 实例
    "detector": None,           # AnomalyDetector 实例
    "insights": None,           # list[dict] 自动洞察
    "chat_session": None,       # ChatSession 实例
    "code_generator": None,     # CodeGenerator 实例
    "report_generator": None,   # ReportGenerator 实例
    "openai_client": None,      # openai.OpenAI 实例
    "quality_score": None,      # 数据质量评分卡结果
}


def create_app() -> Flask:
    """工厂函数：创建并配置 Flask 应用。"""
    app = Flask(__name__)
    app.config["SECRET_KEY"] = config.SECRET_KEY
    app.config["MAX_CONTENT_LENGTH"] = config.MAX_FILE_SIZE
    app.config["UPLOAD_FOLDER"] = config.UPLOAD_FOLDER
    # 开发模式禁用静态文件浏览器缓存，确保 JS/CSS 修改立即生效
    app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0

    # 将全局状态挂到 app 上，方便蓝图访问
    app.state = app_state  # type: ignore[attr-defined]

    # ── 注册蓝图 ────────────────────────────────────────
    from routes.pages import pages_bp
    from routes.api import api_bp

    app.register_blueprint(pages_bp)
    app.register_blueprint(api_bp, url_prefix="/api")

    return app


if __name__ == "__main__":
    application = create_app()
    application.run(
        host=config.HOST,
        port=config.PORT,
        debug=config.DEBUG,
        threaded=True,
    )
