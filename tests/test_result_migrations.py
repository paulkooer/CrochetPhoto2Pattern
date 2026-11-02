"""Stored pattern results upgrade through one chain; newer formats are refused."""
import json
from copy import deepcopy
from pathlib import Path

import pytest

from app.schemas import SCHEMA_VERSION
from app.services import migrations
from app.services.migrations import (
    UNVERSIONED,
    UnsupportedFormatError,
    result_format_version,
    upgrade_result,
)
from app.services.result_logic import import_backup
from tests.test_app_smoke import _mock_result

_FIXTURES = sorted(
    path for path in (Path(__file__).parent / "fixtures").rglob("*.json")
    if path.name in ("pattern.json", "project.json", "legacy-project.json"))


def test_every_registered_version_upgrades_to_the_current_one():
    # Bumping SCHEMA_VERSION without a step from the previous version fails here.
    for start in migrations._STEPS:
        version, seen = start, set()
        while version != SCHEMA_VERSION:
            assert version not in seen, f"cycle at {version}"
            seen.add(version)
            assert version in migrations._STEPS, f"no step from {version}"
            version = migrations._STEPS[version][0]


def test_current_records_pass_through_as_a_copy():
    data = {**_mock_result("current"), "schema_version": SCHEMA_VERSION}
    upgraded = upgrade_result(data)
    assert upgraded == data and upgraded is not data


def test_unversioned_records_are_labelled_without_touching_the_input():
    data = _mock_result("legacy")
    before = deepcopy(data)
    upgraded = upgrade_result(data)
    assert result_format_version(data) == UNVERSIONED
    assert upgraded == {**before, "schema_version": SCHEMA_VERSION}
    assert data == before


@pytest.mark.parametrize("version", ["2", "999", UNVERSIONED, "", 1, 1.0, True, ["1"], {"v": "1"}])
def test_newer_unknown_and_malformed_versions_are_refused(version):
    data = {**_mock_result("future"), "schema_version": version}
    with pytest.raises(UnsupportedFormatError, match="不支持的图解格式版本") as caught:
        upgrade_result(data)
    assert caught.value.version == version
    with pytest.raises(UnsupportedFormatError):
        import_backup(data, "future")


def test_steps_run_in_order_until_the_current_version(monkeypatch):
    calls = []

    def step(name):
        def run(data):
            calls.append((name, data.get("schema_version")))
            return {**data, name: True}
        return run

    monkeypatch.setattr(migrations, "SCHEMA_VERSION", "3")
    monkeypatch.setattr(migrations, "_STEPS", {
        UNVERSIONED: ("1", step("to1")), "1": ("2", step("to2")), "2": ("3", step("to3"))})
    assert upgrade_result({"a": 1}) == {"a": 1, "to1": True, "to2": True, "to3": True,
                                        "schema_version": "3"}
    assert calls == [("to1", None), ("to2", "1"), ("to3", "2")]
    calls.clear()
    assert upgrade_result({"schema_version": "2"}) == {"to3": True, "schema_version": "3"}
    assert calls == [("to3", "2")]


@pytest.mark.parametrize("path", _FIXTURES, ids=lambda p: str(p.relative_to(p.parents[1])))
def test_frozen_fixtures_import_the_same_with_or_without_a_version(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    unversioned = {k: v for k, v in data.items() if k != "schema_version"}
    assert import_backup(unversioned, "same") == import_backup(data, "same")


def _token(data: dict) -> str:
    import base64
    import zlib

    blob = json.dumps(data, ensure_ascii=False).encode("utf-8")
    return base64.urlsafe_b64encode(zlib.compress(blob, 9)).decode()


def test_share_links_and_history_refuse_newer_formats(caplog):
    from app.utils import history, share

    small = {"analysis": {"body_type": "标准"}, "structure": {"parts": []}, "params": {"parts": []}}
    assert share.decode_result(_token({**small, "schema_version": "2"})) is None
    decoded = share.decode_result(_token(small))
    assert decoded == {**small, "schema_version": SCHEMA_VERSION}

    rid = history.save_result(_mock_result("stored"), title="stored")
    assert rid is not None and history.load_result(rid) is not None
    with history._connection() as conn:
        blob = json.loads(conn.execute("SELECT blob FROM patterns WHERE rid = ?", (rid,)).fetchone()[0])
        conn.execute("UPDATE patterns SET blob = ? WHERE rid = ?",
                     (json.dumps({**blob, "schema_version": "2"}), rid))
    assert history.load_result(rid) is None
    assert "不支持的图解格式版本" in caplog.text
