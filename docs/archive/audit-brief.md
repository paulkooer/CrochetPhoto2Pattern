# CrochetPhoto2Pattern 审核要求（Audit Brief）

> 交给独立严格审查者（AI 或人）的完整审核任务书。目标：在 30 分钟内建立
> 准确心智模型，然后按本文指定的优先级与格式产出审查结论。
> 本文档由当前维护者整理，如实陈述，不回避弱点。

---

## 0. 审查目标与产出要求

**角色**：你是一名严苛但公正的资深审查者。你的产出将被直接用于修复决策，
因此每条发现必须可执行、可复现、可反驳。

**产出格式（对每条发现）**：

```
[严重度] 编号 — 一句话标题
位置: 文件:行号（必须精确到行）
类别: bug | 领域错误 | 安全面 | 性能 | 可维护性 | 文档失实
证据: 复现脚本（可直接运行）或逐行推理链；禁止"看起来可能"式推测
影响: 用户可见的行为是什么
建议: 具体修法（一两句，能落地的）
```

**硬性纪律**：

1. **先复现，再上报**。写不出复现脚本或完整推理链的发现不要提交。
2. **先读 §7（刻意设计清单）与 §9（历史误报清单）**，历史上约 1/3 的外部发现
   是误报（多为不知道领域惯例或读漏了注释），重复误报会浪费双方时间。
3. 区分三档：`bug`（行为与声明不符）/ `取舍`（有意为之，可质疑但标注
   为讨论）/ `增强`（新能力建议）。
4. 严重度定义：`blocker`（崩溃/数据损坏/安全）· `high`（用户可见错误）·
   `medium`（边界条件/体验）· `low`（打磨）。
5. 不要给"建议加测试"这类无具体指向的意见；要么指出具体未覆盖分支与
   期望断言，要么不提。

---

## 1. 系统一句话定位

上传一张照片（或手动输入参数）→ 生成可照钩的 Amigurumi（立体钩织玩偶）
图解：逐圈针数（标准符号记法 X/V/A）、逐圈配色与换线、**逐色材料清单
（克重+米数）**、装配说明、进度勾选、**图解自检**、**环形圈数图**。
Streamlit 单体应用，本地运行，LLM 可选（AI/本地视觉/Mock 三模式），
支持中转站（自定义 Base URL）。

## 2. 必读材料（按序）

1. `docs/flow.md` —— 架构与数据流（10 分钟）
2. `docs/handoff-review.md` —— **§3 刻意设计、§4 已知局限、§8 历史修复
   索引必读**；§9–§19 是十二轮外部审查/优化的处置记录（skim 即可，
   但引用历史结论时以代码为准）
3. 本文档 §5–§10 —— 重点审查面、刻意设计、已知局限、误报史、陷阱

## 3. 当前基线（先跑通再开始）

```bash
cd CrochetPhoto2Pattern
.venv/bin/python -m pytest -q --cov=app        # 278 tests, ~90%（基线，先确认全过）
.venv/bin/python -m ruff check app tests       # 零告警
VIRTUAL_ENV=.venv uv build --wheel -o /tmp/w .  # wheel 打包（prompts 必须在内）
.venv/bin/python -m streamlit run app/main.py   # 手动 UI（无 Key 可玩本地/手动/网格）
```

环境事实：Python 3.9.6（`.venv`，uv 管理）；可选依赖 reportlab 已装，
mediapipe **未装**（`[pose]` 路径走回退，测试全覆盖该回退）；平台
macOS arm64；CI 为 `.github/workflows/ci.yml`（py3.9–3.12 矩阵）+
`extras.yml`（[pdf]/[pose] 矩阵，pose 作业兼作 opencv-contrib 覆盖
headless 的金丝雀）。

## 4. 模块地图（行数 ≈ 审查优先级）

| 模块 | 行数 | 职责 | 审查优先级 |
|---|---|---|---|
| `models/crochet_params.py` | 840 | **领域核心**：圈数代数（球/柱/杯/裙/帽/理想球/蛋形/头身一体/照片剖面）、语义配色融合、材料/装配/时长派生、refresh_derived | ★★★ |
| `ui/result_renderer.py` | 531 | 结果页状态机：widget 命名空间/purge/过期勾选清理、快速调尺寸重生成、JSON 修正、备份导入（校验）、历史存取、逐色材料/色样/徽章/环形图渲染 | ★★★ |
| `models/image_parser.py` | 407 | Vision 双路径（Anthropic messages.parse / OpenAI parse→严格 schema+重试→legacy json_object）、中转站 base_url、色板直量化、Mock | ★★★ |
| `models/subject.py` | 204 | GrabCut 主体分割：三档种子（Otsu 阈值+人脸框 FGD）、确定性背景条带、腐蚀、退化回退 | ★★ |
| `models/pose.py` | 206 | 姿态实测 span（可选依赖，mediapipe<1.0）：模型下载+SHA256、人体学映射、span hints 进 prompt | ★★ |
| `models/colors.py` | 217 | 毛线色表（MST 锚点扩充）、CIEDE2000（**官方 34 组数据锁定**）、pick_yarn_palette 直量化 | ★★ |
| `models/local_vision.py` | 201 | 无 LLM 路径：人脸检测/头身比例/剖面/flare（主体范围内取窗） | ★★ |
| `models/color_design.py` | 199 | 纵向色带（GrabCut 优先+空带延续）、PART_SPAN 先验、背景估计 | ★★ |
| `models/profile_shaping.py` | 199 | 剖面→筒壁针数（±6 钳制）、线性插值采样、strip_dome、侧影 SVG | ★★ |
| `models/grid_pattern.py` | 235 | 2D 网格（直量化色板）、C2C 逐行指令、图例/文字图 | ★ |
| `models/validator.py` | ~60 | 图解自检（针数代数/加减不共存） | ★ |
| `models/ring_chart.py` | ~90 | 环形圈数图 SVG | ★ |
| `models/gauge.py` | 144 | **密度单一来源**：三预设+custom、克重/米数换算、钩针标签 | ★★ |
| `models/orchestrator.py` | 134 | 管线协调：pose→parse(hints)→结构→参数，result 全量透传 | ★★ |
| `utils/history.py` | ~90 | SQLite 历史（model_dump 序列化，path 可重定向） | ★ |
| `utils/pdf_export.py` | 129 | PDF 导出（reportlab CID 中文字体） | ★ |
| `ui/tab_photo.py` | 151 | 上传/解析模式 radio（有效 Key 判定）/进度/空状态 | ★ |
| `ui/sidebar.py` / `tab_manual.py` / `tab_grid.py` | ~330 | 侧栏（Key/密度/塑形/历史）、手动、网格 | ★ |

测试 28 文件 / 278 用例，其中 `test_eval_baseline.py` 是**合成真值评测**
（容差有物理依据，见 §5-E7）；`test_colors.py` 内置 CIEDE2000 官方
34 组参考数据。

## 5. 重点审查面（按此顺序投入精力）

### A. 领域代数（历史最高危区）
- 加/减针"隔N针"口径：`(aX,V)×6` 的 a = before//6−1、`(aX,A)×6` 的
  a = before//6−2，镜像对称圈隔数相同——曾错两轮才修对，有双重测试锁定。
  逐个生成函数（`_sphere_rounds`/`_cylinder_rounds`/`_cup_rounds`/
  `_ideal_sphere_rounds`/蛋形/头身一体 `_merge_head_body`/裙/帽/照片
  剖面）手工推演 2–3 组具体数字。
- `_merge_head_body` 的颈部对齐（head_kept 截断逻辑）与 ±6 重钳制。
- 理想球：θ 定义、egg 变体、眼睛定位 `eye_round` 的圈号换算。
- **6 的倍数量化的精度下限**：直径误差 ≤ ±6·w/π/2（fine 密度 0.48cm）
  ——评测基线已锁定，报"直径不准"前先算这个。

### B. 状态机与渲染（result_renderer）
- widget key 生命周期：result_id 命名空间、`purge_result_state` 前缀表
  是否覆盖全部新前缀（sz_/pdf_/hist_/dl_pdf_…）、圈数增减时勾选复活问题
  （删减有清理，**增加时旧键复活**是否可能？从未测过增长方向）。
- 快速调尺寸重生成：换 rid 后各 session 标志的键正确性；pose/color_bands
  透传完整性。
- 历史载回：跨会话恢复的 result 缺新字段（spans/style/color_bands）时
  的 .get 回退是否全部安全。
- 两个 Tab 同屏（photo+manual）+ 历史载入三方共存时的 key 冲突。

### C. 视觉管线常数（启发式的合理性）
- `subject.py`：条带宽度 kt/ks=h//12、覆盖率门槛 0.15、Otsu 钳位
  [16,96]、FGD 阈值 2T、腐蚀 1px、退化区间 [0.05,0.95]——每个数都
  值得质疑：什么照片会让它失效？
- `local_vision.py`：头径锚 9cm、比例钳位 [2,8]、flare 窗口
  (0.72–0.95)/(0.42–0.62)、subject 行阈值 0.08。
- `pose.py`：人体学映射系数（头底=鼻+0.4·肩距、头顶=眼上方等距）、
  可见性阈值 0.5——坐姿/抱物/儿童比例下的表现。
- `color_design.py`：背景距离阈值 48、空带延续策略对 PART_SPAN 消费方
  的连带影响。

### D. 安全面
- Prompt injection 链路：图片内文字→LLM 输出→哪些字段进了
  unsafe_allow_html？（recommended_colors/材料 item/notes——逐一确认
  html.escape 覆盖；`_yarn_chip_html` 只转义色名，**quantity** 的转义
  是否完整？）
- 模型下载：URL 固定+SHA256 锚定，但 `CROCHET_POSE_MODEL` 用户自备
  路径跳过校验（文档声明的取舍）——评估是否可接受。
- SQLite：参数化查询 ✓；`CROCHET_HISTORY_DB` 指向任意路径的文件写入。
- API Key：中转站 base_url 注入 SDK 后的错误信息是否会回显 key？
  session_state 中 key 的滞留面（orchestrator 不缓存的理由见 §3-D5）。

### E. 测试的真实性（"假信心"面）
- OpenAI/Anthropic 调用层是 fake SDK：只锁定我方参数，**不证明真 API
  兼容**（handoff §5 已声明）。S2 的 parse 路径新增后，fake 的属性形状
  （`message.parsed/refusal`）是否与真实 SDK 一致？对照已装 SDK 源码核。
- 评测基线容差：`test_eval_baseline.py` 的 ±0.06/±0.48 等数值是否
  有依据、是否会掩盖回归。
- AppTest 覆盖不到的：file_uploader 交互、真实浏览器渲染、PDF 视觉
  效果、环形图几何正确性的目测验证。

### F. 文档与代码一致性
- handoff §0–§19 中任何与本轮代码不符的陈述（历史上每轮都产生过漂移）。
- README 功能清单逐条对照实现。

## 6. （预留）你的发现清单

[高] F13 — 蛋形头与头身一体组合可生成代数错误的跨圈跳变
位置: app/models/crochet_params.py:686
类别: 领域错误
证据: 默认 classic 密度、头径 11cm、总高 14cm、sphere_mode=egg、one_piece=True 时，一体件 R10=42 针、R11=30 针，但 R11 仅记录 decrease=6，且说明为 `(5X,A)×6`，实际只能从 42 减至 36。`validate_pattern` 明确报告“第 11 圈：针数 30 ≠ 上圈 42 + 0 − 6 = 36”。遍历 UI 可达的三个预设、头径 4–20cm、总高 10–60cm 后，classic+egg 共发现 98 个失败组合。
影响: 用户按针数表需要单圈减 12 针，按文字说明则得到 36 针；两种执行结果互相矛盾，并违反相邻圈 |Δ|≤6 的硬约束。
建议: 不要将目标颈围直接附加到 head_kept。建立通用的 `bridge_rounds(current, target)`，按每圈最多 ±6 逐步过渡并为每圈重新生成 increase/decrease/notes；生成完成后强制调用 `validate_pattern`，失败则拒绝返回图解。

[高] F14 — 中转站异常文本可把 API Key 原样回显给用户和日志
位置: app/models/image_parser.py:355
类别: 安全面
证据: 构造一个中转站 SDK，使其抛出 `401 Unauthorized: relay rejected key sk-ant-SECRET123`。`_parse_anthropic` 将原异常通过 `RuntimeError(f"...{e}")` 原样包装，`parse_image` 又把各 provider 错误拼入最终异常；实测最终用户错误消息和 logger 均包含完整 `sk-ant-SECRET123`。
影响: 恶意、错误配置或过度详细的中转站可令 API Key 出现在 Streamlit 页面、终端日志、日志采集平台或截图中。
建议: 在 provider 边界统一使用 `_redact_secrets(message, known_keys)`，遮蔽当前 OpenAI/Anthropic Key、Bearer 值和常见 `sk-*` token；用户侧只显示错误类别和 request ID，完整异常仅在完成脱敏后写日志。

[中] F15 — 部分 pose 结果会关闭缺失部件的 PART_SPAN 回退
位置: app/models/color_design.py:164
类别: bug
证据: `measured_spans` 在膝盖不可见时返回头部、身体、手臂、帽子和耳朵，但不含腿部、裙子和尾巴。`(spans or PART_SPAN).get(part_name)` 在 spans 非空时只查询该不完整字典。实测同一组三段色带：无 pose 时腿部得到蓝色、尾巴得到红色；传入上述部分 spans 后两者所有圈的 color 均为 None。该行为也与 pose.py:186“非法部件回退先验”的注释不符。
影响: 启用 pose 后，裁掉膝盖、关键点低置信或本就无法测量的部件反而失去照片配色，质量低于未启用 pose 的路径。
建议: 逐部件回退为 `span = (spans or {}).get(part_name, PART_SPAN.get(part_name))`，或在 orchestrator 中先执行 `{**PART_SPAN, **measured}` 合并；增加缺膝、缺腕、尾巴不可测三类回归测试。

[中] F16 — 头身一体件的高度把底部收口圆盘按垂直高度累计
位置: app/models/crochet_params.py:735
类别: 领域错误
证据: 默认 9cm 头、18cm 总高、classic 密度得到一体件 28 圈、height_cm=17.5。末尾存在 30→24→18→12→6 的五圈收口梯，其 3.12cm 被全部计入垂直高度；独立身体路径明确排除起底圆盘，只报告 5.6cm 筒壁高度。按同一口径，头径 9cm+身体筒壁 5.6cm 约为 14.6cm，而一体件多报约 2.9cm。dk/fine 下收口部分被分别多计约 5cm。
影响: UI、Markdown、PDF 和快速尺寸判断展示的一体件成品高度明显偏大，密度越细偏差越大。
建议: 一体件高度按“头部成品高度 + 身体筒壁高度”计算，不以全部圈数乘 row_h；把身体闭合阶梯作为径向收口排除，并用 classic/dk/fine 三预设锁定高度口径。

[中] F17 — 照片剖面身体在最后一圈保持开口，却提示“收针前填充”
位置: app/models/crochet_params.py:597
类别: 领域错误
证据: 构造有效 body_profile 后，生成身体末圈可停在 36X，increase=decrease=0，notes 仅为“36X（不加不减）”；部件说明却写“收针前填充棉花”。对照普通 cylinder 身体会继续生成减针圈，并在末圈明确“断线留15cm用于缝合”。
影响: 用户无法判断剖面身体顶部应保持开口供头部缝合、继续减针收口，还是直接断线；按“收针前填充”理解时图解本身没有提供任何收针步骤。
建议: 明确 profile 身体的拓扑约定。若身体用于接头，末圈追加“保持开口，填充后断线留15cm缝合”；若要求闭合，则通过通用 bridge/closure 生成器逐圈减至目标颈围或 6 针。

[中] F18 — 帽子筒壁深度在 dk/fine 密度下只剩一圈
位置: app/models/crochet_params.py:562
类别: 领域错误
证据: 9cm 头对应帽径 10.3cm。classic 生成 7 圈帽顶圆盘+3 圈直壁，直壁仅 1.88cm；dk 为 9 圈圆盘+1 圈直壁，直壁 0.71cm；fine 为 11 圈圆盘+1 圈直壁，直壁 0.62cm。代码显示的 6.2/7.1/7.5cm “帽高”主要来自帽顶圆盘，而非可覆盖头侧面的深度。
影响: dk/fine 预设下生成的成品近似平圆片或极浅小帽，难以稳定佩戴，却在说明中宣称“不收口可直接佩戴”。
建议: 将帽顶半径和帽侧深度分开建模；侧壁圈数直接由目标覆盖深度除以 row_h 得出，再加帽顶圆盘圈。为三种 gauge 添加最小直壁深度断言。

[中] F19 — 环形图超过 14 圈后标签发生精确像素重叠
位置: app/models/ring_chart.py:65
类别: bug
证据: `_sphere_rounds(36)` 生成 17 圈。标签纵坐标使用 `(i % 14) * 18`，实测 R1 与 R15、R2 与 R16、R3 与 R17 分别落在完全相同的 x/y 坐标，共三个标签不可读。常规 9cm classic 头即能触发。
影响: 环形图的后几圈标签覆盖前几圈，用户无法可靠读取圈号、针数和颜色，导出的视觉说明失真。
建议: 不要对 y 坐标取模。可按圈数动态增加 SVG 高度、将标签拆为可滚动图例，或只标变化圈并把完整圈表保留在旁侧；增加“所有 label 坐标唯一”的测试。

[低] F20 — result_id 清理前缀漏掉两个实际状态键
位置: app/ui/result_renderer.py:21
类别: 可维护性
证据: 静态枚举所有由 result_key 构造的状态键后，`pdf_gen_{result_key}` 和 `sz_{result_key}` 不在 `_WIDGET_KEY_PREFIXES` 中；替换结果时 `purge_result_state` 不会删除它们，其余前缀均可覆盖。
影响: 长会话反复生成或导入结果后会残留无效 session_state 项；当前通常不串档，但破坏了“旧结果状态全部清理”的设计约束并造成缓慢内存增长。
建议: 补入 `pdf_gen_` 和 `sz_`，并新增测试自动扫描或集中通过一个 key 工厂登记所有 result-scoped 状态，避免以后再次漏项。

[低] F21 — README 功能列表包含字面量 `\\n`
位置: README.md:13
类别: 文档失实
证据: 文件中 `毛线色表\\n- 🖩 网格缩放算法可选` 含两个普通字符反斜杠和 n，而非真实换行；脚本统计发现一个字面量 `\\n`。
影响: GitHub 页面会把两个功能渲染在同一列表项并显示 `\\n`，功能清单可读性受损。
建议: 将字面量 `\\n` 替换为真实换行。

[低] F22 — flow 与 handoff 仍把已完成的 PDF 和历史记录列为未来能力
位置: docs/flow.md:56
类别: 文档失实
证据: flow.md:56–57 仍将 PDF 打印导出和图解历史列入扩展路线图；handoff-review.md:102 仍写“无服务端持久化、无 PDF 导出”。当前代码已有 app/utils/pdf_export.py、app/utils/history.py 及结果页入口，handoff-review.md:458 自身也记录了 S4 已完成。
影响: 新审查者和使用者会误判当前能力边界，可能重复提出已经落地的工作。
建议: 把 PDF 与本机 SQLite 历史移入“已实现功能”，仅保留“无服务端/跨机同步、无预设模板库”等尚未完成部分。

### 优化实施顺序

1. **P0 安全止血**：先完成 F14 的异常脱敏，并补 provider 异常、聚合异常、日志脱敏测试。
2. **P0 图解正确性门禁**：修复 F13，引入通用渐变桥接器；让所有生成路径在返回前通过 `validate_pattern`。新增参数化测试覆盖全部 gauge、sphere_mode、one_piece 和 UI 尺寸边界。
3. **P1 几何与工艺口径**：依次处理 F16、F17、F18，将轴向高度、径向圆盘、开口/闭口拓扑拆成明确字段或辅助函数。
4. **P1 配色降级链**：修复 F15，保证 pose 是逐部件增强而不是全局替代。
5. **P2 展示与状态**：处理 F19、F20，增加 SVG 坐标唯一性测试和 result-scoped key 注册机制。
6. **P3 文档收尾**：处理 F21、F22，并在 handoff 中记录本轮修复及新增回归测试。

### 三档分类统计

- bug：7（F13、F14、F15、F16、F17、F19、F20）
- 取舍：1（F18，可接受浅帽设计时应明确标注，而非宣称可稳定佩戴）
- 增强：2（F21、F22）

### 已核验但不提交为发现

- 278 tests 全通过，覆盖率 90%，ruff 全通过。
- OpenAI 2.48.0 的 `chat.completions.parse` 和 Anthropic 0.122.0 的 `messages.parse` 参数及解析结果属性与现有调用一致。
- unsafe_allow_html 链路中的色名、quantity、环形图文本和网格图例均完成转义，未复现 HTML 注入。
- checkbox 圈数缩短后再增长不会复活已删除键；仅增长时保留相同圈索引的完成状态符合现有语义。
- sin 球末圈不强制收到 6 针属于 §7 E4 的刻意设计，不重复上报。

## 7. 刻意设计决策（勿报为 bug——完整清单）

> 本清单**并入并扩展** handoff §3 的 D1–D16（新增 E15–E19 为近三轮
> 引入），两处有出入时以本清单为准。

密度/几何：
- E1 gauge `classic` 预设 w/h=1.23 超物理区间——"图解惯例 vs 物理"的
  已记录取舍（保持 36针=9cm头 锚点），dk/fine 预设物理正确。
- E2 针数恒为 6 的倍数、相邻圈 |Δ|≤6——Amigurumi 惯例+物理极限。
- E3 圆柱/帽标注高度只计筒壁圈（起底圆盘不计高）。
- E4 sin 球末圈 ≤12 针属物理必然，配"勿再减针收成 6 针"原文工艺警告。
- E5 密度常数（克重/时长）是需试钩校准的启发式，注释已声明。

架构/语义：
- E6 `CrochetPart.rows` 是派生 property 非存储字段（消灭失同步）。
- E7 schema 上限比 prompt 宽（两层：prompt 管常规，schema 拦离谱）。
- E8 parts 不用 Literal 枚举，validator 去重——LLM 变体宁可降级小球。
- E9 orchestrator 不用 @st.cache_resource——API key 进程级滞留风险。
- E10 `recommended_colors` 本地量化永远优先于模型输出。
- E11 中转站 base_url：UI > env > 默认；空串归一 None。
- E12 mediapipe 钉在 <1.0（1.0.1 macOS arm64 原生崩溃，已实机证实）；
  必须**可选依赖**——它拖入 opencv-contrib 5.x 与主依赖
  opencv-python-headless<5 冲突（D8）。二者不可共存是约束根源。
- E13 pose 未检出/离线 → 回退 PART_SPAN 先验（实测只是增强，不是依赖）。
- E14 mock 数据带水印（vision_meta.source=mock 全链路可辨）。
- E15 无 Key 的"Mock"选项只在真正无 Key 时出现（N1 修复：有 Key 时
  Mock 与真实调用语义反转的历史 bug）。
- E16 抽取/换算容差：6 倍数量化半步、银行家舍入改 int(x+0.5)、
  逐色材料下限 5g/色、分组材料下限 20g。
- E17 备份导入对 params 重建但对 analysis/structure 只做形状校验
  （结构层深度校验的成本/收益未做）。
- E18 C2C 从左下角起、行方向来回交替——社区常见口径的一种，
  未穷尽所有地区习惯。
- E19 环形图只画顶视图（顶=起针），未做 3D 缠绕可视化。

## 8. 已知局限（只评估严重度，勿当新发现）

1. 单图信息极限：背面厚度靠常识；头径锚 9cm（本地模式）。
2. pose 不可用时部件分段仍为先验（PART_SPAN）。
3. 旋转体假设：profile 身体件=剖面×圆截面，非圆截面（坐姿扁平）不准。
4. tab_photo 上传交互无 AppTest 覆盖（AppTest 无 file_uploader API），
   `utils/images.py` 缓存分支同理。
5. 无真实 API 集成测试（fake SDK）；S2 strict parse 未对真 API 验证。
6. 网格/环形图/PDF 的视觉效果无自动化目测。
7. mediapipe 0.10.x 实机验证因网络限速未完成（1.0.1 崩溃已证实）。
8. 历史记录无加密/无跨机迁移（单用户本地工具定位）。

## 9. 历史误报清单（勿重复——每条都真实发生过）

1. 网格 aspect_ratio 补偿方向——被误报"反了"**两次**（推导在
   grid_pattern.py 注释）。
2. 减针"隔N针"口径——外部第一轮给了错误修法，导致第二轮才修对。
3. "anthropic>=0.95 需要 upgrade 才有 messages.parse"——实测 0.95 已含。
4. sin 球"末圈停在 12 针没收到 6 针"——物理必然+原文工艺，非缺陷。
5. 裙子腰部"应该是圆盘"——闭口圆盘根本套不进身体（F1）。
6. 圆柱标注高度含起底圆盘——计入会把 4.5cm 身体标成 9.4cm（F3）。
7. "经典密度 w/h=1.23 反物理"——已记录取舍（E1），报了也不改默认。
8. "material 分组应按颜色"——已在 T2 实现（提之前先看代码）。
9. "缺少 LICENSE"——已在 T1 修复（引以为证：这类发现也曾真实存在，
   但请先检查当前状态）。

## 10. 审查者陷阱（工具/框架行为，非本仓 bug）

- **AppTest**：session_state 无 `.keys()` 方法（可迭代但无该方法）；
  unkeyed widget set_value 不生效（需显式 key）；无 at.file_uploader；
  主区 widget 先于 sidebar；radio options 换代时残留值会被框架隐式
  重置（1.50 实测）。
- **Streamlit**：expander 内交互触发 rerun 后收起（框架默认）；
  st.success 后立即 st.rerun() 消息不可见（用 session 标志规避——
  标志必须以**新** result_id 为键，S4/S9 都踩过）。
- **mediapipe**：1.0.x macOS arm64 原生崩溃；0.10.x 的 tasks API 与
  1.0 同构但路径 import 方式不同（`vision.PoseLandmarker` 直属）。
- **环境**：`uv build` 前删 `build/`（setuptools 复用陈旧产物）；
  项目 venv 是 `.venv`（py3.9.6），handoff §7 早期描述的"user-site
  无 venv"已过时；opencv-python-headless 与 opencv-contrib-python
  不可共存于同一 venv（E12）。
- **fake SDK 测试**：mock 路径 `monkeypatch.setitem(sys.modules,
  "openai", fake_mod)`——注意函数级 import（`from openai import
  OpenAI`）在 patch 后的解析时机。

## 11. 时间预算建议

- 30 分钟：跑通基线（§3）+ 读 flow.md + handoff §3/§4/§8 + 本文档。
- 2–4 小时：A 领域代数手工推演（最高价值）+ B 状态机边界。
- 2 小时：C 视觉常数压力测试（构造失效照片）+ D 安全面走查。
- 1 小时：E 测试真实性 + F 文档一致性。
- 汇总：按 §0 格式输出，按严重度排序，附"三档分类"统计
  （bug N / 取舍 M / 增强 K）。

---

*整理于 2026-08-29，对应 278 tests / 12 轮演进。如与代码不符，以代码为准。*
