"""r01: run the real CLI for both starters into a NEW sub-directory of the scratch dir and
compare every artefact byte-for-byte with the packaged examples (read-only).

Usage: PYTHONDONTWRITEBYTECODE=1 .venv/bin/python <this> [label]
"""
from __future__ import annotations

import hashlib
import subprocess
import sys
import time

from common import PACKAGED, REPO, SCRATCH, assert_repo

assert_repo()
label = sys.argv[1] if len(sys.argv) > 1 else time.strftime("run-%H%M%S")
out_root = SCRATCH / "out" / label
assert not out_root.exists(), f"{out_root} already exists; pass a new label"

CASES = {"doll-wide-brim": "wide_brim_curls", "doll-folded-cap": "folded_cap_layers"}
failures = 0
for folder, starter in CASES.items():
    target = out_root / folder
    cmd = [sys.executable, "-m", "app.doll_cli", "--starter", starter, "--out-dir", str(target), "--pdf"]
    done = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True,
                          env={"PYTHONDONTWRITEBYTECODE": "1", "PATH": "/usr/bin:/bin"})
    print(f"$ python -m app.doll_cli --starter {starter} --out-dir <scratch>/out/{label}/{folder} --pdf")
    print(f"  exit={done.returncode}")
    print("  stdout:", " ".join(done.stdout.split()))
    if done.stderr.strip():
        print("  stderr:", done.stderr.strip()[:400])
    for name in ("design.json", "plan.json", "plan.md", "assembly.dot", "plan.pdf"):
        fresh = target / name
        packed = PACKAGED / folder / name
        if not fresh.exists():
            print(f"  {name}: MISSING in fresh output")
            failures += 1
            continue
        a, b = fresh.read_bytes(), packed.read_bytes()
        same = a == b
        note = ""
        if not same and name == "plan.pdf":
            note = " (PDF embeds creation time/ID; compared separately in r07)"
        elif not same:
            failures += 1
        print(f"  {name}: fresh sha256={hashlib.sha256(a).hexdigest()[:16]} len={len(a)} | "
              f"packaged sha256={hashlib.sha256(b).hexdigest()[:16]} len={len(b)} | identical={same}{note}")

# Second invocation into the same directory must refuse and leave files untouched.
target = out_root / "doll-wide-brim"
before = {p.name: p.read_bytes() for p in target.iterdir()}
done = subprocess.run([sys.executable, "-m", "app.doll_cli", "--starter", "wide_brim_curls",
                       "--out-dir", str(target)], cwd=REPO, capture_output=True, text=True,
                      env={"PYTHONDONTWRITEBYTECODE": "1", "PATH": "/usr/bin:/bin"})
print(f"re-run into existing dir: exit={done.returncode} stderr={done.stderr.strip()}")
assert before == {p.name: p.read_bytes() for p in target.iterdir()}
print("existing files untouched: True")
print("NON-PDF MISMATCHES:", failures)
