"""Auditable local evaluation for authorized real-photo datasets.

The evaluator is deliberately local-only: it never sends dataset images to an
LLM provider.  A versioned manifest freezes labels, usage approval and file
hashes; the JSON report records both per-case evidence and aggregate gates.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import sys
from collections.abc import Callable
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, Literal, Optional

from PIL import Image
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.colors import YARN_COLORS
from app.schemas import PART_NAMES
from app.utils.images import MAX_UPLOAD_MB, load_image_file

MANIFEST_NAME = "eval_manifest.json"
MANIFEST_SCHEMA_VERSION = 1
REPORT_SCHEMA_VERSION = 1
MAX_MANIFEST_BYTES = 1_000_000
MAX_CASES = 500
ALLOWED_IMAGE_SUFFIXES = frozenset({".jpg", ".jpeg", ".png", ".webp"})

EvaluationRunner = Callable[[Image.Image], dict[str, Any]]


class EvaluationDatasetError(ValueError):
    """The dataset contract is invalid before evaluation can safely start."""


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class DatasetMetadata(_StrictModel):
    name: str = Field(min_length=1, max_length=100)
    version: str = Field(min_length=1, max_length=40)
    rights_basis: Literal["self_owned", "consented", "licensed", "public_domain"]
    evaluation_use_approved: Literal[True]
    contains_personal_data: bool
    retention_policy: str = Field(min_length=1, max_length=500)
    notes: Optional[str] = Field(default=None, max_length=1000)


class ExpectedLabels(_StrictModel):
    parts: list[str] = Field(min_length=1, max_length=len(PART_NAMES))
    flare: Optional[bool] = None
    dominant_colors: list[str] = Field(default_factory=list, max_length=3)

    @field_validator("parts")
    @classmethod
    def _canonical_parts(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise ValueError("parts must not contain duplicates")
        unknown = sorted(set(value) - set(PART_NAMES))
        if unknown:
            raise ValueError(f"unknown canonical parts: {unknown}")
        return value

    @field_validator("dominant_colors")
    @classmethod
    def _canonical_colors(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise ValueError("dominant_colors must not contain duplicates")
        known = {name for _rgb, name in YARN_COLORS}
        unknown = sorted(set(value) - known)
        if unknown:
            raise ValueError(f"unknown yarn colors: {unknown}")
        return value


class EvaluationCase(_StrictModel):
    id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
    file: str = Field(min_length=1, max_length=255)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    expected: ExpectedLabels
    tags: list[str] = Field(min_length=1, max_length=12)
    notes: Optional[str] = Field(default=None, max_length=500)

    @field_validator("file")
    @classmethod
    def _relative_file(cls, value: str) -> str:
        path = Path(value)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("file must be a relative path inside the dataset")
        if path.suffix.lower() not in ALLOWED_IMAGE_SUFFIXES:
            raise ValueError(f"unsupported image suffix: {path.suffix}")
        return value

    @field_validator("tags")
    @classmethod
    def _searchable_tags(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise ValueError("tags must not contain duplicates")
        invalid = [tag for tag in value if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,39}", tag)]
        if invalid:
            raise ValueError(f"invalid tags: {invalid}")
        return value


class EvaluationThresholds(_StrictModel):
    min_cases: int = Field(default=20, ge=1, le=MAX_CASES)
    min_case_part_recall: float = Field(default=0.50, ge=0.0, le=1.0)
    min_macro_part_f1: float = Field(default=0.60, ge=0.0, le=1.0)
    min_case_pass_rate: float = Field(default=0.80, ge=0.0, le=1.0)
    min_flare_accuracy: float = Field(default=0.80, ge=0.0, le=1.0)
    min_color_top3_accuracy: float = Field(default=0.80, ge=0.0, le=1.0)
    min_pattern_valid_rate: float = Field(default=1.0, ge=0.0, le=1.0)


class EvaluationManifest(_StrictModel):
    schema_version: Literal[MANIFEST_SCHEMA_VERSION]
    dataset: DatasetMetadata
    thresholds: EvaluationThresholds = Field(default_factory=EvaluationThresholds)
    cases: list[EvaluationCase] = Field(min_length=1, max_length=MAX_CASES)

    @model_validator(mode="after")
    def _unique_case_identity(self) -> "EvaluationManifest":
        ids = [case.id for case in self.cases]
        files = [case.file for case in self.cases]
        if len(set(ids)) != len(ids):
            raise ValueError("case ids must be unique")
        if len(set(files)) != len(files):
            raise ValueError("case files must be unique")
        return self


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise EvaluationDatasetError(f"manifest contains duplicate key: {key}")
        result[key] = value
    return result


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _case_path(root: Path, case: EvaluationCase) -> Path:
    candidate = (root / case.file).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise EvaluationDatasetError(f"{case.id}: file escapes dataset root") from exc
    if not candidate.is_file():
        raise EvaluationDatasetError(f"{case.id}: image does not exist: {case.file}")
    size = candidate.stat().st_size
    if size > MAX_UPLOAD_MB * 1024 * 1024:
        raise EvaluationDatasetError(
            f"{case.id}: image exceeds {MAX_UPLOAD_MB}MB limit: {case.file}"
        )
    actual = _sha256(candidate)
    if actual != case.sha256:
        raise EvaluationDatasetError(
            f"{case.id}: sha256 mismatch for {case.file}; expected {case.sha256}, got {actual}"
        )
    image = load_image_file(candidate)
    if image is None:
        raise EvaluationDatasetError(f"{case.id}: unable to decode image: {case.file}")
    image.close()
    return candidate


def load_evaluation_dataset(
    dataset_dir: str | Path,
) -> tuple[Path, EvaluationManifest, list[tuple[EvaluationCase, Path]]]:
    """Validate a manifest and freeze every case to its approved file hash."""
    root = Path(dataset_dir).expanduser().resolve()
    if not root.is_dir():
        raise EvaluationDatasetError(f"dataset directory does not exist: {root}")
    manifest_path = root / MANIFEST_NAME
    if not manifest_path.is_file():
        raise EvaluationDatasetError(f"missing {MANIFEST_NAME}: {root}")
    if manifest_path.stat().st_size > MAX_MANIFEST_BYTES:
        raise EvaluationDatasetError("evaluation manifest exceeds 1MB limit")
    try:
        payload = json.loads(
            manifest_path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
        )
        manifest = EvaluationManifest.model_validate(payload)
    except EvaluationDatasetError:
        raise
    except Exception as exc:
        raise EvaluationDatasetError(f"invalid evaluation manifest: {exc}") from exc
    prepared = [(case, _case_path(root, case)) for case in manifest.cases]
    return root, manifest, prepared


def _default_local_runner() -> EvaluationRunner:
    from app.models.orchestrator import PipelineOrchestrator

    orchestrator = PipelineOrchestrator()

    def _run(image: Image.Image) -> dict[str, Any]:
        return orchestrator.run_full_pipeline(
            image,
            local_vision=True,
            target_height_cm=18.0,
            target_height_source="evaluation_reference",
        )

    return _run


def _part_metrics(expected: set[str], actual: set[str]) -> tuple[float, float, float]:
    true_positive = len(expected & actual)
    precision = true_positive / len(actual) if actual else 0.0
    recall = true_positive / len(expected)
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return precision, recall, f1


def _mean(values: list[float]) -> Optional[float]:
    return round(sum(values) / len(values), 4) if values else None


def _application_version() -> str:
    try:
        return version("crochet-photo2pattern")
    except PackageNotFoundError:
        return "source-tree"


def evaluate_dataset(
    dataset_dir: str | Path,
    *,
    runner: Optional[EvaluationRunner] = None,
) -> dict[str, Any]:
    """Evaluate every frozen case and return a report without hiding failures."""
    _root, manifest, prepared = load_evaluation_dataset(dataset_dir)
    run_case = runner or _default_local_runner()
    thresholds = manifest.thresholds
    case_reports: list[dict[str, Any]] = []

    part_f1_values: list[float] = []
    flare_matches: list[float] = []
    color_matches: list[float] = []
    pattern_valid_values: list[float] = []
    case_pass_values: list[float] = []
    pipeline_errors = 0
    tag_counts: dict[str, int] = {}

    for case, image_path in prepared:
        for tag in case.tags:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
        expected_parts = set(case.expected.parts)
        try:
            image = load_image_file(image_path)
            if image is None:
                raise EvaluationDatasetError(f"unable to decode image: {case.file}")
            try:
                result = run_case(image)
            finally:
                image.close()

            analysis = result.get("analysis") or {}
            actual_parts = set(analysis.get("parts") or [])
            precision, recall, part_f1 = _part_metrics(expected_parts, actual_parts)
            structure_parts = (result.get("structure") or {}).get("parts") or []
            got_flare = any(
                (part.get("name") if isinstance(part, dict) else getattr(part, "name", None))
                == "裙子"
                for part in structure_parts
            )
            colors = list(analysis.get("recommended_colors") or [])[:3]
            flare_match = (
                got_flare == case.expected.flare if case.expected.flare is not None else None
            )
            color_match = (
                bool(set(case.expected.dominant_colors) & set(colors))
                if case.expected.dominant_colors
                else None
            )

            from app.models.validator import validate_pattern

            validation = validate_pattern(result.get("params") or {})
            pattern_valid = bool(validation["ok"] and validation["checked"] > 0)
            case_passed = bool(
                recall >= thresholds.min_case_part_recall
                and (flare_match is not False)
                and (color_match is not False)
                and pattern_valid
            )
            case_report = {
                "id": case.id,
                "file": case.file,
                "sha256": case.sha256,
                "tags": case.tags,
                "expected_parts": sorted(expected_parts),
                "actual_parts": sorted(actual_parts),
                "part_precision": round(precision, 4),
                "part_recall": round(recall, 4),
                "part_f1": round(part_f1, 4),
                "parts_exact": actual_parts == expected_parts,
                "expected_flare": case.expected.flare,
                "actual_flare": got_flare,
                "flare_match": flare_match,
                "expected_dominant_colors": case.expected.dominant_colors,
                "actual_colors_top3": colors,
                "color_top3_match": color_match,
                "pattern_valid": pattern_valid,
                "pattern_issues": validation["issues"],
                "passed": case_passed,
                "error": None,
            }
        except Exception as exc:
            pipeline_errors += 1
            part_f1 = 0.0
            flare_match = False if case.expected.flare is not None else None
            color_match = False if case.expected.dominant_colors else None
            pattern_valid = False
            case_passed = False
            case_report = {
                "id": case.id,
                "file": case.file,
                "sha256": case.sha256,
                "tags": case.tags,
                "expected_parts": sorted(expected_parts),
                "actual_parts": [],
                "part_precision": 0.0,
                "part_recall": 0.0,
                "part_f1": 0.0,
                "parts_exact": False,
                "expected_flare": case.expected.flare,
                "actual_flare": None,
                "flare_match": flare_match,
                "expected_dominant_colors": case.expected.dominant_colors,
                "actual_colors_top3": [],
                "color_top3_match": color_match,
                "pattern_valid": False,
                "pattern_issues": [],
                "passed": False,
                "error": {"type": type(exc).__name__, "message": str(exc)[:500]},
            }

        part_f1_values.append(part_f1)
        if flare_match is not None:
            flare_matches.append(float(flare_match))
        if color_match is not None:
            color_matches.append(float(color_match))
        pattern_valid_values.append(float(pattern_valid))
        case_pass_values.append(float(case_passed))
        case_reports.append(case_report)

    macro_part_f1 = _mean(part_f1_values)
    flare_accuracy = _mean(flare_matches)
    color_top3_accuracy = _mean(color_matches)
    pattern_valid_rate = _mean(pattern_valid_values)
    case_pass_rate = _mean(case_pass_values)
    passed = bool(
        len(case_reports) >= thresholds.min_cases
        and macro_part_f1 is not None
        and macro_part_f1 >= thresholds.min_macro_part_f1
        and case_pass_rate is not None
        and case_pass_rate >= thresholds.min_case_pass_rate
        and pattern_valid_rate is not None
        and pattern_valid_rate >= thresholds.min_pattern_valid_rate
        and (flare_accuracy is None or flare_accuracy >= thresholds.min_flare_accuracy)
        and (
            color_top3_accuracy is None
            or color_top3_accuracy >= thresholds.min_color_top3_accuracy
        )
    )
    return {
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "application_version": _application_version(),
        "evaluator": {
            "mode": "local_vision",
            "python": platform.python_version(),
            "network_images_sent": False,
        },
        "dataset": manifest.dataset.model_dump(),
        "thresholds": thresholds.model_dump(),
        "summary": {
            "cases": len(case_reports),
            "tag_counts": dict(sorted(tag_counts.items())),
            "pipeline_errors": pipeline_errors,
            "macro_part_f1": macro_part_f1,
            "case_pass_rate": case_pass_rate,
            "flare_labeled_cases": len(flare_matches),
            "flare_accuracy": flare_accuracy,
            "color_labeled_cases": len(color_matches),
            "color_top3_accuracy": color_top3_accuracy,
            "pattern_valid_rate": pattern_valid_rate,
            "passed": passed,
        },
        "cases": case_reports,
    }


def write_evaluation_report(report: dict[str, Any], destination: str | Path) -> Path:
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="crochet2pattern-eval",
        description="在授权真实照片集上运行本地、可审计的质量评测",
    )
    parser.add_argument("--dataset", required=True, help="含 eval_manifest.json 的数据集目录")
    parser.add_argument("--out", help="JSON 报告路径；省略时输出到 stdout")
    parser.add_argument(
        "--allow-fail",
        action="store_true",
        help="指标未达阈值时仍返回状态码 0（报告中的 passed 仍为 false）",
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = evaluate_dataset(args.dataset)
    except EvaluationDatasetError as exc:
        print(f"评测数据集无效: {exc}", file=sys.stderr)
        return 1
    if args.out:
        path = write_evaluation_report(report, args.out)
        print(f"评测报告: {path}", file=sys.stderr)
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    summary = report["summary"]
    print(
        f"评测完成: {summary['cases']} cases · macro F1={summary['macro_part_f1']} "
        f"· pass_rate={summary['case_pass_rate']} · passed={summary['passed']}",
        file=sys.stderr,
    )
    return 0 if summary["passed"] or args.allow_fail else 2


if __name__ == "__main__":
    raise SystemExit(main())
