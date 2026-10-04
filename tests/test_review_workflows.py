"""Cross-boundary regressions for the 2026-10-04 audit findings."""
from copy import deepcopy
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from app.cli import build_parser, run
from app.models.validator import validate_pattern
from app.ui.result_logic import import_backup, rebuild_params, regenerate_with_size
from app.utils import history
from app.utils.exporters import export_markdown
from app.utils.parade_export import export_parade_report, lint_parade_dsl
from app.utils.share import decode_result, encode_result

_RENDER = '''
import streamlit as st
from app.ui.result_renderer import render_results
render_results(st.session_state["audit_result"], "audit_result")
'''


@pytest.fixture
def result():
    data = run(build_parser().parse_args(["--mock"]))
    data["result_id"] = "review-result"
    return data


@pytest.mark.parametrize("count,inc,ok,notes", [
    (12, 6, True, False), (7, 1, True, True),
    (12, 0, False, False), (13, 0, False, True),
])
def test_validation_messages_and_download_gate(result, count, inc, ok, notes):
    result["params"]["parts"][0]["rounds"] = [
        {"row": 1, "stitches": 6},
        {"row": 2, "stitches": count, "increase": inc},
    ]
    validation = validate_pattern(result["params"])
    assert validation["ok"] is ok
    assert bool(validation["notes"]) is notes
    at = AppTest.from_string(_RENDER, default_timeout=30)
    at.session_state["audit_result"] = result
    at.run()
    assert not at.exception
    warnings = [w.value for w in at.warning if "自检发现问题" in w.value]
    assert bool(warnings) is not ok
    if not ok:
        assert validation["issues"][0] in warnings[0]
    assert at.button(key="pdf_gen_review-result").disabled is not ok


@pytest.mark.parametrize("field,value", [
    ("geometry", {"silhouette": ["malformed"]}),
    ("sizing", {"photo_head_to_height_ratio": "bad"}),
    ("vision_meta", {"source": ["mock"]}),
    ("usage", {"input_tokens": {"bad": 1}}),
    ("style", {"sphere_mode": "unknown"}),
    ("spans", {"头部": [0.8, 0.2]}),
    ("color_bands", [{"start": 0.8, "end": 0.2, "color": "白色"}]),
])
def test_import_rejects_bad_metadata_without_mutation(result, field, value):
    result[field] = value
    original = deepcopy(result)
    with pytest.raises(ValueError):
        import_backup(result, "new")
    assert result == original


def test_invalid_edit_retains_current_result_and_cached_exports(result):
    import json

    at = AppTest.from_string(_RENDER, default_timeout=30)
    at.session_state["audit_result"] = result
    at.session_state["pdf_review-result"] = b"cached-pdf"
    at.session_state["share_token_review-result"] = "cached-token"
    at.run()
    invalid = deepcopy(result["params"])
    invalid["parts"][0]["rounds"][1]["stitches"] = 13
    at.text_area(key="json_edit_review-result").input(json.dumps(invalid))
    at.button(key="regen_review-result").click().run()
    assert not at.exception
    assert at.session_state["audit_result"] == result
    assert at.session_state["pdf_review-result"] == b"cached-pdf"
    assert at.session_state["share_token_review-result"] == "cached-token"
    assert any("自检失败" in error.value for error in at.error)
    with pytest.raises(ValueError, match="自检失败"):
        rebuild_params(invalid)
    with pytest.raises(ValueError, match="自检失败"):
        import_backup({**result, "params": invalid}, "bad")
    with pytest.raises(ValueError, match="自检失败"):
        export_markdown(invalid)
    from app.utils.pdf_export import export_pdf
    with pytest.raises(ValueError, match="自检失败"):
        export_pdf(invalid)


def test_share_history_resize_export_roundtrip_retains_provenance(result):
    token = encode_result(result)
    assert token is not None
    decoded = decode_result(token)
    assert decoded is not None
    shared = import_backup(decoded, "shared")
    history.save_result(shared)
    stored = history.load_result("shared")
    assert stored is not None
    restored = import_backup(stored, "restored")
    resized = regenerate_with_size(restored, 10, 20)
    at = AppTest.from_string(_RENDER, default_timeout=30)
    at.session_state["audit_result"] = resized
    at.run()
    assert not at.exception
    md = export_markdown(resized["params"], result=resized)
    assert "Mock 演示数据" in md
    assert "user_resize" in md
    assert result["generator_version"] in md
    assert "未验证实际可钩性" in md


def test_pdf_contains_source_and_verification_labels(result, monkeypatch):
    pytest.importorskip("reportlab")
    import reportlab.platypus as platypus

    from app.utils.pdf_export import export_pdf

    paragraph = platypus.Paragraph
    texts = []

    def capture(text, *args, **kwargs):
        texts.append(text)
        return paragraph(text, *args, **kwargs)

    monkeypatch.setattr(platypus, "Paragraph", capture)
    assert export_pdf(result["params"], result=result).startswith(b"%PDF-")
    assert any("Mock 演示数据" in text for text in texts)
    assert any("未验证实际可钩性" in text for text in texts)


def test_partial_parade_counts_physical_copies():
    part = {"name": "head", "quantity": 2, "magic_ring": True, "rounds": [
        {"row": 1, "stitches": 6},
        {"row": 2, "stitches": 7, "increase": 2, "decrease": 1},
        {"row": 3, "stitches": 7},
    ]}
    report = export_parade_report({"params": {"parts": [part]}})
    assert lint_parade_dsl(report.text) == []
    assert not report.complete
    assert (report.exported_rounds, report.requested_rounds) == (2, 6)
    assert (report.exported_parts, report.requested_parts) == (0, 2)
    assert report.warnings


def test_parade_counts_skipped_parts_in_requested_totals():
    report = export_parade_report({"params": {"parts": [
        {"name": "valid", "rounds": [{"stitches": 6}]},
        {"name": "empty", "quantity": 2, "rounds": []},
        {"name": "bad-start", "rounds": [{"stitches": 0}]},
    ]}})
    assert not report.complete
    assert (report.exported_parts, report.requested_parts) == (1, 4)
    assert (report.exported_rounds, report.requested_rounds) == (1, 2)


@pytest.mark.parametrize("mode", [None, "disabled", "shared", "typo"])
def test_history_disabled_mode_blocks_every_database_operation(result, monkeypatch, mode):
    history.save_result(result)
    if mode is None:
        monkeypatch.delenv("CROCHET_HISTORY_MODE")
    else:
        monkeypatch.setenv("CROCHET_HISTORY_MODE", mode)
    for operation in (
        lambda: history.list_results(),
        lambda: history.load_result(result["result_id"]),
        lambda: history.delete_result(result["result_id"]),
        lambda: history.save_result(result),
    ):
        with pytest.raises(PermissionError):
            operation()
    monkeypatch.setenv("CROCHET_HISTORY_MODE", "single_user")
    assert history.load_result(result["result_id"]) is not None


def test_share_entry_rejects_malformed_metadata_before_session_install(result):
    result["geometry"] = {"silhouette": ["bad"]}
    token = encode_result(result)
    assert token is not None
    app = str(Path(__file__).resolve().parents[1] / "app" / "main.py")
    at = AppTest.from_file(app, default_timeout=30)
    at.query_params["p"] = token
    at.run()
    assert not at.exception
    assert "result" not in at.session_state
    assert any("分享链接内容无效" in error.value for error in at.error)


def test_disabled_history_is_inaccessible_in_two_ui_sessions(result, monkeypatch):
    history.save_result(result, title="private-pattern")
    monkeypatch.delenv("CROCHET_HISTORY_MODE")
    script = "from app.ui.sidebar import render_sidebar\nrender_sidebar()"
    for _ in range(2):
        at = AppTest.from_string(script, default_timeout=30).run()
        assert not at.exception
        assert not any("private-pattern" in c.value for c in at.caption)
        assert not any(b.key.startswith("hist_load_") for b in at.button)
        assert not any(b.key.startswith("hist_del_") for b in at.button)


def test_legacy_export_does_not_invent_generation_version(result):
    result.pop("generator_version")
    imported = import_backup(result, "legacy")
    assert imported["generator_version"] is None
    md = export_markdown(imported["params"], result=imported)
    assert "生成版本（记录值）：未记录" in md
