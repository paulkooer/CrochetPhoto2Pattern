"""Required main checks must name jobs that the workflows actually define."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_JOB_LINE = re.compile(r"^  ([a-z0-9-]+):\s*$")


def _job_ids() -> set[str]:
    found: set[str] = set()
    for path in (ROOT / ".github" / "workflows").glob("*.yml"):
        body = path.read_text(encoding="utf-8").split("\njobs:\n", 1)[1]
        for line in body.splitlines():
            match = _JOB_LINE.fullmatch(line.rstrip())
            if match:
                found.add(match.group(1))
    return found


def test_every_required_context_is_a_workflow_job():
    required = json.loads((ROOT / ".github" / "required-checks.json").read_text(encoding="utf-8"))
    contexts = required["contexts"]
    assert len(contexts) == len(set(contexts)) == 13
    jobs = _job_ids()
    missing = [
        context for context in contexts
        if not any(context == job or context.startswith(f"{job} (") for job in jobs)
    ]
    assert missing == []
    for context in (
        "browser-smoke", "streamlit-floor", "pose-unlocked (3.11)",
        "pose-unlocked (3.12)", "pip-audit",
    ):
        assert context in contexts
