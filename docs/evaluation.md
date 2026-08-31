# 授权真实照片评测

**简体中文** | [English](evaluation.en.md) | [文档索引 / Documentation index](README.md)

真实评测只运行本地视觉路径，不调用 OpenAI、Anthropic 或第三方中转站。照片、
带识别含义的文件名及报告默认放在 Git 忽略的 `eval_data/`、`eval_outputs/`；
清单中的授权声明只是审计记录，不能替代适用地区所需的真实同意流程。

## 1. 建立数据集

```bash
mkdir -p eval_data/release-01 eval_outputs
cp docs/eval_manifest.example.json eval_data/release-01/eval_manifest.json
shasum -a 256 eval_data/release-01/standing-plain-001.jpg
```

把输出的 64 位哈希填入清单。评测开始前会验证所有文件的 SHA-256；图片被替换、
重新压缩或旋转后必须重新标注版本和哈希，避免结果与实际输入脱节。

清单必须包含：

- `schema_version`：当前固定为 `1`。
- `dataset`：数据集名称、版本、权利基础、评测用途批准、个人数据标记和保留策略。
- `thresholds`：最小样本数与发布质量阈值。
- `cases`：稳定案例 ID、相对文件路径、SHA-256、场景标签和人工真值。

部件和颜色必须使用项目规范名称。`dominant_colors` 可提供最多三个可接受主色；
预测前三色命中任意一个即算成功。`tags` 只允许小写 ASCII，便于跨报告统计。

## 2. 数据集分层

首个发布基线建议至少 30 张，并避免同一人物连续照片构成虚假的大样本。至少覆盖：

- 全身、半身/特写、坐姿或遮挡；
- 纯色背景、室内杂乱背景、低对比背景；
- 有/无裙摆、深浅肤色、浅色/深色服装；
- 横图、竖图、带 EXIF 旋转的手机照片。

报告会输出 `tag_counts`。它不会自动判断分层是否合理；发布审核者需要检查分布，
并确保测试集没有被用于针对性调参。

## 3. 运行与状态码

```bash
uv run crochet2pattern-eval \
  --dataset eval_data/release-01 \
  --out eval_outputs/release-01.json
```

- `0`：清单有效且所有聚合门禁通过。
- `1`：清单、路径、授权字段、图片或哈希无效。
- `2`：评测已完成，但质量指标未达到清单阈值。

探索阶段可加 `--allow-fail` 保持状态码 `0`，但报告中的 `summary.passed` 仍为
`false`，不得把它作为发布通过凭据。

也可以接入 pytest 门禁：

```bash
CROCHET_EVAL_DIR=eval_data/release-01 \
CROCHET_EVAL_REPORT=eval_outputs/pytest-release-01.json \
uv run pytest -q tests/test_eval_real.py
```

## 4. 指标含义

- `macro_part_f1`：逐图部件集合 F1 的宏平均，同时惩罚漏检和多报。
- `case_pass_rate`：部件召回达到单图阈值、已标注裙摆/主色命中且图解自检通过的比例。
- `flare_accuracy`：仅在提供 `flare` 真值的案例上统计。
- `color_top3_accuracy`：仅在提供主色真值的案例上统计。
- `pattern_valid_rate`：生成图解通过针数代数和塑形门禁的比例，发布默认必须为 100%。

这些指标衡量照片到图解的软件行为，不能证明实际尺寸、用线量、工时或成品可钩性。
实体试钩需要独立记录毛线批次、小样密度、实际尺寸、耗材、工时和人工修改。
