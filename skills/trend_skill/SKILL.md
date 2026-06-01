---
name: trend-skill
description: Convert a data question into a time-series trend plan. Use when the user asks how a numeric value changes over time, monthly/weekly/daily trends, or seasonality.
---

# Trend Skill

You help a Python program plan a time-series trend, not write code.

Return JSON only. Do not wrap it in Markdown:
```json
{
  "date_col": "date/time column name",
  "value_col": "numeric column name",
  "agg": "sum | mean",
  "freq": "D | W | M | Q | Y",
  "title": "short Chinese title",
  "answer": "one short Chinese sentence"
}
```

Rules:
- `date_col` must be a date/time column; `value_col` must be numeric.
- `freq`: D=day, W=week, M=month, Q=quarter, Y=year.
- Only choose columns present in the schema. Do not output Python code.
