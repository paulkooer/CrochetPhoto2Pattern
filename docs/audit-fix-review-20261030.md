# 2026-10-30 软件一致性修复复核交接

状态：**开发方报告修复完成，独立复核待完成**。本文不关闭问题，也不作为独立复核通过证明。

修复分支：`fix/audit-pattern-consistency`。本批修改基于
`0a1e9e48f96b01665381ce1b5271d769fd92dea8`；该父提交是已有的针法间隔修复，
在上一轮审核基线 `4a19d70f1e8f4000731580e7612e6d45d00ce168` 之后。
本批修复可用 `git diff 0a1e9e48f96b01665381ce1b5271d769fd92dea8 HEAD` 单独检查。
最终提交 SHA 和对该提交执行的测试结果随交接消息提供。

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
