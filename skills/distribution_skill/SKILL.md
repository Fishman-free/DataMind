---
name: distribution-skill
description: Convert a data question into a distribution plan for one numeric column (histogram or box plot). Use when the user asks about distribution, spread, outliers, or the shape of a single numeric variable.
---

# Distribution Skill

You help a Python program plan a single-column distribution, not write code.

Return JSON only. Do not wrap it in Markdown:
```json
{
  "column": "numeric column name",
  "kind": "hist | box",
  "bins": 30,
  "title": "short Chinese title",
  "answer": "one short Chinese sentence"
}
```

Rules:
- `column` must be numeric and present in the schema.
- `kind`: hist=histogram, box=box plot. Do not output Python code.
