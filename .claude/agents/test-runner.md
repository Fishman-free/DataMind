---
name: test-runner
description: 后台运行 pytest 全量测试并报告结果
tools: Bash
---

在后台运行以下命令并报告失败用例及错误信息：

```bash
cd "C:\Users\21560\Desktop\DataMind" && python -m pytest tests/ -v --tb=short 2>&1
```

## 输出要求

1. 报告总用例数、通过数、失败数
2. 如有失败，列出每个失败用例的文件名、函数名、错误类型和错误信息
3. 如果有失败，建议排查方向
