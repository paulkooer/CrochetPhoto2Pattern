"""Round 3: every difference between the generator snapshots frozen at 6c88b7d and the working tree.

Run from the repository root as a module-free script:
    python r3_snapshot_diff.py
Prints, per differing JSON path pattern, how many of the 102 cases differ, and
asserts that nothing changed but the note of cup parts and, for attached skirts, the
orientation sentence of the assembly text. Nothing is written.
"""
import collections
import gzip
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").is_file())
sys.path.insert(0, str(REPO))

import app  # noqa: E402
from tests.test_generator_output_snapshots import CASES, FIXTURES, generated  # noqa: E402

assert Path(app.__file__).resolve().is_relative_to(REPO), app.__file__


def walk(old, new, path=""):
    if isinstance(old, dict) and isinstance(new, dict):
        for key in sorted(set(old) | set(new)):
            if key not in old or key not in new:
                yield f"{path}/{key}", old.get(key, "<absent>"), new.get(key, "<absent>")
            else:
                yield from walk(old[key], new[key], f"{path}/{key}")
    elif isinstance(old, list) and isinstance(new, list) and len(old) == len(new):
        for index, (a, b) in enumerate(zip(old, new, strict=True)):
            yield from walk(a, b, f"{path}/{index}")
    elif old != new:
        yield path, old, new


BASE = "6c88b7d"
frozen = {}
for preset in sorted({preset for preset, _case, _style in CASES}):
    blob = subprocess.run(["git", "show", f"{BASE}:{(FIXTURES / f'{preset}.json.gz').relative_to(REPO)}"],
                          cwd=REPO, capture_output=True, check=True).stdout
    frozen[preset] = json.loads(gzip.decompress(blob).decode("utf-8"))["cases"]
print(f"frozen outputs read from commit {BASE}; generated outputs from the working tree")

patterns: collections.Counter = collections.Counter()
fields: collections.Counter = collections.Counter()
branches: collections.Counter = collections.Counter()
changed_cases = 0
examples = {}
for preset, case, style in CASES:
    old, new = frozen[preset][case], generated(preset, case, style)
    differences = list(walk(old, new))
    changed_cases += bool(differences)
    fields[len(differences)] += 1
    old_steps = old.get("assembly_instructions", "").split("\n")
    new_steps = new.get("assembly_instructions", "").split("\n")
    for path, before, after in differences:
        if path == "/assembly_instructions":
            assert len(old_steps) == len(new_steps), (preset, case)
            for was, now in zip(old_steps, new_steps, strict=True):
                if was == now:
                    continue
                if "见 F-11" in was:
                    # attached skirts: the orphan "见 F-11" sentence became a self-check
                    assert style.skirt_style == "attached", (preset, case)
                    head, tail = was.split("（朝向前提：")[0], was.split("见 F-11。）")[1]
                    assert now.startswith(head) and now.endswith(tail) and "F-11" not in now
                    middle = now[len(head):len(now) - len(tail)]
                    assert middle.startswith("（先核对半针朝向") and middle.endswith("试钩记录。）"), middle
                    patterns["assembly step: 挑针接裙的朝向说明"] += 1
                    examples.setdefault("attached skirt check", (preset, case, middle))
                else:
                    # the hat step now states the estimated rim against the widest head round
                    stem = was.split("不收口，直接戴在头部（试戴后可缝合固定）")
                    assert len(stem) == 2 and stem[1] == "" and "帽口 " in stem[0], (preset, case, was)
                    assert now.startswith(stem[0] + "不收口，戴在头部。按密度估算，帽口周长约 "), now
                    assert "这是估算不是实测" in now and "先试戴，" in now, now
                    branch = ("rim longer" if "帽口多约" in now else "same length" if "两者相同" in now
                              else "rim shorter" if "帽口少约" in now else None)
                    assert branch, now
                    patterns["assembly step: 帽口与头部最宽圈的估算对比"] += 1
                    branches[f"hat step: {branch}"] += 1
                    examples.setdefault(f"hat step: {branch}", (preset, case, now))
            continue
        match = re.fullmatch(r"/parts/(\d+)/notes", path)
        assert match, (preset, case, path)
        part = new["parts"][int(match.group(1))]
        # _cup_part also serves a non-hat part whose structure shape is "cup".
        assert part["type"] == "cup", (preset, case, part["name"])
        assert after == before.replace(" 针 > 头围，不收口可直接佩戴），", " 针，不收口），") != before
        patterns[f"part note of cup part '{part['name']}': 删去 '> 头围，可直接佩戴'"] += 1
        examples.setdefault("cup part note", (preset, case, after))
    # every part with rounds keeps its ordered stitch table
    if "parts" in old:
        assert [[r["stitches"] for r in p["rounds"]] for p in old["parts"]] == \
               [[r["stitches"] for r in p["rounds"]] for p in new["parts"]]
print(f"cases: {len(CASES)}; cases with any difference: {changed_cases}")
print("   differing fields per case:", dict(sorted(fields.items())))
for name, count in patterns.items():
    print(f"   differing path {name}: {count} cases")
for name, count in sorted(branches.items()):
    print(f"   hat note branch '{name}': {count} cases")
for name, (preset, case, text) in sorted(examples.items()):
    print(f"   e.g. {name} [{preset}/{case}]: {text}")
