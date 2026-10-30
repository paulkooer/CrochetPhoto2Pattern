"""Independent-review boundary regressions against 8f48ba1."""
import hashlib
import json
from copy import deepcopy
from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from PIL import Image
from streamlit.testing.v1 import AppTest

from app.cli import main
from app.models.orchestrator import PipelineOrchestrator
from app.ui.result_logic import import_backup
from app.utils import history
from app.utils.backup import decode_backup_json
from app.utils.exporters import export_markdown
from app.utils.project import pattern_revision
from app.utils.trial_bundle import decode_trial_bundle, encode_trial_bundle, trial_gauge_candidate
from tests.test_app_smoke import _APP, _mock_result

LEGACY_ZIP = Path(__file__).parent / "fixtures/trial_4a19d70/measured.zip"
ZIP_SHA = "47395dd6ef7ed2b0194a3c647cb0b8c9e713da96cfa284771603c34a59babc9e"
SOURCE_SHA = "a287bc76903cee5447f86dbd1e468c6dd9efb93cdc63c9f50ad427b0b746cc39"


@pytest.mark.parametrize("batch", [False, True])
def test_cli_parts_are_explicit_without_claiming_full_review(tmp_path, batch):
    image = tmp_path / "input.png"
    Image.new("RGB", (32, 64), "white").save(image)
    output = tmp_path / "out"
    output.mkdir()
    args = (["--batch-dir", str(tmp_path), "--out-dir", str(output)] if batch
            else ["--image", str(image), "--out", str(output / "input.json")])
    assert main([*args, "--parts", "头部,身体", "--quiet"]) == 0
    result = json.loads((output / "input.json").read_text())
    assert result["analysis"]["parts"] == ["头部", "身体"]
    assert [p["name"] for p in result["params"]["parts"]] == ["头部", "身体"]
    meta = result["vision_meta"]
    assert not meta.get("reviewed_by_user")
    assert meta["parts_source"] == "cli_explicit"
    assert meta["requires_subject_review"] is True
    restored = import_backup(result, "cli-parts-only")
    at = AppTest.from_file(_APP, default_timeout=30)
    at.session_state["result"] = restored
    at.run()
    assert not at.exception
    assert not any("比例与部件已经过人工确认" in c.value for c in at.caption)
    markdown = export_markdown(restored["params"], restored["analysis"], result=restored)
    assert "CLI 显式选择" in markdown
    assert "尚未确认主体类型、头部与比例" in markdown
    assert "当前部件来自默认模板" not in markdown


def _legacy():
    data = LEGACY_ZIP.read_bytes()
    assert hashlib.sha256(data).hexdigest() == ZIP_SHA
    return decode_trial_bundle(data)


def test_complete_photo_ui_review_still_confirms_proportions_and_parts():
    draft = PipelineOrchestrator().prepare_photo(Image.new("RGB", (32, 64)))
    script = '''
import streamlit as st
from app.models.gauge import DEFAULT, DEFAULT_STYLE
from app.ui.photo_review import render_photo_review
result = render_photo_review(st.session_state.draft, "full", gauge=DEFAULT,
                             style=DEFAULT_STYLE, target_height=18)
if result is not None:
    st.session_state.generated = result
'''
    at = AppTest.from_string(script, default_timeout=30)
    at.session_state["draft"] = draft
    at.run()
    assert at.button(key="review_generate_full").disabled
    at.radio(key="review_subject_full").set_value("单个玩偶，所需部件可用下方列表表达").run()
    at.number_input(key="review_ratio_full").set_value(0.3)
    at.multiselect(key="review_parts_full").set_value(["头部", "身体"])
    at.button(key="review_generate_full").click().run()
    assert not at.exception and not at.error
    result = at.session_state["generated"]
    assert result["vision_meta"]["reviewed_by_user"] is True
    assert result["vision_meta"]["parts_source"] == "user_review"
    assert result["vision_meta"]["requires_subject_review"] is False
    assert result["analysis"]["head_diameter_cm"] / result["analysis"]["height_cm"] == pytest.approx(0.3)
    assert result["analysis"]["parts"] == ["头部", "身体"]
    shown = AppTest.from_file(_APP, default_timeout=30)
    shown.session_state["result"] = import_backup(result, "full-review")
    shown.run()
    assert not shown.exception
    assert any("比例与部件已经过人工确认" in c.value for c in shown.caption)


def test_true_legacy_trial_uses_normalized_session_revision_and_keeps_evidence():
    bundle = _legacy()
    source = bundle.source
    raw = decode_backup_json(source)
    assert "auto_color_note" not in raw["params"]["parts"][0]["rounds"][0]
    original = import_backup(raw, "legacy-session")
    assert bundle.source_revision == pattern_revision(original)
    candidate = trial_gauge_candidate(bundle, original)
    assert candidate["params"]["gauge"] == {"stitches_per_10cm": 18, "rows_per_10cm": 24}
    assert candidate["params"] != original["params"]
    assert bundle.source == source
    assert bundle.record.pattern.sha256 == hashlib.sha256(source).hexdigest() == SOURCE_SHA
    reloaded = decode_trial_bundle(encode_trial_bundle(bundle))
    assert reloaded.source == source
    assert reloaded.record == bundle.record
    assert reloaded.record.swatch.measured
    with ZipFile(BytesIO(encode_trial_bundle(reloaded))) as archive:
        assert archive.read("pattern.json") == source


@pytest.mark.parametrize("change", ["stitches", "round_order", "color", "quantity", "gauge",
                                    "round_notes", "part_notes", "opening"])
def test_normalized_trial_baseline_still_rejects_actual_pattern_changes(change):
    bundle = _legacy()
    original = import_backup(decode_backup_json(bundle.source), "legacy-session")
    updated = deepcopy(original)
    part = updated["params"]["parts"][0]
    if change == "stitches":
        part["rounds"][0]["stitches"] += 6
    elif change == "round_order":
        part["rounds"][0], part["rounds"][1] = part["rounds"][1], part["rounds"][0]
    elif change == "color":
        part["rounds"][0]["color"] = "红色"
    elif change == "quantity":
        part["quantity"] += 1
    elif change == "gauge":
        updated["params"]["gauge"]["rows_per_10cm"] += 1
    elif change == "round_notes":
        part["rounds"][0]["notes"] += "；本圈仅挑后半针"
    elif change == "part_notes":
        part["notes"] += "；先填充再继续"
    else:
        skirt = next(p for p in updated["params"]["parts"] if p["name"] == "裙子")
        skirt["opening_row"] = skirt["rounds"][1]["row"]
    with pytest.raises(ValueError, match="当前图解与试钩原图解不同"):
        trial_gauge_candidate(bundle, updated)
    assert bundle.source_revision == pattern_revision(original)


def test_legacy_trial_raw_sha_check_is_not_replaced_by_normalized_revision():
    with ZipFile(LEGACY_ZIP) as archive:
        source = archive.read("pattern.json")
        record = json.loads(archive.read("audit-4a19d70.trial.json"))
    record["pattern"]["sha256"] = "0" * 64
    output = BytesIO()
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("pattern.json", source)
        archive.writestr("audit-4a19d70.trial.json", json.dumps(record))
    with pytest.raises(ValueError, match="不匹配"):
        decode_trial_bundle(output.getvalue())


def test_full_app_opens_legacy_trial_and_enables_measured_gauge(monkeypatch):
    upload = BytesIO(LEGACY_ZIP.read_bytes())
    monkeypatch.setattr("app.ui.trial_editor.st.file_uploader",
                        lambda *a, **k: upload if k.get("key") == "trial_open_file" else None)
    at = AppTest.from_file(_APP, default_timeout=30).run()
    at.button(key="trial_open_apply").click().run()
    assert not at.exception
    assert not any("当前图解已与试钩原图解不同" in w.value for w in at.warning)
    assert not at.button(key="trial_gauge_preview_result").disabled
    original = deepcopy(at.session_state["result"])
    rid = original["result_id"]
    at.button(key="trial_gauge_preview_result").click().run()
    assert not at.exception and not at.error
    assert at.session_state["result"] == original
    pending = at.session_state[f"edit_{rid}_pending_preview"]
    assert pending["candidate"]["gauge"] == {"stitches_per_10cm": 18, "rows_per_10cm": 24}
    bundle = at.session_state["trial_workspace_result"]["bundle"]
    assert hashlib.sha256(bundle.source).hexdigest() == SOURCE_SHA


def _form_button(at, label, rid):
    return next(b for b in at.button if b.label == label and rid in b.key)


@pytest.mark.parametrize("path", ["undo", "preview"])
def test_first_history_save_binding_survives_older_content_snapshots(path, tmp_path, monkeypatch):
    monkeypatch.setenv("CROCHET_HISTORY_DB", str(tmp_path / "history.sqlite"))
    at = AppTest.from_file(_APP, default_timeout=30)
    at.session_state["result"] = _mock_result("other-photo")
    at.run()
    at.button(key="btn_manual").click().run()
    rid = at.session_state["manual_result"]["result_id"]
    at.checkbox(key=f"chk_{rid}_头部_0").check().run()
    at.checkbox(key="chk_other-photo_头部_0").check().run()
    at.text_area(key=f"project_notes_{rid}").input("手动页备注").run()
    at.text_area(key="project_notes_other-photo").input("照片页备注").run()
    if path == "undo":
        _form_button(at, "更新材料估算", rid).click().run()
        rid = at.session_state["manual_result"]["result_id"]
    else:
        at.slider(key=f"edit_{rid}_part0_i0_x").set_value(0.1)
        _form_button(at, "预览部件修改影响", rid).click().run()
        assert f"edit_{rid}_pending_preview" in at.session_state
    at.button(key=f"hist_save_{rid}").click().run()
    history_id = at.session_state["manual_result"]["history_id"]
    assert len(history.list_results()) == 1
    action = f"edit_{rid}_undo" if path == "undo" else f"edit_{rid}_preview_apply"
    at.button(key=action).click().run()
    assert not at.exception
    for direction in (None, "undo" if path == "preview" else "redo", "redo" if path == "preview" else "undo"):
        current = at.session_state["manual_result"]
        rid = current["result_id"]
        if direction:
            at.button(key=f"edit_{rid}_{direction}").click().run()
            current = at.session_state["manual_result"]
            rid = current["result_id"]
        assert not at.exception and not at.error
        assert current.get("history_id") == history_id
        assert at.checkbox(key=f"chk_{rid}_头部_0").value
        assert at.text_area(key=f"project_notes_{rid}").value == "手动页备注"
        assert at.checkbox(key="chk_other-photo_头部_0").value
        assert at.text_area(key="project_notes_other-photo").value == "照片页备注"
        at.button(key=f"hist_save_{rid}").click().run()
        assert not at.exception
        assert [item["rid"] for item in history.list_results()] == [history_id]
        assert history.load_result(history_id)["params"] == current["params"]
    # A newly generated workspace must not inherit the previous storage binding.
    at.button(key="btn_manual").click().run()
    assert not at.exception
    fresh = at.session_state["manual_result"]
    assert not fresh.get("history_id")
    at.button(key=f"hist_save_{fresh['result_id']}").click().run()
    assert len(history.list_results()) == 2
