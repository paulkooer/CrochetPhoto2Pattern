# 系统状态与发布门禁

> 权威状态快照：2026-08-31。代码行为以当前源码、`pyproject.toml`、锁文件和
> 可复现验证结果为准；`audit-brief*.md`、`handoff-review.md` 与
> `optimization-brief.md` 是对应审查轮次的历史快照，不用于判断当前测试数量或发布状态。

## 当前结论

CrochetPhoto2Pattern 当前是 **0.2.0b1 工程候选版**：图解代数、输入门禁、导出和
发行包已有较完整的自动化保障，但尚未完成授权真实照片基线与实体试钩基线，因此不得
描述为“已验证尺寸、材料、工时或成品可钩性”的生产版本。

## 最近一次本地验证

| 检查 | 结果 | 说明 |
|---|---|---|
| 核心环境 | 701 passed, 5 skipped | Python 3.12.13；PDF 依赖、姿态运行时及授权真实照片缺失时按设计跳过 |
| PDF extras | 705 passed, 1 skipped | Python 3.11.15；`[pdf]` 实际执行全部 PDF 用例，仅授权真实照片评测跳过 |
| Pose extras | 701 passed, 5 skipped | Python 3.11.15；固定 MediaPipe 旧绑定后全绿，未安装 PDF/授权照片按设计跳过 |
| 覆盖率 | 88.11% | 干净核心环境，`pytest --cov=app --cov-fail-under=80` |
| 静态检查 | 通过 | `ruff check .` |
| 差异格式 | 通过 | `git diff --check` |
| 依赖锁 | 通过 | `uv lock --check`，Python 3.12 解析 |
| 依赖漏洞 | 通过 | `pip-audit --local` 未发现已知漏洞（2026-08-31） |
| wheel | 通过 | Python 3.12 隔离构建，三项 CLI、许可证、提示词和精选证据均须在包内 |

上述本地结果使用锁定的 Python 3.12.13 环境执行。项目正式支持范围是 Python
3.11–3.14；其他三个版本的结果仍必须以远程 CI 为准，不能由单版本本地结果替代。

## 发布门禁

| 门禁 | 当前状态 | 通过条件 |
|---|---|---|
| G1 可复现源码 | **已通过** | 改动已审查并提交，版本、锁文件、变更日志和远程 `main` 一致 |
| G2 支持版本自动化 | **待远程验证** | Python 3.11–3.14 核心 CI 与可选依赖 CI 全绿 |
| G3 授权照片基线 | **阻断** | 至少30个分层案例，满足 `docs/evaluation.md` 门槛并保留报告 |
| G4 实体试钩基线 | **阻断** | 校准集与图解哈希不重叠的独立验证集均满足 `docs/physical-trials.md` 口径 |
| G5 发行包 | **本地通过** | wheel 内容、元数据、CLI 与包内数据检查通过 |
| G6 产品声明 | **Beta 合格** | UI、README、导出继续明确单图、模板、估算和试钩边界 |

在 G1–G4 全部通过前，不应创建正式发布标签。真实图片或实体样品不能由合成数据、
网络文章、图解预计用量或更多单元测试替代。

## 已具备的核心能力

- 照片、本地视觉、LLM 与手动输入三类入口；目标尺寸由用户明确提供。
- 主体分割、轮廓剖面、配色、可选姿态关键点和版本化模板结构图谱。
- Gauge 驱动的逐圈生成、六等分加减针、跨圈桥接与生成门禁。
- 材料清单、基础工时、装配说明、环形图、Markdown/PDF、历史与分享。
- 授权照片评测、实体试钩、外部证据隔离和保守候选校准工具。

## 仍然有效的产品边界

- 单张照片不能恢复可靠背面、深度或绝对尺度；结构位置与连接仍包含模板推断。
- 本地视觉对坐姿、遮挡、特写、多人和低对比背景仍可能降级。
- 克重和基础工时常数尚无本地实体试钩校准，必须显示为低置信度估算。
- 多角度照片融合、跨设备历史、完整国际化与GPU三维重建尚未交付。
- 精选网络证据只用于数量级检查，模式层固定禁止参与自动校准。

## 复核命令

```bash
uv sync --locked --extra dev
uv run --locked --extra dev ruff check .
uv run --locked --extra dev pytest -q --cov=app --cov-report=term-missing
uv lock --check
uv build --wheel --out-dir dist/
uv run crochet2pattern-trials external-report --curated
git status --short
```

每次改变支持版本、报告模式、测试基线或发布门禁时，先更新本文件，再更新 README 与
CHANGELOG；历史审计快照只增加醒目标记，不回写其中当时的事实数字。
