# 设计文档：预处理可视化增强 & 图表标签补全

**日期：** 2026-06-01
**背景：** 补足大作业要求——加入 matplotlib + seaborn 第三方库，强化数据清洗步骤可视化，补全所有图表标题和坐标轴标签。

---

## 一、目标

1. 新增 `data/preprocess_visualizer.py` 模块，使用 seaborn + matplotlib 生成 5 张预处理诊断图（base64 PNG）。
2. 新增 API 端点 `GET /api/analysis/preprocess_charts`，供前端获取诊断图。
3. 在可视化仪表盘页面顶部新增"数据预处理报告"折叠面板，展示 5 张图。
4. 为 `analyzer.py` 所有分析方法的返回值补全 `title`/`x_label`/`y_label` 元数据。
5. 更新 `charts.js` 渲染时读取元数据，自动填充 Plotly 轴标签。

---

## 二、架构

### 新增文件

| 文件 | 职责 |
|------|------|
| `data/preprocess_visualizer.py` | 使用 seaborn + matplotlib 生成 5 张诊断图，每张返回 base64 PNG 字符串 |

### 修改文件

| 文件 | 改动摘要 |
|------|----------|
| `requirements.txt` | 添加 `matplotlib>=3.7`、`seaborn>=0.13` |
| `routes/api.py` | 新增 `GET /api/analysis/preprocess_charts` 端点 |
| `data/analyzer.py` | 6 个分析方法返回值增加 `title`/`x_label`/`y_label` |
| `static/js/charts.js` | `_renderChartSlot()` 读取轴标签元数据并传给 Plotly layout |
| `templates/visualization.html` | 新增预处理报告折叠面板 + JS 调用逻辑 |

---

## 三、数据流

```
前端 initVisualizationPage()
  └─ 请求 GET /api/analysis/preprocess_charts
       └─ api.py 调用 PreprocessVisualizer(df_raw, df_clean, pp_report).generate_all()
            └─ 返回 {"charts": [{"title": str, "img": "data:image/png;base64,...", "desc": str}, ...]}
  └─ 前端在折叠面板中插入 <img> 标签展示
```

---

## 四、preprocess_visualizer.py 规格

### 类接口

```python
class PreprocessVisualizer:
    def __init__(self, df_raw: pd.DataFrame, df_clean: pd.DataFrame, pp_report: dict) -> None: ...
    def generate_all(self) -> dict:
        """返回 {"charts": [ChartItem, ...]}"""
    def _fig_to_base64(self, fig) -> str:
        """matplotlib Figure → base64 PNG data URL"""
```

每张图均调用 `plt.style.use('dark_background')` + 深色背景色 `#0d1117`，与项目赛博朋克主题统一。

### 5 张诊断图

| # | 方法名 | 图名 | 使用的库/函数 | x 轴标签 | y 轴标签 |
|---|--------|------|---------------|----------|----------|
| 1 | `_chart_missing_heatmap` | 缺失值分布热力图 | `seaborn.heatmap` | 列名 | 样本索引（采样） |
| 2 | `_chart_pipeline_funnel` | 预处理流水线行数变化 | `matplotlib.barh` | 行数 | 处理阶段 |
| 3 | `_chart_outlier_boxplot` | 数值列异常值箱线图 | `seaborn.boxplot` | 列名 | 数值 |
| 4 | `_chart_dtype_pie` | 列数据类型分布 | `matplotlib.pie` | — | — |
| 5 | `_chart_fill_compare` | 缺失值填充前后对比 | `matplotlib.bar` | 列名 | 缺失单元格数 |

每张图均包含：
- 图标题（中文）
- x 轴/y 轴标签（中文）
- 图注/图例（视图类型而定）

---

## 五、analyzer.py 元数据补全

以下 6 个方法返回值新增字段：

| 方法 | title | x_label | y_label |
|------|-------|---------|---------|
| `sales_trend` | 月度销售额趋势 | 日期 | 销售额 |
| `top_products` | Top 10 商品销售额 | 销售额 | 商品名称 |
| `country_distribution` | 各国/地区销售分布 | 国家/地区 | 销售额 |
| `rfm_analysis` | RFM 客户分析（频次 vs 金额） | 购买频次 | 消费金额 |
| `time_pattern` | 每周各小时销售热力图 | 小时 | 星期 |
| `correlation_matrix` | 数值列相关性矩阵 | 列名 | 列名 |

---

## 六、charts.js 修改

`_renderChartSlot(i, cfg)` 中，当 `cfg.x_label`/`cfg.y_label` 存在时，merge 进 Plotly layout：

```js
if (cfg.x_label) layout.xaxis = { ...layout.xaxis, title: { text: cfg.x_label } };
if (cfg.y_label) layout.yaxis = { ...layout.yaxis, title: { text: cfg.y_label } };
if (cfg.title)   layout.title = { text: cfg.title, font: { color: '#8899B8', size: 13 } };
```

---

## 七、visualization.html 修改

在 `#charts-section` 上方新增折叠面板：

```html
<div class="accordion mb-4" id="prepAccordion">
  <div class="accordion-item" style="background:#0d1117;border:1px solid #1e3a5f">
    <h2 class="accordion-header">
      <button class="accordion-button collapsed" data-bs-toggle="collapse" data-bs-target="#prepPanel">
        📊 数据预处理报告（seaborn + matplotlib）
      </button>
    </h2>
    <div id="prepPanel" class="accordion-collapse collapse">
      <div id="prep-charts-grid" class="row g-3 p-3">
        <!-- 5 张 base64 图片动态插入 -->
      </div>
    </div>
  </div>
</div>
```

JS 在页面初始化时请求 `/api/analysis/preprocess_charts`，将返回的图片插入 `#prep-charts-grid`。

---

## 八、验收标准

- [ ] `requirements.txt` 含 matplotlib 和 seaborn
- [ ] `GET /api/analysis/preprocess_charts` 返回 5 张图的 base64 数据
- [ ] 每张图有标题、x/y 轴标签
- [ ] 仪表盘页面折叠面板可展开，图片正常显示
- [ ] Plotly 自适应图表卡片的轴标签已填充
- [ ] 所有现有测试通过
