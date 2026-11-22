"""Fresh manual result: is an untouched JSON apply a no-op? Does a trial made after any edit bind correctly?"""
import common  # noqa: F401
common.banner("q2b_fresh_manual_noop")
from streamlit.testing.v1 import AppTest
from app.utils.project import pattern_revision

at = AppTest.from_file(common.APP_MAIN, default_timeout=120)
at.run()
at.button(key="btn_manual").click().run()
r = at.session_state["manual_result"]; rid = r["result_id"]; rev = pattern_revision(r)
print("fresh: gauge", r.get("gauge"), "params.gauge", r["params"].get("gauge"))
at.button(key=f"all_{rid}_头部").click().run()
at.button(key=f"json_open_{rid}").click().run()
at.button(key=f"regen_{rid}").click().run()
r2 = at.session_state["manual_result"]
h = at.session_state["edit_history_manual_result"]
print("untouched JSON apply -> new result_id:", r2["result_id"] != rid, "| revision changed:", pattern_revision(r2) != rev,
      "| gauge now", r2.get("gauge"), "| undo depth", len(h["undo"]),
      "| ticks kept", len(at.session_state["project_progress_manual_result"]["completed"]),
      "| success:", [str(s.value)[:30] for s in at.success if "已根据" in str(s.value)], "| exc", len(at.exception))
at.text_input(key="trial_maker_manual_result").input("maker-a")
next(b for b in at.button if b.label == "以当前图解新建试钩").click().run()
tw = at.session_state["trial_workspace_manual_result"]
print("trial created after that apply: source_revision == live:",
      tw["bundle"].source_revision == pattern_revision(at.session_state["manual_result"]),
      "| mismatch warning shown:", any("试钩原图解不同" in str(w.value) for w in at.warning))
