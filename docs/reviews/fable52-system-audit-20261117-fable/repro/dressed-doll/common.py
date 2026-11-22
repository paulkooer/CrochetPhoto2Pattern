"""Shared helpers for the dressed-doll audit reproductions (read-only against the repo).

Every script asserts that `app` is imported from the audited checkout, never from
another tree shadowed by the editable install.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

REPO = Path("<repo>")
SCRATCH = REPO / "eval_outputs/fable52-system-audit-20261117-fable-review/repro/dressed-doll"
PACKAGED = REPO / "eval_outputs/fable52-system-audit-20261117/examples/generated"
EXPECTED_SHA = "6c88b7df5d53c18d4c8190288419faeb02cc1b13"

os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
sys.dont_write_bytecode = True
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


def assert_repo() -> None:
    import app

    path = str(Path(app.__file__).resolve())
    assert path.startswith(str(REPO) + "/app/"), f"app imported from unexpected tree: {path}"
    import app.models.dressed_doll.planner as planner

    assert str(Path(planner.__file__).resolve()).startswith(str(REPO) + "/app/"), planner.__file__
    head = (REPO / ".git/HEAD").read_text().strip()
    if head.startswith("ref:"):
        ref = REPO / ".git" / head.split(" ", 1)[1]
        sha = ref.read_text().strip() if ref.exists() else "(packed ref)"
    else:
        sha = head
    print(f"[env] python {sys.version.split()[0]} | app={path} | HEAD={sha}")
    if sha != "(packed ref)":
        assert sha == EXPECTED_SHA, f"unexpected HEAD {sha}"
