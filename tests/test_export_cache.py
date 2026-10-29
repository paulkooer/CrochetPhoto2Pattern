"""Export reuse must not leak sessions or return stale pattern/provenance text."""
import hashlib
import json
from copy import deepcopy

import pytest
from streamlit.testing.v1 import AppTest

from app.cli import build_parser, run

RENDER = '''
import streamlit as st
from app.ui.result_renderer import render_results
render_results(st.session_state["result"], "result")
'''


def test_repeated_render_reuses_exports_but_content_and_provenance_edits_invalidate(monkeypatch):
    from app.ui import result_renderer
    from app.utils import parade_export

    calls = {"markdown": 0, "parade": 0}
    markdown = result_renderer.export_markdown
    parade = parade_export.export_parade_report

    def md(*args, **kwargs):
        calls["markdown"] += 1
        return markdown(*args, **kwargs)

    def dsl(*args, **kwargs):
        calls["parade"] += 1
        return parade(*args, **kwargs)

    monkeypatch.setattr(result_renderer, "export_markdown", md)
    monkeypatch.setattr(parade_export, "export_parade_report", dsl)
    result = run(build_parser().parse_args(["--mock"]))
    result["result_id"] = "cache-test"
    at = AppTest.from_string(RENDER, default_timeout=30)
    at.session_state["result"] = result
    for _ in range(3):
        at.run()
        assert not at.exception
    assert calls == {"markdown": 1, "parade": 1}

    # Even with an unchanged ID, changing the content must invalidate its export.
    changed = deepcopy(at.session_state["result"])
    changed["params"]["parts"][0]["rounds"][0]["color"] = "蓝色"
    at.session_state["result"] = changed
    at.run()
    assert not at.exception
    assert calls == {"markdown": 2, "parade": 2}
    changed = deepcopy(changed)
    changed["generator_version"] = "recorded-version-change"
    at.session_state["result"] = changed
    at.run()
    assert calls == {"markdown": 3, "parade": 2}
    assert any("recorded-version-change" in m.value for m in at.markdown)

    other = AppTest.from_string(RENDER, default_timeout=30)
    other.session_state["result"] = changed
    other.run()
    assert not other.exception
    assert calls == {"markdown": 4, "parade": 3}


def test_failed_refresh_cannot_reuse_old_value_and_can_retry():
    from app.ui.export_cache import cached_export

    cache = {}
    assert cached_export(cache, "markdown", {"revision": 1}, lambda: "old") == "old"

    def fail():
        raise ValueError("export failed")

    with pytest.raises(ValueError, match="export failed"):
        cached_export(cache, "markdown", {"revision": 2}, fail)
    assert "markdown" not in cache
    assert cached_export(cache, "markdown", {"revision": 2}, lambda: "new") == "new"


@pytest.mark.parametrize("old_format", [None, 2, 3, 4, 6, 7])
def test_legacy_cache_is_rebuilt_after_export_semantics_change(old_format):
    from app.ui.export_cache import cached_export

    source = {"params": {"parts": []}, "export_version": "same-installed-version"}
    old_source = source if old_format is None else {"cache_version": old_format, "source": source}
    legacy_fingerprint = hashlib.sha256(json.dumps(
        old_source, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode()).hexdigest()
    cache = {"parade": {"fingerprint": legacy_fingerprint,
                        "value": {"text": "old uniform sequence"}, "bytes": 32}}
    current = {"text": "explicit ordered sequence with loop qualifiers", "inferred_rounds": 0}
    assert cached_export(cache, "parade", source, lambda: current) == current


def test_cache_bounded_in_utf8_bytes_and_returned_objects_are_isolated(monkeypatch):
    from app.ui import export_cache

    monkeypatch.setattr(export_cache, "MAX_EXPORT_CACHE_BYTES", 30)
    cache = {}
    first = export_cache.cached_export(cache, "a", {}, lambda: {"text": "a"})
    first["text"] = "mutated"
    assert export_cache.cached_export(cache, "a", {}, lambda: {}) == {"text": "a"}
    export_cache.cached_export(cache, "b", {}, lambda: "中文" * 4)
    assert "a" not in cache
    assert sum(entry["bytes"] for entry in cache.values()) <= 30
    value = export_cache.cached_export(cache, "large", {}, lambda: "中文" * 20)
    assert value == "中文" * 20 and "large" not in cache


def test_result_replacement_purges_only_its_export_cache(monkeypatch):
    from types import SimpleNamespace

    from app.ui import result_renderer

    state = {"export_cache_current": {"markdown": "old"}, "export_cache_other": {"markdown": "other"}}
    monkeypatch.setattr(result_renderer, "st", SimpleNamespace(session_state=state))
    result_renderer.purge_result_state({"result_id": "current"})
    assert state == {"export_cache_other": {"markdown": "other"}}
