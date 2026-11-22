"""Q5/Q6: construction_guidance_version behaviour and the refreshed snapshot fixtures.

Baseline fixtures are read with `git show ba8ee24:...` into this scratch directory
(read-only git).  No baseline code is executed.

Run: PYTHONDONTWRITEBYTECODE=1 .venv/bin/python <this file>
"""
from __future__ import annotations

import gzip
import io
import json
import subprocess
import sys
import warnings
from collections import Counter
from copy import deepcopy
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
warnings.filterwarnings("ignore")
from common import REPO, SCRATCH, assert_audited_modules  # noqa: E402
from mdcheck import check_markdown  # noqa: E402

from app.models.crochet_params import refresh_derived  # noqa: E402
from app.models.structure_designer import StructureDesigner  # noqa: E402
from app.models.validator import validate_pattern  # noqa: E402
from app.schemas import PART_NAMES, ImageAnalysis, PatternResult  # noqa: E402
from app.services.result_logic import (  # noqa: E402
    import_backup,
    rebuild_params,
    regenerate_with_size,
)
from app.ui.pattern_editor import edit_rounds, edit_yarn  # noqa: E402
from app.utils.exporters import export_markdown  # noqa: E402

assert_audited_modules()
BASE, HEAD = "ba8ee248e97497407ae86bfc46e6c49e2d288299", "6c88b7df5d53c18d4c8190288419faeb02cc1b13"
assert subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"], capture_output=True, text=True,
                      check=True).stdout.strip() == HEAD


def fixture(commit: str, preset: str) -> dict:
    raw = subprocess.run(["git", "-C", str(REPO), "show", f"{commit}:tests/fixtures/generate_params/{preset}.json.gz"],
                         capture_output=True, check=True).stdout
    return json.load(io.TextIOWrapper(gzip.GzipFile(fileobj=io.BytesIO(raw)), encoding="utf-8"))


old = {p: fixture(BASE, p) for p in ("classic", "dk", "fine")}
new = {p: fixture(HEAD, p) for p in ("classic", "dk", "fine")}
for preset in old:
    on_disk = json.load(gzip.open(REPO / f"tests/fixtures/generate_params/{preset}.json.gz", "rt", encoding="utf-8"))
    assert on_disk == new[preset], "worktree fixture differs from HEAD"
print("fixture revisions:", {p: old[p].get("revision") for p in old}, "->", {p: new[p]["revision"] for p in new})
print("cases per preset:", {p: len(new[p]["cases"]) for p in new}, "total", sum(len(new[p]["cases"]) for p in new))


def walk(a, b, path=""):
    """Yield (path, old, new) for every differing leaf."""
    if isinstance(a, dict) and isinstance(b, dict):
        for key in sorted(set(a) | set(b)):
            if key not in a:
                yield f"{path}/{key}", "<absent>", b[key]
            elif key not in b:
                yield f"{path}/{key}", a[key], "<absent>"
            else:
                yield from walk(a[key], b[key], f"{path}/{key}")
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            yield path + "[len]", len(a), len(b)
        for i, (x, y) in enumerate(zip(a, b)):
            yield from walk(x, y, f"{path}[{i}]")
    elif a != b:
        yield path, a, b


print("\n=== Q6. every one of the 102 refreshed snapshot cases: baseline vs audited ===")
import re  # noqa: E402

kinds = Counter()
samples: dict[str, tuple] = {}
round_diffs = 0
for preset in old:
    assert set(old[preset]["cases"]) == set(new[preset]["cases"])
    for case in old[preset]["cases"]:
        a, b = old[preset]["cases"][case], new[preset]["cases"][case]
        for path, x, y in walk(a, b):
            generic = re.sub(r"\[\d+\]", "[]", path)
            if "/rounds[]" in generic:
                round_diffs += 1
            part_name = ""
            if (m := re.match(r"/parts\[(\d+)\]/notes", path)):
                part_name = ":" + b["parts"][int(m[1])]["name"]
            key = generic + part_name
            kinds[key] += 1
            samples.setdefault(key, (preset, case, x, y))
print(f"differing leaves inside any rounds[] (stitches / inc / dec / notes / colour / region): {round_diffs}")
for key, n in sorted(kinds.items()):
    preset, case, x, y = samples[key]
    print(f"  {n:4d}  {key}   e.g. {preset}/{case}")
    if isinstance(x, str) or isinstance(y, str):
        print(f"          - old: {str(x)[:330]}")
        print(f"          + new: {str(y)[:330]}")

# materials: which rows changed
changed_items = Counter()
for preset in old:
    for case in old[preset]["cases"]:
        a, b = old[preset]["cases"][case], new[preset]["cases"][case]
        if "materials" not in a:
            continue
        for ma, mb in zip(a["materials"], b["materials"], strict=True):
            if ma != mb:
                changed_items[(ma["item"], "->", mb["item"])] += 1
            assert {k: v for k, v in ma.items() if k != "item"} == {k: v for k, v in mb.items() if k != "item"}
        assert a["material_summary"] == b["material_summary"]
        assert a["total_stitches"] == b["total_stitches"] and a["estimated_time_minutes"] == b["estimated_time_minutes"]
print("material rows whose label changed (quantities, grams, metres, summary, totals, minutes all asserted equal):")
for key, n in changed_items.items():
    print(f"  {n:4d}  {key}")

print("\n=== Q5a. old-format params (baseline fixture, no version key) through the audited refresh/import code ===")
stats = Counter()
for preset in old:
    for case, params in old[preset]["cases"].items():
        if "parts" not in params:
            continue
        assert "construction_guidance_version" not in params
        refreshed = refresh_derived(deepcopy(params))
        stats["refresh_derived: identical" if refreshed == params else "refresh_derived: CHANGED"] += 1
        if refreshed != params:
            for path, x, y in list(walk(params, refreshed))[:3]:
                print("   CHANGED", preset, case, path, str(x)[:80], "->", str(y)[:80])
        rebuilt = rebuild_params(deepcopy(params))
        diffs = [p for p, *_ in walk(params, rebuilt)]
        stats["rebuild_params: identical" if not diffs else "rebuild_params: CHANGED"] += 1
        if diffs:
            stats[f"rebuild_params diff at {re.sub(r'[[0-9]+]', '[]', diffs[0])}"] += 1
        assert "construction_guidance_version" not in rebuilt
print(dict(stats))

analysis = ImageAnalysis(body_type="未评估", head_diameter_cm=8.3, height_cm=24, main_features=[], pose="站立",
                         difficulty="medium", parts=list(PART_NAMES))
structure = dict(StructureDesigner.design_3d_structure(analysis))


def old_result(preset: str, case: str, style: dict) -> dict:
    params = deepcopy(old[preset]["cases"][case])
    gauge = params["gauge"]
    return PatternResult(analysis=analysis.model_dump(), structure=deepcopy(structure), params=params,
                         gauge=dict(gauge), style=style, generator_version="0.2.0b3").to_backup()


STYLE0 = {"sphere_mode": "ladder", "one_piece": False, "skirt_style": "ring", "ruffle_hem": False}
backup = old_result("classic", "matrix-00", STYLE0)
loaded = import_backup(deepcopy(backup), "old000000001")
print("import_backup(old matrix-00): params identical to stored old params:",
      loaded["params"] == backup["params"], "| version key present:", "construction_guidance_version" in loaded["params"])
if loaded["params"] != backup["params"]:
    for path, x, y in list(walk(backup["params"], loaded["params"]))[:6]:
        print("   ", path, str(x)[:70], "->", str(y)[:70])
print("old assembly as loaded:\n   " + loaded["params"]["assembly_instructions"].replace("\n", "\n   "))
md_old = export_markdown(loaded["params"], loaded["analysis"], result=loaded)
rep = check_markdown(md_old)
print("independent check of the old result's Markdown ->", [str(f) for f in rep.errors()] or "no ERROR")
print("old head part note:", next(p for p in loaded["params"]["parts"] if p["name"] == "头部")["notes"])

print("\n=== Q5b. old result + non-geometry edits keep legacy guidance ===")
y = edit_yarn(loaded, {"ball_weight_g": 50, "ball_length_m": 125, "waste_percent": 10})
print("edit_yarn: version key present:", "construction_guidance_version" in y["params"],
      "| assembly unchanged:", y["params"]["assembly_instructions"] == loaded["params"]["assembly_instructions"],
      "| hook row:", [m["item"] for m in y["params"]["materials"] if "钩针" in m["item"]])
idx = next(i for i, p in enumerate(loaded["params"]["parts"]) if p["name"] == "手臂")
rounds = deepcopy(loaded["params"]["parts"][idx]["rounds"])
rounds[-1]["decrease"], rounds[-1]["stitches"] = 4, rounds[-2]["stitches"] - 4
r = edit_rounds(loaded, idx, rounds)
print("edit_rounds: version key present:", "construction_guidance_version" in r["params"],
      "| first assembly step:", r["params"]["assembly_instructions"].split("\n")[0])

print("\n=== Q5c. old result + geometry edit (quick resize, height only) ===")
resized = regenerate_with_size(loaded, 8.3, 30.0)
print("version key after resize:", resized["params"].get("construction_guidance_version"))
old_parts = {p["name"]: p for p in loaded["params"]["parts"]}
for p in resized["params"]["parts"]:
    kept = p == old_parts.get(p["name"])
    print(f"   {p['name']}: {'kept verbatim (old wording)' if kept else 'regenerated (new wording)'}")
print("assembly after resize:\n   " + resized["params"]["assembly_instructions"].replace("\n", "\n   "))
print("head note after resize:", next(p for p in resized["params"]["parts"] if p["name"] == "头部")["notes"])
print("skirt note after resize:", next(p for p in resized["params"]["parts"] if p["name"] == "裙子")["notes"])
rep = check_markdown(export_markdown(resized["params"], resized["analysis"], result=resized))
print("independent check after resize ->", [str(f) for f in rep.errors()] or "no ERROR")

print("\n=== Q5d. new result: which values of the key select which guidance; is the key validated? ===")
fresh = deepcopy(new["classic"]["cases"]["matrix-00"])
assert fresh["construction_guidance_version"] == 1
for label, mutate in (
    ("1 (generated)", lambda p: None),
    ("key removed", lambda p: p.pop("construction_guidance_version")),
    ("2 (a future revision)", lambda p: p.__setitem__("construction_guidance_version", 2)),
    ('"1" (string)', lambda p: p.__setitem__("construction_guidance_version", "1")),
    ("0", lambda p: p.__setitem__("construction_guidance_version", 0)),
    ("null", lambda p: p.__setitem__("construction_guidance_version", None)),
    ("true", lambda p: p.__setitem__("construction_guidance_version", True)),
    ("1.0", lambda p: p.__setitem__("construction_guidance_version", 1.0)),
    ('[1]', lambda p: p.__setitem__("construction_guidance_version", [1])),
):
    params = deepcopy(fresh)
    mutate(params)
    ok = validate_pattern(params)["ok"]
    try:
        rebuilt = rebuild_params(params)
    except Exception as exc:  # noqa: BLE001
        print(f"   {label:24s} validate ok={ok}; rebuild_params refused: {exc}")
        continue
    steps = rebuilt["assembly_instructions"].split("\n")
    eye = next(i for i, s in enumerate(steps, 1) if "安全眼" in s)
    stuff = next(i for i, s in enumerate(steps, 1) if "填充棉花" in s)
    guidance = "NEW" if steps[0].startswith("1. 独立裙筒先试套") else "LEGACY"
    print(f"   {label:24s} validate ok={ok}; accepted; guidance={guidance}; eye step #{eye}, stuffing step #{stuff}; "
          f"head note still says eyes before stuffing: {'填充和封口前安装' in rebuilt['parts'][0]['notes']}")
legacy_from_new = deepcopy(fresh)
legacy_from_new.pop("construction_guidance_version")
legacy_from_new = rebuild_params(legacy_from_new)
print("new parts + key removed -> assembly:\n   " + legacy_from_new["assembly_instructions"].replace("\n", "\n   "))
(SCRATCH / "out_guidance_new_parts_legacy_assembly.md").write_text(
    export_markdown(legacy_from_new, analysis.model_dump()), encoding="utf-8")
