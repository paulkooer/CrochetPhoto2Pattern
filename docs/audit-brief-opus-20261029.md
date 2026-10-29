# Opus 5.5 全系统审核交待

整理日期：2026-10-29。本文供独立审核者直接执行，目标是核实整个系统的正确性、
数据可靠性、安全性和发布证据，提交可复现的问题清单及修复顺序。

## 1. 审核对象与工作方式

- 仓库：<https://github.com/paulkooer/CrochetPhoto2Pattern>
- 分支：`feat/stitch-notation-fidelity`
- **固定源码提交：`120659c78e60008aa61f652ecaada41ff89445ca`**。
- 源码入口：[固定版本目录](https://github.com/paulkooer/CrochetPhoto2Pattern/tree/120659c78e60008aa61f652ecaada41ff89445ca)。
- [PR #18](https://github.com/paulkooer/CrochetPhoto2Pattern/pull/18)：整理时为 OPEN，
  目标分支为 `main`，head 为上述提交；不能假定这些改动已进入默认分支。
- 软件版本：`0.2.0b2`，面向用户称 `0.2.0-beta.2`。

请审核该提交的**全部源码、测试、配置、依赖和文档**，最新提交的 diff 只是重点复核范围。
本文在后续文档提交中发布；检出固定源码时，本文可能尚不存在，这是正常的。
如果另行审核更新的业务代码，请明确列出新增 SHA 与范围，不要默默切换基线。

本轮交付审核报告。可以在独立临时目录安装依赖、构造最小案例和运行验证；
保留原始结果及日志。不要直接修改目标分支、提交修复、合并 PR、发布版本或发送公开评论。
发现安全问题按 [SECURITY.md](../SECURITY.md) 私下交付，避免公开未修复漏洞的利用细节。
如没有执行环境或无权访问某项资源，标注“静态审查”或“未执行”及具体原因。

## 2. 系统当前定位

这是本地照片分析与人工复核驱动的钩织设计工具，同时提供手动输入和二维网格入口。
主要流程为：照片与主体观测 → 人工确认比例、部件及蒙版 → 模板结构 → 按密度生成圈次
→ 代数/针法/连接校验 → 预览、编辑、工程保存与多格式导出。

技术栈为 Python、Streamlit、Pydantic v2、OpenCV、Pillow、NumPy，依赖由 `uv.lock`
锁定。支持 Python 3.11–3.14；本地默认 3.12，pose extra 只适用于 3.11–3.12。
当前版本没有云端 LLM 接口；可选姿态模块首次使用仍可能下载权重。
照片在 Streamlit 部署主机处理，“本地视觉”不等于所有部署都在用户设备上处理。

系统生成的是待核对、待试钩的设计草稿。针数自洽、可导出 DSL、图示连线正确，
均不能证明实物形状、线股路径、松紧、用线或工时已经验证。单张照片不提供可靠的
背面、深度和绝对尺度；目标厘米尺寸来自用户，部分结构来自模板。

## 3. 证据状态与已知缺口

### 已记录的验证

- 最近本地全量：**1883 passed、1 skipped，120.45s，覆盖率 94.10%**；
  Python 3.12.13。Ruff 全仓、mypy app/tests（164 文件）及差异检查通过。
  这是开发方提供的基线，请自行复现并记录跳过原因，测试数量随环境可能不同。
- 2026-10-29 只读查询 PR #18，确认 head 与固定 SHA 一致，8 项 CheckRun 均为 SUCCESS：
  `test (3.11)`、`test (3.12)`、`test (3.13)`、`test (3.14)`、`type-check`、`docker`、
  `optional-extras (pdf)`、`optional-extras (pose)`。
- 对应 [CI run 40820306117](https://github.com/paulkooer/CrochetPhoto2Pattern/actions/runs/40820306117)
  与 [extras run 40820306121](https://github.com/paulkooer/CrochetPhoto2Pattern/actions/runs/40820306121)。
  请打开日志核对实际解释器、依赖、跳过情况与 wheel 检查，不把旧 run 的结果套到新提交。
- `mypy` 对 app 启用 `check_untyped_defs`，tests 的该选项关闭；覆盖率与类型检查不能
  代替独立测试预期、浏览器交互或领域验证。

### 尚未完成或须独立核实

- **G3 授权真实照片基线未完成，G4 独立实体试钩基线未完成**；不能据此批准正式生产发布。
- 最近业务改动没有新增真实浏览器端到端验证、授权照片评测、实体试钩或外部仿真证据。
  AppTest、合成案例和历史截图各有范围，不能互相替代。
- 该提交上述检查列表中没有依赖安全审计结果。`security.yml` 有路径过滤；
  不能由其他 8 项通过推断 `pip-audit` 已针对本 SHA 运行。
- 推送时 GitHub 提示默认分支有 **43 项依赖漏洞告警（6 critical、24 high、13 moderate）**。
  这是默认分支告警快照，尚未逐项核对本分支。请结合
  [Dependabot](https://github.com/paulkooer/CrochetPhoto2Pattern/security/dependabot)、
  实际锁定版本、直接/间接依赖、可选环境及攻击前提核实；无权限时明确记录。
- 源码已推送到功能分支不等于已合并 `main`。发布门禁中的源码、完整自动化、
  依赖审计、授权数据、实体证据与产品声明应分别判断。

状态入口是 [system-status.zh-CN.md](system-status.zh-CN.md) 及英文对应文件。
其中逐轮“未提交/未推送”记录是当时快照，不能当成当前 GitHub 状态。
旧 `audit-brief.md` 和 `archive/` 也可能包含过时边界，遇到与源码冲突请指出并以证据判断。

## 4. 阅读顺序与代码地图

先读 `README.md` / `README_ZH.md`、`pyproject.toml`、`uv.lock`、
`docs/system-status.zh-CN.md`、`docs/project-format.md`、`docs/physical-trials.md`、
`docs/evaluation.md`、`docs/SOURCES.md`，再沿入口追踪真实调用和数据流。
文档是待核实的声明，不能作为实现正确的唯一证据。

| 审核面 | 主要源码入口 | 必须追踪的关系 |
|---|---|---|
| 应用与生成编排 | `app/main.py`、`app/cli.py`、`app/models/orchestrator.py` | 网页/CLI 是否经过同等生成与输出门禁，异常是否保留当前工作 |
| 输入与结构 | `app/schemas.py`、`app/models/structure_designer.py`、`app/models/parts.py` | 数值、名称、数量、实例、镜像和连接约束是否一致 |
| 本地视觉与人工复核 | `app/models/image_parser.py`、`local_vision.py`、`subject.py`、`geometry.py`、`pose.py`；`app/ui/photo_review.py`、`mask_editor.py`、`mask_canvas/` | 裁剪、EXIF、蒙版、主体/身体区域和复核后观测是否正确失效与复用 |
| 生成、材料与工时 | `app/models/crochet_params.py`、`profile_shaping.py`、`onepiece.py`、`gauge.py`、`materials.py`、`time_estimate.py`、`sizing.py` | 密度、数量、尺寸、颜色、总针数、材料和工时的共同口径 |
| 针法与图示 | `app/models/stitch_notation.py`、`instruction_checks.py`、`validator.py`、`ring_chart.py`、`stitch_connections.py`、`stitch_connection_diagram.py` | 解析、计数、操作顺序、半针范围、实际圈号与图示/导出一致性 |
| 跨部件工艺 | `app/models/stitch_attachments.py`、`skirt_edit.py`、`attachment_diagram.py`、`assembly.py`、`leg_join.py`、`leg_join_diagram.py` | 基底圈、预留圈、接入圈、实体配对与手动方案的语义边界 |
| 编辑与进度 | `app/ui/result_logic.py`、`pattern_editor.py`、`edit_history.py`、`progress_state.py`、`result_renderer.py`、`skirt_editor.py` | 预览、应用、重生成、撤销/重做、分页、状态清理及依赖失效 |
| 备份、分享与工程 | `app/utils/backup.py`、`project.py`、`share.py`、`history.py`；`app/ui/backup_import.py`、`project_save.py`、`sidebar.py` | 大小/结构校验、哈希绑定、个人备注与进度、旧版兼容及失败保护 |
| 网格模式 | `app/models/grid_pattern.py`、`app/ui/tab_grid.py` | 量化、抖动、C2C 方向、工程恢复、矩形修色、历史及下载同步 |
| 试钩与评测 | `app/trials.py`、`app/evaluation.py`、`app/models/trial_draft.py`、`app/utils/trial_bundle.py`、`trial_history.py`；`app/ui/trial_editor.py`、`trial_review.py` | 原图解快照/哈希、草稿与完成记录、ZIP 恢复、校准/独立留出及授权证据 |
| 导出与交付 | `app/utils/exporters.py`、`parade_export.py`、`pdf_export.py`、`output_files.py`；`app/ui/export_cache.py`；`Dockerfile`、`.github/workflows/` | 缓存输入、格式能力差异、部分导出标识、文件失败保护、构建与环境一致性 |

表中未重复写目录的相邻文件沿用该行前面的目录；这不是全部文件清单。
请同时抽查相关 tests、Schema、脚本、配置与说明是否覆盖真实调用边界。

## 5. 重点审核问题

### A. 领域正确性与工艺含义

核对跨圈针数代数与源针消耗，检查起针、加减针、混合顺序、重复组、FLO/BLO、
隐形减针 `inv-sc2tog`、非连续实际圈号及不支持工艺的处理。不要仅因针数相同就认为
两种工艺等价，也不要把生成器采用的六等分塑形先验当成所有钩法的有效性规则。
抽查参考夹具及其原始来源，必要时采用独立的小规模枚举或手算核对。

重点验证 `inv-sc2tog` 是否在规范化、编辑、备份、Markdown/PDF、符号条和 DSL 中
保留语义或明确说明限制。`stitch_connections` 只支持与前后圈针数一致的明确操作式，
每页 24 个操作；不应凭汇总针数虚构针位或把图示当作实物仿真。

检查接裙的实际基底圈、预留操作圈及接回半针引用，数量与实体配对变化是否合理影响
下游进度。独立并腿工具只计算“左右开口针数 + 2 × 锁针数”的特定方案，
记号和实际开口需用户核对，不能暗中把数字核对升级为实体接合验证。

### B. 状态一致性与工作保存

以完整用户路径验证：生成 → 修改 → 预览 → 应用 → 撤销/重做 → 保存 → 新会话恢复。
覆盖照片/手动标签页隔离、图案替换、部件增删改名/重排、实体数量变化、依赖链不同
记录顺序、进度分页、批量完成/重置和工程备注。核对隐藏控件清理、fragment 回调、
过期预览和缓存失效是否导致丢失、串档或恢复了错误工作。

对失败路径注入解析、校验、渲染、导出、历史快照损坏等异常，核对当前结果、输入和
撤销/重做分支是否按声明保留。正常的受影响进度清除应有解释，不能悄悄转移到别的圈。
区分应用内准备失败保护与断电/进程退出时的磁盘事务保证。

### C. 输入边界、安全与隐私

检查图片解码/像素预算、JSON 深度与非有限数值、重复键处理、解压前后配额、ZIP 成员、
分享载荷、SVG/HTML/Markdown、文件路径和 SQLite 访问。确认限制在昂贵分配或展开前
生效，失败不会留下部分安装的工程状态。将可控输入一直追踪到渲染、磁盘或其他边界。

历史默认关闭，`single_user` 只面向可信单用户部署，没有账号认证和所有权隔离。
审核实际数据库读写门禁、部署说明和模式切换；不要把未实现的多用户产品当成现成功能。
普通备份/分享不应意外包含个人备注和完成进度；工程与试钩包的保存范围应明确。

依赖漏洞请引用原始 advisory、锁定版本、受影响环境、利用前提和修复版本，区分
默认分支与本分支、核心与可选依赖、已确认受影响与待确认风险。

### D. 输出、性能与可维护性

比较同一图案在界面、环形图、逐针图、Markdown、PDF、JSON、分享、材料清单和
CrochetPARADE 中的口径。检查超出 DSL 子集的圈是否明确报告部分导出并保持有效前缀，
不能把“导出生成成功”当作外部解析器已接受或完整模型已验证。

对长图案、深层重复表达式、多实体、密集图像、少色抖动和大量导出测量时间/内存，
报告输入规模、机器/解释器、冷/热缓存及测量方法。关注解析/展开配额、分页是否实际
减少对象创建，以及失败/替换后会话状态能否释放。提出重构建议时说明实际重复逻辑、
耦合或维护成本及最小可行改动，不以文件较长本身判为缺陷。

### E. 测试、供应链与声明

抽查测试是否只复述实现，是否缺少独立预期、边界组合、真实 Streamlit 行为或故障路径。
检查 Python 矩阵、可选包缺失与原生库回退、wheel 内资源/入口、Docker、锁文件和工作流。
核对 README、历史审核交待、产品提示与当前实现的冲突；版本和格式兼容说明也须审核。
如果参考同类 GitHub 项目，应记录对方仓库、具体提交/文件及本项目适用条件，
将可借鉴方案与已证实缺陷分开，不为追赶功能清单引入无验证依赖。

## 6. 最近一次提交应特别复核的改动

`120659c` 相对前一提交 `6db95c7` 涉及 37 个文件。以下为风险定位线索，不限制全系统范围：

1. 手动并腿方案的严格 JSON 恢复、字段差异预览、SVG、部件选择稳定性及旧状态清理。
2. 逐针来源查看器的操作窗口、嵌套重复组跳过、FLO/BLO 和 JSON/SVG 范围/哈希。
3. 隐形减针工艺标记、实际圈号和导出缓存版本 7。
4. NumPy 颜色索引转原生整数；网格生成、恢复、修色和历史切换先准备预览及下载再提交状态。
5. 相似名称如“练习”和“练习_copy2”的实体进度消歧、分页/工程统一映射，
   以及批量按钮/跳转改为渲染前回调，保留其他部件进度与备注。

对应测试入口：`tests/test_leg_join.py`、`test_stitch_connections.py`、
`test_technique_fidelity.py`、`test_grid_state_safety.py`、`test_progress_key_isolation.py`、
`test_result_renderer.py`。已有回归不代表没有相邻反例；请用独立场景核对。
旧文件若已经记入错误勾选，应用无法恢复当时实物事实，不能要求自动猜测用户真实进度。

## 7. 可复现检查命令

在独立审查目录执行，先保留版本与环境信息。安装过程需要网络的部分如无法执行，
请明确记录，不要将环境错误记作业务缺陷。

```bash
git clone --branch feat/stitch-notation-fidelity --single-branch https://github.com/paulkooer/CrochetPhoto2Pattern.git
cd CrochetPhoto2Pattern
git checkout --detach 120659c78e60008aa61f652ecaada41ff89445ca
git rev-parse HEAD
uv --version
uv sync --locked --python 3.12 --extra dev
uv run --locked --extra dev python --version
uv run --locked --extra dev ruff check .
uv run --locked --extra dev mypy app tests
uv run --locked --extra dev pytest -q -ra --cov=app --cov-report=term-missing --cov-fail-under=80
uv lock --check
```

运行网页：`uv run --locked --extra dev streamlit run app/main.py`。
用自制或已授权图片验证浏览器流程，记录浏览器版本、操作步骤和脱敏截图。
`node scripts/check_mask_canvas.cjs` 是蒙版组件的可选浏览器冒烟，需要独立安装
Playwright 与可用 Chromium，不能将它的通过视为整个网页通过端到端检查。

按权限与环境补跑以下检查；不要把安装一个 extra 的结果套用于另一个环境：

```bash
uv build --wheel --out-dir dist/
uv sync --locked --extra dev --extra pdf
uv run --locked --extra dev --extra pdf pytest -q -ra
uv sync --locked --extra dev --extra pose
uv run --locked --extra dev --extra pose pytest -q -ra
uv run --locked --extra dev --extra pdf --extra pose --with pip-audit==2.10.1 pip-audit --local --progress-spinner off
docker build -t crochet-photo2pattern-audit .
```

pose 使用 Python 3.11–3.12；Linux 原生库要求及具体命令以
`.github/workflows/extras.yml` 为准。Python 3.11–3.14 矩阵须显式切换解释器，
不能因 `.python-version` 的 3.12 默认值而重复验证同一环境。
CLI 冒烟可使用 `uv run --locked --extra dev crochet2pattern --mock --out audit-demo.json`；
评测和试钩分别参考 `crochet2pattern-eval --help`、`crochet2pattern-trials --help` 及其文档。
不要将私有照片、试钩个人信息、临时数据库、日志或本机路径提交到仓库。

## 8. 报告要求

请用中文输出，先列会影响正常使用、数据完整性或安全的发现，再列其余建议。
每条发现必须包含：

1. 编号、标题、优先级 P0/P1/P2/P3 和确认程度（已复现 / 静态证据充分 / 待验证）。
2. 固定提交下的具体文件和行号；GitHub 证据链接使用完整 SHA，避免指向可变分支。
3. 输入、操作顺序、前置环境、最小复现命令或代码；注明是否实际执行。
4. 预期与实际行为、用户影响及发生条件，引用独立预期或领域来源。
5. 最小修复方向、兼容性影响、建议补充的回归测试与验收条件。

优先级用于实际影响：P0 为灾难性安全/数据事故，P1 为严重错误或关键流程阻断，
P2 为受限条件下的功能/一致性缺陷，P3 为低影响问题或维护改进。
严重程度与确认程度分别判断；尚未复现的猜想不能写成已确认事实。

最后给出：

- **已确认缺陷清单**，按优先级排序；没有发现时说明检查范围和剩余不确定性。
- **待验证风险与执行限制**，包括无权限的 GitHub 安全信息、未跑环境及缺失外部证据。
- **已知产品边界**，检查其是否准确声明和有效执行，不因已知就自动免审。
- **测试/检查记录**：命令、环境、结果、跳过原因和所查 CI run，不引用未经执行的结果。
- **范围覆盖表**：上述每个审核面已读哪些文件、跑过哪些路径、还有哪些未覆盖。
- **修复计划**：最多 10 个优先行动，说明目的、依赖、影响、验证方法及验收标准；
  不限制有证据的问题清单数量。
- **发布判断**：分别评价继续 Beta 使用、合并 PR 和正式发布，列出各自未满足的条件。
  G3/G4 的真实证据缺口不能由单元测试、外部文章或本次静态审核代替。

请独立审视已有结论，追踪真实输入到输出，优先提交能重现、能定位、能验收的发现。
