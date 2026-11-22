"""Q1/Q2 through Streamlit AppTest: export freshness and identity cross-talk on the manual tab."""
import common  # noqa: F401
import hashlib, json
from copy import deepcopy

common.banner("q1_q2_apptest")
from streamlit.testing.v1 import AppTest
from app.schemas import PatternResult, strip_photo_derived
from app.utils.exporters import export_markdown
from app.utils.project import pattern_revision

SLOT = "manual_result"
at = AppTest.from_file(common.APP_MAIN, default_timeout=120)
at.run(); assert not at.exception


def res():
    return at.session_state[SLOT]


def ws():
    return at.session_state[f"workspace_{SLOT}"]


def state(label):
    r, w = res(), ws()
    pdf = w["pdf"]
    md = (w["export_cache"].get("markdown") or {}).get("value")
    fresh = export_markdown(r["params"], r["analysis"], result=r)
    record = at.session_state[f"project_progress_{SLOT}"] if f"project_progress_{SLOT}" in at.session_state else None
    dl_pdf = [b for b in at.get("download_button") if "PDF" in str(getattr(b.proto, "label", ""))]
    print(f"[{label}] rid={r['result_id']} rev={pattern_revision(r)[:10]} ws.rid_match={w['result_id'] == r['result_id']}"
          f" pdf={'none' if pdf is None else hashlib.sha256(pdf['bytes']).hexdigest()[:10]}"
          f" pdf_download_shown={bool(dl_pdf)} share={'none' if w['share'] is None else 'set'}"
          f" md_cache_is_current={md == fresh} ticks={0 if not record else len(record['completed'])}"
          f" record_rid_match={None if not record else record['result_id'] == r['result_id']}"
          f" errors={[str(e.value)[:80] for e in at.error]} exc={len(at.exception)}")
    return r["result_id"]


def click(key):
    at.button(key=key).click().run()


at.multiselect(key="m_parts").set_value(["头部", "身体", "手臂"]).run()
click("btn_manual")
rid = state("generated A")
first = deepcopy(res())

print("\n--- trial bound to a freshly generated manual result ---")
at.text_input(key=f"trial_maker_{SLOT}").input("maker-a")
submit = [b for b in at.button if "以当前图解新建试钩" in str(b.label)]
submit[0].click().run()
tw = at.session_state[f"trial_workspace_{SLOT}"]
print("trial source_revision == pattern_revision(live result):", tw["bundle"].source_revision == pattern_revision(res()),
      "| live top-level gauge:", res().get("gauge"))
print("warnings mentioning 试钩原图解:", [str(w.value)[:60] for w in at.warning if "试钩原图解" in str(w.value)])
measured = [c for c in at.checkbox if c.key and c.key.endswith("_measured")][0]
measured.set_value(True)
[n for n in at.number_input if n.key and n.key.endswith("_stitches_per_10cm")][0].set_value(15.0)
[b for b in at.button if "保存记录并更新下载" in str(b.label)][0].click().run()
tw = at.session_state[f"trial_workspace_{SLOT}"]
print("saved swatch:", tw["bundle"].record.swatch.measured, tw["bundle"].record.swatch.stitches_per_10cm,
      "| 预览按实测密度重算 disabled:", at.button(key=f"trial_gauge_preview_{SLOT}").disabled)
print("captions:", [str(c.value)[:50] for c in at.caption if "重算入口仅用于" in str(c.value)])

print("\n--- Q1 export freshness ---")
click(f"pdf_gen_{rid}"); click(f"share_{rid}")
click(f"all_{rid}_头部")
arm = [c for c in at.checkbox if c.key and c.key.startswith(f"chk_{rid}_手臂_")]
arm[0].check().run(); arm[1].check().run()
state("A + pdf + share + ticks")
pdf_a = ws()["pdf"]["bytes"]

at.slider(key=f"sz_head_{rid}").set_value(10.0).run()
click(f"sz_go_{rid}")
rid2 = state("after size edit")
print("   notices:", [str(w.value)[:70] for w in at.warning if "清除" in str(w.value)])
click(f"pdf_gen_{rid2}")
state("pdf regenerated for edited")
print("   new pdf differs from A pdf:", ws()["pdf"]["bytes"] != pdf_a)
click(f"edit_{rid2}_undo")
rid3 = state("after undo")
print("   undo restored A content:", pattern_revision(res()) == pattern_revision(first))
click(f"edit_{rid3}_redo")
rid4 = state("after redo")

# no-op: JSON editor "重新生成" with untouched text
click(f"json_open_{rid4}")
before = pattern_revision(res())
click(f"regen_{rid4}")
rid5 = state("after untouched JSON 重新生成")
print("   result_id changed by a no-op apply:", rid5 != rid4, "| revision changed:", pattern_revision(res()) != before,
      "| success:", [str(s.value)[:40] for s in at.success], "| info:", [str(i.value)[:40] for i in at.info if "相同" in str(i.value)])
click(f"regen_{rid5}")
rid6 = state("second untouched 重新生成")
print("   second no-op changed id:", rid6 != rid5)

# load another project into the same tab while a PDF is prepared
click(f"pdf_gen_{rid6}")
state("pdf prepared before import")
other = common.manual_result(parts=("头部", "身体", "腿部"), head=8.0, height=20.0)
backup = json.dumps(strip_photo_derived(PatternResult.from_result(other).to_backup()), ensure_ascii=False)
at.text_area(key=f"import_{rid6}").set_value(backup).run()
click(f"importbtn_{rid6}")
rid7 = state("after importing another pattern")
print("   trial workspace still present after import:", f"trial_workspace_{SLOT}" in at.session_state,
      "| edit history reset:", at.session_state[f"edit_history_{SLOT}"]["undo"] == [])

print("\n--- Q2 identical content, new generation ---")
at.multiselect(key="m_parts").set_value(["头部", "身体", "手臂"]).run()
click("btn_manual")
rid8 = state("regenerated same spec as A")
print("   same content as A:", pattern_revision(res()) == pattern_revision(first), "| new id:", rid8 != rid,
      "| leftover chk_/notes keys of older ids:",
      [k for k in at.session_state._state.filtered_state if any(old in str(k).split("_") for old in (rid, rid2, rid3, rid4, rid5, rid6, rid7))][:5])
at.text_area(key=f"project_notes_{rid8}").set_value("A 的备注").run()
click(f"all_{rid8}_头部")
state("ticks+notes on regenerated")
# photo tab gets a result with byte-identical content: nothing may leak across tabs
twin = deepcopy(res()); twin["result_id"] = "twin00000001"
at.session_state["result"] = twin
at.run()
rec = at.session_state["project_progress_result"] if "project_progress_result" in at.session_state else None
print("photo-tab twin: ticks", None if rec is None else len(rec["completed"]), "| notes",
      repr(at.session_state["workspace_result"]["notes"]), "| pdf", at.session_state["workspace_result"]["pdf"],
      "| exc", len(at.exception))
click("all_twin00000001_身体")
print("after ticking twin body: manual ticks", len(at.session_state[f'project_progress_{SLOT}']['completed']),
      "| twin ticks", len(at.session_state['project_progress_result']['completed']))
