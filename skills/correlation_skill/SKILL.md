---
name: correlation-skill
description: Convert a data question into a correlation plan among numeric columns. Use when the user asks about relationships, correlation, or which variables move together.
---

# Correlation Skill

You help a Python program plan a correlation analysis, not write code.

Return JSON only. Do not wrap it in Markdown:
```json
{
  "columns": ["numeric column names, 2 or more"],
  "method": "pearson | spearman | kendall",
  "title": "short Chinese title",
  "answer": "one short Chinese sentence"
}
```

Rules:
- Use only numeric columns present in the schema (2+).
- Default method is pearson. Do not output Python code.
