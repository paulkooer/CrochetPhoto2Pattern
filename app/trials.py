"""Physical crochet trial records and conservative calibration analysis.

This module closes the measurement loop without mutating production constants.
It creates a draft tied to an exact pattern JSON hash, validates completed trial
records, and reports candidate calibration values only after basic diversity
requirements are met.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import sys
from collections import Counter
from collections.abc import Iterable
from datetime import UTC, date, datetime
from importlib.metadata import PackageNotFoundError, version
from importlib.resources import files as resource_files
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, field_validator, model_validator

from app.models.crochet_params import SECONDS_PER_ROUND_OVERHEAD, SECONDS_PER_STITCH
from app.models.gauge import BASE_GRAMS_PER_STITCH, BASE_STITCH_AREA_CM2
from app.utils.counts import integer_count
from app.utils.numbers import finite_float

from .trial_tools.analysis import (
    _distribution as _distribution,
)
from .trial_tools.analysis import (
    _median as _median,
)
from .trial_tools.analysis import (
    _median_absolute_deviation as _median_absolute_deviation,
)
from .trial_tools.analysis import (
    analyze_trial_directory as analyze_trial_directory,
)
from .trial_tools.analysis import (
    analyze_trials as analyze_trials,
)
from .trial_tools.cli import (
    build_parser as build_parser,
)
from .trial_tools.cli import (
    main as main,
)
from .trial_tools.drafts import (
    _design_fingerprint as _design_fingerprint,
)
from .trial_tools.drafts import (
    _fingerprint_hash as _fingerprint_hash,
)
from .trial_tools.drafts import (
    _legacy_design_fingerprint as _legacy_design_fingerprint,
)
from .trial_tools.drafts import (
    _part_quantity as _part_quantity,
)
from .trial_tools.drafts import (
    _pattern_counts as _pattern_counts,
)
from .trial_tools.drafts import (
    create_trial_draft as create_trial_draft,
)
from .trial_tools.drafts import (
    create_trial_draft_from_bytes as create_trial_draft_from_bytes,
)
from .trial_tools.drafts import (
    upgrade_trial_record_from_bytes as upgrade_trial_record_from_bytes,
)
from .trial_tools.external import (
    load_curated_external_evidence as load_curated_external_evidence,
)
from .trial_tools.external import (
    load_external_evidence as load_external_evidence,
)
from .trial_tools.external import (
    summarize_external_evidence as summarize_external_evidence,
)
from .trial_tools.io import (
    _application_version as _application_version,
)
from .trial_tools.io import (
    _finite_json_number as _finite_json_number,
)
from .trial_tools.io import (
    _read_bytes as _read_bytes,
)
from .trial_tools.io import (
    _read_json as _read_json,
)
from .trial_tools.io import (
    _reject_duplicate_keys as _reject_duplicate_keys,
)
from .trial_tools.io import (
    decode_trial_json as decode_trial_json,
)
from .trial_tools.io import (
    load_trial_records as load_trial_records,
)
from .trial_tools.io import (
    write_json as write_json,
)
from .trial_tools.schemas import (
    CURATED_EXTERNAL_EVIDENCE_NAME as CURATED_EXTERNAL_EVIDENCE_NAME,
)
from .trial_tools.schemas import (
    EXTERNAL_EVIDENCE_SCHEMA_VERSION as EXTERNAL_EVIDENCE_SCHEMA_VERSION,
)
from .trial_tools.schemas import (
    MAX_EXTERNAL_EVIDENCE_BYTES as MAX_EXTERNAL_EVIDENCE_BYTES,
)
from .trial_tools.schemas import (
    MAX_PATTERN_BYTES as MAX_PATTERN_BYTES,
)
from .trial_tools.schemas import (
    MAX_RELATIVE_MEDIAN_ABSOLUTE_DEVIATION as MAX_RELATIVE_MEDIAN_ABSOLUTE_DEVIATION,
)
from .trial_tools.schemas import (
    MAX_TRIAL_BYTES as MAX_TRIAL_BYTES,
)
from .trial_tools.schemas import (
    MAX_TRIAL_FILES as MAX_TRIAL_FILES,
)
from .trial_tools.schemas import (
    MIN_CALIBRATION_TRIALS as MIN_CALIBRATION_TRIALS,
)
from .trial_tools.schemas import (
    MIN_DISTINCT_MAKERS as MIN_DISTINCT_MAKERS,
)
from .trial_tools.schemas import (
    MIN_DISTINCT_PATTERNS as MIN_DISTINCT_PATTERNS,
)
from .trial_tools.schemas import (
    MIN_DISTINCT_VALIDATION_PATTERNS as MIN_DISTINCT_VALIDATION_PATTERNS,
)
from .trial_tools.schemas import (
    MIN_VALIDATION_TRIALS as MIN_VALIDATION_TRIALS,
)
from .trial_tools.schemas import (
    TRIAL_REPORT_SCHEMA_VERSION as TRIAL_REPORT_SCHEMA_VERSION,
)
from .trial_tools.schemas import (
    TRIAL_SCHEMA_VERSION as TRIAL_SCHEMA_VERSION,
)
from .trial_tools.schemas import (
    ExternalEvidenceBundle as ExternalEvidenceBundle,
)
from .trial_tools.schemas import (
    ExternalEvidenceSource as ExternalEvidenceSource,
)
from .trial_tools.schemas import (
    ExternalObservation as ExternalObservation,
)
from .trial_tools.schemas import (
    PatternSource as PatternSource,
)
from .trial_tools.schemas import (
    SwatchMeasurement as SwatchMeasurement,
)
from .trial_tools.schemas import (
    TrialDataError as TrialDataError,
)
from .trial_tools.schemas import (
    TrialFloat as TrialFloat,
)
from .trial_tools.schemas import (
    TrialGauge as TrialGauge,
)
from .trial_tools.schemas import (
    TrialInt as TrialInt,
)
from .trial_tools.schemas import (
    TrialObservation as TrialObservation,
)
from .trial_tools.schemas import (
    TrialRecord as TrialRecord,
)
from .trial_tools.schemas import (
    _StrictModel as _StrictModel,
)

__all__ = [
    "Annotated",
    "Any",
    "BASE_GRAMS_PER_STITCH",
    "BASE_STITCH_AREA_CM2",
    "BaseModel",
    "BeforeValidator",
    "CURATED_EXTERNAL_EVIDENCE_NAME",
    "ConfigDict",
    "Counter",
    "EXTERNAL_EVIDENCE_SCHEMA_VERSION",
    "ExternalEvidenceBundle",
    "ExternalEvidenceSource",
    "ExternalObservation",
    "Field",
    "Iterable",
    "Literal",
    "MAX_EXTERNAL_EVIDENCE_BYTES",
    "MAX_PATTERN_BYTES",
    "MAX_RELATIVE_MEDIAN_ABSOLUTE_DEVIATION",
    "MAX_TRIAL_BYTES",
    "MAX_TRIAL_FILES",
    "MIN_CALIBRATION_TRIALS",
    "MIN_DISTINCT_MAKERS",
    "MIN_DISTINCT_PATTERNS",
    "MIN_DISTINCT_VALIDATION_PATTERNS",
    "MIN_VALIDATION_TRIALS",
    "PackageNotFoundError",
    "Path",
    "PatternSource",
    "SECONDS_PER_ROUND_OVERHEAD",
    "SECONDS_PER_STITCH",
    "SwatchMeasurement",
    "TRIAL_REPORT_SCHEMA_VERSION",
    "TRIAL_SCHEMA_VERSION",
    "TrialDataError",
    "TrialFloat",
    "TrialGauge",
    "TrialInt",
    "TrialObservation",
    "TrialRecord",
    "UTC",
    "analyze_trial_directory",
    "analyze_trials",
    "annotations",
    "argparse",
    "build_parser",
    "create_trial_draft",
    "create_trial_draft_from_bytes",
    "date",
    "datetime",
    "decode_trial_json",
    "field_validator",
    "finite_float",
    "hashlib",
    "integer_count",
    "json",
    "load_curated_external_evidence",
    "load_external_evidence",
    "load_trial_records",
    "main",
    "math",
    "model_validator",
    "resource_files",
    "statistics",
    "summarize_external_evidence",
    "sys",
    "upgrade_trial_record_from_bytes",
    "version",
    "write_json",
]


if __name__ == "__main__":
    raise SystemExit(main())
