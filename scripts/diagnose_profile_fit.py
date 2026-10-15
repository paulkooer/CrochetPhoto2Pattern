"""Compare original synthetic silhouettes against the former greedy clamp.

Run: .venv/bin/python -m scripts.diagnose_profile_fit --out /tmp/profile-fit.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from app.models.gauge import PRESETS, next_shaping_stitch_count
from app.models.profile_shaping import _sample_at, _smooth3, profile_to_rounds


def diagnose() -> dict:
    cases = []
    for name, profile in (
        ("straight", [1.0] * 40),
        ("shoulder", [0.2] * 20 + [1.0] * 20),
        ("waist", [1.0] * 12 + [0.2] * 16 + [1.0] * 12),
    ):
        for gauge_name, gauge in PRESETS.items():
            for direction in ("bottom_up", "top_down"):
                height, reference = 6.0, 60
                n = max(3, gauge.rounds_for_height(height))
                raw = [_sample_at(profile, (j + 0.5) / n) for j in range(n)]
                targets = [max(6, round(v * reference / 6) * 6)
                           for v in _smooth3([v / max(raw) for v in raw])]
                if direction == "bottom_up":
                    targets.reverse()
                baseline = [targets[0]]
                for target in targets[1:]:
                    baseline.append(next_shaping_stitch_count(
                        baseline[-1], target, gauge.max_shaping_change))
                refined = profile_to_rounds(
                    profile, (0, 1), height, gauge, reference, direction=direction)
                errors = [sum((a - b) ** 2 for a, b in zip(seq, targets, strict=True))
                          for seq in (baseline, refined)]
                feasible = all(abs(b - a) <= gauge.max_shaping_change
                               and b <= 2 * a and 2 * b >= a
                               for a, b in zip(refined, refined[1:], strict=False))
                assert feasible and errors[1] <= errors[0]
                cases.append({"id": f"{name}_{gauge_name}_{direction}",
                              "profile": profile, "height_cm": height,
                              "reference_stitches": reference, "targets": targets,
                              "greedy": baseline, "global_fit": refined,
                              "greedy_squared_error": errors[0],
                              "global_squared_error": errors[1], "feasible": feasible})
    root = Path(__file__).resolve().parents[1]
    return {
        "schema_version": 1, "kind": "original_synthetic_profile_fit_comparison",
        "source_images_used": False, "release_evidence": False, "calibration_allowed": False,
        "scope": "Squared stitch-count error against smoothed, quantized silhouettes. "
                 "First round fixed. No photo recognition or physical accuracy claim.",
        "cases": cases,
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "source_sha256": {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                          for name in ("app/models/profile_shaping.py", "app/models/gauge.py")},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report = diagnose()
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for case in report["cases"]:
        print(case["id"], case["greedy_squared_error"], case["global_squared_error"])


if __name__ == "__main__":
    main()
