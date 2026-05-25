"""
多轮对话管理模块。

维护与 OpenAI API 的对话上下文，支持：
  - 数据集感知的系统提示词
  - 历史消息管理（自动 trim 到 max_history 限制）
  - 重置对话
  - 持久化到磁盘（防 Flask debug 重载丢失）

来源：学生+AI
"""
from __future__ import annotations

import json
import os
from typing import Any

from config import UPLOAD_FOLDER

# 对话历史持久化文件路径
_CHAT_HISTORY_FILE = os.path.join(UPLOAD_FOLDER, ".chat_history.json")


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
1. 变量名固定为 df（已在执行环境中提供），**计算结果必须赋值给 result 变量**
2. **禁止写任何 import 语句**。以下库已在环境中预加载，直接使用：
   - pd（pandas）、np（numpy）
   - px（plotly.express）、go（plotly.graph_objects）
3. 如果问题适合可视化，将 Plotly Figure 对象赋值给 chart 变量，例如：
   ```python
   fig = px.bar(df, x='Category', y='Amount', title='分类销售额')
   chart = fig
   result = df.groupby('Category')['Amount'].sum()
   ```
   或使用 go.Figure：
   ```python
   fig = go.Figure(go.Bar(x=list(data.index), y=list(data.values)))
   fig.update_layout(title='标题')
   chart = fig
   result = data
   ```
4. 代码放在 ```python ... ``` 块中，自然语言解释放在代码块外
5. **重要**：代码块执行完毕后，必须再用自然语言解释分析结论，
   直接回答用户的问题。不要只说"结果见上方"，
   而要说"根据分析，A 地区销售额最高为 120 万，占比 45%"
6. 如需输出中间信息请使用 print()，print 输出和 result 变量都会被展示给用户
7. 语言简洁，优先中文"""

    # ── 消息管理 ────────────────────────────────────────

    def add_message(self, role: str, content: str) -> None:
        """
        添加一条消息到历史记录。

        超出 max_history 时，从头部逐条移除以保持最新上下文。
        每次添加自动持久化到磁盘，防止 Flask debug 重载丢失。
        """
        self.history.append({"role": role, "content": content})
        # 超出上限时从最旧的消息开始裁剪
        while len(self.history) > self.max_history:
            self.history.pop(0)
        self._save_to_disk()

    def get_context(self) -> list[dict[str, str]]:
        """
        返回完整消息列表供 OpenAI API 使用。

        格式：[{"role": "system", ...}] + history
        """
        system_msg = {"role": "system", "content": self.build_system_prompt()}
        return [system_msg] + self.history

    def reset(self) -> None:
        """清空对话历史，数据集摘要保留。同时清除持久化文件。"""
        self.history = []
        self._save_to_disk()

    # ── 持久化 ──────────────────────────────────────────

    def _save_to_disk(self) -> None:
        """将当前对话历史持久化到 JSON 文件。"""
        try:
            os.makedirs(os.path.dirname(_CHAT_HISTORY_FILE), exist_ok=True)
            with open(_CHAT_HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(self.history, f, ensure_ascii=False)
        except Exception:
            pass

    @staticmethod
    def restore_from_disk(df_summary: dict[str, Any],
                          max_history: int = 20) -> "ChatSession":
        """
        从磁盘恢复对话历史，创建新的 ChatSession 实例。

        用于 Flask 服务重启后恢复对话上下文。
        """
        session = ChatSession(df_summary, max_history)
        try:
            if os.path.exists(_CHAT_HISTORY_FILE):
                with open(_CHAT_HISTORY_FILE, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                if isinstance(saved, list):
                    session.history = saved
        except Exception:
            pass
        return session
