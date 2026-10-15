"""Original interval fixtures comparing midpoint and overlap round allocation.

Run: .venv/bin/python -m scripts.diagnose_round_colors --out /tmp/round-colors.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from app.models.color_design import round_color, round_color_plan


def diagnose() -> dict:
    fixtures = [
        ("midpoint_sliver", 10, [(0, 0.049, "白色"), (0.049, 0.051, "黑色"), (0.051, 1, "白色")]),
        ("three_colors_one_round", 1, [(0, 0.3, "白色"), (0.3, 0.55, "黑色"), (0.55, 1, "红色")]),
        ("resolvable_stripe", 10, [(0, 0.3, "白色"), (0.3, 0.4, "黑色"), (0.4, 1, "红色")]),
    ]
    cases = []
    for name, n, blocks in fixtures:
        baseline = [round_color((j + 0.5) / n, blocks) for j in range(n)]
        refined, omitted = round_color_plan(blocks, (0, 1), n)

        def mismatch(colors, n=n, blocks=blocks):
            matched = sum(max(0, min(e, (j + 1) / n) - max(s, j / n))
                          for j, color in enumerate(colors) for s, e, name in blocks if name == color)
            return round(1 - matched, 12)

        cases.append({"id": name, "rounds": n, "blocks": blocks,
                      "midpoint_colors": baseline, "overlap_colors": refined,
                      "midpoint_mismatched_height": mismatch(baseline),
                      "overlap_mismatched_height": mismatch(refined),
                      "unrepresented_blocks": omitted})
    root = Path(__file__).resolve().parents[1]
    return {
        "schema_version": 1, "kind": "original_synthetic_round_color_comparison",
        "source_images_used": False, "release_evidence": False, "calibration_allowed": False,
        "scope": "Equal-height round intervals, perfect supplied color boundaries. "
                 "Minimizes vertical color mismatch, not stripe count or physical resemblance. "
                 "No real photos, 3D reconstruction or stitch-density calibration.",
        "cases": cases,
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "source_sha256": {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                          for name in ("app/models/color_design.py", "app/models/crochet_params.py")},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report = diagnose()
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for case in report["cases"]:
        print(case["id"], case["midpoint_mismatched_height"], case["overlap_mismatched_height"])


if __name__ == "__main__":
    main()
