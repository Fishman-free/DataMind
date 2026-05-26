# DataMind 可视化可靠性与图像质量提升设计

日期：2026-05-26
范围：方案 A（最小侵入、稳健修复）

## 1. 背景与目标

用户确认本轮优先修复三类关键问题，并要求覆盖所有图类型的清晰可见性：

1. 可视化仪表盘卡片方框堆叠/尺寸异常（重叠、裁切、内容外溢）
2. 数据质量评分卡“时效性”维度绿条缺失
3. 智能问答生成图像中散点图无点或残缺

新增总目标：不仅修散点图，保证 histogram / heatmap / box / bar / line / scatter 全部图类型在常见分辨率下清晰可见。

## 2. 非目标（YAGNI）

- 本轮不做可视化架构重构（不做方案 B 的大规模管线重写）
- 不引入大型新依赖
- 不改变既有视觉主题风格（赛博朋克深色系）

## 3. 成功标准（验收口径）

### 3.1 仪表盘布局
- 6 张卡片在 1920×1080、1366×768、125% 缩放下无覆盖、无裁切、无明显错位
- 图元、坐标轴、标题均位于卡片绘图区内

### 3.2 质量卡“时效性”
- 任意数据集下“时效性”维度始终可见（有条形填充）
- 分值异常值被 clamp 到 [0,100]，前端不因 NaN/None 丢失条形

### 3.3 智能问答散点图
- 请求散点图时，有效数据存在则必须显示可见点
- 若有效点数为 0，自动降级到可解释替代图（箱线图/分布图），并在回答中说明原因

### 3.4 全图类型清晰度
- 对 histogram/heatmap/box/bar/line/scatter 均应用统一可见性守卫
- 不出现“图已渲染但看不到主图元”的情况

## 4. 设计方案（方案 A）

### 4.1 前端渲染层（布局与尺寸稳定）

涉及文件：
- `templates/visualization.html`
- `static/js/charts.js`
- `static/css/style.css`（按需）

关键设计：
1. **容器统一高度策略**：统一 chart-card / chart-slot / header 关系，避免绘图区被 header 挤占。
2. **渲染时机校正**：首次 `Plotly.react/newPlot` 后执行 `requestAnimationFrame + Plotly.Plots.resize` 二次校正。
3. **可见性重试**：容器宽高为 0 时延迟一次重渲染，避免首帧不可见导致图像错位。
4. **窗口变更重排**：对 resize 绑定节流重排，保证不同分辨率下卡片稳定。

### 4.2 质量评分映射层（时效性维度兜底）

涉及文件：
- `data/quality_scorer.py`
- `templates/index.html`

关键设计：
1. 后端输出统一维度协议：`{ key, label, score, reason? }`。
2. `timeliness` 维度不可省略：
   - 有日期列：按日期覆盖度/新鲜度计算
   - 无日期列：返回中性兜底分并附 `reason`
3. 前端渲染强制创建所有维度 DOM，并 `clamp(score, 0, 100)` 后映射宽度。

### 4.3 AI 生成约束层（散点图稳定出图）

涉及文件：
- `ai/chat.py`
- `ai/chart_generator.py`
- （可选）`ai/code_generator.py`

关键设计：
1. Prompt 增加硬约束：
   - `dropna(subset=[x, y])`
   - `pd.to_numeric(..., errors='coerce')`
   - 绘图前检查有效点数
2. 执行后结果校验：
   - 若 scatter trace 点数为 0，触发自动降级
   - 降级优先级：箱线图 > 分布图 > 标准空态提示
3. 回答可解释：明确告知降级原因（如“有效点为 0，已自动降级”）。

## 5. 统一“全图清晰可见”守卫

在 `static/js/charts.js` 增加统一守卫逻辑（按图类型分发）：

1. **数据守卫**：最小有效数据量检查（点数、维度、矩阵结构、长度一致性）
2. **可见性守卫**：最小字号、最小 marker size、最小 opacity、对比度阈值
3. **容器守卫**：渲染后 resize 校正 + 视口变化节流重排
4. **反馈守卫**：降级解释文案标准化，不输出残缺图

## 6. 数据流与回退策略

### 6.1 仪表盘渲染流
`fetch adaptive_charts -> build cards -> initial plot -> rAF resize -> resize listener`

失败回退：
- 容器不可见：延迟一次重试
- 渲染异常：展示标准空态卡片（非破图）

### 6.2 质量卡渲染流
`quality_scorer -> dimensions(all keys) -> frontend clamp -> bar width`

失败回退：
- 维度缺失：后端补齐
- 分值异常：前端归一化后渲染

### 6.3 智能问答图像流
`user intent -> AI code -> execute -> validate chart -> show or fallback`

失败回退：
- scatter 无有效点：降级替代图并解释原因

## 7. 测试策略

### 7.1 自动化
- 后端：图配置结构合法性测试（各类型字段完整）
- 前端：渲染守卫与降级分支测试（坏数据输入）

### 7.2 人工验收矩阵
按 4 类数据集验证 6 图卡：
- numeric（wine）
- retail（online retail）
- categorical（问卷）
- temporal（时间序列）

每张图检查：
1) 主图元存在 2) 轴标签清晰 3) 标题完整 4) 不溢出卡片 5) 缩放后可读

## 8. 风险与缓解

1. **Plotly 在隐藏容器初渲染尺寸错误**
   缓解：可见性判断 + rAF 二次 resize + 延迟重试。

2. **不同数据集字段语义差异导致散点空图**
   缓解：生成时强制清洗 + 执行后点数校验 + 降级链路。

3. **质量维度映射不一致**
   缓解：后端统一协议，前端只做纯渲染。

## 9. 变更清单

- `static/js/charts.js`
- `templates/visualization.html`
- `static/css/style.css`（如需）
- `data/quality_scorer.py`
- `templates/index.html`
- `ai/chat.py`
- `ai/chart_generator.py`
- `ai/code_generator.py`（可选）

## 10. 里程碑

- M1：布局与尺寸稳定（仪表盘）
- M2：质量卡时效性维度稳定输出
- M3：散点图稳定与全图守卫生效
- M4：四类数据集端到端回归通过
