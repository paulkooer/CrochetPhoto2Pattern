"""Q1-Q3: generate a spread of legacy-doll specs through the public generator and
read every exported Markdown round table with the independent checker (mdcheck).

Run: PYTHONDONTWRITEBYTECODE=1 .venv/bin/python <this file>   (prints a summary;
full per-spec findings go to out_sweep_findings.txt in the scratch dir)
"""
from __future__ import annotations

import sys
from collections import Counter, defaultdict
from itertools import product
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import ALL_PARTS, PRESETS, SCRATCH, Gauge, ShapingStyle, assert_audited_modules, manual_result  # noqa: E402
from mdcheck import check_markdown  # noqa: E402

from app.models.crochet_params import PatternGenerationError  # noqa: E402
from app.models.crochetability import crochetability_findings  # noqa: E402
from app.models.validator import validate_pattern  # noqa: E402
from app.utils.exporters import export_markdown  # noqa: E402

assert_audited_modules()

BASIC = ["头部", "身体", "手臂", "腿部"]
specs: list[tuple[str, dict]] = []


def add(label: str, **kwargs) -> None:
    specs.append((label, kwargs))


# A. default doll x gauge x sphere mode
for preset, mode in product(PRESETS, ("ladder", "ideal", "egg")):
    add(f"A basic {preset} {mode}", parts=BASIC, gauge=PRESETS[preset], style=ShapingStyle(sphere_mode=mode))
# B. all parts x full style matrix x gauge
for preset, mode, one_piece, skirt, ruffle in product(
        PRESETS, ("ladder", "ideal", "egg"), (False, True), ("ring", "attached"), (False, True)):
    add(f"B all {preset} {mode} onepiece={int(one_piece)} skirt={skirt} ruffle={int(ruffle)}",
        parts=ALL_PARTS, gauge=PRESETS[preset],
        style=ShapingStyle(mode, one_piece, skirt, ruffle))
# C. sizes x gauges (incl. extremes of the accepted gauge range)
GAUGES = {"classic": PRESETS["classic"], "dk": PRESETS["dk"], "fine": PRESETS["fine"],
          "g6x8": Gauge(6, 8), "g40x50": Gauge(40, 50), "g6x50": Gauge(6, 50), "g40x8": Gauge(40, 8),
          "g25x25": Gauge(25, 25), "g13.5x17.5": Gauge(13.5, 17.5)}
for (head, height), (gname, gauge) in product(
        ((4, 10), (6, 12), (9, 18), (9, 60), (14, 30), (20, 20), (20, 60), (4, 60), (12.5, 31.5)), GAUGES.items()):
    for one_piece in (False, True):
        add(f"C size head={head} height={height} {gname} onepiece={int(one_piece)}", head=head, height=height,
            parts=ALL_PARTS, gauge=gauge, style=ShapingStyle(one_piece=one_piece, skirt_style="attached"))
# D. head opening
for preset, mode, opening in product(PRESETS, ("ladder", "ideal", "egg"), (6, 7, 12, 16, 17, 23, 24, 30, 36, 48)):
    add(f"D opening={opening} {preset} {mode}", parts=BASIC, gauge=PRESETS[preset],
        style=ShapingStyle(sphere_mode=mode), head_opening_stitches=opening)
# E. part-specific gauges (hat / ring skirt)
for base, hat, skirt in (("classic", "fine", "dk"), ("fine", "classic", "classic"), ("dk", "g40x50", "g6x8")):
    add(f"E part gauges base={base} hat={hat} skirt={skirt}", parts=ALL_PARTS, gauge=GAUGES[base],
        style=ShapingStyle(), part_gauges={"帽子": GAUGES[hat], "裙子": GAUGES[skirt]})
# F. photo-profile body (+ colour bands, to see colour notes do not break instructions)
PROFILES = {
    "pear": [0.5, 0.55, 0.6, 0.7, 0.8, 0.9, 1.0, 1.0, 0.95, 0.9],
    "hourglass": [0.9, 1.0, 0.8, 0.5, 0.4, 0.5, 0.8, 1.0, 0.9, 0.7],
    "cone": [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
    "spiky": [1.0, 0.1, 1.0, 0.1, 1.0, 0.1, 1.0, 0.1, 1.0, 0.1],
    "flat": [1.0] * 10,
    "thin": [0.05, 0.05, 0.05, 1.0, 0.05, 0.05, 0.05, 0.05, 0.05, 0.05],
}
BANDS = [{"start": 0.0, "end": 0.4, "color": "红色"}, {"start": 0.4, "end": 1.0, "color": "蓝色"}]
for (pname, profile), preset, one_piece, skirt in product(
        PROFILES.items(), PRESETS, (False, True), ("ring", "attached")):
    add(f"F profile={pname} {preset} onepiece={int(one_piece)} skirt={skirt}", parts=ALL_PARTS,
        gauge=PRESETS[preset], style=ShapingStyle(one_piece=one_piece, skirt_style=skirt),
        body_profile=profile, color_bands=BANDS, spans={"头部": (0.0, 0.3), "身体": (0.3, 0.7)})
for pname, opening in product(("pear", "hourglass"), (12, 16)):
    add(f"F profile={pname} opening={opening}", parts=BASIC, body_profile=PROFILES[pname],
        head_opening_stitches=opening)
# G. part subsets (missing body / head / lone accessories)
for subset in (["头部"], ["身体"], ["头部", "身体"], ["头部", "帽子", "耳朵"], ["身体", "裙子", "尾巴"],
               ["手臂", "腿部"], ["帽子"], ["裙子"], ["头部", "裙子"], ["头部", "身体", "裙子"]):
    for skirt in ("ring", "attached"):
        add(f"G subset={'+'.join(subset)} skirt={skirt}", parts=subset, style=ShapingStyle(skirt_style=skirt))

by_code: dict[str, list[str]] = defaultdict(list)
status = Counter()
rejected: dict[str, list[str]] = defaultdict(list)
lines: list[str] = []
totals = Counter()
checked_specs = 0
for label, kwargs in specs:
    try:
        result = manual_result(**kwargs)
    except (ValueError, PatternGenerationError) as exc:
        status["rejected"] += 1
        rejected[f"{type(exc).__name__}: {str(exc)[:110]}"].append(label)
        continue
    params = result["params"]
    own = validate_pattern(params)
    assert own["ok"], (label, own["issues"])
    blocking = [f.message for f in crochetability_findings(params) if f.level == "block"]
    md = export_markdown(params, result["analysis"], result=result)
    report = check_markdown(md)
    checked_specs += 1
    status["generated"] += 1
    if blocking:
        status["generated_but_blocked_by_crochetability_gate"] += 1
    totals["rows"] += report.stats["rows"]
    totals["formulas_expanded"] += report.stats["expanded"]
    totals["parts"] += len(report.pattern.parts)
    for key, value in report.stats["closings"].items():
        totals[f"finish:{key}"] += value
    for flag in ("neck_anchor_checked", "skirt_anchor_checked"):
        totals[flag] += bool(report.stats.get(flag))
    lines.append(f"## {label}" + ("   [would be blocked by crochetability gate]" if blocking else ""))
    for finding in report.findings:
        by_code[f"{finding.level} {finding.code}"].append(f"{label} :: {finding}")
        lines.append("   " + str(finding))

(SCRATCH / "out_sweep_findings.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"specs={len(specs)} {dict(status)}")
print("checked:", dict(totals))
print("\nrejections (message -> count, first label):")
for message, labels in sorted(rejected.items(), key=lambda kv: -len(kv[1])):
    print(f"  {len(labels):4d}  {message}   e.g. {labels[0]}")
print("\nfindings by code (count, distinct parts, first two examples):")
for code, items in sorted(by_code.items()):
    print(f"  {len(items):5d}  {code}")
    for item in items[:2]:
        print("          ", item[:230])
errors = sum(len(v) for k, v in by_code.items() if k.startswith("ERROR"))
print(f"\nERROR findings: {errors}")
