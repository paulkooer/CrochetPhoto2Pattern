## 变更目的 / Purpose

<!-- 解决什么问题？为什么现在需要？ / What problem does this solve, and why now? -->

## 主要变化 / Main changes

<!-- 用户可见行为、数据格式或内部实现。 / User-visible behavior, formats, or implementation. -->

## 验证 / Verification

<!-- 实际命令与结果；UI 附脱敏截图。 / Actual commands/results; redacted screenshots for UI changes. -->

## 风险与边界 / Risks and boundaries

<!-- 兼容性、隐私、失败模式、Beta/门禁。 / Compatibility, privacy, failures, Beta claims, and gates. -->

## 检查清单 / Checklist

- [ ] 新行为有测试，缺陷修复有复现 / New behavior is tested; fixes include a reproducer
- [ ] `ruff check .`、相关测试与 `git diff --check` 通过 / Checks pass
- [ ] 无密钥、`.env`、私人图片、个人信息或许可不清的数据 / No secrets or unauthorized/private data
- [ ] 未把自动化正确性描述为实体可钩性证据 / Automation is not presented as physical evidence
- [ ] 中英文 README、相关文档、CHANGELOG 和状态已同步 / Both-language user docs are updated where needed
- [ ] 格式变化有版本、兼容读取或迁移说明 / Format changes include versioning, compatibility, or migration
