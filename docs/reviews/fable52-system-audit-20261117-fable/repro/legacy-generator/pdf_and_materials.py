"""Q2 (Markdown vs PDF say the same thing) and Q7 (materials / time arithmetic).

The PDF text is taken from the reportlab story the exporter builds (no PDF text
extractor is installed); the PDF bytes are still produced by the real build().

Run: PYTHONDONTWRITEBYTECODE=1 .venv/bin/python <this file>
"""
from __future__ import annotations

import math
import sys
import warnings
from copy import deepcopy
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
warnings.filterwarnings("ignore")
from common import ALL_PARTS, PRESETS, Gauge, ShapingStyle, assert_audited_modules, manual_result  # noqa: E402
from mdcheck import parse_markdown  # noqa: E402

from reportlab.platypus import Paragraph, SimpleDocTemplate, Table  # noqa: E402

from app.models.crochet_params import refresh_derived  # noqa: E402
from app.models.materials import yarn_requirements  # noqa: E402
from app.models.time_estimate import estimate_minutes  # noqa: E402
from app.models.validator import validate_pattern  # noqa: E402
from app.ui.pattern_editor import edit_yarn  # noqa: E402
from app.utils.exporters import export_markdown  # noqa: E402
from app.utils.pdf_export import export_pdf  # noqa: E402

assert_audited_modules()
captured: list = []
_build = SimpleDocTemplate.build


def _capture(self, story, *args, **kwargs):
    captured.clear()
    captured.extend(story)
    return _build(self, story, *args, **kwargs)


SimpleDocTemplate.build = _capture


def flat_text(flowable) -> list[str]:
    if isinstance(flowable, Paragraph):
        return [flowable.getPlainText()]
    if isinstance(flowable, Table):
        out = []
        for row in flowable._cellvalues:
            cells = []
            for cell in row:
                cells.append(" ".join(flat_text(cell)) if not isinstance(cell, str) else cell)
            out.append(" | ".join(cells))
        return out
    if isinstance(flowable, (tuple, list)):  # reportlab wraps laid-out cell content
        return [text for item in flowable for text in flat_text(item)]
    return []


print("=== Markdown vs PDF: per-round rows, part notes and assembly lines ===")
cases = {
    "default": manual_result(),
    "all ring": manual_result(parts=ALL_PARTS),
    "all one-piece attached ruffle dk egg": manual_result(
        parts=ALL_PARTS, gauge=PRESETS["dk"],
        style=ShapingStyle("egg", True, "attached", True)),
    "opening 16 + part gauges": manual_result(parts=ALL_PARTS, head_opening_stitches=16,
                                              part_gauges={"帽子": PRESETS["fine"], "裙子": PRESETS["dk"]}),
}
for label, result in cases.items():
    md = export_markdown(result["params"], result["analysis"], result=result)
    pdf = export_pdf(result["params"], result["analysis"], result=result)
    assert pdf.startswith(b"%PDF") and len(pdf) > 5000
    lines = [t for f in captured for t in flat_text(f)]
    pdf_text = "\n".join(lines)
    pattern = parse_markdown(md)
    missing = []
    for part in pattern.parts:
        for row in part.rows:
            delta = f"+{row.inc}" if row.inc else (f"-{row.dec}" if row.dec else "—")
            needle = f"{row.row} | {row.stitches} | {delta} | {row.color} | {row.notes}"
            if needle not in lines:
                missing.append(f"round row {part.name} R{row.row}: {needle[:80]}")
        if part.notes and part.notes not in pdf_text:
            missing.append(f"part note {part.name}")
        opening = part.bullets.get("连接开口")
        if opening and f"连接开口：{opening}" not in pdf_text:
            missing.append(f"opening bullet {part.name}")
    for step in pattern.assembly:
        if step not in lines:
            missing.append(f"assembly step {step[:40]}")
    for item, quantity in pattern.materials:
        if f"{item} | {quantity}" not in lines:
            missing.append(f"material {item}")
    md_only = [name for name, text in (
        ("magic-ring bullet (✨ 魔法环起针)", "魔法环起针"),
        ("alternative ring start (环起困难的替代法)", "环起困难的替代法"),
        ("formula column (针法写法)", "针法写法"),
        ("skirt join table (接裙圈序示意)", "接裙圈序示意"),
        ("swatch guidance (玩偶小样)", "玩偶小样："),
        ("height guidance (试钩总高口径)", "试钩总高口径"),
    ) if text in md and text not in pdf_text]
    print(f"  {label}: {sum(len(p.rows) for p in pattern.parts)} round rows, {len(pattern.assembly)} assembly steps; "
          f"present in Markdown but not found in PDF text: {missing or 'none'}; Markdown-only sections: {md_only}")

print("\n=== yarn / time arithmetic recomputed by hand for the default doll ===")
r = cases["default"]
params = r["params"]
stitches = sum(rd["stitches"] * p.get("quantity", 1) for p in params["parts"] for rd in p["rounds"])
rounds = sum(len(p["rounds"]) * p.get("quantity", 1) for p in params["parts"])
g = PRESETS["classic"]
per_stitch = 0.08 * (10 / 13) * (10 / 16) / (0.785 * 0.625)
grams = stitches * per_stitch * 1.1
print(f"  stitches {stitches} (stored {params['total_stitches']}), physical rounds {rounds}")
print(f"  grams by hand {grams:.2f} vs summary {params['material_summary']['grams']}; "
      f"metres by hand {grams * 1.4:.2f} vs {params['material_summary']['meters']}; "
      f"=> {grams * 1.4 / stitches * 100:.1f} cm of yarn per stitch incl. 10% allowance")
print(f"  minutes by hand {max(30, round((stitches * 6.5 + rounds * 10) / 60))} vs stored {params['estimated_time_minutes']}")
print("  implied yarn per stitch by gauge (model: grams ∝ stitch area; metres/100g by stitch-width band):")
for name, gauge in {**PRESETS, "6x8": Gauge(6, 8), "40x50": Gauge(40, 50)}.items():
    cm = gauge.grams_per_stitch * gauge.meters_per_100g  # g * (m/100g) = cm
    print(f"     {name:8s} stitch {gauge.stitch_w_cm:.2f}x{gauge.row_h_cm:.2f} cm: {gauge.grams_per_stitch:.4f} g/st, "
          f"{cm:.1f} cm/st = {cm / (2 * (gauge.stitch_w_cm + gauge.row_h_cm)):.1f} x the stitch perimeter")

print("\n=== boundary inputs ===")


def try_spec(label, spec):
    try:
        out = edit_yarn(r, spec)
    except Exception as exc:  # noqa: BLE001
        print(f"  {label}: refused ({type(exc).__name__}: {str(exc)[:90]})")
        return
    s = out["params"]["material_summary"]
    finite = all(math.isfinite(float(s[k])) for k in ("grams", "meters"))
    print(f"  {label}: accepted -> {s['grams']} g, {s['meters']} m, balls {s['balls']}, finite={finite}, "
          f"validator ok={validate_pattern(out['params'])['ok']}")


base_spec = {"ball_weight_g": 50, "ball_length_m": 125, "waste_percent": 10}
try_spec("normal 50g/125m", base_spec)
try_spec("waste 100%", {**base_spec, "waste_percent": 100})
try_spec("waste -1", {**base_spec, "waste_percent": -1})
try_spec("ball weight 0", {**base_spec, "ball_weight_g": 0})
try_spec("ball weight NaN", {**base_spec, "ball_weight_g": float("nan")})
try_spec("ball length inf", {**base_spec, "ball_length_m": float("inf")})
try_spec("ball weight True", {**base_spec, "ball_weight_g": True})
try_spec("smallest accepted ball (1e-6 g, 10000 m)", {"ball_weight_g": 1e-6, "ball_length_m": 10000, "waste_percent": 10})
try_spec("swatch 1e-6 g over 1000x1000", {**base_spec, "swatch_weight_g": 1e-6, "swatch_stitches": 1000, "swatch_rows": 1000})
try_spec("swatch 2000 g over 1x1", {**base_spec, "swatch_weight_g": 2000, "swatch_stitches": 1, "swatch_rows": 1})
try_spec("swatch partial", {**base_spec, "swatch_weight_g": 5})
for bad in (float("nan"), float("inf"), 0, -5, 5.9, 40.1):
    try:
        Gauge(bad, 16)
        print(f"  Gauge({bad}, 16): ACCEPTED")
    except ValueError as exc:
        print(f"  Gauge({bad}, 16): refused ({exc})")
print("  estimate_minutes([]) =", estimate_minutes([]), "| one 1-stitch round =",
      estimate_minutes([{"name": "x", "rounds": [{"row": 1, "stitches": 1}]}]))
big = deepcopy(params)
for p in big["parts"]:
    p["quantity"] = 20
refresh_derived(big)
print(f"  all quantities 20: {big['total_stitches']} st, {big['estimated_time_minutes']} min, "
      f"{big['material_summary']['grams']} g; eyes row: "
      f"{next(m['quantity'][:8] for m in big['materials'] if m['item'] == '安全眼')}")
rows, summary = yarn_requirements(params["parts"], g)
assert abs(sum(x["grams"] for x in rows) - summary["grams"]) < 0.02
tiny = manual_result(head=4.0, height=10.0)
weights = next(m for m in tiny["params"]["materials"] if m["item"].startswith("配重珠"))
body = next(p for p in tiny["params"]["parts"] if p["name"] == "身体")
print(f"  4 cm-head doll: body is {max(x['stitches'] for x in body['rounds'])} st x {body['height_cm']} cm tall; "
      f"weight row still reads: {weights['quantity'][:22]}…; wire row: "
      f"{next(m['quantity'][:22] for m in tiny['params']['materials'] if m['item'].startswith('定型线'))}…")
