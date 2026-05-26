# AI 使用情况说明书与反思总结

## DataMind 智能问数平台

---

## 一、使用的 AI 工具

| 工具 | 模型 | 使用场景 |
|------|------|---------|
| Claude Code (CLI) | **claude-sonnet-4-6** | 核心开发工具：代码生成、架构设计、Bug 修复、文档编写、测试生成 |
| DeepSeek (API) | **deepseek-v4-pro** | 智能问答后端推理引擎：用户自然语言→Pandas 代码生成+执行+图表输出 |

---

## 二、AI 工具使用环节总览

| 环节 | 工具 | 具体用法 |
|------|------|---------|
| **架构设计** | claude-sonnet-4-6 | 分层架构规划、模块划分方案、数据流设计 |
| **后端代码** | claude-sonnet-4-6 | Python Flask 路由、AI 智能体层（chat/code_generator/report/report_agents/storyteller/chart_generator/plan_generator）、数据层处理逻辑 |
| **前端代码** | claude-sonnet-4-6 | 原生 JavaScript（SSE 流式处理器、图表工作台、聊天 UI）、CSS 赛博朋克设计系统 |
| **模板页面** | claude-sonnet-4-6 | Jinja2 模板（index/analysis/visualization/report） |
| **文档编写** | claude-sonnet-4-6 | README 技术流章节、API 文档、代码注释补充 |
| **单元测试** | claude-sonnet-4-6 | pytest 测试用例生成（11 个测试文件，247 个用例） |
| **Bug 修复** | claude-sonnet-4-6 | 系统排查根因（SSE 事件同步、代码沙箱 import 报错、数据故事生成质量） |
| **AI 推理服务** | deepseek-v4-pro | 用户问答时的流式代码生成与执行 |

---

## 三、五个关键 AI 使用案例

### 案例 1：POST-body SSE 流式底座设计与实现

| 维度 | 内容 |
|------|------|
| **任务目标** | 设计一个支持 POST 请求体传输的 SSE 流式响应系统，替代传统仅支持 GET 的 EventSource |
| **为什么选 AI** | SSE over POST 的实现涉及 fetch ReadableStream、跨 chunk 缓冲区拼接、AbortController 生命周期管理、事件路由派发等多个复杂子问题，手动编写需要大量时间和调试 |
| **采用 Prompt** | `"设计一个基于 fetch + ReadableStream 的 POST SSE 客户端，支持 AbortController 取消、跨 chunk 缓冲区拼接、120s 超时、按 type 字段事件路由派发，并在 SSE 不可用时自动降级为同步模式"` |
| **AI 返回摘要** | Claude 生成了 ~200 行纯 JavaScript 的 `sse-handler.js`，包含 `createSSEConnection()` 工厂函数、递归 `pump()` 读取循环、`processChunk()` 按换行分割+残片保留、`dispatch()` 事件路由 |
| **我的修改/验证** | 1）验证了 `JSON.parse` 异常处理→残片回退的边界逻辑；2）增加 `[DONE]` 字面量检测作为流结束信号；3）测试 120s 全局超时 + AbortError 静默处理；4）将 `recursive pump()` 改用 promise chain 避免调用栈溢出 |
| **最终结果** | 成为项目所有流式功能（问答、报告、图表）的共享底座，支持即插即用的 handler 注册 |

### 案例 2：安全代码沙箱 + Plotly 原生图执行

| 维度 | 内容 |
|------|------|
| **任务目标** | AI 生成的 Python 代码既要安全执行（无文件系统/网络访问），又要能产出交互式 Plotly 图表 |
| **为什么选 AI** | 沙箱白名单设计涉及 Python `exec()` 命名空间注入、内置函数白名单、黑名单检测、import 净化，需要兼顾安全性和功能性 |
| **采用 Prompt** | `"设计一个 Python 安全代码沙箱，__builtins__ 替换为白名单 dict（不允许 __import__），pd/np 预加载，额外预加载 plotly.express 和 plotly.graph_objects，自动将 go.Figure 转为 JSON dict，在 daemon thread 中执行并用 queue.Queue 轮询（1s 心跳），支持超时控制"` |
| **AI 返回摘要** | Claude 生成了 `code_generator.py` 的 `execute_safe()` 方法，包含三层安全防线、命名空间构建、Figure 自动序列化、线程+队列的异步执行模型 |
| **我的修改/验证** | 1）发现 AI 生成的 `validate_code` 在 `_sanitize_code` 之后执行会导致 `import os` 被净化后漏过，修正为先校验后净化；2）升级 import 净化正则从仅匹配 pandas/numpy 到匹配所有 import 语句；3）验证 `to_plotly_json()` 在 go.Figure 上的可用性；4）添加 plotly 未安装时的优雅降级 |
| **最终结果** | 前后端打通：AI 用 `px.bar()` 生成图→自动 JSON 化→SSE `chart` 事件推送→前端 `Plotly.react()` 渲染，全程对 AI 透明 |

### 案例 3：图表工作台双向状态同步调试

| 维度 | 内容 |
|------|------|
| **任务目标** | 解决"工作台图像不能和会话框同步的问题"——智能问答生成的图表有时不会出现在 NL2Vis 图表工作台中 |
| **为什么选 AI** | 问题涉及 SSE 事件时序、JavaScript 全局变量共享、Plotly.react() 渲染失败、竞态条件等多个可能根因，需要系统排查而非盲目改代码 |
| **采用 Prompt** | `"修复一下智能问答功能的问题，经常有工作台图像不能和会话框同步的问题出现"` |
| **AI 返回摘要** | Claude 触发 systematic-debugging 流程，逐文件追踪 `chat.js` → `chart-workspace.js` → `sse-handler.js` → `api.py` 的完整数据流，识别出 4 个根因：1）`onChart` 未调用 `renderChart`；2）`onCodeComplete` 为空函数；3）`renderChart` 缺少 try/catch+格式兼容；4）workspace→chat 方向完全缺失 |
| **我的修改/验证** | 1）验证 `Plotly.react()` 在空容器上的行为（会自动 newPlot）；2）确认 workspace 快捷操作→图表气泡的同步方向确实缺失；3）检查 `_sendingLock` 防抖逻辑不会造成死锁；4）手动测试各种图表格式（{data,layout} / 裸数组 / 单对象）的兼容性 |
| **最终结果** | 修复后的双向同步：Chat→Workspace 通过 `onChart` 推图+状态更新；Workspace→Chat 通过 `window.updateChatChartFromWorkspace()` 就地更新最后的气泡图表 |

### 案例 4：数据故事引擎的 Prompt 工程与调试

| 维度 | 内容 |
|------|------|
| **任务目标** | 数据故事功能生成的总是模板化的通用内容，无法产出生动的、有新闻价值的数据叙事 |
| **为什么选 AI** | 问题涉及 LLM prompt 设计（人设、约束、输出格式）、JSON 解析容错、输入截断优化、fallback 逻辑等多层原因 |
| **采用 Prompt** | `"数据故事这个功能没有效果，还是原来的问题，数据故事无法生成出生动的数据故事和有新闻意义的报道"` |
| **AI 返回摘要** | Claude 分析发现：1）`max_tokens=1000` 导致 JSON 截断→静默 fallback；2）系统 prompt 过于通用（"请生成报告"）；3）fallback 使用了错误的字段名 `description` 应为 `detail` |
| **我的修改/验证** | 1）将系统 prompt 重写为华尔街日报体记者人设（叙事弧线：开篇钩子→背景铺垫→数据深潜→结论启示）；2）`max_tokens` 从 1000→3000；3）输入数据截断从 1000 字符扩展到 2000；4）从 SQLite 格式优化为紧凑 JSON；5）用 curl+Python 解码测试验证实际输出质量（"84.6%的销售都来自一个角落，这家零售商为何不离不弃英国市场"）；6）发现前端 `renderStory` 不渲染 `highlight` 字段→修复 |
| **最终结果** | AI 现在能生成标题如"英国市场贡献84.6%营收，一家电商的全球化困境"的深度叙事，非模板化 |

### 案例 5：README 技术流文档生成

| 维度 | 内容 |
|------|------|
| **任务目标** | 为 README.md 新增"技术流"章节，解释项目的核心技术创新点，需要结合代码实现细节而非泛泛而谈 |
| **为什么选 AI** | 需要从数万行代码中提炼 8 个技术创新点，每个点涉及多文件的实现逻辑，手动编写费时且容易遗漏细节 |
| **采用 Prompt** | `"更新这个文档，新增加一个技术流的内容，解释一下有什么技术创新点"` |
| **AI 返回摘要** | Claude 深入阅读了 8 个源文件，生成了覆盖 POST-SSE 流式底座、安全沙箱、双向同步、多 Agent 框架、数据叙事引擎、质量评分卡、优雅降级、SSE 前端工程化共 8 个章节的完整技术文档，含架构图、代码示例和技术对比表 |
| **我的修改/验证** | 1）核对了每个技术描述的准确性（如 SSE 事件时序 `text_delta→code_complete→heartbeat→exec_result→chart→done`）；2）补充了图表工作台双向同步的 ASCII 架构图；3）调整了技术流章节的位置（置顶在目录之前） |
| **最终结果** | 形成了约 2500 字的技术深度文档，可直接作为项目答辩的技术亮点说明 |

---

## 四、AI 能力边界——我的关键决策与贡献

### 我独立做出的关键决策

| # | 决策 | 说明 |
|---|------|------|
| 1 | **项目定位** | 确定"赛博朋克风格 + 自然语言问数"的产品方向，AI 辅助实现而非主导方向 |
| 2 | **分层架构设计** | data/ ai/ routes/ templates/ static/ 五层架构的职责划分和依赖方向由我决定 |
| 3 | **优雅降级哲学** | "AI enhanced, not AI dependent"——每个 AI 功能必须有规则引擎 fallback 这一核心设计原则是我提出的 |
| 4 | **多服务商兼容方案** | 界面切换 OpenAI/DeepSeek/Kimi/智谱/通义千问/硅基流动/豆包/Ollama 的方案由我设计 |
| 5 | **中文文档体系** | README 的完整中文文档结构（12 个章节 + 14 个 FAQ）、Git 提交规范由我制定 |
| 6 | **测试数据选择** | 选择 Online Retail 电商数据集（54 万行），覆盖真实世界的数据质量问题（缺失值、异常值、文本首尾空白） |

### 我独立提出的分析思路

| # | 分析思路 | 说明 |
|---|---------|------|
| 1 | **华尔街日报体叙事框架** | 数据故事不应是报告改写，而应遵循新闻写作的叙事弧线（钩子→背景→深潜→启示） |
| 2 | **双向图表同步** | 发现 Chat→Workspace 和 Workspace→Chat 两个方向都需要同步，不能只做单向 |
| 3 | **三层安全防线** | Prompt约束→黑名单校验→import净化，逐层收缩的安全模型由我提出并验证 |
| 4 | **零 API 依赖的质量评分卡** | 5 维度加权评分的具体维度、权重分配、扣分规则由我设计 |

### 我自己重写或修改的代码

| 文件 | 修改内容 | 比例 |
|------|---------|:---:|
| `ai/storyteller.py` | 系统提示词从通用模板重写为华尔街日报体记者人设；输入优化（洞察紧凑化、数据截断扩展）；输出约束调整 | ~60% |
| `ai/code_generator.py` | validate/净化执行顺序修正；全量 import 净化正则升级；plotly 命名空间注入 + Figure 自动 JSON 化 | ~40% |
| `static/js/chart-workspace.js` | renderChart 错误处理 + 格式兼容；workspace→chat 同步调用 | ~30% |
| `static/js/chat.js` | onChart 推 workspace 逻辑；updateChatChartFromWorkspace 全局函数；状态提示更新 | ~25% |
| `ai/chat.py` | 系统提示词重写（告知 px/go 预加载，给出代码范例） | ~30% |
| `README.md` | 技术流章节 8 个子章节（约 2500 字） | 新增 |
| `routes/pages.py` | 4 个视图函数的 docstring 补充 | ~50% |
| 各 `__init__.py` | 模块级 docstring 完善 | ~40% |

### 参考了 AI 生成但最终未采纳的内容

| 内容 | 不采纳原因 |
|------|-----------|
| AI 建议的 `PreToolUse: block` Hook 格式 | `"type": "block"` 在该版本不合法，配置报错后删除 |
| AI 初始生成的 `_sanitize_code` 仅移除 pandas/numpy import | 在代码沙箱中不够用，升级为全量 import 移除 |
| AI 初始的"JSON 裸格式"chart 变量 | 升级为 Figure 对象→自动 JSON 化，降低 AI 出错概率 |

---

## 五、反思——AI 的价值与局限

### AI 最帮助我提升效率的环节

| 环节 | 效率提升 | 说明 |
|------|:---:|------|
| **代码生成** | 80% | 200+ 行的 SSE 处理器、安全沙箱、4 Agent 报告框架等复杂模块，手动编写需要数天，AI 可在数小时内完成初版 |
| **Bug 系统排查** | 70% | 从症状（"图表不同步"）到根因（4 个独立 bug）的系统追溯，AI 能遍历所有相关文件形成完整证据链 |
| **测试用例生成** | 90% | 247 个 pytest 用例中约 85% 由 AI 生成初版，我逐一验证逻辑正确性和边界覆盖 |
| **文档编写** | 60% | 12 章的 README、API 文档、技术流章节，AI 能从代码中自动提取信息并结构化呈现 |

### AI 最容易误导我的地方

| 陷阱 | 具体表现 | 教训 |
|------|---------|------|
| **格式语法假设** | AI 生成的 Hook 配置使用了 `"type": "block"`，但该版本不支持 | AI 对特定 CLI 工具配置语法的了解可能过时，需实测验证 |
| **代码执行顺序** | `validate_code` 和 `_sanitize_code` 的顺序错误导致安全漏洞 | AI 关注功能实现但可能忽略安全微妙性，安全代码必须逐行审查 |
| **静默失败** | `Plotly.react()` 的 Promise rejection 和 `renderChart` 缺少 try/catch，导致数据对但渲染不出来的诡异 bug | AI 倾向于"快乐路径"编程，需要主动添加错误处理 |
| **Prompt 设计** | 数据故事最初使用通用 prompt（"生成报告"），产出模板化内容 | 不能直接把功能需求当 prompt，需要注入领域知识（华尔街日报体） |

### 如果重新做一遍，我会如何更高效地使用 AI

1. **先写需求规格，再让 AI 编码** — 一开始我是"想到什么问什么"，后来发现让 AI 先读项目、先出方案、再编码，质量高很多

2. **把 AI 当"高级搜索引擎"而非"万能程序员"** — 遇到技术问题先让 AI 系统排查根因，而不是期待它一次猜对修复

3. **AI 写代码，我做架构和 Review** — 最有效的分工：我负责"做什么、为什么、合不合格"，AI 负责"怎么写、写出来、跑测试"

4. **Prompt 里注入领域知识** — 比如数据故事，不说"生成报告"，而说"用华尔街日报体，开篇用最震撼的数据发现抓住读者"

5. **用 AI 的 automated skill 管理 AI** — 系统地配置 hook（自动测试）、subagent（异步任务）、skill（重复流程），让 AI 自我管理、减少人工干预

---

## 六、结论

本项目在开发过程中系统性地使用了 claude-sonnet-4-6 和 deepseek-v4-pro 两款 AI 工具。AI 在代码生成（~70%）、测试生成（~85%）、Bug 排查（~80%）和文档编写（~60%）环节提供了显著效率提升。但 AI 的输出是"原材料"而非"成品"——每个 AI 生成的模块都经过了：
1. **逻辑验证**（是否正确实现了功能）
2. **安全审查**（是否有安全漏洞或边界问题）
3. **格式兼容**（是否与现有代码库一致）
4. **集成测试**（是否能与上下游模块协同工作）

项目的核心设计决策（分层架构、优雅降级哲学、安全模型、用户体验方向）均由我独立做出。AI 是强大的执行工具，而非决策替代品。

---

*文档生成日期：2026-05-25*
*AI 工具使用：claude-sonnet-4-6（开发）+ deepseek-v4-pro（推理）*
