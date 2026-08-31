# 实体试钩记录与校准

**简体中文** | [English](physical-trials.en.md) | [文档索引 / Documentation index](README.md)

试钩工具把“尺寸可能需要调整”变成可追溯数据，但不会自动修改生成器常数。
原始记录与报告默认放在 Git 忽略的 `trial_data/`、`trial_outputs/`。

## 1. 从精确图解创建草稿

先生成完整图解 JSON，再创建绑定其 SHA-256 的试钩记录：

```bash
uv run crochet2pattern --mock --out pattern.json --quiet
mkdir -p trial_data trial_outputs
uv run crochet2pattern-trials init \
  --pattern pattern.json \
  --trial-id classic-001 \
  --maker-id maker-a \
  --cohort calibration \
  --out trial_data/classic-001.trial.json
```

`maker_id` 应使用稳定的匿名标识，不要填写姓名、邮箱或账号。工具会从图解正文
重新计算实体总针数和总圈数，不信任可能过期的派生字段。

## 2. 完成记录

钩织完成后编辑 `*.trial.json`：

```json
{
  "status": "completed",
  "swatch": {
    "measured": true,
    "stitches_per_10cm": 13,
    "rows_per_10cm": 16,
    "hook_mm": 4,
    "yarn_brand": "品牌",
    "yarn_line": "系列",
    "yarn_lot": "批次",
    "fiber": "棉"
  },
  "observation": {
    "completed_on": "2026-08-30",
    "overall_height_cm": 18.7,
    "yarn_used_grams": 92.4,
    "yarn_used_meters": null,
    "active_minutes": 162,
    "time_scope": "round_crochet_baseline",
    "pattern_modified": false,
    "modifications": [],
    "notes": "仅记录与复现相关的信息"
  }
}
```

实际文件还必须保留 `schema_version`、`trial_id`、`maker_id`、`cohort` 和工具生成的
`pattern` 字段。建议：

当前试钩模式版本为 2。旧的版本 1 完成记录需要补上 `time_scope` 并将
`schema_version` 改为 `2`；工具不会猜测旧记录是否包含收尾工时。早期版本2记录没有
`cohort` 时会兼容为 `calibration`，但留出验证记录必须显式写
`cohort="validation"`。

- `active_minutes` 只计实际操作时间，暂停和等待不计入。若只计逐圈钩织和换圈操作，
  使用 `time_scope="round_crochet_baseline"`；若包含缝合、填充、换色、刺绣或其他收尾，
  必须使用 `time_scope="full_project"`，该工时仍会显示但不会推导每针秒数。
- `yarn_used_grams` 只计毛线，不含填充棉、安全眼、金属件和剩余线团。
- 只有可靠测量起始/剩余长度时才填 `yarn_used_meters`。
- 任何增删圈、改针数或改部件都必须设置 `pattern_modified=true` 并写入
  `modifications`；这类记录仍参与偏差观察，但不进入常数校准。

## 3. 聚合分析

```bash
uv run crochet2pattern-trials analyze \
  --records trial_data \
  --out trial_outputs/baseline.json
```

- `0`：克重与基础工时两组都至少有5个完成且未改图解的合格试钩，并各自覆盖至少3个
  不同图解哈希和2名匿名制作者，可以进入人工校准审核。
- `1`：记录格式、范围、重复 ID 或 JSON 无效。
- `2`：报告已生成，但样本数量/多样性不足。

探索期可添加 `--allow-insufficient`，但报告仍保持
`summary.calibration_ready=false`。

### 独立留出验证

候选常数只能来自 `calibration`。至少另外准备3个完成、未改图解、基础工时口径的
`validation` 记录，覆盖至少2个不同图解哈希和2名匿名制作者，而且这些哈希不得出现
在校准集中：

```bash
uv run crochet2pattern-trials init \
  --pattern unseen-pattern.json \
  --trial-id holdout-001 \
  --maker-id maker-b \
  --cohort validation \
  --out trial_data/holdout-001.trial.json

uv run crochet2pattern-trials analyze \
  --records trial_data \
  --require-validation \
  --out trial_outputs/release-review.json
```

`--require-validation` 会在留出样本不足或图解哈希重叠时返回2。报告中的
`independent_validation.sample_ready=true` 只证明样本量、多样性和隔离条件满足，
不会自动宣称当前或候选常数准确；仍需人工审查尺寸、克重和工时偏差分布。

## 4. 报告口径

- 尺寸：实际总高 ÷ 图解目标总高。
- 密度：实际小样针/行密度 ÷ 图解密度。
- 克重：实际克数 ÷ 实体总针数，再按针宽×行高归一到默认基准针面积。
- 工时：从实际秒数扣除当前每圈10秒固定开销，再除以实体总针数。
- 米数：仅使用同时记录实际米数和克数的案例，换算到每100g。

聚合值使用中位数并同时报告中位绝对偏差、最小值和最大值，降低个别异常样本
的影响。即使数量达标，归一化克重或单针工时的相对中位绝对偏差超过25%，也不会
产生相应候选值。克重与基础工时有各自的 `ready` 和 `blockers`；完整项目工时不会
阻塞克重候选，但不能产生每针秒数候选。`init` 默认拒绝覆盖已有记录；只有明确传入
`--force` 才允许覆盖。
候选值出现也不代表应立即修改生产常数；正确流程是人工检查原始案例、修改常数、
用未参与校准的独立试钩集再次验证。

该工具暂不建模个人钩织速度、不同针法、填充松紧、纤维吸湿和线批差异。
样本增加后应按制作者、线材/针号和图解复杂度分层，而不是把所有记录混成一个常数。

## 5. 网络试钩证据

发行包内置一个只保存少量事实、来源与使用边界的
[`external-trial-evidence.json`](../app/data/external-trial-evidence.json)。它不包含外部图解正文、
图片、用户名或自由文本项目笔记。先单独验证并生成上下文报告：

```bash
uv run crochet2pattern-trials external-report \
  --curated \
  --out trial_outputs/external-context.json
```

也可以把该上下文附在本地试钩报告中：

```bash
uv run crochet2pattern-trials analyze \
  --records trial_data \
  --curated-external-evidence \
  --out trial_outputs/baseline-with-context.json
```

如需使用自有证据文件，把 `external-report --curated` 换成
`external-report --evidence path/to/evidence.json`，或在 `analyze` 中使用
`--external-evidence path/to/evidence.json`。内置和自有证据参数互斥，防止来源混淆。

外部证据模型强制记录来源 URL、访问日期、证据类型、验证层级、原始记录是否可得、
复用依据和样本声明。`calibration_allowed` 在模式中固定为 `false`；外部数字只能出现在
`external_evidence` 上下文，不能改变 `recommendations` 候选值。

当前索引有三种不同证据强度：

- Ma Pelote 声称其工时汇总来自 312 个完成项目和平台计时器，并公布了尺寸、工时中位数
  与部分范围；但原始逐条记录不可下载，当前验证层级仍是 `source_claim`。
- 作者完成样品可以提供用线、尺寸或时间，但通常没有本系统所需的精确总针数和图解哈希。
- “约需多少线”的图解规格即使配有成品照片，也不能等同于称重后的实际消耗，因此单独标为
  `published_pattern_specification`。

基于这些限制，网络数据目前只适合两件事：检查系统估算是否存在明显数量级偏差，以及确定
后续本地试钩应优先覆盖哪些尺寸。不能用“同样高 18 cm”直接推导每针秒数，因为部件数、
缝合、换色、刺绣、针法、线材和制作者熟练度都可能不同。

调研时还检查了两个看似相关但未收入证据文件的来源：CrochetBench 是图解理解/生成基准，
不是实体试钩记录，而且数据集采用限制商业用途的 CC BY-NC 4.0；Ravelry 条款也不支持把
站内图解或用户内容默认批量复制到本项目。未来若接入 Ravelry，应仅接受用户授权导出的
自有项目数据，并继续保留来源和权限信息。
