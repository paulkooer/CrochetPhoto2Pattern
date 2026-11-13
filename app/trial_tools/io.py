"""Physical trial io."""
from __future__ import annotations

import json
import math
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

from .schemas import (
    MAX_TRIAL_BYTES,
    MAX_TRIAL_FILES,
    TrialDataError,
    TrialRecord,
)


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise TrialDataError(f"JSON contains duplicate key: {key}")
        result[key] = value
    return result


def _read_bytes(path: Path, max_bytes: int) -> bytes:
    if not path.is_file():
        raise TrialDataError(f"file does not exist: {path}")
    if path.stat().st_size > max_bytes:
        raise TrialDataError(f"file exceeds {max_bytes} byte limit: {path.name}")
    with path.open("rb") as handle:
        blob = handle.read(max_bytes + 1)
    if len(blob) > max_bytes:
        raise TrialDataError(f"file exceeds {max_bytes} byte limit: {path.name}")
    return blob


def _finite_json_number(value: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise TrialDataError("JSON numbers must be finite")
    return number


def decode_trial_json(blob: bytes, *, max_bytes: int = MAX_TRIAL_BYTES) -> Any:
    """Bounded decoding shared by local files and in-memory trial bundles."""
    if len(blob) > max_bytes:
        raise TrialDataError(f"file exceeds {max_bytes} byte limit")
    try:
        return json.loads(
            blob.decode("utf-8-sig"),
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_finite_json_number,
            parse_float=_finite_json_number,
        )
    except TrialDataError:
        raise
    except Exception as exc:
        raise TrialDataError(f"invalid trial JSON: {exc}") from exc


def _read_json(path: Path, max_bytes: int) -> Any:
    return decode_trial_json(_read_bytes(path, max_bytes), max_bytes=max_bytes)


def _application_version() -> str:
    try:
        return version("crochet-photo2pattern")
    except PackageNotFoundError:
        return "source-tree"


def load_trial_records(records_dir: str | Path) -> list[TrialRecord]:
    root = Path(records_dir).expanduser().resolve()
    if not root.is_dir():
        raise TrialDataError(f"trial directory does not exist: {root}")
    files = sorted(root.glob("*.trial.json"))
    if not files:
        raise TrialDataError(f"no *.trial.json files found in {root}")
    if len(files) > MAX_TRIAL_FILES:
        raise TrialDataError(f"trial directory exceeds {MAX_TRIAL_FILES} records")
    records: list[TrialRecord] = []
    for path in files:
        resolved = path.resolve()
        try:
            resolved.relative_to(root)
        except ValueError as exc:
            raise TrialDataError(f"trial record escapes directory: {path.name}") from exc
        try:
            records.append(TrialRecord.model_validate(_read_json(resolved, MAX_TRIAL_BYTES)))
        except TrialDataError:
            raise
        except Exception as exc:
            raise TrialDataError(f"invalid trial record {path.name}: {exc}") from exc
    ids = [record.trial_id for record in records]
    if len(set(ids)) != len(ids):
        raise TrialDataError("trial_id values must be unique across the directory")
    return records


def write_json(payload: dict[str, Any], destination: str | Path) -> Path:
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path
