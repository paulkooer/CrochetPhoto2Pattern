"""G1/G2 cite release-evidence.json. The file is not required to equal HEAD."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

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


def _attempt(name: str, conclusion: str | None, *, at: str, head: str,
             status: str = "completed", created_at: str | None = None,
             **extra: object) -> dict[str, object]:
    run: dict[str, object] = {
        "name": name,
        "status": status,
        "conclusion": conclusion if status == "completed" else None,
        "started_at": at,
        "completed_at": at if status == "completed" else None,
        "head_sha": head,
    }
    if created_at is not None:
        run["created_at"] = created_at
    run.update(extra)
    return run


def _push(bind, head: str, overrides: dict[str, list[dict[str, object]]] | None = None,
          ) -> list[dict[str, object]]:
    overrides = overrides or {}
    runs: list[dict[str, object]] = []
    for names in bind.PUSH_GROUPS.values():
        for name in names:
            default = _attempt(name, "success", at="2026-11-06T00:00:00Z", head=head)
            runs.extend(overrides.get(name) or [default])
    return runs


def _audit(head: str) -> list[dict[str, object]]:
    return [_attempt("pip-audit", "success", at="2026-11-06T00:00:00Z", head=head)]


def _build(bind, push: list[dict[str, object]], *, head: str = "a" * 40, audit_head: str = "c" * 40):
    return bind.build_evidence(
        commit=head, tree="b" * 40, commit_date="2026-11-06", push_runs=push,
        audit_commit=audit_head, audit_tree="b" * 40, audit_runs=_audit(audit_head))


def test_builder_accepts_same_tree_audit_and_rejects_a_different_tree():
    bind = _binder()
    push = [_run(name, "success") for names in bind.PUSH_GROUPS.values() for name in names]
    audit = [_run("pip-audit", "success")]
    sha = "a" * 40
    tree = "b" * 40
    document = bind.build_evidence(
        commit=sha, tree=tree, commit_date="2026-11-06", push_runs=push,
        audit_commit="c" * 40, audit_tree=tree, audit_runs=audit)
    assert document["schema_version"] == 2
    assert document["commit_date"] == "2026-11-06"
    assert document["checks_completed_at"] == "2026-11-06T00:00:00Z"
    assert document["run_refs"] == {}
    assert "tested_at" not in document
    assert document["g3_real_photo"] == "blocked"
    assert document["g4_physical_trial"] == "blocked"
    assert document["covers_later_commits"] is False
    assert document["pip_audit"]["on_bound_commit"] is False
    assert document["checks"]["pip_audit"] == "pass"

    try:
        bind.build_evidence(
            commit=sha, tree=tree, commit_date="2026-11-06", push_runs=push,
            audit_commit="c" * 40, audit_tree="d" * 40, audit_runs=audit)
    except ValueError as exc:
        assert "不同" in str(exc)
    else:
        raise AssertionError("不同的树不应记成同一次 pip-audit")


def test_old_success_and_newer_incomplete_run_is_refused():
    bind = _binder()
    head = "a" * 40
    # created_at decides. The success starts later, but the unfinished run was created later.
    old = _attempt("docker", "success", at="2026-11-06T02:00:00Z", head=head,
                   created_at="2026-11-06T00:00:00Z")
    new = _attempt("docker", None, at="2026-11-06T00:30:00Z", head=head,
                   status="in_progress", created_at="2026-11-06T01:00:00Z")
    push = _push(bind, head, {"docker": [old, new]})
    with pytest.raises(ValueError, match="docker 的最新运行尚未完成（in_progress）"):
        _build(bind, push, head=head)

    untimed = {"name": "type-check", "status": "queued", "conclusion": None, "head_sha": head}
    with pytest.raises(ValueError, match="type-check 的最新运行尚未完成（queued）"):
        _build(bind, [*_push(bind, head), untimed], head=head)


def test_old_success_and_newer_failure_is_refused():
    bind = _binder()
    head = "a" * 40
    old = _attempt("docker", "success", at="2026-11-06T00:00:00Z", head=head,
                   created_at="2026-11-06T00:00:00Z")
    failed = _attempt("docker", "failure", at="2026-11-06T01:00:00Z", head=head,
                      created_at="2026-11-06T01:00:00Z")
    foreign = _attempt("docker", "success", at="2026-11-06T03:00:00Z", head="e" * 40,
                       created_at="2026-11-06T03:00:00Z")
    push = _push(bind, head, {"docker": [old, failed, foreign]})
    with pytest.raises(ValueError, match="未全部通过"):
        _build(bind, push, head=head)


def test_latest_success_is_accepted():
    bind = _binder()
    head = "a" * 40
    old = _attempt("docker", "failure", at="2026-11-06T00:00:00Z", head=head,
                   created_at="2026-11-06T00:00:00Z")
    done = "2026-11-06T01:00:00Z"
    url = "https://github.com/paulkooer/CrochetPhoto2Pattern/actions/runs/421/job/99"
    new = _attempt("docker", "success", at=done, head=head, created_at=done, id=99, details_url=url)
    foreign = _attempt("docker", None, at="2026-11-06T02:00:00Z", head="e" * 40,
                       status="in_progress", created_at="2026-11-06T02:00:00Z")
    document = _build(bind, _push(bind, head, {"docker": [old, new, foreign]}), head=head)
    assert document["checks"]["ci"] == "pass"
    assert document["checks_completed_at"] == done
    assert document["run_refs"]["docker"] == {"check_run_id": 99, "run_id": 421, "url": url}


def test_status_gates_cite_the_evidence_file_without_matching_head():
    evidence = json.loads((ROOT / "docs" / "release-evidence.json").read_text(encoding="utf-8"))
    zh = (ROOT / "docs" / "system-status.zh-CN.md").read_text(encoding="utf-8")
    en = (ROOT / "docs" / "system-status.md").read_text(encoding="utf-8")
    assert evidence["schema_version"] == 2
    assert "tested_at" not in evidence
    assert evidence["commit_date"] == "2026-11-06"
    assert evidence["checks_completed_at"] == "2026-11-06T06:06:33Z"
    assert evidence["g3_real_photo"] == "blocked"
    assert evidence["g4_physical_trial"] == "blocked"
    assert evidence["covers_later_commits"] is False
    assert evidence["python"] == ["3.11", "3.12", "3.13", "3.14"]
    refs = evidence["run_refs"]
    assert set(refs) == set(evidence["push_checks"]) | {"pip-audit"}
    assert refs["pip-audit"]["check_run_id"] == 127735998256
    assert refs["pip-audit"]["run_id"] == 42170206948
    for ref in refs.values():
        assert isinstance(ref["check_run_id"], int)
        assert str(ref["run_id"]) in ref["url"]
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
