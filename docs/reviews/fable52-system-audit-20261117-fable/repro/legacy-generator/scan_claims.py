"""Q1/Q2: claims in generated text that the generator's own numbers contradict,
and construction facts a maker would need.

1. Hat note says "帽围 N 针 > 头围" — compare with the head's widest round.
2. Hat depth vs. the eye round (row-count geometry only; no physical claim).
3. Eye round: separate head vs. one-piece for the same head.
4. Attached skirt: where the reservation round lands; which loops are used.
5. Closed-end limbs: last-round stitch count vs. stuffing instruction in the part note.

Run: PYTHONDONTWRITEBYTECODE=1 .venv/bin/python <this file>
"""
from __future__ import annotations

import re
import sys
from collections import Counter
from itertools import product
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import ALL_PARTS, PRESETS, Gauge, ShapingStyle, assert_audited_modules, manual_result  # noqa: E402

from app.models.crochet_params import PatternGenerationError  # noqa: E402
from app.models.crochetability import crochetability_findings  # noqa: E402

assert_audited_modules()


def part(result, name):
    return next((p for p in result["params"]["parts"] if p["name"] == name), None)


def peak(p):
    return max(r["stitches"] for r in p["rounds"])


def eye_round(p):
    m = re.search(r"第 (\d+) 圈安装安全眼", p["notes"])
    return int(m[1]) if m else None


print("=== 1. hat note '帽围 N 针 > 头围' vs head widest round (fresh generation, manual-tab ranges) ===")
gauges = {**PRESETS, "g10x12": Gauge(10, 12), "g24x26": Gauge(24, 26), "g30x34": Gauge(30, 34)}
heads = [4 + 0.5 * i for i in range(33)]  # 4.0 .. 20.0, the manual slider range
not_greater: list[tuple] = []
total = blocked = 0
for (gname, gauge), mode, head in product(gauges.items(), ("ladder", "ideal", "egg"), heads):
    try:
        r = manual_result(head=head, height=max(10.0, head * 2), parts=["头部", "身体", "帽子"],
                          gauge=gauge, style=ShapingStyle(sphere_mode=mode))
    except (ValueError, PatternGenerationError):
        continue
    total += 1
    is_blocked = any(f.level == "block" for f in crochetability_findings(r["params"]))
    blocked += is_blocked
    hat, hd = part(r, "帽子"), part(r, "头部")
    claim = re.search(r"帽围 (\d+) 针 > 头围", hat["notes"])
    assert claim and int(claim[1]) == peak(hat)
    if peak(hat) <= peak(hd):
        not_greater.append((gname, mode, head, peak(hat), peak(hd), is_blocked))
print(f"generated {total} (of which {blocked} would be stopped by the first-generation crochetability gate)")
print(f"hat widest <= head widest while note claims '>': {len(not_greater)}")
reachable = [x for x in not_greater if not x[5]]
print(f"  of those NOT stopped by the gate (i.e. reachable from the manual tab / CLI): {len(reachable)}")
by_mode = Counter((g, m) for g, m, *_ in reachable)
print("  by (gauge, mode):", dict(by_mode))
for row in reachable[:12]:
    print("   gauge=%s mode=%s head=%.1fcm hat=%d st head=%d st" % row[:5])

print("\n=== 2. hat rounds vs eye round (same gauge; counts only) ===")
covered = Counter()
examples = []
for (gname, gauge), mode, head in product(PRESETS.items(), ("ladder", "ideal", "egg"), (6.0, 9.0, 12.0, 16.0)):
    r = manual_result(head=head, height=head * 2, parts=["头部", "身体", "帽子"],
                      gauge=gauge, style=ShapingStyle(sphere_mode=mode))
    hat, hd = part(r, "帽子"), part(r, "头部")
    eye = eye_round(hd)
    n_hat, n_head = len(hat["rounds"]), len(hd["rounds"])
    covered[n_hat >= eye] += 1
    examples.append((gname, mode, head, n_head, eye, n_hat, peak(hd), peak(hat)))
print("hat total rounds >= head eye round:", dict(covered))
print("gauge mode head_cm | head rounds | eye round | hat rounds (crown+wall) | head peak st | hat st")
for e in examples:
    print("  %-7s %-6s %5.1f | %3d | %3d | %3d | %3d | %3d" % e)

print("\n=== 3. eye round: separate head vs one-piece (same inputs) ===")
for (gname, gauge), mode in product(PRESETS.items(), ("ladder", "ideal", "egg")):
    sep = manual_result(parts=["头部", "身体"], gauge=gauge, style=ShapingStyle(sphere_mode=mode))
    one = manual_result(parts=["头部", "身体"], gauge=gauge, style=ShapingStyle(sphere_mode=mode, one_piece=True))
    hd, op = part(sep, "头部"), part(one, "头身（一体）")
    sts = [r["stitches"] for r in hd["rounds"]]
    first_max = sts.index(max(sts)) + 1
    last_max = len(sts) - sts[::-1].index(max(sts))
    print(f"  {gname:7s} {mode:6s} separate: eye R{eye_round(hd)} of {len(sts)} (widest rounds R{first_max}–R{last_max}); "
          f"one-piece: eye R{eye_round(op)}, neck R{op['neck_row']} of {len(op['rounds'])}")

print("\n=== 4. attached skirt: reservation round position and loop convention ===")
pos = Counter()
for (gname, gauge), one_piece, (head, height) in product(
        PRESETS.items(), (False, True), ((6, 12), (9, 18), (9, 40), (14, 30), (20, 60))):
    try:
        r = manual_result(head=head, height=height, parts=ALL_PARTS, gauge=gauge,
                          style=ShapingStyle(one_piece=one_piece, skirt_style="attached"))
    except (ValueError, PatternGenerationError) as exc:
        pos[f"rejected: {str(exc)[:40]}"] += 1
        continue
    c = r["params"]["stitch_attachments"]["connections"][0]
    body = part(r, c["target_part"])
    rows = [x["row"] for x in body["rounds"]]
    last = rows[-1]
    reserve = next(x for x in body["rounds"] if x["row"] == c["reservation_row"])
    kind = "reservation is the LAST body round" if c["reservation_row"] == last else "reservation before last round"
    pos[kind] += 1
    shaped = bool(reserve.get("increase") or reserve.get("decrease"))
    pos["reservation round also shapes (FLO inc/dec)"] += shaped
    if c["reservation_row"] == last or shaped:
        print(f"   {gname} one_piece={one_piece} head={head} height={height}: base R{c['target_row']} "
              f"reserve R{c['reservation_row']}/{last}: {reserve['notes']!r}")
print(dict(pos))
r = manual_result(parts=ALL_PARTS, style=ShapingStyle(skirt_style="attached"))
print("loop convention text:", r["params"]["assembly_instructions"].split("\n")[-1][-150:])

print("\n=== 5. open-ended parts: last-round stitches and whether the PART note mentions stuffing ===")
r = manual_result(parts=ALL_PARTS)
for p in r["params"]["parts"]:
    last = p["rounds"][-1]
    print(f"  {p['name']:4s} type={p['type']:8s} state={p.get('connection_state')} last R{last['row']}={last['stitches']} st "
          f"peak={peak(p)}; part note mentions 填充/填棉: {bool(re.search('填充|填棉', p.get('notes') or ''))}; "
          f"last-round note: {last['notes'][-34:]!r}")
