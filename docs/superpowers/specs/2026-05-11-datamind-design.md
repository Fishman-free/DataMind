# DataMind — 智能问数平台 设计规格

## 1. 项目概述

### 1.1 项目定位

DataMind 是一个基于 Flask 的"智能问数" Web 应用程序，用户可上传数据文件，系统自动完成数据预处理和分析，用户通过自然语言问答与 AI 协作进行交互式数据分析，系统自动生成洞察和分析报告。

### 1.2 核心能力

| 模块 | 功能 |
|------|------|
| 数据文件读取 | 支持 CSV/Excel/JSON，自动检测编码 |
| 数据预处理 | Pipeline 链式清洗：去重、缺失值、类型转换、特征工程 |
| 数据分析方法 | 描述性统计、销售趋势、RFM 客户分析、相关性分析等 |
| 数据可视化 | Plotly.js 交互式图表，6 个预置仪表盘 + AI 动态生成 |
| 交互式分析 | 自然语言问答，GPT 将问题转为 Pandas 代码并安全执行 |
| **创新：自动洞察** | 系统主动扫描数据，推送异常/趋势/分布等洞察卡片 |
| **创新：多轮对话** | AI 记忆上下文，支持追问和分析链 |
| **创新：自动报告** | 一键生成包含图表和发现的 Markdown 分析报告 |

### 1.3 默认数据集

Online Retail — UCI 电商交易数据集（约 54 万条记录，8 个原始字段）。

系统设计为**数据集无关**，支持用户上传任意 CSV/Excel 文件进行分析。

---

## 2. 技术栈

| 层面 | 选择 | 理由 |
|------|------|------|
| 后端框架 | Flask | 轻量、课程常见、单体易部署 |
| 数据处理 | Pandas + NumPy | Python 数据分析标准库 |
| AI 服务 | OpenAI GPT API | 代码生成能力强、生态成熟 |
| 前端图表 | Plotly.js | 交互性好（缩放/悬停/导出），Python & JS 生态统一 |
| 前端框架 | Bootstrap 5 | 快速响应式布局 |
| Markdown | marked.js | AI 回复和报告渲染 |
| 代码高亮 | highlight.js | 展示 AI 生成的代码 |

---

## 3. 系统架构

### 3.1 架构图

```
┌─────────────────────────────────────────────────┐
│                    浏览器 (前端)                    │
│  ┌───────────┐ ┌───────────┐ ┌────────────────┐ │
│  │  对话面板  │ │ 可视化面板 │ │  洞察/报告面板  │ │
│  └─────┬─────┘ └─────┬─────┘ └───────┬────────┘ │
│        └──────────┬──┴───────────────┘           │
│              AJAX / Fetch API                     │
└──────────────────┬────────────────────────────────┘
                   │ HTTP REST
┌──────────────────▼────────────────────────────────┐
│              Flask 应用 (app.py)                    │
│  ┌──────────┐ ┌──────────┐ ┌──────────────────┐  │
│  │ 路由层   │ │ AI 层    │ │ 数据层           │  │
│  │ routes/  │ │ ai/      │ │ data/            │  │
│  └──────────┘ └────┬─────┘ └──────────────────┘  │
│                    │                               │
│              OpenAI API                            │
└────────────────────────────────────────────────────┘
```

### 3.2 目录结构

```
datamind/
├── app.py                  # Flask 入口，注册蓝图
├── config.py               # 配置（API key、文件路径等）
├── requirements.txt        # 依赖清单
├── README.md               # 运行说明
│
├── data/                   # 数据层模块
│   ├── __init__.py
│   ├── loader.py           # 数据文件读取（CSV/Excel/JSON）
│   ├── preprocessor.py     # 数据清洗与预处理
│   ├── analyzer.py         # 统计分析方法
│   └── detector.py         # 异常检测引擎
│
├── ai/                     # AI 智能体模块
│   ├── __init__.py
│   ├── chat.py             # 对话管理（多轮上下文）
│   ├── code_generator.py   # 自然语言 → Pandas 代码
│   ├── insight.py          # 自动洞察生成
│   └── report.py           # 分析报告生成
│
├── routes/                 # Flask 路由层
│   ├── __init__.py
│   ├── pages.py            # 页面路由
│   └── api.py              # REST API 路由
│
├── static/                 # 前端静态资源
│   ├── css/
│   │   └── style.css
│   ├── js/
│   │   ├── app.js          # 主交互逻辑
│   │   ├── chat.js         # 对话组件
│   │   ├── charts.js       # 图表渲染
│   │   └── insights.js     # 洞察卡片
│   └── assets/
│
├── templates/              # Jinja2 模板
│   ├── base.html           # 基础布局
│   ├── index.html          # 主页（数据概览）
│   ├── analysis.html       # 交互式分析页
│   ├── visualization.html  # 可视化仪表盘
│   └── report.html         # 报告页
│
├── datasets/               # 测试数据
│   └── online_retail.csv
│
└── tests/                  # 测试
    ├── test_loader.py
    ├── test_preprocessor.py
    ├── test_analyzer.py
    └── test_ai.py
```

### 3.3 设计原则

| 原则 | 体现 |
|------|------|
| 单一职责 | 每个 .py 文件只做一件事 |
| 依赖抽象 | AI 层通过统一接口调用，换模型只改 config |
| KISS | 单体应用，无需容器/消息队列/数据库 |
| YAGNI | 不做用户系统、不做权限、不做数据库 |

---

## 4. 数据层设计

### 4.1 数据读取 (`data/loader.py`)

- 支持格式：CSV、Excel (.xlsx)、JSON
- 统一返回 `pandas.DataFrame`，对外屏蔽格式差异
- 自动检测编码（chardet），处理中文乱码
- 支持用户通过 Flask 前端上传文件

```python
def load_file(file_path: str) -> pd.DataFrame:
    """根据文件后缀自动选择读取方式，返回统一 DataFrame"""
```

### 4.2 数据预处理 (`data/preprocessor.py`)

**Pipeline 链式处理：**

```
原始数据 → 去重 → 缺失值处理 → 类型转换 → 异常值过滤 → 特征工程 → 清洁数据
```

**通用策略（适配任意数据集）：**

| 步骤 | 通用逻辑 | Online Retail 示例 |
|------|---------|-------------------|
| 去重 | 全行去重（默认），可指定列组合 | InvoiceNo + StockCode |
| 缺失值 | 数值列填中位数，文本列填 "Unknown"，高缺失率列(>50%)标记警告 | CustomerID 缺失标记但保留 |
| 类型转换 | 自动推断日期列（pandas infer_datetime_format）；数值列 to_numeric(errors='coerce') | InvoiceDate → datetime |
| 异常值过滤 | 数值列 IQR 法标记异常（不自动删除，由用户决定） | Quantity ≤ 0 过滤 |
| 特征工程 | 若检测到日期列，自动生成 Year/Month/DayOfWeek/Hour；若检测到数量+价格列，生成 TotalAmount | TotalAmount = Quantity × UnitPrice |

**适配机制：** Preprocessor 初始化时自动检测列类型（数值/文本/日期），根据类型应用对应策略，不硬编码列名。Online Retail 的特定策略作为默认配置提供。

**链式调用 API：**

```python
class Preprocessor:
    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()
        self.log = []

    def remove_duplicates(self) -> 'Preprocessor': ...
    def handle_missing(self) -> 'Preprocessor': ...
    def convert_types(self) -> 'Preprocessor': ...
    def filter_outliers(self) -> 'Preprocessor': ...
    def add_features(self) -> 'Preprocessor': ...
    def run_all(self) -> pd.DataFrame: ...
    def get_report(self) -> dict: ...
```

### 4.3 数据分析 (`data/analyzer.py`)

| 分析类型 | 方法 | 输出 |
|---------|------|------|
| 描述性统计 | df.describe() + 自定义汇总 | 各列均值/中位数/分布 |
| 销售趋势 | 按月/周/日聚合 TotalAmount | 时间序列数据 |
| 商品排行 | groupby StockCode，按销售额/销量排序 | Top N 商品 |
| 客户分析 (RFM) | Recency / Frequency / Monetary 三维度打分 | 客户分群 |
| 国家/地区分析 | groupby Country 聚合 | 地区销售分布 |
| 相关性分析 | 数值列 pearson 相关系数 | 相关性矩阵 |
| 时段分析 | 按 Hour/DayOfWeek 聚合 | 购买高峰时段 |

```python
class Analyzer:
    def __init__(self, df: pd.DataFrame):
        self.df = df

    def summary_stats(self) -> dict: ...
    def sales_trend(self, freq='M') -> pd.DataFrame: ...
    def top_products(self, n=10, by='amount') -> pd.DataFrame: ...
    def rfm_analysis(self) -> pd.DataFrame: ...
    def country_distribution(self) -> pd.DataFrame: ...
    def correlation_matrix(self) -> pd.DataFrame: ...
    def time_pattern(self) -> pd.DataFrame: ...
```

### 4.4 异常检测 (`data/detector.py`)

| 方法 | 适用场景 | 原理 |
|------|---------|------|
| IQR 法 | 数值型异常 | Q1 - 1.5×IQR 到 Q3 + 1.5×IQR 之外为异常 |
| Z-Score | 极端值 | 标准化后绝对值 > 3 为异常 |
| 趋势突变检测 | 时间序列 | 滑动窗口均值，偏离超过 2 倍标准差标记为突变 |

```python
class AnomalyDetector:
    def __init__(self, df: pd.DataFrame):
        self.df = df

    def detect_iqr(self, column: str) -> pd.DataFrame: ...
    def detect_zscore(self, column: str, threshold=3) -> pd.DataFrame: ...
    def detect_trend_break(self, date_col, value_col, window=7) -> list[dict]: ...
    def auto_scan(self) -> list[dict]: ...
```

---

## 5. AI 智能体层设计

### 5.1 对话管理 (`ai/chat.py`)

```python
class ChatSession:
    def __init__(self, df_summary: dict, max_history=20):
        self.history = []
        self.df_summary = df_summary
        self.max_history = max_history

    def build_system_prompt(self) -> str: ...
    def add_message(self, role: str, content: str): ...
    def get_context(self) -> list[dict]: ...
    def reset(self): ...
```

**多轮记忆机制：** 每轮对话的问题 + 执行的代码 + 结果摘要都存入 history，LLM 基于完整上下文理解追问。

### 5.2 代码生成 (`ai/code_generator.py`)

**流程：**

```
用户提问 → 构建 Prompt → OpenAI API → 返回 Python 代码
→ 安全校验 → 受限环境 exec() → 捕获结果 → 判断是否需要可视化
→ 返回（文字回答 + 图表数据）
```

```python
class CodeGenerator:
    FORBIDDEN = ['import os', 'import sys', 'subprocess', 'open(',
                 '__import__', 'eval(', 'exec(', 'shutil', 'pathlib']

    def __init__(self, client: OpenAI):
        self.client = client

    def generate(self, question: str, context: list[dict], df_info: dict) -> dict: ...
    def validate_code(self, code: str) -> bool: ...
    def execute_safe(self, code: str, df: pd.DataFrame) -> dict: ...
```

**安全机制：**
- 黑名单关键词校验（FORBIDDEN 列表）
- 受限命名空间执行（只暴露 df、pd、np）
- 执行超时 5 秒自动终止

**System Prompt 要点：**
- 包含数据集结构（列名、类型、行数、示例数据）
- 变量名固定为 df，结果赋值给 result
- 只使用 pandas 和 numpy
- 如果适合可视化，额外返回 chart 配置

### 5.3 自动洞察 (`ai/insight.py`)

| 洞察类型 | 示例 | 生成方式 |
|---------|------|---------|
| 趋势洞察 | "2011年11月销售额环比增长47%" | 时序分析 + 阈值 |
| 异常洞察 | "StockCode 23843 单价异常偏高" | AnomalyDetector |
| 分布洞察 | "82% 的订单来自英国" | 占比计算 |
| 相关洞察 | "订单数量与单价呈弱负相关" | 相关性矩阵 |
| 周期洞察 | "周四是一周中订单最多的一天" | 时段分析 |

```python
class InsightEngine:
    def __init__(self, df, analyzer, detector):
        self.df = df
        self.analyzer = analyzer
        self.detector = detector

    def generate_all(self) -> list[dict]: ...
    # 每条洞察: {type, severity, title, detail, chart_data}
```

**关键：** 洞察基于规则 + 统计阈值生成，不依赖 LLM API。速度快、零成本、结果可解释。

### 5.4 报告生成 (`ai/report.py`)

```python
class ReportGenerator:
    def __init__(self, client: OpenAI):
        self.client = client

    def generate(self, df, insights, chat_history) -> dict: ...
    def to_html(self, report: dict) -> str: ...
```

**报告结构：** 数据概览 → 预处理摘要 → 关键洞察 → 对话分析记录 → 总结与建议

**GPT 角色：** 将结构化数据组织成连贯叙述，数据真实性由代码保证，GPT 只负责"讲故事"。

---

## 6. 前端设计

### 6.1 整体布局

三栏式仪表盘：左侧导航 + 中间主内容区 + 右侧洞察面板

### 6.2 四个主页面

**数据概览页 (index.html):**
- 统计卡片行：总订单数 / 总销售额 / 客户数 / 商品数 / 国家数
- 数据预览表：前 100 行可滚动表格，支持列排序
- 预处理摘要：各步骤处理了多少行
- 数据质量仪表盘：各列完整率

**智能问答页 (analysis.html):**
- 对话区域：消息气泡，AI 回复内嵌图表
- 快捷问题标签：预设常见问题一键发送
- 代码折叠：每个回答附带"查看代码"面板
- 加载动画：AI 思考时显示打字效果

**可视化仪表盘 (visualization.html):**
- 6 个预置图表：月度趋势折线图、Top 10 商品柱状图、国家分布饼图、RFM 散点图、每周热力图、单价分布直方图
- 支持 AI 动态追加图表

**分析报告页 (report.html):**
- 一键生成 → GPT 润色 → Markdown 渲染
- 支持打印 / 导出 HTML

### 6.3 REST API 接口

| 接口 | 方法 | 用途 |
|------|------|------|
| `/api/upload` | POST | 上传数据文件 |
| `/api/data/summary` | GET | 数据概览统计 |
| `/api/data/preview` | GET | 前 N 行预览 |
| `/api/data/preprocess-report` | GET | 预处理摘要 |
| `/api/chat` | POST | 发送问题，获取 AI 回答 + 图表 |
| `/api/chat/history` | GET | 对话历史 |
| `/api/insights` | GET | 自动洞察列表 |
| `/api/analysis/{method}` | GET | 调用内置分析方法 |
| `/api/report/generate` | POST | 生成分析报告 |

---

## 7. 数据流

```
用户上传文件
  → loader.py 读取
  → preprocessor.py 清洗
  → 并行触发: analyzer / detector / insight 自动分析
  → 前端展示概览 + 洞察卡片
  → 用户进入问答 → code_generator 生成代码 → 安全执行 → 返回结果 + 图表
  → 用户可继续追问（多轮记忆）
  → 一键生成报告
```

---

## 8. 错误处理

| 场景 | 处理 |
|------|------|
| 上传非法文件格式 | 前端校验后缀 + 后端二次校验，友好提示 |
| CSV 编码错误 | chardet 自动检测，失败则尝试 utf-8 / gbk / latin1 |
| AI 代码执行出错 | 捕获异常，返回友好提示并建议换方式提问 |
| AI 生成危险代码 | 安全校验拦截，不执行，记录日志 |
| OpenAI API 超时/限流 | 重试 1 次，仍失败则返回服务不可用提示 |
| 列名不匹配预设分析 | 动态检测可用列，不可用则跳过 |
| 空数据集 / 全缺失列 | 预处理阶段检测并提示用户 |

---

## 9. 性能考量

| 问题 | 方案 |
|------|------|
| 大文件读取慢 | DataFrame 缓存在 Flask 全局变量 |
| 重复分析计算 | analyzer 结果缓存，数据不变不重算 |
| AI 响应慢 | 前端打字动画 + 可选 stream 模式 |
| 图表渲染卡顿 | >10000 数据点时随机采样 |

---

## 10. Demo 演示脚本（3 分钟）

| 步骤 | 时间 | 操作 |
|------|------|------|
| 1. 上传数据 | 30s | 上传 online_retail.csv → 自动处理 → 展示概览 + 洞察 |
| 2. 智能问答 | 60s | 自然语言提问 → 图表 → 追问 → 展示代码 |
| 3. 可视化 | 30s | 6 个预置图表 → 交互演示 |
| 4. 生成报告 | 30s | 一键生成 → 展示报告内容 |
| 5. 换数据集 | 30s | 上传新 CSV → 系统自动适配 → 验证通用性 |

---

## 11. 依赖清单

```
flask>=3.0
pandas>=2.0
numpy>=1.24
openai>=1.0
plotly>=5.0
chardet>=5.0
openpyxl>=3.1
markdown>=3.5
pytest>=7.0
```
