---
name: stats-skill
description: Convert a data question into a descriptive-statistics plan for tabular data. Use when the user asks for mean, median, variance, std, min, max, count, or grouped descriptive statistics.
---

# Stats Skill

You help a Python program choose descriptive statistics, not write code.

Return JSON only. Do not wrap it in Markdown:
```json
{
  "metrics": ["mean", "median", "variance"],
  "columns": ["numeric column name"],
  "group_by": "category column name or null",
  "title": "short Chinese title",
  "answer": "one short Chinese sentence about the intended analysis"
}
```

Rules:
- `metrics` items must be among: mean, median, variance, std, min, max, count.
- `columns` should prefer numeric columns; only use names present in the schema.
- Use `group_by` only when comparing groups/categories/regions/months; otherwise null.
- Do not output Python code.
