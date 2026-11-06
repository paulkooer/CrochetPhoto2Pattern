"""Write docs/release-evidence.json from one commit's GitHub check runs.

The file binds G1/G2 to that commit. Later commits are not covered until this
script is run again. pip-audit is recorded from another commit only when the
trees match: security.yml does not run that job on every push to main.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

REPO = "paulkooer/CrochetPhoto2Pattern"
ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_PATH = ROOT / "docs" / "release-evidence.json"
REQUIRED_PATH = ROOT / ".github" / "required-checks.json"

PUSH_GROUPS = {
    "ci": ("docker", "type-check", "test (3.11)", "test (3.12)", "test (3.13)",
           "test (3.14)", "streamlit-floor"),
    "browser": ("browser-smoke",),
    "pdf": ("optional-extras (pdf)",),
    "pose": ("optional-extras (pose)", "pose-unlocked (3.11)", "pose-unlocked (3.12)"),
}
AUDIT_CONTEXT = "pip-audit"


def latest_conclusions(runs: Sequence[Mapping[str, object]]) -> dict[str, str]:
    """One conclusion per check name. A later completed_at replaces an earlier one."""
    chosen: dict[str, tuple[str, str]] = {}
    for run in runs:
        name = run.get("name")
        conclusion = run.get("conclusion")
        if not isinstance(name, str) or not isinstance(conclusion, str) or not conclusion:
            continue
        completed = run.get("completed_at")
        stamp = completed if isinstance(completed, str) else ""
        previous = chosen.get(name)
        if previous is None or stamp >= previous[0]:
            chosen[name] = (stamp, conclusion)
    return {name: conclusion for name, (_stamp, conclusion) in chosen.items()}


def _require_success(conclusions: Mapping[str, str], names: Sequence[str], label: str) -> None:
    missing = [name for name in names if conclusions.get(name) != "success"]
    if missing:
        found = {name: conclusions.get(name, "absent") for name in missing}
        raise ValueError(f"{label} 未全部通过：{found}")


def build_evidence(*, commit: str, tree: str, tested_at: str,
                   push_runs: Sequence[Mapping[str, object]],
                   audit_commit: str, audit_tree: str,
                   audit_runs: Sequence[Mapping[str, object]]) -> dict[str, object]:
    """Return the evidence document. Refuse a pip-audit pass from a different tree."""
    if len(commit) != 40 or len(tree) != 40 or len(audit_commit) != 40 or len(audit_tree) != 40:
        raise ValueError("commit 与 tree 必须是 40 位 SHA")
    if audit_tree != tree:
        raise ValueError(f"pip-audit 证据树 {audit_tree} 与绑定树 {tree} 不同")
    push = latest_conclusions(push_runs)
    for group, names in PUSH_GROUPS.items():
        _require_success(push, names, group)
    audit = latest_conclusions(audit_runs)
    _require_success(audit, (AUDIT_CONTEXT,), "pip-audit")
    if not tested_at:
        raise ValueError("tested_at 不能为空")
    return {
        "schema_version": 1,
        "commit": commit,
        "tree": tree,
        "tested_at": tested_at,
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
    if int(payload.get("total_count") or 0) > len(runs):
        raise ValueError(f"{sha} 的检查超过 100 条，脚本需要分页")
    return [run for run in runs if isinstance(run, dict)]


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


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--commit", default="ba65b8db92c12cab80f4e157a0b11c47bf64763c")
    parser.add_argument("--audit-commit", default="9063635b2411e59d3b3647710d06fa792146c6ba")
    parser.add_argument("--output", type=Path, default=EVIDENCE_PATH)
    args = parser.parse_args(argv)
    commit, tree, tested_at = _commit_facts(args.commit)
    audit_commit, audit_tree, _audit_date = _commit_facts(args.audit_commit)
    document = build_evidence(
        commit=commit, tree=tree, tested_at=tested_at,
        push_runs=_check_runs(commit),
        audit_commit=audit_commit, audit_tree=audit_tree,
        audit_runs=_check_runs(audit_commit),
    )
    required = json.loads(REQUIRED_PATH.read_text(encoding="utf-8"))
    expected = set(required["contexts"]) - {AUDIT_CONTEXT}
    recorded = set(document["push_checks"])
    if recorded != expected:
        raise ValueError(
            "push 检查与 .github/required-checks.json 不一致："
            f"多出 {sorted(recorded - expected)}，缺少 {sorted(expected - recorded)}")
    args.output.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {args.output} for {commit}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
