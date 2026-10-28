"""Portable trial records with an immutable, validated source-pattern snapshot."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from io import BytesIO
from typing import Literal
from zipfile import ZIP_DEFLATED, BadZipFile, ZipFile

from app.models.trial_draft import TrialDraftState, TrialObservationDraft
from app.schemas import PatternResult
from app.trials import (
    MAX_PATTERN_BYTES,
    MAX_TRIAL_BYTES,
    TrialRecord,
    create_trial_draft_from_bytes,
    decode_trial_json,
)
from app.ui.result_logic import import_backup, regenerate_with_gauge
from app.utils.backup import decode_backup_json
from app.utils.numbers import finite_float
from app.utils.project import pattern_revision

MAX_TRIAL_DRAFT_BYTES = MAX_TRIAL_BYTES
MAX_TRIAL_BUNDLE_BYTES = MAX_PATTERN_BYTES + MAX_TRIAL_BYTES + MAX_TRIAL_DRAFT_BYTES + (64 << 10)


@dataclass(frozen=True)
class TrialBundle:
    source: bytes
    record: TrialRecord
    source_revision: str
    draft: TrialObservationDraft | None = None


def _checked_bundle(source: bytes, record: TrialRecord,
                    draft: TrialObservationDraft | None = None) -> TrialBundle:
    record = TrialRecord.model_validate(record.model_dump())
    if draft is not None:
        draft = TrialObservationDraft.model_validate(draft.model_dump())
        if record.status != "draft":
            raise ValueError("完成记录不能同时包含未完成测量草稿")
    payload = decode_backup_json(source)
    # Apply the same complete-pattern checks as opening a backup, but keep the
    # original bytes: normalizing an import must never silently change its hash.
    import_backup(payload, "trial-check")
    expected = create_trial_draft_from_bytes(source, trial_id=record.trial_id,
                                             maker_id=record.maker_id, cohort=record.cohort)["pattern"]
    # Producer version may differ from the version restoring this bundle.
    expected["application_version"] = record.pattern.application_version
    if expected != record.pattern.model_dump(mode="json"):
        raise ValueError("试钩记录与原图解不匹配，请恢复同一次下载的记录包")
    return TrialBundle(source, record, pattern_revision(payload), draft)


def create_trial_bundle(result: dict, *, trial_id: str, maker_id: str,
                        cohort: Literal["calibration", "validation"] = "calibration") -> TrialBundle:
    source = json.dumps(PatternResult.from_result(result).to_backup(), ensure_ascii=False,
                        sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    record = TrialRecord.model_validate(create_trial_draft_from_bytes(
        source, trial_id=trial_id, maker_id=maker_id, cohort=cohort))
    return _checked_bundle(source, record)


def update_trial_bundle(bundle: TrialBundle, *, swatch: dict,
                        observation: dict | None, completed: bool | None = None) -> TrialBundle:
    # Existing callers infer completion from observation presence. The editor
    # explicitly chooses draft/completed; neither route silently drops saved work.
    is_completed = observation is not None if completed is None else completed
    draft = None
    if not is_completed:
        if observation is None:
            previous = bundle.draft or bundle.record.observation
            observation = previous.model_dump() if previous is not None else None
        if observation is not None:
            draft = TrialObservationDraft.model_validate(observation)
            if not draft.model_dump(exclude_defaults=True):
                draft = None
    payload = bundle.record.model_dump(mode="json")
    payload.update(swatch=swatch, observation=observation if is_completed else None,
                   status="completed" if is_completed else "draft")
    return _checked_bundle(bundle.source, TrialRecord.model_validate(payload), draft)


def trial_gauge_candidate(bundle: TrialBundle, result: dict) -> dict:
    """Use only a saved measured swatch, and only against the trial's source."""
    checked = _checked_bundle(bundle.source, bundle.record, bundle.draft)
    if not checked.record.swatch.measured:
        raise ValueError("请先保存实测小样并确认已测量，再预览密度重算")
    if pattern_revision(result) != checked.source_revision:
        raise ValueError("当前图解与试钩原图解不同，请先打开原试钩包再重算")
    swatch = checked.record.swatch
    return regenerate_with_gauge(result, swatch.stitches_per_10cm, swatch.rows_per_10cm)


def trial_comparison_rows(bundle: TrialBundle) -> list[dict[str, str]]:
    """Compare saved measurements; full-project timing has no baseline-time ratio."""
    record = bundle.record
    rows = []

    def add(label: str, reference: float | None, measured: float | None, note: str = "") -> None:
        delta = (f"{(measured / reference - 1) * 100:+.1f}%"
                 if reference and measured is not None and not note else "—")
        rows.append({"项目": label, "原图解目标 / 估算": f"{reference:g}" if reference else "未记录",
                     "已保存实测": f"{measured:g}" if measured is not None else "未确认测量",
                     "差异": delta, "说明": note})

    swatch = record.swatch
    add("10 cm 针数", record.pattern.gauge.stitches_per_10cm,
        swatch.stitches_per_10cm if swatch.measured else None)
    add("10 cm 行数", record.pattern.gauge.rows_per_10cm,
        swatch.rows_per_10cm if swatch.measured else None)
    observation = record.observation
    if observation is not None:
        add("成品总高（cm）", record.pattern.target_height_cm, observation.overall_height_cm)
        params = decode_backup_json(bundle.source)["params"]
        grams: float | None
        try:
            grams = finite_float((params.get("material_summary") or {}).get("grams"))
            if grams <= 0:
                grams = None
        except (ValueError, TypeError, AttributeError):
            grams = None
        add("用线（g）", grams, observation.yarn_used_grams)
        add("操作时间（分钟）", record.pattern.estimated_time_minutes, observation.active_minutes,
            "实测含完整项目操作，与原基础工时口径不同" if observation.time_scope == "full_project" else "")
    return rows


def encode_trial_bundle(bundle: TrialBundle) -> bytes:
    bundle = _checked_bundle(bundle.source, bundle.record, bundle.draft)
    record_bytes = bundle.record.model_dump_json(indent=2).encode("utf-8")
    if len(record_bytes) > MAX_TRIAL_BYTES:
        raise ValueError("试钩记录超过 512 KiB 上限，请减少文字内容")
    draft_bytes = None
    if bundle.draft is not None:
        draft_bytes = TrialDraftState(record_sha256=hashlib.sha256(record_bytes).hexdigest(),
                                     observation=bundle.draft).model_dump_json(indent=2).encode("utf-8")
        if len(draft_bytes) > MAX_TRIAL_DRAFT_BYTES:
            raise ValueError("未完成测量草稿超过 512 KiB 上限，请减少文字内容")
    output = BytesIO()
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("pattern.json", bundle.source)
        archive.writestr(f"{bundle.record.trial_id}.trial.json", record_bytes)
        if draft_bytes is not None:
            archive.writestr("draft.json", draft_bytes)
    data = output.getvalue()
    if len(data) > MAX_TRIAL_BUNDLE_BYTES:
        raise ValueError("试钩记录包超过大小上限")
    return data


def decode_trial_bundle(data: bytes) -> TrialBundle:
    """Read bounded source, record and optional draft members, without extraction."""
    if len(data) > MAX_TRIAL_BUNDLE_BYTES:
        raise ValueError("试钩记录包超过大小上限")
    try:
        with ZipFile(BytesIO(data)) as archive:
            entries = archive.infolist()
            names = [entry.filename for entry in entries]
            trial_names = [name for name in names if name not in ("pattern.json", "draft.json")]
            if (len(entries) not in (2, 3) or len(set(names)) != len(entries)
                    or "pattern.json" not in names or len(trial_names) != 1
                    or any("/" in name or "\\" in name for name in names)):
                raise ValueError("记录包须包含原图解、一份试钩记录及可选的 draft.json")
            trial_name = trial_names[0]
            if not trial_name.endswith(".trial.json"):
                raise ValueError("记录包缺少 *.trial.json")
            blobs = {}
            for entry in entries:
                limit = {"pattern.json": MAX_PATTERN_BYTES, "draft.json": MAX_TRIAL_DRAFT_BYTES}.get(
                    entry.filename, MAX_TRIAL_BYTES)
                if entry.file_size > limit or entry.flag_bits & 1:
                    raise ValueError("记录包成员过大或已加密，无法恢复")
                with archive.open(entry) as handle:
                    blob = handle.read(limit + 1)
                if len(blob) > limit:
                    raise ValueError("记录包成员解压后超过上限")
                blobs[entry.filename] = blob
        record = TrialRecord.model_validate(decode_trial_json(blobs[trial_name]))
        if trial_name != f"{record.trial_id}.trial.json":
            raise ValueError("记录文件名与试钩编号不一致")
        draft = None
        if "draft.json" in blobs:
            state = TrialDraftState.model_validate(decode_trial_json(
                blobs["draft.json"], max_bytes=MAX_TRIAL_DRAFT_BYTES))
            if state.record_sha256 != hashlib.sha256(blobs[trial_name]).hexdigest():
                raise ValueError("未完成测量草稿与试钩记录不匹配，请使用同一次下载的完整记录包")
            draft = state.observation
        return _checked_bundle(blobs["pattern.json"], record, draft)
    except (BadZipFile, OSError, RuntimeError, NotImplementedError, EOFError) as exc:
        raise ValueError("试钩记录包损坏或压缩格式不支持，请使用系统下载的 ZIP") from exc
