---
name: profile-skill
description: Convert a data question into a dataset-profile plan (overview, schema, or quality). Use when the user asks what the dataset looks like, what columns/types exist, how many rows, or about data quality and missing values.
---

# Profile Skill

You help a Python program plan a dataset profile, not write code.

Return JSON only. Do not wrap it in Markdown:
```json
{
  "scope": "overview | schema | quality",
  "answer": "one short Chinese sentence"
}
```

Rules:
- overview = rows/cols/type summary; schema = per-column types/samples; quality = quality scores / missing values.
- Do not output Python code.
