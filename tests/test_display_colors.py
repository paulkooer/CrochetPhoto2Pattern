"""显示色与图解颜色共用一个解析器。

自定义名称可以带一个屏幕 hex。这个 hex 不是品牌色号。没有显示色时，
3D 用中性灰，不退回部件原来的毛线色。Parade 仍然拒绝无法表达的自定义名。
"""
from __future__ import annotations

from copy import deepcopy

import pytest
from streamlit.testing.v1 import AppTest

from app import theme
from app.models.colors import (
    PLACEHOLDER_DISPLAY_HEX,
    UNRESOLVED_DISPLAY_HEX,
    ColorPresentation,
    display_color_issues,
    normalize_hex_color,
    present_color,
    resolve_display_color,
    screen_swatch_suffix,
)
from app.models.materials import yarn_requirements
from app.models.ring_chart import render_ring_svg, render_symbol_strip
from app.models.validator import validate_pattern
from app.schemas import PatternResult
from app.services.color_selection import MODE_UNIFORM, apply_color_change, color_change_preview
from app.services.progress_state import color_only_change
from app.services.result_logic import import_backup
from app.ui.color_editor import _note_swatch
from app.ui.preview3d import build_payload
from app.ui.result_analysis import _yarn_chip_html
from app.ui.result_structure import _unresolved_copy_colors, structure_table_rows
from app.utils.exporters import export_markdown
from app.utils.parade_export import export_parade_report, lint_parade_dsl
from app.utils.project import project_backup, read_project_state
from tests.test_app_smoke import _mock_result

_NAME = "外婆家的藏青"
_HEX = "#26374a"
_SWATCH_UI = """
import streamlit as st
from app.ui.color_editor import render_color_editor
from app.ui.edit_history import render_history
render_color_editor(st.session_state.result, "result")
render_history("result", st.session_state.result)
"""
_STRUCTURE_UI = """
import streamlit as st
from app.ui.result_structure import render_structure
render_structure(st.session_state.result)
"""


def _arms(colors, ids, *, part_color="黄色", displays=None):
    params = {"parts": [{
        "name": "手臂", "color": part_color,
        "instance_colors": colors, "instance_color_ids": ids,
        "rounds": [{"row": 1, "stitches": 6, "color": part_color or "黄色"}],
    }]}
    if displays is not None:
        params["display_colors"] = displays
    return build_payload({
        "analysis": {"height_cm": 18},
        "structure": {"schema_version": "2.0", "parts": [{
            "name": "手臂", "shape": "sphere", "diameter_cm": 4,
            "instances": [
                {"instance_id": "arm-r", "position": {"x": 1, "y": 0.4, "z": 0},
                 "rotation_deg": {}},
                {"instance_id": "arm-l", "position": {"x": -1, "y": 0.4, "z": 0},
                 "rotation_deg": {}},
            ],
        }]},
        "params": params,
    })


def _parade_part(color: str, *, origin: str | None = "manual", displays=None):
    params = {"parts": [{
        "name": "色块", "magic_ring": True, "quantity": 1, "color": color,
        "rounds": [
            {"row": 1, "stitches": 6, "color": color},
            {"row": 2, "stitches": 12, "increase": 6, "color": color},
        ],
    }]}
    if origin is not None:
        params["parts"][0]["color_origin"] = origin
    if displays is not None:
        params["display_colors"] = displays
    return {"params": params}


def test_hex_literals_normalize_before_names():
    assert normalize_hex_color("  #36C ") == "#3366cc"
    assert normalize_hex_color("#AABBCC") == "#aabbcc"
    assert normalize_hex_color("蓝色") is None
    assert normalize_hex_color("#12345") is None
    assert resolve_display_color("#36C") == "#3366cc"
    assert resolve_display_color("蓝色") == "#0078d7"
    assert resolve_display_color("黄色") == "#ffff00"
    assert resolve_display_color("skin") == PLACEHOLDER_DISPLAY_HEX["skin"]
    assert resolve_display_color("body") == PLACEHOLDER_DISPLAY_HEX["body"]
    assert resolve_display_color("skin", placeholders=False) is None
    assert resolve_display_color("body", placeholders=False) is None
    assert resolve_display_color("外婆家的藏青", {"外婆家的藏青": "#26374A"}) == "#26374a"
    # 色表名优先于同名显示色登记。
    assert resolve_display_color("蓝色", {"蓝色": "#112233"}) == "#0078d7"
    assert resolve_display_color("没有这个颜色", {"别的": "#112233"}) is None
    assert resolve_display_color("   ") is None
    assert resolve_display_color(None) is None


def test_suffix_is_only_for_custom_names():
    mapped = {"外婆家的藏青": "#26374a"}
    assert screen_swatch_suffix("蓝色", mapped) == ""
    assert screen_swatch_suffix("skin", mapped) == ""
    assert screen_swatch_suffix("#336699", mapped) == ""
    assert screen_swatch_suffix("外婆家的藏青", mapped) == (
        "（显示色 #26374a，屏幕示意，不是品牌色号）")
    assert screen_swatch_suffix("外婆家的藏青", None) == "（无显示色）"


def test_display_color_issues_reject_bad_maps_and_accept_absence():
    assert display_color_issues(None) == []
    assert display_color_issues({"外婆家的藏青": "#26374A"}) == []
    assert any("对象" in issue for issue in display_color_issues(["#112233"]))
    assert any("64" in issue for issue in display_color_issues(
        {f"色{index}": "#112233" for index in range(65)}))
    assert any("蓝色" in issue for issue in display_color_issues({"蓝色": "#112233"}))
    assert any("skin" in issue for issue in display_color_issues({"skin": "#112233"}))
    assert any("#112233" in issue for issue in display_color_issues({"#112233": "#aabbcc"}))
    assert any("显示色必须是" in issue for issue in display_color_issues({"藏青": "navy"}))
    assert any("颜色名无效" in issue for issue in display_color_issues({" 藏青": "#112233"}))
    assert any("颜色名无效" in issue for issue in display_color_issues({"藏\n青": "#112233"}))
    assert any("颜色名无效" in issue for issue in display_color_issues({"藏#青": "#112233"}))
    assert any("颜色名无效" in issue for issue in display_color_issues({"藏" * 41: "#112233"}))

    params = deepcopy(_mock_result("display-validate")["params"])
    params["display_colors"] = {"藏青": "navy"}
    report = validate_pattern(params)
    assert report["ok"] is False
    assert any("藏青" in issue for issue in report["issues"])


def test_apply_records_one_swatch_and_does_not_require_one():
    result = _mock_result("display-apply")
    updated = apply_color_change(
        result, part_name="身体", color="外婆家的藏青", mode=MODE_UNIFORM,
        display_colors={"外婆家的藏青": "#26374A", "蓝色": "#000000", "多余": "#112233"})
    assert updated["params"]["display_colors"] == {"外婆家的藏青": "#26374a"}
    assert "display_colors" not in result["params"]
    assert updated["params"]["parts"] != result["params"]["parts"]

    plain = apply_color_change(result, part_name="身体", color="自定义测试色", mode=MODE_UNIFORM)
    assert "display_colors" not in plain["params"]

    yarn = apply_color_change(
        result, part_name="身体", color="蓝色", mode=MODE_UNIFORM,
        display_colors={"蓝色": "#112233"})
    assert "display_colors" not in yarn["params"]

    changed = apply_color_change(
        updated, part_name="身体", color="外婆家的藏青", mode=MODE_UNIFORM,
        display_colors={"外婆家的藏青": "#112233"})
    assert changed["params"]["display_colors"]["外婆家的藏青"] == "#112233"

    with pytest.raises(ValueError, match="显示色必须是"):
        apply_color_change(
            result, part_name="身体", color="外婆家的藏青", mode=MODE_UNIFORM,
            display_colors={"外婆家的藏青": "navy"})


def test_one_custom_name_cannot_carry_two_swatches_in_one_edit():
    swatches: dict[str, str] = {}
    assert _note_swatch(swatches, "外婆家的藏青", "#26374a")
    assert not _note_swatch(swatches, "外婆家的藏青", "#112233")
    assert _note_swatch(swatches, "蓝色", None)
    assert swatches == {"外婆家的藏青": "#26374a"}


def test_preview_uses_the_swatch_and_never_the_old_part_colour():
    mapped = _arms(
        ["外婆家的藏青", "#36c"], ["arm-r", "arm-l"],
        displays={"外婆家的藏青": "#26374A"})
    arms = mapped["items"][0]
    by_x = {round(inst["p"][0]): inst["color"] for inst in arms["instances"]}
    assert by_x[18] == "#26374a"
    assert by_x[-18] == "#3366cc"
    assert arms["color"] == "#ffff00"

    unknown = _arms(["不是色表里的名字"], ["arm-r"])
    assert unknown["items"][0]["instances"][0]["color"] == UNRESOLVED_DISPLAY_HEX
    assert unknown["items"][0]["instances"][0]["color"] != "#ffff00"

    part = _arms(None, None, part_color="外婆家的藏青")
    assert part["items"][0]["color"] == UNRESOLVED_DISPLAY_HEX
    assert part["items"][0]["color"] != "#c9a68a"

    missing = _arms(None, None, part_color="")
    assert missing["items"][0]["color"] == "#c9a68a"


def test_parade_emits_a_screen_swatch_and_still_refuses_an_unmapped_name():
    mapped = export_parade_report(_parade_part(
        "外婆家的藏青", displays={"外婆家的藏青": "#26374A"}))
    assert mapped.complete
    assert ("# display swatch for 外婆家的藏青 — screen colour only, "
            "not a yarn brand code") in mapped.text
    assert "COLOR: #26374a" in mapped.text
    assert lint_parade_dsl(mapped.text) == []

    with pytest.raises(ValueError, match="外婆家的藏青.*已跳过"):
        export_parade_report(_parade_part("外婆家的藏青"))

    mixed = _parade_part("黄色")
    other = _parade_part("外婆家的藏青")["params"]["parts"][0]
    other["name"] = "另一块"
    mixed["params"]["parts"].append(other)
    refused = export_parade_report(mixed)
    assert not refused.complete
    assert any("外婆家的藏青" in failure and "已跳过" in failure for failure in refused.failures)
    assert "COLOR: #ffff00" in refused.text
    assert "#26374a" not in refused.text

    placeholder = export_parade_report(_parade_part("skin", origin=None))
    assert "COLOR:" not in placeholder.text


def test_parade_swatch_comment_names_the_colour_that_was_exported():
    """首圈颜色和部件基础色不同时，免责声明必须跟着实际写出的 COLOR。"""
    report = export_parade_report({"params": {
        "parts": [{
            "name": "色块", "magic_ring": True, "quantity": 1,
            "color": "黄色", "color_origin": "manual",
            "rounds": [
                {"row": 1, "stitches": 6, "color": "外婆家的藏青"},
                {"row": 2, "stitches": 12, "increase": 6, "color": "外婆家的藏青"},
            ],
        }],
        "display_colors": {"外婆家的藏青": "#26374a"},
    }})
    note = ("# display swatch for 外婆家的藏青 — screen colour only, "
            "not a yarn brand code")
    assert note in report.text
    assert report.text.index(note) < report.text.index("COLOR: #26374a")
    assert "COLOR: #ffff00" not in report.text

    inverse = export_parade_report({"params": {
        "parts": [{
            "name": "色块", "magic_ring": True, "quantity": 1,
            "color": "外婆家的藏青", "color_origin": "manual",
            "rounds": [
                {"row": 1, "stitches": 6, "color": "黄色"},
                {"row": 2, "stitches": 12, "increase": 6, "color": "外婆家的藏青"},
            ],
        }],
        "display_colors": {"外婆家的藏青": "#26374a"},
    }})
    opening = inverse.text.index("COLOR: #ffff00")
    assert note not in inverse.text[:opening]
    assert inverse.text.index(note) < inverse.text.index("COLOR: #26374a")


def test_ring_and_symbol_use_the_map_or_the_theme_fallback():
    part = {"name": "头部", "rounds": [
        {"row": 1, "stitches": 6, "color": "外婆家的藏青"},
        {"row": 2, "stitches": 12, "increase": 6, "color": "没有这个颜色"},
    ]}
    displays = {"外婆家的藏青": "#26374a"}
    ring = render_ring_svg(part, displays=displays)
    assert "#26374a" in ring
    assert theme.GRID in ring
    strip = render_symbol_strip(part, displays=displays)
    assert "#26374a" in strip
    assert theme.INK in strip


def test_markdown_adds_the_swatch_note_only_for_custom_names():
    result = _mock_result("display-md")
    updated = apply_color_change(
        result, part_name="身体", color="外婆家的藏青", mode=MODE_UNIFORM,
        display_colors={"外婆家的藏青": "#26374a"})
    markdown = export_markdown(updated["params"], result=updated)
    assert "外婆家的藏青（显示色 #26374a，屏幕示意，不是品牌色号）" in markdown
    assert "蓝色（显示色" not in markdown

    bare = apply_color_change(result, part_name="身体", color="外婆家的藏青", mode=MODE_UNIFORM)
    bare_md = export_markdown(bare["params"], result=bare)
    assert "外婆家的藏青（无显示色）" in bare_md


def test_structure_table_keeps_the_original_colour_beside_the_current_one():
    rows = structure_table_rows({
        "structure": {"parts": [
            {"name": "身体", "part_id": "body", "color": "主体色", "shape": "cylinder",
             "count": 1, "instances": []},
            {"name": "尾巴", "part_id": "tail", "color": "黄色", "shape": "cylinder",
             "count": 1, "instances": []},
        ]},
        "params": {"parts": [{"name": "身体", "color": "外婆家的藏青"}],
                   "display_colors": {"外婆家的藏青": "#26374a"}},
    })
    body, tail = rows
    assert body["当前基础色"] == "外婆家的藏青（显示色 #26374a，屏幕示意，不是品牌色号）"
    assert body["原始结构色"] == "主体色"
    assert tail["当前基础色"] == "—"
    assert tail["原始结构色"] == "黄色"

    missing = _unresolved_copy_colors({
        "params": {"parts": [{
            "color": "skin",
            "instance_colors": ["蓝色", "外婆家的藏青", "另一支线"],
        }], "display_colors": {"外婆家的藏青": "#26374a"}},
    })
    assert missing == ["另一支线"]


def test_display_map_alone_is_a_colour_change_and_a_copy_is_not():
    result = _mock_result("display-progress")
    assert not color_only_change(result, deepcopy(result))
    mapped = deepcopy(result)
    mapped["params"]["display_colors"] = {"外婆家的藏青": "#26374a"}
    assert color_only_change(result, mapped)
    empty = deepcopy(result)
    empty["params"]["display_colors"] = {}
    assert not color_only_change(result, empty)
    blank = deepcopy(result)
    blank["params"]["display_colors"] = "不是对象"
    assert not color_only_change(result, blank)


def test_materials_chip_uses_a_mapped_custom_name_and_not_a_placeholder():
    chip = _yarn_chip_html("外婆家的藏青", {"外婆家的藏青": "#26374a"})
    assert "background:#26374a" in chip
    assert "yarn-chip--unknown" not in chip
    assert "外婆家的藏青" in chip
    assert "yarn-chip--unknown" in _yarn_chip_html("skin")
    assert "yarn-chip--unknown" in _yarn_chip_html("没有这个颜色", {"别的": "#112233"})


def _part_named(result, name):
    return next(part for part in result["params"]["parts"] if part["name"] == name)


def _preview_item(result, name):
    payload = build_payload(result)
    assert payload is not None
    return next(item for item in payload["items"] if item["name"] == name)


def _pdf_view(result, monkeypatch):
    pytest.importorskip("reportlab")
    import reportlab.lib.colors as rl_colors
    import reportlab.platypus as platypus

    from app.utils.pdf_export import export_pdf

    texts: list[str] = []
    chips: list[str] = []
    paragraph = platypus.Paragraph
    hex_color = rl_colors.HexColor

    def capture_text(text, *args, **kwargs):
        texts.append(text)
        return paragraph(text, *args, **kwargs)

    def capture_hex(value, *args, **kwargs):
        chips.append(str(value).lower())
        return hex_color(value, *args, **kwargs)

    monkeypatch.setattr(platypus, "Paragraph", capture_text)
    monkeypatch.setattr(rl_colors, "HexColor", capture_hex)
    assert export_pdf(result["params"], result=result).startswith(b"%PDF-")
    return texts, chips


def test_present_color_separates_screen_colour_from_export_identity():
    blank = ColorPresentation(None, None, False, False, False)
    assert present_color(None) == blank
    assert present_color("   ") == blank
    assert present_color(12) == blank

    yarn = present_color("黄色")
    assert yarn.display_hex == yarn.export_hex == "#ffff00"
    assert yarn.is_exportable and not yarn.is_custom and not yarn.is_placeholder

    literal = present_color("#aBc")
    assert literal.display_hex == literal.export_hex == "#aabbcc"
    assert literal.is_exportable and not literal.is_custom

    skin = present_color("skin")
    assert skin.display_hex == PLACEHOLDER_DISPLAY_HEX["skin"]
    assert skin.export_hex is None and skin.is_placeholder
    assert not skin.is_exportable and not skin.is_custom
    body = present_color("body")
    assert body.display_hex == PLACEHOLDER_DISPLAY_HEX["body"]
    assert body.export_hex is None and body.is_placeholder and not body.is_exportable

    mapped = present_color(_NAME, {_NAME: "#26374A"})
    assert mapped.display_hex == mapped.export_hex == _HEX
    assert mapped.is_custom and mapped.is_exportable and not mapped.is_placeholder

    bare = present_color(_NAME, {"别的": "#112233"})
    assert bare.display_hex is None and bare.export_hex is None
    assert bare.is_custom and not bare.is_exportable and not bare.is_placeholder

    assert resolve_display_color("skin") == skin.display_hex
    assert resolve_display_color("skin", placeholders=False) == skin.export_hex
    assert resolve_display_color(_NAME, {_NAME: "#26374A"}) == mapped.display_hex
    assert resolve_display_color(_NAME, {_NAME: "#26374A"}, placeholders=False) == mapped.export_hex
    assert resolve_display_color(_NAME) is None


def test_custom_name_with_hex_matches_in_3d_ring_and_pdf(monkeypatch):
    updated = apply_color_change(
        _mock_result("accept-hex"), part_name="身体", color=_NAME, mode=MODE_UNIFORM,
        display_colors={_NAME: "#26374A"})
    displays = updated["params"]["display_colors"]
    assert present_color(_NAME, displays).display_hex == _HEX
    assert _preview_item(updated, "身体")["color"] == _HEX
    ring = render_ring_svg(_part_named(updated, "身体"), displays=displays)
    assert _HEX in ring
    assert theme.GRID not in ring
    texts, chips = _pdf_view(updated, monkeypatch)
    note = f"{_NAME}（显示色 {_HEX}，屏幕示意，不是品牌色号）"
    assert any(note in text for text in texts)
    assert _HEX in chips


def test_custom_name_without_hex_is_gray_and_says_so(monkeypatch):
    original = _mock_result("accept-gray")
    old_hex = resolve_display_color(_part_named(original, "身体").get("color"))
    updated = apply_color_change(original, part_name="身体", color=_NAME, mode=MODE_UNIFORM)
    assert "display_colors" not in updated["params"]
    assert _preview_item(updated, "身体")["color"] == UNRESOLVED_DISPLAY_HEX
    assert _preview_item(updated, "身体")["color"] != old_hex
    ring = render_ring_svg(_part_named(updated, "身体"))
    assert theme.GRID in ring
    assert UNRESOLVED_DISPLAY_HEX not in ring
    if old_hex is not None:
        assert old_hex not in ring
    texts, chips = _pdf_view(updated, monkeypatch)
    assert any(f"{_NAME}（无显示色）" in text for text in texts)
    assert UNRESOLVED_DISPLAY_HEX in chips

    at = AppTest.from_string(_STRUCTURE_UI, default_timeout=30)
    at.session_state["result"] = updated
    at.run()
    assert not at.exception
    assert any("这些颜色没有显示色，3D 使用中性灰" in caption.value and _NAME in caption.value
               for caption in at.caption)


def test_parade_refuses_an_unsupported_custom_colour_instead_of_claiming_success():
    with pytest.raises(ValueError, match="未能导出") as raised:
        export_parade_report(_parade_part(_NAME))
    assert "已跳过" in str(raised.value)
    assert "COLOR:" not in str(raised.value)

    mixed = _parade_part("黄色")
    other = _parade_part(_NAME)["params"]["parts"][0]
    other["name"] = "另一块"
    mixed["params"]["parts"].append(other)
    refused = export_parade_report(mixed)
    assert refused.complete is False
    assert any(_NAME in failure and "已跳过" in failure for failure in refused.failures)
    assert "COLOR: #ffff00" in refused.text
    assert _HEX not in refused.text
    assert f"COLOR: {PLACEHOLDER_DISPLAY_HEX['skin']}" not in refused.text


def test_placeholder_colours_stay_unselected_and_emit_no_yarn_directive(monkeypatch):
    result = _mock_result("accept-placeholder")
    assert _preview_item(result, "头部")["color"] == PLACEHOLDER_DISPLAY_HEX["skin"]
    body = next(part for part in result["params"]["parts"] if part.get("color") in ("skin", "body"))
    report = export_parade_report(_parade_part(body["color"], origin=None))
    assert "COLOR:" not in report.text
    assert PLACEHOLDER_DISPLAY_HEX["skin"] not in report.text
    assert PLACEHOLDER_DISPLAY_HEX["body"] not in report.text
    texts, _chips = _pdf_view(result, monkeypatch)
    assert "部件颜色：肤色（待选色）" in texts
    assert "部件颜色：主体色（待选色）" in texts
    rows = yarn_requirements(result["params"]["parts"])[0]
    colors = {row["color"] for row in rows}
    assert "肤色（待选色）" in colors
    assert "主体色（待选色）" in colors
    assert not any(str(row["color"]).startswith("#") or "#" in str(row["item"]) for row in rows)


def test_display_hex_does_not_change_material_totals():
    base = _mock_result("display-materials")
    bare = apply_color_change(base, part_name="身体", color=_NAME, mode=MODE_UNIFORM)
    navy = apply_color_change(
        base, part_name="身体", color=_NAME, mode=MODE_UNIFORM,
        display_colors={_NAME: "#26374A"})
    other = apply_color_change(
        base, part_name="身体", color=_NAME, mode=MODE_UNIFORM,
        display_colors={_NAME: "#112233"})
    assert yarn_requirements(bare["params"]["parts"]) == yarn_requirements(navy["params"]["parts"])
    assert yarn_requirements(navy["params"]["parts"]) == yarn_requirements(other["params"]["parts"])
    rows = yarn_requirements(navy["params"]["parts"])[0]
    assert any(row["color"] == _NAME for row in rows)
    assert all(not str(row["color"]).startswith("#") for row in rows)


def test_custom_name_and_hex_survive_backup_import_and_project_restore():
    updated = apply_color_change(
        _mock_result("display-backup"), part_name="身体", color=_NAME, mode=MODE_UNIFORM,
        display_colors={_NAME: "#26374A"})
    backup = PatternResult.from_result(updated).to_backup()
    assert backup["params"]["display_colors"] == {_NAME: _HEX}
    restored = import_backup(backup, "display-restored")
    assert restored["params"]["display_colors"] == {_NAME: _HEX}
    assert _part_named(restored, "身体")["color"] == _NAME

    project = project_backup(updated, {}, notes="显示色核对")
    reloaded = import_backup(project, "display-project")
    progress, notes = read_project_state(project, reloaded)
    assert progress == {}
    assert notes == "显示色核对"
    assert reloaded["params"]["display_colors"] == {_NAME: _HEX}
    assert _part_named(reloaded, "身体")["color"] == _NAME

    broken = deepcopy(backup)
    broken["params"]["display_colors"] = {"藏青": "navy"}
    with pytest.raises(ValueError, match="藏青"):
        import_backup(broken, "display-bad")


def test_colour_panel_keeps_the_display_hex_through_undo_and_redo():
    result = _mock_result("display-undo")
    rid = result["result_id"]
    index = next(i for i, part in enumerate(result["params"]["parts"]) if part["name"] == "头部")
    at = AppTest.from_string(_SWATCH_UI, default_timeout=60)
    at.session_state["result"] = result
    at.run()
    assert not at.exception
    at.selectbox(key=f"edit_{rid}_color_part").set_value(index).run()
    at.selectbox(key=f"edit_{rid}_color{index}_pick").select("自定义颜色名…").run()
    at.text_input(key=f"edit_{rid}_color{index}_custom").set_value(_NAME).run()
    at.color_picker(key=f"edit_{rid}_color{index}_swatch").set_value("#26374A").run()
    at.button(key=f"edit_{rid}_color{index}_preview").click().run()
    at.button(key=f"edit_{rid}_preview_apply").click().run()
    assert not at.exception
    applied = at.session_state["result"]
    assert applied["result_id"] != rid
    assert applied["params"]["display_colors"] == {_NAME: _HEX}
    assert _part_named(applied, "头部")["color"] == _NAME

    at.button(key=f"edit_{applied['result_id']}_undo").click().run()
    undone = at.session_state["result"]
    assert "display_colors" not in undone["params"]
    assert _part_named(undone, "头部")["color"] == _part_named(result, "头部")["color"]

    at.button(key=f"edit_{undone['result_id']}_redo").click().run()
    redone = at.session_state["result"]
    assert redone["params"]["display_colors"] == {_NAME: _HEX}
    assert _part_named(redone, "头部")["color"] == _NAME


def test_changing_a_custom_name_loads_its_own_swatch():
    result = _mock_result("switch-swatch")
    result["params"]["display_colors"] = {"共享蓝": "#123", "共享红": "#dd4433"}
    rid = result["result_id"]
    index = next(i for i, part in enumerate(result["params"]["parts"]) if part["name"] == "身体")
    prefix = f"edit_{rid}_color{index}"
    at = AppTest.from_string(_SWATCH_UI, default_timeout=30)
    at.session_state["result"] = result
    at.run()
    at.selectbox(key=f"edit_{rid}_color_part").set_value(index).run()
    at.selectbox(key=f"{prefix}_pick").select("自定义颜色名…").run()
    at.text_input(key=f"{prefix}_custom").set_value("共享蓝").run()
    assert at.color_picker(key=f"{prefix}_swatch").value == "#112233"

    at.text_input(key=f"{prefix}_custom").set_value("共享红").run()
    assert at.color_picker(key=f"{prefix}_swatch").value == "#dd4433"
    at.color_picker(key=f"{prefix}_swatch").set_value("#aabbcc").run()
    # Whitespace does not change the normalized name or discard an unsaved swatch.
    at.text_input(key=f"{prefix}_custom").set_value("共享红 ").run()
    assert at.color_picker(key=f"{prefix}_swatch").value == "#aabbcc"
    at.text_input(key=f"{prefix}_custom").set_value("全新颜色").run()
    assert at.color_picker(key=f"{prefix}_swatch").value == "#8d8a84"

    # A built-in name has a fixed swatch even if typed through the custom field.
    at.text_input(key=f"{prefix}_custom").set_value("蓝色").run()
    assert not at.color_picker
    assert any("内置色表" in caption.value for caption in at.caption)
    # Editing the name and clicking preview in one event must use the saved swatch too.
    at.text_input(key=f"{prefix}_custom").set_value("共享红")
    at.button(key=f"{prefix}_preview").click().run()
    pending = at.session_state["workspace_result"]["pending_preview"]
    assert _part_named(pending["candidate"], "身体")["color"] == "共享红"
    assert pending["candidate"]["params"]["display_colors"]["共享红"] == "#dd4433"
    assert pending["detail"]["display_changes"] == []
    assert not at.exception


def test_shared_display_swatch_change_is_previewed_and_applied_to_all_uses():
    result = apply_color_change(
        _mock_result("shared-swatch"), part_name="头部", color=_NAME, mode=MODE_UNIFORM,
        display_colors={_NAME: "#123"})
    result = apply_color_change(result, part_name="身体", color=_NAME, mode=MODE_UNIFORM)
    before = deepcopy(result)
    preview = color_change_preview(
        result, part_name="头部", color=_NAME, mode=MODE_UNIFORM,
        display_colors={_NAME: "#aabbcc"})
    assert preview["changed"]
    assert preview["affected"] == []
    assert preview["display_changes"] == [
        {"颜色": _NAME, "旧显示色": "#112233", "新显示色": "#aabbcc"}]
    assert result == before
    assert not color_change_preview(
        result, part_name="头部", color=_NAME, mode=MODE_UNIFORM,
        display_colors={_NAME: "#112233"})["display_changes"]

    rid = result["result_id"]
    at = AppTest.from_string(_SWATCH_UI, default_timeout=30)
    at.session_state["result"] = result
    at.run()
    at.color_picker(key=f"edit_{rid}_color0_swatch").set_value("#aabbcc").run()
    at.button(key=f"edit_{rid}_color0_preview").click().run()
    pending = at.session_state["workspace_result"]["pending_preview"]
    assert pending["detail"]["display_changes"] == preview["display_changes"]
    assert at.session_state["result"] == before
    assert any("同一名称在整张图解中共用" in caption.value for caption in at.caption)
    assert any("#112233" in str(table.value) and "#aabbcc" in str(table.value) for table in at.table)
    at.button(key=f"edit_{rid}_preview_apply").click().run()
    updated = at.session_state["result"]
    assert updated["params"]["display_colors"][_NAME] == "#aabbcc"
    assert _part_named(updated, "头部")["color"] == _NAME
    assert _part_named(updated, "身体")["color"] == _NAME
    assert not at.exception


def test_switching_copies_prefills_the_selected_copys_colour():
    result = apply_color_change(
        _mock_result("switch-copy"), part_name="手臂", color="红色", mode=MODE_UNIFORM,
        instance_index=0)
    result = apply_color_change(
        result, part_name="手臂", color="蓝色", mode=MODE_UNIFORM, instance_index=1)
    rid = result["result_id"]
    index = next(i for i, part in enumerate(result["params"]["parts"]) if part["name"] == "手臂")
    prefix = f"edit_{rid}_color{index}"
    at = AppTest.from_string(_SWATCH_UI, default_timeout=30)
    at.session_state["result"] = result
    at.run()
    at.selectbox(key=f"edit_{rid}_color_part").set_value(index).run()
    at.radio(key=f"{prefix}_scope").set_value("仅所选实体（整份统一换色）").run()
    assert at.selectbox(key=f"{prefix}_copy0_pick").value == "红色"
    at.selectbox(key=f"{prefix}_instance").set_value(1).run()
    assert at.selectbox(key=f"{prefix}_copy1_pick").value == "蓝色"
    at.selectbox(key=f"{prefix}_copy1_pick").select("黄色").run()
    at.button(key=f"{prefix}_preview").click().run()
    pending = at.session_state["workspace_result"]["pending_preview"]
    assert _part_named(pending["candidate"], "手臂")["instance_colors"] == ["红色", "黄色"]
    assert any("3D 预览按各份颜色示意" in warning.value for warning in at.warning)
    assert not any("3D 预览也只按部件主色" in warning.value for warning in at.warning)
    at.button(key=f"edit_{rid}_preview_apply").click().run()
    assert _part_named(at.session_state["result"], "手臂")["instance_colors"] == ["红色", "黄色"]
    assert not at.exception
