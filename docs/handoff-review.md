# CrochetPhoto2Pattern 审查交接说明

> **历史演进记录**：本文包含多个审查时点的环境和测试数字，不是当前发布证明。
> 当前权威状态、验证结果与阻断门禁见 [`system-status.md`](system-status.md)。

> 面向独立审查者（人或 AI）。目标：让你在 30 分钟内建立准确心智模型，知道
> 哪些是刻意设计、哪些是已知局限、哪些地方最值得你花力气挑毛病。
> 本文档由当前维护者整理，**如实陈述**，不回避弱点。
>
> **新一轮外部工作的任务书**：
> - `docs/audit-brief-v3.md`（第三次全面深审任务书）——**当前使用中**，
>   重点：v2 修复引入的回归排查、30+ 校准常量审视、CLI 并发深入、
>   pose.py 43% 覆盖盲区、四份文档一致性；其 §5 为发现落点；
> - `docs/audit-brief-v2.md`（v2，已完结）：F23–F36 已全部处置
>   （handoff §24），§5.F 负面结果 8 条仍有效；
> - `docs/audit-brief.md`（v1，已完结）：F13–F22 已全部处置；
> - `docs/optimization-brief.md`（优化建议任务书）：已实现能力全清单、
>   已否决/搁置项（含三条"不要做"）、防幻觉纪律。
> 本文档作为演进史与细节依据配合使用。

---

## 0. 一句话定位

上传一张照片（或手动输入参数）→ 生成可照钩的 Amigurumi（立体钩织玩偶）图解：
逐圈针数（标准符号记法）、逐圈配色与换线、材料清单、装配说明、进度追踪。
Streamlit 单体应用，本地运行，LLM 可选。

- 仓库：`CrochetPhoto2Pattern/`（flat layout，包名 `app`）
- 运行环境（实测）：macOS / Python 3.9（user-site 安装，无 venv）
- 关键依赖版本：streamlit 1.50、pydantic 2.12、Pillow、opencv-python-headless 4.14、anthropic 0.95、openai 2.31
- 质量现状：**586 测试全过（含 264 组参数矩阵 + 1 条 CROCHET_EVAL_DIR 评测脚手架），覆盖率 90%，ruff 零告警**，CI（见 §6）

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

1. **配色映射是先验近似**：`color_design.PART_SPAN` 按部件纵向占比铺色带。
   主体分割已落地（第六轮 O2：GrabCut，`subject.py`）——主体像素的判定
   不再靠背景色距离启发式，但部件的纵向占比仍是先验（未做人体部位分割），
   坐姿/特写/多人照片的分段会偏。UI 有提示，可逐圈 JSON 修正。
2. **本地视觉的物理极限**：单张照片无尺度参照→头径按 9cm 锚定（UI 明示）；
   haar 只认正面人脸；部件/姿态无法本地语义推断，按规范默认值填充。
3. **轮廓推断只有一种**：下摆展开→裙子。上身宽松/其他形状不识别。
4. **LLM 路径无语义配色**：schema/prompt 未扩展"红裙子/金发"等字段（下一步计划）。
5. **tab_photo 覆盖率 ~50%**：AppTest 无 file_uploader API、IAB 浏览器不能传文件，
   上传交互仅由 `utils/images.py` 单测覆盖（EXIF/损坏/截断/超限）。
   `images.py` 的缓存分支同理（59%）。
6. 无服务端持久化（本机 SQLite 历史 + 手动备份/导入已实现，跨设备同步未做）。无多角度融合；PDF 导出已实现（`[pdf]` 可选依赖）。
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
python3 -m pytest -q --cov=app          # 589 tests（含 264 组矩阵）, ~90%
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


## 10. fable5 第四轮（映射链）处置记录（2026-08-16）

联网核实其引用：AmiGo（SCF 2022）、Ideal Crochet Sphere（mspremiseconclusion）、
PlanetJune 错开加针/jogless 换色——均属实并已落地。本地坐实并修复：
- 长宽比矛盾（#3）：新建 gauge 模块为单一事实来源（M4.15），网格层新增
  "按小样"比例选项，参数层密度全部由 gauge 推导；四肢 1.2/身体 1.6 的
  无依据差异取消（行高统一）；钩针/线材标签按 gauge 推导（旧"2.5mm+中细"
  与隐含 0.79cm 针宽的矛盾消除）。classic 预设保留经典锚点 36针=9cm头，
  其 w/h=1.23 超物理区间属已知取舍（图解惯例 vs 物理，试钩定夺）。
- 信息漏斗（核心诊断）：M1.1 剖面全量透传（vision_meta.silhouette.profile）；
  M1.4 主体高度改剖面实测；M1.3 人脸纵向 span 进 meta（仅展示，未替代先验）。
- M1.2 profile_to_rounds：照片剖面→旋转体逐圈针数（6 倍数量化、±6 钳制、
  三点平滑、自底向上），身体照片驱动（type=profile），模板降级保留；
  M1.5 轮廓 SVG 叠加可视化（生成侧影 vs 照片剖面）进结果页。
- M2.9 连续加针圈"错开半组"提示；M3.12 jogless 换色文案（PlanetJune 口径）。
后续补完（同日第二轮）：
- M2.6/M2.7 理想球（sinθ）与蛋形头（1+e·cosθ 变体，下半收窄；眼睛定位取
  最大围下一两圈）；±6 钳制下 sin 球末圈停在 ≤12 针属物理必然（真实图解
  即"断线勒紧收口"），非缺陷。
- M2.10 头身一体钩：头收针到颈围不断线接身体（壁反转自顶向下，加减针说明
  按新方向重算），装配改"分阶段填充"；配色退化为整段单色（已知取舍）。
- M2.11 裙子挑后半针法（attached，免缝合）+ 波浪裙摆（末圈每针放2针）；
  裙子做法经 params["skirt_style"] 在 refresh_derived 后保留。
- M3.13 语义色-色带融合：分段保留、最近段吸附语义色（红裙白边：白段保留
  红段校正）；语义色不在毛线色表时退回整段单色。
未做：实测 span 直接生效（M1.3 仍只展示）——误报面最大，待 UI 确认流程。

另注：仓库同期出现了用户侧的视觉设计系统 WIP（app/ui/design_system.py、
main.py 改动、uv.lock、.codegraph），与本文档所述工程线独立，未包含在
相关提交中。

*更新于 2026-08-16，163 测试 / 92% 覆盖。*


## 11. 第五轮审查（ZCode）处置记录（2026-08-21）

审查方式：全量通读 + 疑点逐一本地复现（非推测）。以下问题均先坐实再修复，
每项配回归测试；领域代数（加/减针"隔N针"、球/柱/杯/裙圈数构造、理想球
sinθ、头身一体颈部对齐）复核无误。**181 测试 / 93% 覆盖 / ruff 零告警**。

已修复（按严重度）：
- **N1 Mock 标签撒谎（高）**：`has_keys` 只看输入框，.env 用户选"Mock 演示
  数据"实际发起真实计费调用（Mock 是"无 key"的隐式副作用），且 .env 用户
  想用 AI 的唯一入口恰是"Mock"按钮——语义完全反转。修复：照片 Tab 解析
  模式 radio 改为按**有效 Key**（输入框 or 环境变量）出选项：有 Key →
  「AI（默认）/ 本地（免费）」，无 Key → 「本地（默认）/ Mock」，Mock 选项
  在有 Key 时不再出现（构造上不可达）。README/侧栏"清空输入框即停用 Key"
  的错误表述同步修正（清空=回退 .env，仍计费）。
- **N2 refresh_derived 用 DEFAULT_GAUGE 重算材料（高）**：非默认密度下
  JSON 修正/备份导入后克重漂移（fine 实测 65g→100g）、钩针标签换错规格
  （2.0–2.5mm→4–5mm 特粗）。修复：gauge 序列化进 params
  （`params["gauge"]`），`_gauge_from_params` 恢复（数值钳到侧栏同区间，
  非法回退默认）；渲染层轮廓可视化的 gauge 取值增加 params 回退（导入的
  旧备份无 result["gauge"]）。测试盲区根源：旧测试只用 classic（=DEFAULT）。
- **N3 透明 PNG 黑底污染（高）**：黑底透明 PNG（抠图/像素画导出常见）经
  convert("RGB") 丢 alpha 后透明区变实色黑，混进推荐配色/色带/网格（网格
  Tab 的像素画用户高频踩中）。修复：`images.py` 咽喉点（D10 同处）将带
  透明的 RGBA/LA/PA/P 合成到白底，一处修复全管线受益。
- **N4 轮廓可视化圆盘跳过错误（中）**：`_wall[0]//6` 恒为 1（魔法环首圈
  6 针），实际圆盘 5–6 圈——圆盘加针段被画进筒壁侧影、照片剖面对照纵向
  错位；同处一段恒真条件（`or True`）的死代码一并删除。修复：新增
  `profile_shaping.strip_dome`（`_increase_rounds` 构造的逆操作，纯函数
  可单测），渲染层改用它。
- **N5 备份导入不校验 analysis/structure（中）**：坏备份入库后在下一次
  rerun 的渲染层才崩（import 的 try 管不到），表现为异常页。修复：
  `_validated_backup` 与 params 同等待遇——analysis 过 pydantic、structure
  形状校验，失败在导入处以 st.error 呈现。
- **N6/N7/N8（低）**：pyproject 显式声明 numpy（此前靠 opencv 传递带入）；
  `render_silhouette_svg` 改真实尺度（旧版 scale_x 多除一次 2 且生成侧影
  按"直径"定位、照片剖面按"半宽"且未做区间峰值归一——叠加层只有生成侧影
  一半宽且系统性偏窄，两者占画布 1/4，对比失真）；文档口径随 N1 修正。

明确保留未做（低优先级，非 bug）：
- 侧栏 custom 密度残留上一预设值（切换体验问题，涉及"是否记住用户自定义
  值"的产品决策，待定夺）；
- `_img_decode_cache` 缓存 4 张全分辨率解码图（单会话最多 ~150MB，本地
  单用户可接受；后续可缓存 ≤1024px 工作副本，内存降 ~50×）；
- tab_grid 针法比例 select_slider 在 custom gauge 与固定选项等值时出现
  重复刻度（1.50 实测不崩，纯外观）；
- Dockerfile root 运行/无 HEALTHCHECK/层缓存（部署打磨项）。

测试增量（+12）：`test_vision_mode_*`×3（env Key 下默认 AI、Mock 不可达、
Key 状态切换不异常）、`test_backup_import_rejects_malformed_backup`、
`test_params_carry_generation_gauge` / `test_refresh_derived_preserves_
generation_gauge` / `test_refresh_derived_clamps_bad_gauge_values`、
`test_transparent_png_*`×3（白底合成/色带端到端/P 模式）、
`test_strip_dome_removes_bottom_disk` / `test_silhouette_svg_true_scale_
and_alignment`。

*更新于 2026-08-21。如与代码不符，以代码为准，并请指出本文档失实处。*


## 12. 第六轮（论文驱动优化）处置记录（2026-08-29）

本轮以"联网核实 → 本地落地 → 官方数据锁定"推进（延续 fable5 惯例）。
**223 测试 / 93% 覆盖 / ruff 零告警**。

已落地：
- **O1 CIEDE2000 感知色差**（Sharma, Wu & Dalal 2005 实现注记为标准参考）：
  替换 CIE76 距离（蓝区 hue 旋转/中性色失真）。实现按官方注记逐步转写，
  用论文配套 34 组补充测试数据逐对验证（±1e-4，最大实测误差 4.95e-05），
  数据固化进 `test_colors.py`。影响：色表匹配（nearest_yarn）、语义色吸附。
- **O1b 语义吸附目标修正**：吸附目标从"色距最近段"改为"**占比最大的
  主色段**"+ CIEDE2000 平局裁决。CIEDE2000 下红↔白 45.8 < 红↔蓝 50.8，
  纯色距会把"红裙白边"的白边吸成红（与设计意图相反）；旧 RGB 欧氏差距
  <2% 属碰巧正确。语义字段描述的是服装主色，主色段=覆盖圈数最多的段。
- **O2 GrabCut 主体分割**（Rother, Kolmogorov & Blake, SIGGRAPH 2004，
  cv2.grabCut 零新依赖）：新增 `app/models/subject.py`（单一来源），
  三处消费——纵向色带、轮廓剖面、推荐色板（背景色不再入板）。
  分割架构（踩坑实录）：确定性背景=顶+左右条带（主体常贴底边，不能用
  内缩矩形）；前景种子按"到背景色集合（条带全部≥15%覆盖量化色，非众数）
  的距离"三档（GC_FGD >2T / GC_PR_FGD >T / GC_PR_BGD，头与身体断开的小
  孤立块会被 GrabCut 数据项整体吞掉，必须 FGD 强制保留）；掩码腐蚀 1px
  剔除重采样混色边界；色带空带延续最近主体色带（不落回整带均值）。
  实测双色背景（白墙+深灰地板）场景：地板色从色带/色板中完全剔除。
  失败回退旧启发式（cv2 缺失/图过小/主体占比出 5–95% 区间）。
- **O2b 下摆判定构图不变**：`_has_bottom_flare` 窗口改在主体纵向范围
  （首/末超阈行）内取——主体不贴图底时裙摆不再漏检（此前窗口落到背景）。
- **O3 用线米数**：材料清单附"≈Ym"——按针宽分档换算
  （`gauge.meters_per_100g`，与钩针标签同分档）。
  **【V6 更正，2026-08-29】**：当初署名的"CYC m/100g 区间中值"不成立——
  CYC 标准只含密度与针号区间，不含长度。现值（320/250/200/140）如实
  降级为**实务经验估算值**，导出与 UI 均已加"以实际线标为准"提示。

核实后未采用（如实记录）：
- **AmiGo 论文全文核实**（arXiv:2211.01178）：论文 crochet 模型以
  stitch width w 均匀嵌入 + 只用 sc/inc/dec（Observation 2.3），本仓
  profile_to_rounds 的 ±6 钳制与之一致；论文**不含用线量估算方法**，
  未能为"克重→米数"之外的估算提供引用依据（O3 用 CYC 标准，已注明）。
- CMU 2023 机织用线线性模型（textiles.cs.cmu.edu）：针对机器针织结构，
  短针手工织物的面积近似已够用，引入收益不成比例。

测试增量（+8）：CIEDE2000 官方 34 组（参数化）+ 对称性/RGB 入口/蓝区判别
3 条、主色段吸附 1 条、GrabCut 掩码/双色背景剔除/空带延续 3 条、色板剔背
景 1 条、悬空裙摆构图不变 1 条（与 O2b 配套）。

*更新于 2026-08-29。如与代码不符，以代码为准。*


## 13. 第七轮（深审 + 论文驱动）处置记录（2026-08-29）

**227 测试 / 93% 覆盖 / ruff 零告警**。延续"联网核实 → 实验 → 落地 → 数据锁定"。

已落地：
- **O-P1a Otsu 自适应种子阈值**（Otsu 1979, IEEE Trans. SMC）：GrabCut
  前景种子的距离阈值改为 `clamp(Otsu(距离分布), 16, 96)`，退化回退固定
  48。修复低对比度场景（主体/背景 L1 距 <48，如 235 灰墙前的 245 亮灰
  主体——固定阈值完全分不出），高对比图封顶 96 与旧行为一致。Otsu 实现
  取最大类间方差**平台中点**（双尖峰分布峰间区间方差持平，argmax 会命中
  区间起点——单测锁定）。
- **O-P1b 人脸框确定性前景种子**：haar 检出的人脸框（subject 内部调用
  local_vision._detect_face，≤160px 小图上开销毫秒级）作为 GC_FGD 锚定
  头部——GrabCut 论文"检测器供种"的自动化等价用法，防"主体色与背景
  相近时颜色分档救不了头部"。框面积 >50% 图幅时弃用（防误检支配）。
  无脸图行为不变（种子退回颜色分档）。
- **O-P2** subject.py 模块文档与实现对齐（Otsu/人脸种子/确定性声明）；
  extract_subject 类型标注修正（np.ndarray）。
- **O-P3** 网格 Tab 针法比例 select_slider 选项去重（custom 小样比例与
  固定选项等值时不再出现双刻度）。

核实后未采用：
- 人脸框供种仅在检出时启用——未引入新依赖（如 media pipe/deep detector），
  haar 的误检面由面积约束 + "种子仅影响 GrabCut 初始化（图割仍可推翻
  非确定区）"双重控制；检测器升级留待有真实人脸误报数据再议。

测试增量（+3）：Otsu 双峰/退化、低对比度分割、人脸框种子（含过大框
弃用）。

*更新于 2026-08-29。如与代码不符，以代码为准。*



## 14. （编号空缺——原第八轮记录误编为 §15，实际应为本节。内容已并入 §15 上下文，此占位保持编号连续。）

## 15. 第八轮（深审 + 论文驱动）处置记录（2026-08-29）

**239 测试 / 93% 覆盖 / ruff 零告警**。

已落地：
- **O-P4 色表按 Monk Skin Tone Scale 扩充**（Ellis Monk / Google 2022，
  skintone.google/get-started，10 级肤色标尺、深肤色端分布比 Fitzpatrick
  均匀）：新增 6 个肤色条目，取 MST 精确锚点 RGB——白皙肤色
  (246,237,228)=MST-01、小麦肤色 (160,126,86)=MST-06、咖啡肤色
  (130,92,67)=MST-07、深肤色 (96,65,52)=MST-08、暗肤色 (58,49,42)=MST-09、
  深褐肤色 (41,36,32)=MST-10。修复两处语义错误：扩充前 MST-07~10（全球
  相当比例人口的肤色）全被吸到"深棕色/黑色"、MST-01/02 被吸到"浅灰色"。
  MST 全部 10 级→肤色系毛线名的映射由参数化测试锁定。
  已知边界（如实记录）：黑发像素 (~50,40,35) 与深肤色在像素级同域不可
  分——发色的正确来源是语义字段（AI hair_color / 用户修正），像素映射
  给出肤色名是可接受的降级；3 处旧测试的"暗色系头部"断言相应放宽。
- **O-P5 理想球对照原文核实**（mspremiseconclusion 2010 全文）：公式口径
  确认一致（N = C/s，C = π·D·sinθ；原文 "Pi*r^2" 为笔误）。落地原文工艺
  警告：**收尾勿按标准减针收到 6 针（底部过尖）**——保持 ≤12 针穿线勒紧
  收口；理想球末圈备注更新为明确警告（此前只有"勒紧收口"，未说明原因；
  handoff §10 的推断获原文确认）。作者 1:1 针宽/行高备注：classic 预设
  1.23 属已记录取舍，不变。
- **O-P6 剖面采样线性插值**：`profile_to_rounds` 与 `render_silhouette_svg`
  的照片剖面采样从最近邻改为线性插值（`_sample_at` 纯函数）——最近邻在
  墙圈数高于剖面分辨率时产生阶梯伪影；±6 钳制量化在下游不受影响。
  （信号处理常识，无特定论文，如实在此注明。）

测试增量（+12）：MST 10 级参数化 + 深棕/深肤判别 + `_sample_at` 插值
6 断言；3 处旧断言随色表语义放宽（暗色系集合）。

*更新于 2026-08-29。如与代码不符，以代码为准。*


## 16. 第九轮（前端深优化）处置记录（2026-08-29）

**243 测试 / 93% 覆盖 / ruff 零告警**。全部为 UI 层改动，模型层只做了
result 透传扩展（见下）。

已落地：
- **F1 推荐色板真实毛线色样**：色名胶囊从"纯文字"升级为"色表 RGB 色点
  + 文字"（`_yarn_chip_html`）——用户看颜色选线而非只读名字；色表外
  （LLM 自造色名）退化中性胶囊；名字仍经 html.escape（注入防线不变）。
- **F2 结构区可读表格**：`st.json` 逐部件 dump 换成 dataframe（部件/形状/
  尺寸/基准色，形状译为中文），原始 JSON 移入折叠 expander 供高级用户。
- **F3 结果页快速调整尺寸（不重新调用 AI）**：头径/身高滑杆 → 结构+参数
  层本地重算（零 API 成本）。前提是 result 开始透传 `style`（塑形四选项）
  与 `color_bands`（照片色带）——orchestrator 与手动 Tab 同构补充；gauge
  复用 result/params 里已有序列化值。重生成换新 result_id（旧 widget
  状态 purge，不串档）。实现时修掉一个自坑：成功提示标志以 result_id
  为键，重生成换 rid 后标志永远弹不出来——标志改用"新" rid 写入。
- **F4 网格图例真实色块**：新增 `render_legend_html`（色块+符号+名称+
  占比，亮度自适应符号色），屏幕渲染用 HTML 版；下载版仍为纯 Markdown
  表格（`render_legend_markdown` 不变）。
- **F5 照片 Tab**：生成成功后 `progress.empty()` 清掉常驻的"100% 完成
  条"（结果区本身即反馈）；未上传时预览列显示虚线空状态引导（.crochet-empty）。
- **F6 打印样式**：`@media print` 隐藏侧栏/横幅/Tab 栏/按钮/滑杆/上传框/
  文本域，正文白底黑字——钩织时打纸质图解的真实场景；卡片阴影去除。

测试增量（+4）：色样 hex 断言、结构 dataframe 渲染、快速调尺寸端到端
（rid 换新/尺寸生效/塑形与色带透传/头部针数随尺寸变大）、照片路径
style/color_bands 透传。result.keys 断言两处与 grid_view fixture 适配。

*更新于 2026-08-29。如与代码不符，以代码为准。*


## 17. 第十轮（中转站支持）处置记录（2026-08-29）

**248 测试 / 93% 覆盖 / ruff 零告警**。

需求：API 走第三方中转站/代理（国内常见接入方式）。

已落地：
- `ImageParser` / `PipelineOrchestrator` 接受 `openai_base_url` /
  `anthropic_base_url`，直接传给 SDK 构造器（openai 2.48 / anthropic
  0.122 均原生支持，已验证签名）。解析优先级与 Key 一致：**UI 输入 >
  环境变量（OPENAI_BASE_URL / ANTHROPIC_BASE_URL）> 官方默认**；空串
  归一为 None。
- 侧栏新增「🔗 中转站地址（可选）」折叠区（两个输入框，placeholder
  提示官方地址），`tab_photo._build_orchestrator` 透传；手动 Tab 不经
  parser，无需改动。
- `.env.example` 与 README 增加中转站配置说明。

测试增量（+5）：mock SDK 构造器断言 base_url 传递（含 api_key）、
未填 → None、env 回退、UI 覆盖 env、orchestrator 透传；AppTest 验证
侧栏输入填写/清空清理。

*更新于 2026-08-29。如与代码不符，以代码为准。*


## 18. 第十一轮（方案落地：S1–S7）处置记录（2026-08-29）

按第十轮提案一口气实施（S6 仅设计文档，见 docs/3d-reconstruction-design.md）。
**267 测试 / 93% 覆盖 / ruff 零告警**。

已落地：
- **S2 OpenAI 严格结构化输出**：`chat.completions.parse`（pydantic →
  strict json_schema，与 Anthropic messages.parse 对称）。失败带错误反馈
  重试一次（messages 追加 assistant 原文 + schema 校验错误）；refusal
  直接抛错不重试；旧 SDK 无 parse 时回退原 json_object 路径
  （`_parse_with_openai_legacy`）。契约测试断言 parse 存在。
- **S7 WCAG 对比度**：主按钮背景 #d9785f→#a85442（白字 3.09→5.23:1，
  AA 正文达标），新增 `--peach-deep` 变量，hover 同步。
- **S3 毛线色板直量化**：`colors.pick_yarn_palette`——16 级量化桶统计
  毛线色覆盖率取前 N，全像素按 CIEDE2000 重新分配，<1% 长尾剔除。
  网格 Tab 与推荐色板接入（替代"中位切分任意色→映射毛线表"的双重量化），
  图案每一色都是可购买毛线。
- **S1 姿态关键点实测 span**（M1.3 欠账兑现）：新 `app/models/pose.py`——
  MediaPipe Pose Landmarker（Apache-2.0，可选依赖 `[pose]`）33 关键点 →
  人体学映射实测 span（髋=身体/腿分界，不重叠）；模型 ~5.8MB 首用自动
  下载缓存（`CROCHET_POSE_MODEL` 可覆盖），缺失/离线/未检出 → None →
  回退 PART_SPAN 先验。orchestrator 统一注入（本地/LLM 路径皆适用），
  `color_blocks_for_part` / `_apply_color_plan` / profile 身体件 /
  结果页可视化 / 快速调尺寸全链路透传，UI 显示实测来源提示。
  **选型实验记录**：mediapipe 1.0.1 依赖 opencv-contrib-python 5.0，与
  主依赖 opencv-python-headless<5 冲突（D8）——故必须保持可选，二者
  不可共存于同一 venv；实机验证命令 `pip install .[pose]`（本轮因网络
  限速未完成 90MB wheel 下载，live 路径由假关键点测试 + 降级测试覆盖）。
- **S4 图解历史 + PDF**：`utils/history.py`（SQLite 单文件，
  `CROCHET_HISTORY_DB` 可重定向；**pydantic 对象必须 model_dump 序列化**
  ——default=str 会把部件存成字符串，恢复即崩，已有端到端测试锁定）。
  结果页「🗂 存入历史」+ 侧栏「我的图解」载入/删除。`utils/pdf_export.py`
  （reportlab 可选依赖 `[pdf]`，STSong-Light CID 中文字体），结果页
  点「🖨 生成 PDF」才构建（避免 rerun 重复渲染）→ 下载按钮。
- **S5 合成真值评测基线**：`tests/test_eval_baseline.py` 5 条——pose→span
  映射精度（±0.06）、色带蓝/裙分离、flare 轮廓检出、管线确定性（逐字节）、
  密度换算物理自洽。评测本身抓到两个真实边界并如实记录：色表精确锚点
  （(220,50,50)→"暗红色"）与 **6 倍数量化的直径精度下限**（±6·w/π/2，
  fine 密度 0.48cm——容差据此设定，非拍脑袋）。

未实施（如实）：
- S6 单图 3D 重建：GPU 依赖，交付设计文档（TRELLIS/TripoSR 选型、切片
  管线、只换身体件形状来源、风险清单），docs/3d-reconstruction-design.md。
- S1 live mediapipe 实机验证：网络限速未完成下载；补充验证 =
  `pip install crochet-photo2pattern[pose]` 后跑照片 Tab（模型自动下载）。

测试增量（+19）：S2×4（strict parse/重试/refusal/契约）、S1×6（人体学
次序/缺膝回退/实测切块/端到端/降级/成功流）、S4×4（CRUD/非法 id/PDF
中文/历史端到端）、S5×5 评测基线。

*更新于 2026-08-29。如与代码不符，以代码为准。*


## 19. 第十二轮（同类项目对照 + T1–T8）处置记录（2026-08-29）

对照调研：CrochetPARADE（pattern 文法+正确性检查+local-first）、
ajwhitman C2C、judy2k/crochet-cad、KSEHano/AutoCrochetGeneration、
crogen、Tristansko C2P。自审发现 10 项（详见本轮对话），全部处置如下。
**278 测试 / ruff 零告警**。

已落地：
- **T1 合规/供应链**：补 LICENSE（MIT 正文，此前 pyproject 声明而仓库
  无文件）；pose 模型下载后 SHA256 校验（float16/1 版本锚定），不匹配
  删除并回退先验，缓存文件启动时也校验。
- **T5 隐私告知**：照片 Tab 说明 AI 模式照片去向（服务商/中转站）、
  本地模式不出本机、本工具无自有服务器。
- **T2 逐色材料清单**：按圈色跨部件聚合克重+米数（下限 5g/色），复用
  CYC 换算；渲染层带真实色样胶囊；色表外颜色（LLM 语义色）同样给量。
  聚合与总针数一致性有容差断言。
- **T3 C2C 真实现**：`render_c2c_chart`——对角行 word chart（行格数
  min(k,W,H,W+H-k) 的增/平/减相位、来回交替方向、螃蟹针收边说明），
  此前 README 宣称 C2C 而实际只有 tapestry 方格（诚实性缺口已闭合）。
- **T4 PatternValidator**：`app/models/validator.py`——逐圈针数代数
  （=上圈+加−减）、加减不共存、空部件检查；结果页「✅ 自检通过」徽章
  或可读问题清单（借鉴 CrochetPARADE correctness checking，把代数自洽
  从测试层暴露给用户）。
- **T6 span hints 进 prompt**（S1×LLM 协同）：orchestrator 在解析前
  测 pose，`format_span_hints` 生成【几何参考】段注入两家的 prompt——
  Vision 模型的 parts 判断与几何实测交叉验证。
- **T7 部署与门面**：`.streamlit/config.toml`（主题与 CSS 变量同源，
  消除首帧漂移）；`.github/workflows/extras.yml`（[pdf]/[pose] extras
  矩阵——[pose] 作业同时充当"opencv-contrib 5 覆盖 headless 后仍可
  降级运行"的金丝雀）；README 徽章；「辅助角度照片」占位改为诚实的
  规划中文案。
- **T8 环形圈数图**：`app/models/ring_chart.py`——部件顶视图，每圈
  物理半径 r=N·针宽/2π，配色填充+右侧 R/针数/色名标注（双列交替节距
  防重叠）；球类/一体件展开区显示。

S1a 实验结论（补充 §18）：**mediapipe 1.0.1 在 macOS arm64 原生崩溃**
（Metal 图初始化 `Check failed: service_`，强制 CPU 代理同样崩溃）——
依赖约束已收紧为 `mediapipe>=0.10,<1.0`；0.10.21 实机验证因网络限速
（50MB wheel 长时间未完成）仍未跑通，属环境问题，验证命令不变。

测试增量（+11）：逐色材料×2、C2C×2、自检器×3、hints×2、环形图×2。

*更新于 2026-08-29。如与代码不符，以代码为准。*

## 20. 第十三轮（Opus 5 审查 F13–F22 处置）记录（2026-08-29）

外部审查（Opus 5）按 `docs/audit-brief.md` 执行，产出 F13–F22 十项发现
（已复现坐实 8 项 bug + 2 项文档项；F18 首次复现度量有误，用正确口径
确认）。本轮全部处置，无保留项。**509 测试 / ruff 零告警**。

P0 安全与正确性：
- **F14 异常泄露 Key**（已复现：中转站异常含 Bearer token 直接进 UI 异常
  与日志）：新增 `_sanitize_secrets`——实例 Key 精确替换 + sk-* 通配 +
  Bearer 头屏蔽；provider 层、聚合异常、日志全部过脱敏；URL/状态码/
  request id 保留（可诊断性）。测试断言 `key not in str(exc)` 与
  `key not in caplog`。
- **F13 图解代数矛盾**（classic+egg+一体+头 11cm：42→30 跳变但声明减 6；
  216 组矩阵扫出 3 组失败）：根因是 `_merge_head_body` 颈围对齐
  `head_kept.append(neck)` 直接跳变。新增 `bridge_rounds(cur, target)`
  （±6 逐圈桥接），颈围对齐改走桥接；`generate_params` 返回前强制
  `validate_pattern` 门禁，失败抛 `PatternGenerationError` 阻止矛盾图解
  成为可下载产物。审查者要求的参数矩阵测试落地（216 组合：3 密度 ×
  3 球型 × 一体开关 × 头径 4/9/11/20 × 高 10/30/60，断言自洽 + 逐圈
  |Δ|≤6），修复后 **216/216 全过**。

P1 几何与工艺语义：
- **F16 一体件高度虚高**（17.5cm）：根因比报告更深——`n_dome =
  body_sts[0]//6` 是 N4 同款错误（魔法环首圈 6 针 → 恒为 1），dome
  加针圈被混进"筒壁"，一体件底部出现第二个假 dome。改用 `strip_dome`
  统一口径后，高度 = 头部到颈 + 筒壁轴向 = 13.8cm（收口盘径向不计高），
  针数序列形状自洽。
- **F17 剖面身体工艺矛盾**：末圈开口但说明写"收针前填充"。改为开放式
  拓扑明确文案："末圈保持颈部开口不收针：填充后断线留 15cm，与头部
  开口边逐针缝合"。
- **F18 帽子侧壁过浅**（dk/fine 仅 1 圈 ≈0.6–0.7cm，无法佩戴）：帽顶
  与侧壁拆分计算，侧壁 = max(3, ceil(0.6·直径/行高))，三密度侧壁
  9–10 圈；旧测试锁定的"总高=0.6·直径"语义随 F18 更新为"侧壁=0.6·
  直径，总高=帽顶+侧壁"的精确对账断言。
- **F15 pose 部分实测劣化**（缺膝盖时腿/裙/尾丢配色，比不用 pose 更差）：
  有效 span 改为 **先验 ∪ 实测**（实测覆盖先验），`spans_measured`
  元数据记录实测部件；UI 诚实标注"X、Y 来自关键点实测，其余为先验"。
  尾巴永远先验（正面关键点测不到）。

P2 展示与状态：
- **F19 环形图标签重叠**（(i%14)*18 导致 R1/R15 同坐标）：改为只标
  "变化圈"（首/末/配色变化/加减相位变化），17/30/60 圈实测标注数
  7/7/7 且坐标唯一；几何圆环仍全量绘制（修复过程中曾把圆环误删，
  回归测试随即拦截）；完整信息保留在逐圈表格。
- **F20 purge 漏前缀**：补 `pdf_gen_`、`sz_`（泛前缀覆盖 ok 标志族）；
  purge 测试改用 monkeypatch session_state 精确断言清理集合。

P3 文档：
- **F21** README 字面量 `\n` 修复（1 处）。
- **F22** flow.md 路线图同步：PDF 导出/图解历史移入"已实现"，路线图
  只留多角度/模板库/针法扩展/跨设备/符号图；handoff §4.6 能力边界更新。

审查者已排除的误报（F 系列）经本轮复核确认，未重复处理。

测试增量（+231，其中 216 为矩阵参数化）：脱敏×2、矩阵门禁×216、
bridge×1、F15×2、F16/F17/F18×4、F19×1、F20×1。

*更新于 2026-08-29。如与代码不符，以代码为准。*

## 21. 第十四轮（U1–U8 + 自审新发现）处置记录（2026-08-29）

对照十字绣工具生态（CrossStitchApp/png2dmc/tarraz 等的"色号+符号+每色
针数"铁三角）与 CrochetPARADE 符号图标准，自审 + 落地。**572 测试 /
ruff 零告警**。

自审新发现（已坐实并修复）：
- **N-G GrabCut FGD 阈值漏浅肤色**（本轮最重要的发现）：浅肤色 vs 白
  背景 L1 距离实测 ~184，低于 FGD 阈 2T=192——头部被当背景吞掉，推荐
  色板只剩衣服色。FGD 阈改为 max(1.5·T, 144)（绝对下限），浅色主体
  可靠捕获、JPEG 噪声（<48）仍不误入。双色背景剔除不回归。
- **N-A PDF 富文本注入**：`Paragraph(str(notes))` 未转义——`<script>`/
  `<foo>` 被 reportlab 当行内标记解析（不崩溃但可扭曲打印版面）。
  `esc()` 包装全部用户文本入口。

U 系列落地：
- **U1** PDF 转义加固（N-A 修复）+ 测试。
- **U2** `use_container_width` → `width="stretch"` 迁移（5 处；streamlit
  1.50 弃用警告，移除期限 2025-12-31 已过）。
- **U3 CLI 无头模式**：`app/cli.py` + `[project.scripts] crochet2pattern`。
  三模式（--image 本地视觉/AI/--mock、手动参数）、gauge/style/塑形全参、
  `--out/--md/--pdf` 输出；CLI 同受自检门禁（rc=2）。补齐同类项目的
  脚本化形态缺口，批量/CI 评测的地基。
- **U4 hypothesis 属性测试**：生成器不变量（6 倍数/|Δ|≤6/代数自洽）在
  随机域验证（60 examples/组）；`bridge_rounds` 全域不变量（100 组）。
  hypothesis 入 dev 依赖。
- **U5 门禁矩阵扩展**：+48 组（色带×剖面×实测 span×密度×球型），总
  门禁覆盖 264 组合。
- **U6 品牌色号**：`BRAND_CODES` 只收录**已联网核实**的 Scheepjes
  Catona 色号（8 个：黑 110/白 106/橙 189/黄 208/草绿 389/青 397/
  红 506/蓝 113 近似——来源 scheepjes.com 与零售商商品页）；未核实
  色名宁缺毋错。逐色材料条目自动附参考色号。
- **U7 逐圈符号条**：`render_symbol_strip`——每圈针法序列画成 ×/V/A
  记号横条（与本仓记号体系同源），超长圈 "+N" 截断、超多圈只显示末
  24 圈；随环形图一起在结果页展示。
- **U8 分享与缩略图**：生成时携带 96px JPEG 缩略图随 result 存档（历史
  列表可视化）；`utils/share.py`——zlib+base64url 压缩进 `?p=` 分享
  链接（>6000 字符自动拒绝并提示改用备份文件），main.py 启动时检测
  并载入。
- **U9 i18n：明确不做（本轮）**。理由：UI 的 ~100 条中文文案与 30+ 条
  中文断言测试深度耦合，一次性翻译需先做 i18n key 重构，单独成轮；
  强行半翻译比不翻译更差。已按此记录，待后续专项。

测试增量（+63：U1×1、U5×49、U3×4、U6×2、U7×2、U8×4、N-G 经由既有
评测/回归覆盖；参数矩阵计入 264 组）。

*更新于 2026-08-29。如与代码不符，以代码为准。*

## 22. 第十五轮（Opus 5 优化建议 V/K/U 系列处置）记录（2026-08-29）

外部优化建议 17 条（V1–V5、K1–K2、U23–U33），全部先复现/核实再实施。
**574 测试 / ruff 零告警**。

P1（全部修复）：
- **V1 Markdown 表格注入**：exporters 表格单元含 `|`/换行 → 列数错乱
  （实测 19 行损坏）。新增 `_md_cell`（`|`→`\|`、换行合并、反斜杠转义）
  覆盖表格/材料/引用块。注意验证方法：须数**未转义**竖线（`\|` 仍含
  `|` 字符）。
- **V2 门禁盲区（波浪摆 48 针跳变静默过审）**：采用审查者推荐的
  **显式白名单**方案——`CrochetStitch.allow_wide_jump` 字段，ruffle 圈
  置位；validator 把"物理 |Δ|≤6"从测试层升级为独立检查（未声明白名单
  的宽跳变报错），与代数自洽解耦。hypothesis 域扩至裙子/帽子/ruffle
  （48 examples），矩阵同步。输出零变化（白名单方案）。
- **V3 分享 rid 固定 "shared"**：历史表主键覆盖 → 两次另存丢数据。
  改 uuid。
- **V4 share 丢 style/spans/color_bands**：payload 扩为备份同构九键
  （preview 不进 token——会推过长度门限）；旧 token 兼容（渲染层默认
  值兜底）。round-trip 断言 egg/ruffle 保留。

P2（全部落地）：
- **K1 CIEDE2000 向量化**：`ciede2000_vec`（pairwise 自动判 + 显式
  False 修正 N==M 误判）、`_srgb_to_lab_vec`、`nearest_yarn_batch`。
  等价验证：官方 34 组（4.95e-5）+ 随机 2000 对（1.42e-14）+
  nearest 批量 500 样本零不匹配。接入 pick_yarn_palette（桶级两处）与
  网格逐像素分配。实测批量 42×（112.7ms→2.7ms/500 色）。
  **实现陷阱记录**：M 分支左端须升维 (N,1) 否则 (N,) vs (1,M) 广播失败；
  N==M 时自动判 pairwise 会误判，调用方显式 pairwise=False。
- **U23 时长模型改按针数**：`MINUTES_PER_STITCH = 2.5/36`（锚定 classic
  旧语义，classic 下数值不变）——修复审查者实测的"fine 针数 2× 时长仅
  1.3×"系统性低估（现 classic 72min / fine 140min，符合细密度更耗时
  的实际）。
- **U24 密度进导出**：Markdown 与 PDF 均附"密度（小样）"行（复现的
  第一要素）。
- **U25 分享另存**：V3+V4 修复后自然成立（rid 唯一 + style/色带随
  token），端到端测试覆盖"两次载入另存为两条记录"。

P3（V5/U26/K2/U27 落地；U28/U29/U32/U33 搁置）：
- **V5** history 入库最小结构校验（缺 analysis/params.parts 拒绝）。
- **U26** 历史搜索（summary/blob LIKE，侧栏搜索框）。
- **K2** preview 独立列（ALTER TABLE 迁移）+ list_results 随行返回，
  消除侧栏 N+1 全量读取。
- **U27** CLI 批量目录模式（`--batch-dir/--out-dir`：逐图 JSON+MD，
  非图片跳过、失败不中断、rc 汇总）。**实现陷阱**：run_batch 传
  Namespace 给 main 时须识别（parse_args 会把 Namespace 当 argv 迭代）。
- **U28/U29 模块拆分与命名统一：搁置**。881 行的 crochet_params 拆分
  是 2–3 天纯搬移 + 全量回归，当前注释文化/测试网已控制风险，且本批
  已含大量行为变更——排独立专项避免与功能变更混批。
- **U32/U33 Python 3.10+ 与依赖升级：搁置**。requires-python 变更牵动
  CI 矩阵/uv.lock/全部依赖的兼容验证，且 3.9 当前仍可运行（EOL 影响
  的是安全补丁而非功能）；排独立专项，先 U33 后 U32 的依赖链已记录。

测试增量（+15，总 574）：V1×1、V2 经由 hypothesis/矩阵扩域、
share×3（roundtrip/尺寸门控/链接载入+U25）、CLI×5（手动/本地视觉/
未知部件/门禁/批量×2）、U23/U24 经由既有断言更新。

*更新于 2026-08-29。如与代码不符，以代码为准。*

## 23. 第十六轮（Opus 5 审查第二部分 + V6）处置记录（2026-08-29）

Opus 5 第二部分 18 条（含补录 V6 与两条"建议不要做"）。其部分条目基于
上轮修复前快照（U23/U24/K2/U26/V5 已有初版），本轮按其**更优方案升级**，
其余新增落地。**585 测试 + 1 评测脚手架 / ruff 零告警**。

- **V6 CYC 署名不成立（数据诚信，P1）**：核实确认 CYC 标准只含密度与
  针号区间、不含 m/100g——曾经把 320/250/200/140 署名给 CYC 是错误
  引用，且与本项目"色号宁缺毋错"的内部标准不一致（外部审查者一查即中）。
  处置：gauge.py docstring 如实降级为"实务经验估算值"（纠正说明保留
  CYC 事实引用）；crochet_params 注释同步；结果页/Markdown/PDF 材料
  区加"以实际线标为准"免责。handoff §15 的 O3 记录原地加更正标注
  （不改写历史）。optimization-brief §2 现状描述同步。
- **U23 升级（按审查者校准方案）**：时长 = 针数×6.5s + 圈数×10s
  （每圈起头/记号扣/换线固定开销）。校准锚点：classic 默认玩偶
  1044 针/49 圈 → 121min ≈ 旧按圈值 122——**默认路径用户可见值不变**，
  只有跨密度漂移被修正（fine 229min，隐含单针耗时三密度一致 6.8–7.0s）。
  抽出 `estimate_minutes` 共用函数（refresh_derived / _build_result 两份
  重复实现合一，U28 拆分的预演）。
- **U24 升级**：密度行增加"改密度后重新生成"提示；无 gauge 键时兜底
  "未记录（按经典图解默认 13×16）"（旧备份/分享兼容）。
- **U30 双语记号对照表**：导出物（MD+PDF）附 "Stitch Key: X = sc ·
  V = 2 sc in same st · A = sc2tog…"——审查者核实的 CYC 对应关系。
  这是绕开 U9 i18n 搁置的低成本解锁（只加固定对照段，不触碰中文断言）。
  主记号体系不变（X/V/A 对 amigurumi 受众正确，与 CYC 是并行标准）。
- **V5 历史载入校验对等**：侧栏"载入"与 main.py 分享载入均改走
  `_validated_backup` + `_rebuild_params`（与备份导入同等待遇）——坏
  记录从"崩在渲染层"变为 st.error + 删除出路；分享坏 token 不进 session。
- **U25 补全（方案 b）**：无 preview 的历史行显示 🧶 占位（不把
  preview 塞进分享 token——审查者实测会推过 6000 门限）；分享载入
  提示加"存入历史"引导。
- **U26 补全**：title 列（幂等 ALTER 迁移，旧库可读）；结果页存入时
  可命名（占位符=摘要格式）；侧栏 title 优先显示；搜索命中 title。
- **U27 补全**：批量模式 ThreadPoolExecutor 并发（GrabCut 释放 GIL），
  **每图独立 orchestrator**（parser 实例状态 last_usage/last_local_meta
  并发复用会串档——审查者预警的第一个坑）；CROCHET_EVAL_DIR 真实图片
  评测脚手架（manifest 约定 + skipif + 部件命中/flare 一致性指标），
  无评测集时自动跳过。
- **U32 Python ≥3.11：尝试后回滚，搁置待专项**。3.9 已 EOL 10 个月、
  streamlit 1.62/numpy 2.5 被钉是客观事实，本轮曾改 requires-python/
  classifiers/ruff target/CI 矩阵并启用 ruff B905（zip strict=）规则——
  但本地 3.11 运行时因网络限速无法验证，且 `zip(strict=)` 是 3.10+
  特性导致 3.9 venv 全线 TypeError，**已全部回滚**（requires-python/
  classifiers/ruff target/CI 矩阵/strict= 共 7 文件）。完整方案已验证
  可行性并记录：① 3.11 venv 就绪后先跑全量 574+ 套件；② 同批启用
  B905+strict=（11 处存量）；③ CI 矩阵 3.11/3.12/3.13；④ 保留
  opencv<5 与 mediapipe<1.0 两个刻意约束。依赖升级（U33）在其后。
- **U31 品牌色号扩建**：流程已定义（官方色卡页 → 色号+URL+核实日期 →
  ΔE00≤10 才收录，"蓝色 113 近似"为边界案例需补记 ΔE），搁置待网络。

**两条"不要做"已录入 optimization-brief §3**（防未来重复投入）：
① 合并三处 GrabCut 调用点（改输出，K1 已零风险拿走收益）；
② 大图解分享工程（真实图解 token 最坏 5596 < 6000，门禁保留作防御）。

实现陷阱记录：heredoc 内嵌三引号字符串易语法损坏（本轮两次）；
`.replace()` 目标与文件实际内容不符时静默 no-op——多轮字符串手术
应使用 Edit 工具精确锚定或 assert-guard。

测试增量（+11，总 585 + 1 skipif 脚手架）。

*更新于 2026-08-29。如与代码不符，以代码为准。*

## 24. 第十七轮（Opus 5 第二次深审 F23–F36 + E 系列）处置记录（2026-08-29）

Opus 5 按 audit-brief-v2 执行第二次全面深审：14 bug + 3 取舍 + 4 增强，
9/14 来自交互面/对抗输入（§0.5 硬性要求达成）。全部处置。**586 测试 /
ruff 零告警**。

根因修复（审查者的核心判断完全正确——"单点逻辑已硬，接缝没有"）：
- **共用键集常量**：`share.py` 定义 `_BACKUP_KEYS`（10 键，含 preview）/
  `_SHARE_KEYS`（= 备份 − preview），结果 dict 的顶层键集此前在 6 条
  路径各自手抄。落地：F24 备份/导入走 _BACKUP_KEYS、F26 调尺寸补
  preview、F23 分享入口用 _SHARE_KEYS。键集相等断言进测试。

high（4/4）：
- **F23 分享只有收没有发**：U8 实现时 heredoc 编辑脚本损坏（语法错误
  中断），发送侧 UI 从未落地——encode_result 成了死代码，README 空承诺。
  结果页 col_bk3 补分享入口（token + 字符数 + `?p=` 展示），share_ 前缀
  入 purge 表。**教训已记录：多轮 .replace() 因目标文本不符会静默
  no-op（本项目三轮踩过）**。
- **F24 备份只存三键**：导入后调尺寸把一体件拆回分件、egg 退化 ladder
  （实测复现）。备份/导入改走 _BACKUP_KEYS（旧备份缺键 → None 兜底）。
- **F28 网格行数无上界**：1×10000 图 → 30 万行 → 4.5GB RSS + 2.2GB
  SVG（实测复现）。`_MAX_CELLS = 80_000` + `_MAX_GRID_WIDTH = 200`，
  `GridPattern.clamped_from` 记录原始行数，UI 诚实告知"建议先裁剪"。
  修复后 0.15s / 86MB。
- **F33 测试套件非 hermetic**：环境有 OPENAI_API_KEY 时批量测试真实打
  网络（Opus 5 首步就撞上，基线不可复现）。新增 `tests/conftest.py`
  autouse 夹具：delenv 全部外部 Key + 禁用 load_dotenv（.env 会重灌）
  + CROCHET_HISTORY_DB 提示重定向。

medium（3/3）：
- **F25 title 往返丢失**：title 在独立列不在 blob → 载入再存被 NULL
  覆盖。load_result 取回 title 写入 result；输入框 value 回填。
- **F27 批量输出撞名**：doll.png+doll.jpg → 同 stem 并发写同一文件
  静默覆盖（2 进 1 出 rc=0）。输出名带扩展消歧 + 同名分组预判。
- **F36 帽子高度口径与圆柱打架**：帽子 height 含径向帽顶盘（虚高
  ~70%），与 §8.6 圆柱判例矛盾。统一为只计筒壁（height_cm = 筒深），
  notes 明示"帽顶 N 圈径向加针盘，不计入筒深"；旧断言（含帽子 dome
  用自身最大针数推导）同步更新。

low（7/7）：
- **F29** decode 端对称门控（token 长度 + zlib 解压 2MB 上限）。
- **F30** LIKE 字面匹配：**实现陷阱记录**——`ESCAPE '\'` 的 Python/
  SQL 双层转义极易错（本轮两次踩），改用 `!` 作转义符（零反斜杠）；
  query 只搜 summary+title（blob 是 JSON 文本、键名必含 "_"，搜它
  会让 "_" 命中全部），按色筛选走 blob。
- **F31** load_result 吞解码错误返回 None（与"不存在"同出口）；侧栏
  load_result 挪进 try。
- **F32** 脱敏正则收 `*` 进字符类且门限降至 4（覆盖服务端"前5+***+后4"
  半遮蔽回显）+ 已知 Key 的前后缀脱敏。诊断信息（URL/状态码）保留。
- **F34** 评测脚手架补 dominant_color 前三断言（契约三指标全部兑现）。
- **F35** 尺寸门控测试改用 `model_copy` 真类型构造（裸 dict 会触发
  pydantic UserWarning）；pyproject 加 `filterwarnings = ["error::UserWarning"]`。
- **E3** `hist_title_` 补进 _WIDGET_KEY_PREFIXES（F-8 顺带证实了真
  session_state 的 .keys() 安全可用——v1 §9 的限制只针对测试代理）。

取舍（T1–T3）与增强（E1/E2）：
- T1 allow_wide_jump 可被 JSON 修正置 true：**判为取舍**——UI 自检是
  咨询性的、真门禁在生成侧（用户碰不到标志）。若将来升级 UI 自检为
  门禁，需区分生成器置位与用户置位（`_rebuild_params` 剥离该键）。
- T2 estimate_minutes 下限 30：合理（含备料收尾），docstring 已补说明。
- T3 波浪摆 hem_st*2 无上界：工艺定义使然，schema le=50 已兜底。
- **E1 零宽/BiDi 控制符剥离（落地）**：`_strip_invisible` 进色样胶囊与
  PDF esc——LLM 自由文本字段（parts/色名）是显示欺骗面的真实入口。
- E2 row 重复/乱序不校验：记录待议（显示层混乱，算法无影响）。
- E4 历史载入恒写照片 Tab 槽位：记录待议（origin_slot 方案）。

**负面结果（Opus 5 §5.F，8 条已验证无问题的面）**：分享 token 4 轮
循环零衰减、批量失败隔离与实例隔离成立、8 类对抗图片安全降级、PDF
转义无残余、fake SDK 与真实 openai 2.48 形状一致、purge 在真
session_state 下 .keys() 安全、1800 组塑形矩阵零失败、JSON schema 拦
负数/零针数。已录 audit-brief-v2 §5.F，下轮不必重扫。

测试增量（+2，总 586）：批量撞名消歧、（hermetic conftest 使全部
既有测试获得防网络保护）。

*更新于 2026-08-29。如与代码不符，以代码为准。*

## 25. 第十八轮（Opus 5 第三次深审 G1–G10）处置记录（2026-08-30）

Opus 5 按 audit-brief-v3 执行第三次全面深审：10 条发现（G1–G10），
7/10 出自 v2 的修复代码，其中 G1 是"修复的修复"（F24 写入侧修了但读
侧从未落地）。**589 测试 / ruff 零告警**。

全部修复（按审查者推荐顺序）：
- **G8 键集断言先行**：share.py 注释承诺"钉死在结构层"的键集断言
  此前从未写。新增 `tests/test_key_sets.py`——3 条：_SHARE_KEYS ⊂
  _BACKUP_KEYS、_BACKUP_KEYS ⊇ orchestrator 产出键、备份导入后全部
  _BACKUP_KEYS 键值一致（G1 的直接检测器）。
- **G1 备份导入丢九键（high）**：`imported.setdefault(k, None)` 把
  style/gauge/color_bands/spans 等全写 None——F24 的写入侧（备份
  JSON 含全部键）修了但读侧（导入回填）用的是 setdefault(k, None)
  而非 data.get(k)。一行修复。**二次踩坑**：初版修复把 data.get(k)
  应用到全部 _BACKUP_KEYS 包括已处理的 analysis/structure/params，
  覆盖了 _rebuild_params 的 CrochetPart 对象 → 'dict' has no attribute
  'name'。修正：循环排除已处理三键。
- **G2 GrabCut 丢头过面积门（high）**：GMM 内部判定翻转使头部整块
  丢失但总面积占比 0.128 稳过 [0.05,0.95]。**审查者实测否定了三个
  常数假设**（FGD 下限/Otsu 钳位/覆盖率门槛均无需改）——真凶是
  GrabCut 的 GMM 内部行为。修复：新增区域校验——顶部 1/3 主体占比
  < 1% 视为丢头，回退启发式。正常人形/双色背景/低对比度全部不回归。
- **G3 钳制提示不可达**：tab_grid 的 grid_view 字典缺 clamped_from。
  一行补齐。
- **G5 conftest 相对路径**：CROCHET_HISTORY_DB="test-history-db-unset"
  在仓库根产出文件。改为绝对 /tmp 路径。
- **G6 零宽/BiDi 剥离 2/3 出口**：exporters._md_cell 补 _INVISIBLE
  剥离（与 result_renderer/pdf_export 同源）。
- **G7 --batch-dir 不在互斥组**：与 --image 同给时 --image 被静默忽略。
  移入互斥组；同时补 --pdf 批量逐图导出（不再硬置 None 后静默丢弃）。
- **G4 高度口径双标**：结构表（设计意图比例）vs 图解（实际交付尺寸）
  差 +8%~+140%——**判为设计意图而非 bug**（结构层是 Q 版先验骨架，
  参数层按 gauge/塑形/剖面重算）。structure_designer docstring 加
  口径说明。
- **G10 MINUTES_PER_ROUND 死常量**：U23 换模型后全仓零引用，删除。
- **G9 文档**：handoff §14 占位补齐；audit-brief-v2/v3 侧栏行数
  137→159。

审查者的两条额外贡献：
- **§4.C 前提数字修正**：20cm 头径 classic 侧壁实为 22 圈 ≈ 13.8cm
  （非任务书误写的 12 圈 ≈ 7.5cm）。
- **§5.F 负面结果 9 组**（分享 token 4 轮零衰减、批量隔离成立、8 类
  对抗图片安全降级、CIEDE2000 边界无问题、purge 真 session_state 安全
  等）已录 audit-brief-v3 §5，下轮不必重扫。

**审查者对 |Δ|≤6 的量化校准**（增强，列专项）：profile_shaping.py
Δ = 2π·(行高/针宽) 按 gauge 实算 classic 5.1 / fine 7.9——当前硬编码
6 对 classic 偏松、fine 偏紧。改它会动全部生成器不变量，列增强专项。

测试增量（+4，总 589）：键集断言×3、G1 端到端×1。

*更新于 2026-08-30。如与代码不符，以代码为准。*

## 25A. G2 修复迭代记录（2026-08-30）

G2（GrabCut 丢头）的首版修复用"顶部 1/3 GrabCut 掩码占比 <1%"判定——
但坐姿/远景照顶部本来就空（正常构图），被误拒。升级为"启发式 vs 掩码
交叉判定"后仍有两轮踩坑：
1. 首版用 `estimate_background`（众数）做交叉——双色背景（白墙+地板）
   时地板色被当众数 → 白墙被误标为非背景 → 触发丢头判定
2. 改用 `px_min_dist`（到全部背景代表色的距离）后正确——白墙距最近
   背景色 ≈0，不会被误判为非背景

最终实现：`px_min_dist` 与 GrabCut 掩码做同一区域的交叉比对。附带
教训：`estimate_background` 未在延迟 import 中导入导致 NameError 被
宽 `except` 吞掉 → 全部场景返回 None（pytest 8 失败立即暴露）。
**genius 与 garbage 之间只隔一行 import。**

四场景终验：站立 ✓ 坐姿 ✓（不再误拒）双色 ✓ 低对比 ✓。589 全过。
