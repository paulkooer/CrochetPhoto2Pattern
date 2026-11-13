"""Physical trial external."""
from __future__ import annotations

import json
from importlib.resources import files as resource_files
from pathlib import Path
from typing import Any

from .io import (
    _read_json,
    _reject_duplicate_keys,
)
from .schemas import (
    CURATED_EXTERNAL_EVIDENCE_NAME,
    MAX_EXTERNAL_EVIDENCE_BYTES,
    ExternalEvidenceBundle,
    TrialDataError,
)


def load_external_evidence(path: str | Path) -> ExternalEvidenceBundle:
    """Load a bounded, provenance-bearing external evidence bundle."""
    resolved = Path(path).expanduser().resolve()
    try:
        return ExternalEvidenceBundle.model_validate(
            _read_json(resolved, MAX_EXTERNAL_EVIDENCE_BYTES)
        )
    except TrialDataError:
        raise
    except Exception as exc:
        raise TrialDataError(f"invalid external evidence {resolved.name}: {exc}") from exc


def load_curated_external_evidence() -> ExternalEvidenceBundle:
    """Load the attribution-preserving evidence shipped inside the wheel."""
    resource = (
        resource_files("app")
        .joinpath("data")
        .joinpath(CURATED_EXTERNAL_EVIDENCE_NAME)
    )
    try:
        blob = resource.read_bytes()
        if len(blob) > MAX_EXTERNAL_EVIDENCE_BYTES:
            raise TrialDataError(
                f"curated evidence exceeds {MAX_EXTERNAL_EVIDENCE_BYTES} byte limit"
            )
        payload = json.loads(
            blob.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
        )
        return ExternalEvidenceBundle.model_validate(payload)
    except TrialDataError:
        raise
    except Exception as exc:
        raise TrialDataError(f"invalid packaged curated evidence: {exc}") from exc


def summarize_external_evidence(bundle: ExternalEvidenceBundle) -> dict[str, Any]:
    """Return attributed context without deriving any calibration candidates."""
    timed_context: list[dict[str, Any]] = []
    yarn_context: list[dict[str, Any]] = []
    kinds: dict[str, int] = {}
    project_types: dict[str, int] = {}
    total_observations = 0
    sources: list[dict[str, Any]] = []
    for source in bundle.sources:
        kinds[source.evidence_kind] = kinds.get(source.evidence_kind, 0) + 1
        total_observations += len(source.observations)
        sources.append({
            "source_id": source.source_id,
            "title": source.title,
            "publisher": source.publisher,
            "source_url": source.source_url,
            "accessed_on": source.accessed_on.isoformat(),
            "evidence_kind": source.evidence_kind,
            "verification": source.verification,
            "declared_sample_size": source.declared_sample_size,
            "raw_records_available": source.raw_records_available,
            "methodology_available": source.methodology_available,
            "reuse_basis": source.reuse_basis,
        })
        for observation in source.observations:
            project_types[observation.project_type] = (
                project_types.get(observation.project_type, 0) + 1
            )
            identity = {
                "source_id": source.source_id,
                "observation_id": observation.observation_id,
                "project_label": observation.project_label,
                "project_type": observation.project_type,
                "measurement_scope": observation.measurement_scope,
            }
            if observation.completion_minutes_median is not None:
                timed_context.append({
                    **identity,
                    "finished_height_cm": observation.finished_height_cm,
                    "finished_length_cm": observation.finished_length_cm,
                    "completion_minutes_median": observation.completion_minutes_median,
                    "completion_minutes_min": observation.completion_minutes_min,
                    "completion_minutes_max": observation.completion_minutes_max,
                })
            if (
                observation.yarn_used_grams is not None
                or observation.yarn_used_meters is not None
            ):
                yarn_context.append({
                    **identity,
                    "finished_height_cm": observation.finished_height_cm,
                    "finished_length_cm": observation.finished_length_cm,
                    "yarn_used_grams": observation.yarn_used_grams,
                    "yarn_used_meters": observation.yarn_used_meters,
                    "stitches_per_10cm": observation.stitches_per_10cm,
                    "hook_mm": observation.hook_mm,
                })
    return {
        "external_evidence_schema_version": bundle.schema_version,
        "created_on": bundle.created_on.isoformat(),
        "policy": {
            "used_for_calibration": False,
            "automatic_changes_applied": False,
            "reason": (
                "External sources are not bound to an exact generated pattern hash, "
                "verified stitch count, and controlled local trial protocol."
            ),
        },
        "coverage": {
            "sources": len(bundle.sources),
            "observations": total_observations,
            "source_kinds": dict(sorted(kinds.items())),
            "project_types": dict(sorted(project_types.items())),
        },
        "sources": sources,
        "amigurumi_timed_context": [
            item for item in timed_context if item["project_type"] == "amigurumi"
        ],
        "yarn_context": yarn_context,
        "limitations": [
            "Published figures remain source claims unless raw_records_reviewed is set.",
            "Size alone does not control for stitch count, yarn, skill, details, or seaming.",
            "Do not infer per-stitch constants from this contextual report.",
        ],
    }
