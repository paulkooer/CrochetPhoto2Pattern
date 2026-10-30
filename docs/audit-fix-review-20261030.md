# 2026-10-30 软件一致性修复复核交接

状态：**最终独立验收 PASS，本轮原八项问题及三项后续补修均可关闭**。
验收固定提交为 `55280fb485d9182f264402c52cbc171c957c4c51`；真实照片评测、实体试钩和
真实浏览器端到端验证继续作为独立待办，项目保持 Beta 定位。

## 最终独立验收记录

根据项目维护者提供的 GPT Pro 最终独立验收报告，验收方拉取并核对上述提交，
复跑此前失败用例、同一份旧试钩 ZIP、直接相关边界及全量测试，结论为 PASS。

| 验证项 | 独立报告结果 |
| --- | --- |
| 固定提交 | `55280fb485d9182f264402c52cbc171c957c4c51` |
| 环境 | Python 3.12.14，锁定的 dev + pdf 依赖 |
| 全量测试 | 2076 passed、2 skipped，89.35 秒 |
| 静态与差异检查 | Ruff、mypy 通过（175 个源文件，按仓库配置），差异检查通过 |
| 工作树 | 干净 |
| 三项补修 | CLI 局部选择与完整复核状态、旧包规范化身份、历史绑定边界均 PASS，可关闭 |
| 原八项 | 直接复现修复保持通过，可关闭 |

两项跳过分别为缺少授权真实照片评测目录，以及验收环境不满足 MediaPipe 的
EGL/GLESv2 条件。开发方对同一提交的本地结果为 2076 passed、2 skipped，57.25 秒
（Python 3.12.13；MediaPipe 未安装）；两次运行分别记录，不混同环境或耗时。

验收方查询时，该 SHA 尚无公开 GitHub Check Runs 或 Actions 结果。以上为固定代码的
本地独立验收，合并仍须检查修复 PR **当前头提交**的远端 CI，不能沿用旧提交的成功状态。
本次闭项文档更新不改变应用代码、测试、锁文件或 CI 配置。

## 独立复核后的限定补修

外部复核对象为 `8f48ba174f7d2e54340321f534923dfa2b2e8841`，报告复跑结果为
2060 passed、2 skipped。以下补修直接基于该提交，完成于 `55280fb`，现已通过最终独立验收；
不将原提交的测试或远端状态当作新提交的验证。

| 补修 | 验收入口与边界 |
| --- | --- |
| P2：CLI 部件选择误标完整人工确认 | `tests/test_audit_followup_boundaries.py` 的 CLI 单图／批量与完整 UI 确认用例：显式部件不补入默认部件，来源为 `cli_explicit`，主体、头部和比例仍待复核；真正完整确认仍显示已复核。 |
| P2：旧试钩包被误判为改图 | 同文件的旧包原样打开、实测重算及真实修改拦截用例：使用实际 `4a19d70` 源码生成的冻结 ZIP；会话基线按规范化导入计算，原字节和记录 SHA 分别保留并校验。针法、圈序、颜色、数量、密度、工艺备注和连接开口变化仍阻断原包重算。 |
| P3：首次保存后旧快照丢失历史绑定 | 同文件的完整双页面用例：材料编辑→首次保存→撤销／重做，以及位置预览→首次保存→应用旧预览，均继续更新同一记录，保留进度及备注隔离；新建工作重新开始存储绑定。 |

冻结旧包及生成依据见 [trial_4a19d70](../tests/fixtures/trial_4a19d70/README.md)。
该包只有合成图解及软件测试用的小样值，不是实际制作记录。

## 原八项修复的固定版本

修复分支：`fix/audit-pattern-consistency`。原八项修复提交为
`8f48ba174f7d2e54340321f534923dfa2b2e8841`，父提交是已有的针法间隔修复
`0a1e9e48f96b01665381ce1b5271d769fd92dea8`，
在上一轮审核基线 `4a19d70f1e8f4000731580e7612e6d45d00ce168` 之后。
原八项改动可用 `git diff 0a1e9e48 8f48ba17` 单独检查；三项限定补修以本次新提交为准。

## 定向验收入口

下表测试均位于 [test_audit_consistency.py](../tests/test_audit_consistency.py)，
断言修复后的正确行为，不把旧反例脚本的成功退出当作修复通过。

| 项目 | 测试函数与预期 |
| --- | --- |
| 颜色说明与摘要 | `test_color_edits_refresh_neighbors_summary_export_and_restore`：新增、取消和中间单圈换色后，所有邻圈提示、摘要、Markdown 与备份恢复一致，保留用户备注。另有旧自动文案迁移及重复刷新不改色测试。 |
| 裙腰引用 | `test_skirt_assembly_uses_waist_including_legacy_restore_and_pdf`：腰口为 36 针；普通末圈 48 针、波浪末圈 96 针，装配、Markdown、PDF 和旧备份恢复均引用腰口。 |
| 筒壁配色 | `test_body_bands_cover_wall_height_independently_of_base`：两种直径、圆柱与轮廓身体的 20 圈等高筒壁均为黑 10 圈／白 10 圈，底盘沿用底端黑色。圆柱目标包含两个轴向收针圈，测试明确构造实际 10 cm、每 cm 两圈的筒壁。 |
| 历史 ID | `test_manual_save_history_reload_keeps_both_tabs_independent`：通过完整应用 AppTest 手动生成、保存、载入照片页，进度、备注、材料编辑、清理和重复载入独立，重新保存更新同一历史记录。 |
| CLI 部件选择 | `test_photo_and_batch_cli_honor_explicit_parts`：自制 PNG 输入配合 `--parts 头部,身体`，单图和批量均只生成这两个部件。 |
| 一体件头径 | `test_onepiece_preserves_head_measurement_for_materials_and_backup`：分件头径与一体件头部尺寸均保留 15 cm，材料均选取 14 mm 眼件，备份恢复后相同。 |
| 摘要转义 | `test_sidebar_escapes_history_title_and_summary`：自定义标题和自动摘要中的 Markdown 图片、链接标记被转义。 |
| 纯位置编辑 | `test_position_only_changes_preserve_manual_rounds`：先将手臂从 8 圈手改为 9 圈，再移动头部，9 圈及备注原样保留；改变头径或密度仍重新生成且通过校验。 |

## 对固定提交执行的检查

```bash
git rev-parse HEAD
uv sync --locked --extra dev --extra pdf
.venv/bin/python -m pytest -q -rs
.venv/bin/ruff check .
.venv/bin/mypy app tests
git diff --check
git status --short
```

全量检查包含八项定向验收及历史、编辑、导入导出、工程、密度重算等直接受影响的既有测试。
测试开始后不再修改业务代码；如果修改，应重新报告对应提交及验证范围。

## 兼容与验证边界

新增字段可选，顶层备份版本仍为 1。旧自动文案迁移、开口圈、头部尺寸、
历史身份与展示身份的兼容行为见 [工程格式说明](project-format.md#图解数据的一致性与兼容读取)。
导出缓存版本为 10，避免复用旧说明。

本轮使用合成输入和 Streamlit AppTest。真实浏览器上传、画布、下载及新会话恢复，
授权真实照片评测、实体试钩和外部 CrochetPARADE 仿真仍未验证；它们分别记录，
不与本批软件缺陷的定向复核混为一项。项目继续保持 Beta 定位。
