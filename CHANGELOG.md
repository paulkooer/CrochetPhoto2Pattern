# Changelog

**简体中文** | [English](CHANGELOG_EN.md)

本项目遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 的组织方式，
版本号采用 [Semantic Versioning](https://semver.org/lang/zh-CN/)。Beta 阶段的备份、
结构和可编辑工程格式仍可能升级；发生不兼容变化时必须记录迁移方式。

## Unreleased

### Changed

- **视觉重设计「图解纸」**：整体视觉从通用暖色卡通风改为"一张打印
  的图解纸"——冷白纸面、藏青墨色、唯一的高亮记号扣黄只用于"你在哪 /
  你做完了什么"（激活 Tab、选中项、已勾选圈、进度），毛线色成为页面
  上仅有的其他颜色。新增 `app/theme.py` 叶子令牌模块作为 `.streamlit/
  config.toml`、注入 CSS 与全部 SVG/canvas 渲染器（环图/符号条/侧影/
  网格/3D 预览）的单一颜色来源（叶子模块无 Streamlit 依赖，避免
  models→ui 循环）；`tests/test_theme_tokens.py` 断言四个表面不漂移，
  并守护旧调色板不再回潮。结果页按 1–5 编号章节重排：部件圈序渲染为
  图解纸行（宋体行、勾选后记号扣黄扫过）、逐圈标签中的 notes/配色先
  经 md_safe 再进 Markdown 标签（注入防线同口径）、毛线芯片改为规则
  边框样式。Hero 为"前六圈顶视图（6→36 等距环）"的一次性描线动画
  （pathLength 属性会被 st.html 消毒器剥离，改用内联 dash 值）；
  `prefers-reduced-motion` 全量降级。字体不加载 Web 字体（离线/隐私
  立场，大陆访问 Google Fonts 不可靠）：正文系统黑体、标题西文优先
  Charter/Palatino 回落宋体，数字等宽内衬。打印样式隐藏界面 chrome、
  白底黑字输出图解。对比度：正文 ≈14:1、次级 5.3:1、控件边框 3:1
  （WCAG 1.4.11）。PDF 导出表头/斑马纹同步对齐令牌（旧陶土色清除）。

### Added

- **真实图解印证测试**（`tests/test_reference_patterns.py`，24 项）：以
  专业/社区公开图解外部校准系统——Clover 官方 AKIHIRO 玩偶（22 针腿/
  16 针臂/9 针尾/14 针耳）、社区通用球体公式（6 起针、每圈 +6）、
  Lovable Loops 樱桃迷你 C2C 图表（9×9 逐行色块全文）、Spin a Yarn
  Crochet 的 8 针起环（8→16→24 倍增）、Ms Premise-Conclusion《The Ideal
  Crochet Sphere》的 sin 轮廓性质验证（逐圈对照独立重算的 N=C/s 理论值）
  与原工艺警告落实检查、Craft Yarn Council 缩写规范一致性（sc2tog）、
  DROPS Design Children 23-60 苹果玩偶（Garnstudio 专业图解：7 针起环、
  +7 增圈、9 圈平针、对称减到 6、4 针锁针起点果柄；R17 勘误史——2012 年
  曾把减针误印为加针——构成首例"已发布出版错误"夹具）、StringyDingDing
  袋鼠 + 小袋鼠（头部环起后先平钩一圈再增、一体钩非均匀增减与 21/15
  奇数圈、耳朵 inc-4；腿部 R5 加针指令 vs (24) 计数的印刷矛盾为第二例）、
  Supergurumi「The Chubby Bee」蜜蜂（德国专业设计工作室：55 圈头身一体、
  66 针峰值、黄黑条纹逐圈换色、BLO 脊线圈、"1 短针"螺旋移位圈、错位
  增减圈、3 针递减奇数收尾序列 33→…→9→6；55 圈经机械核对逐圈自洽，
  校验器全过、CrochetPARADE 全圈可译含 COLOR 条纹指令）。
- **难度标签对齐 CYC Project Levels**（`app/schemas.py`）：官方四级
  Basic/Easy/Intermediate/Complex 定义（2026-09 抓取逐字核对）——本系统
  只生成短针玩偶，easy/medium/hard 分别对齐 Basic/Easy/Intermediate，
  Complex 要求多种技法同时使用、生成器不产生故不设。结果页 metric、
  手动页滑条、Markdown/PDF 导出四处展示面全部从裸英文枚举值切换为
  CYC 对齐标签（旧数据未知值兜底原样显示）。
- **CYC 纱线重量档映射**（`Gauge.cyc_label`）：按 Craft Yarn Council
  Standard Yarn Weight System（官方"短针/4 英寸"密度分档，2026-09 抓取
  核对）把密度映射到官方档位并附该档标准钩针区间；材料清单钩针行并列
  展示"玩偶紧钩建议 + CYC 标准档"。明示口径：这是"密度→档位"映射，
  不是"线材→档位"（紧钩玩偶同一密度可来自更粗的线）。交叉验证：DROPS
  Children 23-60（18 短针/10cm、4.5mm）恰落 CYC #2 fine，4.5mm 为该档
  官方钩针区间（3.5–4.5mm）上限。
- **C2C 起格约定**：网格导出的 C2C 逐行指令补充标准起格写法（锁 6 针，
  从钩针端第 4 针起每针钩 1 长针，共 3 长针，翻面）——Craftematics 与
  Crochet.com 两个独立教程来源一致。
- **圈表新增"针法写法"列**（Markdown 导出）：聚合数（+6/-6）按图例
  约定的 X/V/A 记号翻译为专业重复写法（如 (4X,V)×6）——对齐
  Supergurumi/DROPS 等图解的 "[4 sc, 1 inc] repeat" 表达；非均匀圈、
  单针增量、聚合不自洽或 JSON 改坏时降级为"—"。
- **CrochetPARADE 导出颜色流优化**：连续同色圈不再逐圈重复 COLOR 指令
  （条纹件从逐圈重复降为每边界一条，蜜蜂 23→6 条）；多份拷贝
  （quantity>1）每份都以部件色重置，不再继承上一份的结尾色。
- **材料米数最细档校准为棉线口径**（fine 档 320→250 m/100g）：依据
  Supergurumi 蜜蜂所用 Schachenmayr Catania（100% 棉、125m/50g、
  Sport/Fine(2)、2.5mm 钩）——正是该档标签"2.0–2.5mm + 中细棉线"的
  配置；旧值 320 为毛线 sport 口径偏高约 28%。其余三档待实体试钩（G4）
  校准，购买仍以实际线标为准。
- **安全眼尺寸随头径分档**（`_safety_eye_mm`，材料清单）：旧实现固定
  "8mm" 不随玩偶大小变化——16cm 大头径配 8mm 明显失真。新分档对齐
  r/Amigurumi 眼睛 wiki 社区口径（迷你 5–6mm / 常规 8–12mm / 大型
  14–20mm+，2026-09 抓取），专业锚点：约 10cm 头径配 12mm（Supergurumi
  蜜蜂 32cm 与 StringyDingDing 袋鼠 23cm 均为 12mm 安全眼）。默认 9cm
  头 8→10mm；无头径数据的旧结果兜底 8mm。
- **导出前言补环起替代法**：魔法环钩不好时的两种通行替代——锁 4 针
  引拔成环（Supergurumi 图解原文写法）与锁 2 针在第 2 针内钩入首圈
  （社区通行，Hobbii《Easy Alternative to the Magic Ring》）。
- **俄语圈跨语言印证**（kruchcom.ru 泰迪熊指偶，逐字原文）：КА
  （кольцо амигуруми=魔法环）环起 6 针、6 ПРИБ、平针 24——与社区标准
  完全同一节奏；同站大熊头部用 ВПП（起立锁针）逐圈引拔，聚合计数与
  螺旋钩一致，校验器无需区分钩法。
- **装配说明贯通开口针数**（`build_assembly` 新增 `openings` 参数）：
  专业图解装配段惯例——缝合前先报开口针数（"sew the remaining 12 sts"）。
  四肢缝合步骤现带"（开口 N 针）"（N=末圈针数），帽口/裙腰报明确
  针数；完全收口的球体头部如实不报（无开口）。JSON 修正（删/改部件）
  后随 refresh_derived 一并重算。生成链路与 refresh_derived 两个调用
  点均从 parts 推导，旧调用方缺省不传时行为不变。
- **收尾技法升级为"无痕收口"**：球体/蛋形/一体钩的收尾注记从朴素的
  "勒紧收口"升级为社区通行技法——"穿末圈每针前半针后拉紧"（中文社区
  术语"无痕收口"，源自编织人生等图解；英文社区对应 PlanetJune
  Fastening Off 的 front-loops 织法）。国内来源可达性调研同步记录：
  小红书正文需登录且图解以图片为主；编织人生全文在二级分享平台后
  （持续 502/500）且主站图解区为图片制图——中文社区的文字级校准源
  基本不可抓取，这正是本系统"照片→图解"在国内市场的价值所在。

### Fixed

- **部件注记安全眼直径与材料清单统一口径**：头部注记曾写死
  "安装安全眼（8mm...）"，与按头径分档的材料清单（9cm 头 10mm、
  15cm 头 14mm）冲突——现同样走 `_safety_eye_mm` 分档，回归测试
  钉死两处口径一致。
- **图片图解视觉转录通道打通（首个中文社区夹具）**：编织人生转载的
  紫柚手作「骨头团子」图片图解经视觉识别逐字转录为聚合计数——记号
  （X/V/A/CH/SL）与本项目导出图例完全一致，线材 4 股毛线 + 1.8/2.0mm
  钩印证 fine 预设"4 股棉线"标签。五个新测试钉死：主体 6→42→6 对称
  ±6（引拔圈钩法，零提示）、骨头2 的 18→36 倍增圈（原文"36X"）、
  刘海环起 10/8 非 6 起针、头套 30 针开口进入开口推导、导出前言补
  "引拔圈与螺旋钩等价"桥接说明。
- **开口过滤修正**：末圈注记含"不收口/勿收口"（明确的开口声明，
  如头套"开口保留…不收口"）不再被子串"收口"误判为已闭合——负向
  断言正则 `(?<![不勿])收口`。
- **校验器第 3 处先验修正：同圈混用加减速降级为 notes**：垂耳兔眼窝
  塑形圈 `7X,7V,A,7V,7X`（30→43）在真实图解中同圈混用加减速且代数
  完全成立——旧校验器硬判错误；可执行性由 inc≤prev / dec≤prev/2 保证
  （保持硬检查），混用圈超出本生成器的均匀分组表达，CrochetPARADE
  导出诚实跳过。
- **国内外渠道梳理补采（视觉转录通道批量投产）**：垂耳兔（面部塑形/
  sc3tog/平织椭圆耳/6 针筒臂/3mm 极小安全眼数据点）、橘子先生
  （**3 等分帽子拓扑** +3/圈、7 起针头套带倍增与引拔边、脚减到奇数 7、
  R16 同圈加入脚臂的一体钩）、AllAboutAmi Elephant（象鼻圆锥 -3/圈；
  椭圆起链与跨部件挑钩腿超出聚合模型，如实记录）。导出图例补中文
  社区标准记号 W（1 针目 3 短针）/M（三针并一针）。
- **C2C 逐行指令升级为专业 written 格式**（对齐 Juniper & Oakes 等
  图解的行格式）：每行加方向箭头（奇数行 ↗ / 偶数行 ↙）与正反面
  标注（正面/反面随翻面交替）；表头注明标注惯例出处。方向以两个
  独立来源（Juniper & Oakes、Lovable Loops）逐行核对为奇数行 ↙ 正面 /
  偶数行 ↗ 反面——初版方向相反，被心形图非对称行夹具当场纠正。
- **第二张已发布网格图表夹具（Lovable Loops 心形 9×9）**：17 行逐色
  written 序列转录为网格 → 本系统 C2C 渲染 → 逐行复现 published
  序列（含非对称行 7/8/9）——与 cherry 夹具的簇计数验证互补，钉死
  行内颜色读取方向。
- **小开口捏扁缝合建议进装配文案**：开口 ≤6 针的四肢步骤附
  "小开口可捏扁缝合"（垂耳兔等社区图解惯例，可免填充）。
- **眼位注记锚定措辞**：部件注记补"（最大围附近）"——专业图解以
  鼻线/眼窝等地标定位眼位（Supergurumi 蜜蜂："鼻线（BLO 圈）后 2 行"，
  间距可近至 1 针），本生成器无地标，明示几何近似并提示按眼径脸型调整。
- **渠道批量枚举通道**：编织人生 sitemap 分片（2.5 万 URL）可枚举，
  图解帖按 ID 段定位；软糖系列迷你挂件图解（视觉转录）新增枣形针
  B（5 卷长针并 1，进出各 1——针数中性）进导出图例，24→12 满额减圈
  与 BLO 圈内换色（超出逐圈配色粒度，如实记录）夹具。

- **校验器域混淆修正（印证发现，两处）**：真实图解中 22/16/9/14 针的圈
  完全可钩，旧校验器把"非 6 的倍数"硬判为错误；专业设计师图解的
  8→16 倍增圈（每针加一针，物理上恒可执行）也被 ±6 平滑节奏上限误拒。
  两者均降级为 `notes` 提示——可执行性由 inc≤prev / dec≤prev/2 保证
  （保持硬检查），六等分与平滑节奏是生成器先验而非可钩性要求。
  结果页以 ℹ️ 展示提示。
- **网格管线外部印证**：樱桃图表（white 57 / red 18 / green 6）经
  nearest 直采样后逐簇整簇映射毛线色，簇大小与发布图表完全一致。

## 0.2.0-beta.2 - 2026-09-05

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

### Fixed

- 共享部署上用户 API Key 不再可能被服务器环境的 `OPENAI_BASE_URL` /
  `ANTHROPIC_BASE_URL` 静默接管：用户 Key 未填 Base URL 时显式配对官方
  默认端点（SDK 不再回落读取环境变量）。
- 上传图片资源上限真正生效：`.streamlit/config.toml` 增加
  `server.maxUploadSize = 20`，解码后立即降采样到 2048px 再合成白底与
  缓存，JPEG 按 draft 比例解码——39.7MP 合法 PNG 的 +650MB 解码/合成
  峰值不再出现，结果页预览不再全尺寸传输。
- Mock 演示模式标注诚实化：UI、CLI 与 `vision_meta` 一致改为
  "体型与部件为固定演示值，配色与分段参考照片"（旧文案"与照片内容
  无关"与实际行为不符）。
- 解析模式改为显式三态 `vision_mode`（ai / local / mock）：库层不再靠
  "有没有 Key"隐式推导，Mock 与 Key 状态完全解耦且绝不发起 API 调用；
  `.env.example` 占位 Key（`sk-your-key-here`）不再被视为已配置。
- 模型可控自由文本（主要特征、识别部件、装配说明、材料清单回退行）
  改为纯文本渲染或转义输出，图片内文字注入无法再借 Markdown 链接/
  图片语法进入页面。
- SQLite 历史库连接用 `contextlib.closing` 确保关闭（消除 Python 3.13+
  ResourceWarning），建表与旧库迁移每个文件只执行一次。

### Changed

- 新增 `PatternResult` pydantic 模型作为结果字典的单一契约：orchestrator、
  CLI 两个分支、手动输入、快速调尺寸、备份导入共 6 处手写字典全部收口；
  备份与分享 token 携带 `schema_version`，分享解码拒绝未来版本。
- Vision 结构化输出改用独立的 `VisionOutput` 契约（与内部 `ImageAnalysis`
  分离）：枚举字段用 `Literal` 约束，不再携带模型无权填写的
  `recommended_colors`，并直接索取 `head_to_height_ratio`（替代"固定
  18.0 画布"的间接比例换算）；旧 prompt 厘米形态仅在无 schema 回退
  路径容忍转换。
- 新增 `PartKind` `StrEnum` 与中英显示标签表：部件的英文领域主键
  （= 结构 v2 part_id）与中文规范名从此单一来源派生，为 i18n 迁移
  铺路；`PART_NAMES` 数值保持不变。
- CI 新增 `type-check` job：`mypy` 纳入 dev 依赖，app 全包 37 文件
  0 错误为基线（配置见 `[tool.mypy]`），防止类型回归。
- 结果页三条本地流程（快速调尺寸 / 结构修正 / 备份导入）从按钮回调
  抽离为 `app/ui/result_logic.py` 纯函数层，可离线单测；逐圈勾选区改用
  `st.fragment`，勾选/取消只重跑该区块，不再触发整页 rerun。
- 产品显示名统一为 `CrochetPhoto2Pattern`：新增 `app.PRODUCT_NAME`
  单一来源，页面标题、hero、页脚与 Markdown/PDF 导出全部从其读取
  （此前 UI/导出用 Photo2Amigurumi，仓库与包名是 CrochetPhoto2Pattern）。

### Security

- 第二轮审视收口跨用户注入残留面：分享 token / 备份导入是"他人内容"
  入口，`params` 中仍以 Markdown 渲染的三处（部件 notes 的 `st.info`、
  形状/颜色行的 `st.write`、自检 issues 的 `st.warning`）改为 `md_safe`
  转义（剥零宽/BiDi → 反斜杠转义 `[]` 使链接/图片语法失效 → HTML 转义）；
  spans_measured、sizing/vision_meta 备注与全部异常文案同样转义。
- 备份导入新增 2MB 粘贴长度门禁（与分享 token 的 2MB 解压上限同源）。

### Added

- **CrochetPARADE DSL 导出器**（外部对标研究 P1）：`app/utils/parade_export.py`
  把逐圈图解翻译为 crochetparade.org 的文本语法（`ring` / `scNinc` /
  `N[sc,sc2inc]` / `start_anew` / `COLOR:` 子集，逐条核对官方手册与官方
  示例），CLI `--parade` 与结果页导出入口均可生成；导出自带 emitter
  级语法自检。用户粘贴到其本地网页应用即得独立 3D 渲染、针目张力
  分析与 Blender 可导入模型——代数自检之外的独立验证层。许可边界：
  只输出文本、不引入其 GPLv3 代码。
- 评测协议新增第二层"可执行正确性"指标 `parade_export_rate`
  （CrochetBench 方法论：从表面相似度到可执行正确性的双层口径），
  与 `pattern_valid_rate` 并列写入报告。
- 结构 v2 → 3D 结构预览（`app/ui/preview3d.py`）：自研 canvas 软渲染
  （三角面片 + 画家算法 + Lambert 着色，零外部依赖），instances 的
  位置/旋转与部件尺寸/配色直接成图，可拖动旋转/滚轮缩放；圆柱直径
  从针数与密度推导，profile 部件按逐圈针数车床成面（与环形图同口径）。
- `docs/schemas/` 发布核心契约的 JSON Schema（PatternResult /
  StructureGeometry / ImageAnalysis / CrochetPart，pydantic 自动生成），
  漂移测试保证文档与模型同步——对标 Knitout 的开放中间格式思路。
- 网格 Tab 新增 Floyd–Steinberg 抖动选项（少色板下保留渐变层次；
  对照 Stitchy 等照片转网格工具的通行能力），默认关闭。

### Fixed

- `st.components.v1.html` 已过 Streamlit 的弃用截止线（2026-06-01），
  三处 SVG 渲染（环形圈数图、逐圈符号条、轮廓验证、网格画布）迁移到
  `st.html`；定高与滚动由 `html_box` 写入内容 HTML（st.html 无
  height/scrolling 参数）。
- Dependabot 生态从 `pip` 改为 `uv`（官方 2025-12 起支持）：pip 生态
  对 uv 项目存在"只改 pyproject 不重建 uv.lock"的已知问题。
- 历史 SQLite 库在多会话线程下的首连 DDL 加锁；`_init_schema` 中
  commit 不再落入 suppress 块（已迁移库的 ALTER 全部失败时也能正确
  提交并标记初始化，含回归测试）。
- 历史 blob 携带 `schema_version`，载入端拒绝未来版本（旧记录照常）。
- 分享 token 改为按需生成（点击后缓存进 session），不再每次 rerun
  重复全量 JSON + zlib 压缩。

### Changed

- `py.typed` 随 wheel 发布（库形态使用可获类型提示），CI wheel 检查
  同步断言。
- mypy 开启 `check_untyped_defs`（app 全包 0 错误）；tests/ 以 documented
  override 仅检查模块顶层与调用签名——测试以 dict/SimpleNamespace 直捣
  内部形态，逐例标注收益低。
- CI 新增 `docker` job（只构建不推送，GHA 缓存），防止 Dockerfile 与
  依赖图腐化。
- `params["parts"]` 在内存中统一为 dict 形态（与落盘/分享/历史一致）：
  `_part_name`/`_part_rounds`/`_part_quantity`/`_round_stitches` 及
  validator、导出、PDF、环形图中的 dict/模型双态分支全部移除，
  CrochetPart/CrochetStitch 仅作校验与构造层。
- Vision SDK 超时预算收敛：60s×3 次重试 → 40s×1（两家 provider 回退后
  最坏 ≈2.7 分钟，此前接近 8 分钟）；`openai` 增加上界 `<4`，
  `anthropic` 增加上界 `<1`（1.x 是 httpx2 底座的破坏性升级）。
- Dockerfile 改为多阶段构建：依赖按 `uv.lock` 精确安装（不再
  `pip install .` 现场解析最新版）、依赖层缓存、非 root 用户运行、
  内置 `/_stcore/health` HEALTHCHECK。
- CI 三个 workflow 统一迁移到 `astral-sh/setup-uv@v7` 并开启缓存
  （`setup-python` 的 pip 缓存对 uv 管理的环境无效）；新增 Dependabot
  （pip + github-actions 每周）；ruff 启用 UP / SIM 规则集并清理
  全部存量（typing 现代化 + 可简化分支）。
- 历史审查快照（audit-brief*、handoff-review、optimization-brief、audits）
  移入 `docs/archive/`；按审查轮次命名的测试文件改为按覆盖范围命名
  （test_round12/14/15 → test_validator_c2c_materials /
  test_exports_share_cli / test_export_disclaimers_history）。
- 测试历史库改用每用例独立 `tmp_path`，并行/多用户环境不再共享
  `/tmp` 固定路径。

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
