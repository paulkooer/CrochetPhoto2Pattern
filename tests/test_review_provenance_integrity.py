"""Only recognized review evidence may produce affirmative provenance labels."""
from copy import deepcopy

import pytest
from streamlit.testing.v1 import AppTest

from app.services.result_logic import import_backup
from app.utils.exporters import export_markdown
from app.utils.provenance import provenance_lines
from tests.test_app_smoke import _mock_result
from tests.test_project_backup import RENDER

_SCOPE = "single_representable_subject"


def _render(result):
    at = AppTest.from_string(RENDER, default_timeout=30)
    at.session_state["result"] = result
    at.run()
    assert not at.exception
    return at


def _captions(result):
    return [caption.value for caption in _render(result).caption]


@pytest.mark.parametrize("flags", [
    {"reviewed_by_user": "false", "requires_subject_review": False, "subject_scope_review": "not_reviewed"},
    {"reviewed_by_user": True, "requires_subject_review": None, "subject_scope_review": _SCOPE},
    {"reviewed_by_user": True, "requires_subject_review": False, "subject_scope_review": None},
])
def test_imported_invalid_review_metadata_is_preserved_without_affirmative_claims(flags):
    source = _mock_result("invalid-review")
    source["vision_meta"] = {
        "source": "default", **flags, "review_head_box": {"invalid": True},
    }
    source["spans"] = {"头部": [0.2, 0.4]}
    original = deepcopy(source)
    restored = import_backup(source, "invalid-review")
    assert source == original
    assert restored["vision_meta"] == source["vision_meta"]
    from app.schemas import PatternResult

    assert PatternResult.from_result(restored).to_backup()["vision_meta"] == source["vision_meta"]
    at = _render(restored)
    captions = [caption.value for caption in at.caption]
    assert not any("比例与部件已经过人工确认" in text for text in captions)
    assert not any("人工框选分段：头部" in text for text in captions)
    assert any("复核记录无法识别" in warning.value for warning in at.warning)
    assert any("头部框记录无效" in text for text in captions)
    markdown = export_markdown(restored["params"], result=restored)
    assert "用户已确认" not in markdown
    assert "主体复核：记录无法识别" in markdown


def test_pdf_reports_unknown_review_without_a_false_confirmation(monkeypatch):
    pytest.importorskip("reportlab")
    import reportlab.platypus as platypus

    from app.utils.pdf_export import export_pdf

    result = _mock_result("invalid-review-pdf")
    result["vision_meta"] = {"requires_subject_review": "false", "subject_scope_review": _SCOPE}
    texts = []
    paragraph = platypus.Paragraph

    def capture(text, *args, **kwargs):
        texts.append(text)
        return paragraph(text, *args, **kwargs)

    monkeypatch.setattr(platypus, "Paragraph", capture)
    assert export_pdf(result["params"], result=result).startswith(b"%PDF-")
    assert any("主体复核：记录无法识别" in text for text in texts)
    assert not any("用户已确认" in text for text in texts)


@pytest.mark.parametrize(("meta", "confirmed"), [
    ({"reviewed_by_user": True, "requires_subject_review": False, "subject_scope_review": _SCOPE}, True),
    ({"reviewed_by_user": True}, True),
    ({"reviewed_by_user": True, "requires_subject_review": True}, False),
    ({"reviewed_by_user": True, "requires_subject_review": "false"}, False),
    ({"reviewed_by_user": True, "requires_subject_review": None}, False),
    ({"reviewed_by_user": True, "subject_scope_review": None}, False),
    ({"reviewed_by_user": True, "subject_scope_review": "not_reviewed"}, False),
    ({"reviewed_by_user": 1, "requires_subject_review": False}, False),
])
def test_result_page_only_confirms_recognized_review_records(meta, confirmed):
    result = _mock_result("review-label")
    result["vision_meta"] = {"source": "default", **meta}
    captions = _captions(result)
    assert any("比例与部件已经过人工确认" in text for text in captions) is confirmed


@pytest.mark.parametrize(("meta", "confirmed", "pending"), [
    ({"requires_subject_review": False, "reviewed_by_user": True, "subject_scope_review": _SCOPE},
     True, False),
    ({"subject_scope_review": _SCOPE}, True, False),
    ({"requires_subject_review": True, "reviewed_by_user": True, "subject_scope_review": _SCOPE},
     False, True),
    ({"requires_subject_review": False, "subject_scope_review": "not_reviewed"}, False, False),
    ({"requires_subject_review": "false", "reviewed_by_user": True, "subject_scope_review": _SCOPE},
     False, False),
    ({"requires_subject_review": 0, "reviewed_by_user": True, "subject_scope_review": _SCOPE}, False, False),
    ({"requires_subject_review": None, "reviewed_by_user": True, "subject_scope_review": _SCOPE},
     False, False),
    ({"requires_subject_review": False, "reviewed_by_user": None, "subject_scope_review": _SCOPE},
     False, False),
    ({"requires_subject_review": False, "reviewed_by_user": True, "subject_scope_review": None},
     False, False),
    ({"requires_subject_review": False, "reviewed_by_user": "false", "subject_scope_review": _SCOPE},
     False, False),
    ({"requires_subject_review": False, "reviewed_by_user": 1, "subject_scope_review": _SCOPE}, False, False),
])
def test_exported_subject_review_does_not_promote_unknown_evidence(meta, confirmed, pending):
    lines = provenance_lines({"vision_meta": meta})
    assert any("用户已确认" in line for line in lines) is confirmed
    assert any("尚未确认" in line for line in lines) is pending


@pytest.mark.parametrize(("box", "span", "confirmed"), [
    ([0.1, 0.2, 0.7, 0.4], [0.2, 0.4], True),
    ((0.1, 0.2, 0.7, 0.4), (0.2, 0.4), True),
    ({"invalid": True}, [0.2, 0.4], False),
    ([0.1, 0.2, 0.7], [0.2, 0.4], False),
    ([0.1, True, 0.7, 1.0], [1.0, 1.0], False),
    ([0.1, 0.0, 0.7, 0.4], [False, 0.4], False),
    ([0.1, 0.4, 0.7, 0.2], [0.2, 0.4], False),
    ([0.1, 0.2, 0.7, 0.4], [0.1, 0.4], False),
    ([0.1, 0.2, 0.7, 0.4], None, False),
])
def test_head_box_label_requires_valid_matching_record(box, span, confirmed):
    result = _mock_result("head-evidence")
    result["vision_meta"]["review_head_box"] = box
    result["spans"] = {"头部": span} if span is not None else None
    captions = _captions(result)
    assert any("人工框选分段：头部" in text for text in captions) is confirmed
