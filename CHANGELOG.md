# Changelog

**简体中文** | [English](CHANGELOG_EN.md)

本项目遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 的组织方式，
版本号采用 [Semantic Versioning](https://semver.org/lang/zh-CN/)。Beta 阶段的备份、
结构和可编辑工程格式仍可能升级；发生不兼容变化时必须记录迁移方式。

## Unreleased

### Added

- 版本化真实照片评测协议：授权/保留策略、SHA-256、场景标签、聚合质量门禁与 JSON 报告。
- `crochet2pattern-eval` 本地评测命令；图片不会发送到 LLM 服务。
- `crochet2pattern-trials` 实体试钩闭环：图解哈希、实测密度/尺寸/用线/工时记录与保守校准建议。
- 精选网络试钩证据随 wheel 发布；`external-report --curated` 可直接生成带来源边界的上下文报告。
- 试钩记录新增向后兼容的 `calibration`/`validation` 分组；候选常数只读取校准集，留出集要求图解哈希完全独立并单独报告偏差。
- 公开仓库贡献指南、安全策略、行为准则、结构化 Issue 表单和 Pull Request 检查清单。
- 完整英文项目入口与当前规范文档；Issue / Pull Request 模板改为中英双语，
  历史审计快照通过双语索引与当前权威状态明确区分。

### Changed

- GitHub 与发行包默认入口改为英文；完整中文说明保留在 `README_ZH.md` 与
  `docs/system-status.zh-CN.md`，旧英文专用链接继续提供兼容跳转。
- README 新增结构正确性、照片泛化与实体可钩性三层证据说明，以及照片、第三方
  视觉服务、分享链接和本地历史的数据隐私边界。
- 仓库密钥检查覆盖准备提交的未跟踪文件，并新增 GitHub / AWS / 私钥常见形态。
- 核心测试不再隐式依赖 `[pdf]` 可选包；PDF extras 仍实际运行 PDF 用例。Streamlit
  AppTest 统一使用仓库绝对入口，并为双结果冷启动设置合理超时。
- 新增依赖变更触发和每周定时的 `pip-audit` 工作流；先按 `uv.lock` 同步环境，
  再审计实际安装版本，审计工具不会改写项目锁文件。
- CI 通过 `UV_PYTHON` 强制使用矩阵声明的解释器，避免 `.python-version` 把
  3.11–3.14 四个 job 静默收敛为 3.12。
- GitHub 官方 Actions 升级到 Node 24 运行时的 `checkout@v7` 与
  `setup-python@v7`，消除 Node 20 弃用告警。
- MediaPipe pose 升级到 1.0.1 并明确支持 Python 3.11–3.12；移除旧版
  `protobuf<5` 高危约束，所有核心环境统一使用 Protobuf 6+。Python 3.13+
  同时
  使用提供新解释器 wheel 的 NumPy 2.x，避免回退编译 NumPy 1.26 源码。
- 依赖安全工作流同时安装并审计核心、PDF 与 pose extras。
- Linux pose 在构造 MediaPipe 对象前检查 EGL/GLESv2，缺失时安全回退；
  extras CI 安装原生运行库并执行真实 `mp.Image` 桥接冒烟测试。

### Planned

- 采集授权真实图片并执行首份评测报告，建立实体试钩基线。
- 拆分参数生成、结果渲染、网格图案和视觉服务商适配巨型模块。
- G3 授权照片与 G4 独立实体试钩门禁通过后发布首个 Beta 标签。

## 0.2.0-beta.1 - 2026-08-30

### Added

- 服务商无关的单图几何观测、用户目标尺寸变换与 StructureGeometry v2。
- 部件实例、镜像数量、连接锚点和装配计划；材料、工时、进度按实体数量计算。
- Gauge 驱动的动态塑形上限，以及逐圈代数、六等分拓扑和 V/A 可执行性校验。
- 照片剖面塑形、理想球/蛋形头、头身一体和高级结构 JSON 修正。
- 网格生成前裁剪、单格/矩形修色、撤销/重做、可编辑工程 JSON 和完整 Markdown。
- CLI、SQLite 历史、分享链接、PDF 导出、环形圈数图与多层备份校验。

### Changed

- 最低 Python 版本提升为 3.11；CI 覆盖 Python 3.11–3.14。
- 配色统一使用真实毛线色表和 CIEDE2000；导入网格必须匹配可信色名/RGB。
- README 明确 Beta 状态、单图限制和试钩责任边界。

### Security

- 上传图片、分享载荷、备份、结构 JSON 和网格工程均增加大小与结构门禁。
- API Key/中转站来源隔离，异常信息脱敏，跟踪文件执行密钥形态扫描。
