# 系统错漏审查与优化记录 · 2026-09-07

目标：查看错漏处，并深入优化系统。审查起点为干净工作树 `d6112d2`。
本轮沿生成后校验、批量运行、导出、分享和恢复路径检查，并先用回归用例复现缺陷。
这是持续审查的阶段记录，不代表全系统已完成验证。

## 已修复且验证

| 路径 | 可复现缺陷与修复 | 回归证据 |
|---|---|---|
| 图解自检 | `6.9` 被截成 6；负减针可伪装成加针；无穷大抛异常。现在拒绝非法计数并返回诊断 | `tests/test_validation_boundaries.py` |
| 图解结构 | 空部件返回成功；空圈列表或非对象圈抛异常；坏圈后跨越它比较针数产生误报。现在报告格式错误并重置相邻圈状态 | 同上；真实图解夹具继续通过 |
| 批量命名 | `doll.png`、`doll.jpg`、`doll_png.png` 可写同一路径。现在启动线程前预留所有候选名并分配唯一名称，比较时考虑 Unicode 与大小写 | `test_cli_batch_secondary_collision_preserves_every_image` |
| 批量容错 | 图片加载失败抛 `SystemExit`，越过 `except Exception` 中断结果汇总。现在隔离每图退出，保留成功产物并返回批量失败码 | `test_cli_batch_corrupt_image_does_not_stop_other_images` |
| 目录校验 | 不存在的输入目录被自动创建；以 `.png` 结尾的目录被当作图片。现在先枚举有效输入文件 | `test_cli_batch_missing_input_does_not_create_it` 与损坏图片用例 |
| Parade | 未声明加针的 6→12 平针圈被直接输出；非法首圈可能截断取整；首圈颜色未覆盖部件颜色；空末部件产生悬空分隔 | `tests/test_parade_export.py` 新增计数、首圈配色与空部件用例 |
| 分享完整性 | zlib 缺校验尾部也可被解码；允许多余数据；高度压缩的大结果可能编码成功而解码失败。现在检查流结束、剩余输入、字节上限 | `tests/test_exports_share_cli.py` 新增分享完整性与上限用例 |
| 备份版本 | 分享和历史拒绝未知版本，但直接 JSON 导入接受版本 999。现在在 `PatternResult` 统一检查版本 | `test_import_backup_rejects_future_version`；旧备份往返测试 |
| 历史损坏 | 合法 JSON `[]`、`null`、数字或字符串会在 `.get()` 处崩溃。现在返回 `None` | `test_history_non_object_json_returns_none` |

## 验证记录

- 本地解释器：Python 3.12.13，使用既有 `.venv`，未改变依赖。
- 修改前：`.venv/bin/python -m pytest -q` → **852 passed, 1 skipped**。
- 修复后：同一全量命令 → **891 passed, 1 skipped，37.78s**。
- 全量后增加精确字节边界用例，并收紧压缩上限测试的隔离性：
  `.venv/bin/python -m pytest -q tests/test_exports_share_cli.py -k 'uncompressed_limit or byte_limit'`
  → **2 passed, 22 deselected**。
- `.venv/bin/ruff check .`、`.venv/bin/mypy app`（43 源文件）、`git diff --check` 通过。
- 未配置授权照片目录，`tests/test_eval_real.py` 按设计跳过；本轮未运行外部服务、
  远程 CI、发行包构建或实体试钩。

## 第二轮：密度、尺寸与编辑意图

上一轮属于实质进展：修改已保留在工作树，复核全量为 **892 passed, 1 skipped**。
在此基础上新增回归用例，先复现后修复：

| 发现 | 最终行为 | 证据 |
|---|---|---|
| 材料使用修改后的密度，预览和重生成却使用旧顶层值 | `gauge_from_result` 优先图解内密度，顶层仅作旧备份回退；编辑和导入同步规范化的两层值 | `test_edited_gauge_survives_import_resize_and_preview`、页面编辑用例 |
| NaN/无穷大被 `min/max` 意外变成边界密度；布尔值被当作数字 | 非有限与布尔输入回退经典值，正常有限越界值保留原钳制行为；数字字符串写回数字 | `tests/test_gauge.py`、`test_rebuild_normalizes_gauge_before_export` |
| Markdown/PDF 对字符串密度使用 `:g` 导致异常 | 两种导出与自检使用同一密度解码 | `test_exports_normalize_numeric_string_gauge` |
| 调尺寸时重新套模板，丢失数量、位姿、连接与删改部件 | 在现有结构上缩放；直径与圆形附件随头径，其余长度随剩余身高。保留编辑的图节点与颜色，不修改输入对象 | `test_resize_preserves_edited_structure_graph_and_dimension_ratios`、删除部件用例 |
| 圆柱直径、杯深、裙摆直径虽可编辑，却不影响针数 | 显式尺寸优先于模板比例；窄裙摆用减针过渡；清空结构触发生成门禁 | `tests/test_result_logic.py` 新增直径、杯深、窄裙摆和空结构用例 |
| 用户选定的结构颜色被照片语义或色带覆盖 | 显式毛线色优先，只有 `skin/body` 模板占位色继续读取照片配色 | `test_structure_color_edit_overrides_saved_photo_colors` |
| 局部编辑后旧 PDF/分享仍可下载；UI 备份绕过带版本号的统一序列化 | 应用编辑时清理两项缓存，完整备份使用 `PatternResult.to_backup()`；分享超限明确提示改用备份 | `test_manual_regenerate_applies_edited_json` 与分享/备份往返测试 |

第二轮全量：**909 passed, 1 skipped，40.67s**；Ruff、mypy app（43 源文件）、
mypy app tests（82 源文件）通过。随后补齐页面缓存失效与版本化备份接线，
页面、分享、历史、结果逻辑和仓库规范的定向回归 **95 passed，34.96s**；
再次通过 Ruff、mypy app tests 与差异格式检查。

### 照片链路测量

本地视觉路径在同一张图上分别以 `max_side=120/150/160` 调用主体分割三次，
分别供轮廓、推荐色板、逐圈色带使用。使用 240×480 RGB 合成图（浅灰背景、
棕色椭圆头、蓝色矩形身体），关闭可选 pose、清空 provider 环境并禁用 dotenv，
单个 orchestrator 连跑四次，后三次总管线耗时中位数为 **0.1097 秒**。
这是本机合成场景测量，不是授权照片质量基线，也没有宣称尚未实施的加速收益。

## 第三轮：照片观测、可选模型缓存与尺寸锚点 · 2026-09-08

接续复核基线为 **909 passed, 1 skipped，39.14s**。本轮修复：

| 发现 | 最终行为 | 证据 |
|---|---|---|
| 同张照片的轮廓、色板、色带分别分割，且缩放尺寸不同 | 单次管线使用独立 `SubjectObservation`，统一在 160px 内分割一次并缓存失败；下一次运行重新观测 | `tests/test_subject_observation.py` 覆盖 local/ai/mock、失败回退、图片编辑与并发隔离 |
| 越界人脸框在 NumPy 切片时被截断，纯色图也可能凭空产生前景 | 人脸种子须全部位于缩略图内部，并满足原面积约束 | 三种越界框回归；本地视觉完整管线原断言继续保留 |
| GrabCut 初始化依赖此前 RNG 状态，重复运行有边缘像素漂移 | 每次分割固定 OpenCV 当前线程的 RNG 种子；同一环境内串行、并发得到相同掩码 | 新用例先复现 2/12800 像素差异，再验证五种初始 RNG 状态及三线程执行 |
| Pose 缓存下载共享临时文件、失败路径不完整 | 进程内线程锁合并成功下载；跨进程用独立临时文件，SHA256 通过后原子替换。缓存读取失败、超限、超时均回退，清理本次临时文件 | `tests/test_pose_model_cache.py` 八项离线用例，含四调用者只下载一次 |
| 编辑头径后再次输入绝对头径仍按旧 analysis 比例计算；控件截断非常用尺寸 | 滑块读当前结构头径并容纳已有值；缩放基准取当前结构头径，头径结果使用输入绝对值；按原值重生成保持部件尺寸 | `test_explicit_new_head_size_overrides_previous_structure_head_edit`、大尺寸页面完整重生成用例 |

Pose 下载使用 10 秒网络 I/O 超时、16 MiB 大小上限与 30 秒传输期限检查。
期限在每次 `read1` 后检查，并非整个调用严格不超过 30 秒；锁等待也不计入传输期限。
校验不通过的新文件不会替换既有缓存。普通测试使用缺失的临时模型路径，避免读取
开发机模型缓存或意外下载；专门缓存测试自行覆盖该配置。未进行真实模型下载。

### 确定性修复依据

[OpenCV GrabCut 源码](https://github.com/opencv/opencv/blob/4.x/modules/imgproc/src/grabcut.cpp)
用 k-means++ 初始化 GMM；[核心接口说明](https://github.com/opencv/opencv/blob/4.x/modules/core/include/opencv2/core.hpp)
说明 `theRNG` 按线程独立，`setRNGSeed` 设置默认 RNG 状态（2026-09-08 核实）。
因此在调用前固定种子，不需要串行化批量图片分割；不承诺跨 OpenCV 版本逐像素一致。

### 性能对照

沿用上一轮 240×480 合成图、无 provider/pose 的测量条件，交替运行共享与
禁用缓存两条路径各六次，分别剔除首轮。为单独衡量复用收益，对照路径也统一
`max_side=160`，通过替换 `SubjectObservation.extract` 为每次直接
`extract_subject(image, 160)` 实现。最终种子修复后的结果：

| 模式 | 每图分割调用 | 后五次总管线耗时中位数 |
|---|---|---|
| 不缓存、统一 160px | 3 | 0.1074 秒 |
| 共享主体观测 | 1 | 0.0543 秒 |

本机场景耗时约降低 **49.4%**；`analysis`、`geometry`、`params`、`color_bands`
四项输出全部相等。这是合成输入与固定依赖环境内的对照，不是授权真实照片准确率、
跨版本一致性或所有工作负载的加速保证。修改前不同缩放尺寸的三次分割基线仍保留在上一节。

### 最终验证

- `.venv/bin/pytest -q` → **932 passed, 1 skipped，37.37s**，较本轮起点新增 23 项通过。
- `.venv/bin/ruff check .`、`.venv/bin/mypy app tests`（84 源文件）与
  `git diff --check` 通过。
- 跳过项仍为缺少 `CROCHET_EVAL_DIR` 的授权真实照片评测；本轮没有进行真实
  模型下载、远程版本矩阵、发行包重建或实体试钩。所有修改保留在未提交工作树。

## 第四轮：编辑契约与装配连接 · 2026-09-08

本轮起点为上一轮的 **932 passed, 1 skipped**。

| 发现 | 最终行为 | 证据 |
|---|---|---|
| `CrochetStitch`/`CrochetPart` 把布尔值转为 0/1，原值丢失后自检无法发现 | 模型、原始 JSON 自检、Parade 共用 `integer_count`；拒绝布尔、小数及非有限值，保留整数字符串/整数浮点数 | `tests/test_edit_contract.py` 覆盖四种逐圈计数、部件数量和结构实例数量 |
| 空圈、重复圈号、重名部件可进入页面，引发空图解或进度控件标识冲突 | 部件 schema 要求非空圈与唯一圈号；重建拒绝空部件列表及重名部件，校验完成后返回新结果 | 同上；同步 `crochet_part.schema.json` 并通过漂移测试 |
| 图解修改非法时可能破坏当前编辑状态 | JSON 编辑与备份导入都先完成重建；失败保留原结果、PDF、分享缓存 | 页面三类坏输入 × 编辑/导入两入口回归 |
| 改了锚点、源连接端或连接方法，装配仍按名称套用默认文案 | 仅完整匹配默认边配置时使用模板文案，其余按实际连接与每个实例生成说明 | `tests/test_assembly_edits.py` 覆盖六类部件、非对称连接、左右互换与帽子缝合方法 |
| 一体件的连接目标全部显示为身体段 | 分组保留原目标部件名，区分一体件头部段/身体段 | 一体件耳朵连接回归 |
| 只改制作数量，连接图仍保留旧数量时，文案会虚构对称/均匀分配 | 显示制作数量、图中已连接实例数，并要求核对结构中的数量和位置 | 更新原数量回归的断言，保留默认模板与旧无图备份行为测试 |

计数/结构新用例在修复前为 **16 failed, 18 passed**；装配新用例先复现
**9 failed**，修复后再增加左右互换用例。数据结构合法但针数代数不一致的图解
仍可进入编辑页面并由自检报告，便于逐步修正；不会自动补写缺失的加减针。

旧备份中的空圈或重复标识需先在 JSON 中修正再导入。顶层备份版本不变，
正常旧格式与整数编码继续兼容。此次没有真实照片/实体试钩数据，未解除发布门禁。

最终全量 `.venv/bin/pytest -q` → **983 passed, 1 skipped，40.22s**，
新增 51 项通过；Ruff、mypy app tests（87 源文件）、Schema 文档同步及
`git diff --check` 通过。修改仍保留在未提交工作树，未运行远程矩阵或发行包重建。

## 第五轮：物理输入边界与预览旋转 · 2026-09-08

起点为 **983 passed, 1 skipped**。延续异常输入检查，发现结构正数约束仍接受
无穷大，`Gauge` 直接构造也允许零、布尔或非有限值；生成器没有统一验证结构，
导致错误延迟至除法、整数转换或圈列表分配阶段。新增尺寸用例先复现
**49 failed, 2 passed**，再修复以下路径：

- 分析尺寸、结构尺寸和图解尺寸共用有限数值解码，拒绝布尔值；图解尺寸为正数，
  新旧结构输入的三个厘米维度均须在 `(0, 200]` 内。200 cm 与分析层既有身高
  上限一致，是工程输入边界，不代表成品尺寸可行性或全部资源消耗已获上界证明。
- `generate_params` 在分配针法圈前校验结构。旧结构保留无图格式，规范化合法
  数字字符串，移除可选尺寸的 `null` 以使用已有缺省值；不原地改写输入。
- 显式 `Gauge` 构造限定在既有 UI 范围（6–40 针、8–50 行/10cm），错误直接报告。
  映射/UI 适配器继续按原规则回退与钳制；两种路径的合法数值计算保持相同。
- 参数编辑与导入新增无穷尺寸页面回归，失败时保留原结果、PDF 和分享缓存。

3D 预览另复现 Y 轴角度未参与投影：四个顶点旋转用例与一个倾斜圆柱 SVG 用例
失败，原双轴用例通过。现按 **Z→X→Y** 顺序应用三轴角度，保留旧双轴调用。
同步 `EulerRotation` 的契约说明及结构 Schema；示意图仍不是物理仿真。

新增证据位于 `tests/test_dimension_boundaries.py`、`tests/test_preview_geometry.py`
及页面回归；尺寸、密度、结构、生成、重生成和预览定向集 **171 passed**。
超范围/非法尺寸备份需修正 JSON 再导入；支持范围内的旧数字编码与可选空值保持兼容。

最终差异复核还发现可选数值字段叠加前置解码后，Schema 一度生成 `gt/le`
非标准关键字。调整约束在类型注解中的位置，使公开文件正确输出
`exclusiveMinimum/maximum`，并新增标准关键字断言；单纯的文件同步测试不能发现
这种“运行时有约束、外部 JSON Schema 工具忽略约束”的问题。

最终全量 `.venv/bin/pytest -q` → **1045 passed, 1 skipped，59.11s**，
较本轮起点新增 62 项通过；Ruff、mypy app tests（90 源文件）、Schema 同步及
`git diff --check` 通过。跳过项仍为未配置授权真实照片集。本轮未进行远程矩阵、
发行包重建或实体试钩；修改保留在未提交工作树。

## 第六轮：独立复核与修复 · 装配文案、pose 重试与资源边界 · 2026-10-02

本轮先以独立复核通读前五轮全部改动并复验基线：全量 **1045 passed, 1 skipped**，
Ruff、mypy（90 源文件）通过，文档记录与实际一致。随后按"先复现后修复"
处理复核发现（新增用例在未修复代码上先失败）：

| 发现 | 最终行为 | 证据 |
|---|---|---|
| 编辑锚点后的装配明细把内部实例 id（如「尾巴（tail）」）泄入中文文案；单实例部件的摘要行与明细行近乎重复 | 左右副本仍用左/右前缀；多副本的自定义 id 保留以区分实例；单实例合并为一行含自身锚点与开口说明的完整句子 | `tests/test_assembly_edits.py` 四项新回归（帽子缝合断言随合并行为更新，并断言无 id 泄漏） |
| 下载失败后每张批量图片都在锁内重新尝试下载：离线批量 = N 个超时窗口串行（上一轮"待核查"第 1 条，确认属实） | 进程内负缓存：失败后 300 秒内跳过重试；有效缓存始终绕过退避；成功下载清除标记 | `tests/test_pose_model_cache.py` 三项新离线用例（退避、过期恢复、缓存优先） |
| `CrochetPart` 尺寸只有 `gt=0`，比结构层 `(0, 200]` 更宽，公开 schema 同样缺失上界 | `PositiveMeasurement` 统一 `le=200`；schema 文档同步输出 `maximum`，标准关键字断言更新 | `tests/test_dimension_boundaries.py` 新增 201/1e100 参数化；`test_schema_docs.py` 断言更新 |
| 头身比说明行两端散文硬耦合，文案一处改动会让调尺寸的重写静默失灵 | 生成与重写共享 `PROPORTIONS_HEAD_BODY_PREFIX` 常量；调尺寸回归新增重写断言 | `test_resize_preserves_...` 扩展断言 |
| 旧格式结构不拒绝重名部件，生成的图解无法再次编辑；部件数无上限 | 旧路径要求字符串 name 并拒绝重名；两代格式统一部件数上限 64 | `tests/test_dimension_boundaries.py` 两项新回归 |
| 病态 JSON（10⁶ 圈、千级部件、1e99 针数）拖垮自检/重建，诊断不可读 | 自检与重建拒绝超过 64 的部件数；单部件圈数超过 2000 跳过逐圈检查并报告；单圈针数超过 100000 报上限并重置相邻链 | `tests/test_edit_contract.py` 两项、`tests/test_validation_boundaries.py` 一项 |
| share 解压上限常量名为 CHARS 实为字节 | 改名 `_MAX_DECOMPRESSED_BYTES` 并注明字节语义 | 既有字节边界用例更新引用后继续通过 |

### 验证记录

- 新增用例先在未修复代码上确认失败（14 failed + 10 errors），修复后定向集
  187 passed。
- 最终全量 `.venv/bin/pytest -q` → **1060 passed, 1 skipped，20.52s**，
  较本轮起点新增 15 项通过。
- `.venv/bin/ruff check .`、`.venv/bin/mypy app tests`（90 源文件）、
  schema 文档同步与 `git diff --check` 通过。
- 期间修正一个工程化问题：装配明细的嵌套闭包捕获循环变量触发 Ruff B023，
  改为普通循环构建明细列表；共享常量需先定义后引用。
- 资源上限是工程输入边界（200cm ÷ 最低行高 0.2cm ≈ 1000 圈的合法输出
  尚有两倍余量），不代表更大的图解必然非法。跳过项仍为未配置
  `CROCHET_EVAL_DIR` 的授权真实照片评测；未运行远程矩阵或发行包重建。
  修改保留在未提交工作树。

## 第七轮：独立复审 · 未覆盖模块扫描 · 2026-10-02

起点为第六轮提交（6428d56/f7828c7）后的干净树，复核基线 **1060 passed, 1 skipped**。
本轮以两个独立扫描代理覆盖前六轮未深审的 UI 层与辅助层（trials、evaluation、
images、colors、main 等 ~5200 行），同时人工复审核心算法模块（stitches、sizing、
profile_shaping、ring_chart、structure_designer、grid_pattern）及第六轮自身改动。

| 发现 | 最终行为 | 证据 |
|---|---|---|
| 「轮廓对应验证」折叠区被 `getattr` 过滤器静默禁用（params 部件恒为 dict，属性访问恒 None）——照片驱动的核心可视化从未真正展示 | 提取 `_silhouette_verifications` 纯函数（dict 访问），折叠区复活；病态圈行由渲染层容错降级 | `tests/test_result_renderer.py` |
| `geometry`/`sizing` 是备份可控的自由字段：`confidence: null/"abc"` → `float()` TypeError；头身比非数值 → 格式化 ValueError——导入坏备份后下一帧渲染整页崩溃且无法就地恢复 | 展示层容错解码（`_confidence_text`/`_ratio_text`），非法值转义显示为字面量 | 同上 |
| trials.py 裸 `int()` 遇 JSON `Infinity`/`1e400` 抛 OverflowError 越过 except 元组 → CLI 直接 traceback（友好错误契约失守）；布尔/小数静默强转（`true`→1、`2.9`→2）会污染校准统计 | quantity/stitches/时长改用 `integer_count`，身高改用 `finite_float`；试钩记录模型全部数值字段改用 `TrialInt`/`TrialFloat`（与 schemas 同一约定：拒绝布尔，保留整数字符串/整数浮点） | `tests/test_trials.py` 六项参数化 + 两项记录模型回归 |
| evaluation.py 冻结哈希只在数据集载入时校验，评测循环重新读文件（TOCTOU）——源图被并发替换时报告仍把分数归因到旧哈希 | 每例打分前重校验 SHA256，不匹配记为该例错误、不计分 | `test_evaluation.py` 中途替换用例 |
| trials/evaluation 共三处 `write_json`/`write_evaluation_report` 的 OSError 以 traceback 暴露 | 统一友好错误 + 退出码 1 | 修复为纯防御包装（权限类故障难以稳定注入，无专属回归） |
| `render_silhouette_svg` 对纯球部件（strip_dome 后为空列表）在两处 `max()` 抛 ValueError | `default=` 守卫，空列表降级渲染 | `test_profile_shaping.py` 空列表用例 |
| `vision_meta.source` 兜底文案未过 `md_safe`（分享/备份可控的 markdown 注入面）；`dl_parade_` 键未进 purge 前缀表（旧键随结果替换持续累积）；sidebar 损坏记录提示「可点删」却先 `st.stop()` 使删除键当轮不可达；tab_grid 升级前遗留会话缓存缺 `legend_html`/`c2c` 键会 KeyError | 全部修复：来源文案转义、purge 前缀补录、载入失败改 try/except/else 不中断渲染、旧缓存 `.get` 回退 | `test_audit_fixes.py` purge 断言扩展；其余为渲染路径小改 |
| colors.py 注释声称 24 色实际 30 色 | 注释改为跟随 `YARN_COLORS` 长度（由测试钉住） | 既有色表计数测试 |

核心算法模块复审结论：stitches（纯数据词条）、sizing（有界钳制）、grid_pattern
（严格导入、单元上限、C2C 坐标翻转正确）、ring_chart（转义齐全、整数算子分布）、
structure_designer（连接目标不在图内时不出边、重复 id 去重）未发现新问题；
profile_shaping 两处空列表边界如上修复。第六轮自身改动复查：装配文案合并、
pose 下载退避、资源上限交互未见回归。

### 验证记录

- 新增用例先复现：死代码过滤、trials OverflowError 均在修复前于 REPL 复现；
  修复后定向集通过。profile_shaping 第二处 `max()` 边界由新用例在修复后
  仍失败而暴露（同函数相邻行），随即补修。
- 最终全量 `.venv/bin/pytest -q` → **1074 passed, 1 skipped，22.70s**，
  较本轮起点新增 14 项通过。
- `.venv/bin/ruff check .`、`.venv/bin/mypy app tests`（91 源文件）、
  `git diff --check` 通过。跳过项仍为未配置 `CROCHET_EVAL_DIR` 的授权
  真实照片评测。未运行远程矩阵、发行包重建或实体试钩；修改保留在未提交工作树。

## 第八轮：外部审计处理 · 模块拆分与逐条核实 · 2026-10-04

处理一份外部全项目审计报告（2026-10-03）。方法论：**逐条对照代码核实后再动**
——报告有两处技术性误读（延迟导入、copy+thumbnail）与若干数据偏差，
全部按核实结论处置。起点基线 1074 passed, 1 skipped。

| 审计主张 | 核实结论 | 处置 |
|---|---|---|
| crochet_params.py 上帝模块（1396 行），建议拆 4-5 模块 | 属实；`_merge_head_body` 为类方法（报告对其位置的描述正确） | **采纳**：按真实依赖拆出 `parts`（微型助手+部件名常量，无依赖底座）、`time_estimate`（SECONDS 常量+时长）、`materials`、`assembly`（含 `_CLOSING_RE`/开口统计）、`onepiece`（纯函数化，调用点延迟导入避免环）。crochet_params 降至 892 行，公开名经再导出保持可导入；**零行为变化**（正则扩展单列为下一提交） |
| `_srgb_to_lab_vec` 三连 `np.stack` | 属实（网格量化热路径） | **采纳**：stack 一次复用 |
| gauge 属性内冗余 `import math` | 属实（4 处，非报告所称 5 处） | **采纳** |
| `_CLOSING_RE` 缺 未/没/别 变体 | 属实——"未收口"被误判为已闭合，装配文案丢失真实开口 | **采纳** + 三变体回归测试 |
| history `ESCAPE` 子句拼接可读性差 | 属实（安全但难审计） | **采纳**：模块常量 |
| preview 缺 data URL 前缀校验 | 属实（手改 DB 的注入面） | **采纳**：`load_result` 丢弃非 JPEG data URL 的 preview，图解本体不受影响 |
| orchestrator 内联缩略图属展示层关注点 | 属实 | **采纳**：`utils.images.thumbnail_data_url` |
| 裸 `except Exception` 分级（pose spans） | 部分属实（mediapipe 缺失在 pose.py 内已处理，此处是兜底） | **采纳**：ImportError→info，其余→debug |
| Docker 基础镜像摘要固定 / 内存说明 / .dockerignore | digest 经 `docker buildx imagetools inspect` 实核；.dockerignore 已齐全 | **采纳**前两项（附刷新流程注释）；第三项无需改 |
| LLM 响应负面测试不足 | 部分不实——已有 6 类负面用例 | **采纳**补 3 类：NaN/Infinity 字面量、10 万字符噪声前缀后取对象、纯噪声报错 |
| 延迟导入"每次调用都重新导入" | **不成立**——Python import 有 sys.modules 缓存，重复执行只是查表；真实判据是循环依赖 | 驳回迁移；onepiece 的真实环处已加注释（与报告自身"标注循环"的建议一致） |
| copy+thumbnail 改 resize | **不成立**——copy 防止原地修改共享解码缓存图（承重逻辑）；thumbnail 永不放大、保纵横比，resize 需手写等价逻辑且无收益 | 驳回 |
| `_sanitize_secrets` 去掉前后缀分段遮蔽 | **不成立**——整串替换在先，前后缀遮蔽的是**截断泄漏**的密钥片段（错误信息常只带半截 key），移除反而缩小安全覆盖；"重叠"只是过遮蔽，fail-safe | 驳回 |
| PatternResult `dict[str, Any]` 收紧为模型 | 不采纳——`from_result` 的宽容契约承载旧备份/旧 token（缺键走默认值是文档化行为）；信任边界校验已由 `validate_backup` + `rebuild_params` 在分享/导入/历史每个入口完成，"形同虚设"不成立 | 驳回并记录理由 |
| 毛线色表 30→40-50 色并外置 | 缓议——改色表影响全部配色输出与既有钉测；新增色需来源锚点（SOURCES 惯例）与选色决策 | 转入下一轮清单 |
| 时长模型加/减针分级系数 | 缓议——`SECONDS_PER_STITCH` 是 trials 校准基线先验，无实体试钩数据不改 | 转入下一轮清单 |
| mutation testing | 缓议——引入新工具依赖 | 不引入 |

### 验证记录

- 拆分以纯重构提交（`b60e35c`），修复以行为提交（`5d09b80`）分开，可独立回溯；
  手术脚本曾出现多行结束标记少含末行的截断缺陷，靠 py_compile 即时暴露并修复。
- 最终全量 `.venv/bin/pytest -q` → **1079 passed, 1 skipped，23.45s**
  （较本轮起点 +5）；Ruff、mypy app tests（96 源文件）、`git diff --check` 通过。
- 跳过项仍为未配置 `CROCHET_EVAL_DIR` 的授权真实照片评测；Docker 镜像重建
  属发布流程，本轮只核对摘要未重建。修改随轮次提交，工作树干净。

## 下一轮需继续核查

1. 照片处理：授权真实照片质量基线仍缺（需 `CROCHET_EVAL_DIR`）；可选 Pose
   检测每图开销待实测。
2. 生成与显示契约：资源边界与组合矩阵测试已建立；**毛线色表扩展与外置**
   （需选色与来源锚点决策）、**时长模型分级系数**（需试钩校准数据）为本轮
   转入的两项待决事项。
3. 发布验证：授权真实照片与独立实体试钩基线仍缺失。当前修复不解除 G3/G4，
   也不替代支持版本矩阵或新的发行包验证。

## 第九轮：导入、导出与部署边界（2026-10-04）

基线提交 `a8101d5`：1079 passed、1 skipped（58.08s）；以下记录修复完成、提交 GitHub PR 前的本地快照。

- 自检的错误分支原来挂在 `notes` 判断下，导致有效结果误报、错误结果有 notes 时
  隐藏错误。现按 `ok` 显示成功/错误，notes 独立展示；编辑应用、导入及 Markdown/PDF
  导出均拒绝代数错误，失败编辑保留当前结果及 PDF/分享缓存。
- **修正第八轮关于宽泛元数据契约的判断**：保留旧备份兼容不等于嵌套字段可以不校验。
  `geometry.silhouette` 为 list 的备份曾导入成功并崩溃。现在分享、历史和粘贴备份
  共用 `import_backup`；已知元数据由嵌套模型校验和规范化，缺失字段不伪造来源。
- Parade 导出返回结构化完整性、实体部件/圈次计数及警告；`parade_syntax_rate` 与
  `parade_export_rate` 分离，截断前缀通过语法检查也不能通过发布门禁。旧报告需重跑。
- Markdown/PDF 使用完整结果的来源和尺寸元数据，保留 Mock 标识及实体验证边界。
  新生成结果记录 `generator_version`，旧结果显示“未记录”，不反填当前版本。
- 历史记录默认关闭；`CROCHET_HISTORY_MODE=single_user` 仅用于可信单用户部署，
  数据库入口强制执行策略，公开/多人部署保持禁用。旧库保留；未实施多人认证体系。
- 新增跨流程测试覆盖四种自检状态、损坏元数据、失败编辑的状态保留、分享入口、
  分享→历史→调整尺寸→导出往返、PDF 来源标签及两个会话的禁用历史访问边界。

### 本轮验证结果

- Python 3.12.13；全量 `.venv/bin/python -m pytest -q -p no:cacheprovider`：
  **1103 passed, 1 skipped，48.39s**，较基线新增 24 项回归。
- Ruff、mypy app tests（99 个文件）、Schema 文档同步及 `git diff --check` 通过。
- 唯一跳过项为缺少授权照片数据的真实评测；未运行远端矩阵、依赖漏洞联网审计、
  Docker 重建或实体试钩。此为提交 GitHub PR 前的记录；后续远端验证以该 PR 的检查记录为准。

### 仍缺的发布材料

当前工作区没有 `eval_data/`、`trial_data/`，也未配置 `CROCHET_EVAL_DIR`。
G3/G4 继续阻断，不以合成图、已有单元测试或外部公开资料替代：

1. G3：至少 30 张分层授权照片、schema-v2 清单、逐图 SHA-256、权利/主体证据和
   人工真值；按 `docs/evaluation.md` 运行并检查完整导出门禁。
2. G4：精确图解哈希绑定的实际试钩记录、小样、用线克数、尺寸及分口径工时。
   校准与独立留出图解哈希必须隔离，数量/制作者多样性见 `docs/physical-trials.md`。
3. 修复本身不构成新提交的远端版本矩阵、依赖漏洞审计或发行包验证。

### GitHub 发布补充：HTTPX2 安全更新

创建 PR #10 时，GitHub 默认分支报告高危告警 GHSA-8xx6-hgc6-gc2m（流式响应解压
内存放大）。通过 GitHub 告警 API 核实受影响版本 `<2.12.0`、修复版 `2.12.0`，
按 `uv lock --upgrade-package httpx2==2.12.0` 更新锁文件，仅改变 httpx2/httpcore2
两包版本，并重新同步 dev/pdf/pose 环境。该更新在同一 PR 内重新执行受保护检查
及依赖审计；本记录不把早先提交的绿灯当作新锁文件的验证结果。

PR：https://github.com/paulkooer/CrochetPhoto2Pattern/pull/10
告警：https://github.com/advisories/GHSA-8xx6-hgc6-gc2m

安全更新后的本地验证：1103 passed、1 skipped（42.44s）；Ruff、mypy app tests
（99 文件）、`uv lock --check` 与 `git diff --check` 通过。
