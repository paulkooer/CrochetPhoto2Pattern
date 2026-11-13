"""Freeze complete serialized generator outputs before moving its implementation.

Refresh explicitly with ``python -m tests.test_generator_output_snapshots --write``
only after reviewing an intentional behavior change. Pytest never rewrites fixtures.
"""
from __future__ import annotations

import gzip
import json
from itertools import product
from pathlib import Path

import pytest

from app.models.crochet_params import CrochetParamsGenerator, PatternGenerationError
from app.models.gauge import PRESETS, ShapingStyle
from app.models.structure_designer import StructureDesigner
from app.schemas import PART_NAMES, ImageAnalysis

FIXTURES = Path(__file__).parent / "fixtures" / "generate_params"
SOURCE_COMMIT = "60084d09db40d8f5d068980b99c632f736fc5de8"
MODES = ("ladder", "ideal", "egg")
STYLES = [ShapingStyle(*values) for values in product(MODES, (False, True), ("ring", "attached"),
                                                    (False, True))]
CASES = [(preset, f"matrix-{i:02d}", style) for preset in PRESETS for i, style in enumerate(STYLES)]
CASES += [(preset, f"{variant}-{mode}", ShapingStyle(sphere_mode=mode))
          for preset in PRESETS for mode in MODES for variant in ("opening", "profile-colors")]
CASES += [(preset, variant, ShapingStyle()) for preset in PRESETS
          for variant in ("independent-gauges", "shape-priority", "empty", "fallback")]


def generated(preset: str, case: str, style: ShapingStyle) -> dict:
    analysis = ImageAnalysis(
        body_type="未评估", head_diameter_cm=8.3, height_cm=24,
        main_features=[], pose="站立", difficulty="medium", parts=list(PART_NAMES),
    )
    structure = dict(StructureDesigner.design_3d_structure(analysis))
    options: dict = {"gauge": PRESETS[preset], "style": style}
    if case.startswith("opening-"):
        options["head_opening_stitches"] = 16
    elif case.startswith("profile-colors-"):
        options.update(
            body_profile=[0.6, 0.7, 0.9, 1.0, 0.8, 0.65, 0.7, 0.75, 0.6, 0.4],
            color_bands=[{"start": 0.0, "end": 0.4, "color": "红色"},
                         {"start": 0.4, "end": 1.0, "color": "蓝色"}],
            spans={"头部": (0.0, 0.3), "身体": (0.3, 0.7)},
        )
    elif case == "independent-gauges":
        options["part_gauges"] = {"帽子": PRESETS["fine"], "裙子": PRESETS["dk"]}
    elif case == "shape-priority":
        structure = {"parts": [{"name": "头部", "shape": "cylinder", "diameter_cm": 8.3},
                               {"name": "身体", "shape": "cup", "diameter_cm": 5.0},
                               {"name": "裙子", "shape": "sphere", "diameter_cm": 3.0}]}
    elif case == "empty":
        structure = {"parts": []}
    elif case == "fallback":
        structure = {}
    if case == "empty":
        with pytest.raises(PatternGenerationError) as raised:
            CrochetParamsGenerator.generate_params(analysis, structure, **options)
        return {"exception": type(raised.value).__name__, "message": str(raised.value)}
    params = CrochetParamsGenerator.generate_params(analysis, structure, **options)
    # JSON is the output boundary: normalize tuples while preserving list order and every field.
    return json.loads(json.dumps(params, ensure_ascii=False, allow_nan=False))


@pytest.fixture(scope="module")
def snapshots():
    result = {}
    for preset in PRESETS:
        with gzip.open(FIXTURES / f"{preset}.json.gz", "rt", encoding="utf-8") as handle:
            data = json.load(handle)
        assert data["source_commit"] == SOURCE_COMMIT
        result[preset] = data["cases"]
    return result


@pytest.mark.parametrize(("preset", "case", "style"), CASES,
                         ids=[f"{preset}-{case}" for preset, case, _style in CASES])
def test_complete_serialized_generator_output_is_unchanged(snapshots, preset, case, style):
    assert generated(preset, case, style) == snapshots[preset][case]


def write_snapshots() -> None:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    for preset in PRESETS:
        cases = {case: generated(name, case, style) for name, case, style in CASES if name == preset}
        raw = (json.dumps({"source_commit": SOURCE_COMMIT, "cases": cases}, ensure_ascii=False,
                          indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")
        with (
            (FIXTURES / f"{preset}.json.gz").open("wb") as output,
            gzip.GzipFile(filename="", mode="wb", fileobj=output, mtime=0) as compressed,
        ):
            compressed.write(raw)
        print(preset, len(cases), "complete outputs;", len(raw), "uncompressed bytes")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", required=True, action="store_true")
    parser.parse_args()
    write_snapshots()
