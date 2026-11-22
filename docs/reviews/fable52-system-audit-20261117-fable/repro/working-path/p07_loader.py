"""Area 5: loader (read_path, used by CLI and UI) versus the Python API."""
import json
import time

from _common import SCRATCH, attempt, plan, route, show, span, work
from app.models.working_path import WorkingPath, armhole_path_demo, compile_working_path
from app.working_paths import MAX_PLAN_BYTES, main, read_path


def raw(text, label):
    try:
        model = read_path(text if isinstance(text, bytes) else text.encode())
        compile_working_path(model)
        print(f"{label}: ACCEPT")
        return model
    except ValueError as exc:
        first = str(exc).splitlines()
        print(f"{label}: REJECT ({type(exc).__name__}) :: {' | '.join(s.strip() for s in first[:3])[:230]}")
    except Exception as exc:  # noqa: BLE001 - the point is to see what escapes the ValueError contract
        print(f"{label}: UNCAUGHT {type(exc).__name__} :: {str(exc)[:200]}")
    return None


demo = armhole_path_demo().model_dump()
good = json.dumps(demo, ensure_ascii=False)

print("== strict JSON ==")
raw(good, "demo round trip")
raw(good.replace('"title":', '"title": "x", "title":', 1), "duplicate top-level key")
raw(good.replace('"count": 28', '"count": 28, "count": 3', 1), "duplicate nested key")
raw(good.replace('"count": 28', '"count": 28.0', 1), "float for int")
raw(good.replace('"count": 28', '"count": "28"', 1), "string for int")
raw(good.replace('"count": 28', '"count": true', 1), "bool for int")
raw(good.replace('"count": 28', '"count": NaN', 1), "NaN")
raw(good.replace('"count": 28', '"count": 1e999', 1), "overflowing float")
raw(good.replace('"count": 28', '"count": ' + "9" * 5000, 1), "5000-digit integer")
raw(good.replace('"corner_sites": false', '"corner_sites": 0', 1), "0 for bool")
raw(good.replace('"final_edges"', '"extra": 1, "final_edges"', 1), "unknown top-level key")
raw(good.replace('"kind": "hold"', '"kind": "hold", "reserve": true', 1), "unknown step key")
raw(good.replace('"kind": "hold"', '"kind": "Hold"', 1), "wrong-case discriminator")
raw("[" + good + "]", "top-level list")
raw('"just a string"', "top-level string")
raw("", "empty file")
raw(b"\xef\xbb\xbf" + good.encode(), "UTF-8 BOM")
raw(good.encode("utf-16"), "UTF-16")
raw("[" * 200_000, "200k nested arrays")
raw('{"a":' * 100_000 + "1" + "}" * 100_000, "100k nested objects")
raw(b" " * (MAX_PLAN_BYTES + 1), "2 MiB + 1 of spaces")
raw(good.replace('"袖窿工作路径演示小样（不是完整衣物图解）"', '"\\ud800"', 1), "lone surrogate in title")
raw(good.replace('"袖窿工作路径演示小样（不是完整衣物图解）"', '"a\\u0000b"', 1), "NUL in title")

print("== strict typing of floats written as integers (hand-written JSON) ==")
tracked = {"schema_version": "working-path-v2", "title": "t", "yarn_tracking": True, "steps": [
    {"kind": "new_yarn", "id": "n", "label": "n", "yarn": "y", "method": "foundation_chain", "side": "RS"},
    {"kind": "foundation_chain", "id": "ch", "label": "ch", "chains": 4, "work_face": "underside", "other_face": "top"},
    {"kind": "route", "id": "row", "label": "row", "expected_sites": 3, "mode": "flat", "side": "RS",
     "row_direction": "forward", "gauge": "g",
     "operations": [{"kind": "work", "source": {"edge": "ch", "first": 1, "last": 3, "face": "underside"}}]},
    {"kind": "fasten_off", "id": "f", "label": "f", "yarn": "y", "source": {"edge": "row", "first": 3, "last": 3},
     "tail_cm": 15},
    {"kind": "hold", "id": "o", "label": "o", "spans": [{"edge": "ch", "first": 1, "last": 3}]}],
    "final_edges": ["row", "o"],
    "gauges": [{"id": "g", "method": "sc", "hook_mm": 3, "basis": "unmeasured"}]}
raw(json.dumps(tracked), 'tail_cm: 15 and hook_mm: 3 (JSON integers)')
tracked["steps"][3]["tail_cm"] = 15.0
tracked["gauges"][0]["hook_mm"] = 3.0
raw(json.dumps(tracked), 'tail_cm: 15.0 and hook_mm: 3.0')

print("== schema_version tricks ==")
v1 = json.loads(good)
v1["schema_version"] = "working-path-v1"
raw(json.dumps(v1), "v1 demo")
for label, mutate in [
    ("v1 + flat mode", lambda d: d["steps"][0].update(mode="flat", side="RS", row_direction="forward")),
    ("v1 + section/row_number on a segment route", lambda d: d["steps"][0].update(section="s", row_number=1)),
    ("v1 + turn and turning chain on a segment route", lambda d: d["steps"][0].update(turn="clockwise", turning_chains=2)),
    ("v1 + input_origin manual_instructions + gauges + review_notes",
     lambda d: d.update(input_origin="manual_instructions", review_notes=["n"],
                        gauges=[{"id": "g", "method": "m", "hook_mm": 2.5, "basis": "unmeasured"}])),
    ("v1 + route.gauge", lambda d: (d.update(gauges=[{"id": "g", "method": "m", "hook_mm": 2.5, "basis": "unmeasured"}]),
                                    d["steps"][0].update(gauge="g"))),
    ("v1 + BLO work", lambda d: d["steps"][0]["operations"][0].update(loop="back")),
    ("v1 + slst", lambda d: d["steps"][0]["operations"][0].update(stitch="slst")),
    ("v1 + edge_path step", lambda d: d["steps"].insert(1, {"kind": "edge_path", "id": "ep", "label": "ep",
                                                         "spans": [{"edge": "yoke", "first": 5, "last": 5}]})),
    ("v1 + yarn_tracking true", lambda d: d.update(yarn_tracking=True)),
    ("v1 + underside face span in hold (already in demo)", lambda d: None),
    ("unknown version working-path-v3", lambda d: d.update(schema_version="working-path-v3")),
    ("version omitted (defaults to v2)", lambda d: d.pop("schema_version")),
]:
    data = json.loads(json.dumps(v1))
    mutate(data)
    raw(json.dumps(data), label)

print("== limits ==")
steps601 = [{"kind": "hold", "id": f"h{i}", "label": "h", "spans": [span("seed", i + 1)]} for i in range(601)]
show("601 steps", plan(steps601, existing=[("seed", 1000)], final=[]), expect="REJECT")
show("101 operations in a route", plan([route("r", [work("seed", i + 1) for i in range(101)], 101)],
                                      existing=[("seed", 1000)], final=["r"]), expect="REJECT")
show("21 existing edges", plan([{"kind": "hold", "id": "h", "label": "h", "spans": [span("e0", 1)]}],
                               existing=[(f"e{i}", 1) for i in range(21)], final=[]), expect="REJECT")
edges20 = [(f"e{i}", 1000) for i in range(20)]
show("20 x 1000 existing sites = exactly 20000, nothing created",
     plan([{"kind": "hold", "id": "h", "label": "h", "spans": [span("e0", 1)]}], existing=edges20,
          final=[f"e{i}" for i in range(1, 20)] + ["h"]))
show("20000 sites + one more stitch", plan([route("r", [work("e0", 1)], 1)], existing=edges20,
                                           final=[f"e{i}" for i in range(1, 20)] + ["r"]), expect="REJECT")

print("== CLI behaviour on bad input and wording ==")
import contextlib
import io
import tempfile
from pathlib import Path

with tempfile.TemporaryDirectory(dir=SCRATCH) as tmp:
    bad = Path(tmp) / "bad.json"
    bad.write_text(json.dumps(plan([route("r", [work("seed", 1, 5)], 4)], existing=[("seed", 5)], final=["r"])))
    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        try:
            main(["--plan", str(bad), "--out-dir", str(Path(tmp) / "out")])
        except SystemExit as exc:
            print("exit code:", exc.code, "| out dir created:", (Path(tmp) / "out").exists())
    print("stderr:", err.getvalue().strip())
    missing = io.StringIO()
    with contextlib.redirect_stderr(missing):
        try:
            main(["--plan", str(Path(tmp) / "nope.json"), "--out-dir", str(Path(tmp) / "out2")])
        except SystemExit as exc:
            print("missing file exit code:", exc.code)
    print("stderr:", missing.getvalue().strip()[:160])
