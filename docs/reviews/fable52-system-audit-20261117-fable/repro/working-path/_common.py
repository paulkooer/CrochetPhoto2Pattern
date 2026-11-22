"""Shared helpers for the working-path audit probes (read-only against the audited tree)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

REPO = Path("<repo>")
SCRATCH = REPO / "eval_outputs/fable52-system-audit-20261117-fable-review/repro/working-path"
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")

import app  # noqa: E402

assert app.__file__.startswith(str(REPO) + "/app/"), app.__file__

import app.models.working_path as wp  # noqa: E402

assert wp.__file__.startswith(str(REPO) + "/app/"), wp.__file__

from app.models.working_path import WorkingPath, compile_working_path  # noqa: E402


def span(edge, first, last=None, *, face="top", direction="forward"):
    return {"edge": edge, "first": first, "last": first if last is None else last,
            "face": face, "direction": direction}


def work(edge, first, last=None, *, face="top", direction="forward", stitch="sc", loop="both",
         disposition="working"):
    return {"kind": "work", "source": span(edge, first, last, face=face, direction=direction),
            "stitch": stitch, "loop": loop, "disposition": disposition}


def route(id_, ops, expected, **extra):
    data = {"kind": "route", "id": id_, "label": extra.pop("label", id_), "operations": ops,
            "expected_sites": expected}
    data.update(extra)
    return data


def plan(steps, *, existing=(), final=(), **extra):
    data = {"schema_version": "working-path-v2", "title": extra.pop("title", "probe"),
            "existing_edges": [{"id": k, "count": v} for k, v in existing],
            "steps": steps, "final_edges": list(final)}
    data.update(extra)
    return data


def attempt(data):
    """Return ('ACCEPT', PathResult) or ('REJECT', message) via the same JSON path as the CLI/UI."""
    import json

    from app.working_paths import read_path

    try:
        model = read_path(json.dumps(data, ensure_ascii=False).encode())
        return "ACCEPT", compile_working_path(model)
    except ValueError as exc:
        text = str(exc)
        return "REJECT", text.splitlines()[0] if "validation error" not in text else " | ".join(
            line.strip() for line in text.splitlines()[:4])


def show(name, data, *, expect=None):
    status, value = attempt(data)
    detail = value if status == "REJECT" else (
        f"created={value.created_sites} consumed={value.consumed_sites} "
        f"final={ {k: len(v) for k, v in value.final_edges.items()} }")
    flag = "" if expect is None else ("  [as expected]" if status == expect else "  [UNEXPECTED]")
    print(f"{name}: {status}{flag} :: {detail}")
    return status, value


def pdf_paragraphs(exporter, model):
    """Run a PDF exporter and return (pdf_bytes, [plain paragraph texts in story order])."""
    from reportlab.platypus import Paragraph

    captured = []
    init = Paragraph.__init__

    def record(self, text, *args, **kwargs):
        init(self, text, *args, **kwargs)
        if isinstance(text, str):
            captured.append(self.getPlainText())

    Paragraph.__init__ = record
    try:
        data = exporter(model)
    finally:
        Paragraph.__init__ = init
    return data, captured
