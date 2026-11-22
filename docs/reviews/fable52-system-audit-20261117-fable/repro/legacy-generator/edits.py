"""Q3/Q4: after each edit operation (the same functions the result page calls),
do round tables, assembly, materials, time, validation and exported text still
describe one pattern?  Anything stale is printed.

Run: PYTHONDONTWRITEBYTECODE=1 .venv/bin/python <this file>
"""
from __future__ import annotations

import json
import re
import sys
import warnings
from copy import deepcopy
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
warnings.filterwarnings("ignore")
from common import ALL_PARTS, PRESETS, Gauge, ShapingStyle, assert_audited_modules, manual_result  # noqa: E402
from mdcheck import check_markdown  # noqa: E402

from app.models.assembly import assembly_for_pattern  # noqa: E402
from app.models.crochet_params import refresh_derived  # noqa: E402
from app.models.gauge import gauge_for_part, gauge_from_result  # noqa: E402
from app.models.skirt_edit import move_skirt_join, waist_rows  # noqa: E402
from app.models.validator import validate_pattern  # noqa: E402
from app.services.result_logic import (  # noqa: E402
    rebuild_params,
    regenerate_with_gauge,
    regenerate_with_head_opening,
    regenerate_with_part_gauge,
    regenerate_with_size,
    regenerate_with_structure,
)
from app.ui.pattern_editor import edit_rounds, edit_structure_part, edit_yarn  # noqa: E402
from app.utils.exporters import export_markdown  # noqa: E402
from app.utils.pdf_export import export_pdf  # noqa: E402

assert_audited_modules()
DERIVED = ("materials", "material_summary", "estimated_time_minutes", "time_estimate_basis",
           "total_stitches", "shaping", "assembly_instructions")
problems: list[str] = []
ok_count = 0


def part(result, name):
    return next((p for p in result["params"]["parts"] if p["name"] == name), None)


def struct_index(result, name):
    return next(i for i, p in enumerate(result["structure"]["parts"]) if p["name"] == name)


def param_index(result, name):
    return next(i for i, p in enumerate(result["params"]["parts"]) if p["name"] == name)


def audit(label: str, result: dict, *, expect_note_drift: bool = False) -> list[str]:
    """Return human-readable inconsistencies for one result."""
    global ok_count
    out: list[str] = []
    params = result["params"]
    own = validate_pattern(params)
    if not own["ok"]:
        out.append(f"own validator fails: {own['issues'][:2]}")
        return out
    # 1. derived fields: would a refresh change anything that is stored?
    fresh = refresh_derived(deepcopy(params))
    for key in DERIVED:
        if fresh.get(key) != params.get(key):
            out.append(f"STALE params[{key!r}] (refresh_derived would change it)")
    # 2. what the exporters print as assembly vs what is stored
    if assembly_for_pattern(params) != params.get("assembly_instructions"):
        out.append("assembly_for_pattern(params) != stored assembly_instructions")
    # 3. independent read of the exported Markdown
    md = export_markdown(params, result["analysis"], result=result)
    report = check_markdown(md)
    for finding in report.errors():
        out.append(f"mdcheck {finding}")
    # 4. part-level derived numbers
    default = gauge_from_result(result)
    for p in params["parts"]:
        gauge = gauge_for_part(p, default)
        rounds = p["rounds"]
        if p.get("type") in ("cylinder", "cup", "profile") and p.get("height_cm") is not None:
            walls = [r for r in rounds if r.get("region") == "wall"]
            n = len(walls) if walls else len(rounds)
            expected = round(n * gauge.row_h_cm, 1)
            if abs(expected - p["height_cm"]) > 0.051:
                out.append(f"STALE {p['name']}.height_cm={p['height_cm']} but {n} axial rounds x "
                           f"{gauge.row_h_cm:.3f} = {expected}")
    # 5. header dimensions vs the structure the generator actually used
    head_s = next((sp for sp in result["structure"]["parts"] if sp["name"] == "头部"), None)
    if head_s and head_s.get("diameter_cm") and abs(head_s["diameter_cm"] - result["analysis"]["head_diameter_cm"]) > 1e-9:
        out.append(f"header 目标头径 {result['analysis']['head_diameter_cm']} cm but structure/parts head is "
                   f"{head_s['diameter_cm']} cm")
    # 6. hat claim
    hat, head = part(result, "帽子"), part(result, "头部") or part(result, "头身（一体）")
    if hat and head and "> 头围" in (hat.get("notes") or ""):
        hat_peak = max(r["stitches"] for r in hat["rounds"])
        head_peak = max(r["stitches"] for r in head["rounds"]) if head["name"] == "头部" else None
        if head_peak is not None and gauge_for_part(hat, default) == default and hat_peak <= head_peak:
            out.append(f"hat note claims '帽围 {hat_peak} 针 > 头围' but head widest round is {head_peak} 针")
    # 7. PDF builds
    try:
        export_pdf(params, result["analysis"], result=result)
    except Exception as exc:  # noqa: BLE001
        out.append(f"PDF export raised {type(exc).__name__}: {exc}")
    if out:
        problems.extend(f"{label}: {line}" for line in out)
    else:
        ok_count += 1
    print(("  ok   " if not out else "  !!   ") + label)
    for line in out:
        print("         - " + line[:300])
    return out


def attempt(label: str, fn, **audit_kwargs):
    try:
        result = fn()
    except Exception as exc:  # noqa: BLE001
        print(f"  --   {label}: refused -> {type(exc).__name__}: {str(exc)[:150]}")
        return None
    audit(label, result, **audit_kwargs)
    return result


print("### base results")
bases = {
    "sep-ring": manual_result(parts=ALL_PARTS, style=ShapingStyle()),
    "sep-attached": manual_result(parts=ALL_PARTS, style=ShapingStyle(skirt_style="attached")),
    "one-attached": manual_result(parts=ALL_PARTS, style=ShapingStyle(one_piece=True, skirt_style="attached", ruffle_hem=True)),
    "one-ring-egg-dk": manual_result(parts=ALL_PARTS, gauge=PRESETS["dk"],
                                     style=ShapingStyle(sphere_mode="egg", one_piece=True)),
    "opening16": manual_result(parts=ALL_PARTS, style=ShapingStyle(), head_opening_stitches=16),
    "profile-fine": manual_result(parts=ALL_PARTS, gauge=PRESETS["fine"], style=ShapingStyle(skirt_style="attached"),
                                  body_profile=[0.5, 0.55, 0.6, 0.7, 0.8, 0.9, 1.0, 1.0, 0.95, 0.9],
                                  spans={"头部": (0.0, 0.3), "身体": (0.3, 0.7)}),
}
# profile results keep their profile in geometry for regeneration, as the photo path does
bases["profile-fine"]["geometry"] = {**bases["profile-fine"]["geometry"], "silhouette": {
    "profile": [0.5, 0.55, 0.6, 0.7, 0.8, 0.9, 1.0, 1.0, 0.95, 0.9], "flare": False,
    "source": "segmentation_pipeline"}, "used_for_generation": True}
bases["profile-fine"]["spans"] = {"头部": [0.0, 0.3], "身体": [0.3, 0.7]}
for name, base in bases.items():
    audit(f"base {name}", base)

for name, base in bases.items():
    print(f"\n### edits on {name}")
    # resize (quick size panel)
    for head, height in ((6.0, 12.0), (12.0, 30.0), (9.0, 40.0), (20.0, 60.0), (4.0, 10.0)):
        attempt(f"{name} resize head={head} height={height}", lambda: regenerate_with_size(base, head, height))
    # whole-pattern gauge change (trial workspace path)
    for st, rows in ((17.0, 14.0), (20.0, 16.0), (6.0, 8.0), (40.0, 50.0)):
        attempt(f"{name} gauge {st}x{rows}", lambda: regenerate_with_gauge(base, st, rows))
    # structure edits (visual part editor)
    for target, kwargs in (
        ("头部", {"count": 1, "dimensions": {"diameter_cm": 13.0}}),
        ("头部", {"count": 1, "dimensions": {"diameter_cm": 6.0}}),
        ("身体", {"count": 1, "dimensions": {"height_cm": 12.0}}),
        ("手臂", {"count": 3, "dimensions": {}}),
        ("手臂", {"count": 1, "dimensions": {}}),
        ("腿部", {"count": 2, "dimensions": {"length_cm": 9.0}}),
        ("帽子", {"count": 1, "dimensions": {"diameter_cm": 6.0}}),
        ("裙子", {"count": 1, "dimensions": {"height_cm": 6.0}}),
        ("尾巴", {"count": 1, "dimensions": {}, "attachments": [
            {"target_part_id": "head", "target_anchor": "back", "self_anchor": "base", "method": "sewn"}]}),
        ("耳朵", {"count": 2, "dimensions": {}, "attachments": []}),
    ):
        attempt(f"{name} structure-edit {target} {json.dumps(kwargs, ensure_ascii=False)[:70]}",
                lambda: edit_structure_part(base, struct_index(base, target), **kwargs))
    # remove / add / rename a part through the structure JSON
    def without(part_name):
        s = deepcopy(base["structure"])
        s["parts"] = [p for p in s["parts"] if p["name"] != part_name]
        for p in s["parts"]:
            for inst in p.get("instances", []):
                inst["attachments"] = [a for a in inst.get("attachments", [])
                                       if a["target_part_id"] in {q["part_id"] for q in s["parts"]}]
        return s
    for removed in ("帽子", "裙子", "身体", "头部", "腿部"):
        attempt(f"{name} structure-remove {removed}", lambda: regenerate_with_structure(base, without(removed)))
    # head opening on / off
    if part(base, "头部"):
        opened = attempt(f"{name} head-opening 16", lambda: regenerate_with_head_opening(base, 16))
        if opened:
            attempt(f"{name} head-opening 16 -> closed", lambda: regenerate_with_head_opening(opened, None))
            attempt(f"{name} head-opening 16 -> resize 12/30", lambda: regenerate_with_size(opened, 12.0, 30.0))
        attempt(f"{name} head-opening 7", lambda: regenerate_with_head_opening(base, 7))
    else:
        attempt(f"{name} head-opening 16 (one-piece)", lambda: regenerate_with_head_opening(base, 16))
    # part gauge
    attempt(f"{name} part-gauge 帽子 fine", lambda: regenerate_with_part_gauge(base, "帽子", PRESETS["fine"]))
    attempt(f"{name} part-gauge 裙子 dk", lambda: regenerate_with_part_gauge(base, "裙子", PRESETS["dk"]))
    hat_fine = None
    try:
        hat_fine = regenerate_with_part_gauge(base, "帽子", Gauge(22, 24))
    except Exception:  # noqa: BLE001
        pass
    if hat_fine:
        attempt(f"{name} part-gauge 帽子 22x24 -> resize 12/30", lambda: regenerate_with_size(hat_fine, 12.0, 30.0))
        attempt(f"{name} part-gauge 帽子 22x24 -> back to default", lambda: regenerate_with_part_gauge(hat_fine, "帽子", None))
    # skirt join moves
    if base["params"].get("skirt_style") == "attached":
        choices = [r["row"] for r in waist_rows(base["params"])]
        current = base["params"]["stitch_attachments"]["connections"][0]["target_row"]
        print(f"       waist candidates {choices}, current base row {current}")
        for row in choices:
            moved = attempt(f"{name} move-skirt-join -> R{row}", lambda: move_skirt_join(base, row))
            if moved and row in (choices[0], choices[-1]):
                attempt(f"{name} move-skirt-join R{row} -> resize 12/30", lambda: regenerate_with_size(moved, 12.0, 30.0))
                attempt(f"{name} move-skirt-join R{row} -> gauge dk", lambda: regenerate_with_gauge(moved, 17.0, 14.0))
    # yarn spec
    attempt(f"{name} yarn-spec with swatch", lambda: edit_yarn(base, {
        "ball_weight_g": 50, "ball_length_m": 125, "waste_percent": 15,
        "swatch_weight_g": 4.2, "swatch_stitches": 20, "swatch_rows": 20}))
    # round-table edits
    for target in ("手臂", "身体", "头部", "帽子", "裙子", "头身（一体）"):
        if not part(base, target):
            continue
        idx = param_index(base, target)
        rounds = deepcopy(base["params"]["parts"][idx]["rounds"])
        last = rounds[-1]
        prev = rounds[-2]["stitches"]
        if last.get("decrease"):
            # close two stitches fewer on the last round: opening grows by 2
            last["decrease"] -= 2
            last["stitches"] = prev - last["decrease"]
            attempt(f"{name} round-edit {target}: last round {prev}->{last['stitches']}",
                    lambda: edit_rounds(base, idx, rounds), expect_note_drift=True)
        else:
            last["increase"] = last.get("increase", 0) + 6 if not last.get("allow_wide_jump") else last["increase"]
            last["stitches"] = prev + last["increase"]
            attempt(f"{name} round-edit {target}: last round {prev}->{last['stitches']}",
                    lambda: edit_rounds(base, idx, rounds), expect_note_drift=True)

print("\n### params-JSON edits (advanced editor path: rebuild_params) on sep-ring")
base = bases["sep-ring"]


def json_edit(mutator):
    candidate = deepcopy(base)
    corrected = json.loads(json.dumps(base["params"], ensure_ascii=False))
    mutator(corrected)
    candidate["params"] = rebuild_params(corrected, previous=base["params"], structure=base["structure"])
    candidate["gauge"] = candidate["params"].get("gauge")
    return candidate


def drop(name):
    def run(p):
        p["parts"] = [x for x in p["parts"] if x["name"] != name]
    return run


def rename(old, new):
    def run(p):
        for x in p["parts"]:
            if x["name"] == old:
                x["name"] = new
    return run


def quantity(name, n):
    def run(p):
        for x in p["parts"]:
            if x["name"] == name:
                x["quantity"] = n
    return run


def drop_rounds(name, rows):
    def run(p):
        for x in p["parts"]:
            if x["name"] == name:
                x["rounds"] = [r for r in x["rounds"] if r["row"] not in rows]
    return run


no_hat = attempt("json drop 帽子", lambda: json_edit(drop("帽子")))
renamed = attempt("json rename 手臂->胳膊", lambda: json_edit(rename("手臂", "胳膊")))
attempt("json quantity 腿部=3", lambda: json_edit(quantity("腿部", 3)))
attempt("json drop 身体", lambda: json_edit(drop("身体")))
attempt("json drop 头部", lambda: json_edit(drop("头部")))
# shorten the head by deleting two plain widest rounds including the eye round
short_head = attempt("json delete head rounds 13,14 (the eye round)", lambda: json_edit(drop_rounds("头部", {13, 14})))
if short_head:
    notes = part(short_head, "头部")["notes"]
    rows = [r["row"] for r in part(short_head, "头部")["rounds"]]
    print("       head notes after deletion:", re.search(r"第 \d+ 圈安装安全眼", notes)[0], "| rows now:", rows)
print("\n### does a later geometry edit keep a params-JSON deletion / rename?")
for label, edited in (("after json drop 帽子", no_hat), ("after json rename 手臂->胳膊", renamed)):
    if not edited:
        continue
    resized = regenerate_with_size(edited, 9.0, 20.0)
    print(f"   {label}: parts before resize {[p['name'] for p in edited['params']['parts']]}")
    print(f"   {' ' * len(label)}  parts after  resize {[p['name'] for p in resized['params']['parts']]}")

print(f"\nSUMMARY: {ok_count} audited results consistent; {len(problems)} inconsistency lines")
kinds: dict[str, int] = {}
for line in problems:
    key = re.sub(r"\d+(\.\d+)?", "N", line.split(": ", 1)[1])[:90]
    kinds[key] = kinds.get(key, 0) + 1
for key, n in sorted(kinds.items(), key=lambda kv: -kv[1]):
    print(f"  {n:4d}  {key}")
