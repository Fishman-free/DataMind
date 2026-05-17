"""
多轮对话管理模块。

维护与 OpenAI API 的对话上下文，支持：
  - 数据集感知的系统提示词
  - 历史消息管理（自动 trim 到 max_history 限制）
  - 重置对话

来源：学生+AI
"""
from __future__ import annotations

from typing import Any


class ChatSession:
    """
    多轮对话会话管理。

    用法
    ----
    session = ChatSession(analyzer.summary_stats(), max_history=20)
    session.add_message("user", "月均销售额是多少？")
    messages = session.get_context()   # 传给 OpenAI API
    session.add_message("assistant", "月均销售额为 ...")
    """

    def __init__(self, df_summary: dict[str, Any], max_history: int = 20) -> None:
        self.df_summary   = df_summary
        self.max_history  = max_history
        self.history: list[dict[str, str]] = []

    # ── 系统提示词 ──────────────────────────────────────

    def build_system_prompt(self) -> str:
        """
        根据数据集摘要动态构建系统提示词。

        提示词包含：数据集规模、数值列名、操作规范。
        """
        rows     = self.df_summary.get("row_count", "未知")
        cols     = self.df_summary.get("column_count", "未知")
        num_cols = list(self.df_summary.get("numeric_stats", {}).keys())

        col_text = "、".join(num_cols) if num_cols else "（无）"

        return f"""你是一个专业的数据分析助手，帮助用户分析已上传的数据集。

【数据集信息】
- 行数：{rows}
- 列数：{cols}
- 数值列：{col_text}

【回答规范】
1. 变量名固定为 df（已在执行环境中提供），结果赋值给 result
2. 仅使用 pandas（pd）和 numpy（np），禁止 import 其他库
3. 如果问题适合可视化，额外以 JSON 格式提供 Plotly 图表配置（赋值给 chart）
4. 代码放在 ```python ... ``` 块中，自然语言解释放在代码块外
5. 语言简洁，优先中文"""

    # ── 消息管理 ────────────────────────────────────────

    def add_message(self, role: str, content: str) -> None:
        """
        添加一条消息到历史记录。

        超出 max_history 时，从头部逐条移除以保持最新上下文。
        """
        self.history.append({"role": role, "content": content})
        # 超出上限时从最旧的消息开始裁剪
        while len(self.history) > self.max_history:
            self.history.pop(0)

    def get_context(self) -> list[dict[str, str]]:
        """
        返回完整消息列表供 OpenAI API 使用。

        格式：[{"role": "system", ...}] + history
        """
        system_msg = {"role": "system", "content": self.build_system_prompt()}
        return [system_msg] + self.history

    def reset(self) -> None:
        """清空对话历史，数据集摘要保留。"""
        self.history = []
