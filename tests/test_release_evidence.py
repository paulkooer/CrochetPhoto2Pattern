"""G1/G2 cite release-evidence.json. The file is not required to equal HEAD."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _binder():
    spec = importlib.util.spec_from_file_location(
        "bind_release_evidence", ROOT / "scripts" / "bind_release_evidence.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _section(text: str, heading: str) -> str:
    start = text.index(heading)
    rest = text[start + len(heading):]
    nxt = rest.find("\n## ")
    return rest if nxt < 0 else rest[:nxt]


def _run(name: str, conclusion: str) -> dict[str, str]:
    return {"name": name, "conclusion": conclusion, "completed_at": "2026-11-06T00:00:00Z"}


def test_builder_accepts_same_tree_audit_and_rejects_a_different_tree():
    bind = _binder()
    push = [_run(name, "success") for names in bind.PUSH_GROUPS.values() for name in names]
    audit = [_run("pip-audit", "success")]
    sha = "a" * 40
    tree = "b" * 40
    document = bind.build_evidence(
        commit=sha, tree=tree, tested_at="2026-11-06", push_runs=push,
        audit_commit="c" * 40, audit_tree=tree, audit_runs=audit)
    assert document["g3_real_photo"] == "blocked"
    assert document["g4_physical_trial"] == "blocked"
    assert document["covers_later_commits"] is False
    assert document["pip_audit"]["on_bound_commit"] is False
    assert document["checks"]["pip_audit"] == "pass"

    try:
        bind.build_evidence(
            commit=sha, tree=tree, tested_at="2026-11-06", push_runs=push,
            audit_commit="c" * 40, audit_tree="d" * 40, audit_runs=audit)
    except ValueError as exc:
        assert "不同" in str(exc)
    else:
        raise AssertionError("不同的树不应记成同一次 pip-audit")


def test_status_gates_cite_the_evidence_file_without_matching_head():
    evidence = json.loads((ROOT / "docs" / "release-evidence.json").read_text(encoding="utf-8"))
    zh = (ROOT / "docs" / "system-status.zh-CN.md").read_text(encoding="utf-8")
    en = (ROOT / "docs" / "system-status.md").read_text(encoding="utf-8")
    assert evidence["g3_real_photo"] == "blocked"
    assert evidence["g4_physical_trial"] == "blocked"
    assert evidence["covers_later_commits"] is False
    assert evidence["python"] == ["3.11", "3.12", "3.13", "3.14"]
    assert set(evidence["checks"]) == {"ci", "browser", "pdf", "pose", "pip_audit"}
    assert all(value == "pass" for value in evidence["checks"].values())
    for text, heading in ((zh, "## 发布门禁"), (en, "## Release gates")):
        gate = _section(text, heading)
        assert "release-evidence.json" in gate
        assert evidence["commit"] in gate
        assert "59f8737" not in gate
        assert "c8039b9" not in gate
    assert evidence["commit"] in zh and evidence["commit"] in en
    assert evidence["pip_audit"]["evidence_commit"] in zh
    assert evidence["pip_audit"]["evidence_commit"] in en
