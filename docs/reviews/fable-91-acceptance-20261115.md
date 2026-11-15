# #91 Fable 独立验收记录（2026-11-15）

来源：维护者转交的 Fable 独立报告。本页由开发方整理，未新增独立复核。
这是评论性质的验收记录，没有正式 GitHub APPROVE，不应记作“已批准”。

## 提交与结论

- 待审提交：`d2effababe7a7af4ba332207a55bbd46e9c454f8`（#91）。
- 基线：`294cbe118b4f0546bf40b656d2e176f509097162`。
- 报告确认当时 main `0b91f49` 的 `app/` 与待审提交完全一致，结论同样适用。
- 交接范围内没有发现行为变化，另有下述入口回归和守卫缺口；两者不影响文档中的用法。

## 两项低严重度发现

1. `python app/trials.py …` 在基线可运行，待审提交因 `from .trial_tools…` 报
   `ImportError: attempted relative import with no known parent package`。建议改用
   `from app.trial_tools…`，并增加 `python app/trials.py --help` 的回归测试。
   文档使用的 `crochet2pattern-trials` 和 `python -m app.trials` 在两棵树上输出、退出码一致。
2. `tests/test_layering.py` 的 `_HEADLESS` 没有包含 `app/trial_tools/`。建议纳入全部
   Python 文件。新包目前没有 Streamlit 或 `app.ui` 导入，加载时的子进程检查仍覆盖它；
   缺少的是对函数内延迟导入的静态检查。

Fable 没有修改这两处，以保持验收独立。后续修复须以自己的检查和复核结果验收，
不能自动继承本次结论。

## 报告中的证据

| 范围 | 静态对照 | 运行时对照 |
|---|---|---|
| 试钩工具拆分 | 36 个定义、17 条模块级语句的 AST 一致；35 个函数的 183 处全局引用解析到同一批对象 | 2199 个场景逐字段一致 |
| 评测汇总重构 | 仅 `evaluate_dataset` 改写；还原 `totals.X` 后，循环体 13 条及汇总 35 条语句一致 | 258 个场景一致，含 2122 个案例评分和 674 个管线错误 |
| 网格辅助函数拆分 | 内联 8 个辅助函数后，`render_tab_grid` 的 AST 一致 | 69 个场景、408 步的控件树、消息和会话状态一致 |

- 试钩新代码行覆盖 99%（716 行中 9 行未执行）；20 处植入行为改动检出 19 处。
- `from app.trials import *` 的 69 个公开名字不变；没有测试或代码经 `app.trials` 打补丁。
- wheel 包含全部 7 个新模块。
- 网格比较去掉 Streamlit 自动生成的控件 ID；同树重复运行也出现该差异。
- 报告在 main 上运行试钩、评测、网格与分层相关测试，344 个通过；未重跑全量 3030 个测试。

以上均为 Fable 报告中的结果，不是开发方对后续修复的验证结果。

## 未覆盖边界

- 未审 #91 的 `app/models/crochet_params.py`、`app/models/assembly.py`、
  `app/ui/design_system.py`、`app/schemas.py` 改动。
- 网格仅通过 Streamlit AppTest 驱动，未验证真实浏览器下载、上传控件或 CSS。
- 评测主要使用合成数据和自定义运行器；默认本地视觉管线只运行了 2 例冒烟。
- 试钩未执行的 9 行涉及读文件期间增长、包未安装时版本回退及内置证据超限或损坏；
  这些行的 AST 未变。离散度门槛由 `>` 改成 `>=` 的植入改动未检出，缺少恰好 25% 的输入。
- 试钩 ZIP 仅比较成员内容，未比较压缩包字节；`trial_bundle.py` 不在 #91 内。
- 环境仅为 macOS、Python 3.12.13 和本机 `.venv`，未重复 Python 3.11 或 Linux。

复现脚本与小型日志保留在本机忽略目录
`eval_outputs/maintenance-closeout-20261115/fable-91-acceptance/`，不随本页提交。
报告使用 `git archive` 导出两棵树，再分别运行 `trial_diff.py`、`eval_diff.py`、
`grid_diff.py`，通过 `compare_logs.py` 和 `grid_compare.py` 比较输出。

工程侧后续为上述两项小修复。G3 授权照片和 G4 实体试钩仍是正式发布前的硬门槛；
本次验收不解除它们。
