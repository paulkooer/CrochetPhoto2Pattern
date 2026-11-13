# 系统状态与发布门禁

**简体中文** | [English](system-status.md) | [文档索引 / Documentation index](README.md)

> 状态快照：2026-11-13。代码行为以当前源码、`pyproject.toml`、锁文件和
> 可复现验证结果为准；`audit-brief*.md`、`handoff-review.md` 与
> `optimization-brief.md` 是对应审查轮次的历史快照，不用于判断当前测试数量或发布状态。

## 当前结论

CrochetPhoto2Pattern 当前是 **0.2.0-beta.2 工程候选版**：图解代数、输入门禁、导出和
发行包已有较完整的自动化保障，但尚未完成授权真实照片基线与实体试钩基线，因此不得
描述为“已验证尺寸、材料、工时或成品可钩性”的生产版本。

## 最近一次可复现验证

已保存的 G1/G2 发布证据见 [`docs/release-evidence.json`](release-evidence.json)。
它是该文件 `commit` 字段所指提交的历史收据，不代表当前 `main` 状态；
`checks_completed_at` 和 `run_refs` 记录所采用的远端检查时间与链接。后续提交不继承通过结论。

仅在选定发布候选并完成检查后，按[发布流程](release-process.zh-CN.md)生成新收据。
日常合并查看各自的 CI，不刷新发布证据，也不把证据哈希抄到本页。
生成器只接受每项检查最新且成功完成的运行；使用另一个提交的 pip-audit 时，必须与候选树完全一致。
G3 与 G4 仍是阻断。

以下命令只读取证据并核对指定提交，不访问网络或改写文件：

```bash
python scripts/bind_release_evidence.py --status --commit HEAD
```

退出码 1 表示该提交未被证据覆盖；退出码 0 只表示绑定匹配，不代表全部发布门禁通过。


变更历史见 [CHANGELOG](../CHANGELOG.md)；逐轮验证的[旧状态快照](https://github.com/paulkooer/CrochetPhoto2Pattern/blob/d12cda6e6dd02cee31c032a8341a8c58d03cd98b/docs/system-status.zh-CN.md)保留在 Git 中，不再追加到当前状态页。

## 已独立验收的合并基线

2026-10-30 软件一致性问题最终独立验收：固定提交 `55280fb485d9182f264402c52cbc171c957c4c51`
的原八项问题及两项 P2、一项 P3 后续补修均为 **PASS，可关闭**。维护者提供的 GPT Pro
独立报告记录：Python 3.12.14、锁定 dev+pdf，全量 **2076 passed、2 skipped，89.35s**；
Ruff、mypy（175 个源文件，按仓库配置）、差异检查通过，审核工作树干净。
跳过项为授权照片目录缺失及验收环境未满足 MediaPipe 的 EGL/GLESv2 条件。
开发方在同一提交的本地结果为 2076 passed、2 skipped，57.25s（Python 3.12.13，
MediaPipe 未安装），与独立运行分开记录。该轮导出缓存为 **10**，备份顶层版本仍为 1。
验收方查询该 SHA 时没有公开远端 CI 结果；合并门禁以修复 PR 当前头提交的 Checks 为准。
该验收轮次尚未执行真实浏览器；后续合成浏览器覆盖见上节。授权照片、实体试钩及
浏览器其他平台与真实照片场景仍独立待办，Beta 定位及 G3/G4 不变。
验收边界见[闭项交接](archive/audit-fix-review-20261030.md)。

## 发布门禁

| 门禁 | 当前状态 | 通过条件 |
|---|---|---|
| G1 可复现源码 | **须核对候选绑定** | 确切提交和树只记录在 [`release-evidence.json`](release-evidence.json)。新候选按[发布流程](release-process.zh-CN.md)生成证据；旧收据不覆盖后续提交，也不扩展既有独立验收范围 |
| G2 支持版本自动化 | **见绑定候选的证据** | 候选的最新必需检查须全部成功；另一个提交的 pip-audit 必须同树。Python 版本、结论和运行链接以证据文件为准，必需检查名见 `.github/required-checks.json` |
| G3 授权照片基线 | **阻断** | 至少30个分层 schema-v2 案例，逐图具备版权/被摄者证据，并满足 `docs/evaluation.md` 策略 v3 全部门槛。无交互自动路径可交付未经校准的轮廓候选；合成图能超过固定模板不代表真实照片达标 |
| G4 实体试钩基线 | **阻断** | 校准集与图解哈希不重叠的独立验证集均满足 `docs/physical-trials.md` 口径 |
| G5 发行包 | **本地通过** | wheel 内容、元数据、CLI 与包内数据检查通过 |
| G6 产品声明 | **Beta 合格** | UI、README、导出继续明确单图、模板、估算和试钩边界 |

在 G1–G4 全部通过前，不应创建正式发布标签。真实图片或实体样品不能由合成数据、
网络文章、图解预计用量或更多单元测试替代。

仓库目前没有语料摄取、模型权重训练或微调流水线；公开图解只提供经过窄化提取的
针数/圈结构事实，用于确定性参考测试。这不使未经授权的网络图片具备 G3 资格。

## 已具备的核心能力

- 本地照片分析、人工确认、手动输入与二维网格入口；目标尺寸由用户明确提供。
- 主体分割、轮廓剖面、配色、可选姿态关键点和版本化模板结构图谱。
- Gauge 驱动的逐圈生成、六等分加减针、跨圈桥接与生成门禁。
- 材料清单、基础工时、装配说明、环形图、Markdown/PDF、历史与分享。
- 授权照片评测、网页实体试钩记录及恢复、外部证据隔离和保守候选校准工具。

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
# 声明的 Streamlit 下限必须真的能安装、能运行（CI：streamlit-floor 作业）
uv venv --python 3.12 /tmp/floor && uv pip install --python /tmp/floor/bin/python "streamlit==1.66.1" -e ".[dev]"
/tmp/floor/bin/python -m pytest -q tests/test_app_smoke.py tests/test_dependency_floor.py
uv run crochet2pattern-trials external-report --curated
git status --short
```

本页只维护当前结论、证据绑定和门禁；常规变更记入 CHANGELOG。发布证据、支持范围或
门禁发生变化时更新本页与相关文档，历史审计快照保留当时的事实。
