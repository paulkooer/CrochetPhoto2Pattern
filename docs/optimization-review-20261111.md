# 2026-11-11 系统审查与处理记录

这是该轮审查的事实快照；当前发布状态以[系统状态](system-status.zh-CN.md)为准。
合成图片、静态公式和自动化测试均不能替代授权真实照片评测或实体试钩。

## 复现与处理

| 项目 | 状态与边界 |
| --- | --- |
| A1 主体坐标 | [PR #65](https://github.com/paulkooer/CrochetPhoto2Pattern/pull/65) 将部件比例先验映射到轮廓估算的主体范围；姿态实测和人工框选仍使用整图坐标。平移构图的合成图中，四个部件的圈色和身体筒壁针数保持一致。40 带轮廓、遮挡和分割错误仍会限制精度。 |
| A2 阶梯球密度 | 2026-11-12 起新生成的阶梯球按针宽和行高估计圈数，并以每圈最多 6 针分布塑形；极端密度无法匹配目标圈数时提示。旧备份圈序不变。下方保留修复前模型数值；[G4 试钩](physical-trials.md)与真实成品形状仍无实测依据。 |
| A3 理想球末圈 | 图解末圈仍可能为 6 针；说明已改为如实提示可能过尖，不再同时要求勿减至 6 针。未声称已改进实体形状。 |
| A4 开口与颈部 | 新图解以连接状态、开口圈和一体件颈部圈为结构数据；备份升为版本 3。校验器只拦截独立明确或已知生成器的收口指令，不把普通否定备注当作闭合；自由文本并非完整自然语言解析。未标版本及版本 1、2 继续使用原有文字回退，仍可能遇到文字歧义。工程进度兼容有回归测试。 |
| A5 WebP | 评测清单与上传入口统一接受 JPEG、PNG；WebP 在清单校验阶段拒绝。 |
| B1 G3 | 报告版本 5 增加耳朵、裙子、尾巴提示的非门禁 precision/recall 及不可用计数。2026-11-12 用户选择全自动口径后，无交互 CLI 与默认评测自动交付未经校准的轮廓候选；报告版本 6 记录该方式，原门槛不变。确认页仍可人工选择；没有授权真实照片数据，不能声称已达门槛。 |
| B2 语义配色 | **保留兼容。** `hair_color`、`top_color`、`bottom_color` 和 `clothing_type` 可存在于旧图解并参与重算，直接删除会改变旧数据行为。当前生产路径不自动提供这些字段，未新增手动输入控件。 |
| C1 文档 | 中英文状态页收敛到当前结论、门禁和证据；历史状态保留在固定 Git 版本。未新增自动生成或翻译 changelog 的脚本。 |
| C2 分支与依赖 | [PR #66](https://github.com/paulkooer/CrochetPhoto2Pattern/pull/66) 对常规 minor/patch 更新分组；安全更新仍独立处理。没有添加可能影响安全更新的 OpenCV ignore 规则，也没有批量关闭 PR 或删除分支。 |
| C3 测试组织 | 新测试按模块/行为命名，贡献指南要求继续如此；没有大规模搬迁旧测试。 |
| C4 CI | PR #66 保留四个 Python 版本的全量测试，仅 3.12 收集并校验覆盖率。该版本矩阵已通过远端检查；可选依赖作业仍保留全量测试。 |
| C5 其他 | 新的本地照片结果不再由头身比推测胖瘦；手动体型仅作记录，空 API 用量不再出现在诊断中。`generate_params` 拆分、`PartKind` 分派收敛及其他重构尚未完成。PR #65 的同一次本机覆盖率运行中 `parade_export.py` 为 92%、`uploads.py` 为 59%，不能直接把旧报告的数字当成当前值。 |

## 可复现实验

```bash
.venv/bin/pytest -q tests/test_subject_relative_spans.py tests/test_connection_semantics.py tests/test_evaluation_hints.py
.venv/bin/pytest -q --cov=app --cov-report=term --cov-fail-under=80
```

以下复现修复前不传密度的历史阶梯序列；新生成路径会传入密度并调整圈次：

```python
from math import pi
from app.models.crochet_params import _sphere_rounds, _stitches_for_diameter
from app.models.gauge import PRESETS

for name, gauge in PRESETS.items():
    peak = _stitches_for_diameter(8.3, gauge)
    equivalent_diameter = peak * gauge.stitch_w_cm / pi
    arc = len(_sphere_rounds(peak)) * gauge.row_h_cm
    ideal = pi * equivalent_diameter / 2
    print(name, peak, round(equivalent_diameter, 3), round(arc, 3), round(ideal, 3))
```

修复前本机结果（厘米；等效直径由量化后的最大围针数换算）：

| 密度 | 最大围 | 等效直径 | 圈数 × 行高 | 理想球经线估计 | 相对差 |
| --- | ---: | ---: | ---: | ---: | ---: |
| classic | 36 | 8.815 | 10.625 | 13.846 | −23.3% |
| dk | 42 | 7.864 | 14.286 | 12.353 | +15.6% |
| fine | 54 | 8.594 | 16.250 | 13.500 | +20.4% |

修复后，同一模型下 classic/dk/fine 分别为 22/17/22 圈，圈数乘行高与理想经线
估计相差约 −0.7%/−1.7%/+1.9%。这是纸面模型比较：量化、针法变形和填充会影响实物，
不能据此声称成品误差或实体形状已达标。
PR #65 对应的本机完整运行是 2823 passed、2 skipped、覆盖率 94.47%；未做真实照片评测或实体试钩。
