"""Per-tab state that belongs to the live result but is not a progress record.

Each tab keeps one workspace dict in its session state, bound to the result it
was made for. Reading it for another result starts a fresh one, so export
caches, PDFs, share tokens, notices and pending previews never outlive their
result and need no cleanup. An edit carries the project notes, history title
and recovery notice to the new result; a new generation or import starts over.
"""
from __future__ import annotations

from collections.abc import Mapping, MutableMapping

from app.schemas import ResultData


def workspace_key(slot: str) -> str:
    return f"workspace_{slot}"


def new_workspace(result: ResultData, slot: str, *, notes: str = "", title: str | None = None,
                  recovery_notice: str | None = None) -> dict:
    return {
        "result_id": result.get("result_id") or slot,
        # Carried across edits of the same work.
        "notes": notes,
        "title": (result.get("title") or "") if title is None else title,
        "recovery_notice": recovery_notice,
        # Bound to this exact result.
        "notice": None,
        "success": None,
        "pending_preview": None,
        "export_cache": {},
        "export_trace": {},
        "pdf": None,
        "share": None,
    }


def workspace(result: ResultData, slot: str, state: MutableMapping, *, create: bool = True) -> dict:
    """The tab's workspace for ``result``; one left by another result is replaced.

    With ``create=False`` a missing workspace is returned fresh but not stored,
    so callers can prepare a replacement before mutating the session.
    """
    current = state.get(workspace_key(slot))
    if isinstance(current, dict) and current.get("result_id") == (result.get("result_id") or slot):
        return current
    fresh = new_workspace(result, slot)
    if create:
        state[workspace_key(slot)] = fresh
    return fresh


def carried_workspace(current: Mapping, updated: ResultData, slot: str) -> dict:
    """A workspace for ``updated``, an edit of ``current``'s result, keeping the user's own text."""
    return new_workspace(updated, slot, notes=current["notes"], title=current["title"],
                         recovery_notice=current["recovery_notice"])
