"""Compare coarse and refined bands on original narrow-stripe fixtures.

Run: .venv/bin/python -m scripts.diagnose_color_stripes --out /tmp/stripes.json
No downloaded images, external model calls or third-party pattern text are used.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from app.models.color_design import vertical_color_bands
from app.models.subject import SubjectObservation


def diagnose() -> dict:
    cases = []
    for height in (100, 137, 160):
        for start in (31, 45, 62):
            image = Image.new("RGB", (100, height), "white")
            ImageDraw.Draw(image).rectangle((0, start, 99, start + 3), fill="black")
            subject = SubjectObservation(image)
            subject.__dict__["segmentation"] = (np.ones((height, 100), dtype=bool), image)
            expected = [{"start": start / height, "end": (start + 4) / height, "color": "黑色"}]
            outcomes = {}
            for name, refine in (("baseline", False), ("refined", True)):
                bands = vertical_color_bands(image, subject=subject, refine_stripes=refine)
                outcomes[name] = {
                    "bands": bands,
                    "stripe_exact": [b for b in bands if b["color"] == "黑色"] == expected,
                }
            cases.append({"id": f"h{height}_y{start}", "pixel_sha256":
                          hashlib.sha256(image.tobytes()).hexdigest(), "size": list(image.size),
                          "expected_stripe": expected, **outcomes})
    root = Path(__file__).resolve().parents[1]
    return {
        "schema_version": 1, "kind": "original_synthetic_narrow_stripe_comparison",
        "source_images_used": False, "release_evidence": False, "calibration_allowed": False,
        "mask": "perfect_all_foreground_to_isolate_band_resolution",
        "scope": "Development counterexamples, not held-out real-photo accuracy or physical trials. "
                 "Tests additionally cover noise, sparse masks, minority patches and evidence preservation.",
        "summary": {"cases": len(cases), **{
            f"{name}_stripe_exact": sum(c[name]["stripe_exact"] for c in cases)
            for name in ("baseline", "refined")}},
        "cases": cases,
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "color_design_sha256": hashlib.sha256(
            (root / "app/models/color_design.py").read_bytes()).hexdigest(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    report = diagnose()
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"]))


if __name__ == "__main__":
    main()
