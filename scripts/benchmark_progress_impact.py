"""Measure progress-preview time on synthetic patterns and hash the complete report."""
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
    parser.add_argument("--copies", type=int, default=2)
    parser.add_argument("--completed", choices=("one", "all"), default="one")
    parser.add_argument("--samples", type=int, default=3)
    args = parser.parse_args()
    if (not 1 <= args.parts <= 64 or not 1 <= args.rounds_per_part <= 2000
            or args.parts * args.rounds_per_part > 16000 or not 1 <= args.copies <= 20
            or not 1 <= args.samples <= 30):
        parser.error("Use 1–64 parts, 1–2000 rounds/part, at most 16000 rounds, 1–20 copies and 1–30 samples")
    source_root = args.source_root.resolve()
    source_file = source_root / "app/ui/progress_state.py"
    if not source_file.is_file():
        parser.error("source root must contain the app source tree")
    sys.path.insert(0, str(source_root))
    module = importlib.import_module("app.ui.progress_state")
    parts = [{"name": f"部件{i}", "type": "cylinder", "quantity": args.copies, "color": "红色",
              "rounds": [{"row": row + 1, "stitches": 6, "notes": "6X"}
                         for row in range(args.rounds_per_part)]} for i in range(args.parts)]
    current = {"result_id": "benchmark", "structure": {"parts": []}, "params": {"parts": parts}}
    updated = deepcopy(current)
    progress = ({identity: True for identity, _, _ in module.progress_entries(current, "result")}
                if args.completed == "all" else {json.dumps(["部件0", "copy1", 1], ensure_ascii=False): True})
    times = []
    digests = set()
    for i in range(args.samples + 1):
        started = time.perf_counter()
        report = module.progress_impact(current, updated, "result", progress)
        elapsed = time.perf_counter() - started
        digests.add(hashlib.sha256(json.dumps(report, ensure_ascii=False, sort_keys=True,
                                             separators=(",", ":")).encode()).hexdigest())
        if i:
            times.append(elapsed)
    print(json.dumps({"source_root": str(source_root), "python": platform.python_version(),
                      "source_sha256": hashlib.sha256(source_file.read_bytes()).hexdigest(),
                      "rounds": args.parts * args.rounds_per_part, "copies_per_part": args.copies,
                      "completed": args.completed, "samples": args.samples,
                      "median_ms": round(statistics.median(times) * 1000, 3),
                      "report_sha256": sorted(digests)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
