"""Portable work-in-progress envelope, separate from shareable pattern data."""
from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app import software_version
from app.schemas import SCHEMA_VERSION, PatternResult, ResultData, strip_photo_derived
from app.services.progress_state import (
    ambiguous_legacy_progress,
    has_legacy_identity_collision,
    progress_entries,
)

MAX_PROJECT_NOTES = 20_000


class ProjectState(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: Literal["1"] = "1"
    pattern_revision: str = Field(pattern=r"^[0-9a-f]{64}$")
    saved_with_version: str = Field(min_length=1, max_length=80)
    completed_rounds: dict[str, bool] = Field(default_factory=dict)
    notes: str = Field(default="", max_length=MAX_PROJECT_NOTES)
    progress_identity_version: Literal["2"] | None = None


class AmbiguousProjectProgressError(ValueError):
    """A legacy completed-round key could belong to more than one copy."""

    def __init__(self, count: int) -> None:
        self.count = count
        super().__init__(f"旧工程中有 {count} 个完成圈次无法区分属于哪份实体，请按实物核对")


def _revision_hash(data: dict) -> str:
    encoded = json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
                         allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _revision_backup(result: Mapping[str, Any], *, canonical: bool = True) -> dict:
    """Keep unchanged old patterns bound across optional-field migrations."""
    source_version = result.get("schema_version")
    if source_version is not None and source_version != SCHEMA_VERSION:
        from app.services.migrations import upgrade_result

        backup = PatternResult.from_result(upgrade_result(result)).to_backup()
        backup["schema_version"] = source_version
    else:
        backup = PatternResult.from_result(result).to_backup()
    # Both migrations leave old data unchanged. New optional fields still
    # participate in the hash when present.
    if canonical and backup.get("schema_version") in ("1", "2", "3"):
        backup["schema_version"] = "1"
    return backup


def pattern_revision(result: Mapping[str, Any]) -> str:
    # Session IDs, progress and personal notes are intentionally outside this hash.
    # 照片衍生数据（preview/mask_review）同样剔除：图解身份不应随照片缩略图而变。
    return _revision_hash(strip_photo_derived(_revision_backup(result)))


def _legacy_pattern_revision(result: Mapping[str, Any]) -> str:
    # 剔除照片衍生数据之前保存的工程（同为 0.2.0b2，无法按版本号区分）把
    # preview/mask_review 计入了哈希；读取时仍须认可，否则照片结果的旧工程无法恢复进度。
    return _revision_hash(_revision_backup(result))


def project_backup(result: ResultData, progress: dict[str, bool], notes: str = "") -> dict:
    from app.models.validator import require_valid_pattern
    from app.services.color_identity import require_aligned_copy_colors

    require_valid_pattern(result["params"])
    require_aligned_copy_colors(result)
    # 工程文件可能被转发：剔除缩略图与画笔掩码，其他分析摘要仍可能保留。
    data = strip_photo_derived(PatternResult.from_result(result).to_backup())
    state = ProjectState(pattern_revision=pattern_revision(data), saved_with_version=software_version(),
                         completed_rounds=progress, notes=notes,
                         progress_identity_version="2" if has_legacy_identity_collision(result) else None)
    _validate_progress(result, state.completed_rounds)
    return {**data, "project_state": state.model_dump(exclude_none=True)}


def _validate_progress(result: ResultData, progress: dict[str, bool]) -> None:
    remaining = set(progress)
    if any(value is not True for value in progress.values()):
        raise ValueError("工程进度只允许记录已完成的圈次")
    for identity, _, _ in progress_entries(result, "result"):
        remaining.discard(identity)
        if not remaining:
            break
    if remaining:
        raise ValueError("工程进度引用了不存在的部件、实体或圈次")


def read_project_state(data: dict, restored: ResultData, *,
                       clear_legacy_ambiguity: bool = False) -> tuple[dict[str, bool], str]:
    if "project_state" not in data:
        return {}, ""  # Original pattern backups remain supported.
    try:
        state = ProjectState.model_validate(data["project_state"])
    except ValidationError as exc:
        raise ValueError("工程记录格式无效，请核对工程版本、备注与进度") from exc
    revisions = {pattern_revision(data), _legacy_pattern_revision(data)}
    source = _revision_backup(data, canonical=False)
    revisions.update((_revision_hash(source), _revision_hash(strip_photo_derived(source))))
    if "schema_version" not in data:
        # Early unversioned project files were hashed by the version-1 writer,
        # which supplied schema_version=1 while constructing its backup.
        legacy = _revision_backup(data)
        legacy["schema_version"] = "1"
        revisions.update((_revision_hash(legacy), _revision_hash(strip_photo_derived(legacy))))
    if state.pattern_revision not in revisions:
        raise ValueError("工程中的图解版本与进度绑定版本不一致；请恢复原工程，在系统内修改图解后重新保存")
    _validate_progress(restored, state.completed_rounds)
    ambiguous = (ambiguous_legacy_progress(restored, state.completed_rounds)
                 if state.progress_identity_version is None else set())
    if ambiguous and not clear_legacy_ambiguity:
        raise AmbiguousProjectProgressError(len(ambiguous))
    progress = {key: value for key, value in state.completed_rounds.items() if key not in ambiguous}
    return progress, state.notes
