"""Measure synthetic material refresh time and compare complete output hashes."""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import platform
import statistics
import sys
import time
from copy import deepcopy
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--parts", type=int, default=3)
    parser.add_argument("--rounds-per-part", type=int, default=50)
    parser.add_argument("--samples", type=int, default=11)
    args = parser.parse_args()
    if (not 1 <= args.parts <= 64 or not 1 <= args.rounds_per_part <= 2000
            or args.parts * args.rounds_per_part > 16000 or not 1 <= args.samples <= 100):
        parser.error("Use 1–64 parts, 1–2000 rounds/part, at most 16000 rounds and 1–100 samples")
    source_root = args.source_root.resolve()
    source_files = [source_root / "app/models/crochet_params.py", source_root / "app/models/materials.py"]
    if not all(path.is_file() for path in source_files):
        parser.error("source root must contain the app source tree")
    sys.path.insert(0, str(source_root))
    refresh = importlib.import_module("app.models.crochet_params").refresh_derived
    original = {
        "parts": [
            {"name": f"测试部件{part}", "type": "cylinder", "quantity": 1,
             "color": "红色", "rounds": [
                 {"row": i + 1, "stitches": 6, "increase": 0, "decrease": 0,
                  "color": "红色" if i // 50 % 2 == 0 else "蓝色", "notes": None}
                 for i in range(args.rounds_per_part)]}
            for part in range(args.parts)],
        "gauge": {"stitches_per_10cm": 26, "rows_per_10cm": 28},
        "yarn_spec": {"ball_weight_g": 50, "ball_length_m": 125, "swatch_weight_g": 5,
                      "swatch_stitches": 10, "swatch_rows": 10,
                      "swatch_gauge": {"stitches_per_10cm": 26, "rows_per_10cm": 28}},
    }
    times = []
    digests = set()
    for i in range(args.samples + 2):
        data = deepcopy(original)
        started = time.perf_counter()
        refresh(data)
        elapsed = time.perf_counter() - started
        payload = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        digests.add(hashlib.sha256(payload.encode()).hexdigest())
        if i >= 2:
            times.append(elapsed)
    print(json.dumps({"source_root": str(source_root), "python": platform.python_version(),
                      "source_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                        for p in source_files},
                      "parts": args.parts, "rounds": args.parts * args.rounds_per_part,
                      "samples": args.samples, "median_ms": round(statistics.median(times) * 1000, 3),
                      "output_sha256": sorted(digests)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
