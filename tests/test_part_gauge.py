"""Independent garment swatches must stay consistent with every saved/output path."""
import json
import math
from copy import deepcopy
from dataclasses import asdict
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import pytest
from streamlit.testing.v1 import AppTest

from app.models.crochet_params import CrochetParamsGenerator
from app.models.gauge import Gauge, ShapingStyle, gauge_for_part
from app.models.materials import material_summary_text
from app.models.structure_designer import StructureDesigner
from app.models.validator import require_valid_pattern, validate_pattern
from app.schemas import CrochetPart, ImageAnalysis, PatternResult
from app.trials import TrialDataError, create_trial_draft_from_bytes
from app.ui.pattern_editor import edit_yarn
from app.ui.progress_state import capture_progress, progress_entries, retained_progress
from app.ui.result_logic import (
    import_backup,
    rebuild_params,
    regenerate_with_gauge,
    regenerate_with_head_opening,
    regenerate_with_part_gauge,
    regenerate_with_size,
    regenerate_with_structure,
)
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
from tests.test_project_backup import RENDER
from tests.test_selective_regeneration import part
from tests.test_stitch_attachments import _result as attached_result

FIXTURE = Path(__file__).parent / "fixtures/garment_gauge_a64490c"


def garment(one_piece=False):
    analysis = ImageAnalysis(body_type="标准", head_diameter_cm=5.7, height_cm=36,
                             main_features=[], pose="站立", difficulty="medium",
                             parts=["头部", "身体", "手臂", "帽子", "裙子"])
    structure = StructureDesigner.design_3d_structure(analysis)
    for p in structure["parts"]:
        p["color"] = "红色"
    gauge = Gauge(30, 32)
    style = ShapingStyle(one_piece=one_piece)
    params = CrochetParamsGenerator.generate_params(analysis, structure, gauge=gauge, style=style,
                                                     head_opening_stitches=None if one_piece else 16)
    return PatternResult(analysis=analysis.model_dump(), structure=structure, params=params,
                         gauge=asdict(gauge), style=asdict(style), result_id="garment").to_result_dict()


def mark(result, name):
    result = deepcopy(result)
    rows = part(result, name)["rounds"]
    rows.append({"row":rows[-1]["row"] + 1, "stitches":rows[-1]["stitches"],
                 "notes":f"{rows[-1]['stitches']}X；保留人工第末圈"})
    result["params"] = rebuild_params(result["params"])
    return result


@pytest.mark.parametrize("name", ["帽子", "裙子"])
def test_body_30_32_and_garment_26_28_use_separate_geometry_and_keep_authored_arms(name):
    current = mark(garment(), "手臂")
    snapshot = deepcopy(current)
    updated = regenerate_with_part_gauge(current, name, Gauge(26, 28))
    assert current == snapshot
    assert updated["params"]["gauge"] == {"stitches_per_10cm":30, "rows_per_10cm":32}
    chosen = part(updated, name)
    assert chosen["gauge"] == {"stitches_per_10cm":26, "rows_per_10cm":28}
    for p in current["params"]["parts"]:
        if p["name"] != name:
            assert part(updated, p["name"]) == p
    if name == "裙子":
        # π × 5.7cm × 2.6 sts/cm rounded to six sectors is 48, not the body's 54.
        assert chosen["rounds"][0]["stitches"] == 48
        assert part(current, name)["rounds"][0]["stitches"] == 54
        assert chosen["height_cm"] == round(len(chosen["rounds"]) * 10 / 28, 1)
        assert "48 针开口" in updated["params"]["assembly_instructions"]
    else:
        assert max(r["stitches"] for r in chosen["rounds"]) == 54
        wall = [r for r in chosen["rounds"] if r["region"] == "wall"]
        assert chosen["height_cm"] == round(len(wall) * 10 / 28, 1)
        assert wall[-1]["height_range_cm"][1] == pytest.approx(len(wall) * 10 / 28)
    assert part(updated, "头部")["rounds"][-1]["stitches"] == 16
    require_valid_pattern(updated["params"])


def test_same_color_usage_weights_default_measured_and_independent_heuristic_stitches():
    current = edit_yarn(garment(), {"ball_weight_g":50, "ball_length_m":125,
                                   "swatch_weight_g":5, "swatch_stitches":10, "swatch_rows":10,
                                   "waste_percent":10})
    updated = regenerate_with_part_gauge(current, "裙子", Gauge(26, 28))
    parts = updated["params"]["parts"]
    independent = sum(r["stitches"] for r in part(updated, "裙子")["rounds"])
    all_stitches = sum(sum(r["stitches"] for r in p["rounds"]) * p["quantity"] for p in parts)
    # Independent hand calculation from documented area heuristic, not the estimator helper.
    garment_rate = .08 * (10 / 26) * (10 / 28) / (.785 * .625)
    grams = ((all_stitches - independent) * .05 + independent * garment_rate) * 1.1
    summary = updated["params"]["material_summary"]
    assert summary["total_stitches"] == all_stitches
    assert summary["grams"] == round(grams, 2)
    assert summary["meters"] == round(grams * 2.5, 2)
    assert summary["balls"] == math.ceil(grams / 50)
    assert summary["basis"] == "mixed_swatch_and_heuristic"
    assert "独立密度用经验估算" in material_summary_text(updated["params"])
    yarn = [m for m in updated["params"]["materials"] if "color" in m]
    assert len(yarn) == 1 and yarn[0]["stitches"] == all_stitches


def test_default_density_changes_keep_fixed_garment_work_and_only_clear_affected_progress():
    current = mark(regenerate_with_part_gauge(garment(), "帽子", Gauge(26, 28)), "帽子")
    progress = {identity:True for identity,_,_ in progress_entries(current,"result")}
    updated = regenerate_with_gauge(current, 32, 34)
    assert part(updated, "帽子") == part(current, "帽子")
    assert part(updated, "身体") != part(current, "身体")
    kept = retained_progress(current, updated, "result", progress)
    assert kept and all(json.loads(k)[0] == "帽子" for k in kept)
    assert len(kept) == len(part(current, "帽子")["rounds"])
    reset = regenerate_with_part_gauge(updated, "帽子", None)
    assert "gauge" not in part(reset, "帽子")
    assert "保留人工第末圈" not in str(part(reset, "帽子"))
    assert part(reset, "头部") == part(updated, "头部")


def test_equal_effective_gauge_and_reset_do_not_erase_manual_rounds_or_progress():
    current = mark(garment(), "帽子")
    progress = {identity:True for identity,_,_ in progress_entries(current,"result")}
    explicit = regenerate_with_part_gauge(current, "帽子", Gauge(30, 32))
    assert part(explicit, "帽子")["rounds"] == part(current, "帽子")["rounds"]
    assert retained_progress(current, explicit, "result", progress) == progress
    reset = regenerate_with_part_gauge(explicit, "帽子", None)
    assert reset["params"]["parts"] == current["params"]["parts"]
    assert retained_progress(explicit, reset, "result", progress) == progress
    bundle = create_trial_bundle(explicit, trial_id="uniform-explicit", maker_id="synthetic")
    measured = update_trial_bundle(bundle, swatch={**bundle.record.swatch.model_dump(),
        "measured":True, "stitches_per_10cm":28, "rows_per_10cm":30}, observation=None)
    candidate = trial_gauge_candidate(measured, explicit)
    assert candidate["params"]["gauge"] == asdict(Gauge(28,30))
    assert part(candidate,"帽子") == part(explicit,"帽子")
    assert retained_progress(explicit,candidate,"result",progress) == {
        k:v for k,v in progress.items() if json.loads(k)[0] == "帽子"}
    assert measured.source == bundle.source


def test_independent_gauge_survives_resize_backup_and_head_opening_changes():
    current = regenerate_with_part_gauge(garment(), "帽子", Gauge(26, 28))
    restored = import_backup(PatternResult.from_result(current).to_backup(), "restored")
    for updated in (regenerate_with_size(restored, 8, 40),
                    regenerate_with_head_opening(restored, 18)):
        assert part(updated, "帽子")["gauge"] == {"stitches_per_10cm":26, "rows_per_10cm":28}
        require_valid_pattern(updated["params"])
    structure = deepcopy(restored["structure"])
    structure["parts"] = [p for p in structure["parts"] if p["name"] != "帽子"]
    removed = regenerate_with_structure(restored, structure)
    assert all(p["name"] != "帽子" for p in removed["params"]["parts"])


@pytest.mark.parametrize("one_piece", [False, True])
def test_hat_can_use_its_own_density_with_both_body_constructions(one_piece):
    current = garment(one_piece)
    updated = regenerate_with_part_gauge(current, "帽子", Gauge(17, 14))
    assert part(updated, "帽子")["gauge"] == {"stitches_per_10cm":17, "rows_per_10cm":14}
    for p in current["params"]["parts"]:
        if p["name"] != "帽子":
            assert part(updated, p["name"]) == p
    require_valid_pattern(updated["params"])


@pytest.mark.parametrize("raw", [{}, {"stitches_per_10cm":26},
    {"stitches_per_10cm":26,"rows_per_10cm":28,"extra":1},
    {"stitches_per_10cm":True,"rows_per_10cm":28},
    {"stitches_per_10cm":5,"rows_per_10cm":28},
    {"stitches_per_10cm":41,"rows_per_10cm":28},
    {"stitches_per_10cm":26,"rows_per_10cm":7},
    {"stitches_per_10cm":26,"rows_per_10cm":51},
    {"stitches_per_10cm":float("nan"),"rows_per_10cm":28},
    {"stitches_per_10cm":26,"rows_per_10cm":float("inf")}, "invalid", []])
def test_invalid_override_fails_schema_import_and_print_boundaries(raw):
    current = garment()
    part(current, "帽子")["gauge"] = raw
    for operation in (lambda:CrochetPart(**part(current,"帽子")),
                      lambda:require_valid_pattern(current["params"]),
                      lambda:import_backup(current,"bad"),
                      lambda:export_markdown(current["params"],result=current),
                      lambda:export_pdf(current["params"],result=current)):
        with pytest.raises(ValueError):
            operation()


def test_attached_skirt_and_non_garment_overrides_are_explicitly_rejected():
    current = attached_result()
    snapshot = deepcopy(current)
    with pytest.raises(ValueError, match="挑针接裙"):
        regenerate_with_part_gauge(current,"裙子",Gauge(26,28))
    assert current == snapshot
    part(current,"裙子")["gauge"] = asdict(Gauge(26,28))
    with pytest.raises(ValueError, match="密度"):
        import_backup(current,"invalid")
    for name in ("头部","身体","手臂","missing"):
        original = garment()
        with pytest.raises(ValueError):
            regenerate_with_part_gauge(original,name,Gauge(26,28))


def test_validator_uses_the_part_density_for_shaping_advice():
    params = {"gauge":asdict(Gauge(13,16)), "parts":[
        {"name":"帽子", "type":"cup", "color":"红色", "gauge":asdict(Gauge(17,14)),
         "rounds":[{"row":1,"stitches":12,"notes":"魔法环起12针（X×12）"},
                   {"row":2,"stitches":24,"increase":12,"notes":"12V"}]}]}
    validation = validate_pattern(params)
    assert validation["ok"]
    assert not any("平滑塑形节奏" in note for note in validation["notes"])
    params["parts"][0].pop("gauge")
    assert any("平滑塑形节奏" in note for note in validate_pattern(params)["notes"])


def test_exports_show_default_and_independent_density_and_pdf_input(monkeypatch):
    current = regenerate_with_part_gauge(garment(),"帽子",Gauge(26,28))
    markdown = export_markdown(current["params"],result=current)
    assert "默认密度：10cm × 30 针 × 32 行" in markdown
    assert "独立密度：10cm × 26 针 × 28 行" in markdown
    assert "所有 cm 标注由它推导" not in markdown
    platypus = pytest.importorskip("reportlab.platypus")
    original = platypus.Paragraph
    texts = []
    def paragraph(text,*args,**kwargs):
        texts.append(str(text))
        return original(text,*args,**kwargs)
    monkeypatch.setattr(platypus,"Paragraph",paragraph)
    assert export_pdf(current["params"],result=current).startswith(b"%PDF-")
    assert any("独立密度：10cm × 26 针 × 28 行" in text for text in texts)


def test_independent_gauge_cannot_be_recorded_as_a_single_swatch_trial():
    current = regenerate_with_part_gauge(garment(),"帽子",Gauge(26,28))
    with pytest.raises(TrialDataError, match="默认密度"):
        create_trial_bundle(current,trial_id="mixed",maker_id="synthetic")
    blob=json.dumps(PatternResult.from_result(current).to_backup(),ensure_ascii=False).encode()
    with pytest.raises(TrialDataError, match="默认密度"):
        create_trial_draft_from_bytes(blob,trial_id="mixed",maker_id="synthetic")


def test_actual_old_project_keeps_hash_progress_and_notes_without_new_null_fields():
    old = json.loads((FIXTURE/"project.json").read_text())
    restored = import_backup(old,"restored")
    assert pattern_revision(restored) == old["project_state"]["pattern_revision"]
    assert read_project_state(old,restored) == (old["project_state"]["completed_rounds"],
                                               old["project_state"]["notes"])
    assert all("gauge" not in p for p in restored["params"]["parts"])


def test_actual_old_trial_retains_source_bytes_hash_and_measured_regeneration():
    raw=(FIXTURE/"trial.zip").read_bytes()
    bundle=decode_trial_bundle(raw)
    with ZipFile(BytesIO(raw)) as archive:
        assert bundle.source == archive.read("pattern.json")
    restored=import_backup(json.loads(bundle.source),"legacy")
    assert pattern_revision(restored)==bundle.source_revision
    candidate=trial_gauge_candidate(bundle,restored)
    assert candidate["params"]["gauge"]==asdict(Gauge(28,30))
    with ZipFile(BytesIO(encode_trial_bundle(bundle))) as archive:
        assert archive.read("pattern.json")==bundle.source


def test_preview_apply_undo_redo_and_project_recovery_keep_unaffected_progress():
    current=mark(garment(),"手臂")
    at=AppTest.from_string(RENDER,default_timeout=30)
    at.session_state["result"]=current
    at.run()
    at.checkbox(key="chk_garment_头部_0").check().run()
    at.checkbox(key="chk_garment_帽子_0").check().run()
    at.text_area(key="project_notes_garment").input("帽子换针号后核对小样").run()
    at.checkbox(key="edit_garment_partgauge0_enabled").check().run()
    at.number_input(key="edit_garment_partgauge0_stitches").set_value(26).run()
    at.number_input(key="edit_garment_partgauge0_rows").set_value(28).run()
    at.button(key="edit_garment_partgauge0_preview").click().run()
    assert at.session_state["result"]==current
    at.button(key="edit_garment_preview_apply").click().run()
    for action in (None,"undo","redo"):
        if action:
            rid=at.session_state["result"]["result_id"]
            at.button(key=f"edit_{rid}_{action}").click().run()
        assert not at.exception
        saved=at.session_state["result"]
        rid=saved["result_id"]
        assert at.checkbox(key=f"chk_{rid}_头部_0").value
        assert at.checkbox(key=f"chk_{rid}_帽子_0").value==(action=="undo")
        assert (part(saved,"帽子").get("gauge") is not None)==(action!="undo")
        assert part(saved,"手臂")==part(current,"手臂")
        assert at.text_area(key=f"project_notes_{rid}").value=="帽子换针号后核对小样"
    create=next(b for b in at.button if b.label=="以当前图解新建试钩")
    assert create.disabled
    progress=capture_progress(saved,"result",at.session_state)
    project=project_backup(saved,progress,"帽子换针号后核对小样")
    restored=import_backup(json.loads(json.dumps(project)),"new-session")
    assert read_project_state(project,restored)==(progress,"帽子换针号后核对小样")
    assert gauge_for_part(part(restored,"帽子"),Gauge(30,32))==Gauge(26,28)
