"""
代码生成与安全执行模块。

流程：
  用户问题 → 构建 Prompt → OpenAI API → 提取 Python 代码
  → 安全校验 → 受限环境 exec() → 返回结果

来源：学生+AI
"""
from __future__ import annotations

import base64
import io
import json
import re
import textwrap
import threading
from contextlib import redirect_stdout
from typing import Any

import numpy as np
import pandas as pd


# 禁止出现的危险关键词（任一命中即拒绝执行）
_FORBIDDEN = [
    "import os", "import sys", "subprocess", "open(",
    "__import__", "eval(", "exec(", "shutil", "pathlib",
    "socket", "__builtins__", "globals(", "locals(",
    "compile(", "breakpoint(",
]

# 允许在沙盒中使用的 Python 内置函数
_SAFE_BUILTINS = {
    "len": len, "range": range, "sorted": sorted, "sum": sum,
    "min": min, "max": max, "abs": abs, "round": round,
    "str": str, "int": int, "float": float, "bool": bool,
    "list": list, "dict": dict, "tuple": tuple, "set": set,
    "enumerate": enumerate, "zip": zip, "map": map,
    "filter": filter, "print": print, "isinstance": isinstance,
    "hasattr": hasattr, "getattr": getattr,
}

# 从 OpenAI 回复中提取 Python 代码块的正则
_CODE_BLOCK_RE = re.compile(r"```python\s*(.*?)```", re.DOTALL | re.IGNORECASE)


class CodeGenerator:
    """
    自然语言 → Pandas 代码生成器。

    generate()    : 调用 OpenAI，解析并执行返回的代码
    validate_code : 安全白名单校验
    execute_safe  : 受限命名空间执行
    """

    def __init__(self, client: Any) -> None:
        """
        Parameters
        ----------
        client : OpenAI()  实例（或 Mock），用于调用 chat.completions.create
        """
        self.client = client

    # ── 安全校验 ───────────────────────────────────────

    def validate_code(self, code: str) -> bool:
        """
        检查代码中是否含有禁止关键词。

        Returns
        -------
        True  — 代码安全可执行
        False — 代码含危险操作，应拒绝
        """
        for keyword in _FORBIDDEN:
            if keyword in code:
                return False
        return True

    # ── 受限执行 ───────────────────────────────────────

    def execute_safe(self, code: str, df: pd.DataFrame) -> dict[str, Any]:
        """
        在受限命名空间中执行代码（带超时控制）。

        Parameters
        ----------
        code : Python 代码字符串，约定将结果赋值给 result
        df   : 用户数据集（会被复制，防止原始数据被修改）

        Returns
        -------
        {"success": True, "result": <value>, "stdout": <str or None>, "chart": None}
        {"success": False, "error": <msg>}
        """
        # 安全校验必须在净化之前，防止净化后漏过危险代码（如 import os）
        if not self.validate_code(code):
            return {"success": False, "error": "代码包含禁止操作，已被拦截 blocked"}
        # 净化：移除所有 import 语句（px/go/pd/np 均已预加载），防止沙盒 __import__ 报错
        code = _sanitize_code(code)

        import config as _cfg
        exec_timeout = getattr(_cfg, "CODE_EXEC_TIMEOUT", 30)

        result_holder: dict[str, Any] = {}
        done_event = threading.Event()

        def _run():
            # 预加载可视化库（plotly 可选，未安装时忽略）
            _extra: dict[str, Any] = {}
            try:
                import plotly.express as _px
                import plotly.graph_objects as _go
                _extra["px"] = _px
                _extra["go"] = _go
            except ImportError:
                pass

            namespace: dict[str, Any] = {
                "__builtins__": _SAFE_BUILTINS,
                "df": df.copy(),
                "pd": pd,
                "np": np,
                "json": __import__("json"),
                **_extra,
            }
            stdout_buf = io.StringIO()
            try:
                with redirect_stdout(stdout_buf):
                    exec(textwrap.dedent(code), namespace)  # noqa: S102
                raw = namespace.get("result")
                chart = namespace.get("chart")
                # 将 plotly Figure 对象转为纯 JSON 可序列化的 dict。
                #
                # 注意：plotly 5.x 的 to_json() 对 numpy 数组使用 Base64 二进制编码
                #   {"dtype": "i1", "bdata": "AQIDBAUGBwg..."}
                # 这种格式需要 Plotly.js >= 2.12 才能解码，旧版浏览器会把 x/y 当空对象
                # 导致散点图显示空白坐标轴（-1~6, -1~4 等默认空图 range）。
                #
                # 正确方案：to_dict() + 递归 numpy→list 转换，跳过二进制编码路径。
                if chart is not None:
                    if hasattr(chart, "to_dict"):
                        chart = _plotly_fig_to_dict(chart)
                    elif hasattr(chart, "to_plotly_json"):
                        # 兜底：to_plotly_json 仍可能含 ndarray，用 json roundtrip 处理
                        chart = json.loads(
                            json.dumps(chart.to_plotly_json(), default=_json_serial)
                        )
                    # 剥离嵌入的 plotly_dark 模板并强制透明背景
                    if isinstance(chart, dict) and isinstance(chart.get("layout"), dict):
                        chart["layout"].pop("template", None)
                        chart["layout"]["paper_bgcolor"] = "rgba(0,0,0,0)"
                        chart["layout"]["plot_bgcolor"]  = "rgba(0,0,0,0)"
                result_val = _serialize(raw)
                stdout_text = stdout_buf.getvalue().strip()
                result_holder["result"] = {
                    "success": True,
                    "result": result_val,
                    "chart": chart,
                    "stdout": stdout_text if stdout_text else None,
                }
            except Exception as exc:
                result_holder["result"] = {"success": False, "error": str(exc)}
            finally:
                done_event.set()

        t = threading.Thread(target=_run, daemon=True)
        t.start()

        finished = done_event.wait(timeout=exec_timeout)
        if not finished:
            # 超时：线程作为 daemon 会在进程退出时自动回收，
            # Python 限制无法强制杀死线程，但返回超时错误。
            return {"success": False, "error": f"代码执行超时（{exec_timeout}s），请简化分析逻辑"}

        return result_holder.get("result", {"success": False, "error": "执行结果为空"})

    # ── 代码提取（静态工具方法）───────────────────────

    @staticmethod
    def extract_code(text: str) -> str:
        """从 AI 回复中提取 ```python ... ``` 代码块。"""
        return _extract_code(text)

    # ── 代码生成（调用 OpenAI）──────────────────────────

    def generate(
        self,
        question: str,
        context: list[dict[str, str]],
        df_info: dict[str, Any],
        df: pd.DataFrame,
    ) -> dict[str, Any]:
        """
        将用户问题发送给 OpenAI，提取并执行返回的代码。

        Parameters
        ----------
        question : 用户问题
        context  : 对话历史（list of {role, content}）
        df_info  : 数据集摘要（summary_stats 返回值）
        df       : 用户数据集

        Returns
        -------
        {"answer": str, "code": str, "success": bool, "result": Any, ...}
        """
        # 构建本次请求消息
        user_msg = {"role": "user", "content": question}
        messages = list(context) + [user_msg]

        import config as _cfg
        try:
            response = self.client.chat.completions.create(
                model=_cfg.AI_MODEL,
                messages=messages,
                temperature=0.2,
                max_tokens=_cfg.AI_MAX_TOKENS,
                timeout=_cfg.AI_REQUEST_TIMEOUT,
            )
            # 防御性解析：兼容不同服务商响应结构
            raw_answer: str = _extract_content(response) or ""
        except Exception as exc:
            return {
                "answer": f"调用 AI 服务失败：{exc}",
                "code": "",
                "success": False,
                "error": str(exc),
            }

        # 提取代码块
        code = _extract_code(raw_answer)

        # 执行代码
        exec_result: dict[str, Any] = {"success": True, "result": None, "chart": None}
        if code:
            exec_result = self.execute_safe(code, df)

        return {
            "answer":  raw_answer,
            "code":    code,
            "success": exec_result["success"],
            "result":  exec_result.get("result"),
            "chart":   exec_result.get("chart"),
            **({"error": exec_result["error"]} if not exec_result["success"] else {}),
        }


# ── 内部工具函数 ──────────────────────────────────────────

def _extract_content(response: Any) -> str:
    """
    从各类服务商响应中安全提取文本内容。

    兼容场景：
    - 标准 OpenAI ChatCompletion 对象（openai v1+）
    - MagicMock（单元测试）
    - 部分国内服务商返回的非标准 dict / 类 dict 对象
    - 极端情况下响应本身是字符串
    """
    # 情形 1：有 .choices 属性（ChatCompletion 对象 / MagicMock）
    # 用 try/except 而非 len() 检查，兼容 MagicMock（len 默认 0）
    try:
        choices = getattr(response, "choices", None)
        if choices is not None:
            item    = choices[0]               # list 或 MagicMock.__getitem__
            msg     = getattr(item, "message", None)
            if msg is not None:
                content = getattr(msg, "content", None)
                if content is not None:
                    return str(content)
    except Exception:
        pass

    # 情形 2：dict 风格响应（部分中转站直接返回原始 dict）
    try:
        if isinstance(response, dict):
            return str(
                response.get("choices", [{}])[0]
                        .get("message", {})
                        .get("content", "")
            )
    except Exception:
        pass

    # 情形 3：响应本身就是纯文本字符串
    if isinstance(response, str):
        return response

    return ""


# 匹配所有 import 语句（所有常用库均已在执行命名空间中预加载，禁止额外 import）
_IMPORT_RE = re.compile(
    r"^\s*(import\s+\S.*|from\s+\S+\s+import\s+.*)$",
    re.MULTILINE,
)


def _json_serial(obj: Any) -> Any:
    """json.dumps default 回调：将 numpy 类型转为 Python 原生类型。"""
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def _decode_plotly_bdata(obj: Any) -> Any:
    """
    递归解码 plotly 5.x 的 Base64 二进制数组编码。

    plotly 5.x 将 numpy 数组序列化为 {"dtype": "f8", "bdata": "<base64>"} 格式，
    而非普通 JSON 数组。Plotly.js 旧版本不支持此格式，导致 x/y 被当作空对象，
    散点图显示为无数据的空坐标轴（range: -1~6 等默认值）。

    本函数将所有 {dtype, bdata} 对象解码为 Python list，确保跨版本兼容。
    """
    if isinstance(obj, dict):
        # plotly binary-encoded array 特征：同时含 'dtype' 和 'bdata'
        if "bdata" in obj and "dtype" in obj:
            raw_bytes = base64.b64decode(obj["bdata"])
            arr = np.frombuffer(raw_bytes, dtype=np.dtype(obj["dtype"]))
            return arr.tolist()
        return {k: _decode_plotly_bdata(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_decode_plotly_bdata(v) for v in obj]
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    return obj


def _plotly_fig_to_dict(fig: Any) -> dict:
    """
    将 plotly Figure 转为纯 JSON 可序列化的 Python dict。

    关键点：plotly 5.x 的 to_dict() 对 numpy 数组使用 Base64 二进制编码
    {"dtype": "i1", "bdata": "AQIDBAUGBw..."}，而非普通 JSON 数组。
    旧版 Plotly.js 把 x/y 当空对象处理 → 散点图空白。

    本函数通过 _decode_plotly_bdata 递归解码所有 binary 字段，
    返回完全由 Python 原生类型组成的 dict。
    """
    raw = fig.to_dict()
    return _decode_plotly_bdata(raw)


def _sanitize_code(code: str) -> str:
    """移除所有 import 语句，避免沙盒 __import__ 报错。
    pd、np、px（plotly.express）、go（plotly.graph_objects）均已在命名空间预加载。
    """
    return _IMPORT_RE.sub("", code).strip()


def _extract_code(text: str) -> str:
    """从 AI 回复中提取 ```python ... ``` 代码块。"""
    match = _CODE_BLOCK_RE.search(text)
    return match.group(1).strip() if match else ""


# 结果序列化最大大小（50KB），超出则截断
_SERIALIZE_MAX_BYTES = 50 * 1024


def _serialize(value: Any) -> Any:
    """将 pandas/numpy 对象转为 JSON 可序列化的 Python 原生类型（带大小保护）。"""
    if value is None:
        return None
    if isinstance(value, pd.DataFrame):
        # 限制最多 500 行，防止超大结果
        rows = min(len(value), 500)
        result = value.head(rows).to_dict(orient="records")
        return _truncate_if_large(result, len(value), "DataFrame")
    if isinstance(value, pd.Series):
        raw = value.to_dict()
        result = {str(k): v for k, v in raw.items()}
        return _truncate_if_large(result)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, np.ndarray):
        result = value.tolist()
        return _truncate_if_large(result)
    if isinstance(value, (list, dict)):
        return _truncate_if_large(value)
    return value


def _truncate_if_large(value: Any, total_rows: int = 0, source_type: str = "") -> Any:
    """检查序列化结果大小，超过 50KB 时截断。"""
    try:
        serialized = json.dumps(value, ensure_ascii=False, default=str)
        if len(serialized.encode("utf-8")) > _SERIALIZE_MAX_BYTES:
            # 截断为前 200 项（列表）或前 50 个键（字典）
            if isinstance(value, list):
                truncated = value[:200]
                note = {"_truncated": True, "_original_count": len(value), "_note": "结果已截断（前200条）"}
                if total_rows:
                    note["_original_rows"] = total_rows
                return truncated + [note]
            elif isinstance(value, dict):
                keys = list(value.keys())[:50]
                return {k: value[k] for k in keys}
    except (TypeError, ValueError):
        pass
    return value
