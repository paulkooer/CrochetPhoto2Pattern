"""Conservative PR scope selection; no dependencies, network, or changed-file limit."""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from pathlib import Path, PurePosixPath

ROOT_DOCS = {
    "README.md", "README_EN.md", "CHANGELOG.md", "CHANGELOG_EN.md",
    "CONTRIBUTING.md", "CONTRIBUTING_EN.md", "SECURITY.md", "CODE_OF_CONDUCT.md",
    "THIRD_PARTY_CONTENT.md", "THIRD_PARTY_CONTENT_EN.md",
}


def documentation_path(path: str) -> bool:
    parsed = PurePosixPath(path)
    if parsed.is_absolute() or ".." in parsed.parts:
        return False
    return (
        path in ROOT_DOCS
        or (path.startswith("docs/") and path.endswith(".md"))
        or (path.startswith("changelog.d/") and len(parsed.parts) == 2
            and parsed.suffix in {".json", ".md"})
    )


def changed_paths(repo: Path, base: str, head: str) -> list[str]:
    for sha in (base, head):
        if not re.fullmatch(r"[0-9a-f]{40}", sha):
            raise ValueError("missing or invalid PR SHA")
    diff = subprocess.run(
        ["git", "diff", "--name-status", "-z", "--find-renames", "--no-ext-diff",
         f"{base}...{head}", "--"], cwd=repo, check=True, capture_output=True,
    ).stdout.decode("utf-8", errors="strict")
    fields = iter(diff.removesuffix("\0").split("\0") if diff else [])
    paths = []
    for status in fields:
        if not re.fullmatch(r"[ACDMRTUXB][0-9]*", status):
            raise ValueError(f"unrecognized diff status: {status!r}")
        # Both sides of a rename/copy count, including source code renamed to Markdown.
        for _ in range(2 if status[0] in "RC" else 1):
            path = next(fields, "")
            if not path:
                raise ValueError("incomplete diff")
            paths.append(path)
    return paths


def select_scope(event_name: str, event: dict, repo: Path) -> tuple[bool, str]:
    if event_name != "pull_request":
        return True, "push, schedule and manual runs always validate fully"
    try:
        pr = event["pull_request"]
        paths = changed_paths(repo, pr["base"]["sha"], pr["head"]["sha"])
    except (KeyError, TypeError, ValueError, OSError, subprocess.CalledProcessError) as exc:
        return True, f"scope unavailable; full validation required ({type(exc).__name__})"
    if paths and all(documentation_path(path) for path in paths):
        return False, f"documentation-only PR ({len(paths)} changed paths)"
    return True, "runtime, workflow, test, data, unknown path or empty diff"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--guard", action="store_true")
    args = parser.parse_args()
    if args.guard:
        if os.environ.get("SCOPE_RESULT") != "success" or os.environ.get("RUN_FULL") not in {"true", "false"}:
            parser.error("scope job did not complete with a valid decision")
        print("Full validation" if os.environ["RUN_FULL"] == "true" else
              "Documentation check passed; runtime checks intentionally omitted")
        return 0
    try:
        event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text(encoding="utf-8"))
        full, reason = select_scope(os.environ.get("GITHUB_EVENT_NAME", ""), event, Path.cwd())
    except (KeyError, ValueError, OSError):
        full, reason = True, "event unavailable; full validation required"
    print(reason)
    with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8") as output:
        output.write(f"run_full={str(full).lower()}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
