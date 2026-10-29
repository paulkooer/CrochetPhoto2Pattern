"""Bounded session-only history of saved measurements, sharing one source pattern."""
from __future__ import annotations

import json
from copy import deepcopy

from app.models.trial_draft import TrialObservationDraft
from app.trials import TrialRecord, decode_trial_json
from app.utils.trial_bundle import TrialBundle, encode_trial_bundle

MAX_TRIAL_SNAPSHOTS = 8
MAX_TRIAL_HISTORY_BYTES = 2 << 20


def _snapshot(bundle: TrialBundle) -> bytes:
    return json.dumps({"record": bundle.record.model_dump(mode="json"),
                       "draft": bundle.draft.model_dump(mode="json") if bundle.draft else None},
                      sort_keys=True, ensure_ascii=False, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def _same_identity(before: TrialBundle, after: TrialBundle) -> None:
    if (before.source != after.source or before.source_revision != after.source_revision
            or (before.record.trial_id, before.record.maker_id, before.record.cohort)
            != (after.record.trial_id, after.record.maker_id, after.record.cohort)):
        raise ValueError("保存历史只能用于同一份试钩及原图解，请重新打开相应试钩包")


def _trim(undo: list[bytes], redo: list[bytes]) -> None:
    while (len(undo) + len(redo) > MAX_TRIAL_SNAPSHOTS
           or sum(map(len, undo)) + sum(map(len, redo)) > MAX_TRIAL_HISTORY_BYTES):
        (undo or redo).pop(0)


def save_trial_version(workspace: dict, updated: TrialBundle) -> dict:
    """Return a new workspace only after validation/serialization succeeds."""
    current = workspace["bundle"]
    _same_identity(current, updated)
    before = _snapshot(current)
    if before == _snapshot(updated):
        return workspace  # No-op saves retain redo and the exact existing download.
    archive = encode_trial_bundle(updated)
    undo = [*workspace.get("undo", []), before]
    redo: list[bytes] = []
    _trim(undo, redo)
    return {**workspace, "bundle": deepcopy(updated), "archive": archive, "undo": undo, "redo": redo}


def restore_trial_version(workspace: dict, direction: str) -> dict:
    if direction not in ("undo", "redo"):
        raise ValueError("invalid trial history direction")
    undo, redo = list(workspace.get("undo", [])), list(workspace.get("redo", []))
    selected, opposite = (undo, redo) if direction == "undo" else (redo, undo)
    if not selected:
        return workspace
    payload = decode_trial_json(selected[-1], max_bytes=MAX_TRIAL_HISTORY_BYTES)
    if not isinstance(payload, dict) or set(payload) != {"record", "draft"}:
        raise ValueError("试钩保存历史格式无效，当前记录保持不变")
    current = workspace["bundle"]
    record = TrialRecord.model_validate(payload["record"])
    draft = (TrialObservationDraft.model_validate(payload["draft"])
             if payload["draft"] is not None else None)
    restored = TrialBundle(current.source, record, current.source_revision, draft)
    _same_identity(current, restored)
    archive = encode_trial_bundle(restored)
    selected.pop()
    opposite.append(_snapshot(current))
    _trim(undo, redo)
    return {**workspace, "bundle": restored, "archive": archive, "undo": undo, "redo": redo}
