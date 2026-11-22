"""Dressed-doll entry through Streamlit AppTest, without ever opening the inner expander.

1. Change only the target height and generate: which dimensions follow?
2. Compare with the CLI starter at the same height.
3. Round trip: design JSON -> read_design -> build_doll_plan gives the same plan.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

os.environ["CROCHET_HISTORY_DB"] = str(Path(tempfile.mkdtemp(prefix="fable-audit-")) / "history.db")

import app  # noqa: E402
from streamlit.testing.v1 import AppTest  # noqa: E402

from app.doll_cli import read_design  # noqa: E402
from app.models.dressed_doll import build_doll_plan, starter_design  # noqa: E402

REPO = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").is_file())
assert Path(app.__file__).resolve().is_relative_to(REPO), app.__file__


def page() -> None:
    from app.ui.dressed_doll import render_dressed_doll_designer
    render_dressed_doll_designer()


KEYS = ("height_cm", "head_diameter_cm", "leg_length_cm", "body_diameter_cm", "neck_diameter_cm",
        "arm_length_cm", "palm_diameter_cm", "wrist_diameter_cm", "foot_length_cm", "foot_width_cm",
        "brim_width_cm", "bodice_length_cm", "skirt_length_cm", "bag_width_cm", "bag_height_cm",
        "strap_length_cm")

at = AppTest.from_function(page, default_timeout=60).run()
assert not at.exception, at.exception
at.number_input(key="doll_design_height").set_value(48.0).run()
assert not at.exception, at.exception
at.button(key="doll_design_generate").click().run()
assert not at.exception, at.exception
ui_design = at.session_state["doll_design_plan"]["design"]
cli_design = starter_design("wide_brim_curls", height_cm=48).model_dump()
print("height 48: UI (only the height field touched) versus CLI --starter --height 48")
print(f"  {'field':22s} {'UI':>8s} {'CLI':>8s}")
for key in KEYS:
    marker = "" if abs(ui_design[key] - cli_design[key]) < 1e-9 else "   <-- differs"
    print(f"  {key:22s} {ui_design[key]:8.2f} {cli_design[key]:8.2f}{marker}")
ui_plan = build_doll_plan(read_design(json.dumps(ui_design).encode()))
cli_plan = build_doll_plan(starter_design("wide_brim_curls", height_cm=48))


def rounds(plan, part):
    return [s.stitches for s in next(p for p in plan.components if p.id == part).steps]


for part in ("head", "body", "arms", "shoes", "hair_cap", "garment_back"):
    a, b = rounds(ui_plan, part), rounds(cli_plan, part)
    print(f"  {part:13s} UI: {len(a):3d} steps, widest {max(a):3d} st | CLI: {len(b):3d} steps, widest {max(b):3d} st")
messages = [m.value for m in list(at.info) + list(at.warning) + list(at.error)]
print("  notices shown by the UI after generating:", messages or "none")
captions = [c.value for c in at.caption]
print("  any caption mentioning that some dimensions keep earlier values:",
      any("沿用" in c or "未随" in c or "保持" in c for c in captions))

print("\nround trip: downloaded design JSON -> load -> plan")
plan = build_doll_plan(starter_design("folded_cap_layers", height_cm=30))
text = plan.design.model_dump_json(indent=2)
again = build_doll_plan(read_design(text.encode()))
print("  same plan after reload:", again == plan, "| same JSON bytes:", again.model_dump_json() == plan.model_dump_json())
