"""Incomplete measurements kept outside completed trial evidence."""
from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator

from app.trials import TrialFloat, TrialInt


class TrialObservationDraft(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    completed_on: date | None = None
    overall_height_cm: TrialFloat | None = Field(default=None, gt=0.0, le=300.0)
    yarn_used_grams: TrialFloat | None = Field(default=None, gt=0.0, le=5000.0)
    yarn_used_meters: TrialFloat | None = Field(default=None, gt=0.0, le=100_000.0)
    active_minutes: TrialInt | None = Field(default=None, gt=0, le=100_000)
    time_scope: Literal["round_crochet_baseline", "full_project"] = "full_project"
    pattern_modified: StrictBool = False
    modifications: list[str] = Field(default_factory=list, max_length=50)
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("completed_on")
    @classmethod
    def _not_in_future(cls, value: date | None) -> date | None:
        if value is not None and value > date.today():
            raise ValueError("完成日期不能晚于今天")
        return value

    @field_validator("modifications")
    @classmethod
    def _nonempty_modifications(cls, value: list[str]) -> list[str]:
        return [item.strip() for item in value if item.strip()]


class TrialDraftState(BaseModel):
    """Sidecar is bound to the exact trial JSON, which binds the source pattern."""
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1"] = "1"
    record_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    observation: TrialObservationDraft
