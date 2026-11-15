# Dependency update policy / 依赖更新口径

[Documentation index / 文档索引](README.md)

OpenCV is constrained to `<5` in both runtime and pose dependencies. Dependabot ignores
only routine major-version proposals for these two packages using `update-types`; it does
not use a dependency-wide ignore or a `versions` range. In Dependabot's upstream
[`IgnoreCondition#ignored_versions`](https://github.com/dependabot/dependabot-core/blob/fe4849492ce9f8b30213b718abaea99dfc581ded/common/lib/dependabot/config/ignore_condition.rb#L36-L41),
security-only updates return explicit `versions` and skip type-derived ranges. Its
[security-update regression test](https://github.com/dependabot/dependabot-core/blob/fe4849492ce9f8b30213b718abaea99dfc581ded/common/spec/dependabot/config/ignore_condition_spec.rb#L310-L316)
allows major, minor, and patch updates under such a rule. The manifest's `<5` constraint
still applies: a security fix requiring OpenCV 5 needs an explicit compatibility migration.

运行时与 pose 的 OpenCV 依赖继续限制为 `<5`。Dependabot 仅用 `update-types` 忽略两个包的
常规大版本提案，不使用整包忽略或 `versions` 范围。上面固定版本的官方实现及回归测试表明，
安全更新任务会跳过类型推导的忽略范围，因此本规则不会额外屏蔽安全更新。依赖声明中的
`<5` 约束仍存在；安全修复若要求 OpenCV 5，须单独处理兼容迁移。

This confirms the scope left open in the Fable review of PR #73. The earlier 2026-11-11
snapshot records the decision at that time and remains historical.
这补齐了 #73 复审中尚未核实的规则范围；11-11 审查快照保留当时的决定，不改写历史。
