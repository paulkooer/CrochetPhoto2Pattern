"""Exploratory local-only comparison of public photos with their source patterns.

Images are supplied locally and are never embedded in the report. This is not
an authorized release dataset or a physical trial. No source pattern text is copied.
Run from repository root with: .venv/bin/python -m scripts.probe_public_pairs --help
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import patch

from app.models.orchestrator import PipelineOrchestrator
from app.models.validator import validate_pattern
from app.utils.images import MAX_UPLOAD_MB, load_image_bytes

CASES: dict[str, dict[str, Any]] = {
    "akihiro": {
        "page_url": "https://www.clover-mfg.com/en/project/amigurumi-akihiro-crochet-pattern/",
        "image_url": "https://www.clover-mfg.com/wp-content/uploads/2023/08/Amigurumi-AKIHIRO-Crochet-Pattern.jpg",
        "publisher": "Clover / Maria Atelier",
        "visible_parts": ["头部", "身体", "手臂", "腿部", "耳朵", "尾巴"],
        "construction_observation": ("Joined legs continue into body and head; "
                                     "arms, ears and tail attach separately."),
        "target_height_cm": 26,
        "target_basis": "source_declared_finished_height",
    },
    "bunny": {
        "page_url": "https://53stitches.com/low-sew-bunny-free-crochet-pattern/",
        "image_url": "https://53stitches.com/wp-content/uploads/2026/04/pasted-image-48-1024x819.jpeg",
        "publisher": "53stitches",
        "visible_parts": ["头部", "身体", "手臂", "腿部", "耳朵"],
        "construction_observation": ("Continuous main form with popcorn limbs; "
                                     "separate ears; carrot accessory."),
        "target_height_cm": 18,
        "target_basis": "application_default_not_source_measurement",
    },
}


def probe(name: str, path: Path, reference: dict | None = None) -> dict:
    reference = CASES[name] if reference is None else reference
    with path.open("rb") as handle:
        raw = handle.read(MAX_UPLOAD_MB * 1024 * 1024 + 1)
    image = load_image_bytes(raw)
    if image is None:
        raise ValueError(f"Cannot decode {path}")
    # No dotenv credentials, paid vision calls or pose-weight downloads.
    with patch.dict(
        os.environ, {"OPENAI_API_KEY": "", "ANTHROPIC_API_KEY": "",
                     "CROCHET_POSE_MODEL": str(path.parent / "disabled-public-pair-pose.task")}
    ), patch("app.models.pose.get_body_landmarks", return_value=None):
        result = PipelineOrchestrator().run_full_pipeline(
            image, vision_mode="local", target_height_cm=reference["target_height_cm"],
            target_height_source="public_pair_probe")
    actual = set(result["analysis"]["parts"])
    expected = set(reference["visible_parts"])
    scored = reference.get("evaluation_group", "single_animal") == "single_animal" and bool(expected)
    return {
        "id": name, "reference": reference, "sha256": hashlib.sha256(raw).hexdigest(),
        "image_size": list(image.size), "vision_meta": result["vision_meta"],
        "analysis": result["analysis"],
        "part_metrics_applicable": scored,
        "missing_visible_parts": sorted(expected - actual) if scored else None,
        "unexpected_parts": sorted(actual - expected) if scored else None,
        "visible_part_recall": len(expected & actual) / len(expected) if scored else None,
        "visible_part_precision": len(expected & actual) / len(actual) if scored and actual else None,
        "canonical_parts_exact": actual == expected if scored else None,
        "status": "completed",
        "generated_parts": [{"name": p["name"], "quantity": p.get("quantity", 1),
                             "type": p.get("type"), "round_count": len(p["rounds"]),
                             "colors": sorted({r.get("color") or p.get("color", "") for r in p["rounds"]})}
                            for p in result["params"]["parts"]],
        "pattern_validation": validate_pattern(result["params"]),
        "physical_trial": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in CASES:
        parser.add_argument(f"--{name}", type=Path)
    parser.add_argument("--catalog", type=Path, help="Versioned reference metadata JSON")
    parser.add_argument("--image-dir", type=Path, help="Local downloaded images named by catalog image_file")
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    if args.catalog:
        if not args.image_dir or any(getattr(args, name) for name in CASES):
            parser.error("--catalog requires --image-dir and cannot mix legacy per-image flags")
        catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
        references = catalog["cases"]
        if not references:
            parser.error("catalog must contain cases")
        paths = {}
        for name, ref in references.items():
            filename = ref["image_file"]
            if Path(filename).name != filename:
                parser.error("image_file must be a filename without directories")
            paths[name] = args.image_dir / filename
    else:
        if args.image_dir or not all(getattr(args, name) for name in CASES):
            parser.error("provide both --akihiro and --bunny, or --catalog and --image-dir")
        references = CASES
        paths = {name: getattr(args, name) for name in CASES}
    cases = []
    for name, reference in references.items():
        try:
            case = probe(name, paths[name], reference)
        except Exception as exc:
            case = {"id": name, "reference": reference, "status": "error",
                    "error": {"type": type(exc).__name__, "message": str(exc)}}
        cases.append(case)
    completed = [c for c in cases if c["status"] == "completed"]
    scored = [c for c in completed if c["part_metrics_applicable"]]
    source_hash = hashlib.sha256()
    root = Path(__file__).resolve().parents[1]
    for path in sorted((root / "app").rglob("*.py")):
        source_hash.update(str(path.relative_to(root)).encode() + b"\0" + path.read_bytes() + b"\0")
    report: dict[str, Any] = {
        "kind": "exploratory_public_photo_pattern_pairs",
        "created_at": datetime.now(UTC).isoformat(), "app_source_sha256": source_hash.hexdigest(),
        "mode": "local_vision_pose_disabled", "release_evidence": False,
        "rights_status": "public_source_reference_only_no_redistribution_permission_asserted",
        "python_version": platform.python_version(),
        "probe_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "catalog_sha256": hashlib.sha256(args.catalog.read_bytes()).hexdigest() if args.catalog else None,
        "scope": "Manually selected development cases; not a held-out benchmark. "
                 "Visible semantic parts are distinct from separately crocheted pieces. "
                 "Pattern instructions were not supplied to the pipeline. Gauge was not calibrated.",
        "summary": {
            "requested": len(cases), "completed": len(completed), "errors": len(cases) - len(completed),
            "unique_image_hashes": len({c["sha256"] for c in completed}),
            "canonical_part_scored_cases": len(scored),
            "canonical_parts_exact_cases": sum(c["canonical_parts_exact"] for c in scored),
            "pattern_valid_cases": sum(c["pattern_validation"]["ok"] for c in completed),
            "boundary_cases_completed": len(completed) - len(scored),
        },
        "cases": cases,
    }
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False))
    for case in report["cases"]:
        if case["status"] == "error":
            print(case["id"], case["error"])
            continue
        print(case["id"], "missing=", case["missing_visible_parts"],
              "extra=", case["unexpected_parts"], "vision=", case["vision_meta"],
              "valid=", case["pattern_validation"]["ok"])


if __name__ == "__main__":
    main()
