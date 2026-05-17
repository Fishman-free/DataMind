# DataMind — 智能问数平台

> **赛博朋克风格 · 液态玻璃 UI · 自然语言问数 · 零 API 依赖分析**

```
上传数据 → 自动清洗 → 规则引擎洞察 → 自然语言提问 → 交互图表 → 一键报告
```

---

## 为什么选择 DataMind？

| 优势 | 说明 |
|------|------|
| **赛博朋克沉浸式 UI** | 液态玻璃卡片、全息旋转立方体、粒子星场、赛博视频背景，浏览器即震撼 |
| **零 API 消耗核心功能** | 数据清洗、统计分析、自动洞察、可视化仪表盘全部本地运行，不调用任何外部 API |
| **多服务商 AI 接入** | 支持 OpenAI / DeepSeek / Kimi / 智谱 / 通义千问 / 硅基流动 / 豆包及任意兼容 OpenAI 格式的国内中转站，运行时一键切换，无需重启 |
| **优雅降级设计** | 无 API Key 时智能问答/报告自动切换模板模式，核心体验完整 |
| **全格式数据接入** | CSV（自动检测 UTF-8/GBK/Latin1 编码）、Excel、JSON，拖拽即上传 |
| **多轮上下文对话** | ChatSession 维护完整对话历史，支持追问和上下文引用 |
| **安全代码沙箱** | AI 生成的代码在白名单执行环境中运行，禁止 os/sys/subprocess 等危险调用 |
| **169 个单元测试** | 全模块覆盖，全部使用 MagicMock 模拟，不依赖真实 API 环境 |

---

## 目录

1. [界面预览](#1-界面预览)
2. [功能概览](#2-功能概览)
3. [目录结构](#3-目录结构)
4. [环境准备](#4-环境准备)
5. [快速启动](#5-快速启动)
6. [使用说明](#6-使用说明)
7. [API 接口参考](#7-api-接口参考)
8. [配置说明](#8-配置说明)
9. [测试说明](#9-测试说明)
10. [常见问题](#10-常见问题)
11. [技术架构](#11-技术架构)

---

## 1. 界面预览

### 视觉设计亮点

- **背景层**：粒子星场（80 颗星尘 + 径向渐变光晕）+ 脉冲同心环 + 电路网格 + 全息旋转 3D 线框立方体
- **赛博视频**：机械女孩 MP4 作为全屏背景，`mix-blend-mode: screen` 令暗色背景消融，人物以全息投影形式浮现
- **液态玻璃卡片**：`backdrop-filter: blur()` + `::before` 渐变遮罩边框，纯 CSS 实现
- **字体系统**：Instrument Serif（标题衬线）+ Barlow（正文）+ JetBrains Mono（代码）
- **配色**：纯黑 `#000` 底 + 电蓝 `#4D8AFF` / 青色 `#00E5FF` / 紫色 `#9B59FF` 三色高亮
- **拖拽上传遮罩**：全局拖拽监听，动态虚线边框动画，计数器防子元素误触发

---

## 2. 功能概览

| 功能模块 | 说明 | 需要 API Key |
|----------|------|:------------:|
| 数据上传（点击/拖拽） | CSV / Excel / JSON，自动检测编码，50 MB 限制 | 否 |
| 自动数据清洗 | 去重→缺失值→类型转换→无效过滤→异常值→特征工程 | 否 |
| 数据概览页 | 统计卡片 + 预处理摘要 + 前 50 行预览表格 | 否 |
| 自动洞察面板 | 趋势/异常/分布/相关/周期 5 类洞察，实时推送 | 否 |
| 可视化仪表盘 | 6 个 Plotly 交互图表 | 否 |
| 智能问答（多轮） | 自然语言 → AI 生成并执行代码 → 文字 + 图表 | **是** |
| 自动分析报告 | GPT 润色的结构化 Markdown 报告（含降级模板） | 是（降级可用） |

---

## 3. 目录结构

```
python_final/
├── app.py                    # Flask 入口，注册蓝图，维护全局 app_state
├── config.py                 # 配置（API Key、端口、文件大小限制等）
├── requirements.txt          # Python 依赖清单
├── README.md                 # 本文档
│
├── data/                     # 数据层
│   ├── loader.py             # 读取 CSV / Excel / JSON，自动检测编码
│   ├── preprocessor.py       # Pipeline 清洗（5 步骤 + 特征工程）
│   ├── analyzer.py           # 统计分析（趋势/商品/RFM/相关/时段/国家）
│   └── detector.py           # 异常检测（IQR / Z-Score / 趋势突变）
│
├── ai/                       # AI 智能体层
│   ├── chat.py               # 多轮对话管理（ChatSession）
│   ├── code_generator.py     # 自然语言 → Pandas 代码，安全沙箱执行
│   ├── insight.py            # 规则引擎自动洞察（零 API 依赖）
│   └── report.py             # GPT 润色分析报告，Markdown → HTML
│
├── routes/                   # Flask 路由层
│   ├── pages.py              # 页面路由（/, /analysis, /visualization, /report）
│   └── api.py                # REST API（/api/*，共 10 个端点）
│
├── templates/                # Jinja2 HTML 模板
│   ├── base.html             # 三栏布局基模板（含全部背景特效 DOM）
│   ├── index.html            # 数据概览页
│   ├── analysis.html         # 智能问答页
│   ├── visualization.html    # 可视化仪表盘
│   └── report.html           # 分析报告页
│
├── static/
│   ├── css/style.css         # 全量设计系统（液态玻璃 / 动画 / 拖拽遮罩）
│   ├── js/
│   │   ├── app.js            # 文件上传 + 拖拽 + 状态栏 + 洞察面板
│   │   ├── bg-effects.js     # 粒子星场 Canvas 动画
│   │   ├── chat.js           # 问答 UI（发送/渲染/重置）
│   │   ├── charts.js         # 6 个 Plotly 图表渲染
│   │   └── insights.js       # 洞察卡片渲染
│   └── videos/
│       └── mech-girl.mp4     # 赛博朋克背景视频
│
├── datasets/                 # 上传文件保存目录
│
└── tests/                    # 单元测试（169 个用例，全 Mock）
    ├── test_loader.py
    ├── test_preprocessor.py
    ├── test_analyzer.py
    ├── test_detector.py
    ├── test_chat.py
    ├── test_code_generator.py
    ├── test_insight.py
    ├── test_report.py
    └── test_api.py
```

---

## 4. 环境准备

### 4.1 Python 版本要求

```bash
# 要求 Python 3.10+，推荐 3.11
python --version
```

### 4.2 安装依赖

```bash
cd python_final
pip install -r requirements.txt
```

| 包 | 版本要求 | 用途 |
|----|---------|------|
| flask | ≥ 3.0 | Web 框架 |
| pandas | ≥ 2.0 | 数据处理核心 |
| numpy | ≥ 1.24 | 数值计算 |
| openai | ≥ 1.0 | 智能问答 + 报告生成 |
| plotly | ≥ 5.0 | 交互式图表（后端 JSON 序列化） |
| chardet | ≥ 5.0 | CSV 编码自动检测 |
| openpyxl | ≥ 3.1 | Excel 文件读写 |
| markdown | ≥ 3.5 | 报告 Markdown → HTML 转换 |
| pytest | ≥ 7.0 | 单元测试框架 |

### 4.3 配置 AI 服务（可选）

DataMind 支持任意兼容 **OpenAI Chat Completions API** 格式的服务商，包括国内中转站。

**不配置 API Key 时**，以下功能依然 100% 可用：
- 数据上传与自动清洗
- 数据概览（统计卡片 + 预处理摘要 + 数据预览）
- 自动洞察面板（全 5 类洞察）
- 可视化仪表盘（全 6 个图表）
- 分析报告（降级为内置模板版本）

**需要 API Key** 的功能：
- 智能问答（自然语言 → 代码 → 图表）
- GPT/大模型润色版分析报告

#### 方式一：界面配置（推荐，无需重启）

启动应用后，点击顶栏右侧 **⚙ CPU 图标** 打开 AI 服务配置面板：

1. 点击服务商卡片（OpenAI / DeepSeek / Kimi / 智谱 / 通义千问 / 硅基流动 / 豆包 / 自定义）
2. 填入对应的 API Key
3. 确认 Base URL 和模型名称
4. 点击「测试连接」验证
5. 点击「保存配置」即时生效

#### 方式二：环境变量（服务器部署推荐）

```bash
# Windows PowerShell
$env:AI_API_KEY  = "sk-..."
$env:AI_BASE_URL = "https://api.openai.com/v1"   # 或其他服务商地址
$env:AI_MODEL    = "gpt-4o-mini"

# macOS / Linux
export AI_API_KEY="sk-..."
export AI_BASE_URL="https://api.openai.com/v1"
export AI_MODEL="gpt-4o-mini"
```

#### 方式三：直接修改 `config.py`（仅限本地开发）

```python
AI_API_KEY  = "sk-..."
AI_BASE_URL = "https://api.openai.com/v1"
AI_MODEL    = "gpt-4o-mini"
```

#### 支持的服务商一览

| 服务商 | Base URL | 推荐模型 |
|--------|---------|---------|
| OpenAI | `https://api.openai.com/v1` | `gpt-4o-mini` |
| DeepSeek | `https://api.deepseek.com/v1` | `deepseek-chat` |
| Moonshot / Kimi | `https://api.moonshot.cn/v1` | `moonshot-v1-32k` |
| 智谱 GLM | `https://open.bigmodel.cn/api/paas/v4` | `glm-4-flash` |
| 通义千问 | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-plus` |
| 硅基流动 | `https://api.siliconflow.cn/v1` | `deepseek-ai/DeepSeek-V3` |
| 字节豆包 | `https://ark.cn-beijing.volces.com/api/v3` | `doubao-pro-32k` |
| **Ollama（本地免费）** | `http://localhost:11434/v1` | `qwen3:8b` |
| 自定义中转站 | 填写你的中转地址 | 按服务商支持填写 |

---

#### 方式四：Ollama 本地免费部署（无需 API Key，数据不出本机）

Ollama 允许在本机运行开源大模型，完全免费、无需联网、无需注册账号。

**前提条件**

1. 已安装 Ollama（[官网下载](https://ollama.com/download)，Windows/macOS/Linux 均支持）
2. 已拉取模型（在命令提示符/终端执行）：

```bash
ollama pull qwen3:8b     # 推荐，约 5 GB，16 GB 内存可用
ollama pull qwen3:4b     # 轻量版，约 2.6 GB，8 GB 内存可用
ollama pull qwen2.5:7b   # 备选，中文支持同样出色
```

**在 DataMind 中配置**

1. 启动 DataMind：`python app.py`
2. 点击顶栏 **⚙ 图标** 打开 AI 配置面板
3. 点击服务商卡片「**Ollama（本地免费）**」
4. Base URL 和 API Key 会**自动填入**（`http://localhost:11434/v1` 和 `ollama`），无需手动修改
5. 确认模型名与你拉取的一致（默认 `qwen3:8b`）
6. 点击「**测试连接**」，显示绿色"连接成功"后点「**保存配置**」

**验证 Ollama 服务正在运行**

```bash
# 查看已下载的模型列表
ollama list

# 若连接测试失败，手动启动服务
ollama serve
```

**已测试可用的 Qwen 模型**

| 模型 | 拉取命令 | 内存需求 | 特点 |
|------|---------|---------|------|
| `qwen3:4b` | `ollama pull qwen3:4b` | 8 GB | 轻量快速 |
| `qwen3:8b` | `ollama pull qwen3:8b` | 16 GB | 推荐，质量均衡 |
| `qwen3:14b` | `ollama pull qwen3:14b` | 32 GB | 更强推理 |
| `qwen2.5:7b` | `ollama pull qwen2.5:7b` | 16 GB | 上一代，稳定 |

> **注意**：Ollama 本地模型响应速度取决于硬件。有 NVIDIA GPU 时自动加速；纯 CPU 运行时，qwen3:8b 每次回答约需 15-60 秒。

---

## 5. 快速启动

```bash
cd python_final
python app.py
```

控制台输出：

```
 * Running on http://0.0.0.0:5000
 * Debug mode: on
```

打开浏览器访问：**http://localhost:5000**

> 首次访问会加载 Google Fonts CDN（Instrument Serif / Barlow / JetBrains Mono），国内网络可能需要数秒。若字体加载慢，可将 `base.html` 中 Google Fonts `<link>` 替换为本地字体文件。

---

## 6. 使用说明

### 6.1 上传数据

**方式一：点击上传**

顶部导航栏点击「上传数据」按钮，选择文件（支持 CSV / Excel / JSON）。

**方式二：拖拽上传**

将文件直接拖入浏览器窗口任意位置，松开即上传。页面会显示全屏蓝色遮罩提示。

| 格式 | 编码支持 | 备注 |
|------|---------|------|
| CSV | UTF-8 / GBK / Latin1（自动检测） | 任意分隔符 |
| Excel (.xlsx) | — | 默认读取第一个 Sheet |
| JSON | records 格式 / columns 格式 | — |

文件大小上限：**50 MB**（可在 `config.py` 修改 `MAX_FILE_SIZE`）

上传成功后：
- 顶栏状态变为「已加载: 文件名」（青色高亮）
- 底部状态栏显示「X 条记录  Y 个字段」
- 右侧洞察面板自动填充 5 类分析结果
- 若当前在概览页，数据卡片自动刷新

---

### 6.2 数据概览页（`/`）

上传成功后展示三部分内容：

**① 统计卡片**

| 卡片 | 说明 |
|------|------|
| 总记录数 | 清洗后的有效行数 |
| 字段数 | 数据集列数 |
| 时间跨度 | 自动识别日期列的起止时间（无日期列显示 `—`） |
| 总销售额 | 自动识别金额列求和（无金额列显示 `—`） |

**② 预处理摘要**

系统对数据执行 5 步 Pipeline 清洗，并逐步骤展示报告：

| 步骤 | 内容 |
|------|------|
| 1. 去重 | 移除完全重复的行，显示移除数量 |
| 2. 缺失值处理 | 数值列中位数填充，字符列众数填充，高缺失列（>50%）直接删除 |
| 3. 类型转换 | 字符串 → 数值 / 日期类型，显示转换的列名 |
| 4. 无效记录过滤 | 删除数量 ≤ 0 或单价 < 0 的行（适用电商场景） |
| 5. 异常值过滤 | IQR 法标记极端值，显示检测到的数量 |
| 特征工程 | 自动新增 TotalAmount、Hour、DayOfWeek 等派生字段 |

**③ 数据预览**

展示前 50 行数据的可横向滚动表格。

---

### 6.3 智能问答页（`/analysis`）

> 此功能需要配置 OpenAI API Key

**操作步骤：**

1. 先上传数据文件
2. 在输入框用自然语言提问，按回车或点击「发送」
3. AI 返回：文字分析 + 生成的 Python 代码 + 执行结果 + 可选图表

**示例问题（以 Online Retail 电商数据集为例）：**

```
月均销售额是多少？
Top 10 畅销商品有哪些，按销售额排序？
UK 客户的平均消费金额是多少？
画一个每月销售趋势的折线图
2011年11月销售额相比10月增长了多少百分比？
哪个国家的客户最多？
```

**多轮对话示例（支持上下文追问）：**

```
用户: Top 10 畅销商品是哪些？
AI:   （返回商品排名表）
用户: 这 10 个商品中，来自 UK 的销售额占比是多少？
AI:   （基于上文继续分析，无需重复指定数据集）
用户: 画个饼图展示一下
AI:   （生成并执行绘图代码，渲染 Plotly 交互图）
```

**界面元素说明：**

| 元素 | 功能 |
|------|------|
| 快捷提问按钮 | 预设 4 个常见问题，点击自动发送 |
| 发送按钮 | 提交问题（回车键等效） |
| 垃圾桶按钮 | 清空对话历史（不影响已上传数据集） |
| 「生成代码」区域 | 展示 AI 生成的 Python 代码，带语法高亮，支持一键复制 |
| 执行结果区域 | 展示代码运行的文字输出 |
| 动态图表区域 | Plotly 交互图表（可缩放/平移/下载） |

---

### 6.4 可视化仪表盘（`/visualization`）

6 个预置 Plotly 交互图表，上传数据后自动加载：

| 图表 | 类型 | 内容 |
|------|------|------|
| 月度销售趋势 | 折线图 | 按月聚合的销售额变化曲线 |
| Top 10 畅销商品 | 横向柱状图 | 按销售额排序的前 10 名商品 |
| 国家销售分布 | 环形饼图 | 各国家/地区的销售额占比 |
| 相关性矩阵 | 热力图 | 数值列两两相关系数（-1 ～ 1） |
| 订单时间规律 | 柱状图 | 按星期几的订单量分布 |
| RFM 客户散点图 | 散点图 | 频次 × 金额，点颜色表示最近购买天数 |

**Plotly 图表交互操作：**

| 操作 | 方法 |
|------|------|
| 区域缩放 | 鼠标框选图表中的区域 |
| 平移 | 按住左键拖动 |
| 数据悬停提示 | 鼠标悬停在数据点/柱/扇形上 |
| 保存为图片 | 点击图表右上角相机图标（PNG 格式） |
| 重置视图 | 双击图表空白区域 |
| 显示/隐藏系列 | 点击图例中的对应项 |

---

### 6.5 分析报告页（`/report`）

点击「生成分析报告」按钮生成报告：

**有 API Key**：GPT 将数据摘要、洞察结果、对话历史整合为结构化 Markdown 报告

**无 API Key（降级模式）**：系统使用内置模板立即生成基础报告（约 1 秒）

**报告结构：**

```markdown
# DataMind 数据分析报告

## 数据概览
- 总记录数 / 字段数 / 时间跨度 / 数据质量

## 关键发现
- 自动洞察转化的要点分析

## 对话摘要
- 本次智能问答的问答记录（若有）

## 总结与建议
- 数据质量评估
- 业务层面改进建议
```

点击「下载 Markdown」将报告保存为 `.md` 文件到本地。

---

### 6.6 右侧自动洞察面板

每次成功上传数据后，右侧面板自动刷新，显示 5 类规则引擎洞察（**零 API 消耗**）：

| 类型 | 严重度标签 | 检测逻辑 | 示例 |
|------|-----------|---------|------|
| 趋势洞察 | 🔴 高 | 相邻月份销售额环比变化 > 20% | 「2011年11月销售额环比增长 47%」 |
| 异常洞察 | 🔴 高 | IQR 法检测数值列极端值 | 「Quantity 列检测到 23 个异常值（2.1%）」 |
| 分布洞察 | 🟠 中 | 类别列某一值占比 > 60% | 「82% 的订单来自 United Kingdom」 |
| 相关洞察 | 🔵 低 | 数值列两两 Pearson 相关系数 > 0.7 | 「Quantity 与 TotalAmount 强正相关（0.89）」 |
| 周期洞察 | 🔵 低 | 按星期统计订单量找峰值 | 「周四是一周中订单量最高的一天」 |

---

## 7. API 接口参考

所有接口均以 `/api` 为前缀，返回 JSON。

### GET /api/ping

```json
{"status": "ok", "message": "DataMind API is running"}
```

---

### POST /api/upload

**请求**：`multipart/form-data`，字段名 `file`

**响应（成功 200）**：
```json
{
  "status": "ok",
  "filename": "online_retail.csv",
  "row_count": 406829,
  "clean_rows": 397924,
  "column_count": 9
}
```

**响应（失败 400）**：
```json
{"error": "不支持的文件格式"}
```

---

### GET /api/data/summary

```json
{
  "row_count": 397924,
  "column_count": 9,
  "date_range": {"start": "2010-12-01", "end": "2011-12-09"},
  "numeric_stats": {
    "Quantity": {"mean": 12.06, "std": 248.69, "min": 1, "max": 80995},
    "UnitPrice": {"mean": 3.46, "std": 69.32, "min": 0.001, "max": 38970}
  }
}
```

---

### GET /api/data/preview?n=100

返回前 N 行记录列表（默认 100，最大 500）。

---

### GET /api/data/preprocess-report

```json
{
  "original_rows": 541909,
  "final_rows": 397924,
  "remove_duplicates": {"removed": 5268},
  "fill_missing": {"filled_columns": ["CustomerID"], "dropped_columns": []},
  "type_conversion": {"converted": ["InvoiceDate"]},
  "filter_invalid": {"removed": 10624},
  "outlier_detection": {"flagged": 8907},
  "feature_engineering": {"added": ["TotalAmount", "Hour", "DayOfWeek", "Month"]}
}
```

---

### GET /api/insights

```json
[
  {
    "type": "trend",
    "severity": "high",
    "title": "销售额出现显著增长",
    "detail": "2011年11月相比10月环比增长 47.2%，需关注是否为季节性因素。"
  }
]
```

---

### GET /api/analysis/\<method\>

| method | 可选参数 | 说明 |
|--------|---------|------|
| `summary_stats` | — | 描述性统计（均值/中位数/标准差/分位数） |
| `sales_trend` | `?freq=ME` | 销售趋势（ME=月 / W=周 / D=日） |
| `top_products` | `?n=10` | 畅销商品 Top N（按销售额降序） |
| `rfm_analysis` | — | RFM 客户价值分析（Recency/Frequency/Monetary） |
| `country_distribution` | — | 国家/地区销售额分布 |
| `correlation_matrix` | — | 数值列相关系数矩阵 |
| `time_pattern` | — | 按星期/小时的订单规律 |

---

### POST /api/chat

**请求**：
```json
{"question": "月均销售额是多少？"}
```

**响应（成功）**：
```json
{
  "answer": "根据数据，月均销售额约为 74,570 元...",
  "code": "monthly = df.groupby(df['InvoiceDate'].dt.to_period('M'))['TotalAmount'].sum()\nresult = monthly.mean()",
  "execution": {
    "success": true,
    "result": 74570.23,
    "chart": null
  }
}
```

---

### GET /api/chat/history

返回当前会话的完整对话历史列表。

---

### POST /api/chat/reset

重置对话历史，返回 `{"status": "ok"}`。

---

### POST /api/report/generate

**响应**：
```json
{
  "title": "DataMind 数据分析报告",
  "content": "## 数据概览\n...",
  "html": "<h2>数据概览</h2>...",
  "generated_at": "2026-05-12 14:30:00"
}
```

---

## 8. 配置说明

编辑 `config.py` 修改以下参数：

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `AI_API_KEY` | `""` | API Key（优先读取环境变量，运行时可界面修改） |
| `AI_BASE_URL` | `https://api.openai.com/v1` | 服务商 Base URL，兼容所有 OpenAI 格式接口 |
| `AI_MODEL` | `"gpt-4o-mini"` | 使用的模型名称 |
| `UPLOAD_FOLDER` | `./datasets/` | 上传文件保存目录 |
| `MAX_FILE_SIZE` | `50 MB` | 最大上传文件大小（字节） |
| `ALLOWED_EXTENSIONS` | `csv, xlsx, json` | 允许上传的文件格式 |
| `SECRET_KEY` | `datamind-dev-secret-2026` | Flask Session 密钥（生产环境务必修改） |
| `DEBUG` | `true` | 调试模式（生产环境改为 `false`） |
| `HOST` | `0.0.0.0` | 监听地址 |
| `PORT` | `5000` | 监听端口 |

---

## 9. 测试说明

### 运行测试

```bash
# 运行全部测试（169 个用例）
python -m pytest tests/ -v

# 只运行特定模块
python -m pytest tests/test_api.py -v
python -m pytest tests/test_preprocessor.py -v

# 快速摘要（不显示详细用例）
python -m pytest tests/ -q
```

### 测试覆盖范围

| 测试文件 | 覆盖模块 | 用例数 |
|----------|----------|:------:|
| test_loader.py | data/loader.py | ~10 |
| test_preprocessor.py | data/preprocessor.py | ~30 |
| test_analyzer.py | data/analyzer.py | ~25 |
| test_detector.py | data/detector.py | 21 |
| test_chat.py | ai/chat.py | 12 |
| test_code_generator.py | ai/code_generator.py | 19 |
| test_insight.py | ai/insight.py | 7 |
| test_report.py | ai/report.py | 7 |
| test_api.py | routes/api.py | 34 |
| **合计** | | **169** |

> 所有测试均使用 `unittest.mock.MagicMock` 模拟 OpenAI API，无需真实 Key，CI 环境可直接运行。

---

## 10. 常见问题

**Q1：上传 CSV 后中文显示乱码？**

系统已内置自动编码检测（chardet），支持 UTF-8 / GBK / Latin1。若仍乱码，请用 Excel「另存为 CSV UTF-8（含 BOM）」格式后重新上传。

---

**Q2：智能问答返回 400 / API Key 错误？**

未配置 API Key，或 Key 格式不正确。参考第 4.3 节在界面配置面板填入 API Key，或通过环境变量 `AI_API_KEY` 设置后**重启应用**（`python app.py`）。

---

**Q3：可视化某个图表显示「暂无数据」？**

数据集缺少对应列。系统使用以下关键词模糊匹配（大小写不敏感）：

| 分析类型 | 识别关键词 |
|----------|-----------|
| 日期列 | date, time, invoice |
| 金额列 | amount, total, revenue, price |
| 数量列 | quantity, qty, count |
| 客户 ID | customerid, custid, client |
| 国家列 | country, region, area |

---

**Q4：如何分析非电商数据（气象/财务/医疗）？**

直接上传即可。系统自动检测列类型并应用通用策略。不能匹配的特定分析（如 RFM）会显示「暂无数据」，不影响其他功能（统计卡片、洞察面板、相关性矩阵、智能问答等仍完整可用）。

---

**Q5：报告生成等待很久没有响应？**

OpenAI API 响应通常需要 10-30 秒。若超时或 API 调用失败，系统自动降级为内置模板报告立即返回。

---

**Q6：如何在生产环境部署？**

```bash
pip install gunicorn

# 设置生产环境变量
export FLASK_DEBUG=false
export AI_API_KEY=sk-...
export FLASK_SECRET_KEY=your-strong-secret-key

# 启动（4 个 worker 进程）
gunicorn -w 4 -b 0.0.0.0:5000 "app:create_app()"
```

---

**Q7：视频背景无法播放 / 一片黑色？**

确认 `static/videos/mech-girl.mp4` 文件存在且可被 Flask 静态文件服务访问。浏览器需支持 `autoplay` muted 视频（Chrome / Edge / Firefox 均支持）。由于视频使用 `mix-blend-mode: screen`，若文件损坏，背景仍正常显示（粒子 + 光晕效果）。

---

**Q8：修改了 JS/CSS 代码后浏览器页面没有变化？**

Flask 开发服务器已配置禁用静态文件缓存（`SEND_FILE_MAX_AGE_DEFAULT = 0`），重启服务器后普通刷新即可生效。若仍无效，按 `Ctrl+Shift+F5`（Windows）或 `Cmd+Shift+R`（macOS）强制刷新浏览器缓存。

---

**Q9：切换到其他页面后数据消失，提示「请先上传数据文件」？**

Flask 重启后内存状态会清空。但系统已实现持久化恢复机制：重启后访问任意需要数据的页面，会自动从 `datasets/.last_upload.json` 读取上次上传的文件路径并恢复状态。

若自动恢复失败（文件已被删除或路径变更），重新上传数据文件即可。

---

**Q10：生成报告后下载的 `.md` 文件是网站的 HTML，而不是分析内容？**

这是 **Base URL 配置错误**导致的。AI 请求打到了中转站的前端页面，服务器把网页 HTML 当成了 API 响应返回。

**解决步骤：**

1. **重启 Flask 服务器**（`Ctrl+C` 后重新执行 `python app.py`）
2. 打开浏览器访问 `http://localhost:5000`，点击顶栏 **⚙ 图标** 进入 AI 配置面板
3. 检查并修正 **Base URL**：末尾必须带 `/v1`（或服务商指定的 API 路径）

   | ❌ 错误示例 | ✅ 正确示例 |
   |---|---|
   | `https://stuhelperai.com` | `https://stuhelperai.com/v1` |
   | `https://api.openai.com` | `https://api.openai.com/v1` |
   | `https://api.deepseek.com` | `https://api.deepseek.com/v1` |

4. 点击「**测试连接**」，确认返回绿色"连接成功"后再点击「**保存配置**」
5. 重新上传数据文件，再点击「生成分析报告」

> **系统已内置自动检测**：配置面板保存时会校验 Base URL 格式，若不以 `/v1` 结尾会弹出警告。同时报告生成时若 AI 返回 HTML 内容，会自动降级到模板报告，不再把网页代码写入下载文件。

---

**Q11：智能问答返回了答案，但页面上只显示绿色「AI」徽章、看不到文字内容？**

极少数情况下浏览器缓存了旧版 `chat.js`。解决方法：

```
Ctrl+Shift+F5   （Windows/Linux 强制刷新）
Cmd+Shift+R     （macOS 强制刷新）
```

或在浏览器开发者工具（F12）→「Network」选项卡中勾选「Disable cache」后刷新页面。

---

**Q12：图表渲染完成后，「加载中」的转圈动画仍然显示在图表上方？**

此问题已在当前版本修复（各图表渲染前会先清空容器内容）。若仍出现，同样通过强制刷新浏览器缓存（`Ctrl+Shift+F5`）解决。

---

**Q13：AI 配置「测试连接」成功，但智能问答总是返回「执行成功，无返回值」，没有文字答案？**

可能原因及排查步骤：

1. **模型名称错误**：确认填写的模型名称与服务商支持的一致（如 `glm-4-flash` 而非 `glm4-flash`）
2. **问题触发了代码路径而非纯文字答案**：系统默认让 AI 生成并执行代码，「执行成功，无返回值」表示代码执行了但 `result` 为空（如 `print()` 语句）。尝试换一个更明确的问题，如「月均销售额是多少，给我一个数字」
3. **数据未上传**：确认顶栏状态显示「已加载: 文件名」，若显示「未上传」则先上传数据文件

---

## 11. 技术架构

### 分层架构

```
┌─────────────────────────────────────────────────────────────┐
│  浏览器 (Bootstrap 5 · Plotly.js · marked.js · Canvas API)  │
│  Cinematic Space UI: 液态玻璃 · 粒子场 · 赛博视频 · 全息立方体  │
└──────────────────────┬──────────────────────────────────────┘
                       │  Fetch API (JSON)
┌──────────────────────▼──────────────────────────────────────┐
│  Flask  routes/pages.py  +  routes/api.py                   │
│  10 个 REST 端点  ·  app_state 内存缓存                       │
└──────┬────────────────────────────────────────┬─────────────┘
       │                                        │
┌──────▼──────────────┐              ┌──────────▼──────────────┐
│  data/ 数据层        │              │  ai/ 智能体层            │
│  loader.py          │              │  chat.py (多轮对话)      │
│  preprocessor.py    │              │  code_generator.py      │
│  analyzer.py        │              │  insight.py (零 API)    │
│  detector.py        │              │  report.py              │
└─────────────────────┘              └──────────┬──────────────┘
                                                │
                                     ┌──────────▼──────────────┐
                                     │  OpenAI gpt-4o-mini     │
                                     │  （可选，降级可用）        │
                                     └─────────────────────────┘
```

### 前端 z-index 层级

```
z-index 9990  #drag-overlay          全局拖拽上传遮罩
z-index  100  .topbar / .statusbar   顶部导航 + 底部状态栏
z-index    2  .main-wrapper          侧边栏 + 主内容区 + 洞察面板（液态玻璃）
z-index    1  .mech-video-bg         机械女孩赛博视频背景
z-index    0  canvas / .bg-orbs /    粒子星场 + 星云光晕 + 电路网格 +
              .holo-cube-wrapper /   全息旋转立方体 + 脉冲同心环
              .ring-system
```

### 安全沙箱（代码执行）

AI 生成的 Python 代码在受限命名空间中执行：

**允许的对象**：`df`, `pd`, `np`, `len`, `range`, `sum`, `min`, `max`, `round`, `sorted`, `list`, `dict`, `zip`, `enumerate`

**黑名单关键词**（检测到即拒绝执行）：
```
os, sys, subprocess, open, __import__, eval, exec,
shutil, pathlib, socket, __builtins__, globals, locals
```

---

*DataMind v1.0 — 来源：学生 + AI*
