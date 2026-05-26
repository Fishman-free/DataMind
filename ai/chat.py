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
        根据数据集摘要和数据画像动态构建系统提示词。

        包含：数据画像名称、完整列信息（名称+类型+样本值）、语义映射提示、操作规范。
        """
        rows       = self.df_summary.get("row_count", "未知")
        cols_count = self.df_summary.get("column_count", "未知")
        mode_name  = self.df_summary.get("profile_mode_name", "数据集")

        # 构建完整列信息表（用于语义映射）
        # 对宽数据集（>25列）智能截断：优先保留数值列 + 分类列 + 时间列，
        # 防止 prompt 过长导致 token 超限或 AI 注意力分散。
        col_info: dict = self.df_summary.get("col_info", {})
        if col_info:
            col_lines = []
            MAX_COLS_IN_PROMPT = 25
            items = list(col_info.items())
            if len(items) > MAX_COLS_IN_PROMPT:
                # 截断策略：保留前 25 列，附加说明
                items = items[:MAX_COLS_IN_PROMPT]
                truncated = True
            else:
                truncated = False
            for col_name, info in items:
                samples_str = ", ".join(info.get("samples", [])[:3])
                col_lines.append(f"  - {col_name} ({info.get('dtype','')})：样本值 [{samples_str}]")
            col_table = "\n".join(col_lines)
            if truncated:
                total = self.df_summary.get("column_count", "?")
                col_table += f"\n  （共 {total} 列，此处仅列出前 {MAX_COLS_IN_PROMPT} 列，其余可通过 df.columns 查询）"
        else:
            # 降级：只展示数值列
            num_cols = list(self.df_summary.get("numeric_stats", {}).keys())
            col_table = "  - " + "\n  - ".join(num_cols) if num_cols else "  （无）"

        return f"""你是一个专业的数据分析助手，帮助用户分析已上传的数据集。

【数据集信息】
- 类型：{mode_name}
- 行数：{rows}
- 列数：{cols_count}

【完整列信息（使用精确列名编写代码）】
{col_table}

【操作规范】
1. 变量名固定为 df（已在执行环境中提供），**计算结果必须赋值给 result 变量**
2. **禁止写任何 import 语句**。以下库已在环境中预加载，直接使用：
   - pd（pandas）、np（numpy）、px（plotly.express）、go（plotly.graph_objects）
3. **使用上方列表中的精确列名**，禁止翻译或猜测列名。
   例如：用户说"酒精浓度"→ 使用列名 `alcohol`；用户说"销售金额"→ 使用列名 `UnitPrice` 或 `Quantity`
4. 如果问题适合可视化，将 Plotly Figure 赋值给 chart 变量：
   ```python
   fig = px.bar(df, x='colA', y='colB', title='标题')
   chart = fig
   result = df.groupby('colA')['colB'].sum()
   ```
5. 生成散点图时，务必设置可见的 marker：
   ```python
   fig = px.scatter(df, x='colA', y='colB', title='标题',
                    opacity=0.7, color_discrete_sequence=['#00e5ff'])
   # 或使用 go：
   fig = go.Figure(go.Scatter(x=df['colA'], y=df['colB'],
                              mode='markers',
                              marker=dict(color='rgba(0,229,255,0.7)', size=6)))
   chart = fig
   ```
6. 纯分类数据分析时优先使用频次统计和柱状图：
   ```python
   vc = df['colA'].value_counts().reset_index()
   vc.columns = ['类别', '数量']
   fig = px.bar(vc, x='类别', y='数量', title='colA 频次分布')
   chart = fig
   result = vc
   ```
7. 代码放在 ```python ... ``` 块中，自然语言解释放在代码块外
8. 代码执行完毕后，用自然语言解释结论
9. 如需输出中间信息请使用 print()，语言优先中文"""

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
