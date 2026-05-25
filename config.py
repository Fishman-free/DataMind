"""
项目配置文件
来源：学生
"""
import os

# ── AI 服务配置（运行时可通过 /api/config/ai 动态更新）──────
AI_API_KEY  = os.getenv("AI_API_KEY",  os.getenv("OPENAI_API_KEY", ""))
AI_BASE_URL = os.getenv("AI_BASE_URL", "https://api.openai.com/v1")
AI_MODEL    = os.getenv("AI_MODEL",    "gpt-4o-mini")

# ── 预置服务商（前端展示用）───────────────────────────────
AI_PROVIDERS = {
    "openai": {
        "name":     "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "models":   ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"],
    },
    "deepseek": {
        "name":     "DeepSeek",
        "base_url": "https://api.deepseek.com/v1",
        "models":   ["deepseek-chat", "deepseek-reasoner"],
    },
    "moonshot": {
        "name":     "Moonshot / Kimi",
        "base_url": "https://api.moonshot.cn/v1",
        "models":   ["moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k"],
    },
    "zhipu": {
        "name":     "智谱 GLM",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "models":   ["glm-4", "glm-4-flash", "glm-3-turbo"],
    },
    "qwen": {
        "name":     "通义千问 (Qwen)",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "models":   ["qwen-turbo", "qwen-plus", "qwen-max", "qwen-long"],
    },
    "siliconflow": {
        "name":     "硅基流动 SiliconFlow",
        "base_url": "https://api.siliconflow.cn/v1",
        "models":   [
            "deepseek-ai/DeepSeek-V3",
            "Qwen/Qwen2.5-72B-Instruct",
            "Qwen/Qwen2.5-7B-Instruct",
            "Pro/deepseek-ai/DeepSeek-R1",
        ],
    },
    "doubao": {
        "name":     "字节豆包 (Doubao)",
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "models":   ["doubao-pro-4k", "doubao-pro-32k", "doubao-lite-4k"],
    },
    "ollama": {
        "name":     "Ollama（本地免费）",
        "base_url": "http://localhost:11434/v1",
        "models":   ["qwen3:8b", "qwen3:4b", "qwen3:14b", "qwen2.5:7b", "qwen2.5:14b", "glm4:9b", "llama3.2:3b"],
    },
    "custom": {
        "name":     "自定义 / 中转站",
        "base_url": "",
        "models":   [],
    },
}

# ── 文件上传 ─────────────────────────────────────────────
UPLOAD_FOLDER      = os.path.join(os.path.dirname(__file__), "datasets")
MAX_FILE_SIZE      = 50 * 1024 * 1024          # 50 MB
ALLOWED_EXTENSIONS = {"csv", "xlsx", "json"}

# ── AI 请求参数 ─────────────────────────────────────────
AI_MAX_TOKENS      = int(os.getenv("AI_MAX_TOKENS", "4096"))
AI_REQUEST_TIMEOUT = float(os.getenv("AI_REQUEST_TIMEOUT", "60.0"))
CODE_EXEC_TIMEOUT  = int(os.getenv("CODE_EXEC_TIMEOUT", "30"))

# ── Flask ────────────────────────────────────────────────
SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "datamind-dev-secret-2026")
DEBUG      = os.getenv("FLASK_DEBUG", "true").lower() == "true"
HOST       = "0.0.0.0"
PORT       = 5000

# ── 向后兼容 ─────────────────────────────────────────────
OPENAI_API_KEY = AI_API_KEY
OPENAI_MODEL   = AI_MODEL
