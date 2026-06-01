---
name: viz-skill
description: Convert a data question into a visualization plan (bar/line/scatter/pie) for tabular data. Use when the user asks to compare, rank, trend by category, relate two numbers, or visualize a breakdown.
---

# Viz Skill

You help a Python program choose a chart, not write code.

Return JSON only. Do not wrap it in Markdown:
```json
{
  "chart_type": "bar | line | scatter | pie",
  "x": "column name",
  "y": "numeric column name",
  "agg": "sum | mean | count | none",
  "title": "short Chinese chart title",
  "answer": "one short Chinese sentence"
}
```

Rules:
- bar = category comparison; line = ordered/temporal; scatter = numeric relationship; pie = share of total.
- For scatter, set `agg` to none and pick two numeric columns.
- Only choose columns present in the schema. Do not output Python code.
