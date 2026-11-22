"""Shared helpers for the legacy-generator audit reproductions.

Read-only against the audited tree: everything the code under test writes goes
to tempfile directories; only this scratch directory receives captured output.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO = Path("<repo>")
SCRATCH = REPO / "eval_outputs/fable52-system-audit-20261117-fable-review/repro/legacy-generator"
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
sys.dont_write_bytecode = True

import app  # noqa: E402

assert Path(app.__file__).resolve().is_relative_to(REPO), app.__file__
assert "eval_outputs" not in Path(app.__file__).parts, app.__file__

from app import software_version  # noqa: E402
from app.models.crochet_params import CrochetParamsGenerator  # noqa: E402
from app.models.gauge import PRESETS, Gauge, ShapingStyle  # noqa: E402
from app.models.geometry import no_photo_geometry  # noqa: E402
from app.models.sizing import sizing_meta_for_analysis  # noqa: E402
from app.models.structure_designer import StructureDesigner  # noqa: E402
from app.schemas import PART_NAMES, ImageAnalysis, PatternResult  # noqa: E402

ALL_PARTS = list(PART_NAMES)


def assert_audited_modules() -> None:
    """Every loaded app.* module must come from the audited checkout."""
    for name, module in list(sys.modules.items()):
        if name == "app" or name.startswith("app."):
            path = getattr(module, "__file__", None)
            if path is not None:
                assert Path(path).resolve().is_relative_to(REPO / "app"), (name, path)


def manual_result(*, head=9.0, height=18.0, parts=None, gauge=None, style=None,
                  result_id="audit000000", **generate_kwargs) -> dict:
    """Same construction as app/ui/tab_manual._run_pipeline_from_analysis and the
    manual branch of app/cli.run (minus the crochetability gate, applied by callers)."""
    gauge = gauge or PRESETS["classic"]
    style = style or ShapingStyle()
    analysis = ImageAnalysis(
        body_type="标准", head_diameter_cm=head, height_cm=height, main_features=["卡通风格"],
        pose="站立", difficulty="easy", parts=list(parts or ["头部", "身体", "手臂", "腿部"]))
    structure = StructureDesigner.design_3d_structure(analysis)
    params = CrochetParamsGenerator.generate_params(
        analysis, structure, gauge=gauge, style=style, **generate_kwargs)
    return PatternResult(
        generator_version=software_version(),
        analysis=analysis.model_dump(), structure=dict(structure), params=dict(params),
        result_id=result_id,
        gauge={"stitches_per_10cm": gauge.stitches_per_10cm, "rows_per_10cm": gauge.rows_per_10cm},
        style={"sphere_mode": style.sphere_mode, "one_piece": style.one_piece,
               "skirt_style": style.skirt_style, "ruffle_hem": style.ruffle_hem},
        spans_measured=[], sizing=sizing_meta_for_analysis(analysis, "manual_dimensions"),
        geometry=no_photo_geometry().model_dump(),
    ).to_result_dict()


def jdump(value) -> str:
    return json.dumps(value, ensure_ascii=False, indent=1, sort_keys=True, default=str)


__all__ = ["ALL_PARTS", "PRESETS", "REPO", "SCRATCH", "Gauge", "ShapingStyle",
           "assert_audited_modules", "jdump", "manual_result"]
