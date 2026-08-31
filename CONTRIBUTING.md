# 贡献指南

**简体中文** | [English](CONTRIBUTING_EN.md)

感谢你改进 CrochetPhoto2Pattern。项目当前处于 Beta，优先接受能提高图解正确性、
证据质量、可复现性、隐私或可维护性的改动。

## 开始之前

- Bug 和功能建议请优先使用仓库的结构化 Issue 表单。
- 安全漏洞不要提交公开 Issue，请按 [SECURITY.md](SECURITY.md) 报告。
- 不要提交 API Key、`.env`、未经授权的人物照片、评测原图、试钩者个人信息或
  来历/许可不清楚的图解数据。
- 较大的算法、数据格式或产品声明变更，建议先发 Issue 说明问题、证据和兼容方案。

## 本地开发

需要 Python 3.11–3.14；仓库默认使用 Python 3.12 和 `uv.lock`：

```bash
uv sync --locked --extra dev
uv run --locked --extra dev ruff check .
uv run --locked --extra dev pytest -q --cov=app --cov-report=term-missing
uv lock --check
```

若改动 PDF 或姿态可选能力，还应分别运行：

```bash
uv sync --locked --extra dev --extra pdf
uv run --locked --extra dev --extra pdf pytest -q
uv sync --locked --extra dev --extra pose
uv run --locked --extra dev --extra pose pytest -q
```

## 设计与证据约束

1. **保持确定性核心可测试。** 模型输出必须先进入结构化模型和验证门禁，不能绕过
   针数代数、输入大小、部件连接或塑形上限检查。
2. **区分观测、推断和用户目标。** 单张照片提供相对视觉观测，绝对尺寸来自用户；
   背面、深度和不可见连接不能伪装成照片实测。
3. **不把自动化测试等同实体试钩。** 新算法需要单元/性质测试；声称改善可钩性、
   尺寸、材料或工时时，还要按 `docs/physical-trials.md` 提供独立验证证据。
4. **保护评测数据权利。** 真实照片评测必须遵守 `docs/evaluation.md` 的授权、用途、
   保留和哈希记录要求。原图与包含个人信息的报告不得进入仓库。
5. **保持兼容与可迁移。** 修改备份、分享、图解 JSON 或试钩记录格式时，增加版本、
   兼容读取或清晰迁移说明，并更新测试和 CHANGELOG。

## Pull Request 要求

- 一个 PR 聚焦一个可以独立审查的目标。
- 说明用户可见变化、风险、验证命令和结果；UI 变化附脱敏截图。
- 新行为带测试，修复缺陷先覆盖可复现案例。
- 若改变功能、安装、隐私、数据格式或发布门禁，同步更新 README、相关 `docs/`、
  `CHANGELOG.md` 或 `docs/system-status.md`。
- 确保 `git diff --check` 通过，且没有无关生成文件和本机路径。

提交 Pull Request 即表示你有权提交相关内容，并同意其按本仓库的 MIT License 发布。
