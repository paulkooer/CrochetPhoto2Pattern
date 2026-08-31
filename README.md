# 🧶 CrochetPhoto2Pattern

**简体中文** | [English](README_EN.md)

[![CI](https://github.com/paulkooer/CrochetPhoto2Pattern/actions/workflows/ci.yml/badge.svg)](https://github.com/paulkooer/CrochetPhoto2Pattern/actions/workflows/ci.yml) [![Version: 0.2.0 beta 1](https://img.shields.io/badge/version-0.2.0--beta.1-orange.svg)](CHANGELOG.md) [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> AI 驱动的 Amigurumi 立体人物钩织图解生成器：从一张照片自动生成完整钩织方法。

> **发布状态：Beta。** 自动化自检只能证明图解满足当前代数与塑形规则，
> 不能替代实际毛线小样和成品试钩；公开分享图解前请先验证尺寸、张力与装配。
> 当前验证结果与发布阻断项见 [系统状态与发布门禁](docs/system-status.md)。

## 项目定位与证据等级

本项目追求的是“可复核的图解生成”，不是把视觉模型输出直接包装成可发布成品。
当前证据分为三个互不替代的层级：

1. **结构正确性（已覆盖）**：逐圈针数、加减针拓扑、输入边界、导出与发行包由自动化测试检查。
2. **照片泛化（待建立）**：需要按场景分层、取得授权的真实照片集验证；合成图不能替代。
3. **实体可钩性（待建立）**：需要相互独立的校准/验证试钩，实测尺寸、用线和工时。

因此，生成结果适合作为设计草稿和试钩起点；在完成后两层证据前，不应把尺寸、
材料用量或成品可钩性描述为已验证结论。

## ✨ 功能

- 📷 上传照片（正面为主，侧面辅助照片规划中）
- 🧮 无 LLM 模式：本地人脸检测推算头身比例 + 轮廓识别（下摆展开自动加裙子），零 API 成本
- 🎯 GrabCut 主体分割：配色/轮廓/推荐色板只看主体像素，双色背景（墙+地板）不串色
- 🧍 姿态关键点实测分段（Python 3.11–3.12 可选 `pip install .[pose]`；Linux 还需 `libEGL.so.1`）：肩/髋/膝关键点实测部件配色区间；原生库缺失时安全回退比例先验
- 🎨 照片配色设计：纵向色带映射到逐圈毛线色，自动生成换线说明；AI 模式识别发色/上衣/下装直达部件配色；CIEDE2000 感知色差匹配毛线色表
- 🖩 网格缩放算法可选：照片平滑（LANCZOS）/ 像素画锐利（NEAREST）
- 🤖 AI 视觉解析人物特征（支持 OpenAI GPT-4o / Anthropic Claude）
- 🧊 版本化基础结构骨架（非完整 3D 重建）：显式记录部件位置、旋转、左右镜像实例与连接锚点，并标注模板推断置信度
- 🧶 生成完整钩织参数（针数、加减针、逐圈步骤）
- 📐 塑形上限随小样密度推导：连续几何变化率量化为六等分可执行针法，经典密度每圈最多 ±6，DK/细密度可到 ±12
- 🧮 双臂/双腿/双耳按两个实体计量：总针数、材料、工时、导出和逐圈进度不会漏算第二件
- 📝 结构化输出（JSON + 可视化表格）
- ✏️ 支持局部修正和重新生成
- 🧩 高级结构修正：编辑并严格校验部件尺寸、数量、位姿和连接图，无需再次调用 AI 即可重生成针法与装配说明
- 🟦 2D 像素网格图案（生成前比例裁剪、单格/矩形修色、5 步撤销重做、可编辑工程 JSON、完整 Markdown、Tapestry / C2C / 十字绣）
- ✅ 逐圈钩织进度追踪
- 🧾 逐色材料清单（每色克重+米数+色样+品牌参考色号，跨部件合并）
- 🔗 分享链接：小图解可压缩进 URL 直接打开（无需服务器）
- 🩺 图解自检：针数代数逐圈校验，矛盾直接标出
- ⭕ 环形圈数图：部件顶视图，内圈起针外圈收尾，配色一目了然
- 💾 完整结果备份/导入（JSON）+ 本机图解历史（SQLite，侧栏随时载回）+ PDF 打印导出（可选 `pip install .[pdf]`）
- 🖼️ EXIF 方向自动修正（手机竖拍照片直出正确比例）

## 🛠 技术栈

- Python 3.11+
- Streamlit（交互 UI）
- OpenAI / Anthropic API（Vision + Reasoning）
- Pydantic v2（数据验证）

## 🚀 快速开始

### 安装

```bash
cd CrochetPhoto2Pattern
uv sync --locked              # 推荐：严格使用仓库锁定依赖
# 或：python -m pip install -e .
```

### 配置

复制 `.env.example` 为 `.env`，填入你的 API Key：

```bash
cp .env.example .env
# 编辑 .env 填入 OPENAI_API_KEY 或 ANTHROPIC_API_KEY
```

Key 优先级：**侧栏输入框 > `.env`**。注意：清空输入框并不会停用 Key——
此时回退使用 `.env` 中配置的 Key（仍会真实计费）；只有输入框与 `.env`
都不配置时，照片 Tab 才进入「本地视觉估算 / Mock」的免费模式。

**中转站（第三方 API 代理）**：个人使用时可在侧栏同时填写“自己的 API
Key + 对应 Base URL”（如 `https://your-relay.example/v1`）；Base URL 不能借用
服务器 `.env` 中的 Key。部署方可在 `.env` 成对配置 `OPENAI_API_KEY` +
`OPENAI_BASE_URL` 或 `ANTHROPIC_API_KEY` + `ANTHROPIC_BASE_URL`。两组来源不会
交叉混用，避免共享部署把服务器密钥发送到用户控制的地址。模型名也可用环境
变量覆盖：
`ANTHROPIC_VISION_MODEL`（默认 claude-sonnet-5）、`OPENAI_VISION_MODEL`（默认 gpt-4o）。

> 💡 不设置 API Key 也可以运行：照片 Tab 可选「本地视觉估算」（OpenCV
> 人脸检测推算相对头身比例）或 Mock 演示；照片没有绝对尺度，厘米尺寸始终
> 来自你在照片 Tab 选择的目标成品高度。手动/网格 Tab 本就无需 Key。
> ⚠️ 多人共享部署应禁用不需要的出站网络；应用会拒绝 HTTP、localhost 和
> 显式私网 Base URL，但 DNS 重绑定等边界仍须由网络层策略兜底。

### 数据与隐私

- 本地视觉、手动输入和网格模式不把照片发送给 LLM 服务。
- 选择 OpenAI / Anthropic 视觉模式时，所选照片会发送到对应服务商；配置自定义
  Base URL 时则发送到该第三方地址。请只使用你有权处理的图片并核对服务条款。
- 图解历史默认保存在运行应用的本机 SQLite 数据库中；分享链接会把压缩后的图解
  数据放入 URL，请勿用于敏感或不希望被接收方保存的内容。
- `.env`、授权评测照片、评测输出和实体试钩记录默认被 Git 忽略。提交前仍应主动
  检查是否含 API Key、人物照片或个人信息。

### 运行

```bash
uv run streamlit run app/main.py
# pip 安装方式可直接运行：streamlit run app/main.py
```

### 命令行（无头模式）

```bash
uv run crochet2pattern --image photo.jpg --gauge dk --out pattern.json --md pattern.md
uv run crochet2pattern --head 9 --height 18 --parts 头部,身体 --sphere-mode egg --out p.json
uv run crochet2pattern --mock --out demo.json                       # 固定演示数据
uv run crochet2pattern --batch-dir photos/ --out-dir patterns/      # 目录批量生成
```

AI 模式读取环境变量中的 API Key（支持 `OPENAI_BASE_URL` / `ANTHROPIC_BASE_URL`
中转站）；无 Key 自动走本地视觉估算。所有输出经过图解自检门禁（代数矛盾
或超过当前密度塑形上限时返回码 2）。

### Docker（可选）

```bash
docker build -t crochet-photo2pattern .
docker run -p 8501:8501 -e ANTHROPIC_API_KEY=sk-ant-... crochet-photo2pattern
```

### 测试

```bash
uv sync --locked --extra dev
uv run --locked --extra dev pytest tests/ -v
```

### 授权真实照片评测

真实评测强制记录数据权利基础、用途批准、SHA-256 和场景标签，并且只运行本地
视觉路径，不向 LLM 服务发送照片：

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
│   │   ├── image_parser.py  # Vision API 图像解析
│   │   ├── geometry.py      # 单图观测 IR + StructureGeometry v2 部件图谱
│   │   ├── sizing.py        # 照片相对比例 → 用户目标尺寸
│   │   ├── structure_designer.py  # 版本化模板结构（位姿/镜像/连接）
│   │   ├── crochet_params.py      # 钩织参数生成
│   │   ├── grid_pattern.py        # 2D 像素网格图案
│   │   ├── colors.py              # 共享毛线色表 + Lab 感知色距
│   │   └── orchestrator.py        # 流水线编排
│   ├── ui/
│   │   ├── sidebar.py             # API Key 配置
│   │   ├── tab_photo.py           # 照片识别 Tab
│   │   ├── tab_manual.py          # 手动输入 Tab
│   │   ├── tab_grid.py            # 2D 网格 Tab
│   │   └── result_renderer.py     # 结果渲染（进度/修正/导出）
│   ├── utils/
│   │   ├── exporters.py           # Markdown 导出
│   │   └── images.py              # 上传图片安全加载（容错/大小限制）
│   └── prompts/             # LLM 提示词模板
├── tests/                   # 自动化测试
├── docs/                    # 文档
└── pyproject.toml           # 项目配置（依赖单一来源）
```

## 📄 License

[MIT](LICENSE)。参与开发前请阅读 [贡献指南](CONTRIBUTING.md)；安全问题请按
[安全策略](SECURITY.md) 私下报告。
