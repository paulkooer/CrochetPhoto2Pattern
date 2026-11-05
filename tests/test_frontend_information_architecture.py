"""Sidebar order and chapter-5 layering after the 2026-11-03 information-architecture pass.

These checks guard the control flow the layout depends on: both "open existing
work" entries must render when history is disabled (the default deployment), the
advanced JSON panel must hold both raw editors while every download stays outside
it, and an unapplied JSON draft must survive a full rerun triggered elsewhere.
"""
import json
from copy import deepcopy
from io import BytesIO

from streamlit.testing.v1 import AppTest

from app.utils.trial_bundle import create_trial_bundle, encode_trial_bundle
from tests.test_app_smoke import _APP, _mock_result

_RENDER = """
import streamlit as st
from app.ui.result_renderer import render_results
render_results(st.session_state.result, "result")
"""


def _outline(block) -> list[tuple[str, object]]:
    """Flat, in-order (type, label-or-key-or-value) pairs for a block's subtree."""
    items: list[tuple[str, object]] = []
    for child in block.children.values():
        identifier = (getattr(child, "label", None) or getattr(child, "key", None)
                      or getattr(child, "value", None))
        items.append((child.type, identifier))
        if hasattr(child, "children"):
            items.extend(_outline(child))
    return items


def test_sidebar_puts_gauge_first_and_groups_existing_work(monkeypatch):
    monkeypatch.setenv("CROCHET_HISTORY_MODE", "disabled")
    at = AppTest.from_file(_APP, default_timeout=30).run()
    assert not at.exception
    assert [item.value for item in at.sidebar.subheader] == ["编织密度（小样）", "打开已有工作"]
    assert [item.label for item in at.sidebar.expander] == [
        "塑形选项（进阶）", "打开备份图解", "打开试钩包", "我的图解（历史）"]
    outline = _outline(at.sidebar)
    gauge = outline.index(("select_slider", "密度预设"))
    shaping = outline.index(("expander", "塑形选项（进阶）"))
    existing = outline.index(("subheader", "打开已有工作"))
    assert gauge < shaping < existing < outline.index(("expander", "打开备份图解"))
    assert len(at.sidebar.divider) == 1


def test_history_disabled_keeps_both_open_entries_usable(monkeypatch):
    monkeypatch.setenv("CROCHET_HISTORY_MODE", "disabled")
    bundle = create_trial_bundle(_mock_result("trial-source"), trial_id="ia-trial",
                                 maker_id="maker-a", cohort="calibration")
    upload = BytesIO(encode_trial_bundle(bundle))
    monkeypatch.setattr("app.ui.trial_editor.st.file_uploader",
                        lambda *a, **k: upload if k.get("key") == "trial_open_file" else None)
    at = AppTest.from_file(_APP, default_timeout=30).run()
    assert not at.exception
    assert any("历史记录未启用" in item.value for item in at.sidebar.caption)
    # The history panel used to ``return`` from inside the sidebar function.
    assert at.sidebar.button(key="open_backup_apply").disabled
    assert not at.sidebar.button(key="trial_open_apply").disabled
    at.button(key="trial_open_apply").click().run()
    assert not at.exception and not at.error
    assert at.session_state["trial_workspace_result"]["bundle"] == bundle
    assert at.session_state["result"]["result_id"] != "trial-source"


def test_chapter_five_layers_common_editors_above_one_advanced_panel():
    at = AppTest.from_string(_RENDER, default_timeout=30)
    at.session_state["result"] = _mock_result("ia-layout")
    at.run()
    assert not at.exception
    labels = [item.label for item in at.expander]
    assert "调整部件结构（高级）" not in labels
    advanced = labels.index("高级编辑（JSON）")
    assert (labels.index("快速调整尺寸（不重新识别照片）") < labels.index("可视化编辑部件")
            < labels.index("逐圈表格编辑") < labels.index("按实际毛线与试片估算用量") < advanced)
    # 挂载闩（2026-11-05）：启用前不渲染编辑器控件；点击「启用」并重新运行后
    # 挂载两段编辑器（草稿保留语义由下方 draft 测试覆盖）。
    assert not any(area.key == "json_edit_ia-layout" for area in at.text_area)
    at.button(key="json_open_ia-layout").click().run()
    assert not at.exception
    panel = next(item for item in at.expander if item.label == "高级编辑（JSON）")
    assert {area.key for area in panel.text_area} == {"json_edit_ia-layout", "struct_edit_ia-layout"}
    assert {button.key for button in panel.button} == {
        "edit_ia-layout_json_preview", "regen_ia-layout",
        "edit_ia-layout_structure_preview", "struct_go_ia-layout"}
    assert not panel.download_button
    assert {item.label for item in at.download_button} >= {"备份完整结果", "下载 JSON", "下载 Markdown 图解"}
    outline = _outline(at.main)
    assert (outline.index(("button", "↶ 撤销修改"))
            < outline.index(("expander", "快速调整尺寸（不重新识别照片）")))


def test_json_draft_survives_preview_and_cancel_then_applies():
    result = _mock_result("ia-draft")
    at = AppTest.from_string(_RENDER, default_timeout=30)
    at.session_state["result"] = deepcopy(result)
    at.run()
    at.button(key="json_open_ia-draft").click().run()
    assert not at.exception
    draft = deepcopy(result["params"])
    draft["parts"][0]["rounds"][0]["notes"] += "；核对张力"
    text = json.dumps(draft, ensure_ascii=False)
    at.text_area(key="json_edit_ia-draft").input(text).run()
    assert not at.exception
    # Once under the editor, once above the downloads.
    assert len([item for item in at.caption if "JSON 草稿" in item.value]) == 2
    at.button(key="edit_ia-draft_size_preview").click().run()
    assert not at.exception
    assert any("修改影响预览" in item.value for item in at.markdown)
    assert at.text_area(key="json_edit_ia-draft").value == text
    at.button(key="edit_ia-draft_preview_cancel").click().run()
    assert at.session_state["result"]["result_id"] == "ia-draft"
    assert at.text_area(key="json_edit_ia-draft").value == text
    assert len([item for item in at.caption if "JSON 草稿" in item.value]) == 2
    at.button(key="regen_ia-draft").click().run()
    assert not at.exception and not at.error
    applied = at.session_state["result"]
    assert applied["result_id"] != "ia-draft"
    assert applied["params"]["parts"][0]["rounds"][0]["notes"].endswith("核对张力")
    assert not [item for item in at.caption if "JSON 草稿" in item.value]


def test_result_page_folds_sources_and_moves_coordinates_into_json():
    """2026-11-05：结构表默认列不含开发者坐标串，来源与限制默认折叠进面板。

    「位置 / 旋转」列只出现在「查看结构 JSON」里；坐标说明 caption 随之移动；
    来源面板本身由浏览器回归检查默认折叠状态（AppTest 无折叠可见性概念）。
    """
    at = AppTest.from_string(_RENDER, default_timeout=30)
    at.session_state["result"] = _mock_result("ia-sources")
    at.run()
    assert not at.exception
    structure = next(item.value for item in at.dataframe if "连接" in item.value.columns)
    assert "位置 / 旋转" not in structure.columns
    assert {"部件", "数量", "形状", "尺寸", "连接", "基准色"} <= set(structure.columns)
    assert not any("位置 / 旋转" in item.value for item in at.caption)
    assert any(item.label == "来源与限制" for item in at.expander)
    assert any("结构 v2 坐标" in item.value for item in at.caption)
    assert not any(item.label == "照片局部配色观测" for item in at.expander)
    assert not any(item.label == "运行耗时与回退原因" for item in at.expander)
