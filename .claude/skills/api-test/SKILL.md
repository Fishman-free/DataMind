---
name: api-test
description: 快速验证 Flask API 端点可用性，自动检测改动影响的接口并跑测试
disable-model-invocation: true
---

# API 端点测试

## 使用方式

用户输入 `/api-test` 或 `/api-test <端点名称>` 快速验证接口。

## 工作流程

1. 检查 `routes/api.py` 最近改动，定位可能受影响的端点
2. 如果用户指定了端点名称，只跑对应的测试函数
3. 运行 `python -m pytest tests/test_api.py -v --tb=short -k "<关键词>"`
4. 报告结果：通过数 / 失败数 / 错误详情

## 常用命令

```bash
# 跑全部 API 测试
python -m pytest tests/test_api.py -v --tb=short

# 只跑对话相关端点
python -m pytest tests/test_api.py -v --tb=short -k "chat"

# 只跑图表相关端点
python -m pytest tests/test_api.py -v --tb=short -k "chart"

# 只跑 SSE 流相关端点
python -m pytest tests/test_api.py -v --tb=short -k "stream"

# 快速冒烟（只跑不报细节）
python -m pytest tests/test_api.py -q
```

## 接口覆盖清单

| 端点 | 测试关键词 |
|------|-----------|
| GET /api/ping | ping |
| POST /api/upload | upload |
| GET /api/data/summary | summary |
| GET /api/data/preview | preview |
| GET /api/data/preprocess-report | preprocess |
| GET /api/data/quality | quality |
| GET /api/insights | insight |
| POST /api/chart/generate | chart_generate |
| GET /api/analysis/<method> | analysis |
| POST /api/chat | chat |
| GET /api/chat/history | history |
| POST /api/chat/reset | reset |
| POST /api/report/generate | report |
| POST /api/plan/generate | plan |
| POST /api/report/story | story |
