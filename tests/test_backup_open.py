"""A saved pattern must be usable in a fresh session without generating a seed."""
import io
import json
from copy import deepcopy

import pytest
from streamlit.testing.v1 import AppTest

from app.schemas import PatternResult
from app.ui.result_logic import import_backup
from app.utils.backup import MAX_BACKUP_BYTES, MAX_PASTED_BACKUP_BYTES, decode_backup_json
from tests.test_app_smoke import _APP, _mock_result

_IMPORTER = "from app.ui.backup_import import render_backup_import\nrender_backup_import()"


def _backup():
    result = _mock_result("backup-source")
    result["params"]["parts"][0]["rounds"][2]["notes"] = "FLO((X,V)×6)"
    return PatternResult.from_result(result).to_backup()


@pytest.mark.parametrize("encoding", ["text", "utf8", "bom", "text_bom"])
def test_backup_decodes_unicode_and_bom_without_changing_pattern(encoding):
    original = _backup()
    text = json.dumps(original, ensure_ascii=False)
    payload = {"text": text, "utf8": text.encode(), "bom": text.encode("utf-8-sig"),
               "text_bom": "\ufeff" + text}[encoding]
    decoded = decode_backup_json(payload)
    assert decoded == original
    restored = import_backup(decoded, "restored")
    assert restored["params"]["parts"][0]["rounds"][2]["notes"] == "FLO((X,V)×6)"
    assert decoded == original  # Neither decoding nor validation mutates the backup.


@pytest.mark.parametrize("payload,message", [
    ("", "完整备份"), (b"  \n", "完整备份"), (b"\xff\xfe", "UTF-8"),
    ("\ud800", "UTF-8"), ('{"analysis":', "有效 JSON"),
    ("[]", "顶层"), ("null", "顶层"), ("123", "顶层"),
    ('{"parts":[]}', "备份完整结果"),
    ('{"analysis":{},"analysis":{}}', "重复字段"),
    ('{"analysis":{"a":1,"a":2}}', "重复字段"),
    ('{"analysis":NaN}', "NaN"), ('{"analysis":Infinity}', "Infinity"),
    ('{"analysis":-Infinity}', "Infinity"), ('{"analysis":1e999}', "非有限"),
])
def test_invalid_backup_has_actionable_error(payload, message):
    with pytest.raises(ValueError, match=message):
        decode_backup_json(payload)


def test_decoder_recursion_has_actionable_error(monkeypatch):
    # Decoder depth limits vary across Python versions and platforms. Exercise
    # the failure boundary without assuming a particular payload must hit it.
    def exhausted_decoder(*args, **kwargs):
        raise RecursionError("decoder recursion limit")

    monkeypatch.setattr("app.utils.backup.json.loads", exhausted_decoder)
    with pytest.raises(ValueError, match="嵌套过深") as error:
        decode_backup_json('{"analysis":{},"structure":{},"params":{}}')
    assert isinstance(error.value.__cause__, RecursionError)


def test_limit_is_utf8_bytes_and_exact_boundary_is_allowed():
    raw = json.dumps({"analysis": {}, "structure": {}, "params": {}, "note": "中文"},
                     ensure_ascii=False)
    size = len(raw.encode())
    assert size > len(raw)
    assert decode_backup_json(raw, max_bytes=size)["note"] == "中文"
    for payload in (raw, raw.encode()):
        with pytest.raises(ValueError, match="上限"):
            decode_backup_json(payload, max_bytes=size - 1)


def test_file_path_accepts_backups_larger_than_paste_limit():
    # Existing large backups can use the file path without weakening the paste bound.
    payload = json.dumps({"analysis": {}, "structure": {}, "params": {},
                          "note": "x" * MAX_PASTED_BACKUP_BYTES}).encode()
    assert MAX_PASTED_BACKUP_BYTES < len(payload) < MAX_BACKUP_BYTES
    assert len(decode_backup_json(payload)["note"]) == MAX_PASTED_BACKUP_BYTES
    with pytest.raises(ValueError, match="2 MiB"):
        decode_backup_json(payload, max_bytes=MAX_PASTED_BACKUP_BYTES)


def test_fresh_app_can_restore_backup_with_history_disabled(monkeypatch):
    monkeypatch.setenv("CROCHET_HISTORY_MODE", "disabled")
    at = AppTest.from_file(_APP, default_timeout=30).run()
    assert "result" not in at.session_state and "manual_result" not in at.session_state
    assert at.button(key="open_backup_apply").disabled
    at.radio(key="open_backup_source").set_value("粘贴 JSON").run()
    at.text_area(key="open_backup_text").set_value(json.dumps(_backup(), ensure_ascii=False)).run()
    at.button(key="open_backup_apply").click().run()
    assert not at.exception
    restored = at.session_state["result"]
    assert restored["result_id"] != "backup-source"
    assert restored["params"]["parts"][0]["rounds"][2]["notes"] == "FLO((X,V)×6)"
    assert "manual_result" not in at.session_state
    assert any("备份已打开" in message.value for message in at.success)
    at.run()
    assert at.session_state["result"]["result_id"] == restored["result_id"]


def test_failed_import_preserves_current_work_then_valid_import_replaces_only_target():
    old, other = _mock_result("old"), _mock_result("other")
    at = AppTest.from_string(_IMPORTER, default_timeout=30)
    at.session_state["result"] = deepcopy(old)
    at.session_state["manual_result"] = deepcopy(other)
    at.session_state["export_cache_old"] = {"saved": True}
    at.session_state["chk_other_round1"] = True
    at.session_state["import_source_old"] = "粘贴 JSON"
    at.session_state["import_file_old"] = "old upload"
    at.run()
    at.radio(key="open_backup_source").set_value("粘贴 JSON").run()
    invalid = _backup()
    invalid["params"]["parts"][0]["rounds"][2]["notes"] = "FLO((2X,V)×6)"
    at.text_area(key="open_backup_text").set_value(json.dumps(invalid)).run()
    at.button(key="open_backup_apply").click().run()
    assert not at.exception and any("导入失败" in error.value for error in at.error)
    assert at.session_state["result"] == old
    assert at.session_state["export_cache_old"] == {"saved": True}
    at.text_area(key="open_backup_text").set_value(json.dumps(_backup())).run()
    at.button(key="open_backup_apply").click().run()
    assert not at.exception and at.session_state["result"]["result_id"] != "old"
    assert at.session_state["manual_result"] == other and at.session_state["chk_other_round1"]
    for key in ("export_cache_old", "import_source_old", "import_file_old"):
        assert key not in at.session_state


def test_uploaded_json_uses_same_validation_and_is_not_reapplied_on_rerun(monkeypatch):
    import streamlit as st

    uploaded = io.BytesIO(json.dumps(_backup(), ensure_ascii=False).encode("utf-8-sig"))
    uploaded.seek(0, io.SEEK_END)
    monkeypatch.setattr(st, "file_uploader", lambda *args, **kwargs: uploaded)
    at = AppTest.from_string(_IMPORTER, default_timeout=30).run()
    assert "result" not in at.session_state
    at.button(key="open_backup_apply").click().run()
    assert not at.exception
    result_id = at.session_state["result"]["result_id"]
    assert at.session_state["result"]["params"]["parts"][0]["rounds"][2]["notes"] == "FLO((X,V)×6)"
    at.run()
    assert at.session_state["result"]["result_id"] == result_id


def test_oversized_upload_read_is_bounded_and_leaves_current_pattern(monkeypatch):
    import streamlit as st

    from app.ui import backup_import

    monkeypatch.setattr(backup_import, "MAX_BACKUP_BYTES", 64)
    uploaded = io.BytesIO(b"x" * 1000)
    monkeypatch.setattr(st, "file_uploader", lambda *args, **kwargs: uploaded)
    at = AppTest.from_string(_IMPORTER, default_timeout=30)
    original = _mock_result("kept")
    at.session_state["result"] = deepcopy(original)
    at.run()
    assert uploaded.tell() == 65
    at.button(key="open_backup_apply").click().run()
    assert not at.exception and any("上限" in error.value for error in at.error)
    assert at.session_state["result"] == original
