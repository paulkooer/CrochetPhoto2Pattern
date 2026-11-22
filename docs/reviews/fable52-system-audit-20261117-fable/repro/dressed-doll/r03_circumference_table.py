"""r03: implied circumferences, layer allowances and profiles for a dressed-doll plan.

Reads only plan.json (data) -- no app imports. All centimetres are *implied by the stated
gauge* (stitches x stitch width, rows x row height); they are not measurements and say
nothing about real fabric, stuffing or stretch.

Usage: PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -I <this> [plan_dir ...]
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

sys.dont_write_bytecode = True
PACKAGED = Path("<repo>/eval_outputs/"
                "fable52-system-audit-20261117/examples/generated")
dirs = [Path(a) for a in sys.argv[1:]] or [PACKAGED / "doll-wide-brim", PACKAGED / "doll-folded-cap"]


def height_of(counts: list[int], w: float, h: float, start: int = 0, end: int | None = None) -> float:
    """Axial height of a surface of revolution whose successive rounds are `h` apart along
    the surface and have radius n*w/2pi. A round whose radius changes by more than `h`
    contributes no height (it lies flat and would have to stretch)."""
    end = len(counts) if end is None else end
    z = 0.0
    for i in range(max(1, start), end):
        dr = (counts[i] - counts[i - 1]) * w / (2 * math.pi)
        z += math.sqrt(max(0.0, h * h - dr * dr))
    return z


for root in dirs:
    plan = json.loads((root / "plan.json").read_text(encoding="utf-8"))
    d = plan["design"]
    w = 10.0 / d["stitches_per_10cm"]
    h = 10.0 / d["rows_per_10cm"]
    parts = {c["id"]: c for c in plan["components"]}
    counts = {k: [s["stitches"] for s in c["steps"]] for k, c in parts.items()}
    sect = {k: [s["section"] for s in c["steps"]] for k, c in parts.items()}

    def cm(n: float) -> float:
        return n * w

    print("=" * 110)
    print(f"{root.name}: gauge {d['stitches_per_10cm']:g} st x {d['rows_per_10cm']:g} rows per 10cm "
          f"-> stitch width {w:.4f} cm, row height {h:.4f} cm; garment_ease_cm={d['garment_ease_cm']}")

    # ------------------------------------------------------------------ part profiles
    print("\n## A. Profiles (stitches -> implied circumference / diameter)")
    print("| part | where | stitches | circumference cm | diameter cm | design target |")
    print("|---|---|---:|---:|---:|---|")

    def row(part: str, where: str, n: int, target: str = "") -> None:
        print(f"| {part} | {where} | {n} | {cm(n):.2f} | {cm(n) / math.pi:.2f} | {target} |")

    body = counts["body"]
    bsec = sect["body"]
    hip = max(n for n, s in zip(body, bsec) if s == "下身")
    waist = min(n for n, s in zip(body, bsec) if s == "腰部")
    chest = max(n for n, s in zip(body, bsec) if s == "胸肩")
    neck = body[-1]
    row("body", "lower body / hip", hip, f"body_diameter {d['body_diameter_cm']} cm")
    row("body", "waist", waist, "(0.8 x torso, no design field)")
    row("body", "chest/shoulder", chest, f"body_diameter {d['body_diameter_cm']} cm")
    row("body", "neck (open edge)", neck, f"neck_diameter {d['neck_diameter_cm']} cm")
    head = counts["head"]
    row("head", f"max girth (rounds {head.index(max(head)) + 1}-"
        f"{len(head) - head[::-1].index(max(head))})", max(head), f"head_diameter {d['head_diameter_cm']} cm")
    arms = counts["arms"]
    asec = sect["arms"]
    palm = max(n for n, s in zip(arms, asec) if s == "手掌")
    wrist = min(n for n, s in zip(arms, asec) if s == "手腕")
    fore = arms[-1]
    row("arm", "palm max", palm, f"palm_diameter {d['palm_diameter_cm']} cm")
    row("arm", "wrist", wrist, f"wrist_diameter {d['wrist_diameter_cm']} cm")
    row("arm", "forearm / shoulder opening", fore, "(max(wrist+2, palm-2), no design field)")
    legs = counts["legs"]
    row("leg", "tube", legs[-1], f"max(wrist, 0.65 x foot_width)={max(d['wrist_diameter_cm'], 0.65 * d['foot_width_cm']):.2f} cm")
    shoes = counts["shoes"]
    row("shoe", "sole edge", max(shoes), "")
    row("shoe", "opening", shoes[-1], "")
    row("hair cap", "rim", counts["hair_cap"][-1], "")
    hat = counts["hat"]
    hsec = sect["hat"]
    hat_rim = [n for n, s in zip(hat, hsec) if s == "帽身"][-1]
    row("hat", "crown rim (帽身)", hat_rim, "")
    if "帽檐" in hsec:
        row("hat", "brim outer edge", hat[-1], f"brim_width {d['brim_width_cm']} cm")
    for k in ("skirt_1", "skirt_2"):
        if k in counts:
            row(k, "waist chain ring", counts[k][0], "")
            row(k, "hem", counts[k][-1], "")
    row("sleeve", "tube (both ends)", counts["sleeves"][0], "")
    gb, gf = counts["garment_back"][0], counts["garment_front"][0]
    row("garment", f"whole piece {gb} + 2 open pieces x {gf}", gb + 2 * gf, "")

    # ------------------------------------------------------------------ layer allowances
    print("\n## B. Layer allowances (outer minus inner), implied by gauge only")
    print("| interface | inner st | outer st | inner cm | outer cm | diff cm | diff % | radial gap between "
          "fabric mid-surfaces mm | where the allowance comes from |")
    print("|---|---:|---:|---:|---:|---:|---:|---:|---|")

    def layer(name: str, inner: float, outer: float, src: str, inner_cm: float | None = None,
              outer_cm: float | None = None) -> None:
        a = cm(inner) if inner_cm is None else inner_cm
        b = cm(outer) if outer_cm is None else outer_cm
        print(f"| {name} | {inner:g} | {outer:g} | {a:.2f} | {b:.2f} | {b - a:+.2f} | {100 * (b - a) / a:+.1f} | "
              f"{10 * (b - a) / (2 * math.pi):+.2f} | {src} |")

    cap = counts["hair_cap"][-1]
    layer("head max girth -> hair cap rim", max(head), cap, "planner.py:106 `cap_rim = head_peak + 2` (constant 2 st)")
    layer("hair cap rim -> hat crown rim (hair strands lie in between)", cap, hat_rim,
          "planner.py:117 `cap_rim + max(2, ceil(garment_ease_cm / stitch_w))`")
    layer("head max girth -> hat crown rim", max(head), hat_rim, "sum of the two above")
    if "hat_band" in counts:
        band_rows = len(counts["hat_band"])
        layer("hat rim (stitches) -> rib band length (rows)", hat_rim, band_rows,
              "planner.py:124 rows = round(hat_rim*stitch_w/row_h); BLO rib uses the plain sc row gauge",
              outer_cm=band_rows * h)
    total = gb + 2 * gf
    layer("body chest/hip -> garment (3 panels, before seams)", chest, total,
          "planner.py:133-134 `torso + max(2, ceil(garment_ease_cm / stitch_w))`")
    layer("body waist -> garment", waist, total, "garment is sized from the widest body round")
    for k in ("skirt_1", "skirt_2"):
        if k in counts:
            layer(f"body hip (must pass) -> {k} waist ring", hip, counts[k][0],
                  "planner.py:134,136 `torso + ease + 2*layer`")
            layer(f"body waist (where it sits) -> {k} waist ring", waist, counts[k][0], "same; not sized to the waist")
    if "skirt_2" in counts:
        layer("skirt_1 waist -> skirt_2 waist", counts["skirt_1"][0], counts["skirt_2"][0],
              "planner.py:136 `+ layer * 2` (constant 2 st)")
    sleeve = counts["sleeves"][0]
    layer("palm max (must pass) -> sleeve", palm, sleeve, "planner.py:146 `max(palm, upper) + ease`")
    layer("forearm (where it sits) -> sleeve", fore, sleeve, "same; not sized to the forearm")
    layer("leg -> shoe opening", legs[-1], shoes[-1],
          "recipes.py:170 `max(leg + 2, 2*straight + 4)`; here the sole's straight sides decide")
    # neckline
    import re
    fin_b = parts["garment_back"]["finish"]
    fin_f = parts["garment_front"]["finish"]
    shoulder = int(re.search(r"各 (\d+) 针用于肩缝", fin_b)[1])
    neck_gap = int(re.search(r"中央 (\d+) 针留领口", fin_b)[1])
    front_neck = int(re.search(r"内侧 (\d+) 针留领口", fin_f)[1])
    armhole = int(re.search(r"各留 (\d+) 行边作袖窿", fin_b)[1])
    neckline = neck_gap + 2 * front_neck
    layer("body neck -> neckline perimeter (stitches left open)", neck, neckline,
          "planner.py:152-154 shoulder/neck split; garment also has an open placket")
    rows_panel = len(counts["garment_back"])
    layer("sleeve top (stitches) -> armhole (row edges, front+back)", sleeve, 2 * armhole,
          "planner.py:147 `round(sleeve_n*stitch_w/(2*row_h))`", outer_cm=2 * armhole * h)
    print(f"\nshoulder seam {shoulder} st = {cm(shoulder):.2f} cm each; neck gap {neck_gap} st = {cm(neck_gap):.2f} cm; "
          f"panel {rows_panel} rows = {rows_panel * h:.2f} cm; armhole {armhole} row edges = {armhole * h:.2f} cm "
          f"per panel; side seam {rows_panel - armhole} row edges = {(rows_panel - armhole) * h:.2f} cm")
    print(f"whole piece {gb} st = {cm(gb):.2f} cm wide vs half body circumference {cm(chest) / 2:.2f} cm; "
          f"outer end of each shoulder seam is {cm(gb) / 2:.2f} cm from centre vs body radius {cm(chest) / (2 * math.pi):.2f} cm")

    # ------------------------------------------------------------------ heights
    print("\n## C. Lengths and heights implied by the round counts")
    bh = height_of(body, w, h)
    hh = height_of(head, w, h)
    lh = height_of(legs, w, h)
    target_body = d["height_cm"] - d["head_diameter_cm"] - d["leg_length_cm"]
    print(f"body: {len(body)} rounds = {len(body) * h:.2f} cm along the surface; axial height ~{bh:.2f} cm "
          f"(target body+neck {target_body:g} cm) -> {100 * bh / target_body:.0f}% of target")
    straight = sum(1 for i in range(1, len(body)) if body[i] == body[i - 1])
    print(f"      rounds that add full height (count unchanged): {straight} = {straight * h:.2f} cm")
    print(f"head: {len(head)} rounds = {len(head) * h:.2f} cm pole to pole along the surface "
          f"(a {d['head_diameter_cm']:g} cm sphere has {math.pi * d['head_diameter_cm'] / 2:.2f} cm); axial ~{hh:.2f} cm")
    print(f"legs: {len(legs)} rounds = {len(legs) * h:.2f} cm; axial ~{lh:.2f} cm (target {d['leg_length_cm']:g} cm)")
    print(f"arms: {len(arms)} rounds = {len(arms) * h:.2f} cm (target {d['arm_length_cm']:g} cm); "
          f"palm section {sum(1 for s in asec if s in ('起针', '手掌'))} rounds = "
          f"{sum(1 for s in asec if s in ('起针', '手掌')) * h:.2f} cm long, {cm(palm) / math.pi:.2f} cm across")
    print(f"sum legs+body+head (axial, no overlap, no shoe sole) ~{lh + bh + hh:.2f} cm vs header target "
          f"{d['height_cm']:g} cm -> {100 * (lh + bh + hh) / d['height_cm']:.0f}%")
    print(f"sleeve: {len(counts['sleeves'])} rounds = {len(counts['sleeves']) * h:.2f} cm; "
          f"arm {len(arms) * h:.2f} cm")
    for k in ("skirt_1", "skirt_2"):
        if k in counts:
            print(f"{k}: {len(counts[k])} rounds = {len(counts[k]) * h:.2f} cm (target skirt_length {d['skirt_length_cm']:g})")

    # ------------------------------------------------------------------ hair cap vs eyes
    print("\n## D. Hair cap depth vs eye round (both counted from the crown, same row gauge)")
    capc = counts["hair_cap"]
    eye = int(re.search(r"第 (\d+) 圈为眼位候选", parts["head"]["finish"])[1])
    crown = next(i for i, n in enumerate(capc) if n == capc[-1]) + 1
    print(f"hair cap: {len(capc)} rounds ({crown} to reach {capc[-1]} st, then {len(capc) - crown} straight) "
          f"= {len(capc) * h:.2f} cm from crown to rim along the fabric")
    print(f"head: reaches {max(head)} st at round {head.index(max(head)) + 1}; eye candidate round {eye} "
          f"= {(eye - 1) * h:.2f}-{eye * h:.2f} cm from the crown; equator of a "
          f"{len(head)}-round head is between rounds {len(head) // 2} and {len(head) // 2 + 1}")
    print(f"cap rounds minus eye round = {len(capc) - eye:+d} rounds "
          f"({(len(capc) - eye) * h:+.2f} cm): positive means a crown-centred cap that follows the head ends BELOW the eye round")
    print("round-by-round (cap st / head st): " + " ".join(f"{i + 1}:{capc[i]}/{head[i]}" for i in range(len(capc))))

    # ------------------------------------------------------------------ sole
    print("\n## E. Shoe sole")
    ch = parts["shoes"]["foundation"]["chains"]
    sole_rounds = sum(1 for s in sect["shoes"] if s == "鞋底")
    L = (ch - 3) * w + 2 * sole_rounds * h
    W = 2 * sole_rounds * h
    print(f"chain {ch} -> straight {ch - 3} st; {sole_rounds} sole rounds -> implied sole {L:.2f} x {W:.2f} cm "
          f"(targets {d['foot_length_cm']:g} x {d['foot_width_cm']:g} cm)")
    print(f"opening {shoes[-1]} st = {cm(shoes[-1]):.2f} cm vs leg {legs[-1]} st = {cm(legs[-1]):.2f} cm")

    # ------------------------------------------------------------------ brim
    if "帽檐" in hsec:
        brim = [n for n, s in zip(hat, hsec) if s == "帽檐"]
        need = 2 * math.pi * h / w
        flat_edge = hat_rim + need * len(brim)
        print("\n## F. Brim")
        print(f"brim rounds {brim}: +6 per round; a flat ring at this gauge needs +{need:.2f} per round "
              f"-> flat edge would be {flat_edge:.1f} st, plan has {brim[-1]} ({100 * (brim[-1] / flat_edge - 1):+.1f}%)")

    # ------------------------------------------------------------------ hair
    print("\n## G. Hair strands")
    for k in ("hair", "fringe"):
        c = parts[k]
        n = c["foundation"]["chains"]
        print(f"{k}: {c['quantity']} strands, chain {n} -> {n - 1} working chains = {(n - 1) * w:.2f} cm before curling; "
              f"{c['steps'][0]['expression']} = {c['steps'][0]['stitches']} sc")
    print(f"hair cap rim {cm(cap):.2f} cm; {parts['hair']['quantity']} long strands over sides+back")
