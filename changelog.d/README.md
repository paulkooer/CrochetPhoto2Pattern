# Changelog fragments / 变更片段

Each PR adds one bilingual JSON file here instead of editing both shared changelogs.
每个 PR 在此新增一个中英双语 JSON 文件，避免并行修改两份总日志。

Name / 文件名：`<PR-number-or-slug>.<category>.json`

Categories / 分类：`added`, `changed`, `deprecated`, `removed`, `fixed`, `security`.

```json
{
  "zh": ["说明用户可见的变化、兼容性或发布流程变化。"],
  "en": ["Describe the user-visible, compatibility or release-process change."]
}
```

Use nonempty single-line bullets; Markdown links and code spans are allowed. Documentation
or maintenance changes may use a short maintenance note. Never include private photos,
local paths, or personal trial information. / 每项为非空单行文字，可包含 Markdown 链接和
代码。文档或维护改动可写简短维护说明；勿包含私人照片、本机路径或试钩个人信息。

```bash
python scripts/changelog_fragments.py check
python scripts/changelog_fragments.py render --date 2026-11-15
# Preview collection (no writes) / 预览汇总，不改文件
python scripts/changelog_fragments.py collect --date 2026-11-15
# At release preparation, before selecting the candidate / 发布准备、选定候选之前
python scripts/changelog_fragments.py collect --date 2026-11-15 --write
```

Collection inserts categorized entries into both `Unreleased` sections and removes fragments
only after both languages are written. Historical entries remain unchanged. Commit the two
logs and removed fragments together; only release preparation edits the shared logs.
汇总写入两份 `Unreleased`，双语均写入成功后才删除片段；历史条目保留。一起提交两份日志
和片段删除记录。共享日志仅在发布准备时修改。
