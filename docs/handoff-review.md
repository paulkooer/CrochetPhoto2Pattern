# CrochetPhoto2Pattern 审查交接说明

> 面向独立审查者（人或 AI）。目标：让你在 30 分钟内建立准确心智模型，知道
> 哪些是刻意设计、哪些是已知局限、哪些地方最值得你花力气挑毛病。
> 本文档由当前维护者整理，**如实陈述**，不回避弱点。

---

## 0. 一句话定位

上传一张照片（或手动输入参数）→ 生成可照钩的 Amigurumi（立体钩织玩偶）图解：
逐圈针数（标准符号记法）、逐圈配色与换线、材料清单、装配说明、进度追踪。
Streamlit 单体应用，本地运行，LLM 可选。

- 仓库：`CrochetPhoto2Pattern/`（flat layout，包名 `app`）
- 运行环境（实测）：macOS / Python 3.9（user-site 安装，无 venv）
- 关键依赖版本：streamlit 1.50、pydantic 2.12、Pillow、opencv-python-headless 4.14、anthropic 0.95、openai 2.31
- 质量现状：**133 测试全过，覆盖率 93%（核心模块 99–100%），ruff 零告警**，CI（见 §6）

## 1. 架构与数据流

```
app/main.py（入口：侧栏 + 3 Tab 分发）
├── 📸 照片 Tab（tab_photo.py）
│    PipelineOrchestrator.run_full_pipeline(image, progress_cb, local_vision)
│    ├─ Step1 语义解析（二选一）
│    │   ├─ LLM：Anthropic structured output（messages.parse + ImageAnalysis schema）
│    │   │        失败降级 → OpenAI（response_format=json_object）→ 全败抛错
│    │   └─ 本地（无 Key）：OpenCV haar 人脸检测→头身比例 + 轮廓剖面→裙摆检测
│    ├─ Step2 StructureDesigner：部件名→形状/比例映射（sphere/cylinder/cup）
│    └─ Step3 CrochetParamsGenerator：圈数算法 + 照片色带逐圈配色
├── ✏️ 手动 Tab（tab_manual.py）：跳过 Step1，直连 Step2/3（无图→单色降级）
├── 📹 网格 Tab（tab_grid.py）：独立 2D Tapestry 管线（量化+Lab 配色+SVG）
└── result_renderer.py：结果渲染（两 Tab 复用；进度勾选/JSON 修正/备份导入/下载）

app/models/：image_parser / local_vision / color_design / structure_designer /
             crochet_params / grid_pattern / colors / orchestrator
app/utils/：exporters（Markdown 导出）/ images（上传安全加载+EXIF+解码缓存）
app/schemas.py：CrochetStitch(+color) / CrochetPart(rows 为派生 property) /
             ImageAnalysis(parts 去重 validator)
```

## 2. 领域规范依据（勿当 bug 报）

针法记法**按发布图解的通行规范**实现，非自行设计。依据已写入
`crochet_params.py` 文件头注释，核心：

- 符号：X=短针、V=加针（1针目钩2短针）、A=减针（2针并1针）
- 加针表：环起6X → 6V → (X,V)×6 → (2X,V)×6 → …（每圈+6，系数1省略）
- 减针表：(4X,A)×6 → (3X,A)×6 → … → A×6（每圈-6；镜面对称圈"隔"数相同）
- "隔N针"= 两次加/减针**之间的短针数**（不是组宽）——曾在此出过错，已修正并
  用双重测试锁定（`test_standard_inc_dec_table` 断言符号+隔数，
  `test_symbolic_pattern_arithmetic_is_executable` 断言符号算术自洽）
- 图解级惯例：螺旋钩（不引拔不翻转）、记号扣、隐形减针——写入 notes/UI/导出
- 参考来源：mstinacrochet.com、zhuanlan.zhihu.com/p/2397749055、pipsrainbow.com

其余领域口径（均有注释或测试锁定）：
- 网格 aspect_ratio 补偿方向：`grid_pattern.py` 内有完整推导（曾两次被误报"方向反了"，推导+测试在此）
- 密度常数（4针/cm、身体1.6圈/cm、四肢1.2圈/cm、0.08g/针）是**需试钩校准的启发式**，集中在 `crochet_params.py` 顶部常量区
- 帽子=开口杯形（cup，1.15× 松量不收口）；裙子=腰部环形开口起针（≈腰围针数）展开至裙摆、两端均开口——fable5 F1 曾发现旧版腰部为闭口圆盘，已修复并锁定测试
- 圆柱标注高度=（直钩圈+收针圈）÷密度：起底加针段是水平圆盘不计高（fable5 F3 修正口径）

## 3. 刻意设计决策（附理由，避免误报）

| # | 决策 | 理由 |
|---|------|------|
| D1 | `CrochetPart.rows` 非存储字段，是派生 property | 消灭 rows/rounds 失同步（历史 bug）；旧 JSON 残留 rows 被 pydantic 忽略 |
| D2 | `recommended_colors` 本地量化永远优先于模型输出 + `html.escape` | 防图片内文字 prompt-injection 直通 unsafe_allow_html |
| D3 | `parts` 不用 Literal 枚举，改 validator 去重 | LLM 输出变体（"双手"）宁可降级为小球，不让整次解析校验失败；重名部件会撞 widget key（修过的崩溃） |
| D4 | schema 上限（头≤50/高≤200）比 prompt（4–20/10–60）宽 | 两层设计：prompt 管常规尺寸，schema 只拦离谱值 |
| D5 | orchestrator **不用** `@st.cache_resource` | API key 会进程级滞留（共享部署风险）；client 本就每次调用新建，缓存收益微小 |
| D6 | 无 Key 时提供 radio：本地估算（默认）/ Mock | Mock 保留作演示；本地估算是真实分析照片的免费路径 |
| D7 | `anthropic>=0.95.0` 下限 | 实测 0.95.0 已含 `messages.parse(output_format=...)`（曾误报需升级） |
| D8 | `opencv-python-headless>=4.8,<5` | OpenCV 5 移除 legacy CascadeClassifier；代码另有 hasattr 防御 |
| D9 | `streamlit>=1.40,<2.0` | Streamlit 大版本常破坏 API |
| D10 | EXIF 转置放在 `utils/images.py` 上传加载处 | 单一咽喉点，两 Tab 共用；手机竖拍曾以横向进流水线（修过） |
| D11 | 模型层通过 `progress_cb` 回调拿进度 | 模型层不 import streamlit，可独立测试 |
| D12 | widget key 以 result_id 命名空间 + 替换时 purge + 圈数缩减时清残留勾选 | 防 session_state 无限累积与"进度复活" |
| D13 | JSON 修正后 `refresh_derived` 重算时长/材料 | 派生量必须跟随编辑（修过的失同步） |
| D14 | 备份/导入用**粘贴文本**而非 file_uploader | AppTest 无法注入文件上传；粘贴路径可测试 |
| D15 | 尺寸量化用 `int(x+0.5)` | Python round 是银行家舍入，.5 系统性偏偶 |
| D16 | 照片缩放用 LANCZOS 而非 NEAREST | 照片类输入防单点采样锯齿（像素画场景未提供选项——见 §4） |

## 4. 已知局限（如实清单，欢迎评估严重度）

1. **配色映射是先验近似**：`color_design.PART_SPAN` 按部件纵向占比铺色带，
   未做人体分割——坐姿/特写/多人照片的分段会偏。UI 有提示，可逐圈 JSON 修正。
2. **本地视觉的物理极限**：单张照片无尺度参照→头径按 9cm 锚定（UI 明示）；
   haar 只认正面人脸；部件/姿态无法本地语义推断，按规范默认值填充。
3. **轮廓推断只有一种**：下摆展开→裙子。上身宽松/其他形状不识别。
4. **LLM 路径无语义配色**：schema/prompt 未扩展"红裙子/金发"等字段（下一步计划）。
5. **tab_photo 覆盖率 ~50%**：AppTest 无 file_uploader API、IAB 浏览器不能传文件，
   上传交互仅由 `utils/images.py` 单测覆盖（EXIF/损坏/截断/超限）。
   `images.py` 的缓存分支同理（59%）。
6. 无服务端持久化（刷新即丢；有手动备份/导入）。无多角度融合、无 PDF 导出（路线图）。
7. 密度/克数/时长均为启发式估算，需试钩校准（注释已声明）。
8. 网格 Tab 对像素画用户没有 NEAREST 选项（当前固定 LANCZOS）。

## 5. 审查建议聚焦（我们最想要的外部意见）

1. **领域正确性**：圈数算法/比例/收尾是否符合你见过的真实图解（历史上这里
   错过两轮，外部钳制有价值）
2. `color_design` 的近似质量与 `PART_SPAN` 先验是否值得换成分割方案
3. `local_vision` 启发式的误报面（裙摆检测假阳性、比例钳位区间 2–8）
4. `result_renderer` 状态机边界：purge/stale-key/import 与 Streamlit rerun 的交互
5. 测试的"假信心"面：哪些 mock 替身掩盖了真实 API 兼容性
   （已知：OpenAI/Anthropic 调用层是 fake SDK，只锁定我方参数，不证明真 API 兼容）

## 6. 如何验证

```bash
cd CrochetPhoto2Pattern
python3 -m pytest -q --cov=app          # 133 tests, ~93%
python3 -m ruff check app tests         # 零告警
python3 -m streamlit run app/main.py    # 手动跑 UI（无 Key 也能玩本地/手动模式）
pip3 wheel . --no-deps -w /tmp/w && python3 -c \
  "import zipfile,glob;print([n for n in zipfile.ZipFile(glob.glob('/tmp/w/*.whl')[0]).namelist() if 'prompts' in n])"
                                        # wheel 打包含 app/prompts/*.txt（修过的打包 bug，CI 有锁）
```

测试地图：`test_crochet_params`（圈数算法+记法标准表）、`test_color_design` /
`test_local_vision`（图片驱动设计）、`test_app_smoke`（AppTest UI 流）、
`test_image_parser`（LLM 层+降级）、`test_exporters`/`test_orchestrator`/
`test_utils_images`/`test_repo_hygiene`（.env 泄漏防护）、其余为单元。

## 7. 审查者陷阱区（工具/框架行为，非本仓 bug）

- **AppTest**：`session_state` 无 `.get`/`.keys()`；unkeyed widget `set_value("")`
  不生效（需显式 key）；主区 widget 排在 sidebar 之前；无 `at.file_uploader`。
- **Streamlit**：expander 内交互触发 rerun 后 expander 收起（框架默认）；
  `st.success` 后立即 `st.rerun()` 消息不可见（已用 session 标志规避）。
- **工作区状态**：改动均未提交（git 可查 24 文件修改+若干新增）；
  `build/` 已清理（setuptools 会复用陈旧产物，本地打 wheel 前建议删）。
- 环境为 user-site 安装的 Python 3.9，无虚拟环境——审查时留意版本相关判断。

## 8. 历史修复索引（判断"是否回归旧病"时可对照）

安全：LLM 颜色字段注入、.env 入库防护、key 清除/滞留。
崩溃：重复部件 widget key、坏 materials 渲染/导出、坏图上传。
一致性：rows 派生、标注高度自洽、修正后派生量重算、过期勾选清理。
领域：减针"隔N针"口径（两轮才修对）、帽子闭口球、身体针数硬编码、
EXIF 方向、收尾工艺说明。
工程：prompt 未入 wheel、coverage/lint/CI、Dockerfile、备份导入、
本地视觉路径（人脸+轮廓+配色）。

---

## 9. fable5 第三轮审查的处置记录（2026-08-16）

已修复并各配回归测试：F1 裙子腰部闭口（重写为腰部开口环起）；F2 端部起针部件
（身体/手臂/腿部）的照片配色自底向上映射；F3 圆柱标注高度剔除起底圆盘；F4 背景
色改真·众数并消除两处重复实现；F5 refresh_derived 同步重算装配说明；F8 侧栏文案；
F9 Mock 全链路水印（vision_meta.source=mock）；新增已装 SDK 的 messages.parse 契约
测试（inspect.signature 断言 output_format/output_config）。
P2 项随后完成：LLM 语义配色字段（hair_color/top_color/bottom_color/clothing_type，
语义色优先于色带；clothing_type=裙子/连衣裙 自动补裙子部件——含一个"结构层补件
必须到达参数层"的回归修复）；网格缩放算法可选（lanczos/nearest）；LLM 路径
vision_meta 记录 provider（渲染层区分 AI/本地/Mock）。
唯一保留未做：canonical output_config.format 迁移——现形式经契约测试验证可用，
无真实 API 验证手段前不冒险切换。

*整理日期：2026-08-16。如与代码不符，以代码为准，并请指出本文档失实处。*
