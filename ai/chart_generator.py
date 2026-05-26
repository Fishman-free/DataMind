"""
NL2Vis — 自然语言图表生成器。
将用户的自然语言描述转换为 Plotly 交互图表，支持迭代修改。

支持图表类型：散点图、折线图、柱状图、饼图、面积图、热力图、
              箱线图、散点矩阵、桑基图、漏斗图、仪表盘、气泡图

来源：学生+AI
"""
from __future__ import annotations

import json
import re
from typing import Any

import pandas as pd


class ChartGenerator:
    """自然语言 → Plotly 图表生成器，使用 AI + 沙箱执行。"""

    _SYSTEM_PROMPT = """你是一个数据可视化专家。根据用户的自然语言描述生成 Plotly 图表代码。

要求：
1. 使用 import plotly.graph_objects as go
2. 图表对象赋值给变量 `chart`（必须是 go.Figure 类型）
3. 使用 template="plotly_dark" 匹配暗色主题
4. 添加合适的标题和轴标签
5. 只输出 Python 代码块，不要其他解释
6. 数据已存在于 `df` 变量中，可直接使用
7. 不需要 import pandas 或读取文件

【颜色/色系指导】当用户要求修改颜色、色系、配色方案时：
- 莫兰迪色系（Morandi）：低饱和度灰调色，参考色值 —
  灰棕 #C2A899、雾蓝 #8B9DAF、灰绿 #A3B5A6、灰粉 #C4B7A6、
  灰紫 #9B8EA8、灰黄 #B8AA8E、灰橙 #C49A8A、鼠尾草绿 #9CAF9C
- 修改方式：设置 trace 的 marker_color 或 marker.colors 属性
- 柱状图/散点图：给每个 trace 设置 marker=dict(color=[色值列表])
- 饼图：设置 marker=dict(colors=[色值列表])
- 折线图：设置 line=dict(color='色值')

【修改图表区分】收到修改请求时，判断是：
- "改样式"（改色系、改主题、改标题）：只修改样式属性，保持数据不变
- "改数据"（按季度、只看Top5、改图表类型）：重新处理数据

支持的图表类型：散点图、折线图、柱状图、饼图、面积图、热力图、箱线图、散点矩阵、桑基图、漏斗图、仪表盘、气泡图
"""

    # 支持的图表类型
    _SUPPORTED_CHART_TYPES = [
        "散点图", "折线图", "柱状图", "饼图", "面积图",
        "热力图", "箱线图", "散点矩阵", "桑基图", "漏斗图",
        "仪表盘", "气泡图",
    ]

    def __init__(self, client: Any = None):
        """client: OpenAI 兼容客户端（可为 None，降级模式）。"""
        self._client = client

    # ── 公共接口 ─────────────────────────────────────────

    def generate(self, description: str, df: pd.DataFrame,
                 previous_chart: dict | None = None) -> dict:
        """
        根据自然语言描述生成图表。

        Args:
            description: 自然语言图表描述
            df: 数据集 DataFrame
            previous_chart: 上一张图表的 Plotly JSON（迭代修改时使用）

        Returns:
            {"success": bool, "chart": {...}, "explanation": str}
        """
        if self._client is None:
            return {
                "success": False,
                "explanation": "AI 服务未启用，请在设置中配置 API Key",
            }

        try:
            code = self._call_ai(description, df, previous_chart)
            if not code:
                return {
                    "success": False,
                    "explanation": "AI 未能生成有效的图表代码",
                }

            result = self._execute_chart_code(code, df)
            if result.get("success"):
                result["code"] = code
            return result

        except Exception as exc:
            return {
                "success": False,
                "explanation": f"图表生成失败：{exc}",
            }

    @staticmethod
    def get_supported_chart_types() -> list[str]:
        """返回支持的图表类型列表。"""
        return list(ChartGenerator._SUPPORTED_CHART_TYPES)

    # ── 内部实现 ─────────────────────────────────────────

    def _call_ai(self, description: str, df: pd.DataFrame,
                 previous_chart: dict | None = None) -> str | None:
        """调用 AI 生成 Plotly 代码。"""
        import config as _cfg

        # 构建数据摘要
        df_info = self._build_df_summary(df)

        user_prompt = f"""数据摘要：
{df_info}

图表需求：{description}"""

        if previous_chart:
            user_prompt += f"\n\n当前图表（请基于此修改）：\n{json.dumps(previous_chart, ensure_ascii=False)[:2000]}"
            user_prompt += "\n\n提示：如果用户要求修改颜色、色系、主题等样式，只修改样式属性（marker/colorscale/line color），保持数据查询逻辑不变。"

        try:
            resp = self._client.chat.completions.create(
                model=_cfg.AI_MODEL,
                messages=[
                    {"role": "system", "content": self._SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.2,
                max_tokens=2500,
            )
            content = resp.choices[0].message.content or ""
            return self._extract_code(content)
        except Exception:
            return None

    def _build_df_summary(self, df: pd.DataFrame) -> str:
        """构建 DataFrame 摘要信息供 AI 使用。"""
        lines = [
            f"行数: {len(df)}",
            f"列数: {len(df.columns)}",
            f"列名: {', '.join(str(c) for c in df.columns)}",
            f"数据类型:\n{df.dtypes.to_string()}",
        ]
        # 数值列统计
        num_cols = df.select_dtypes(include=["number"]).columns
        if len(num_cols) > 0:
            lines.append(f"数值列前5行:\n{df[num_cols].head(5).to_string()}")
        return "\n".join(lines)

    def _extract_code(self, text: str) -> str | None:
        """从 AI 响应中提取 Python 代码块。"""
        pattern = r"```python\s*(.*?)```"
        matches = re.findall(pattern, text, re.DOTALL)
        if matches:
            return matches[0].strip()
        # 如果没有代码块标记，尝试直接使用全文
        if "import plotly" in text.lower():
            return text.strip()
        return None

    def _execute_chart_code(self, code: str, df: pd.DataFrame) -> dict:
        """在沙箱中执行图表代码并序列化结果。"""
        from ai.code_generator import _SAFE_BUILTINS, _FORBIDDEN

        # 安全检查
        for keyword in _FORBIDDEN:
            if keyword in code:
                return {
                    "success": False,
                    "explanation": f"代码包含禁止的操作：{keyword}",
                }

        safe_builtins = dict(_SAFE_BUILTINS)
        safe_builtins["__import__"] = __import__

        try:
            # 限制 import 范围
            exec_globals: dict[str, Any] = {
                "__builtins__": safe_builtins,
                "df": df.copy(),
                "pd": pd,
                "np": __import__("numpy"),
                "json": __import__("json"),
            }
            # 预先导入 plotly
            exec_globals["go"] = __import__("plotly.graph_objects", fromlist=["graph_objects"])

            exec(code, exec_globals)

            chart = exec_globals.get("chart")
            if chart is None:
                return {
                    "success": False,
                    "explanation": "代码执行完成但未生成 chart 变量，请确保图表对象赋值给 `chart`",
                }

            # 序列化 Plotly Figure
            try:
                chart_json = chart.to_plotly_json()
            except AttributeError:
                return {
                    "success": False,
                    "explanation": "chart 变量不是有效的 Plotly Figure 对象",
                }

            # 递归清理 numpy 类型，确保 JSON 可序列化
            chart_json = _sanitize_numpy(chart_json)

            return {
                "success": True,
                "chart": chart_json,
                "explanation": "图表生成成功",
            }

        except SyntaxError as e:
            return {
                "success": False,
                "explanation": f"代码语法错误：{e}",
            }
        except Exception as e:
            return {
                "success": False,
                "explanation": f"代码执行错误：{e}",
            }


# ── 工具函数 ──────────────────────────────────────────────

def _sanitize_numpy(obj: Any) -> Any:
    """递归遍历对象，将 numpy 类型转为 Python 原生类型，确保 JSON 可序列化。"""
    import numpy as np
    if isinstance(obj, dict):
        return {k: _sanitize_numpy(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize_numpy(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return _sanitize_numpy(obj.tolist())
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    return obj
