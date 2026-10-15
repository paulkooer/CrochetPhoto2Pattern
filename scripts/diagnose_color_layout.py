"""Original synthetic counterexamples for horizontal-band color compression.

No third-party pixels or pattern instructions are used. The mask is supplied
exactly to isolate representation loss from foreground-segmentation quality.
Run: python -m scripts.diagnose_color_layout --out /tmp/color-layout.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from app.models.color_design import vertical_color_bands
from app.models.color_observation import ColorObservation
from app.models.subject import SubjectObservation


def diagnose() -> dict:
    images = []
    for rectangles in (
        [(30, 40, 45, 79), (110, 40, 125, 79)],
        [(64, 40, 95, 79)],
    ):
        image = Image.new("RGB", (160, 160), "white")
        draw = ImageDraw.Draw(image)
        for rectangle in rectangles:
            draw.rectangle(rectangle, fill="black")
        images.append(image)
    cases = []
    for name, image in zip(("two_separate_patches", "one_center_patch"), images, strict=True):
        subject = SubjectObservation(image)
        subject.__dict__["segmentation"] = (np.ones((160, 160), dtype=bool), image)
        evidence = {}
        bands = vertical_color_bands(image, subject=subject, observation=evidence)
        pixels = np.asarray(image)
        cases.append({
            "id": name, "pixel_sha256": hashlib.sha256(image.tobytes()).hexdigest(),
            "black_pixels": int(np.all(pixels == 0, axis=2).sum()),
            "bands": bands,
            "observation": evidence,
            "requires_review": ColorObservation.model_validate(evidence).requires_review,
            "black_preserved_in_output": any(b["color"] == "黑色" for b in bands),
        })
    return {
        "kind": "original_synthetic_representation_counterexample", "schema_version": 2,
        "source_images_used": False, "release_evidence": False,
        "mask": "perfect_all_foreground_supplied_to_isolate_color_compression",
        "cases": cases,
        "distinct_pixels": cases[0]["pixel_sha256"] != cases[1]["pixel_sha256"],
        "identical_band_outputs": cases[0]["bands"] == cases[1]["bands"],
        "distinct_region_outputs": cases[0]["observation"]["regions"] != cases[1]["observation"]["regions"],
        "interpretation": "Horizontal majority bands discard minority patches and horizontal positions. "
                          "Spatial observations preserve patches separately from stitch instructions. "
                          "This diagnoses representation, not real-photo accuracy or improved segmentation.",
        "color_observation_sha256": hashlib.sha256(
            (Path(__file__).resolve().parents[1] / "app/models/color_observation.py").read_bytes()
        ).hexdigest(),
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "color_design_sha256": hashlib.sha256(
            (Path(__file__).resolve().parents[1] / "app/models/color_design.py").read_bytes()).hexdigest(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    report = diagnose()
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
