# DataMind 全面重设计：全数据集通用化

**日期**: 2026-05-26
**版本**: C（全面重设计）
**目标**: 五大模块对任意数据集均可完整运行

---

## 一、问题根因

| # | 根因 | 影响 |
|---|------|------|
| 1 | `data/loader.py` CSV 分隔符固定为逗号 | 分号分隔的数据集（wine quality 等）解析成 1 列 |
| 2 | `ai/chat.py` 系统提示词只列出数值列名 | AI 无法映射用户自然语言到真实列名（"酒精浓度" → `alcohol`） |
| 3 | `data/analyzer.py` 6 个分析方法全部假设零售列存在 | 非零售数据全部返回 `None`/`[]`/`error` |
| 4 | `ai/insight.py` 洞察引擎 5 类中 3 类需要零售专属列 | 非零售数据洞察面板空白 |
| 5 | `templates/visualization.html` 仪表盘硬编码 6 张零售图 | 非零售数据仪表盘近乎全空 |
| 6 | `templates/analysis.html` 快捷提问按钮硬编码零售词汇 | 换数据集后快捷按钮无意义 |

---

## 二、全面重设计架构

```
数据上传
    │
    ▼
┌─────────────────────────────────────────┐
│  DataProfiler（新模块）                   │
│  - 自动检测数据画像（6 种模式）             │
│  - 输出: mode, cols 分类, suggested_qs  │
└─────────────────────────────────────────┘
    │
    ├──► Loader（修复）—— 分隔符自动嗅探
    │
    ├──► Analyzer（扩展）—— 新增通用分析方法
    │
    ├──► InsightEngine（扩展）—— 新增通用洞察
    │
    ├──► ChatSession（重写）—— 全列上下文 + 语义映射
    │
    └──► 前端自适应层（重写）
         ├── 可视化仪表盘：按画像选择 6 张图
         └── 快捷提问：从数据动态生成
```

---

## 三、数据画像分类系统（DataProfiler）

### 新增模块：`data/profiler.py`

**6 种数据画像：**

| 画像 ID | 名称 | 判断规则 |
|---------|------|---------|
| `retail` | 零售交易型 | 有日期 + 客户ID + 产品列 + 金额列 |
| `temporal` | 时间序列型 | 有日期列 + ≥1 数值列，无客户ID |
| `numeric` | 科学/数值型 | ≥4 数值列，无日期，无明显分类 |
| `categorical` | 分类/调查型 | ≥3 低基数类别列（唯一值 ≤50）|
| `geographic` | 地理分布型 | 有国家/省份/城市列 |
| `mixed` | 混合型 | 以上规则不唯一匹配时 |

**DataProfiler 输出结构：**
```python
{
  "mode": "numeric",              # 画像类型
  "display_name": "科学数值型",    # 展示名称
  "numeric_cols": ["fixed acidity", "alcohol", ...],
  "categorical_cols": [],
  "date_col": None,
  "target_col": "quality",        # 自动检测目标变量
  "has_date": False,
  "has_geography": False,
  "has_customer": False,
  "col_info": {                   # 全列信息（注入 AI）
    "fixed acidity": {"dtype": "float64", "samples": [7.4, 7.8, 7.8]},
    "alcohol": {"dtype": "float64", "samples": [9.4, 9.8, 9.8]},
    ...
  },
  "suggested_questions": [        # 自动生成建议问题
    "alcohol 列的分布情况如何？",
    "哪些特征与 quality 相关性最高？",
    ...
  ]
}
```

---

## 四、Loader 修复：CSV 分隔符自动嗅探

**`data/loader.py`** `_read_csv()` 增加嗅探逻辑：

```python
def _detect_separator(file_path: str, encoding: str) -> str:
    """用 csv.Sniffer 检测分隔符，候选: , ; \t |"""
    with open(file_path, encoding=encoding, errors="replace") as f:
        sample = f.read(4096)
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        return dialect.delimiter
    except csv.Error:
        return ","   # 回退逗号
```

逻辑：先检测编码 → 再嗅探分隔符 → 再读取 DataFrame。

---

## 五、Analyzer 扩展：通用分析方法

**`data/analyzer.py`** 新增以下方法：

### 5.1 `numeric_distributions(max_cols=6)`
返回 Top N 数值列的直方图数据（bins=30）。

```python
返回: [{"col": "alcohol", "bins": [...], "counts": [...], "mean": 10.4, "std": 1.0}]
```

### 5.2 `category_distributions(max_cols=4, max_categories=20)`
返回低基数类别列的频次数据。

```python
返回: [{"col": "quality", "labels": [3,4,5,6,7,8], "counts": [10,53,681,...]}]
```

### 5.3 `scatter_top_pairs(n_pairs=3)`
取相关性最高的 N 对数值列，返回散点数据（最多 500 个采样点）。

```python
返回: [{"x_col": "alcohol", "y_col": "quality", "x": [...], "y": [...], "corr": 0.48}]
```

### 5.4 `box_plots(max_cols=6)`
返回数值列的箱线图统计（q1, q3, median, whiskers）。

### 5.5 `radar_chart()`
返回各数值列的均值归一化后的雷达图数据（适合科学型数据集概览）。

### 5.6 `adaptive_chart_configs(profile: dict) -> list`
根据数据画像，自动选择并填充 6 个图表的数据配置。**核心路由逻辑：**

```
retail   → [sales_trend, top_products, country_dist, corr, time_pattern, rfm]
temporal → [time_trend, category_dist, numeric_dist, corr, time_pattern, box_plots]
numeric  → [numeric_dist, corr_heatmap, box_plots, scatter_pair, radar, target_dist]
categorical → [cat_dist_1, cat_dist_2, cat_cross, corr, numeric_dist, radar]
geographic  → [geo_dist, numeric_dist, corr, box_plots, cat_dist, radar]
mixed       → [numeric_dist, corr, cat_dist, box_plots, scatter, radar]
```

---

## 六、InsightEngine 扩展

**`ai/insight.py`** 新增 3 类通用洞察：

### 6.1 `_numeric_distribution_insights()`
检测偏态系数（skewness）> 1.5 的数值列，提示"分布偏态"。

### 6.2 `_category_concentration_insights()`
检测类别列中最高频率类别占比 > 60% 的情况，提示"分类集中"。

### 6.3 `_target_correlation_insights(target_col)`
若存在目标列，找出与其相关性 > 0.3 的特征，提示"预测特征"。

---

## 七、ChatSession 重写：全列语义感知

**`ai/chat.py`** `build_system_prompt()` 重写：

**注入内容：**
1. 所有列名 + 数据类型 + 3 个样本值
2. 数据画像模式（"这是一个科学数值型数据集"）
3. **列名映射提示**：`"当用户说'酒精浓度'时，请使用列名 'alcohol'"`
4. 明确指令：`"使用数据中精确列名，禁止猜测或翻译列名"`

**系统提示词结构：**
```
角色定义
数据集画像（模式名称 + 规模）
---
【完整列信息】
列名 | 类型 | 样本值
fixed acidity | float64 | 7.4, 7.8, 7.8
volatile acidity | float64 | 0.7, 0.88, 0.76
alcohol | float64 | 9.4, 9.8, 9.8
quality | int64 | 5, 5, 5
---
【重要规则】
- 禁止使用 import 语句
- 使用精确列名（如用户说"酒精浓度"即为 "alcohol"）
- result 赋值，chart 赋值
...
```

---

## 八、前端自适应仪表盘重设计

### 8.1 API 变更

**新增端点：**
```
GET /api/analysis/data_profile
→ 返回数据画像（6 种模式 + 列信息 + 建议问题）

GET /api/analysis/adaptive_charts
→ 返回 6 个图表的数据配置（每个含 type + title + data）

GET /api/analysis/suggested_questions
→ 返回 4 个基于真实数据的建议问题
```

### 8.2 visualization.html 重设计

**布局不变（6-slot 网格），内容自适应：**

```html
<!-- 动态图表容器 -->
<div id="charts-section">
  <!-- 通过 JS 动态插入 6 个 chart-card -->
  <div id="adaptive-charts-grid" class="row g-4">
    <!-- 由 renderAdaptiveDashboard() 填充 -->
  </div>
</div>

<!-- 数据画像徽章 -->
<div id="profile-badge">
  <span id="profile-mode-label">◈ 检测中...</span>
</div>
```

**JS 渲染逻辑（`charts.js` 新增）：**
```javascript
async function renderAdaptiveDashboard() {
  const profile = await fetch('/api/analysis/data_profile').then(r => r.json());
  const charts  = await fetch('/api/analysis/adaptive_charts').then(r => r.json());

  // 更新画像徽章
  updateProfileBadge(profile.mode, profile.display_name);

  // 渲染 6 张图（type 驱动）
  charts.forEach((cfg, i) => renderChartSlot(i, cfg));
}

function renderChartSlot(index, cfg) {
  // cfg.type: histogram | heatmap | scatter | bar | box | line | pie | radar
  const renderers = {
    histogram:  renderHistogram,
    heatmap:    renderHeatmap,
    scatter:    renderScatter,
    bar:        renderBarChart,
    box:        renderBoxPlot,
    line:       renderLineChart,
    pie:        renderPieChart,
    radar:      renderRadarChart,
  };
  renderers[cfg.type]?.(document.getElementById(`chart-slot-${index}`), cfg);
}
```

### 8.3 画像视觉风格差异化

| 画像 | 徽章颜色 | 图标 | 卡片强调色 |
|------|---------|------|---------|
| retail | 琥珀 `var(--amber)` | 🛒 | 金色边框 |
| temporal | 蓝色 `var(--blue)` | 📈 | 蓝色边框 |
| numeric | 青色 `var(--cyan)` | 🔬 | 青色边框 |
| categorical | 紫色 `var(--purple)` | 📊 | 紫色边框 |
| geographic | 绿色 `var(--green)` | 🌍 | 绿色边框 |
| mixed | 渐变 | ◈ | 多色边框 |

### 8.4 analysis.html 快捷提问按钮

**当前（硬编码）：**
```html
<button>月均销售额</button>
<button>Top 10 商品</button>
<button>国家分布</button>
<button>趋势图</button>
```

**改为（动态加载）：**
```javascript
async function loadSuggestedQuestions() {
  const qs = await fetch('/api/analysis/suggested_questions').then(r => r.json());
  const container = document.getElementById('quick-prompts');
  container.innerHTML = qs.map(q =>
    `<button class="quick-btn" onclick="sendQuestion('${q}')">${q}</button>`
  ).join('');
}
```

后端按数据画像生成问题：
- `numeric`: "alcohol 和 quality 的关系？", "哪列有异常值？", ...
- `temporal`: "最近一个月的趋势？", "每周高峰时段？", ...
- `retail`: 原有四个问题

---

## 九、实现顺序（优先级排序）

| 优先级 | 文件 | 理由 |
|--------|------|------|
| P0 | `data/loader.py` | 修复后所有问题均可触发 |
| P0 | `ai/chat.py` | 修复语义理解是演示必需 |
| P1 | `data/profiler.py`（新建） | 其余功能的基础 |
| P1 | `data/analyzer.py` | 新增通用方法 |
| P1 | `routes/api.py` | 新增 3 个端点 |
| P2 | `static/js/charts.js` | 自适应仪表盘渲染 |
| P2 | `templates/visualization.html` | 动态 DOM 结构 |
| P2 | `templates/analysis.html` | 动态快捷提问 |
| P3 | `ai/insight.py` | 通用洞察补充 |

---

## 十、验证标准

测试数据集（按画像分类）：
- **numeric**: `winequality-red.csv`（12数值列）
- **retail**: `Online Retail.csv`（原测试集）
- **temporal**: 任意有日期的时间序列 CSV
- **categorical**: 任意调查问卷类 CSV

验证标准：
- [ ] 每种数据集上传后仪表盘均显示 6 张有意义的图表
- [ ] AI 能正确识别用户问的是哪个列（语义映射）
- [ ] 快捷提问按钮与数据集内容匹配
- [ ] 自动洞察对非零售数据集有有效输出
- [ ] `pytest tests/ -x` 全部通过
