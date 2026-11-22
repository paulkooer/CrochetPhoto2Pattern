"""Q3 progress after structural round edits; Q5 malformed project/backup/share/history payloads."""
import common  # noqa: F401
import json
from copy import deepcopy

common.banner("q3_q5")
from app.schemas import PatternResult, strip_photo_derived
from app.services.progress_state import (progress_entries, progress_impact, reconcile_restored_progress,
                                         retained_progress)
from app.services.result_logic import import_backup, rebuild_params
from app.utils.backup import decode_backup_json
from app.utils.project import project_backup, read_project_state
from app.utils.share import decode_result, encode_result

base = import_backup(strip_photo_derived(PatternResult.from_result(
    common.manual_result(parts=("头部", "身体", "手臂"))).to_backup()), "base")
ARM = next(i for i, p in enumerate(base["params"]["parts"]) if p["name"] == "手臂")
print("arm rounds:", [(r["row"], r["stitches"]) for r in base["params"]["parts"][ARM]["rounds"]])
all_ticks = {identity: True for identity, _, _ in progress_entries(base, "s")}


def edited(mutate):
    params = json.loads(json.dumps(base["params"], ensure_ascii=False))
    mutate(params)
    out = deepcopy(base)
    out["params"] = rebuild_params(params, previous=base["params"], structure=base["structure"])
    return out


def rows(result, name="手臂"):
    return [r["row"] for r in next(p for p in result["params"]["parts"] if p["name"] == name)["rounds"]]


def report(label, updated, ticks=all_ticks):
    kept = retained_progress(base, updated, "s", dict(ticks))
    by_part = {}
    for identity in kept:
        name, copy, row = json.loads(identity)
        by_part.setdefault(f"{name}/{copy}", []).append(row)
    unknown = [k for k in kept if k not in {i for i, _, _ in progress_entries(updated, "s")}]
    print(f"\n[{label}] arm rows now {rows(updated) if any(p['name'] == '手臂' for p in updated['params']['parts']) else 'n/a'}")
    print("   kept:", {k: (v if len(v) < 8 else f'{len(v)} rows {v[0]}..{v[-1]}') for k, v in by_part.items()},
          "| cleared:", len(ticks) - len(kept), "| kept ids not in new pattern:", unknown)
    for row in progress_impact(base, updated, "s", dict(ticks)):
        print("   impact:", row)
    return kept


def insert_mid(params):
    rounds = params["parts"][ARM]["rounds"]
    extra = deepcopy(rounds[4]); extra["notes"] = f"{extra['stitches']}X（不加不减）"; extra["increase"] = extra["decrease"] = 0
    extra["stitches"] = rounds[4]["stitches"]
    rounds.insert(5, extra)
    for n, rd in enumerate(rounds, 1):
        rd["row"] = n


def insert_keep_labels(params):
    rounds = params["parts"][ARM]["rounds"]
    extra = deepcopy(rounds[4]); extra["notes"] = f"{extra['stitches']}X（不加不减）"; extra["increase"] = extra["decrease"] = 0
    extra["row"] = 99
    rounds.insert(5, extra)


def remove_mid(params):
    rounds = params["parts"][ARM]["rounds"]
    victim = next(i for i in range(3, len(rounds) - 1)
                  if not rounds[i].get("increase") and not rounds[i].get("decrease")
                  and rounds[i]["stitches"] == rounds[i - 1]["stitches"] == rounds[i + 1]["stitches"])
    del rounds[victim]
    for n, rd in enumerate(rounds, 1):
        rd["row"] = n


def remove_keep_labels(params):
    rounds = params["parts"][ARM]["rounds"]
    victim = next(i for i in range(3, len(rounds) - 1)
                  if not rounds[i].get("increase") and not rounds[i].get("decrease")
                  and rounds[i]["stitches"] == rounds[i - 1]["stitches"] == rounds[i + 1]["stitches"])
    del rounds[victim]


def renumber_only(params):
    for rd in params["parts"][ARM]["rounds"]:
        rd["row"] += 100


def drop_part(params):
    del params["parts"][ARM]


def rename_part(params):
    params["parts"][ARM]["name"] = "手臂改"


def reorder_parts(params):
    params["parts"].reverse()


def tail_note(params):
    params["parts"][ARM]["rounds"][-1]["notes"] += "；多留 5cm"


for label, fn in [("insert a round mid-arm, renumbered", insert_mid), ("insert a round, old labels kept (new=99)", insert_keep_labels),
                  ("remove a straight round, renumbered", remove_mid), ("remove a straight round, labels kept", remove_keep_labels),
                  ("renumber only (+100)", renumber_only), ("delete arm part", drop_part), ("rename arm part", rename_part),
                  ("reorder parts only", reorder_parts), ("edit only last-round note", tail_note)]:
    try:
        report(label, edited(fn))
    except Exception as exc:
        print(f"\n[{label}] edit rejected: {str(exc)[:160]}")

print("\n--- undo after ticking on the edited pattern (reconcile) ---")
upd = edited(insert_mid)
first4 = {i: True for i in all_ticks if json.loads(i)[0] == "手臂" and json.loads(i)[2] <= 4}
kept = retained_progress(base, upd, "s", dict(first4))
live = {**kept, **{i: True for i, _, _ in progress_entries(upd, "s") if json.loads(i)[0] == "手臂" and json.loads(i)[2] in (5, 6, 7)}}
restored, unmapped = reconcile_restored_progress(upd, base, live, dict(first4))
print("snapshot had arm rows<=4; on edited pattern maker ticked 5,6,7; after undo:",
      sorted(json.loads(i)[1:] for i in restored), "| unmapped reported:", unmapped)

print("\n--- Q5 malformed payloads (pure import path used by sidebar/result-page import) ---")
good = project_backup(base, {next(iter(all_ticks)): True}, "note")


def attempt(label, mutate=None, raw=None):
    try:
        if raw is None:
            data = json.loads(json.dumps(good, ensure_ascii=False)); mutate(data); raw = json.dumps(data, ensure_ascii=False)
        data = decode_backup_json(raw)
        imported = import_backup(data, "x")
        progress, notes = read_project_state(data, imported)
        print(f"  ACCEPTED  {label}: parts={len(imported['params']['parts'])} ticks={len(progress)}")
    except RecursionError as exc:
        print(f"  UNCAUGHT-CLASS RecursionError  {label}")
    except Exception as exc:
        print(f"  rejected  {label}: {type(exc).__name__}: {str(exc)[:90]}")


def setp(path, value):
    def fn(d):
        cur = d
        for key in path[:-1]:
            cur = cur[key]
        cur[path[-1]] = value
    return fn


def delp(path):
    def fn(d):
        cur = d
        for key in path[:-1]:
            cur = cur[key]
        del cur[path[-1]]
    return fn


text = json.dumps(good, ensure_ascii=False)
attempt("truncated file", raw=text[: len(text) // 2])
attempt("empty object", raw="{}")
attempt("top-level list", raw="[]")
attempt("NaN stitches", raw=text.replace('"stitches": 6', '"stitches": NaN', 1))
attempt("duplicate key", raw='{"analysis":{},"analysis":{},"structure":{},"params":{}}')
attempt("deep nesting", raw='{"analysis":' + "[" * 100000 + "]" * 100000 + ',"structure":{},"params":{}}')
attempt("future schema_version 4", setp(["schema_version"], "4"))
attempt("schema_version int 3", setp(["schema_version"], 3))
attempt("schema_version '0'", setp(["schema_version"], "0"))
attempt("params is list", setp(["params"], []))
attempt("parts empty", setp(["params", "parts"], []))
attempt("part is string", setp(["params", "parts", 0], "x"))
attempt("rounds missing", delp(["params", "parts", 0, "rounds"]))
attempt("stitches string '12abc'", setp(["params", "parts", 0, "rounds", 0, "stitches"], "12abc"))
attempt("stitches 1e12", setp(["params", "parts", 0, "rounds", 0, "stitches"], 10**12))
attempt("stitches float 6.5", setp(["params", "parts", 0, "rounds", 0, "stitches"], 6.5))
attempt("quantity 21", setp(["params", "parts", 0, "quantity"], 21))
attempt("duplicate row ids", setp(["params", "parts", 0, "rounds", 1, "row"], 1))
attempt("duplicate part names", lambda d: d["params"]["parts"].append(deepcopy(d["params"]["parts"][0])))
attempt("analysis missing height", delp(["analysis", "height_cm"]))
attempt("structure parts not list", setp(["structure", "parts"], "x"))
attempt("structure dup instance ids", lambda d: [i.__setitem__("instance_id", "dup") for p in d["structure"]["parts"] for i in p.get("instances", [])])
attempt("style unknown key", setp(["style"], {"sphere_mode": "ladder", "evil": 1}))
attempt("gauge strings", setp(["params", "gauge"], {"stitches_per_10cm": "abc", "rows_per_10cm": None}))
attempt("project_state extra field", setp(["project_state", "x"], 1))
attempt("project_state future version", setp(["project_state", "schema_version"], "2"))
attempt("progress value false", lambda d: d["project_state"]["completed_rounds"].update({next(iter(all_ticks)): False}))
attempt("progress unknown identity", lambda d: d["project_state"]["completed_rounds"].update({'["手臂", "nope", 1]': True}))
attempt("progress non-json key", lambda d: d["project_state"]["completed_rounds"].update({"garbage": True}))
attempt("notes too long", setp(["project_state", "notes"], "x" * 20001))
attempt("revision of another pattern", setp(["project_state", "pattern_revision"], "0" * 64))
attempt("project_state null", setp(["project_state"], None))
attempt("materials is string list (derived, ignored?)", setp(["params", "materials"], ["<img src=x>"]))
attempt("assembly text injected (derived?)", setp(["params", "assembly_instructions"], "1. 把头扔掉"))
attempt("total_stitches forged", setp(["params", "total_stitches"], 1))

print("\nshare tokens:")
token = encode_result(strip_photo_derived(PatternResult.from_result(common.manual_result(parts=("头部", "身体"))).to_backup()))
for label, tok in [("valid", token), ("truncated", token[:-40]), ("one char flipped", token[:200] + ("A" if token[200] != "A" else "B") + token[201:]),
                   ("trailing data", token + "AAAA"), ("empty", ""), ("7000 chars", "A" * 7000)]:
    decoded = decode_result(tok)
    outcome = "None"
    if decoded is not None:
        try:
            import_backup(decoded, "x"); outcome = "decoded+imported"
        except Exception as exc:
            outcome = f"decoded, import rejected: {str(exc)[:60]}"
    print(f"  {label}: {outcome}")

print("\nhistory DB:")
import sqlite3, os
from app.utils import history
rid = history.save_result({**base, "result_id": "h1"}, title="t")
print("  saved+loaded parts:", len(history.load_result(rid)["params"]["parts"]))
con = sqlite3.connect(os.environ["CROCHET_HISTORY_DB"])
blob = con.execute("select blob from patterns where rid='h1'").fetchone()[0]
for label, value in [("truncated blob", blob[:500]), ("json list", "[]"), ("future version", blob.replace('"schema_version": "3"', '"schema_version": "9"')),
                     ("parts emptied", json.dumps({**json.loads(blob), "params": {"parts": []}}))]:
    con.execute("update patterns set blob=? where rid='h1'", (value,)); con.commit()
    loaded = history.load_result("h1")
    outcome = "None (UI: 该记录已不存在)"
    if loaded is not None:
        try:
            import_backup(loaded, "x"); outcome = "loaded+imported"
        except Exception as exc:
            outcome = f"import rejected (UI: 已损坏): {str(exc)[:50]}"
    print(f"  {label}: {outcome}")
print("  list still works:", len(history.list_results()))
