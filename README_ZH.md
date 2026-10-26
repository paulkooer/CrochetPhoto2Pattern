# 🧶 CrochetPhoto2Pattern

**简体中文** | [English](README.md)

[![CI](https://github.com/paulkooer/CrochetPhoto2Pattern/actions/workflows/ci.yml/badge.svg)](https://github.com/paulkooer/CrochetPhoto2Pattern/actions/workflows/ci.yml) [![Version: 0.2.0 beta 2](https://img.shields.io/badge/version-0.2.0--beta.2-orange.svg)](CHANGELOG.md) [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> 本地视觉与规则驱动的 Amigurumi 钩织图解生成器：照片分析、人工确认、逐圈生成。

> **发布状态：Beta。** 自动化自检只能证明图解满足当前代数与塑形规则，
> 不能替代实际毛线小样和成品试钩；公开分享图解前请先验证尺寸、张力与装配。
> 当前验证结果与发布阻断项见 [系统状态与发布门禁](docs/system-status.zh-CN.md)。

照片默认使用本地视觉＋人工确认，不再调用云端 LLM；接口、密钥设置和 SDK 依赖已移除。`--local` 保留兼容旧命令，旧环境中的 API Key 不影响生成。

从旧版迁移：删除库调用中的 `openai_key` / `anthropic_key` / Base URL 参数，将 `vision_mode="ai"` 改为 `"local"`。无需删除旧图解，历史来源与用量仍能导入。更新依赖环境请执行 `uv sync --locked`。

## 项目定位与证据等级

本项目追求的是“可复核的图解生成”，不是把视觉模型输出直接包装成可发布成品。
当前证据分为三个互不替代的层级：

1. **结构正确性（已覆盖）**：逐圈针数、加减针拓扑、输入边界、导出与发行包由自动化测试检查。
2. **照片泛化（待建立）**：需要按场景分层、取得授权的真实照片集验证；合成图不能替代。
3. **实体可钩性（待建立）**：需要相互独立的校准/验证试钩，实测尺寸、用线和工时。

因此，生成结果适合作为设计草稿和试钩起点；在完成后两层证据前，不应把尺寸、
材料用量或成品可钩性描述为已验证结论。

**为什么"可执行正确性"是本项目的关键：** 钩织视觉-语言模型研究
（[CrochetBench, ACL 2026](https://arxiv.org/abs/2511.09483)）实测表明：当评估从
"表面相似度"推进到"可执行正确性"时，模型性能骤降——模型擅长描述，却很难产出
可运行的编织指令。因此本项目把图解当作**可校验的工件**：每份生成结果都必须先
通过代数自检门禁才能下载；评测协议同时报告第二层指标 `parade_export_rate`——
结果能否翻译为 [CrochetPARADE](https://crochetparade.org) 的图解语言（在其本地
运行的网页应用中获得独立结构分析、3D 渲染与针目张力检查；粘贴导出的 DSL 即可，
结果页与 CLI `--parade` 均可导出）。这不能替代实际试钩验证。

## ✨ 功能

- 未知部件保留供人工复核；确认页需移除误识别项或改选受支持部件，自动生成不会将其替换为小球。已有自定义结构备份仍可导入。
- 📷 照片先裁剪，再识别与确认：预览主体轮廓和头部框，调整头身比例与部件后生成；确认后本地生成
- 可手动限定身体轮廓的蓝框，排除框外手臂及背景；原图轮廓与身体框观测分别保存，备份及尺寸调整保留。框选不补回漏分割像素，也不提供实际厘米尺寸；身体配色只同步上下区间。
- 漏分割时勾选「补选／擦除主体区域」，直接在照片上涂抹；松开后更新轮廓与配色，支持撤销最近 20 笔和恢复自动分割。修正掩码随备份保存，仍需确认部件；被遮挡或拍摄裁掉的部分无法凭空恢复。
- ↶ 部件尺寸／数量／位置／连接表单和逐圈表格；会话内撤销／重做（最多 12 份、合计 8 MB）及修改前后对比
- ⏱ 分阶段耗时、回退原因与运行预算；导入旧版图解时保留历史用量记录
- 🧮 无 LLM 模式：头部候选框检查与轮廓分析，零 API 成本；部件来自待确认模板，下方变宽仅提示可能有裙摆
- 🎯 GrabCut 主体分割：配色、轮廓与推荐色板共用同次主体观测，固定初始化种子；
  分割失败时回退启发式，减少重复计算与重复运行漂移
- 🧍 姿态关键点实测分段（Python 3.11–3.12 可选 `pip install .[pose]`；Linux 还需 EGL/GLESv2）：肩/髋/膝关键点实测部件配色区间；原生库缺失时安全回退比例先验
- 🎨 照片配色设计：纵向色带映射到逐圈毛线色，自动生成换线说明；CIEDE2000 感知色差匹配毛线色表
- 🖩 网格缩放算法可选：照片平滑（LANCZOS）/ 像素画锐利（NEAREST）+ Floyd–Steinberg 抖动可选
- 🧶 CrochetPARADE 导出：图解一键翻译为其 DSL（结果页 / CLI `--parade`），
  粘贴到其本地网页应用即得独立 3D 渲染与针目张力分析（评测协议报告
  `parade_export_rate` 第二层"可执行正确性"指标）
- 明确操作式的针法顺序贯通 Markdown、逐圈符号条与 CrochetPARADE：支持错位、混合加减针和嵌套重复组；仅有总针数的导出会标明针位推断圈次，特殊工艺及文字错位提示仍需复核。
- 支持 `BLO((2X,V)×6)`、`4sc-FLO` 等整组或局部挑针写法，前／后半针范围贯通校验与导出；符号条以 F/B 标记针位，范围不清时停止该部件的 DSL 导出并提示核对。
- 连续六针加针圈直接写出组尾/组中的针位，例如 `(X,V,X)×6`；修改前一圈时同步更新相邻自动说明，保留收口与留线步骤。
- 🧊 版本化基础结构骨架（非完整 3D 重建）：显式记录部件位置、旋转、左右镜像实例与连接锚点，并标注模板推断来源；启发式未经校准，不展示置信度百分比
- 🧶 生成完整钩织参数（针数、加减针、逐圈步骤）
- 📐 塑形上限随小样密度推导：连续几何变化率量化为六等分可执行针法，经典密度每圈最多 ±6，DK/细密度可到 ±12
- 🧮 双臂/双腿/双耳按两个实体计量：总针数、材料、工时、导出和逐圈进度不会漏算第二件
- 📝 结构化输出（JSON + 可视化表格）
- ✏️ 支持局部修正和重新生成
- 🧩 高级结构修正：编辑并严格校验部件尺寸、数量、位姿和连接图，可在本地重生成针法与装配说明
- 📏 调整成品尺寸时保留已编辑的结构；显式直径、杯深和颜色参与生成。图解密度编辑同步用于材料、导出、预览和后续重生成。
- 🟦 2D 像素网格图案（生成前比例裁剪、单格/矩形修色、5 步撤销重做、可编辑工程 JSON、完整 Markdown、Tapestry / C2C / 十字绣）
- ✅ 逐圈钩织进度追踪
- 🧾 唯一逐色采购清单与独立小计（不重复相加）；可输入每团克重／米数及实测试片克重，默认预留 10% 损耗。线标与试片统一适用于所有颜色
- 🔗 分享链接：小图解可压缩进 URL 直接打开（无需服务器）
- 🩺 图解自检：针数代数与 X/V/A 等操作式逐圈核对；逐圈编辑区可用针法计算器查看消耗、产出及加减针数
- ⭕ 环形圈数图：部件顶视图，内圈起针外圈收尾，配色一目了然
- 💾 完整结果备份/导入（JSON）+ 部署主机图解历史（SQLite，默认关闭，侧栏随时载回）+ PDF 打印导出（可选 `pip install .[pdf]`）
- 🖼️ EXIF 方向自动修正（手机竖拍照片直出正确比例）

## 🛠 技术栈

- Python 3.11+
- Streamlit（交互 UI）
- Pydantic v2（数据验证）

## 🚀 快速开始

### 安装

```bash
cd CrochetPhoto2Pattern
uv sync --locked              # 推荐：严格使用仓库锁定依赖
# 或：python -m pip install -e .
```

### 配置

无需配置 API Key 或模型服务。需要可信单用户历史时，可复制 `.env.example` 为 `.env` 并配置历史选项。
旧版 provider 环境变量不再使用。照片仅估算相对比例，厘米尺寸由用户指定。
可选姿态功能首次使用可能下载模型权重；可用 `CROCHET_POSE_MODEL` 指向本地模型文件。

### 数据与隐私

- 上传照片会传到运行 Streamlit 的主机；仅在自己电脑部署时才是本机处理。“本地估算”表示不调用模型服务商。

- 本地视觉、手动输入和网格模式不把照片发送给 LLM 服务。
- 请只使用你有权处理的图片。
- 图解历史默认关闭；仅可信单用户部署可设置 `CROCHET_HISTORY_MODE=single_user`，
  使用服务器本机 SQLite。多人/公开部署必须保持 `disabled`：历史没有用户认证或
  所有权隔离。旧数据库不会被删除。分享链接把压缩图解放入 URL，请勿用于敏感内容。
- `.env`、授权评测照片、评测输出和实体试钩记录默认被 Git 忽略。提交前仍应主动
  检查是否含 API Key、人物照片或个人信息。
- 网络可见不等于授权；免责声明、致谢或“通知即删”都不能替代许可。第三方照片与
  资料须遵守[第三方内容政策](THIRD_PARTY_CONTENT.md)和[通知下架流程](NOTICE_AND_TAKEDOWN.md)。

### 运行

```bash
uv run streamlit run app/main.py
# pip 安装方式可直接运行：streamlit run app/main.py
```

### 保存与恢复图解

在结果页点击「💾 备份完整结果」保存 JSON。下次打开系统，展开侧栏的
「📂 打开备份图解」，上传该文件后点击「导入并打开图解」，即可在
「照片分析（本地）」页继续查看和编辑，无需先生成图解或开启历史。
上传文件上限 20 MiB；也可切换到「粘贴 JSON」（上限 2 MiB），使用 UTF-8 编码。
请使用完整备份，单独下载的参数 JSON 不含恢复所需信息。

导入先核对备份格式、针数和明确操作式；失败时保留当前结果，成功后替换照片页图解。
手动输入页的结果不受侧栏导入影响；各结果页的「导入结果备份」可替换所在页图解。
要保留实际钩织进度，展开结果页「🧺 我的钩织工程」，填写个人备注，点击
「💾 保存工程（含进度）」并在弹窗中下载工程 JSON。工程保存每份部件分别完成的
圈次、备注及图解版本；下次从同一个侧栏入口上传即可继续。每次继续钩织后请重新保存，
下载的是点击保存时的快照；修改图解后会提示清除受影响的进度，撤销可恢复。
普通图解备份和分享链接不包含个人备注与进度；撤销历史仍只保留在当前会话。
长图解按部件分页显示，可点击「前往下一未完成圈」返回所选部件第一个尚未勾选的圈次，
包括第二份及后续实体。跳转只改变查看位置，不修改进度。若图解包含多级预留针目连接，
修改基底会逐层清除依赖部件的进度，不受连接记录顺序影响。

### 挑针接裙

侧栏「塑形选项」选择「挑后半针（钩在身体上）」后，生成器会明确指定身体的基底圈、
其下一圈的 FLO 预留步骤，以及裙子第 1 圈使用的 BLO 针目范围。身体与裙子数量须相同；
头身一体时使用合并后的圈号，调整尺寸后重新计算，Markdown/PDF 使用同一份接合记录。
例如基底为身体第 11 圈的 36 针，则身体第 12 圈只挑第 11 圈前半针；裙子接入第 11 圈
留下的 36 个后半针。具体圈号以生成结果为准，腰位属于模板安排，仍需试钩确认。
旧接裙备份可继续导入，但缺少精确接合记录时提示复核。当前 CrochetPARADE 子集尚不表达
跨部件接回预留针目的操作，会明确跳过接入部件并报告部分导出。

### 命令行（无头模式）

```bash
uv run crochet2pattern --image photo.jpg --gauge dk --out pattern.json --md pattern.md
uv run crochet2pattern --head 9 --height 18 --parts 头部,身体 --sphere-mode egg --out p.json
uv run crochet2pattern --mock --out demo.json                       # 固定演示数据
uv run crochet2pattern --batch-dir photos/ --out-dir patterns/      # 目录批量生成
```

照片模式始终使用本地算法，旧版 Key 不会触发云端调用。所有输出经过图解自检门禁（代数矛盾
或超过当前密度塑形上限时返回码 2）。

### Docker（可选）

```bash
docker build -t crochet-photo2pattern .
docker run -p 8501:8501 crochet-photo2pattern
```

### 测试

```bash
uv sync --locked --extra dev
uv run --locked --extra dev pytest tests/ -v
```

### 授权真实照片评测

真实评测强制逐图记录版权依据、被摄者同意、用途批准、SHA-256 和场景标签，并且
只运行本地视觉路径，不向 LLM 服务发送照片：

```bash
uv run crochet2pattern-eval --dataset eval_data/release-01 \
  --out eval_outputs/release-01.json
```

数据协议、指标和状态码见 [docs/evaluation.md](docs/evaluation.md)。真实图片及评测
报告默认被 Git 忽略；自动化结果仍不能替代实体试钩。

### 实体试钩闭环

可从精确图解 JSON 创建带 SHA-256 的试钩草稿，记录实际密度、尺寸、毛线和
操作时间，再生成不会自动改写生产常数的校准报告：

```bash
uv run crochet2pattern-trials init --pattern pattern.json \
  --trial-id classic-001 --maker-id maker-a \
  --cohort calibration \
  --out trial_data/classic-001.trial.json
uv run crochet2pattern-trials analyze --records trial_data \
  --out trial_outputs/baseline.json
```

可选附加带来源、许可边界和验证层级的网络试钩上下文；外部数据在模式层固定为
`calibration_allowed=false`，不会参与生产常数候选：

```bash
uv run crochet2pattern-trials external-report \
  --curated \
  --out trial_outputs/external-context.json
```

记录口径、样本门槛和校准流程见
[docs/physical-trials.md](docs/physical-trials.md)。

## 📐 处理流程

```
照片上传 → 几何/语义观测 → 用户目标尺寸 → 部件结构 → 钩织参数 → 用户修正
```

详见 [docs/flow.md](docs/flow.md)

## 📁 项目结构

```
CrochetPhoto2Pattern/
├── app/
│   ├── main.py              # Streamlit 入口（薄壳：配置 + Tab 分发）
│   ├── evaluation.py        # 授权真实照片评测、聚合指标与 JSON 报告
│   ├── trials.py            # 实体试钩记录、偏差分析与保守校准建议
│   ├── schemas.py           # Pydantic 数据模型
│   ├── models/
│   │   ├── image_parser.py  # 本地图像分析
│   │   ├── geometry.py      # 单图观测 IR + StructureGeometry v2 部件图谱
│   │   ├── sizing.py        # 照片相对比例 → 用户目标尺寸
│   │   ├── structure_designer.py  # 版本化模板结构（位姿/镜像/连接）
│   │   ├── crochet_params.py      # 钩织参数生成
│   │   ├── grid_pattern.py        # 2D 像素网格图案
│   │   ├── colors.py              # 共享毛线色表 + Lab 感知色距
│   │   └── orchestrator.py        # 流水线编排
│   ├── ui/
│   │   ├── sidebar.py             # 密度与塑形配置
│   │   ├── tab_photo.py           # 照片识别 Tab
│   │   ├── tab_manual.py          # 手动输入 Tab
│   │   ├── tab_grid.py            # 2D 网格 Tab
│   │   └── result_renderer.py     # 结果渲染（进度/修正/导出）
│   ├── utils/
│   │   ├── exporters.py           # Markdown 导出
│   │   └── images.py              # 上传图片安全加载（容错/大小限制）
├── tests/                   # 自动化测试
├── docs/                    # 文档
└── pyproject.toml           # 项目配置（依赖单一来源）
```

## 📄 License

[MIT](LICENSE)。参与开发前请阅读 [贡献指南](CONTRIBUTING.md)；安全问题请按
[安全策略](SECURITY.md) 私下报告。

## 照片确认与运行预算

照片流程为“识别 → 人工确认 → 生成”。修改裁剪或解析模式会清除旧识别草稿，
修改目标高度、头部范围或部件复用本地观测。单次默认运行预算 180 秒，界面可设
15–600 秒，人工确认停留时间不计入。预算在阶段边界检查，
不能中途终止本地图像处理，因此不是严格的墙钟超时保证。

每次导出另有 60 秒协作式预算，导出耗时仅留在当前会话；照片阶段诊断随备份保存。
结构重生成会替换手工调整过的逐圈针数，撤销可恢复上一版本。编辑失败保留当前图解。
