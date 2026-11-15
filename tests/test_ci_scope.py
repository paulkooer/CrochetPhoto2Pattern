"""Real Git comparisons and workflow guards for documentation-only PRs."""
from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("ci_scope", ROOT / "scripts/ci_scope.py")
assert spec is not None and spec.loader is not None
scope = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scope)


@pytest.mark.parametrize("path", [
    "README.md", "docs/evaluation.md", "docs/archive/old review.md",
    "changelog.d/123.fixed.json", "changelog.d/README.md",
])
def test_documentation_allowlist(path):
    assert scope.documentation_path(path)


@pytest.mark.parametrize("path", [
    "app/main.py", "docs/release-evidence.json", ".github/workflows/ci.yml",
    "tests/test_ci_scope.py", "scripts/browser/package-lock.json", "uv.lock",
    "docs/../app/main.py", "/docs/a.md", "unknown.md", "docs/tool.py",
    "changelog.d/nested/data.json",
])
def test_unknown_or_executable_paths_require_full_validation(path):
    assert not scope.documentation_path(path)


def _git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


def test_three_dot_diff_handles_renames_newlines_and_code_deleted_into_docs(tmp_path):
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "test@example.invalid")
    _git(tmp_path, "config", "user.name", "Scope test")
    (tmp_path / "app").mkdir()
    (tmp_path / "app/old.py").write_text("print('preserved')\n")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-qm", "base")
    base = _git(tmp_path, "rev-parse", "HEAD")
    (tmp_path / "docs").mkdir()
    (tmp_path / "app/old.py").rename(tmp_path / "docs/new\nname.md")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "rename")
    head = _git(tmp_path, "rev-parse", "HEAD")
    event = {"pull_request": {"base": {"sha": base}, "head": {"sha": head}}}
    assert scope.changed_paths(tmp_path, base, head) == ["app/old.py", "docs/new\nname.md"]
    assert scope.select_scope("pull_request", event, tmp_path)[0] is True
    (tmp_path / "docs/another.md").write_text("docs only\n")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-qm", "documentation")
    event["pull_request"]["base"]["sha"] = head
    event["pull_request"]["head"]["sha"] = _git(tmp_path, "rev-parse", "HEAD")
    assert scope.select_scope("pull_request", event, tmp_path)[0] is False
    assert scope.select_scope("push", event, tmp_path)[0] is True
    event["pull_request"]["head"]["sha"] = head
    assert scope.select_scope("pull_request", event, tmp_path)[0] is True  # empty diff


@pytest.mark.parametrize("event", [{}, {"pull_request": None},
                                          {"pull_request": {"base": {"sha": "--help"}}}])
def test_incomplete_event_fails_closed(event, tmp_path):
    assert scope.select_scope("pull_request", event, tmp_path)[0] is True


@pytest.mark.parametrize("result,decision,ok", [
    ("success", "false", True), ("success", "true", True),
    ("failure", "false", False), ("skipped", "false", False),
    ("success", "", False), ("success", "typo", False),
])
def test_required_job_guard_rejects_unavailable_scope(result, decision, ok):
    run = subprocess.run([sys.executable, str(ROOT / "scripts/ci_scope.py"), "--guard"],
                         env={**os.environ, "SCOPE_RESULT": result, "RUN_FULL": decision},
                         capture_output=True, text=True)
    assert (run.returncode == 0) is ok
