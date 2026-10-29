"""Portable physical measurements must stay bound to their original pattern."""
import hashlib
import json
from copy import deepcopy
from datetime import date, timedelta
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from streamlit.testing.v1 import AppTest

from app.trials import (
    MAX_TRIAL_BYTES,
    TrialDataError,
    analyze_trials,
    create_trial_draft,
    decode_trial_json,
    load_trial_records,
)
from app.utils.project import project_backup
from app.utils.trial_bundle import (
    MAX_TRIAL_BUNDLE_BYTES,
    create_trial_bundle,
    decode_trial_bundle,
    encode_trial_bundle,
    update_trial_bundle,
)
from tests.test_app_smoke import _APP, _mock_result

RENDER = '''
import streamlit as st
from app.ui.trial_editor import render_trial_editor
render_trial_editor(st.session_state.result, "result")
'''


def _draft():
    return create_trial_bundle(_mock_result("trial-source"), trial_id="trial-a", maker_id="maker-a")


def _completed(bundle=None, *, scope="full_project", modified=False):
    bundle = bundle or _draft()
    return update_trial_bundle(bundle, swatch={**bundle.record.swatch.model_dump(), "measured": True},
                               observation={"completed_on": date.today(), "overall_height_cm": 19.2,
                                            "yarn_used_grams": 70.5, "active_minutes": 110,
                                            "time_scope": scope, "pattern_modified": modified,
                                            "modifications": ["身体加两圈"] if modified else []})


def _zip(members):
    out = BytesIO()
    with ZipFile(out, "w", compression=ZIP_DEFLATED) as archive:
        for name, data in members:
            archive.writestr(name, data)
    return out.getvalue()


def _members(bundle):
    return [("pattern.json", bundle.source), ("trial-a.trial.json", bundle.record.model_dump_json())]


def _click(at, label):
    return next(b for b in at.button if b.label == label).click().run()


def _app():
    at = AppTest.from_string(RENDER, default_timeout=30)
    at.session_state["result"] = _mock_result("trial-source")
    at.run()
    return at


def _start(at):
    at.text_input(key="trial_id_result").input("trial-a")
    at.text_input(key="trial_maker_result").input("maker-a")
    _click(at, "以当前图解新建试钩")
    assert not at.exception
    return f"trial_fields_result_{at.session_state['trial_workspace_result']['token']}_"


def test_bundle_draft_matches_cli_and_keeps_personal_project_state_out(tmp_path):
    source = _mock_result("personal")
    project = project_backup(source, {}, "不应进入试钩包的个人备注")
    original = deepcopy(project)
    bundle = create_trial_bundle(project, trial_id="trial-a", maker_id="maker-a")
    assert project == original
    assert "project_state" not in json.loads(bundle.source)
    assert "不应进入" not in bundle.source.decode()
    path = tmp_path / "pattern.json"
    path.write_bytes(bundle.source)
    cli_draft = create_trial_draft(path, trial_id="trial-a", maker_id="maker-a")
    assert cli_draft == bundle.record.model_dump(mode="json")
    assert bundle.record.pattern.sha256 == hashlib.sha256(bundle.source).hexdigest()
    expected = sum(sum(r["stitches"] for r in p["rounds"]) * p.get("quantity", 1)
                   for p in source["params"]["parts"])
    assert bundle.record.pattern.total_stitches == expected


@pytest.mark.parametrize("completed", [False, True])
def test_bundle_roundtrip_remains_cli_analyzable_without_rewriting_source(tmp_path, completed):
    bundle = _completed() if completed else _draft()
    # A later application must preserve the producer's recorded version.
    bundle.record.pattern.application_version = "older-producer"
    restored = decode_trial_bundle(encode_trial_bundle(bundle))
    assert restored == bundle
    with ZipFile(BytesIO(encode_trial_bundle(restored))) as archive:
        (tmp_path / "trial-a.trial.json").write_bytes(archive.read("trial-a.trial.json"))
    records = load_trial_records(tmp_path)
    assert records == [bundle.record]
    report = analyze_trials(records)
    assert report["summary"]["calibration_ready"] is False


@pytest.mark.parametrize("scope,modified,time_eligible,grams_eligible", [
    ("full_project", False, False, True),
    ("round_crochet_baseline", False, True, True),
    ("round_crochet_baseline", True, False, False),
])
def test_ui_records_follow_existing_analysis_eligibility(scope, modified, time_eligible, grams_eligible):
    bundle = _completed(scope=scope, modified=modified)
    report = analyze_trials([decode_trial_bundle(encode_trial_bundle(bundle)).record])
    case = report["cases"][0]
    assert case["time_calibration_eligible"] is time_eligible
    assert case["calibration_eligible"] is grams_eligible


@pytest.mark.parametrize("field,value", [("sha256", "0" * 64), ("total_stitches", 1),
                                         ("total_physical_rounds", 1), ("target_height_cm", 123),
                                         ("estimated_time_minutes", 1),
                                         ("gauge", {"stitches_per_10cm": 6, "rows_per_10cm": 8})])
def test_restoration_rejects_tampered_source_binding_even_with_valid_record_shape(field, value):
    bundle = _draft()
    payload = bundle.record.model_dump(mode="json")
    payload["pattern"][field] = value
    data = _zip([("pattern.json", bundle.source), ("trial-a.trial.json", json.dumps(payload))])
    with pytest.raises(ValueError, match="不匹配"):
        decode_trial_bundle(data)


def test_reformatting_source_cannot_silently_rebind_a_trial():
    bundle = _draft()
    data = _zip([("pattern.json", bundle.source + b"\n"), _members(bundle)[1]])
    with pytest.raises(ValueError, match="不匹配"):
        decode_trial_bundle(data)


@pytest.mark.parametrize("damage", ["extra", "path", "filename", "no_trial", "bad_zip", "oversize_record"])
def test_bundle_rejects_unsupported_or_oversized_archives(damage):
    members = _members(_draft())
    if damage == "extra":
        members.append(("extra.json", "{}"))
    elif damage == "path":
        members[1] = ("../trial-a.trial.json", members[1][1])
    elif damage == "filename":
        members[1] = ("different.trial.json", members[1][1])
    elif damage == "no_trial":
        members[1] = ("record.json", members[1][1])
    elif damage == "oversize_record":
        members[1] = ("trial-a.trial.json", " " * (MAX_TRIAL_BYTES + 1))
    data = b"not a zip" if damage == "bad_zip" else _zip(members)
    with pytest.raises(ValueError):
        decode_trial_bundle(data)


@pytest.mark.parametrize("raw", [b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":1e400}', b'\xff', b'{'])
def test_trial_json_rejects_ambiguous_or_nonfinite_payloads(raw):
    with pytest.raises(TrialDataError):
        decode_trial_json(raw)


def test_trial_json_bom_and_byte_limits():
    assert decode_trial_json(b'\xef\xbb\xbf{"a":1}') == {"a": 1}
    with pytest.raises(ValueError):
        decode_trial_json(b" " * (MAX_TRIAL_BYTES + 1))
    with pytest.raises(ValueError):
        decode_trial_bundle(b" " * (MAX_TRIAL_BUNDLE_BYTES + 1))


@pytest.mark.parametrize("damage", ["no_swatch", "missing_size", "future", "modified_without_notes"])
def test_incomplete_observations_never_replace_draft(damage):
    draft = _draft()
    observation = _completed().record.observation.model_dump(mode="json")
    swatch = {**draft.record.swatch.model_dump(), "measured": True}
    if damage == "no_swatch":
        swatch["measured"] = False
    elif damage == "missing_size":
        observation["overall_height_cm"] = None
    elif damage == "future":
        observation["completed_on"] = date.today() + timedelta(days=1)
    else:
        observation["pattern_modified"] = True
    with pytest.raises(ValueError):
        update_trial_bundle(draft, swatch=swatch, observation=observation)
    assert draft.record.status == "draft" and draft.record.observation is None


def test_editor_create_complete_and_later_pattern_edit_keep_original_binding():
    at = _app()
    _click(at, "以当前图解新建试钩")
    assert "trial_workspace_result" not in at.session_state
    assert any("编号" in error.value for error in at.error)
    prefix = _start(at)
    initial = at.session_state["trial_workspace_result"]["archive"]
    # 表单内勾选不加中途 .run()（streamlit≥1.66 会丢弃未提交的表单值）：
    # 直接提交，让“标记为完成”随提交生效，才能触发缺少实测小样的校验错误。
    at.checkbox(key=prefix + "complete").check()
    _click(at, "保存记录并更新下载")
    assert any("实测小样" in error.value for error in at.error)
    assert at.session_state["trial_workspace_result"]["archive"] == initial
    at.checkbox(key=prefix + "measured").check()
    at.date_input(key=prefix + "date").set_value(date.today())
    at.number_input(key=prefix + "overall_height_cm").set_value(19.2)
    at.number_input(key=prefix + "yarn_used_grams").set_value(70.5)
    at.number_input(key=prefix + "minutes").set_value(110)
    at.text_area(key=prefix + "notes").input("实测记录")
    _click(at, "保存记录并更新下载")
    assert not at.exception and not at.error
    saved = at.session_state["trial_workspace_result"]["bundle"]
    assert saved.record.status == "completed" and saved.record.observation.notes == "实测记录"
    assert saved.record.observation.time_scope == "full_project"
    assert at.metric[0].value == "+6.7%"
    source = deepcopy(at.session_state["result"])
    changed = deepcopy(source)
    changed["analysis"]["height_cm"] = 25
    changed["result_id"] = "edited-source"
    at.session_state["result"] = changed
    at.run()
    assert not at.exception and any("绑定原图解" in warning.value for warning in at.warning)
    assert at.session_state["trial_workspace_result"]["bundle"] == saved
    at.session_state["result"] = source
    at.run()
    assert not any("绑定原图解" in warning.value for warning in at.warning)


def test_fresh_editor_restores_measurements_and_failed_restore_is_atomic(monkeypatch):
    saved = _completed()
    upload = BytesIO(encode_trial_bundle(saved))
    monkeypatch.setattr("app.ui.trial_editor.st.file_uploader", lambda *a, **k: upload)
    at = _app()
    original = deepcopy(at.session_state["result"])
    at.button(key="trial_restore_result").click().run()
    assert not at.exception
    assert at.session_state["trial_workspace_result"]["bundle"] == saved
    assert at.session_state["result"] == original
    token = at.session_state["trial_workspace_result"]["token"]
    assert at.number_input(key=f"trial_fields_result_{token}_yarn_used_grams").value == 70.5
    upload = BytesIO(b"broken")
    at.button(key="trial_restore_result").click().run()
    assert not at.exception and any("原记录保持不变" in error.value for error in at.error)
    assert at.session_state["trial_workspace_result"]["bundle"] == saved
    assert at.session_state["result"] == original
    at.button(key="trial_close_result").click().run()
    assert "trial_workspace_result" not in at.session_state
    assert not any(str(key).startswith("trial_fields_result_") for key in at.session_state.to_dict())


def test_two_result_panels_keep_trial_workspaces_separate():
    script = RENDER + '\nrender_trial_editor(st.session_state.manual_result, "manual_result")'
    at = AppTest.from_string(script, default_timeout=30)
    at.session_state["result"] = _mock_result("source-photo")
    at.session_state["manual_result"] = _mock_result("source-manual")
    at.run()
    at.text_input(key="trial_maker_result").input("maker-a")
    next(b for b in at.button if b.label == "以当前图解新建试钩").click().run()
    assert not at.exception
    assert "trial_workspace_result" in at.session_state
    assert "trial_workspace_manual_result" not in at.session_state


def test_sidebar_opens_trial_in_fresh_session_and_failure_preserves_all_work(monkeypatch):
    saved = _completed()
    upload = BytesIO(encode_trial_bundle(saved))
    monkeypatch.setattr("app.ui.trial_editor.st.file_uploader",
                        lambda *a, **k: upload if k.get("key") == "trial_open_file" else None)
    at = AppTest.from_file(_APP, default_timeout=30).run()
    assert "result" not in at.session_state
    at.button(key="trial_open_apply").click().run()
    assert not at.exception
    assert at.session_state["trial_workspace_result"]["bundle"] == saved
    assert "manual_result" not in at.session_state
    assert not any("绑定原图解" in w.value for w in at.warning)
    original = deepcopy(at.session_state["result"])
    rid = original["result_id"]
    at.checkbox(key=f"chk_{rid}_头部_0").check().run()
    at.text_area(key=f"project_notes_{rid}").input("保留现有工作").run()
    upload = BytesIO(b"invalid")
    at.button(key="trial_open_apply").click().run()
    assert not at.exception and any("当前工作保持不变" in e.value for e in at.error)
    assert at.session_state["result"] == original
    assert at.session_state["trial_workspace_result"]["bundle"] == saved
    assert at.checkbox(key=f"chk_{rid}_头部_0").value
    assert at.text_area(key=f"project_notes_{rid}").value == "保留现有工作"
