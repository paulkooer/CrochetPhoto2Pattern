"""Cross-module counterexamples from the 2026-10-30 review."""
from copy import deepcopy
from pathlib import Path

import pytest
from PIL import Image
from streamlit.testing.v1 import AppTest

from app.cli import build_parser, main, run
from app.models.crochet_params import CrochetParamsGenerator, refresh_derived
from app.models.gauge import Gauge
from app.models.validator import validate_pattern
from app.schemas import ImageAnalysis, PatternResult
from app.ui.pattern_editor import edit_rounds, edit_structure_part
from app.ui.result_logic import (
    import_backup,
    rebuild_params,
    regenerate_with_gauge,
    regenerate_with_structure,
)
from app.utils import history
from app.utils.exporters import export_markdown

APP = str(Path(__file__).resolve().parents[1] / "app" / "main.py")


def manual(*args):
    result = run(build_parser().parse_args(list(args)))
    result["result_id"] = "audit-manual"
    return result


def colored_head():
    result = manual("--parts", "头部")
    result["params"] = CrochetParamsGenerator.generate_params(
        ImageAnalysis(**result["analysis"]),
        result["structure"],
        color_bands=[{"start": 0, "end": 0.15, "color": "白色"},
                     {"start": 0.15, "end": 1, "color": "黑色"}],
    )
    return result


@pytest.mark.parametrize("mode", ["insert", "remove", "middle"])
def test_color_edits_refresh_neighbors_summary_export_and_restore(mode):
    result = colored_head()
    rounds = deepcopy(result["params"]["parts"][0]["rounds"])
    boundary = next(i for i, r in enumerate(rounds) if "换线：" in (r.get("notes") or ""))
    index = boundary if mode in {"remove", "insert"} else boundary + 2
    rounds[index]["color"] = rounds[index - 1]["color"] if mode == "remove" else "红色"
    rounds[index]["notes"] += "；用户备注：保留记号扣"
    edited = edit_rounds(result, 0, rounds)
    restored = import_backup(PatternResult.from_result(edited).to_backup(), "restored")
    assert result["params"]["parts"][0]["rounds"] != rounds
    for candidate in (edited, restored):
        part = candidate["params"]["parts"][0]
        for i, rd in enumerate(part["rounds"]):
            expected = i > 0 and rd["color"] != part["rounds"][i - 1]["color"]
            assert ("换线：" in (rd.get("notes") or "")) == expected
            if expected:
                assert f"换线：{rd['color']}（" in rd["notes"]
        assert "用户备注：保留记号扣" in part["rounds"][index]["notes"]
        if mode != "remove":
            assert f"R{index + 1} 红色" in part["notes"]
            assert "换线：红色" in export_markdown(candidate["params"], candidate["analysis"])
        assert validate_pattern(candidate["params"])["ok"]


@pytest.mark.parametrize("ruffle", [False, True])
def test_skirt_assembly_uses_waist_including_legacy_restore_and_pdf(ruffle, monkeypatch):
    result = manual("--parts", "头部,身体,裙子", *(["--ruffle"] if ruffle else []))
    skirt = next(p for p in result["params"]["parts"] if p["name"] == "裙子")
    waist = skirt["rounds"][0]["stitches"]
    assert waist == 36
    assert skirt["rounds"][-1]["stitches"] == (96 if ruffle else 48)
    assert waist != skirt["rounds"][-1]["stitches"]
    # Legacy backups have no explicit opening reference and can contain stale prose.
    backup = PatternResult.from_result(result).to_backup()
    for p in backup["params"]["parts"]:
        p.pop("opening_row", None)
    restored = import_backup(backup, "old-skirt")
    for candidate in (result, restored):
        assert f"裙筒腰部（{waist} 针开口）" in candidate["params"]["assembly_instructions"]
        assert f"裙筒腰部（{waist} 针开口）" in export_markdown(candidate["params"])
    pytest.importorskip("reportlab")
    from reportlab import platypus

    from app.utils import pdf_export
    original = platypus.Paragraph
    paragraphs = []

    def capture(text, *args, **kwargs):
        paragraphs.append(text)
        return original(text, *args, **kwargs)

    monkeypatch.setattr(platypus, "Paragraph", capture)
    assert pdf_export.export_pdf(restored["params"]).startswith(b"%PDF-")
    assert any(f"裙筒腰部（{waist} 针开口）" in text for text in paragraphs)


@pytest.mark.parametrize("profile", [None, [1.0] * 20])
@pytest.mark.parametrize("diameter", [6, 12])
def test_body_bands_cover_wall_height_independently_of_base(profile, diameter):
    result = manual("--parts", "身体")
    structure = deepcopy(result["structure"])
    # The cylinder adds two axial taper rows to the straight-wall target.
    structure["parts"][0].update(height_cm=9 if profile is None else 10, diameter_cm=diameter)
    params = CrochetParamsGenerator.generate_params(
        ImageAnalysis(**result["analysis"]), structure,
        gauge=Gauge(16, 20), body_profile=profile,
        spans={"身体": (0, 1)},
        color_bands=[{"start": 0, "end": 0.5, "color": "白色"},
                     {"start": 0.5, "end": 1, "color": "黑色"}],
    )
    body = params["parts"][0]
    # Reference expectation uses the declared 10 cm wall and 2 rows/cm.
    wall = body["rounds"][-20:]
    base = body["rounds"][:-20]
    assert len(base) > 0
    assert [r["color"] for r in wall] == ["黑色"] * 10 + ["白色"] * 10
    assert all(r["color"] == "黑色" for r in base)
    assert body["height_cm"] == 10


def test_photo_and_batch_cli_honor_explicit_parts(tmp_path):
    image = tmp_path / "input.png"
    Image.new("RGB", (32, 64), "white").save(image)
    result = run(build_parser().parse_args(["--image", str(image), "--parts", "头部,身体"]))
    assert [p["name"] for p in result["params"]["parts"]] == ["头部", "身体"]
    assert result["analysis"]["parts"] == ["头部", "身体"]
    out = tmp_path / "out"
    assert main(["--batch-dir", str(tmp_path), "--out-dir", str(out),
                 "--parts", "头部,身体", "--quiet"]) == 0
    import json
    batch = json.loads((out / "input.json").read_text())
    assert [p["name"] for p in batch["params"]["parts"]] == ["头部", "身体"]


def test_onepiece_preserves_head_measurement_for_materials_and_backup():
    separate = manual("--head", "15", "--height", "30")
    merged = manual("--head", "15", "--height", "30", "--one-piece")
    restored = import_backup(PatternResult.from_result(merged).to_backup(), "onepiece-restored")

    def eyes(result):
        return next(m for m in result["params"]["materials"] if m["item"] == "安全眼")

    assert "14mm" in eyes(separate)["quantity"]
    head = next(p for p in separate["params"]["parts"] if p["name"] == "头部")
    assert head["diameter_cm"] == 15
    assert merged["params"]["parts"][0]["head_diameter_cm"] == 15
    assert restored["params"]["parts"][0]["head_diameter_cm"] == 15
    assert eyes(merged) == eyes(separate) == eyes(restored)


def test_legacy_color_notes_are_migrated_and_numeric_edits_still_refresh():
    result = colored_head()
    part = result["params"]["parts"][0]
    part.pop("auto_color_summary", None)
    for rd in part["rounds"]:
        rd.pop("auto_color_note", None)
    boundary = next(i for i, r in enumerate(part["rounds"]) if "换线：" in (r.get("notes") or ""))
    part["rounds"][boundary]["color"] = "红色"
    restored = import_backup(PatternResult.from_result(result).to_backup(), "legacy-colors")
    assert "换线：红色（" in restored["params"]["parts"][0]["rounds"][boundary]["notes"]
    assert f"R{boundary + 1} 红色" in restored["params"]["parts"][0]["notes"]
    rounds = deepcopy(restored["params"]["parts"][0]["rounds"])
    rounds[0]["stitches"] = 12
    rounds[0]["color"] = "红色"
    rounds[1]["increase"] = 0
    edited = edit_rounds(restored, 0, rounds)
    assert "12" in edited["params"]["parts"][0]["rounds"][0]["notes"]
    assert validate_pattern(edited["params"])["ok"]


def test_partial_color_edits_preserve_inherited_yarns_across_refreshes():
    result = manual("--parts", "头部")
    rounds = deepcopy(result["params"]["parts"][0]["rounds"])
    for rd in rounds[:len(rounds) * 3 // 4]:
        rd["color"] = "红色"
    original_yarn = result["params"]["parts"][0]["color"]
    edited = edit_rounds(result, 0, rounds)
    assert edited["params"]["parts"][0]["rounds"][-1]["color"] == original_yarn
    snapshot = deepcopy(edited)
    refresh_derived(edited["params"])
    assert edited == snapshot


def test_position_only_changes_preserve_manual_rounds():
    result = manual()
    arm_index = next(i for i, p in enumerate(result["params"]["parts"]) if p["name"] == "手臂")
    original_rounds = deepcopy(result["params"]["parts"][arm_index]["rounds"])
    assert len(original_rounds) == 8
    # Advanced JSON editing can add rows; preserve the audit's exact 9-row case.
    params = deepcopy(result["params"])
    arm = params["parts"][arm_index]
    arm["rounds"].append({"row": 9, "stitches": arm["rounds"][-1]["stitches"],
                          "notes": "6X；用户手改针法备注"})
    result["params"] = rebuild_params(params)
    manual_rounds = deepcopy(result["params"]["parts"][arm_index]["rounds"])
    structure = deepcopy(result["structure"])
    head = next(p for p in structure["parts"] if p["name"] == "头部")
    head["instances"][0]["position"]["x"] += 0.1
    updated = regenerate_with_structure(result, structure)
    assert updated["params"] == result["params"]
    head_index = next(i for i, p in enumerate(result["structure"]["parts"]) if p["name"] == "头部")
    edited = edit_structure_part(result, head_index, count=1, dimensions={},
                                 position=head["instances"][0]["position"])
    assert edited["params"] == result["params"]
    assert result["structure"] != edited["structure"]
    assert edited["params"]["parts"][arm_index]["rounds"] == manual_rounds
    assert len(edited["params"]["parts"][arm_index]["rounds"]) == 9

    # Physical edits must still recalculate instead of taking the layout shortcut.
    dimensioned = edit_structure_part(result, head_index, count=1, dimensions={"diameter_cm": 12})
    assert dimensioned["params"]["parts"][head_index]["diameter_cm"] == 12
    assert dimensioned["params"] != result["params"]
    regauged = regenerate_with_gauge(result, 18, 24)
    assert regauged["params"]["gauge"] == {"stitches_per_10cm": 18, "rows_per_10cm": 24}
    assert regauged["params"]["parts"][arm_index]["rounds"] != manual_rounds
    assert validate_pattern(dimensioned["params"])["ok"]
    assert validate_pattern(regauged["params"])["ok"]


def test_manual_save_history_reload_keeps_both_tabs_independent(tmp_path, monkeypatch):
    monkeypatch.setenv("CROCHET_HISTORY_DB", str(tmp_path / "history.sqlite"))
    at = AppTest.from_file(APP, default_timeout=60).run()
    at.button(key="btn_manual").click().run()
    assert not at.exception
    manual_result = at.session_state["manual_result"]
    rid = manual_result["result_id"]
    at.button(key=f"hist_save_{rid}").click().run()
    assert at.session_state["manual_result"]["history_id"] == rid
    at.run()
    at.button(key=f"hist_load_{rid}").click().run()
    assert not at.exception
    loaded = at.session_state["result"]
    assert loaded["result_id"] != rid
    assert loaded["history_id"] == rid
    assert {"result_id", "history_id"}.isdisjoint(PatternResult.from_result(loaded).to_backup())
    assert at.session_state["manual_result"] == manual_result
    loaded_id = loaded["result_id"]
    at.text_area(key=f"project_notes_{rid}").input("手动页备注").run()
    at.text_area(key=f"project_notes_{loaded_id}").input("历史载入页备注").run()
    at.button(key=f"all_{loaded_id}_头部").click().run()
    assert not at.exception
    assert not any(c.value for c in at.checkbox if c.key.startswith(f"chk_{rid}_"))
    # An applied edit gets another display ID and retains the persistent record ID.
    next(b for b in at.button if b.label == "更新材料估算"
         and loaded_id in b.key).click().run()
    assert not at.exception
    edited_id = at.session_state["result"]["result_id"]
    assert edited_id != loaded_id
    assert at.session_state["result"]["history_id"] == rid
    assert at.text_area(key=f"project_notes_{rid}").value == "手动页备注"
    assert at.text_area(key=f"project_notes_{edited_id}").value == "历史载入页备注"
    at.button(key=f"clear_{edited_id}_头部").click().run()
    assert not at.exception
    assert at.text_area(key=f"project_notes_{rid}").value == "手动页备注"
    at.button(key=f"hist_save_{edited_id}").click().run()
    assert not at.exception
    assert len(history.list_results()) == 1
    # Repeated opening must also leave the manual tab's widgets intact.
    at.button(key=f"hist_load_{rid}").click().run()
    assert not at.exception
    assert at.session_state["result"]["result_id"] not in {rid, loaded_id, edited_id}
    assert at.text_area(key=f"project_notes_{rid}").value == "手动页备注"


@pytest.mark.parametrize("title", [None, "[自定义](https://example.invalid) ![x](https://example.invalid/x)"])
def test_sidebar_escapes_history_title_and_summary(tmp_path, monkeypatch, title):
    monkeypatch.setenv("CROCHET_HISTORY_DB", str(tmp_path / "history.sqlite"))
    result = manual()
    result["analysis"]["body_type"] = "![摘要](https://example.invalid/a)"
    history.save_result(result, title=title)
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert not at.exception
    caption = next(c.value for c in at.caption if "example.invalid" in c.value)
    assert "\\[" in caption
    assert "[摘要](" not in caption and "[自定义](" not in caption and "[x](" not in caption
