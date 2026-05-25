---
name: gen-release-notes
description: 从 git log 自动提取 Conventional Commits，按 feat/fix/chore 分类生成中文 changelog
disable-model-invocation: true
---

# 生成 Release Notes

## 使用方式

用户输入 `/gen-release-notes` 或 `/gen-release-notes v2.0..v3.0` 指定版本范围。

## 工作流程

1. 获取 git log（默认从上次 tag 到 HEAD，或用户指定范围）
2. 按 Conventional Commits 分类：
   - `feat:` → 新功能
   - `fix:` → Bug 修复
   - `chore:` / `docs:` / `refactor:` → 其他
3. 生成中文 changelog，格式如下：

```markdown
## vX.Y.Z (YYYY-MM-DD)

### 新功能
- xxx

### Bug 修复
- xxx

### 其他
- xxx
```

## 执行命令

```bash
# 获取最近 20 条 commit
git log --oneline -20

# 从上次 tag 到 HEAD
git log $(git describe --tags --abbrev=0 2>/dev/null || echo "HEAD~20")..HEAD --oneline

# 指定版本范围
git log <old-version>..<new-version> --oneline
```
