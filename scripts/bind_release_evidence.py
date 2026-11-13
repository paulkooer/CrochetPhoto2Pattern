"""Write docs/release-evidence.json from one commit's GitHub check runs.

The file binds G1/G2 to that commit. Later commits are not covered; generate a
new receipt only for a selected release candidate. pip-audit is recorded from
another commit only when the trees match: security.yml does not run that job
on every push to main.

Each check name contributes only its latest run. Latest means the greatest
created_at, or started_at when created_at is absent. That run must have
status completed, conclusion success, and head_sha equal to the requested
commit. An unfinished latest run rejects the file instead of reusing an older
success. --commit and --audit-commit are required, so a bare run cannot
rewrite the file onto the previous binding.

--status compares the saved binding with --commit (HEAD by default), without
network access or writing evidence. Exit 1 means that commit is not covered;
this binding check does not evaluate the other release gates.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import cast

REPO = "paulkooer/CrochetPhoto2Pattern"
ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_PATH = ROOT / "docs" / "release-evidence.json"
REQUIRED_PATH = ROOT / ".github" / "required-checks.json"
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
_ACTIONS_RUN = re.compile(r"/actions/runs/(\d+)")

PUSH_GROUPS = {
    "ci": ("docker", "type-check", "test (3.11)", "test (3.12)", "test (3.13)",
           "test (3.14)", "streamlit-floor"),
    "browser": ("browser-smoke",),
    "pdf": ("optional-extras (pdf)",),
    "pose": ("optional-extras (pose)", "pose-unlocked (3.11)", "pose-unlocked (3.12)"),
}
AUDIT_CONTEXT = "pip-audit"


def _text(run: Mapping[str, object], key: str) -> str:
    value = run.get(key)
    return value if isinstance(value, str) else ""


def _is_completed(run: Mapping[str, object]) -> bool:
    return run.get("status") == "completed"


def _clock(run: Mapping[str, object]) -> str:
    """Ordering clock: created_at, then started_at, then completed_at if finished."""
    stamp = _text(run, "created_at") or _text(run, "started_at")
    if stamp:
        return stamp
    if _is_completed(run):
        return _text(run, "completed_at")
    return ""


def _recency(run: Mapping[str, object]) -> tuple[int, str, int]:
    stamp = _clock(run)
    raw_id = run.get("id")
    identity = raw_id if isinstance(raw_id, int) else 0
    if stamp:
        return (1, stamp, identity)
    # No clock and not finished: sort after every stamped run so it cannot lose to an old success.
    return (2, "", identity)


def latest_runs(runs: Sequence[Mapping[str, object]], *, head_sha: str) -> dict[str, Mapping[str, object]]:
    """One run per check name. Refuse when that newest run is not completed."""
    grouped: dict[str, list[Mapping[str, object]]] = {}
    for run in runs:
        name = run.get("name")
        if not isinstance(name, str) or not name:
            continue
        if run.get("head_sha") != head_sha:
            continue
        grouped.setdefault(name, []).append(run)
    chosen: dict[str, Mapping[str, object]] = {}
    for name, group in grouped.items():
        latest = max(group, key=_recency)
        if not _is_completed(latest):
            status = latest.get("status")
            shown = status if isinstance(status, str) and status else "incomplete"
            raise ValueError(f"{name} 的最新运行尚未完成（{shown}），拒绝沿用更早的成功记录")
        conclusion = latest.get("conclusion")
        if not isinstance(conclusion, str) or not conclusion:
            raise ValueError(f"{name} 的最新运行没有结论")
        chosen[name] = latest
    return chosen


def _require_success(conclusions: Mapping[str, str], names: Sequence[str], label: str) -> None:
    missing = [name for name in names if conclusions.get(name) != "success"]
    if missing:
        found = {name: conclusions.get(name, "absent") for name in missing}
        raise ValueError(f"{label} 未全部通过：{found}")


def _completed_stamp(run: Mapping[str, object]) -> str:
    stamp = _text(run, "completed_at")
    if "T" not in stamp:
        raise ValueError(f"{run.get('name')} 已完成但没有完成时间")
    return stamp


def _run_ref(run: Mapping[str, object]) -> dict[str, object]:
    ref: dict[str, object] = {}
    check_run_id = run.get("id")
    if isinstance(check_run_id, int):
        ref["check_run_id"] = check_run_id
    url = _text(run, "details_url") or _text(run, "html_url")
    if url:
        match = _ACTIONS_RUN.search(url)
        if match:
            ref["run_id"] = int(match.group(1))
        ref["url"] = url
    return ref


def build_evidence(*, commit: str, tree: str, commit_date: str,
                   push_runs: Sequence[Mapping[str, object]],
                   audit_commit: str, audit_tree: str,
                   audit_runs: Sequence[Mapping[str, object]]) -> dict[str, object]:
    """Return the evidence document. Refuse a pip-audit pass from a different tree."""
    if len(commit) != 40 or len(tree) != 40 or len(audit_commit) != 40 or len(audit_tree) != 40:
        raise ValueError("commit 与 tree 必须是 40 位 SHA")
    if not _DATE.fullmatch(commit_date):
        raise ValueError("commit_date 必须是 YYYY-MM-DD")
    if audit_tree != tree:
        raise ValueError(f"pip-audit 证据树 {audit_tree} 与绑定树 {tree} 不同")
    push = latest_runs(push_runs, head_sha=commit)
    push_conclusions = {name: str(run["conclusion"]) for name, run in push.items()}
    for group, names in PUSH_GROUPS.items():
        _require_success(push_conclusions, names, group)
    audit = latest_runs(audit_runs, head_sha=audit_commit)
    audit_conclusions = {name: str(run["conclusion"]) for name, run in audit.items()}
    _require_success(audit_conclusions, (AUDIT_CONTEXT,), "pip-audit")
    accepted = [push[name] for names in PUSH_GROUPS.values() for name in names]
    accepted.append(audit[AUDIT_CONTEXT])
    run_refs = {str(run["name"]): ref for run in accepted if (ref := _run_ref(run))}
    return {
        "schema_version": 2,
        "commit": commit,
        "tree": tree,
        "commit_date": commit_date,
        "checks_completed_at": max(_completed_stamp(run) for run in accepted),
        "python": ["3.11", "3.12", "3.13", "3.14"],
        "checks": {
            "ci": "pass",
            "browser": "pass",
            "pdf": "pass",
            "pose": "pass",
            "pip_audit": "pass",
        },
        "push_checks": {name: "pass" for names in PUSH_GROUPS.values() for name in names},
        "pip_audit": {
            "status": "pass",
            "evidence_commit": audit_commit,
            "evidence_tree": audit_tree,
            "on_bound_commit": audit_commit == commit,
            "note": (
                "security.yml 只在改动 pyproject.toml、uv.lock 或该工作流时对 push 运行 "
                "pip-audit。这里的通过来自同一棵树的检查，不一定是绑定提交自己的 push job。"
                if audit_commit != commit else
                "pip-audit 在绑定提交上通过。"
            ),
        },
        "run_refs": run_refs,
        "g3_real_photo": "blocked",
        "g4_physical_trial": "blocked",
        "covers_later_commits": False,
        "note": "此文件只覆盖 commit 字段的那一次远端检查。其后的提交须重新生成。",
    }


def _gh_json(path: str) -> dict[str, object]:
    completed = subprocess.run(
        ["gh", "api", "--hostname", "github.com", path],
        check=True, capture_output=True, text=True,
    )
    payload = json.loads(completed.stdout)
    if not isinstance(payload, dict):
        raise ValueError(f"GitHub API 返回的不是对象：{path}")
    return payload


def _check_runs(sha: str) -> list[dict[str, object]]:
    payload = _gh_json(f"/repos/{REPO}/commits/{sha}/check-runs?per_page=100")
    runs = payload.get("check_runs")
    if not isinstance(runs, list):
        raise ValueError(f"{sha} 没有 check_runs")
    if int(cast("int | str", payload.get("total_count") or 0)) > len(runs):
        raise ValueError(f"{sha} 的检查超过 100 条，脚本需要分页")
    checked: list[dict[str, object]] = []
    for run in runs:
        if not isinstance(run, dict):
            continue
        if run.get("head_sha") != sha:
            raise ValueError(f"{sha} 的检查 {run.get('name')!r} 与 head_sha 不一致")
        checked.append(run)
    return checked


def _commit_facts(sha: str) -> tuple[str, str, str]:
    payload = _gh_json(f"/repos/{REPO}/commits/{sha}")
    full = payload.get("sha")
    commit = payload.get("commit")
    tree = commit.get("tree") if isinstance(commit, dict) else None
    tree_sha = tree.get("sha") if isinstance(tree, dict) else None
    committer = commit.get("committer") if isinstance(commit, dict) else None
    date = committer.get("date") if isinstance(committer, dict) else None
    if not isinstance(full, str) or not isinstance(tree_sha, str) or not isinstance(date, str):
        raise ValueError(f"无法读取 {sha} 的提交、树或日期")
    return full, tree_sha, date[:10]


def binding_status(document: Mapping[str, object], commit: str, tree: str, *,
                   checksum_valid: bool) -> dict[str, object]:
    """Check local receipt consistency and exact Git identity, without remote calls."""
    errors = []
    if not checksum_valid:
        errors.append("receipt checksum missing or mismatched")
    if document.get("schema_version") != 2:
        errors.append("unsupported receipt schema")
    for field in ("commit", "tree"):
        value = document.get(field)
        if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{40}", value):
            errors.append(f"invalid {field}")
    if document.get("covers_later_commits") is not False:
        errors.append("receipt must not cover later commits")
    if document.get("checks") != dict.fromkeys((*PUSH_GROUPS, "pip_audit"), "pass"):
        errors.append("required check groups are not all passing")
    expected_push = dict.fromkeys((name for names in PUSH_GROUPS.values() for name in names), "pass")
    if document.get("push_checks") != expected_push:
        errors.append("required push checks are not all passing")
    audit = document.get("pip_audit")
    if (not isinstance(audit, Mapping) or audit.get("status") != "pass"
            or audit.get("evidence_tree") != document.get("tree")):
        errors.append("pip-audit does not pass on the receipt tree")
    matches = document.get("commit") == commit and document.get("tree") == tree
    return {
        "candidate_commit": commit,
        "candidate_tree": tree,
        "evidence_commit": document.get("commit"),
        "evidence_tree": document.get("tree"),
        "receipt_valid": not errors,
        "validation_errors": errors,
        "covers_candidate_commit": matches and not errors,
        "checks_completed_at": document.get("checks_completed_at"),
        "g3_real_photo": document.get("g3_real_photo", "unknown"),
        "g4_physical_trial": document.get("g4_physical_trial", "unknown"),
    }


def write_evidence(document: Mapping[str, object], path: Path) -> None:
    """Write the receipt and its byte checksum together on deliberate regeneration."""
    raw = (json.dumps(document, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    path.write_bytes(raw)
    path.with_suffix(".sha256").write_text(hashlib.sha256(raw).hexdigest() + "\n", encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--status", action="store_true", help="Read the saved binding without writing it")
    parser.add_argument("--commit", help="Required when writing; defaults to HEAD for --status")
    parser.add_argument("--audit-commit", help="Required when writing")
    parser.add_argument("--output", type=Path, default=EVIDENCE_PATH,
                        help="Evidence file to write, or read with --status")
    args = parser.parse_args(argv)
    if args.status:
        if args.audit_commit:
            parser.error("--audit-commit cannot be used with --status")
        candidate = subprocess.check_output(
            ["git", "rev-parse", "--verify", "--end-of-options", f"{args.commit or 'HEAD'}^{{commit}}"],
            cwd=ROOT, text=True,
        ).strip()
        tree = subprocess.check_output(
            ["git", "rev-parse", "--verify", f"{candidate}^{{tree}}"], cwd=ROOT, text=True,
        ).strip()
        raw = args.output.read_bytes()
        document = json.loads(raw)
        if not isinstance(document, dict):
            parser.error("release receipt must be a JSON object")
        checksum_path = args.output.with_suffix(".sha256")
        checksum_valid = (
            checksum_path.is_file()
            and checksum_path.read_text(encoding="utf-8").strip() == hashlib.sha256(raw).hexdigest()
        )
        status = binding_status(document, candidate, tree, checksum_valid=checksum_valid)
        print(json.dumps(status, ensure_ascii=False, indent=2))
        return 0 if status["covers_candidate_commit"] else 1
    if not args.commit or not args.audit_commit:
        parser.error("--commit and --audit-commit are required when writing release evidence")
    commit, tree, commit_date = _commit_facts(args.commit)
    audit_commit, audit_tree, _audit_date = _commit_facts(args.audit_commit)
    document = build_evidence(
        commit=commit, tree=tree, commit_date=commit_date,
        push_runs=_check_runs(commit),
        audit_commit=audit_commit, audit_tree=audit_tree,
        audit_runs=_check_runs(audit_commit),
    )
    required = json.loads(REQUIRED_PATH.read_text(encoding="utf-8"))
    expected = set(required["contexts"]) - {AUDIT_CONTEXT}
    recorded = set(cast(Mapping[str, str], document["push_checks"]))
    if recorded != expected:
        raise ValueError(
            "push 检查与 .github/required-checks.json 不一致："
            f"多出 {sorted(recorded - expected)}，缺少 {sorted(expected - recorded)}")
    print(f"commit {commit} tree {tree}")
    print(f"audit-commit {audit_commit} tree {audit_tree}")
    write_evidence(document, args.output)
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
