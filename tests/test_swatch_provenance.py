"""A weighed swatch belongs to its recorded density, across edits and recovery."""
import hashlib
import json
from copy import deepcopy
from dataclasses import asdict
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import pytest
from streamlit.testing.v1 import AppTest

from app.models.crochet_params import CrochetParamsGenerator
from app.models.gauge import Gauge, ShapingStyle
from app.models.materials import YarnSpec, material_summary_text
from app.models.structure_designer import StructureDesigner
from app.models.validator import require_valid_pattern
from app.schemas import ImageAnalysis, PatternResult
from app.services.progress_state import capture_progress
from app.services.result_logic import import_backup, regenerate_with_gauge, regenerate_with_part_gauge
from app.ui.pattern_editor import edit_yarn
from app.utils.exporters import export_markdown
from app.utils.pdf_export import export_pdf
from app.utils.project import pattern_revision, project_backup, read_project_state
from app.utils.trial_bundle import (
    create_trial_bundle,
    decode_trial_bundle,
    encode_trial_bundle,
    trial_gauge_candidate,
    update_trial_bundle,
)

FIXTURE = Path(__file__).parent / "fixtures/swatch_4ae91ca"
SPEC = {"ball_weight_g":50, "ball_length_m":125, "swatch_weight_g":5,
        "swatch_stitches":10, "swatch_rows":10, "waste_percent":10}
RENDER = '''
import streamlit as st
from app.ui.result_renderer import render_results
if "audit_bundle" in st.session_state and "trial_workspace_result" not in st.session_state:
    from app.ui.trial_editor import _install
    _install("result", st.session_state.audit_bundle)
render_results(st.session_state.result, "result")
'''


def source():
    a = ImageAnalysis(body_type="标准", head_diameter_cm=5.7, height_cm=36,
        main_features=[], pose="站立", difficulty="medium", parts=["头部","身体","帽子"])
    structure = StructureDesigner.design_3d_structure(a, infer_missing_parts=False)
    for part in structure["parts"]:
        part["color"] = "蓝色" if part["name"] == "帽子" else "红色"
    gauge, style = Gauge(30,32), ShapingStyle()
    params = CrochetParamsGenerator.generate_params(a,structure,gauge=gauge,style=style)
    return PatternResult(analysis=a.model_dump(),structure=structure,params=params,
        gauge=asdict(gauge),style=asdict(style),result_id="swatch").to_result_dict()


def hat(result):
    return next(p for p in result["params"]["parts"] if p["name"] == "帽子")


def blue(result):
    return next(m for m in result["params"]["materials"] if m.get("color") == "蓝色")


def measured_bundle(result):
    bundle = create_trial_bundle(result,trial_id="synthetic-swatch",maker_id="synthetic")
    return update_trial_bundle(bundle,swatch={**bundle.record.swatch.model_dump(),
        "measured":True,"stitches_per_10cm":26,"rows_per_10cm":28},observation=None)


@pytest.mark.parametrize("pinned", [Gauge(30,32),Gauge(26,28)])
def test_unchanged_hat_keeps_usage_when_default_changes_to_or_away_from_its_density(pinned):
    current = regenerate_with_part_gauge(edit_yarn(source(),SPEC),"帽子",pinned)
    original = deepcopy(current)
    updated = regenerate_with_gauge(current,26,28)
    assert current == original
    assert hat(updated) == hat(current)
    assert blue(updated) == blue(current)
    assert updated["params"]["yarn_spec"]["swatch_gauge"] == asdict(Gauge(30,32))
    count = blue(updated)["stitches"]
    # Independent calculation: 5g per 100 stitches only applies to the 30×32 sample.
    rate = .05 if pinned == Gauge(30,32) else .08*(10/26)*(10/28)/(.785*.625)
    assert blue(updated)["grams"] == round(count*rate*1.1,2)
    assert updated["params"]["material_summary"]["basis"] == (
        "mixed_swatch_and_heuristic" if pinned == Gauge(30,32) else "heuristic")


def test_explicit_swatch_can_match_an_independent_part_instead_of_the_default():
    current = regenerate_with_part_gauge(source(),"帽子",Gauge(26,28))
    result = edit_yarn(current,{**SPEC,"swatch_gauge":asdict(Gauge(26,28))})
    assert blue(result)["grams"] == round(blue(result)["stitches"]*.05*1.1,2)
    assert result["params"]["material_summary"]["basis"] == "mixed_swatch_and_heuristic"
    assert "试片密度：10cm × 26 针 × 28 行" in material_summary_text(result["params"])
    assert "匹配试片密度用实测" in material_summary_text(result["params"])


def test_new_record_binds_origin_and_label_only_specs_have_no_new_null_field():
    original = source()
    updated = edit_yarn(original,SPEC)
    assert updated["params"]["yarn_spec"]["swatch_gauge"] == asdict(Gauge(30,32))
    assert "yarn_spec" not in original["params"]
    assert "swatch_gauge" not in YarnSpec(ball_weight_g=50,ball_length_m=125).model_dump()
    assert "swatch_gauge" not in YarnSpec(**SPEC).model_dump()
    assert "yarn_spec" not in edit_yarn(updated,None)["params"]


@pytest.mark.parametrize("raw", [{},[],{"stitches_per_10cm":26},
    {"stitches_per_10cm":True,"rows_per_10cm":28},
    {"stitches_per_10cm":float("nan"),"rows_per_10cm":28},
    {"stitches_per_10cm":26,"rows_per_10cm":float("inf")},
    {"stitches_per_10cm":5,"rows_per_10cm":28},
    {"stitches_per_10cm":41,"rows_per_10cm":28},
    {"stitches_per_10cm":26,"rows_per_10cm":7},
    {"stitches_per_10cm":26,"rows_per_10cm":51},
    {"stitches_per_10cm":26,"rows_per_10cm":28,"extra":1}])
def test_invalid_swatch_origin_fails_import_and_both_print_boundaries(raw):
    result = source()
    result["params"]["yarn_spec"] = {**SPEC,"swatch_gauge":raw}
    for operation in (lambda:require_valid_pattern(result["params"]),
                      lambda:import_backup(result,"bad"),
                      lambda:export_markdown(result["params"],result=result),
                      lambda:export_pdf(result["params"],result=result)):
        with pytest.raises(ValueError):
            operation()


def test_origin_without_a_complete_weighed_swatch_is_rejected():
    with pytest.raises(ValueError,match="称重"):
        YarnSpec(ball_weight_g=50,ball_length_m=125,swatch_gauge=asdict(Gauge(30,32)))


def test_actual_legacy_project_retains_raw_binding_progress_and_unknown_measurement():
    data = json.loads((FIXTURE/"project.json").read_text())
    original = deepcopy(data)
    restored = import_backup(data,"restored")
    assert data == original
    assert pattern_revision(data) == data["project_state"]["pattern_revision"]
    progress,notes = read_project_state(data,restored)
    assert progress and progress == data["project_state"]["completed_rounds"]
    assert notes == data["project_state"]["notes"]
    assert restored["params"]["yarn_spec"] == data["params"]["yarn_spec"]
    assert "swatch_gauge" not in restored["params"]["yarn_spec"]
    assert restored["params"]["material_summary"]["basis"] == "heuristic"
    assert "旧试片未记录测量密度" in material_summary_text(restored["params"])
    saved = project_backup(restored,progress,notes)
    second = import_backup(saved,"second")
    assert read_project_state(saved,second) == (progress,notes)


def test_actual_legacy_trial_preserves_source_sha_and_allows_saved_density_preview():
    raw = (FIXTURE/"trial.zip").read_bytes()
    bundle = decode_trial_bundle(raw)
    with ZipFile(BytesIO(raw)) as archive:
        assert bundle.source == archive.read("pattern.json")
    assert hashlib.sha256(bundle.source).hexdigest() == bundle.record.pattern.sha256
    current = import_backup(json.loads(bundle.source),"legacy")
    assert pattern_revision(current) == bundle.source_revision
    updated = trial_gauge_candidate(bundle,current)
    assert updated["params"]["gauge"] == asdict(Gauge(26,28))
    assert "swatch_gauge" not in updated["params"]["yarn_spec"]
    assert updated["params"]["material_summary"]["basis"] == "heuristic"
    with ZipFile(BytesIO(encode_trial_bundle(bundle))) as archive:
        assert archive.read("pattern.json") == bundle.source
    damaged = deepcopy(current)
    damaged["params"]["yarn_spec"]["swatch_gauge"] = asdict(Gauge(30,32))
    with pytest.raises(ValueError,match="原图解"):
        trial_gauge_candidate(bundle,damaged)


def test_ui_trial_apply_undo_redo_and_project_keep_fixed_hat_measurement_and_progress():
    current = regenerate_with_part_gauge(edit_yarn(source(),SPEC),"帽子",Gauge(30,32))
    at = AppTest.from_string(RENDER,default_timeout=30)
    at.session_state["result"] = current
    at.session_state["audit_bundle"] = measured_bundle(current)
    at.run()
    at.checkbox(key="chk_swatch_头部_0").check().run()
    at.checkbox(key="chk_swatch_帽子_0").check().run()
    at.text_area(key="project_notes_swatch").input("保留帽子已测用量").run()
    at.button(key="trial_gauge_preview_result").click().run()
    assert at.session_state["result"] == current
    at.button(key="edit_swatch_preview_apply").click().run()
    for action in (None,"undo","redo"):
        if action:
            rid = at.session_state["result"]["result_id"]
            at.button(key=f"edit_{rid}_{action}").click().run()
        assert not at.exception
        saved = at.session_state["result"]
        rid = saved["result_id"]
        assert hat(saved) == hat(current) and blue(saved) == blue(current)
        assert at.checkbox(key=f"chk_{rid}_帽子_0").value
        assert at.checkbox(key=f"chk_{rid}_头部_0").value == (action=="undo")
    # Editing only the ball label must retain the swatch's original 30×32 density.
    rid = at.session_state["result"]["result_id"]
    assert at.number_input(key=f"edit_{rid}_swatchgauge_stitches").value == 30
    at.number_input(key=f"edit_{rid}_weight").set_value(60)
    next(b for b in at.button if b.label=="更新材料估算").click().run()
    saved = at.session_state["result"]
    assert not at.exception and blue(saved)["grams"] == blue(current)["grams"]
    assert saved["params"]["yarn_spec"]["swatch_gauge"] == asdict(Gauge(30,32))
    progress = capture_progress(saved,"result",at.session_state)
    project = project_backup(saved,progress,"保留帽子已测用量")
    restored = import_backup(json.loads(json.dumps(project)),"fresh")
    assert read_project_state(project,restored) == (progress,"保留帽子已测用量")
    assert blue(restored)["grams"] == blue(current)["grams"]


def test_legacy_ui_requires_confirmation_without_losing_weighed_data_then_supports_undo():
    current = import_backup(json.loads((FIXTURE/"project.json").read_text()),"old")
    at = AppTest.from_string(RENDER,default_timeout=30)
    at.session_state["result"] = current
    at.run()
    assert any("旧试片未记录" in warning.value for warning in at.warning)
    next(b for b in at.button if b.label=="更新材料估算").click().run()
    assert at.session_state["result"] == current
    assert any("核对并确认" in error.value for error in at.error)
    at.checkbox(key="edit_old_swatch_confirm").check()
    next(b for b in at.button if b.label=="更新材料估算").click().run()
    confirmed = at.session_state["result"]
    assert confirmed["params"]["yarn_spec"]["swatch_gauge"] == asdict(Gauge(30,32))
    assert confirmed["params"]["material_summary"]["basis"] == "measured_swatch"
    rid = confirmed["result_id"]
    at.button(key=f"edit_{rid}_undo").click().run()
    assert not at.exception
    assert at.session_state["result"]["params"] == current["params"]


def test_markdown_and_actual_pdf_input_use_the_recorded_origin_after_default_change(monkeypatch):
    result = regenerate_with_part_gauge(edit_yarn(source(),SPEC),"帽子",Gauge(30,32))
    result = trial_gauge_candidate(measured_bundle(result),result)
    origin = "试片密度：10cm × 30 针 × 32 行"
    assert origin in export_markdown(result["params"],result=result)
    platypus = pytest.importorskip("reportlab.platypus")
    original = platypus.Paragraph
    texts = []
    def capture(text,*args,**kwargs):
        texts.append(str(text))
        return original(text,*args,**kwargs)
    monkeypatch.setattr(platypus,"Paragraph",capture)
    assert export_pdf(result["params"],result=result).startswith(b"%PDF-")
    assert any(origin in text for text in texts)
