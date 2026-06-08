# DataMind 项目指南

## 项目概述

DataMind 是一个智能数据分析平台，支持自然语言问数、NL2Vis 图表生成、自动洞察、多 Agent 报告生成等功能。

**核心特性**：
- 全数据集普适性（6 种画像自动检测）
- 技能路由 + 确定性执行（杜绝 AI 编造数据）
- 智能问答 ↔ NL2Vis 双向同步
- 零 API 依赖的规则引擎

---

## 技术栈

### 后端
- **框架**: Flask 3.0+（蓝图架构）
- **数据处理**: pandas 2.0+ / numpy 1.24+
- **AI 服务**: openai 1.0+（兼容 DeepSeek/Moonshot/智谱/通义千问/硅基流动/豆包/Ollama）
- **可视化**: plotly 5.0+ / matplotlib 3.7+ / seaborn 0.13+
- **文件解析**: openpyxl（Excel）/ python-calamine（高速 Excel）/ chardet（编码检测）
- **文档生成**: markdown 3.5+

### 前端
- **UI 框架**: Bootstrap 5 + 自定义赛博朋克 CSS
- **图表**: Plotly.js（交互式）
- **Markdown 渲染**: marked.js
- **通信**: SSE（Server-Sent Events）流式响应

### 部署
- **容器化**: Docker + docker-compose
- **反向代理**: Nginx（静态资源 + SSE 透传）

### 测试
- **框架**: pytest 7.0+
- **运行命令**: `python -m pytest tests/ -x --tb=short -q`

---

## 项目结构

```
DataMind/
├── app.py                    # Flask 应用入口（工厂函数）
├── config.py                 # 配置文件（AI 服务/文件上传/Flask 参数）
├── requirements.txt          # Python 依赖
├── Dockerfile                # Docker 构建文件
├── docker-compose.yml        # Docker Compose 编排
├── nginx.conf                # Nginx 配置（SSE 透传）
│
├── ai/                       # AI 智能体层
│   ├── chat.py               # 多轮对话管理（ChatSession）
│   ├── code_generator.py     # 自然语言→代码生成 + 安全沙箱
│   ├── chart_generator.py    # NL2Vis 自然语言图表生成器
│   ├── insight.py            # 规则引擎自动洞察（零 API 依赖）
│   ├── report.py             # 报告生成器（简洁/深度双模式）
│   ├── report_agents.py      # 多 Agent 深度报告框架（4 个 Agent）
│   ├── storyteller.py        # 数据叙事引擎（华尔街日报体）
│   ├── plan_generator.py     # 智能分析计划生成器
│   ├── skill_router.py       # 技能路由器（LLM 选择技能 + 生成计划）
│   └── anthropic_adapter.py  # Anthropic SDK → OpenAI 兼容适配器
│
├── data/                     # 数据处理层
│   ├── loader.py             # 文件加载器（CSV/Excel/JSON）
│   ├── preprocessor.py       # 7 步预处理 Pipeline
│   ├── analyzer.py           # 7 种内置分析方法
│   ├── detector.py           # 异常值检测器（IQR 法）
│   ├── profiler.py           # 数据画像检测（6 种模式）
│   ├── quality_scorer.py     # 数据质量评分卡（5 维度）
│   └── preprocess_visualizer.py  # 预处理可视化（seaborn/matplotlib）
│
├── skills/                   # 技能层（确定性执行）
│   ├── __init__.py           # 技能注册表
│   ├── _contract.py          # 公共契约（SkillResult/infer_schema/safe_col）
│   ├── stats_skill/          # 统计分析技能
│   ├── viz_skill/            # 数据可视化技能
│   ├── trend_skill/          # 趋势分析技能
│   ├── correlation_skill/    # 相关性分析技能
│   ├── distribution_skill/   # 分布分析技能
│   └── profile_skill/        # 数据画像技能
│
├── routes/                   # 路由层
│   ├── pages.py              # 页面路由（渲染 HTML 模板）
│   └── api.py                # REST API 路由（20+ 接口）
│
├── templates/                # Jinja2 模板
│   ├── base.html             # 基础模板（导航栏 + 赛博朋克样式）
│   ├── index.html            # 数据概览页
│   ├── analysis.html         # 智能问答页（双栏布局）
│   ├── visualization.html    # 可视化仪表盘
│   └── report.html           # 分析报告页
│
├── static/                   # 静态资源
│   ├── css/style.css         # 全局样式（赛博朋克主题）
│   └── js/
│       ├── app.js            # 全局工具函数
│       ├── chat.js           # 智能问答组件（SSE 流式）
│       ├── chart-workspace.js # NL2Vis 图表工作台
│       ├── charts.js         # 仪表盘图表渲染
│       ├── insights.js       # 洞察卡片渲染
│       ├── sse-handler.js    # SSE 连接管理器
│       └── fireworks.js      # 烟花动画效果
│
├── tests/                    # 测试文件
│   ├── test_loader.py
│   ├── test_preprocessor.py
│   ├── test_analyzer.py
│   ├── test_detector.py
│   ├── test_chat.py
│   ├── test_insight.py
│   ├── test_report.py
│   └── test_report_agents.py
│
├── datasets/                 # 用户上传数据目录（.gitignore 排除）
├── docs/                     # 项目文档
└── .claude/                  # Claude Code 配置
    ├── skills/               # 技能定义
    ├── agents/               # 子代理定义
    └── settings.json         # Hooks 配置
```

---

## 编码规范

### Python 代码风格

1. **类型注解**: 使用 Python 3.10+ 语法（`list[str]` 而非 `List[str]`，`dict[str, Any]` 而非 `Dict[str, Any]`）
2. **字符串引号**: 统一使用双引号 `"`，除非字符串内含双引号
3. **导入顺序**: 标准库 → 第三方库 → 本地模块，用空行分隔
4. **文档字符串**: 每个模块、类、公共方法必须有 docstring（Google 风格）
5. **命名约定**:
   - 模块/函数/变量: `snake_case`
   - 类: `PascalCase`
   - 常量: `UPPER_SNAKE_CASE`
   - 私有方法/变量: `_前缀`
6. **来源标注**: 每个模块顶部添加 `来源：学生`、`来源：AI` 或 `来源：学生+AI`

### JavaScript 代码风格

1. **变量声明**: 优先使用 `var`（全局作用域），避免 `let`/`const`（防止作用域隔离导致跨文件访问失败）
2. **函数定义**: 全局函数不使用 `var`/`let`/`const` 前缀，确保可被其他文件调用
3. **字符串引号**: 统一使用单引号 `'`
4. **DOM 操作**: 优先使用 `document.getElementById()`，避免 jQuery 依赖
5. **错误处理**: 关键操作使用 `try/catch`，静默失败不阻塞用户交互

### HTML/CSS 代码风格

1. **模板继承**: 所有页面继承 `base.html`，使用 `{% block content %}` 和 `{% block scripts %}`
2. **CSS 变量**: 使用 `var(--blue)`、`var(--cyan)` 等主题变量，确保深色主题一致性
3. **响应式设计**: 使用 Bootstrap 的 `col-*` 网格系统，移动端优先

---

## 文件操作规则

### 读取文件前

1. **先确认文件存在**: 使用 `Glob` 工具查找文件路径，避免硬编码路径
2. **检查文件大小**: 超过 2000 行的文件使用 `offset` 和 `limit` 分段读取
3. **优先使用专用工具**: `Read` 工具 > `Grep` 工具 > `Bash` 命令

### 修改文件前

1. **先读后写**: 必须先使用 `Read` 工具读取文件内容，再使用 `Edit` 或 `Write` 工具修改
2. **精确匹配**: 使用 `Edit` 工具时，`old_string` 必须与文件内容完全匹配（包括缩进和空格）
3. **最小化变更**: 优先使用 `Edit` 工具进行局部修改，避免 `Write` 工具覆盖整个文件
4. **保留注释**: 不要删除现有的来源标注注释（`来源：学生`、`来源：AI`、`来源：学生+AI`）

### 创建新文件

1. **模块文档**: 每个新 Python 文件必须包含模块级 docstring 和来源标注
2. **导入规范**: 遵循导入顺序规范（标准库 → 第三方库 → 本地模块）
3. **测试文件**: 新增功能必须同步创建对应的测试文件

---

## 测试规范

### 测试策略

1. **TDD 优先**: 实现功能前先写测试（使用 `test-driven-development` skill）
2. **测试隔离**: 每个测试函数使用 `@pytest.fixture` 创建独立的测试数据
3. **边界覆盖**: 测试正常路径、边界条件、异常情况
4. **Mock 外部依赖**: 使用 `unittest.mock` 或 `pytest-mock` 模拟 AI API 调用

### 测试文件命名

- 测试文件: `tests/test_<模块名>.py`
- 测试函数: `test_<功能描述>`
- 测试夹具: `<数据描述>_df` 或 `<场景描述>_fixture`

### 运行测试

```bash
# 运行所有测试
python -m pytest tests/ -x --tb=short -q

# 运行单个测试文件
python -m pytest tests/test_analyzer.py -v

# 运行特定测试函数
python -m pytest tests/test_analyzer.py::test_summary_stats -v
```

---

## Git 提交规范

### Commit 消息格式

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Type 类型

- `feat`: 新功能
- `fix`: 修复 bug
- `docs`: 文档更新
- `style`: 代码格式调整（不影响逻辑）
- `refactor`: 重构（既不是新功能也不是修复）
- `perf`: 性能优化
- `test`: 测试相关
- `chore`: 构建/工具链/依赖更新

### 示例

```
feat(ai): 添加数据叙事引擎（华尔街日报体）

- 新增 storyteller.py 模块
- 支持 AI 生成 + 规则降级双模式
- JSON 解析三级容错

Closes #42
```

---

## AI 服务配置

### 支持的服务商

| 服务商 | Base URL | 推荐模型 |
|--------|----------|----------|
| OpenAI | `https://api.openai.com/v1` | gpt-4o-mini |
| DeepSeek | `https://api.deepseek.com/v1` | deepseek-chat |
| Moonshot | `https://api.moonshot.cn/v1` | moonshot-v1-8k |
| 智谱 GLM | `https://open.bigmodel.cn/api/paas/v4` | glm-4-flash |
| 通义千问 | `https://dashscope.aliyuncs.com/compatible-mode/v1` | qwen-turbo |
| 硅基流动 | `https://api.siliconflow.cn/v1` | DeepSeek-V3 |
| 豆包 | `https://ark.cn-beijing.volces.com/api/v3` | doubao-pro-4k |
| Ollama | `http://localhost:11434/v1` | qwen3:8b |

### 环境变量

```bash
AI_API_KEY=sk-xxx          # API 密钥
AI_BASE_URL=https://...    # API 端点
AI_MODEL=gpt-4o-mini       # 模型名称
AI_MAX_TOKENS=4096         # 最大 token 数
AI_REQUEST_TIMEOUT=60.0    # 请求超时（秒）
CODE_EXEC_TIMEOUT=30       # 代码执行超时（秒）
```

---

## 核心架构设计

### 1. 全数据集普适性

通过 `data/profiler.py` 的 `DataProfiler` 实现：
- **列名语义推断**: 正则匹配日期/客户/商品/金额/地理关键词
- **数据类型推断**: pandas dtype 检测 + nunique() 阈值
- **画像分类**: 6 种模式（retail/temporal/numeric/categorical/geographic/mixed）

### 2. 技能路由架构

通过 `ai/skill_router.py` 的 `SkillRouter` 实现：
- **第一层**: LLM 选择技能（注入所有 SKILL.md + 字段 schema + 数据样例）
- **第二层**: 确定性脚本执行（`skills/` 目录下的 `_skill.py` 文件）
- **兜底**: 无技能命中时走代码生成路径

### 3. 双向同步机制

通过全局变量实现零耦合同步：
- `window._currentChartData`: 当前图表 Plotly JSON（唯一真相源）
- `window.updateChatChartFromWorkspace()`: 工作台 → 对话区的同步函数
- `renderChart()`: 对话区 → 工作台的同步函数

### 4. 多 Agent 报告框架

通过 `ai/report_agents.py` 实现：
- `StatisticsAgent`: 数据特征统计描述
- `InsightAgent`: 关键洞察深度解读
- `QAAgent`: 对话问答摘要分析
- `SynthesisAgent`: 综合总结与建议

每个 Agent 独立降级（`_fallback()` 方法），保证报告始终可输出。

### 5. 零 API 依赖引擎

- **洞察引擎** (`ai/insight.py`): 8 种洞察类型，纯规则 + 统计阈值
- **质量评分** (`data/quality_scorer.py`): 5 维度评分，加权汇总
- **数据画像** (`data/profiler.py`): 6 种模式检测，自动建议问题

---

## 常见任务指南

### 新增分析方法

1. 在 `data/analyzer.py` 中添加新方法
2. 在 `routes/api.py` 的 `_SUPPORTED_METHODS` 中注册
3. 在 `tests/test_analyzer.py` 中添加测试
4. 更新 `skills/` 目录下对应的技能（如需要）

### 新增技能

1. 在 `skills/` 目录下创建新子目录
2. 创建 `SKILL.md`（技能描述 + JSON 输出格式）
3. 创建 `<name>_skill.py`（执行函数）
4. 在 `skills/__init__.py` 中注册
5. 在 `tests/` 中添加测试

### 新增 API 接口

1. 在 `routes/api.py` 中添加路由函数
2. 使用 `_require_data()` 检查数据是否已加载
3. 使用 `jsonify()` 返回 JSON 响应
4. 如需流式响应，使用 `_sse_stream()` 包装器

### 新增前端页面

1. 在 `templates/` 中创建新模板（继承 `base.html`）
2. 在 `routes/pages.py` 中添加页面路由
3. 在 `static/js/` 中添加对应的 JavaScript 文件
4. 在 `templates/base.html` 的导航栏中添加链接

---

## 调试技巧

### 后端调试

- Flask debug 模式: `config.DEBUG = true`（修改代码自动重载）
- 查看日志: 终端输出 Flask 请求日志 + 异常堆栈
- 测试单个接口: 使用 `curl` 或 Postman 直接调用 `/api/*` 接口

### 前端调试

- 浏览器开发者工具: F12 → Console 查看 JavaScript 错误
- Network 面板: 查看 SSE 流式响应和 API 请求
- Plotly 图表调试: 在 Console 中访问 `window._currentChartData` 查看图表数据

### AI 服务调试

- 测试连通性: 调用 `POST /api/config/ai/test` 接口
- 查看配置: 调用 `GET /api/config/ai` 接口
- 持久化配置: AI 配置保存在 `datasets/.ai_config.json`

---

## 注意事项

1. **单用户场景**: 当前设计为单用户模式，全局状态存储在 `app.state` 字典中
2. **文件上传限制**: 最大 50MB，支持 CSV/Excel/JSON 格式
3. **代码执行超时**: AI 生成的代码默认 30 秒超时，防止死循环
4. **Plotly 兼容性**: 使用 `_decode_plotly_bdata()` 解决 plotly 5.x Base64 编码问题
5. **SSE 透传**: Nginx 配置必须包含 `X-Accel-Buffering: no` 头，否则流式响应会被缓冲

---

<!-- superpowers-zh:begin (do not edit between these markers) -->
## Superpowers-ZH 技能框架

本项目已安装 superpowers-zh 技能框架（20 个 skills）。

### 核心规则

1. **收到任务时，先检查是否有匹配的 skill** — 哪怕只有 1% 的可能性也要检查
2. **设计先于编码** — 收到功能需求时，先用 brainstorming skill 做需求分析
3. **测试先于实现** — 写代码前先写测试（TDD）
4. **验证先于完成** — 声称完成前必须运行验证命令

### 可用 Skills

Skills 位于 `.claude/skills/` 目录，每个 skill 有独立的 `SKILL.md` 文件。

- **brainstorming**: 在任何创造性工作之前必须使用此技能——创建功能、构建组件、添加功能或修改行为。在实现之前先探索用户意图、需求和设计。
- **chinese-code-review**: 中文 review 沟通参考——话术模板、分级标注（必须修复/建议修改/仅供参考）、国内团队常见反模式应对。仅在用户显式 /chinese-code-review 时调用，不要根据上下文自动触发。
- **chinese-commit-conventions**: 中文 commit 与 changelog 配置参考——Conventional Commits 中文适配、commitlint/husky/commitizen 中文模板、conventional-changelog 中文配置。仅在用户显式 /chinese-commit-conventions 时调用，不要根据上下文自动触发。
- **chinese-documentation**: 中文文档排版参考——中英文空格、全半角标点、术语保留、链接格式、中文文案排版指北约定。仅在用户显式 /chinese-documentation 时调用，不要根据上下文自动触发。
- **chinese-git-workflow**: 国内 Git 平台配置参考——Gitee、Coding.net、极狐 GitLab、CNB 的 SSH/HTTPS/凭据/CI 接入差异与镜像同步配置。仅在用户显式 /chinese-git-workflow 时调用，不要根据上下文自动触发。
- **dispatching-parallel-agents**: 当面对 2 个以上可以独立进行、无共享状态或顺序依赖的任务时使用
- **executing-plans**: 当你有一份书面实现计划需要在单独的会话中执行，并设有审查检查点时使用
- **finishing-a-development-branch**: 当实现完成、所有测试通过、需要决定如何集成工作时使用——通过提供合并、PR 或清理等结构化选项来引导开发工作的收尾
- **mcp-builder**: MCP 服务器构建方法论 — 系统化构建生产级 MCP 工具，让 AI 助手连接外部能力
- **receiving-code-review**: 收到代码审查反馈后、实施建议之前使用，尤其当反馈不明确或技术上有疑问时——需要技术严谨性和验证，而非敷衍附和或盲目执行
- **requesting-code-review**: 完成任务、实现重要功能或合并前使用，用于验证工作成果是否符合要求
- **subagent-driven-development**: 当在当前会话中执行包含独立任务的实现计划时使用
- **systematic-debugging**: 遇到任何 bug、测试失败或异常行为时使用，在提出修复方案之前执行
- **test-driven-development**: 在实现任何功能或修复 bug 时使用，在编写实现代码之前
- **using-git-worktrees**: 当需要开始与当前工作区隔离的功能开发或执行实现计划之前使用——创建具有智能目录选择和安全验证的隔离 git 工作树
- **using-superpowers**: 在开始任何对话时使用——确立如何查找和使用技能，要求在任何响应（包括澄清性问题）之前调用 Skill 工具
- **verification-before-completion**: 在宣称工作完成、已修复或测试通过之前使用，在提交或创建 PR 之前——必须运行验证命令并确认输出后才能声称成功；始终用证据支撑断言
- **workflow-runner**: 在 Claude Code / OpenClaw / Cursor 中直接运行 agency-orchestrator YAML 工作流——无需 API key，使用当前会话的 LLM 作为执行引擎。当用户提供 .yaml 工作流文件或要求多角色协作完成任务时触发。
- **writing-plans**: 当你有规格说明或需求用于多步骤任务时使用，在动手写代码之前
- **writing-skills**: 当创建新技能、编辑现有技能或在部署前验证技能是否有效时使用

### 如何使用

当任务匹配某个 skill 时，使用 `Skill` 工具加载对应 skill 并严格遵循其流程。绝不要用 Read 工具读取 SKILL.md 文件。

如果你认为哪怕只有 1% 的可能性某个 skill 适用于你正在做的事情，你必须调用该 skill 检查。
<!-- superpowers-zh:end -->
