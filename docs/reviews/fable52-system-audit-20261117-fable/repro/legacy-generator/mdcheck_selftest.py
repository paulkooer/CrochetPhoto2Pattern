"""Mutation self-test: prove the independent checker actually notices defects.

Run: PYTHONDONTWRITEBYTECODE=1 .venv/bin/python <this file>
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import ShapingStyle, assert_audited_modules, manual_result  # noqa: E402
from mdcheck import check_markdown, expand, tally  # noqa: E402

from app.utils.exporters import export_markdown  # noqa: E402

assert_audited_modules()

# formula expander
assert tally(expand("(4X,V)×6")) == (30, 36, 6, 0)
assert tally(expand("(X,V,X)×6")) == (18, 24, 6, 0)
assert tally(expand("(A)×6")) == (12, 6, 0, 6)
assert tally(expand("36X")) == (36, 36, 0, 0)
assert tally(expand("V×36")) == (36, 72, 36, 0)
assert tally(expand("(7X,A)×2")) == (18, 16, 0, 2)
assert tally(expand("(2X,A)×5,3X,A")) == (25, 19, 0, 6)
assert tally(expand("FLO(36X)")) == (36, 36, 0, 0)
assert tally(expand("36X-FLO")) == (36, 36, 0, 0)
assert tally(expand("BLO((X,V,X)×5)")) == (15, 20, 5, 0)

result = manual_result(parts=["头部", "身体", "手臂", "腿部", "帽子", "裙子"],
                       style=ShapingStyle(skirt_style="attached"))
md = export_markdown(result["params"], result["analysis"], result=result)
base = check_markdown(md)
print("baseline findings on a valid generated pattern:")
for finding in base.findings:
    print("  ", finding)
assert not base.errors(), "valid pattern must not produce ERROR findings"

mutations = {
    "stitch count 30 -> 31 in one row":
        lambda t: t.replace("| 7 | 30 | +6 | — | (3X,V)×6 |", "| 7 | 31 | +6 | — | (3X,V)×6 |", 1),
    "formula column (4X,V)x6 -> (3X,V)x6":
        lambda t: t.replace("| (4X,V)×6 | — | (4X,V)×6，隔4针加1针 |", "| (3X,V)×6 | — | (4X,V)×6，隔4针加1针 |", 1),
    "note formula changed, column kept":
        lambda t: t.replace("| (4X,V)×6 | — | (4X,V)×6，隔4针加1针 |", "| (4X,V)×6 | — | (5X,V)×6，隔4针加1针 |", 1),
    "interval wording wrong":
        lambda t: t.replace("(4X,V)×6，隔4针加1针", "(4X,V)×6，隔3针加1针", 1),
    "magic ring count wrong":
        lambda t: t.replace("魔法环起6针（X×6）", "魔法环起8针（X×6）", 1),
    "arm opening count in assembly wrong":
        lambda t: t.replace("（开口 6 针，小开口可捏扁缝合）", "（开口 12 针）", 1),
    "eye step moved after stuffing":
        lambda t: t.replace("头部安全眼按部件说明的具体圈号定位；在填充和封口前安装并扣好内侧垫片", "占位步骤", 1)
                   .replace("用黑色毛线绣鼻子和嘴巴", "头部安全眼安装", 1),
    "skirt anchor row shifted":
        lambda t: t.replace("只挑第 11 圈的前半针", "只挑第 10 圈的前半针", 1),
    "skirt anchor stitch count wrong":
        lambda t: t.replace("保留其第 1–36 针的后半针", "保留其第 1–30 针的后半针", 1),
    "workload stitches wrong":
        lambda t: t.replace("个实体部件 · ", "个实体部件 · 9", 1),
    "decrease column dropped":
        lambda t: t.replace("| 30 | — | -6 | (4X,A)×6 |", "| 30 | — | — | (4X,A)×6 |", 1),
    "finish instruction moved off the last row":
        lambda t: t.replace("| 14 | 30 | — | -6 | (4X,A)×6 | — | (4X,A)×6，隔4针减1针 |",
                            "| 14 | 30 | — | -6 | (4X,A)×6 | — | (4X,A)×6，隔4针减1针；断线留15cm用于缝合 |", 1),
    "hat note peak wrong":
        lambda t: t.replace("帽围 42 针", "帽围 48 针", 1),
    "opening bullet wrong":
        lambda t: t.replace("- **连接开口**：第 15 圈 · 24 针", "- **连接开口**：第 15 圈 · 30 针", 1),
    "yarn subtotal wrong":
        lambda t: t.replace("毛线小计：", "毛线小计：9", 1),
}
failed = []
for label, mutate in mutations.items():
    mutated = mutate(md)
    if mutated == md:
        failed.append(f"{label}: mutation did not apply (anchor text not found)")
        continue
    errors = check_markdown(mutated).errors()
    print(f"mutation [{label}] -> {len(errors)} ERROR(s): {errors[0].code if errors else '—'}")
    if not errors:
        failed.append(f"{label}: not detected")
print("SELFTEST", "FAILED" if failed else "PASSED", failed)
sys.exit(1 if failed else 0)
