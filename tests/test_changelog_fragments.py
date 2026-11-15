"""Validate bilingual inputs and safe, repeatable release collection."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("changelog_fragments", ROOT / "scripts/changelog_fragments.py")
assert spec is not None and spec.loader is not None
changes = importlib.util.module_from_spec(spec)
spec.loader.exec_module(changes)


@pytest.fixture
def repo(tmp_path):
    directory = tmp_path / "changelog.d"
    directory.mkdir()
    (directory / "README.md").write_text("instructions")
    for name in changes.LOGS.values():
        (tmp_path / name).write_text("# Changelog\n\n## Unreleased\n\nolder content\n\n## 0.1.0\nhistory\n")
    (directory / "123.fixed.json").write_text(json.dumps({"zh": ["修复内容。"], "en": ["Fix behavior."]}))
    return tmp_path


@pytest.mark.parametrize("data", [
    {"zh": ["中文"]}, {"zh": [], "en": ["English"]},
    {"zh": ["中文"], "en": [""]}, {"zh": ["中文"], "en": ["two\nlines"]},
    {"zh": ["中文"], "en": [1]}, {"zh": ["中文"], "en": "text"},
    {"zh": ["中文"], "en": ["English"], "extra": []}, [],
])
def test_reject_invalid_bilingual_fragments(repo, data):
    (repo / "changelog.d/123.fixed.json").write_text(json.dumps(data))
    with pytest.raises(ValueError):
        changes.fragments(repo)


def test_preview_does_not_write_and_collection_preserves_history(repo):
    originals = {name: (repo / name).read_bytes() for name in changes.LOGS.values()}
    preview = changes.collect(repo, "2026-11-15")
    assert all((repo / name).read_bytes() == raw for name, raw in originals.items())
    assert "修复内容。" in preview["CHANGELOG.md"]
    assert "Fix behavior." in preview["CHANGELOG_EN.md"]
    changes.collect(repo, "2026-11-15", write=True)
    assert not (repo / "changelog.d/123.fixed.json").exists()
    for name, raw in originals.items():
        assert (repo / name).read_text().endswith(raw.decode().split("## Unreleased\n", 1)[1])
    saved = {name: (repo / name).read_bytes() for name in originals}
    changes.collect(repo, "2026-11-15", write=True)
    assert all((repo / name).read_bytes() == raw for name, raw in saved.items())


def test_interrupted_bilingual_write_retains_fragments_and_retry_does_not_duplicate(repo, monkeypatch):
    replace = Path.replace

    def interrupt(path, target):
        if target.name == "CHANGELOG_EN.md":
            raise OSError("simulated full disk")
        return replace(path, target)

    with monkeypatch.context() as patch:
        patch.setattr(Path, "replace", interrupt)
        with pytest.raises(OSError, match="full disk"):
            changes.collect(repo, "2026-11-15", write=True)
    assert (repo / "changelog.d/123.fixed.json").exists()
    changes.collect(repo, "2026-11-15", write=True)
    assert (repo / "CHANGELOG.md").read_text().count("修复内容。") == 1
    assert (repo / "CHANGELOG_EN.md").read_text().count("Fix behavior.") == 1


def test_invalid_date_or_second_log_leaves_every_file_untouched(repo):
    raw = (repo / "CHANGELOG.md").read_bytes()
    with pytest.raises(ValueError):
        changes.collect(repo, "2026-13-01", write=True)
    (repo / "CHANGELOG_EN.md").write_text("missing heading")
    with pytest.raises(ValueError):
        changes.collect(repo, "2026-11-15", write=True)
    assert (repo / "CHANGELOG.md").read_bytes() == raw
    assert (repo / "changelog.d/123.fixed.json").exists()


def test_filename_categories_are_validated(repo):
    (repo / "changelog.d/123.fixed.json").rename(repo / "changelog.d/123.unknown.json")
    with pytest.raises(ValueError, match="filename"):
        changes.fragments(repo)
