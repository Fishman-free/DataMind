"""
代码生成与安全执行模块。

流程：
  用户问题 → 构建 Prompt → OpenAI API → 提取 Python 代码
  → 安全校验 → 受限环境 exec() → 返回结果

来源：学生+AI
"""
from __future__ import annotations

import re
import textwrap
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
        在受限命名空间中执行代码。

        Parameters
        ----------
        code : Python 代码字符串，约定将结果赋值给 result
        df   : 用户数据集（会被复制，防止原始数据被修改）

        Returns
        -------
        {"success": True, "result": <value>, "chart": None}
        {"success": False, "error": <msg>}
        """
        if not self.validate_code(code):
            return {"success": False, "error": "代码包含禁止操作，已被拦截 blocked"}

        namespace: dict[str, Any] = {
            "__builtins__": _SAFE_BUILTINS,
            "df": df.copy(),
            "pd": pd,
            "np": np,
        }

        try:
            exec(textwrap.dedent(code), namespace)  # noqa: S102
        except Exception as exc:
            return {"success": False, "error": str(exc)}

        raw = namespace.get("result")
        chart = namespace.get("chart")

        # 将 pandas 对象序列化为 Python 原生类型
        result_val = _serialize(raw)

        return {"success": True, "result": result_val, "chart": chart}

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
                max_tokens=1000,
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


def _extract_code(text: str) -> str:
    """从 AI 回复中提取 ```python ... ``` 代码块。"""
    match = _CODE_BLOCK_RE.search(text)
    return match.group(1).strip() if match else ""


def _serialize(value: Any) -> Any:
    """将 pandas/numpy 对象转为 JSON 可序列化的 Python 原生类型。"""
    if value is None:
        return None
    if isinstance(value, pd.DataFrame):
        return value.to_dict(orient="records")
    if isinstance(value, pd.Series):
        return value.to_dict()
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    return value
