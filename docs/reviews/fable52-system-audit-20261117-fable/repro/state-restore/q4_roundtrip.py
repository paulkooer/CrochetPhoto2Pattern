"""Q4: save -> restore round trip, revision stability, trial byte binding (pure functions)."""
import common  # noqa: F401  (must be first)
import io, json, zipfile
from copy import deepcopy

common.banner("q4_roundtrip")
from app.schemas import PART_NAMES, PatternResult, strip_photo_derived
from app.services.result_logic import (import_backup, rebuild_params, regenerate_with_head_opening,
                                       regenerate_with_size)
from app.services.progress_state import progress_entries
from app.utils.backup import decode_backup_json
from app.utils.project import pattern_revision, project_backup, read_project_state
from app.utils.share import decode_result, encode_result
from app.utils.trial_bundle import (create_trial_bundle, decode_trial_bundle, encode_trial_bundle,
                                    update_trial_bundle)
from app.ui.pattern_editor import edit_rounds, edit_yarn


def diff(a, b, path="", out=None, limit=12):
    out = [] if out is None else out
    if len(out) >= limit:
        return out
    if type(a) is not type(b):
        out.append(f"{path}: {type(a).__name__} {str(a)[:60]!r} -> {type(b).__name__} {str(b)[:60]!r}")
    elif isinstance(a, dict):
        for k in dict.fromkeys([*a, *b]):
            if k not in a:
                out.append(f"{path}/{k}: <absent> -> {str(b[k])[:60]!r}")
            elif k not in b:
                out.append(f"{path}/{k}: {str(a[k])[:60]!r} -> <absent>")
            else:
                diff(a[k], b[k], f"{path}/{k}", out, limit)
    elif isinstance(a, list):
        if len(a) != len(b):
            out.append(f"{path}: len {len(a)} -> {len(b)}")
        for i, (x, y) in enumerate(zip(a, b)):
            diff(x, y, f"{path}[{i}]", out, limit)
    elif a != b:
        out.append(f"{path}: {str(a)[:60]!r} -> {str(b)[:60]!r}")
    return out


def backup_of(r):
    return json.loads(json.dumps(strip_photo_derived(PatternResult.from_result(r).to_backup()), ensure_ascii=False))


scenarios = {}
scenarios["S1 manual default(头部,身体)"] = common.manual_result(parts=("头部", "身体"))
full = common.manual_result(parts=tuple(PART_NAMES))
scenarios["S2 manual all parts"] = full
scenarios["S4 smoke _mock_result"] = common.mock_result("mock-1")
for label, build in {
    "S3 manual one-piece + attached skirt": lambda: common.manual_result(
        parts=tuple(PART_NAMES), one_piece=True, skirt_style="attached"),
    "S3b manual attached skirt": lambda: common.manual_result(parts=tuple(PART_NAMES), skirt_style="attached"),
    "S5 S2 + resize(10,20)": lambda: regenerate_with_size(full, 10.0, 20.0),
    "S7 S2 + yarn spec": lambda: edit_yarn(full, {"ball_weight_g": 50, "ball_length_m": 125, "waste_percent": 10,
                                                   "swatch_weight_g": 5, "swatch_stitches": 20, "swatch_rows": 20}),
    "S8 S2 + head opening 16": lambda: regenerate_with_head_opening(full, 16),
}.items():
    try:
        scenarios[label] = build()
    except Exception as exc:
        print(f"[build-failed] {label}: {type(exc).__name__}: {exc}")
# S6: table edit of one arm round note (hand-written instruction)
arm_index = next(i for i, p in enumerate(full["params"]["parts"]) if p["name"] == "手臂")
rounds = deepcopy(full["params"]["parts"][arm_index]["rounds"])
rounds[2]["notes"] = (rounds[2].get("notes") or "") + "；此圈换记号扣"
scenarios["S6 S2 + round note edit"] = edit_rounds(full, arm_index, rounds)
# S9: photo path through the real orchestrator in mock mode with a synthetic image
try:
    from PIL import Image, ImageDraw
    from app.models.gauge import ShapingStyle, gauge_from_ui
    from app.models.orchestrator import PipelineOrchestrator
    from app.models.sizing import DEFAULT_PROPORTION_STYLE

    img = Image.new("RGB", (240, 360), "white")
    d = ImageDraw.Draw(img)
    d.ellipse((70, 20, 170, 120), fill=(240, 200, 170)); d.rectangle((85, 120, 155, 300), fill=(60, 90, 200))
    draft = PipelineOrchestrator().prepare_photo(img, vision_mode="mock", budget_seconds=120.0)
    scenarios["S9 photo(mock vision, synthetic image)"] = PipelineOrchestrator.generate_from_draft(
        draft, analysis=draft.analysis, gauge=gauge_from_ui("classic", None, None),
        style=ShapingStyle(sphere_mode="ladder", one_piece=False, skirt_style="ring", ruffle_hem=False),
        target_height_cm=18.0, target_height_source="user_photo_target", run_trace=deepcopy(draft.trace),
        proportion_style=DEFAULT_PROPORTION_STYLE)
    scenarios["S9 photo(mock vision, synthetic image)"]["result_id"] = "photo-1"
except Exception as exc:
    print(f"[build-failed] S9 photo: {type(exc).__name__}: {exc}")

print("\n--- A. live result vs. its own backup re-imported (what a maker gets back) ---")
for label, r in scenarios.items():
    r.setdefault("result_id", "rid-" + label[:2])
    b = backup_of(r)
    imp = import_backup(deepcopy(b), "imp-1")
    b2 = backup_of(imp)
    imp2 = import_backup(deepcopy(b2), "imp-2")
    live, back, again = pattern_revision(r), pattern_revision(imp), pattern_revision(imp2)
    changes = diff(b, b2)
    rebuilt = rebuild_params(json.loads(json.dumps(r["params"], ensure_ascii=False)), structure=r["structure"])
    hist = diff(json.loads(json.dumps(r["params"], ensure_ascii=False)), json.loads(json.dumps(rebuilt, ensure_ascii=False)))
    try:
        bundle = create_trial_bundle(r, trial_id="t-1", maker_id="maker-a")
        trial = "same" if bundle.source_revision == live else "DIFFERENT"
    except Exception as exc:
        trial = f"n/a ({str(exc)[:40]})"
    token = encode_result(b)
    share = "too large" if token is None else f"{len(token)} chars"
    if token:
        assert pattern_revision(import_backup(decode_result(token), "s")) == back
    print(f"{label}\n   revision live={live[:10]} reimported={back[:10]} reimported-twice={again[:10]}"
          f" | live==reimported: {live == back} | idempotent: {back == again}"
          f"\n   trial source_revision vs live: {trial} | top-level gauge live={r.get('gauge')!r}"
          f"\n   share token: {share} | rebuild_params(history-save path) changes: {len(hist)}")
    for line in changes:
        print("     backup-diff", line)
    for line in hist[:6]:
        print("     history-diff", line)

print("\n--- B. project file: progress + notes round trip ---")
r = scenarios["S6 S2 + round note edit"]
entries = [identity for identity, _, _ in progress_entries(r, "result")]
progress = {identity: True for identity in entries[::3]}
payload = json.dumps(project_backup(r, progress, "4.0mm 钩针；左臂停在第 5 圈"), ensure_ascii=False)
data = decode_backup_json(payload)
restored = import_backup(data, "proj-1")
got_progress, got_notes = read_project_state(data, restored)
print("progress identical:", got_progress == progress, f"({len(progress)} ticks)", "| notes identical:",
      got_notes == "4.0mm 钩针；左臂停在第 5 圈")
print("params diff saved-file vs restored session:", diff(data["params"], json.loads(json.dumps(restored["params"], ensure_ascii=False))) or "none")
print("project_state keys:", sorted(data["project_state"]), "| top-level keys dropped vs session:",
      sorted(set(r) - set(data)))
tampered = json.loads(payload); tampered["params"]["parts"][0]["rounds"][1]["notes"] = "改过的说明"
try:
    read_project_state(tampered, import_backup(deepcopy(tampered), "x")); print("tampered project: ACCEPTED")
except Exception as exc:
    print("tampered project rejected:", exc)

print("\n--- C. trial bundle bound to exact pattern bytes ---")
bundle = create_trial_bundle(full, trial_id="t-9", maker_id="maker-a")
bundle = update_trial_bundle(bundle, swatch={"measured": True, "stitches_per_10cm": 14.0, "rows_per_10cm": 17.0,
                                             "hook_mm": 4.0, "yarn_brand": None, "yarn_line": None,
                                             "yarn_lot": None, "fiber": None},
                             observation={"overall_height_cm": 17.5}, completed=False)
archive = encode_trial_bundle(bundle)
members = {i.filename: zipfile.ZipFile(io.BytesIO(archive)).read(i.filename)
           for i in zipfile.ZipFile(io.BytesIO(archive)).infolist()}
print("members:", {k: len(v) for k, v in members.items()})
again = decode_trial_bundle(archive)
print("reopen: source bytes identical:", again.source == bundle.source, "| record equal:", again.record == bundle.record,
      "| draft equal:", again.draft == bundle.draft, "| re-encode byte-identical:", encode_trial_bundle(again) == archive)


def rezip(changed):
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for name, blob in {**members, **changed}.items():
            z.writestr(name, blob)
    return out.getvalue()


pattern = json.loads(members["pattern.json"])
note_changed = deepcopy(pattern); note_changed["params"]["parts"][0]["rounds"][3]["notes"] = "改过的说明"
count_kept = deepcopy(pattern); count_kept["params"]["parts"][0]["color"] = "红色"
record_name = next(n for n in members if n.endswith(".trial.json"))
record = json.loads(members[record_name])
record_changed = deepcopy(record); record_changed["swatch"]["stitches_per_10cm"] = 15.0
for label, changed in {
    "pattern.json: one round note edited": {"pattern.json": json.dumps(note_changed, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()},
    "pattern.json: part colour edited": {"pattern.json": json.dumps(count_kept, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()},
    "pattern.json: same content, re-indented": {"pattern.json": json.dumps(pattern, ensure_ascii=False, indent=2).encode()},
    "trial.json: swatch edited, draft.json kept": {record_name: json.dumps(record_changed, ensure_ascii=False, indent=2).encode()},
    "trial.json: re-indented only, draft.json kept": {record_name: json.dumps(record, ensure_ascii=False).encode()},
}.items():
    try:
        decode_trial_bundle(rezip(changed)); print(f"  {label}: ACCEPTED")
    except Exception as exc:
        print(f"  {label}: rejected -> {str(exc)[:110]}")
