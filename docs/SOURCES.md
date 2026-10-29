# 外部规则参考证据（图解来源索引）

**简体中文** | [English](SOURCES.en.md)

本系统使用公开图解中的规则案例核对领域假设；公开发表不等于已证明可钩，
人工提取必要的针数代数与圈结构事实，先做机械核对，再落成可运行的测试夹具
（[`tests/test_reference_patterns.py`](../tests/test_reference_patterns.py)，
夹具总数以
`uv run pytest tests/test_reference_patterns.py tests/test_reference_grid.py
--collect-only -q` 为准，不在文档中手工维护）。真实图解五次推翻生成器
先验，校验器随之修正——每处修正的
证据都在下表。这里只做参考验证，不训练或微调模型权重；仅取针数代数与圈结构，
不复制创作文本或图解图片（遵循各源版权声明）。

## 2026-10-29 隐形减针语义与圈号一致性

再次核对 [PlanetJune 隐形减针教程](https://www.planetjune.com/blog/amigurumi-help/how-to-crochet-an-invisible-decrease/)
的动作定义。原教程将 invdec 作为独立工艺说明；本系统词表也已区分它与普通 sc2tog，
但旧操作树因二者都消耗 2 针、产出 1 针而将 `inv-sc2tog` 归并为 A，导致规范写法和
DSL 丢失工艺标记。这是本系统的语义归并问题，不能由计数通过来证明工艺等价。

本轮保留 `inv-sc2tog` 叶节点及紧凑重复组。Markdown 的规范操作式保留该标记，
原说明与 PDF 仍保留用户文字。当前 DSL 子集不翻译隐形减针的具体动作，因此在该圈
停止并报告部分导出；符号条和逐针图也明确待核对，不自动改成普通 A 或 FLO 减针。
单独的 `invdec`、中英文工艺提示同样触发人工核对，不据此猜读完整操作式。

| 自制输入 | 原行为 | 当前行为 |
|---|---|---|
| `2X,inv-sc2tog`，4→3 | 规范化为 `2X,A`，DSL 输出 `2sc,sc2tog` | 保留 `2X,inv-sc2tog`；DSL 报告该圈未支持 |
| 隐形减针提示与 FLO/BLO 并用 | 部分写法可能丢失工艺关系 | 明确需人工核对；接裙编辑拒绝自动预留 |
| 原圈号 7、19、23 | 旧环形图和符号条显示 1、2、3 | 保留实际圈号；旧无标签数据使用圈序回退 |

`tests/test_technique_fidelity.py` 使用自制案例验证计数与工艺身份分别保留、嵌套及长
重复组、编辑/备份/打印、部分导出的实体计数、接裙拒绝的原子性，以及圈号与截断标题。
导出缓存版本为 7；没有新增实体试钩或外部仿真证据。

## 2026-10-29 GitHub 同类项目对照与逐针连接

本轮直接阅读项目维护者的仓库说明及领域文档，按当前本地视觉、显式操作式和工程保存
架构筛选改进；这些是实现思路参考，不是本系统的照片或实体试钩证据。

| 项目与本轮核对的原始资料 | 可借鉴的事实 | 结合当前系统的处理 |
|---|---|---|
| [CrochetPARADE 能力说明](https://github.com/stassev/CrochetPARADE/blob/main/capabilities.md) | 用针目连接图辅助检查，并支持针目定位和图形导出 | 本轮增加相邻圈的针目来源图；保持既有 DSL 出口，不引入其计算或物理仿真代码 |
| [stitch-grapher README](https://github.com/bilgesucakir/stitch-grapher) | 区分顺序边 `NEXT` 与来源边 `PARENT`；加针和减针对应一对多、多对一 | 本轮只绘制来源关系，明确不表示线股路径；沿用本系统已有的局部 FLO/BLO 语法 |
| [KnittingPatternMaker 领域约定](https://github.com/John-Donnelly/KnittingPatternMaker/blob/main/docs/KNITTING_NOTES.md) | 把图表读取方向和工艺假设写成可检查规则 | 本轮明确针序以操作式起点编号；不把该项目的平针正反面规则搬入玩偶螺旋圈 |
| [Tesserow 使用说明](https://github.com/deiussum/tesserow) | 手工编辑网格与逐行说明保持联系，编辑受具体工艺约束 | 作为网格工作流的后续参考；本轮不将马赛克钩织的约束用于现有 C2C 或玩偶图解 |

已落地：自主编写 `stitch_connections`，从已有操作树建立 X/V/A/W/M 的源针与产出针
关联，保留原始顺序及 FLO/BLO 范围。无完整操作式、矛盾或未支持的挑针说明时给出原因，
不从聚合量推测位置。首圈、跨部件接合和隐形减针的具体挑针过程不在此查看器范围内。

重复组按子树计数跳过，每页只创建 24 个操作。自制长圈 `(X,V,X)×25000` 的
75,000 个操作产出 100,000 针，末页仅有 24 个操作；本轮直接序列化得到 JSON
2,529 字节、SVG 16,917 字节。这是有界输出示例，不是与旧查看器的性能对比，
也不代表照片识别准确率或成品形状改善。

`tests/test_stitch_connections.py` 用独立逐针预期及属性测试核对来源与产出索引、嵌套
重复组跨页偏移、长圈、挑针范围、未知工艺、SVG 转义及会话隔离。没有复制外部代码、
图片或完整图解，没有新增依赖，也未执行上述项目的解析器、三维仿真或实体试钩。

## 本地图例：锁针并腿人工规划

按用户指定复核 `Downloads/gz/gz2/IMG_5068.JPG` 的两腿通过锁针接成身体的做法。
新工具只处理两条完整开口和锁针两侧各一短针的计数：两个开口针数之和加两倍锁针数；
允许记录人工指定的圈号和记号针。例子与测试数字均自行设计，不复制原图解内容或图片。
原图解标明个人使用及版权限制；不分发图解。工具不判断开口、针位或实物适配，也不会
自动接合部件，不能把该案例视为实体试钩或通用工艺验证。

## 2026-10-25 打印图例与针位说明复核

- [Craft Yarn Council 官方缩写表](https://www.craftyarncouncil.com/standards/crochet-abbreviations)：核对 sc2tog、FLO 与 BLO 的含义。X/V/A/W/M/B 为本项目图例约定，不作为所有图解通用的字母规范。
- [PlanetJune 隐形减针教程](https://www.planetjune.com/blog/amigurumi-help/how-to-crochet-an-invisible-decrease/)：普通 sc2tog 与只挑两针目前半针的隐形减针是不同做法。修正旧 Markdown/PDF 将两者直接等同的说明，整圈 FLO/BLO 仍以本圈工艺要求为准。

界面、Markdown 和 PDF 复用针法说明；删除旧前言要求每圈自动漂移一针的提示，
按本系统已生成的明确操作式执行加针位置，不叠加额外移动。改用引拔圈时须核对
起立针计数、换色边界与针位。以上为说明一致性修正，不是实体成形效果验证。
`tests/test_printed_stitch_guidance.py` 使用自制图解比对文字、限定针位与 PDF 缓存升级；
`tests/test_backup_open.py` 验证新会话直接恢复以及错误输入不覆盖当前图解。
没有复制来源图片或完整教程，备份格式和运行时依赖不变。

## 2026-10-24 网络图例与前后半针

本轮直接核对以下原始来源，仅提取挑针方式与语法事实，不复制图解或原图：

- [Supergurumi 机器人图例](https://www.supergurumi.com/amigurumi-robot-crochet-pattern)：整圈前／后半针与加减针结合使用，说明单有总针数不足以记录工艺。
- [PlanetJune 前后半针对比](https://www.planetjune.com/blog/amigurumi-help/fuzzy-to-brushed-crochet/)：作者展示 BLO 与普通双半针的成形差异，因此不能在输出时丢弃挑针限定。
- [Supergurumi 蜜蜂原图例](https://www.supergurumi.com/amigurumi-crochet-bee-pattern)：复核头身 R6/R19 与腿 R7 均为前半针，修正旧夹具及词表误写的 BLO 为 FLO。仅补齐这三处操作式；55 条聚合围长采样仍不表示还原了原作移位和全部针位，导出测试明确断言其余 52 圈使用了推断。
- [CrochetPARADE 官方 HTML 手册](https://github.com/stassev/CrochetPARADE/blob/main/Manual.html)的 stitch table、`stitch_nameNinc/Ntog`，以及[官方能力说明 §1.5](https://github.com/stassev/CrochetPARADE/blob/main/capabilities.md)：核对 `scfl`/`scbl` 与增减后缀。此处以较新的 HTML 手册为依据；旧 `Manual.md` 未列出这组挑针词表。没有引入其实现。

新增的范围语法支持 `BLO((X,V,X)×5)`、`FLO: 12X`、`2X,4sc-FLO,2X`；
`BLO；12X` 或 `本圈只挑后半针；12X` 的独立说明明确作用于整圈。
前后半针限定保留在 Markdown、符号条 F/B 标识及 DSL 中；相同针位的冲突范围
会被校验拦截。自由文字仍可人工使用，但无法确定范围时停止该部件的 DSL 导出，
缺少基底的首圈挑针同样不按魔法环猜译。生成器的断线穿针收口不属于钩织操作。

| 自制反例 | 此前 | 现在 |
|---|---|---|
| `BLO((X,V,X)×5)`，15→20 | 按普通均匀短针推断 | `5[scbl,scbl2inc,scbl]` |
| `2X,4sc-FLO,2X`，8→8 | 输出 `8sc`，丢失局部挑针 | `2sc,4scfl,2sc` |
| `FLO；BLO；8X` | 只使用 `8X` | 拦截整圈范围冲突 |

`tests/test_loop_notation.py` 使用自制输入验证独立计数、针位与范围、长重复组、
多实体、编辑、备份、Markdown/PDF 和部分导出；原计算器交互测试新增局部 FLO。
该子集只作用于已有 X/V/A/W/M 短针操作。跨层挑针、预留针目再接回、隐形减针
与挑针组合仍需人工复核；也不自动调整行高、尺寸或用线估算。没有运行官方解析器、
三维仿真或实体试钩，不能据此声明物理成形已验证。

## 2026-10-24 针法顺序与导出一致性

生成器进一步把旧“错开半组”提示替换成明确的组尾/组中操作式。范围限定为
连续 +6 且短针间隔为偶数的圈；例如将 `(2X,V)×6` 写成 `(X,V,X)×6`，仍消耗
18 针、产出 24 针。它采用前述本地图例中将短针分置加针两侧的表达方式，
是本系统的明确排针规则，不是对参考作品完整图解的还原，也未验证实物更圆。
`tests/test_generated_stitch_placement.py` 覆盖逐针顺序、幂等、留线说明保留、
旧备份与数字编辑，以及全部预设密度、三种头部模式与分件/一体组合。

复核 [CrochetPARADE 官方手册](https://github.com/stassev/CrochetPARADE/blob/main/Manual.md)
中每行一圈、按前圈顺序连接针目及重复组的规则，保留本项目已使用的短针增减语法。
仅以语法为参考，本轮没有引入其实现或运行外部仿真。

同一组自制表达式在修改前后直接调用导出器的结果如下；这些是软件反例，不是实体试钩：

| 操作式与数值 | 修改前 | 修改后 |
|---|---|---|
| `X,(V,2X)×5,V,X`，18→24 | 改排为 `(2X,V)×6` | 保留原针位 |
| `3X,V,A`，6→6，加1减1 | 跳过 | 同一行导出混合针法 |
| `(X,V,V)×6`，18→30，加12 | 无法均分，跳过 | 保留六组集中加针 |
| `(X,V)×6`，数值6→12，加6 | 忽略说明，按6V导出 | 发现消耗/产出矛盾，停止该部件后续圈 |

`tests/test_notation_fidelity.py` 使用独立的逐操作序列和 DSL 展开器比较针位，覆盖
嵌套重复、W/M、非六等分、多实体与部分导出，以及长重复组的可见前缀渲染。
Markdown 和符号条共用有序表达式。只有聚合数据时，DSL 报告单独记录推断针位的
实体圈次；文字错位提示、挑针、非魔法环起针及收口动作仍需对照原说明核对。

## 2026-10-24 本地图例与逐圈操作式

本轮按用户指定查看 `Downloads/gz` 中的 JOLA 娃娃图例，具体为
`IMG_5035.JPG`、`IMG_5038.JPG`、`gz2/IMG_5053.JPG` 和 `gz2/IMG_5057.JPG`。
参考点是材料清单、独立总针数列、拆分位置的重复组，以及跨层挑针须区分于
普通短针计数；没有将该作品转录成内置图解，也未导入原图或 PDF。

据此补齐操作式与数值字段的相互核对，并在逐圈编辑区提供计算器。
`tests/test_stitch_notation.py` 使用自制短表达式验证消耗/产出、加减针、
重复组、异常边界与编辑/导入/打印导出。完整可识别的独立操作式按整圈处理；
含未知针法或自由文字的表达式不会部分猜读。跨层挑针、锁针并腿、颜色位置、
眼位和装配流程均不属于这次操作式校验范围。旧夹具四处 `2 sc` 的加针意图
改用明确的 `inc` 表达；这是修正夹具的缩写歧义，不是判定原作品有误。
这些证据只覆盖符号计数与软件边界，不是照片识别评测或实体试钩。

## 2026-10-15 主体修正画布

- [Streamlit 双向组件文档](https://docs.streamlit.io/develop/concepts/custom-components/components-v1/intro)
  与[最低支持版本的消息接口](https://github.com/streamlit/streamlit/blob/1.40.0/component-lib/src/streamlit.ts)
  用于核对画布和 Python 之间的消息协议。画布为本项目自写，不加载远程脚本。
- 本轮采用直接补选/擦除最终掩码，不是重新执行 GrabCut 或生成照片中不存在的结构。
  修正与备份回归见 `tests/test_mask_review.py`；浏览器合成烟雾测试见
  `scripts/check_mask_canvas.cjs`（测试环境需安装 Playwright，可指定 Chrome 路径）。
- 已在本机 Chrome 与实际 Streamlit 页面验证画笔、撤销、恢复及生成联动；
  这是交互与数据链路证据，不是独立真实照片准确率评测。

## 2026-10-14 图例与轮廓塑形复核

**同日后续已实施**：用户确认不再需要 LLM 后，已删除云端接口、SDK、密钥设置与提示词，照片默认本地分析。下方“本轮只作可行性评估”的段落记录前一轮判断，已由本次实施取代。旧备份仍保留来源和用量；库调用须移除 provider 构造参数，将 `ai` 模式改为 `local`。

- [CYC 官方符号表](https://www.craftyarncouncil.com/standards/crochet-chart-symbols)：应结合每份图解自己的图例解读；不能把 X/V/A 当作所有图解的统一字母编码。
- [Trishagurumi Crochet Pear](https://trishagurumi.com/wp-content/uploads/2021/07/crochet-pear-pattern-trishagurumi.pdf)：肩部收窄间有平钩圈，最终外形还涉及填充及拉线塑形。仅提取 R18–22 的五个针数用于回归，不复制完整图解；不能由针数序列宣称已复现梨形。
- [Geek and Yarn 错位加针教程](https://geekandyarn.com/how-to-stagger-increases/)：错位改变加针位置而不改变圈总数，支持保留现有错位说明；本轮未实现针位级三维仿真。
- [AmiGo 原论文](https://arxiv.org/abs/2211.01178)：输入为闭合三角网格，构造 crochet graph 后转为指令；并非单张照片识别算法。纠正代码中的作者/会议归属为 Edelstein 等、SCF 2022。

本轮自主实现的是六针格点上的动态规划，不是 AmiGo 的复现：首圈固定，最小化整段量化轮廓的针数平方误差，等误差时减少总加减量。约束包括密度变化上限、加针源针数及两针并一针的消耗上限，保留原有圈数。仅适用于当前短针旋转体模型，不能推广为所有针法的约束。

[18 例合成对照](profile-fit-comparison-20261014.json)含直筒、肩部、收腰，三种密度与两个方向。12 例严格改善，6 个直筒保持零误差；例如经典肩部误差 2556→864。该指标针对平滑、量化后的目标，不是原照片像素误差，也不证明识别或成品准确率提升。复现：

```bash
.venv/bin/python -m scripts.diagnose_profile_fit --out /tmp/profile-fit.json
.venv/bin/python -m pytest -q tests/test_profile_shaping.py
```

LLM 架构判断：核心生成器、密度、配色、校验和导出均无需云端 LLM。可以采用本地视觉＋人工确认作为产品主流程。当前版本仍保留 provider 接口和 SDK 必装依赖；有 Key 时 CLI 仍默认 AI，必须显式 `--local`，界面选择“本地视觉估算”。彻底移除应同时处理 SDK/锁文件、Key 与 Base URL 设置、CLI/UI 默认值、预算账本和 provider 测试；旧结果的来源元数据仍需兼容。本轮只作可行性评估，没有删除接口或改变调用默认值。本地部件识别不足不能由本次塑形优化补齐。


## 网络方法能验证什么（2026-10-09 原始资料复核）

| 原始来源 | 可用作何种证据 | 不能据此声称 |
|---|---|---|
| [Craft Yarn Council 密度/线材表](https://www.craftyarncouncil.com/standards/yarn-weight-system) | 行业参考范围；该表明确是指导值，应遵循具体图解密度 | 本系统的厘米尺寸或用线已校准 |
| [PlanetJune 钩针与张力实验](https://www.planetjune.com/blog/stitch-tension-in-amigurumi-an-investigation/) | 同一杯形样本改变钩针后，尺寸、硬挺程度和针隙发生变化，支持实测试片的必要性 | 本系统生成玩偶已实测成功 |
| [CrochetPARADE 作者能力说明](https://github.com/stassev/CrochetPARADE/blob/main/capabilities.md) | 独立图结构渲染、拓扑与张力检查工具 | 仅导出 DSL 就已通过外部仿真或实体试钩 |

网络教程可转化为规则参考用例；原始教程、独立程序运行结果和实体测量必须分开记录。
本项目的 `parade_export_rate` 检查导出完整性及自有语法子集，不是外部程序运行成功率。
这组资料不解除照片基线 G3 或实体试钩 G4。由第三方完成的系统图解试钩可以提交
可追溯原始记录，按[试钩协议](physical-trials.md)审核；仅找到相似成品不能替代。

## 成品照片与原图解配对探索（2026-10-09）

已下载原站的两张成品照片到临时目录，运行本地完整生成管线，再用同页图解和人工
观察进行对照。原图解没有传给生成器；禁用云端 API 和可选姿态模型。这补充了原来
只提取针数规则的测试。[机器报告](public-pair-probe-20261009.json)记录照片 URL、
SHA-256、应用源码摘要、识别信息、生成部件及自检结果，仓库不包含照片或原图解全文。

| 配对来源 | 实际结果 | 原图解带来的额外对照 |
|---|---|---|
| [Clover / Maria Atelier AKIHIRO](https://www.clover-mfg.com/en/project/amigurumi-akihiro-crochet-pattern/) | 可见部件漏耳朵、尾巴；针数自检通过 | 原图解有并腿后连续钩身体和头的结构；默认输出为分离部件 |
| [53stitches Low sew Bunny](https://53stitches.com/low-sew-bunny-free-crochet-pattern/) | 漏耳朵、误加裙子；未检出人脸，走默认比例；针数自检通过 | 原图解用主体内的泡芙针形成肢体，耳朵另作；默认输出为圆筒四肢 |

配色也需要改进：兔子推荐色包含暗肤色、深绿色、钢蓝色，生成部件大量使用灰色。
这两例证明自检通过不保证图像语义一致；不用于推算全体照片的准确率，也不代表云端
视觉路径表现。可见语义部件与实际钩织独立件必须分开比较，不能要求所有正确方案
逐圈复刻原作者图解。AKIHIRO 使用来源标注的 26cm 作为输入目标；兔子使用默认
18cm，两者均未校准原作者密度，不能据圈数差异直接判定尺寸错误。

复现（先将页面链接中的对应照片保存到本地）：

```bash
.venv/bin/python -m scripts.probe_public_pairs \
  --akihiro /private/tmp/crochet-akihiro-reference.jpg \
  --bunny /private/tmp/crochet-bunny-reference.jpeg \
  --out /private/tmp/public-pair-probe.json
```

两例为开发探索集，原图解此前已用于规则测试，不作为独立留出集。
公开配对资料可支持识别、结构和工艺回归；正式共享照片集需核实复用条件，
本报告未声称已有再分发许可，也未声称系统输出已被实体钩出。

## 扩展至 10 个配对样本（2026-10-09）

新增 8 例，连同前轮 2 例全部实际运行，覆盖 5 个发布站点、10 个不同图片哈希。
[样本清单](public-pair-catalog-20261009.json)在运行前记录原站照片地址、人工部件标签、
结构事实和场景分组；[完整结果](public-pair-probe-expanded-20261009.json)保留成功、
失败与边界案例。原图仅存在本地临时目录，没有进入仓库。

| 新增样本及原钩法 | 场景/结构差异 | 本地生成观察 |
|---|---|---|
| [53stitches Ginger Cat](https://53stitches.com/ginger-cat-free-low-sew-crochet-pattern/) | 手持、植物背景；耳和脚形成于主体 | 漏耳、尾，额外生成手臂 |
| [53stitches Pigeon](https://53stitches.com/no-sew-pigeon-free-crochet-pattern/) | 手持、多色；预留针环接翅膀 | 额外生成手臂；检测框落在腹部 |
| [53stitches Gummy Worms](https://53stitches.com/sour-gummy-worms-free-candy-crochet-pattern/) | 多作品、手持、双色弯管 | 仍输出头身、双臂、双腿；作为边界案例 |
| [Clover Cupcakes](https://www.clover-mfg.com/en/project/crochet-cupcakes/) | 双作品、食物、装饰 | 仍输出人形部件；作为边界案例 |
| [Clover Pretzel](https://www.clover-mfg.com/en/project/amigurumi-pretzel/) | 俯拍、打结长管 | 仍输出人形部件；作为边界案例 |
| [Tiny Curl Monsieur Bear](https://www.tinycurl.co/monsieur-bear-free-amigurumi-crochet-pattern/) | 浅色背景、帽子、条纹、脚部出框 | 漏耳/帽，误加裙子；检测框落在腿部 |
| [All About Ami Elephant](https://www.allaboutami.com/elephantpattern/) | 双作品、四足、象鼻 | 仍输出双臂双腿的人形模板；作为边界案例 |
| [Supergurumi Bee](https://www.supergurumi.com/amigurumi-crochet-bee-pattern) | 斜俯视、条纹、六足、翅膀和触角 | 额外生成手臂，腿部数量仍为 2 |

本次 **10/10 执行完成、10/10 针数自检通过；6 个单主体动物的规范部件集合精确
匹配为 0/6**。另外 4 个边界案例不进入部件准确率，空标签不被计为“召回 100%”。
这不等于系统对所有照片准确率为零；仅是人工挑选的开发探索样本，并且只运行本地
视觉路径。鸽子/蜜蜂当前无法表达的翅膀、喙、触角单列 `unmodeled_features`，
不能因规范部件召回完整便认定图解完整。图片出现多个物体也未被分离成多个图解。

检测框人工复核：熊的 `[676,1329,73,73]` 位于腿部，鸽子的 `[386,511,46,46]`
位于腹部；两者比例均到达代码上限 8。不是实测真实头身比例。由此优先改进：

1. 确认主体类型、单/多主体与部件列表，无法表达的对象显式提示，避免自动套人形。
2. 对“人脸框”增加适用性与位置检查，并让用户确认头部范围后再决定尺寸比例。
3. 扩展结构表达：把翅膀、象鼻、触角、连续钩织和针法形成的肢体与独立缝合件分开。
4. 对浅色作品、背景色、条纹做独立配色对照；圈数对比需先统一密度，不能直接照抄。

复现：按清单 `image_url` 下载到同一目录，并使用对应 `image_file` 命名，再运行：

```bash
.venv/bin/python -m scripts.probe_public_pairs \
  --catalog docs/public-pair-catalog-20261009.json \
  --image-dir /private/tmp/crochet-pair-expansion \
  --out /private/tmp/public-pair-expanded.json
```

脚本兼容前轮双图片参数；每例异常写入报告并继续，不删失败案例。
新增 3 个回归验证边界排除、针数通过与语义失败分离、批次失败计数；全部通过。
脚本及测试 Ruff 通过，脚本 mypy 通过。应用代码未改，未重跑应用全量测试。

## 配对样本驱动的首轮改进（2026-10-09）

同一清单、同一 10 张图片重跑：[改进后原始报告](public-pair-probe-guarded-20261009.json)。
原[扩展报告](public-pair-probe-expanded-20261009.json)保留作为修改前对照，不覆盖历史结果。

| 项目 | 修改前 | 修改后 |
|---|---|---|
| 兔子/戴帽熊误加裙子 | 2 例 | 0 例；轮廓展开仅记录 `possible_skirt` 提示 |
| 候选头部框被自动采用 | 6 例 | 1 例；另外 5 例因位置/相对尺寸被拒绝 |
| 6 个单主体规范部件精确匹配 | 0/6 | 0/6；耳、尾、帽和不需要的手臂仍需人工修正 |
| 针数自检 | 10/10 | 10/10 |

头部检查使用主体纵向范围：候选中心不在上半部，或框相对主体过小（推算比例超过
既有 8 倍上限）时，不再把它钳成看似正常的比例；退回默认并保存拒绝原因。规则
只适用于直立构图的保守筛选，不证明保留下来的框正确，也不自动识别卧姿/动物头部。

照片确认界面要求用户选择单个且现有部件可表达的主体。未选择、多个主体、食品或
不可表达结构不能直接点击生成；多主体提示重新裁剪。用户仍需修正部件和数量。
这属于人工确认流程，未加入自动食品/多主体检测器。CLI/直接管线仍可生成待审阅
模板，元数据、CLI 提示和便携导出均明确标记需要复核，不能算作已拦截所有路径。

本轮没有给测试照片增加专用分支，也没有将原钩法输入识别器；保留开发集和验证集
的区别。下一步仍需改进主体语义、部件数量和复杂工艺结构表达。

## 第二批新增配对例子（2026-10-09）

继续查阅 6 个原站页面，成功取得并运行 5 组照片/钩法；累计已实际对照 **15 张
不同照片，来自 9 个站点**。原 10 例与本批 5 例的应用源码摘要一致，图片 SHA-256
跨批去重为 15。应用和评测脚本本轮均未修改。

[本批清单](public-pair-catalog-wave2-20261009.json)与[实际运行报告](public-pair-probe-wave2-20261009.json)
独立保存。清单记录未下载成功的蘑菇候选：原站直接请求返回 HTTP 403，没有实测，
不计入 15 例。没有用其他来源图片冒充该图解成品。

| 新来源 | 参考钩法/新覆盖 | 实际本地输出问题 |
|---|---|---|
| [lilleliis Little Christmas Elf](https://www.lilleliis.com/amigurumi-crochet-freebies/little-christmas-elf/) | 人形、尖帽、耳朵；并腿成身，其他件连接 | 漏帽子、耳朵 |
| [lilleliis Little Tree](https://www.lilleliis.com/amigurumi-crochet-freebies/little-amigurumi-tree/) | 树冠/树干/根团连续钩，盆栽场景 | 仍输出头身、双臂双腿，作为非动物边界例 |
| [Spin a Yarn Ragdoll Mermaid](https://spinayarncrochet.com/ragdoll-mermaid-free-crochet-pattern/) | 前后片拼合、鱼尾、尾鳍、长发 | 漏尾巴，误加双腿；默认立体部件没有表达片式拼合 |
| [Cuddly Stitches Craft Jellyfish](https://www.cuddlystitchescraft.com/free-crochet-jellyfish-pattern/) | 伞体/腹片连接，直触手与卷触手 | 仍输出人形部件，作为现有模型不可表达的边界例 |
| [Yarnhild Sverre the Lamb](https://yarnhild.com/crochet-ragdoll-pattern/) | 前后片拼合、泡芙纹理、四足 | 漏耳朵、尾巴，额外生成手臂；下方脚部在原照片中部分出框 |
| [Stitch by Fay Mushroom Buddy](https://www.stitchbyfay.com/mushroom-buddy-crochet-pattern/) | 已核对网页文本：菌盖/菌柄接合 | 照片未取得，仅为候选，不报告生成结果 |

照片选择在运行前完成：水母从同页拼图封面改选单主体照片，保留其标题文字和边框，
没有裁剪或修图；美人鱼的水印/旁置海星也保留。它们属于有装饰背景的探索场景，
不能作为纯净背景样本。精灵背景的树与椅子作为道具，标注主体为前景精灵。

本批 **5/5 执行完成，5/5 针数自检通过；3 个可做规范部件对照的样本精确匹配为
0/3，另 2 个边界例不进入部件指标**。候选头部框有 3 个被上一轮新增的检查拒绝；
全部输出仍标记需要主体复核。这里走直接管线，没有人工确认和修正步骤，不是界面
人工修正后的结果，也不代表云端语义识别表现。目标高度统一使用默认 18cm，不做
原图解尺寸或针数的直接等价比较。

新增案例强调两个后续方向：识别非双腿结构（鱼尾、四足、触手），以及表达片式拼合
而非只有立体圈钩。清单记录的工艺事实只用于对照，没有将原图解输入生成器。

```bash
.venv/bin/python -m scripts.probe_public_pairs \
  --catalog docs/public-pair-catalog-wave2-20261009.json \
  --image-dir /private/tmp/crochet-pair-wave2 \
  --out /private/tmp/public-pair-wave2.json
```

## 校验器演进：五处先验修正

| # | 规则 | 修正 | 驱动证据 | 夹具 |
|---|------|------|----------|------|
| 1 | 非 6 倍数圈 | 硬错误 → notes | Clover AKIHIRO 22 针腿 / 16 针臂 / 9 针尾 | `test_published_akihiro_*` |
| 2 | 相邻圈跳变 ±6 | 硬错误 → notes（`allow_wide_jump` 只抑制该 note） | Spin a Yarn 8→16 倍增圈；Ms Premise-Conclusion 理想球体 sin 轮廓 | `test_professional_eight_stitch_ring_start_passes_validation`、`test_ideal_sphere_*` |
| 3 | 同圈加减速混用 | 硬错误 → notes | 紫柚手作垂耳兔眼窝圈 7X,7V,A,7V,7X | `test_cn_rabbit_head_face_shaping_passes` |
| 4 | 加针 ≤ 上圈源针 | 硬错误 → notes | granny 实心款第 2 圈：+16 加进 4 个锁针角空间（12 源针） | `test_intl_solid_granny_space_increase_downgraded_to_note` |
| 5 | 减针超纯 A（2并1）配对上限 | 硬错误 → notes（外部 AI 审核确认） | 机械反例：4 针经一次 sc4tog 收到 1 针（3 > 2，完全可钩）；小黄人 8 ≤ 9 的最密圈在纯 A 配对内 | `test_validator_downgrades_incapable_v_and_incapable_a` |

降级 ≠ 放水：硬错误保留代数断裂、空圈、非数字字段与针数 < 1；notes 分两类——
非 6 倍数/超平滑跳变只提示（正常导出），混圈与超均匀分组表达的圈由
parade 导出跳过并留 warning。

## 来源清单

### 官方标准与专业机构

| 来源 | 印证内容 | 夹具 |
|------|----------|------|
| [Clover 官方 AKIHIRO 玩偶](https://www.clover-mfg.com/en/project/amigurumi-akihiro-crochet-pattern/) | 22 针腿/16 针臂/9 针尾/14 针耳（先验修正 #1）；均匀 +6 头 | `test_published_akihiro_*` |
| [DROPS Design 苹果玩偶 23-60](https://www.garnstudio.com/pattern.php?id=5888&cid=17) | 7 起针对称球、官方密度 18sc/10cm；锁针果柄诚实警告 | `test_published_drops_apple_*` |
| [CYC 纱线重量系统](https://www.craftyarncouncil.com/standards/yarn-weight-system) | gauge 层 cyc_label 七档映射 | `test_gauge.py` |
| [CYC Project Levels](https://www.craftyarncouncil.com/standards/skill-levels) | 难度四级标签对齐 | `test_schemas.py` |
| [CYC 缩写规范](https://www.craftyarncouncil.com/standards/crochet-abbreviations) | CrochetPARADE DSL 令牌一致性 | `test_parade_tokens_align_with_cyc_abbreviations` |
| [Shelley Husband US↔UK 对照](https://shelleyhusbandcrochet.com/uk-and-us-crochet-terms-conversion-help-and-chart/) | 错位一级对照链（sc=dc、hdc=htr、dc=tr、tr=dtr、dtr=ttr）——针法表 UK 列 | `test_height_ladder_us_uk_offset_invariant` |
| [中文图解符号体系（知乎/Reddit 新手指南）](https://zhuanlan.zhihu.com/p/2397749055) | X/T/F/E/V/A 字母记号 ↔ sc/hdc/dc/tr——针法表中文列与符号列 | `tests/test_stitches.py` |
| [cbfiberworks 圈圈针](https://cbfiberworks.com/how-to-make-loop-stitches-for-amigurumi/) / [Yarnhild](https://yarnhild.com/how-to-crochet-the-loop-stitch/) | 纹理针族：环圈成于反面（反过来钩/front-side 变体）、减针挂 4 环并拉过、双圈内卷警告、费线提示 | `test_intl_loop_stitch_texture_rounds_pass`、`test_loop_stitch_family_entries` |
| [AmiguRoom 俄语熊](https://amigurum.ru/2018/04/medvezhonok-amigurumi.html)（Юлия Дейнеги） | 头部 6↔3 等分切换增减两向（与橘子先生互证）、17 圈漂移减针、5 起针尾巴；评论区共识：颈部塞棉紧实 → 组装说明 | `test_intl_ru_deynega_bear_*`、`test_assembly_neck_stuffing_note` |
| [Yarnspirations Red Heart Bear](https://www.yarnspirations.com/products/red-heart-bear-amigurumi)（Sarah Zimmerman） | 北美大厂锚点：10 起针全程合圈、腰身掐细一体件、眼距 = 最大圈/6 精确印证、12mm 眼 @ 23cm、13 sc/10cm 官方密度、脚外撇坐姿支撑 | `test_intl_red_heart_bear_*` |
| [Lion Brand 经典 granny](https://www.lionbrand.com/community/blog/how-to-crochet-a-classic-granny-square/) | 四角拓扑 +12/圈、边圈 76 | `test_intl_lionbrand_classic_granny_passes` |

### 专业设计工作室 / 独立设计师

| 来源 | 印证内容 | 夹具 |
|------|----------|------|
| [Supergurumi 蜜蜂](https://www.supergurumi.com/amigurumi-crochet-bee-pattern) | 55 圈头身一体 66 峰值、逐圈换色、BLO 脊线、错位增减、33→9→6 奇数收尾；Catania 纱线校准 fine 档米数 | `test_published_bee_*` |
| [AllAboutAmi 大象](https://www.allaboutami.com/elephantpattern/) | 象鼻圆锥 −3/圈；椭圆起链身体/跨部件挑钩超出聚合模型（如实记录不夹注） | `test_intl_elephant_trunk_cone_taper_passes` |
| [StringyDingDing 袋鼠](https://stringydingding.com/kangaroo-amigurumi-free-crochet-pattern/) | 环起后先平钩、一体钩非均匀增减、21/15 奇数圈；**腿部 R5 出版矛盾**（真实印刷错误第二例，校验器正确拦截） | `test_published_kangaroo_*`、`test_validator_catches_published_kangaroo_leg_round5_contradiction` |
| [53stitches 低缝兔](https://53stitches.com/low-sew-bunny-free-crochet-pattern/) | MR 8 起环、泡芙针（5dc popcorn）直接成四肢 | `test_intl_lowsew_bunny_popcorn_limbs` |
| [Tiny Curl Monsieur Bear](https://www.tinycurl.co/monsieur-bear-free-amigurumi-crochet-pattern/) | 显式合圈贝雷帽 "joined rnds, not continuous spiral"、ch-3 计针、MR7 翻面 hdc 耳 | `test_intl_tinycurl_*` |
| [Craftably Ever After 坐姿熊](https://craftablyeverafter.wordpress.com/2022/04/22/patchy-bear-crochet-pattern/) | 锁针并腿身体 R15=36（13sc+2ch+16sc+2sc+3sc 逐字自报）；椭圆起针 [10]；眼位"帽沿上 2 行、间距 2 针" | `test_intl_patchy_bear_chain_joined_body_passes`、`test_intl_snout_oval_start_verbatim` |
| [Squirrel Picnic Motley Bear](https://squirrelpicnic.com/2015/04/24/motley-the-bear-crochet-pattern/) | 合圈与螺旋同件混用、起立锁针不计针、(sc,sk)×6 跳针收口、FLO 颈圈 | `test_intl_squirrelpicnic_motley_joined_muzzle_and_skip_close` |
| [Marching North 实心 granny](https://www.marchingnorth.com/solid-crochet-granny-square-pattern/) | +16/圈、空间加针（先验修正 #4 驱动源） | `test_intl_solid_granny_space_increase_downgraded_to_note` |
| [Chibiscraft 小黄人](https://blog.alwaysfreeamigurumi.com/cute-minion-amigurumi-free-crochet-pattern/) | 5×sc2tog + sc4tog 净减 8 的密集圈（早期 4× 转录注释已勘误；不再视为通用硬规则证据）、鞋底 BLO/FLO 交替、54→9 收尾、椭圆起针 [12] | `test_intl_minion_*` |
| [Spin a Yarn Rudolph](https://spinayarncrochet.com/rudolph-ornament-free-crochet-pattern/) | 8 起环倍增（先验修正 #2 驱动源） | `test_professional_eight_stitch_ring_start_passes_validation` |
| [Ms Premise-Conclusion 理想球体](https://mspremiseconclusion.wordpress.com/2010/03/14/the-ideal-crochet-sphere/) | sin 轮廓逐圈对照独立重算；工艺警告落实 | `test_ideal_sphere_*` |

### 社区教程与论坛

| 来源 | 印证内容 | 夹具 |
|------|----------|------|
| [PlanetJune magic ring](https://www.planetjune.com/blog/amigurumi-help/how-to-crochet-a-magic-ring/) | 6 起环 +6 公式口径；无痕收口（front loops 拉紧） | `test_generated_sphere_matches_community_formula` |
| [PlanetJune needlesculpting](https://www.planetjune.com/blog/tutorials/needlesculpting/) | 针塑形（可选组装步骤）：眼窝=横穿头内、两端同孔拉紧打结藏线；隐形走线法（V 形两线间进针）；锚点选择；「内建塑形的图解无需此步」定性 | `test_assembly_optional_needle_sculpting_step` |
| [Grace and Yarn 配重底](https://www.graceandyarn.com/2019/12/how-to-add-weighted-base-to-your.html) / [The Loopy Lamb](https://theloopylamb.com/how-to-use-poly-pellets-in-amigurumi/) | 配重珠法（可选）：约 3/4 杯聚乙烯珠装丝袜打结、减针开口尚能伸手时置底、丝袜色近玩偶防透出、3 岁以下勿用、可正常水洗 | `test_weighted_base_materials_and_assembly` |
| [r/Amigurumi 眼睛 wiki](https://www.reddit.com/r/Amigurumi/wiki/faq_eyeqs/) | 安全眼分档（迷你 5–6 / 常规 8–12 / 大型 14–20+ mm） | `test_crochet_params.py` 眼径梯 |
| [kruchcom.ru 泰迪指偶](https://kruchcom.ru/archives/22215) | 俄语圈 КА/ПРИБ/СБН 逐字——跨语言同一标准 | `test_russian_finger_puppet_rounds_pass_validation` |
| [Lovable Loops 樱桃 C2C](https://lovableloops.com/cherry-square-mini-c2c-crochet-pattern/) | 9×9 逐行色块全文回写 | `test_grid_pipeline_reproduces_published_c2c_chart` |
| [Lovable Loops 心形 C2C](https://lovableloops.com/mini-heart-square-c2c-crochet-pattern/) | 非对称行钉死读取方向（↙正面/↗反面） | `test_grid_written_rows_match_published_heart_chart` |
| [Maclafersa 定型线安全指南](https://maclafersa.com/how-to-add-wire-to-amigurumi-safely-for-posing/) | 端部折环+包裹防戳（胶带单独不可靠）、比量手→肩→手、尾线略短于成品、开口时放入、九大错误清单 | `test_materials_wire_row_for_limbs_only` |
| [Crafty Intentions 线材清单](https://craftyintentions.com/blog/2019/7/8/supplies-wire) | 纸包 18 号 18 英寸花艺线规格锚点（布包同号过软）、纸褶摩擦防移位、防锈 | `test_materials_wire_row_for_limbs_only` |
| [toruyuri 円の増し目の法則](https://toruyuri.com/2020/02/02/wanomashime/) | 日语圈错位加针法则（奇数段段尾/偶数段段中，六角形 vs 圆照片实证）；起针数实验（3 最小、10 露洞）；第 4 套语言 notation（段/目/増し目） | `test_japanese_circle_increase_law_passes`、`test_preamble_mentions_increase_offset_rule` |
| [Zepiany ES-Bee](https://www.zepiany.com/pages/es-bee1) / [Melonchillo 圆环法则](https://melonchillo.com/anillo-magico/) | 第 5 套语言 notation（vuelta/pb/aum）；30 峰对称球；第 3 例出版矛盾（V1 记号 6 vs 正文 8）；针高→起针数法则（短针 6/中长针 8/长针 12）；安全眼 3 岁以下/宠物警示 → 材料行 | `test_intl_zepiany_es_bee_body_and_contradiction`、`test_intl_melonchillo_dc_circle_start_height_law` |

### 国内图解（图片图解，视觉转录）

| 来源 | 印证内容 | 夹具 |
|------|----------|------|
| [紫柚手作·垂耳兔](https://www.bianzhirensheng.com/a/44051_zhifa.html) / [橘子先生](https://www.bianzhirensheng.com/a/44093_zhifa.html) | 面部塑形混用加减速（先验修正 #3 驱动源）、M 三并一、平织椭圆耳、3 等分帽子 +3/圈、7 起针头套、减到奇数 7 的脚 | `test_cn_tuanzi_*`、`test_cn_rabbit_*`、`test_cn_orange_*` |
| [骨头团子](https://www.bianzhirensheng.com/a/44074_zhifa.html) / [软糖系列](https://www.bianzhirensheng.com/a/44140_zhifa.html) | 对称节奏、倍增圈（8→16）如实降提示、枣形针 B 中性语义 + 图例 | `test_cn_bone_doubling_round_passes_with_note`、`test_cn_gummy_*` |
| [晴一手作·小兔叽妹妹](https://www.bianzhirensheng.com/a/43996_zhifa.html)（小红书原生） | 背带裤两腿并钩 24+24→48、胡萝卜先减后增收肩、5 起环奇数收口 | `test_cn_overalls_two_leg_join_passes`、`test_cn_carrot_*` |

## 抓取方法与诚实记录

- **逐字全文**：web 抓取 HTML 后只取圈行文本，机械核对每圈
  `st = prev + inc − dec` 后落夹具——四次转录错误全被校验器当场
  拦截（蜜蜂 R6、胡萝卜 R3、低缝兔省略行、软糖），夹具即勘误记录。
- **图片图解（国内主流形态）**：编辑器视觉识图逐圈转录，同样过校验器。
- **可达性欠账**（未能核验，如实记录）：Etsy 403、Ravelry 登录墙、
  小红书登录墙 + 图片图解、编织人生分享平台 502、部分论坛私密版块、
  Raffamusa 403、Hobbii PDF 无法直取、Ami Amour 404、Supergurumi
  /patterns 索引 404。这些来源未入夹具，未来若可达再补。

## 2026-10-11：结构与局部配色候选补充

新增 [7 个候选及访问状态](public-pattern-candidates-20261011.json)：5 个原站正文可读，
2 个仅核对原站搜索索引；后者不能声称完成页面或图片核验。本轮只提取结构事实，
未取得照片处理许可、未运行新的网络照片，不合并进此前 15 张实测统计，不计 G3/G4。

| 原站例子 | 核验到的结构事实 | 对算法的启发（待验证） |
|---|---|---|
| [Grace and Yarn 熊猫](https://www.graceandyarn.com/2021/04/free-crochet-panda-pattern.html) | 眼斑是另做后附着的片 | 局部斑块不应变成整圈色带 |
| [Cuddly Stitches 熊猫](https://www.cuddlystitchescraft.com/free-crochet-panda-pattern/)（仅索引） | 部分连接边钩边完成，眼斑另缝 | 外观部件和装配方式分开标注 |
| [Polly 熊猫](https://chaicoffeecrochet.com/crochet-panda-polly/)（仅索引） | 同圈换色构成眼斑 | 每圈单一 `color` 表达能力不足 |
| [Pudgy Panda](https://spinayarncrochet.com/pudgy-panda-plushie-free-crochet-pattern/) | 平片组装，身体片内存在行内换色 | 识别出“熊猫”仍不能推定球体/筒体制作方式 |
| [蜗牛](https://stringydingding.com/snail-amigurumi-free-crochet-pattern/) | 两片壳连接，另做身体，触角用打结线 | 需要壳面、连接边和非针目装饰的独立语义 |
| [Tiny Whale](https://www.planetjune.com/blog/free-crochet-patterns/tiny-whale/) | 连续主体末端压扁后穿过双层形成尾部 | 尾巴不必是独立圆柱；需要局部工作轴与开口语义 |
| [小狗摇铃](https://www.lilleliis.com/amigurumi-crochet-freebies/puppy-rattle/) | 头、耳、口鼻和握柄结构 | 避免固定模板凭空补出身体、手臂和腿 |

**已运行的独立反例：** [诊断 JSON](color-layout-diagnostic-20261011.json) 来自自行绘制的
两幅 160×160 黑白几何图，无第三方像素。输入两块分离黑斑与一块居中黑斑，逐带颜色
占比相同；为排除抠图影响，显式提供全前景掩码。两图各有 1280 个黑像素，当前输出
均仅剩白色。证明横带多数投票会丢掉少数色与横向位置；不代表真实熊猫照片成绩。

复现：

```bash
.venv/bin/python -m scripts.diagnose_color_layout --out /private/tmp/color-layout.json
```

建议按以下顺序改进（第一项已在后续实现，见下）：

1. 配色观测保留每带完整颜色占比和二维连通区域，单独标记少数色丢失；不要仅返回赢家。
2. 用户可确认部件区域及局部斑块；别把人脸框自动当作所有可见头部色块的范围。
3. 图解模型分别表达整圈色、圈内色段与附着装饰；不从一张照片强推唯一制作方法。
4. 分开评估部件存在性、数量、连接方式、平片/立体模式及局部色块保留率。

验收应包含少数色保留、左右斑块位置区分、白底白主体、单色无误报，以及对未支持
结构的明确提示；必须在取得许可的真实照片留出集上验证，不用这两个自制反例代替。

### 后续实现：保留局部颜色观测

[改进后对照](color-layout-observation-20261011.json) 保留原诊断的像素与供给掩码：
两幅图仍输出相同的白色整圈色带，但现在观测中均保留 1280 个黑像素；二维区域分别
记录两个左右分离黑斑和一个中央黑斑。原始诊断 JSON 保留不覆盖，上述命令现在输出新版对照。

配色提取复用现有量化和前景掩码，记录每带全部颜色计数、归一化位置及掩码来源。
最多保留 64 个区域；小于 max(4, ceil(前景像素数×0.002)) 的碎片及超出数量上限的区域
只省略位置明细，颜色总计、省略数量和像素数仍保留。每带非多数色总面积占前景达到
2% 时，结果页及 Markdown/PDF 提示局部配色待复核；这是界面提示阈值，不是置信度。

观测随备份、可容纳的分享链接和尺寸调整保留；超长分享仍使用原有备份回退。
位置属于裁剪图坐标，不是针目坐标，也不判定眼斑应缝上还是圈内换色。
未新增真实照片测试，尚未完成局部配色针法生成及授权留出集验证。

## 2026-10-12：窄条纹案例与边界细化

本轮核对以下三个原站正文，仅记录事实与独立设计结论，没有复制图解正文或处理原站照片。

| 来源 | 核验事实 | 对本项目的意义 |
|---|---|---|
| [Sharon Ojala / Little Bee](https://www.amigurumitogo.com/2020/04/little-bee-free-crochet-pattern.html) | 身体上有短换色区间，作者特别说明条纹位置调整 | 固定十等分会丢失窄色段或移动边界，需要细化颜色位置 |
| [Stitch by Fay / No-Sew Bee](https://www.stitchbyfay.com/crochet-bee-pattern/) | 螺旋钩织，条纹使用后半针，翅膀边钩边连接 | 颜色区间不等于针法和装配，不能凭条纹推断 BLO 或连接方式 |
| [Ollie + Holly / Cotton Stripe Experiment](https://www.ollieholly.com/blog/2021/03/24/how-to-crochet-better-stripes-for-amigurumi-when-using-cotton-yarn-an-experiment) | 作者比较多种减少棉线条纹换色接缝的方法 | 图像边界恢复不代表接缝工艺已解决 |

**实现：** `vertical_color_bands` 默认先保留原固定横带投票，再用持续逐行主色覆盖可靠区间。
每行主色至少占前景 75%，前景宽度至少为 max(4, ceil(最大前景行宽×20%))，
同色连续高度至少为 max(2, ceil(缩略图高度×1.5%))。这些是降噪启发式，未经照片校准。
空行、混色行和短噪声继续使用原估计；相邻同色合并。设置 `refine_stripes=False` 可复现原算法。
原始横带计数和二维局部色块不变，因此复核提示仍是保守提示，不能当作细化后的误差分数。

**对照：** [9 个自绘反例](color-stripe-comparison-20261012.json) 使用三种图高、三个条纹位置、
四像素宽黑条纹和全前景掩码，隔离分割误差。精确恢复条纹颜色及两个边界由 **0/9 → 9/9**。
`tests/test_color_stripes.py` 另覆盖单像素横线、稀疏前景、少数色斑块、原始观测守恒及逐圈颜色查询。

```bash
.venv/bin/python -m scripts.diagnose_color_stripes --out /private/tmp/color-stripes.json
```

仅证明开发反例修复；未新增原站照片管线运行，不计 G3/G4，也未推导任何试钩校准常数。
算法仍以图像竖直方向为轴，斜条纹、遮挡、毛线纹理和复杂背景需授权照片验证；
缩放到 160 像素后过细的条纹仍会丢失，逐圈采样也可能跳过小于一圈的色段。

### 后续实现：按圈区间覆盖量配色

逐圈分配已从区间中点采样改为累加各颜色与该圈高度区间的交集，选择总覆盖量最大者。
这在既有等高圈近似下最小化纵向颜色不匹配长度，不保证保留每根细条纹。覆盖量平局优先
保留中点颜色，其次取照片中先出现的颜色；先按照片从上到下计算，再对身体和四肢反转，
保证钩织方向不会改变取色结果。对没有任何相交圈被分配该色的色段，图解及导出明确提示复核；
同一颜色别处已出现也不会掩盖该色段的丢失。原始照片色带仍保留。

[三个独立区间反例](round-color-comparison-20261012.json) 的不匹配高度占比：

| 自绘区间案例 | 中点采样 | 覆盖量选色 |
|---|---:|---:|
| 极细黑条纹刚好穿过圈中点 | 9.8% | 0.2% |
| 一圈覆盖三个颜色 | 75% | 55% |
| 圈数足以准确表示的条纹 | 0% | 0% |

```bash
.venv/bin/python -m scripts.diagnose_round_colors --out /private/tmp/round-colors.json
```

这是纵向区间的确定性开发诊断，不是照片准确率、三维面积误差或试钩效果。
`tests/test_round_color_plan.py` 还用 280 个固定种子生成的整数像素案例，独立核对每圈
所选颜色确为覆盖最多者，并检查反向映射、重复同色色段丢失、生成针数代数与导出提示。

另核对 [PlanetJune 换色教程](https://www.planetjune.com/blog/amigurumi-help/how-to-change-colour-in-amigurumi/)：
前一针最后一次挂线切换颜色，与处理整圈条纹接缝是不同步骤。生成说明已去掉“避免螺旋台阶”
承诺，改为明确提示螺旋圈仍可能出现台阶；没有自动插入额外针目或未经支持的接缝工艺。
