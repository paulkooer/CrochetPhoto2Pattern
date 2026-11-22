"""Provenance labels in the cardigan designer's 'own swatch' mode (driven through AppTest).

The UI offers no hook-size input and keeps the example dimensions as defaults.
What do the report, the plan gauges and the PDF say about hook size and about
where the dimensions came from?
"""
from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path

os.environ["CROCHET_HISTORY_DB"] = str(Path(tempfile.mkdtemp(prefix="fable-audit-")) / "history.db")

import app  # noqa: E402
from streamlit.testing.v1 import AppTest  # noqa: E402

REPO = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").is_file())
assert Path(app.__file__).resolve().is_relative_to(REPO), app.__file__


def page() -> None:
    from app.ui.cardigan_design import render_cardigan_designer
    render_cardigan_designer()


at = AppTest.from_function(page, default_timeout=120).run()
assert not at.exception, at.exception
at.radio(key="cardigan_gauge_mode").set_value("填入自己的小样密度").run()
labels = [w.label for w in at.number_input] + [w.label for w in at.text_input] + [w.label for w in at.selectbox]
print("inputs offered in own-swatch mode:", labels)
print("any input for hook size:", any(re.search(r"钩针|针号|mm", label) for label in labels))
values = {"cardigan_sc_own_gs": 24.0, "cardigan_sc_own_gr": 27.0, "cardigan_hem_own_gs": 25.0,
          "cardigan_hem_own_gr": 25.0, "cardigan_band_own_gs": 38.0, "cardigan_band_own_gr": 38.0,
          "cardigan_cuff_own_gs": 38.0, "cardigan_cuff_own_gr": 38.0}
for key, value in values.items():
    at.number_input(key=key).set_value(value)
at.run()
at.button(key="cardigan_generate").click().run()
assert not at.exception, at.exception
errors = [e.value for e in at.error]
stored = at.session_state["cardigan_design_result"] if "cardigan_design_result" in at.session_state else None
print("errors shown:", errors)
if stored is None:
    raise SystemExit("no result stored")
report, plan = stored["report"], stored["plan"]
print("stage:", report["stage"])
print("request.dimension_basis:", report["request"]["dimension_basis"],
      "| dimensions used:", {k: report["request"]["yoke"][k] for k in
                             ("neck_edge_cm", "body_span_cm", "sleeve_circumference_cm", "yoke_depth_cm")},
      "(these are the untouched example defaults)")
print("request.method.hook_mm:", report["request"]["method"]["hook_mm"])
if plan is not None:
    for gauge in plan["gauges"]:
        print("  plan gauge:", {k: gauge[k] for k in ("id", "hook_mm", "basis", "stitches_per_10cm", "rows_per_10cm")})
    notes = [n for n in plan["review_notes"] if "尺寸来源" in n or "输入密度来源" in n]
    for note in notes:
        print("  review note:", note[:130])
    from reportlab.platypus import Paragraph

    from app.models.working_path import WorkingPath
    from app.utils.working_recipe_export import export_working_recipe_pdf
    captured = []
    original = Paragraph.__init__

    def spy(self, text, *args, **kwargs):
        captured.append(re.sub(r"<[^>]+>", "", text))
        original(self, text, *args, **kwargs)

    Paragraph.__init__ = spy
    try:
        export_working_recipe_pdf(WorkingPath.model_validate(plan))
    finally:
        Paragraph.__init__ = original
    for line in captured:
        if "mm；" in line:
            print("  PDF line:", line)
