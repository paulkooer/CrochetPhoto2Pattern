"""G1/G2 cite release-evidence.json. The file is not required to equal HEAD."""
from __future__ import annotations

import importlib.util
import json
from datetime import date, datetime
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


def _run(name: str, conclusion: str, head: str) -> dict[str, object]:
    return {
        "name": name,
        "status": "completed",
        "conclusion": conclusion,
        "head_sha": head,
        "started_at": "2026-11-06T00:00:00Z",
        "completed_at": "2026-11-06T00:00:00Z",
    }


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
    sha = "a" * 40
    audit_sha = "c" * 40
    push = [_run(name, "success", sha) for names in bind.PUSH_GROUPS.values() for name in names]
    audit = [_run("pip-audit", "success", audit_sha)]
    tree = "b" * 40
    document = bind.build_evidence(
        commit=sha, tree=tree, commit_date="2026-11-06", push_runs=push,
        audit_commit=audit_sha, audit_tree=tree, audit_runs=audit)
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
            audit_commit=audit_sha, audit_tree="d" * 40, audit_runs=audit)
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


def test_success_without_status_or_head_sha_is_refused():
    bind = _binder()
    head = "a" * 40
    concluded = {
        "name": "docker",
        "conclusion": "success",
        "head_sha": head,
        "completed_at": "2026-11-06T03:00:00Z",
    }
    with pytest.raises(ValueError, match="docker 的最新运行尚未完成"):
        _build(bind, _push(bind, head, {"docker": [concluded]}), head=head)

    no_head = _attempt("docker", "success", at="2026-11-06T00:00:00Z", head=head)
    del no_head["head_sha"]
    with pytest.raises(ValueError, match="未全部通过"):
        _build(bind, _push(bind, head, {"docker": [no_head]}), head=head)


def test_commit_arguments_are_required(capsys):
    bind = _binder()
    with pytest.raises(SystemExit) as raised:
        bind.main([])
    assert raised.value.code == 2
    assert "--commit" in capsys.readouterr().err


@pytest.mark.parametrize(("candidate", "expected_code"), [("a" * 40, 0), ("d" * 40, 1)])
def test_status_reads_saved_binding_without_network_or_writes(
    tmp_path, monkeypatch, capsys, candidate, expected_code,
):
    bind = _binder()
    document = _build(bind, _push(bind, "a" * 40))
    evidence_path = tmp_path / "release-evidence.json"
    evidence_path.write_text(json.dumps(document))
    before = evidence_path.read_bytes()
    monkeypatch.setattr(bind, "_gh_json", lambda _path: pytest.fail("status must work offline"))
    monkeypatch.setattr(bind.subprocess, "check_output", lambda *a, **k: candidate + "\n")
    assert bind.main(["--status", "--output", str(evidence_path)]) == expected_code
    status = json.loads(capsys.readouterr().out)
    assert status["covers_candidate_commit"] is (expected_code == 0)
    assert status["candidate_commit"] == candidate
    assert status["evidence_commit"] == document["commit"]
    assert status["g3_real_photo"] == status["g4_physical_trial"] == "blocked"
    assert evidence_path.read_bytes() == before


def test_status_gates_cite_the_evidence_file_without_matching_head():
    evidence = json.loads((ROOT / "docs" / "release-evidence.json").read_text(encoding="utf-8"))
    zh = (ROOT / "docs" / "system-status.zh-CN.md").read_text(encoding="utf-8")
    en = (ROOT / "docs" / "system-status.md").read_text(encoding="utf-8")
    assert evidence["schema_version"] == 2
    assert "tested_at" not in evidence
    assert date.fromisoformat(evidence["commit_date"])
    assert datetime.fromisoformat(evidence["checks_completed_at"])
    assert evidence["g3_real_photo"] == "blocked"
    assert evidence["g4_physical_trial"] == "blocked"
    assert evidence["covers_later_commits"] is False
    assert evidence["python"] == ["3.11", "3.12", "3.13", "3.14"]
    refs = evidence["run_refs"]
    assert set(refs) == set(evidence["push_checks"]) | {"pip-audit"}
    for ref in refs.values():
        assert isinstance(ref["check_run_id"], int)
        assert str(ref["run_id"]) in ref["url"]
    assert set(evidence["checks"]) == {"ci", "browser", "pdf", "pose", "pip_audit"}
    assert all(value == "pass" for value in evidence["checks"].values())
    for text, heading in ((zh, "## 发布门禁"), (en, "## Release gates")):
        gate = _section(text, heading)
        assert "release-evidence.json" in gate
        assert "release-process" in gate
        assert "59f8737" not in gate
        assert "c8039b9" not in gate
    for text in (zh, en):
        assert "--status" in text
        assert evidence["commit"] not in text
        assert evidence["pip_audit"]["evidence_commit"] not in text
