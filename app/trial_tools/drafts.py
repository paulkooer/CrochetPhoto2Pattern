"""Physical trial drafts."""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Literal

from app.utils.counts import integer_count
from app.utils.numbers import finite_float

from .io import (
    _application_version,
    _read_bytes,
    decode_trial_json,
)
from .schemas import (
    MAX_PATTERN_BYTES,
    PatternSource,
    SwatchMeasurement,
    TrialDataError,
    TrialGauge,
    TrialRecord,
)


def _part_quantity(part: dict[str, Any]) -> int:
    try:
        return max(1, integer_count(part.get("quantity", 1)))
    except ValueError:
        raise TrialDataError("pattern part quantity must be an integer") from None


def _pattern_counts(parts: list[dict[str, Any]]) -> tuple[int, int]:
    total_stitches = 0
    total_rounds = 0
    for part in parts:
        if not isinstance(part, dict):
            raise TrialDataError("pattern parts must be JSON objects")
        rounds = part.get("rounds") or []
        if not isinstance(rounds, list) or not rounds:
            raise TrialDataError("every pattern part must contain rounds")
        quantity = _part_quantity(part)
        total_rounds += len(rounds) * quantity
        for crochet_round in rounds:
            try:
                # integer_count also catches the OverflowError that raw int()
                # raises on JSON Infinity/1e400 payloads.
                stitches = integer_count(crochet_round["stitches"])
            except (KeyError, TypeError, ValueError):
                raise TrialDataError("every pattern round must contain integer stitches") from None
            if stitches <= 0:
                raise TrialDataError("pattern round stitches must be positive")
            total_stitches += stitches * quantity
    return total_stitches, total_rounds


def create_trial_draft(
    pattern_path: str | Path,
    *,
    trial_id: str,
    maker_id: str,
    cohort: Literal["calibration", "validation"] = "calibration",
) -> dict[str, Any]:
    """Create an editable draft bound to an exact generated pattern file."""
    path = Path(pattern_path).expanduser().resolve()
    return create_trial_draft_from_bytes(_read_bytes(path, MAX_PATTERN_BYTES),
                                         trial_id=trial_id, maker_id=maker_id, cohort=cohort)


def _fingerprint_hash(core: dict[str, Any]) -> str:
    encoded = json.dumps(core, sort_keys=True, ensure_ascii=False,
                         separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _legacy_design_fingerprint(params: dict[str, Any]) -> str:
    """Frozen unversioned algorithm, used only to verify existing saved records."""
    gauge = params.get("gauge") or {}
    parts = params.get("parts") or []
    core = {
        "gauge": [gauge.get("stitches_per_10cm"), gauge.get("rows_per_10cm")],
        "parts": [
            {
                "name": part.get("name"),
                "quantity": part.get("quantity", 1),
                "rounds": [
                    [rd.get("stitches"), rd.get("increase") or 0, rd.get("decrease") or 0]
                    for rd in (part.get("rounds") or []) if isinstance(rd, dict)
                ],
            }
            for part in parts if isinstance(part, dict)
        ],
    }
    return _fingerprint_hash(core)


def _design_fingerprint(params: dict[str, Any]) -> str:
    """Conservative identity of gauge and the multiset of physical round sequences.

    Part labels/order and equivalent grouping of identical copies do not create
    new designs. Preserve round order and multiplicity; normalize numeric spelling.
    This count-based identity does not establish complete physical equivalence.
    """
    gauge = TrialGauge.model_validate(params.get("gauge") or {})
    from app.models.gauge import INDEPENDENT_TRIAL_MESSAGE, has_independent_gauge

    if has_independent_gauge(params):
        raise TrialDataError(INDEPENDENT_TRIAL_MESSAGE)
    sequences: Counter[str] = Counter()
    for part in params.get("parts") or []:
        rounds = [[integer_count(rd["stitches"]), integer_count(rd.get("increase", 0)),
                   integer_count(rd.get("decrease", 0))] for rd in part["rounds"]]
        signature = json.dumps(rounds, separators=(",", ":"))
        sequences[signature] += _part_quantity(part)
    return _fingerprint_hash({
        "version": "1",
        "gauge": [gauge.stitches_per_10cm, gauge.rows_per_10cm],
        "parts": [[json.loads(signature), count] for signature, count in sorted(sequences.items())],
    })


def create_trial_draft_from_bytes(
    blob: bytes, *, trial_id: str, maker_id: str,
    cohort: Literal["calibration", "validation"] = "calibration",
) -> dict[str, Any]:
    """Hash the same bounded bytes used to derive metadata; no temporary file."""
    payload = decode_trial_json(blob, max_bytes=MAX_PATTERN_BYTES)
    if not isinstance(payload, dict):
        raise TrialDataError("pattern JSON root must be an object")
    params = payload.get("params", payload)
    if not isinstance(params, dict):
        raise TrialDataError("pattern params must be an object")
    parts = params.get("parts") or []
    if not isinstance(parts, list) or not parts:
        raise TrialDataError("pattern has no parts")
    total_stitches, total_rounds = _pattern_counts(parts)
    gauge = params.get("gauge") or {}
    analysis = payload.get("analysis") or {}
    try:
        source = PatternSource(
            sha256=hashlib.sha256(blob).hexdigest(),
            design_fingerprint=_design_fingerprint(params),
            design_fingerprint_version="1",
            application_version=_application_version(),
            target_height_cm=finite_float(analysis["height_cm"]),
            gauge=TrialGauge.model_validate(gauge),
            total_stitches=total_stitches,
            total_physical_rounds=total_rounds,
            estimated_time_minutes=integer_count(params["estimated_time_minutes"]),
        )
        draft = TrialRecord(
            schema_version=2,  # == TRIAL_SCHEMA_VERSION
            trial_id=trial_id,
            maker_id=maker_id,
            status="draft",
            cohort=cohort,
            pattern=source,
            swatch=SwatchMeasurement(
                measured=False,
                stitches_per_10cm=source.gauge.stitches_per_10cm,
                rows_per_10cm=source.gauge.rows_per_10cm,
            ),
        )
    except TrialDataError:
        raise
    except Exception as exc:
        raise TrialDataError(f"pattern is missing required trial metadata: {exc}") from exc
    return draft.model_dump(mode="json")


def upgrade_trial_record_from_bytes(blob: bytes, record: TrialRecord) -> TrialRecord:
    """Verify every source field before migrating legacy identity; retain measurements."""
    record = TrialRecord.model_validate(record.model_dump())
    expected = create_trial_draft_from_bytes(blob, trial_id=record.trial_id,
                                             maker_id=record.maker_id, cohort=record.cohort)["pattern"]
    expected["application_version"] = record.pattern.application_version
    stored = record.pattern.model_dump(mode="json")
    comparable = dict(expected)
    if record.pattern.design_fingerprint_version is None:
        if record.pattern.design_fingerprint is not None:
            payload = decode_trial_json(blob, max_bytes=MAX_PATTERN_BYTES)
            legacy = _legacy_design_fingerprint(payload.get("params", payload))
            if legacy != record.pattern.design_fingerprint:
                raise TrialDataError("试钩记录与原图解不匹配：旧设计指纹无效")
        comparable["design_fingerprint"] = stored["design_fingerprint"]
        comparable["design_fingerprint_version"] = None
    if comparable != stored:
        raise TrialDataError("试钩记录与原图解不匹配，请恢复同一次下载的记录包")
    return TrialRecord.model_validate({**record.model_dump(mode="json"), "pattern": expected})
