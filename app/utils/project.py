"""Portable work-in-progress envelope, separate from shareable pattern data."""
from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app import software_version
from app.schemas import PatternResult
from app.ui.progress_state import progress_entries

MAX_PROJECT_NOTES = 20_000


class ProjectState(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: Literal["1"] = "1"
    pattern_revision: str = Field(pattern=r"^[0-9a-f]{64}$")
    saved_with_version: str = Field(min_length=1, max_length=80)
    completed_rounds: dict[str, bool] = Field(default_factory=dict)
    notes: str = Field(default="", max_length=MAX_PROJECT_NOTES)


def pattern_revision(result: dict) -> str:
    # Session IDs, progress and personal notes are intentionally outside this hash.
    data = PatternResult.from_result(result).to_backup()
    encoded = json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
                         allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def project_backup(result: dict, progress: dict[str, bool], notes: str = "") -> dict:
    from app.models.validator import require_valid_pattern

    require_valid_pattern(result["params"])
    data = PatternResult.from_result(result).to_backup()
    state = ProjectState(pattern_revision=pattern_revision(data), saved_with_version=software_version(),
                         completed_rounds=progress, notes=notes)
    _validate_progress(result, state.completed_rounds)
    return {**data, "project_state": state.model_dump()}


def _validate_progress(result: dict, progress: dict[str, bool]) -> None:
    remaining = set(progress)
    if any(value is not True for value in progress.values()):
        raise ValueError("工程进度只允许记录已完成的圈次")
    for identity, _, _ in progress_entries(result, "result"):
        remaining.discard(identity)
        if not remaining:
            break
    if remaining:
        raise ValueError("工程进度引用了不存在的部件、实体或圈次")


def read_project_state(data: dict, restored: dict) -> tuple[dict[str, bool], str]:
    if "project_state" not in data:
        return {}, ""  # Original pattern backups remain supported.
    try:
        state = ProjectState.model_validate(data["project_state"])
    except ValidationError as exc:
        raise ValueError("工程记录格式无效，请核对工程版本、备注与进度") from exc
    if state.pattern_revision != pattern_revision(data):
        raise ValueError("工程中的图解版本与进度绑定版本不一致；请恢复原工程，在系统内修改图解后重新保存")
    _validate_progress(restored, state.completed_rounds)
    return state.completed_rounds, state.notes
