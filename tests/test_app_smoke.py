"""Smoke tests for the Streamlit UI layer (app/main.py) via AppTest.

app.models 的单元测试永远不会执行 main.py——这类冒烟测试专门捕获
启动级故障：NameError（如 tab_grid 未定义）、DuplicateWidgetID、
注解语法兼容问题等。无需浏览器，直接进 pytest 套件。
"""
from pathlib import Path

from streamlit.testing.v1 import AppTest

from app.models.crochet_params import CrochetParamsGenerator
from app.models.image_parser import ImageParser
from app.models.structure_designer import StructureDesigner

_APP = str(Path(__file__).resolve().parent.parent / "app" / "main.py")


def _mock_result(result_id: str) -> dict:
    analysis = ImageParser._mock_analysis()
    structure = StructureDesigner.design_3d_structure(analysis)
    params = CrochetParamsGenerator.generate_params(analysis, structure)
    return {
        "analysis": analysis.model_dump(),
        "structure": structure,
        "params": params,
        "result_id": result_id,
        "usage": {},
        "vision_meta": {},
        "gauge": {"stitches_per_10cm": 13.0, "rows_per_10cm": 16.0},
        "style": {"sphere_mode": "ladder", "one_piece": False,
                  "skirt_style": "ring", "ruffle_hem": False},
        "color_bands": None, "spans": None, "spans_measured": [],
        "preview": None,
        "sizing": {"source": "test", "absolute_scale_from_photo": False,
                   "note": "测试显式尺寸"},
        "geometry": {"schema_version": "1.0", "silhouette": None,
                     "used_for_generation": False, "limitations": []},
    }


def test_app_boots_without_exception():
    """The script must run top-to-bottom with no uncaught exception."""
    at = AppTest.from_file(_APP, default_timeout=30)
    at.run()
    assert not at.exception
    assert at.slider(key="photo_target_height").value == 18.0


def test_both_tabs_with_results_render_together():
    """照片 Tab 与手动 Tab 的结果同屏渲染时不得发生 widget key 冲突。"""
    # 双结果会生成两组环形图、符号条和完整逐圈控件；覆盖率模式与冷启动
    # 环境下可能超过 30 秒，但正常会在 60 秒内完成。
    at = AppTest.from_file(_APP, default_timeout=60)
    at.session_state["result"] = _mock_result("smoke-photo-1")
    at.session_state["manual_result"] = _mock_result("smoke-manual-1")
    at.run()
    assert not at.exception


def test_mark_all_done_button_checks_every_round():
    """「全部完成」必须真正勾上所有圈（回归：旧实现被 checkbox 状态覆盖而静默失效）。"""
    at = AppTest.from_file(_APP, default_timeout=30)
    at.session_state["result"] = _mock_result("smoke-photo-2")
    at.run()
    assert not at.exception

    at.button(key="all_smoke-photo-2_头部").click().run()
    assert not at.exception
    head_checks = [
        c for c in at.checkbox
        if c.key and c.key.startswith("chk_smoke-photo-2_头部_")
    ]
    assert head_checks, "未找到头部的逐圈 checkbox"
    assert all(c.value for c in head_checks)


def test_symmetric_pair_progress_tracks_both_physical_copies():
    """双臂共享圈序，但两份实体必须有独立进度且「全部完成」覆盖两份。"""
    at = AppTest.from_file(_APP, default_timeout=30)
    at.session_state["result"] = _mock_result("smoke-pair-progress")
    at.run()
    assert not at.exception

    arms = next(
        part for part in at.session_state["result"]["params"]["parts"]
        if part.name == "手臂")
    at.button(key="all_smoke-pair-progress_手臂").click().run()
    arm_checks = [
        checkbox for checkbox in at.checkbox
        if checkbox.key and checkbox.key.startswith(
            "chk_smoke-pair-progress_手臂_")
    ]
    assert len(arm_checks) == len(arms.rounds) * 2
    assert any("_copy2_" in checkbox.key for checkbox in arm_checks)
    assert all(checkbox.value for checkbox in arm_checks)


def test_manual_tab_generates_result_end_to_end():
    """手动 Tab：默认参数点击生成 → 无异常且渲染出结果。"""
    at = AppTest.from_file(_APP, default_timeout=30)
    at.run()
    assert not at.exception

    at.button(key="btn_manual").click().run()
    assert not at.exception
    assert "manual_result" in at.session_state
    assert at.session_state["manual_result"]["analysis"]["parts"] == ["头部", "身体"]


def test_manual_regenerate_applies_edited_json():
    """局部修正：编辑 JSON（删圈）→ 重新生成 → rows/rounds 保持同步。"""
    at = AppTest.from_file(_APP, default_timeout=30)
    at.run()
    at.button(key="btn_manual").click().run()
    assert not at.exception

    rid = at.session_state["manual_result"]["result_id"]
    params = at.session_state["manual_result"]["params"]
    edited = {
        **{k: v for k, v in params.items() if k != "parts"},
        # 残留一个过期的 rows=999，头部删到只剩前 3 圈
        "parts": [{**p.model_dump(), "rows": 999} for p in params["parts"]],
    }
    edited["parts"][0]["rounds"] = edited["parts"][0]["rounds"][:3]

    import json as _json
    at.text_area(key=f"json_edit_{rid}").set_value(
        _json.dumps(edited, ensure_ascii=False, default=str)
    ).run()
    at.button(key=f"regen_{rid}").click().run()
    assert not at.exception

    head = [p for p in at.session_state["manual_result"]["params"]["parts"]
            if p.name == "头部"][0]
    assert len(head.rounds) == 3
    assert head.rows == 3  # 过期的 rows=999 不得复活
    # A5 回归：成功提示通过 session 标志在 rerun 后真实可见
    assert any("已根据修正" in str(s.value) for s in at.success)
    # C2 回归：派生量已按编辑后的圈数重算（3 圈 → 时长为下限 30 分钟）
    assert at.session_state["manual_result"]["params"]["estimated_time_minutes"] <= 30 + 2.5 * (
        sum(len(p.rounds) for p in at.session_state["manual_result"]["params"]["parts"]) - 3
    )


def test_grid_view_renders_from_stored_strings():
    """网格 Tab：从预渲染的字符串视图渲染，不依赖 GridPattern 对象。"""
    at = AppTest.from_file(_APP, default_timeout=30)
    at.session_state["grid_view"] = {
        "width": 4, "height": 3, "n_colors": 2,
        "svg": "<svg xmlns='http://www.w3.org/2000/svg'></svg>",
        "legend": "| 符号 | 颜色名称 |\n|:--:|:--:|\n| ■ | 红色 |",
        "legend_html": "<div>legend</div>",
        "chart": "R03: ■■■■",
        "c2c": "C2C 逐行指令",
    }
    at.run()
    assert not at.exception
    assert any("4 列 × 3 行" in str(s.value) for s in at.success)


def test_grid_single_cell_edit_survives_rerun_and_updates_payload():
    """网格修色按钩织行坐标写回轻量载荷，显式操作后才重新渲染。"""
    from app.models.grid_pattern import GridCell, GridPattern
    from app.ui.tab_grid import _rendered_grid_view

    palette = [("红色", (255, 0, 0)), ("蓝色", (0, 120, 215))]
    pattern = GridPattern(
        width=2,
        height=2,
        cells=[
            [GridCell(0, *palette[0]), GridCell(0, *palette[0])],
            [GridCell(0, *palette[0]), GridCell(1, *palette[1])],
        ],
        palette=palette,
        symbol_map={0: "■", 1: "▲"},
    )
    at = AppTest.from_file(_APP, default_timeout=30)
    at.session_state["grid_view"] = _rendered_grid_view(pattern)
    at.run()
    at.selectbox(key="grid_edit_color_1_1").set_value("蓝色").run()
    at.button(key="grid_apply_cell").click().run()
    assert not at.exception
    # R1 是成品底行，对应图像坐标最后一行；C1 是第一列。
    assert at.session_state["grid_view"]["pattern_payload"]["cells"][1][0] == 1
    assert any("网格修色" in str(item.value) for item in at.success)

    at.button(key="grid_undo").click().run()
    assert not at.exception
    assert at.session_state["grid_view"]["pattern_payload"]["cells"][1][0] == 0

    at.button(key="grid_redo").click().run()
    assert not at.exception
    assert at.session_state["grid_view"]["pattern_payload"]["cells"][1][0] == 1


def test_grid_edit_history_keeps_only_lightweight_recent_payloads():
    from app.ui.tab_grid import _GRID_HISTORY_LIMIT, _bounded_history_append

    history = []
    for index in range(_GRID_HISTORY_LIMIT + 3):
        _bounded_history_append(history, {"cells": [[index]]})
    assert len(history) == _GRID_HISTORY_LIMIT
    assert history[0]["cells"] == [[3]]
    assert all("svg" not in payload for payload in history)


def test_grid_rectangle_edit_converts_bottom_up_rows_correctly():
    from app.models.grid_pattern import GridCell, GridPattern
    from app.ui.tab_grid import _rendered_grid_view

    palette = [("红色", (255, 0, 0)), ("蓝色", (0, 120, 215))]
    pattern = GridPattern(
        width=2,
        height=2,
        cells=[
            [GridCell(0, *palette[0]), GridCell(0, *palette[0])],
            [GridCell(0, *palette[0]), GridCell(1, *palette[1])],
        ],
        palette=palette,
        symbol_map={0: "■", 1: "▲"},
    )
    at = AppTest.from_file(_APP, default_timeout=30)
    at.session_state["grid_view"] = _rendered_grid_view(pattern)
    at.run()
    at.radio(key="grid_edit_mode").set_value("矩形").run()
    at.number_input(key="grid_region_row_start").set_value(2).run()
    at.number_input(key="grid_region_row_end").set_value(2).run()
    at.number_input(key="grid_region_col_end").set_value(2).run()
    at.selectbox(key="grid_region_color_2_2_1_2").set_value("蓝色").run()
    at.button(key="grid_apply_cell").click().run()
    assert not at.exception
    payload = at.session_state["grid_view"]["pattern_payload"]
    # R2 是成品顶行，对应图像载荷第 0 行；底行保持原样。
    assert payload["cells"] == [[1, 1], [0, 1]]


def test_editable_grid_view_exposes_project_download():
    from app.models.grid_pattern import GridCell, GridPattern, import_grid_project
    from app.ui.tab_grid import _rendered_grid_view

    pattern = GridPattern(
        width=1, height=1,
        cells=[[GridCell(0, "红色", (255, 0, 0))]],
        palette=[("红色", (255, 0, 0))], symbol_map={0: "■"},
    )
    view = _rendered_grid_view(pattern)
    restored = import_grid_project(view["project_json"])
    assert restored.cells[0][0].color_name == "红色"

    at = AppTest.from_file(_APP, default_timeout=30)
    at.session_state["grid_view"] = view
    at.run()
    assert not at.exception
    assert any("可编辑工程" in str(button.label)
               for button in at.get("download_button"))


def test_sidebar_key_can_be_cleared():
    """侧栏清空 Key 后 session_state 必须同步清空（回归：旧实现残留旧值）。"""
    at = AppTest.from_file(_APP, default_timeout=30)
    at.run()
    at.text_input(key="openai_key_input").set_value("sk-old").run()
    assert at.session_state["openai_key"] == "sk-old"
    at.text_input(key="openai_key_input").set_value("").run()
    assert at.session_state["openai_key"] == ""


def test_nokey_mode_radio_renders(monkeypatch):
    """无 Key（输入框与 .env 都没有）时照片 Tab 应出现"本地视觉估算 / Mock"模式选择。"""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    at = AppTest.from_file(_APP, default_timeout=30)
    at.run()
    assert not at.exception
    radio = at.radio(key="vision_mode")
    assert radio is not None
    assert radio.value.startswith("🧮")
    assert any("Mock" in o for o in radio.options)


def test_env_keys_default_to_ai_and_hide_mock(monkeypatch):
    """.env（环境变量）有 Key 而输入框为空时：默认 AI 解析、不提供 Mock。

    回归（N1）：旧版只看输入框判定"无 Key"，.env 用户选"Mock 演示数据"
    时空串 key 回退 env → 实际发起真实计费调用，选项与行为完全脱节。
    """
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-only")
    at = AppTest.from_file(_APP, default_timeout=30)
    at.run()
    assert not at.exception
    radio = at.radio(key="vision_mode")
    assert radio is not None
    assert radio.value.startswith("🤖")          # 默认 AI
    assert not any("Mock" in o for o in radio.options)  # Mock 只在真正无 Key 时提供
    assert any("本地" in o for o in radio.options)      # 免费的本地模式仍可选


def test_env_keys_offer_local_mode_for_free(monkeypatch):
    """配了 Key 的用户仍可显式选择本地视觉估算（免费路径不被 Key 绑架）。"""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-only")
    at = AppTest.from_file(_APP, default_timeout=30)
    at.run()
    radio = at.radio(key="vision_mode")
    at.radio(key="vision_mode").set_value("🧮 本地视觉估算（免费）").run()
    assert not at.exception
    assert radio.value.startswith("🧮")


def test_vision_mode_resets_when_keys_appear(monkeypatch):
    """无 Key 时选了 Mock，随后配了 Key → radio 确定性回到 AI 默认且不异常。"""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    at = AppTest.from_file(_APP, default_timeout=30)
    at.run()
    at.radio(key="vision_mode").set_value("🎬 Mock 演示数据").run()
    assert at.radio(key="vision_mode").value.startswith("🎬")

    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-only")
    at.run()  # options 已切换（残留的 Mock 不在新 options 中）
    assert not at.exception
    assert at.radio(key="vision_mode").value.startswith("🤖")


def test_local_vision_result_renders_with_meta():
    """本地估算结果带 vision_meta 时渲染来源提示且不异常。"""
    from PIL import Image as _PILImage

    from app.models.local_vision import DEFAULT_HEAD_CM
    from app.models.orchestrator import PipelineOrchestrator

    orch = PipelineOrchestrator()
    # 不 monkeypatch：纯色图无脸 → default 源，逻辑路径相同
    result = orch.run_full_pipeline(_PILImage.new("RGB", (60, 60), (245, 194, 158)),
                                    local_vision=True)
    result["result_id"] = "local-1"
    at = AppTest.from_file(_APP, default_timeout=30)
    at.session_state["result"] = result
    at.run()
    assert not at.exception
    assert result["analysis"]["head_diameter_cm"] == DEFAULT_HEAD_CM
    assert result["vision_meta"]["source"] in ("default", "opencv-face")


def test_stored_result_with_duplicate_parts_renders():
    """历史坏结果/JSON 编辑复制部件导致的重名部件不得使页面崩溃（回归 B2）。"""
    at = AppTest.from_file(_APP, default_timeout=30)
    result = _mock_result("dup-parts-1")
    result["params"]["parts"] = list(result["params"]["parts"]) + [
        result["params"]["parts"][0]  # 复制头部 → 重名
    ]
    at.session_state["result"] = result
    at.run()
    assert not at.exception


def test_broken_materials_render_without_crash():
    """JSON 编辑器改坏 materials（纯字符串/缺字段）后渲染不崩溃（回归 B3）。"""
    at = AppTest.from_file(_APP, default_timeout=30)
    at.run()
    at.button(key="btn_manual").click().run()
    params = at.session_state["manual_result"]["params"]
    params["materials"] = ["毛线甲", {"item": "毛线乙"}]  # 字符串 + 缺 quantity
    at.run()  # 触发 rerun 渲染
    assert not at.exception


def test_regenerating_purges_old_widget_state():
    """二次生成时旧 result_id 命名空间的勾选状态必须被清理（此前 0 覆盖）。"""
    at = AppTest.from_file(_APP, default_timeout=30)
    at.run()
    at.button(key="btn_manual").click().run()
    rid1 = at.session_state["manual_result"]["result_id"]
    at.checkbox(key=f"chk_{rid1}_头部_0").check().run()
    assert at.session_state[f"chk_{rid1}_头部_0"]  # 勾选状态已写入

    at.button(key="btn_manual").click().run()  # 二次生成
    rid2 = at.session_state["manual_result"]["result_id"]
    assert rid2 != rid1
    # AppTest 的 session_state 不支持 keys() 枚举，用成员检查验证清理
    assert f"chk_{rid1}_头部_0" not in at.session_state
    assert f"json_edit_{rid1}" not in at.session_state
    assert f"regen_{rid1}" not in at.session_state


def test_recommended_colors_are_html_escaped():
    """推荐色板含 HTML 时必须转义后再进 unsafe_allow_html（注入防御回归）。"""
    at = AppTest.from_file(_APP, default_timeout=30)
    result = _mock_result("esc-1")
    result["analysis"]["recommended_colors"] = ['<img src=x onerror=alert(1)>红色']
    at.session_state["result"] = result
    at.run()
    assert not at.exception
    md_values = [str(m.value) for m in at.markdown]
    assert any("&lt;img" in v for v in md_values), "未找到转义后的色板渲染"
    assert not any("<img src=x" in v for v in md_values), "原始 HTML 泄漏进渲染"


def test_stale_checkbox_state_removed_after_rounds_shrink():
    """圈数删减后，超出新圈数的旧勾选状态在渲染时清理（防进度"复活"）。"""
    at = AppTest.from_file(_APP, default_timeout=30)
    at.run()
    at.button(key="btn_manual").click().run()
    rid = at.session_state["manual_result"]["result_id"]
    at.session_state[f"chk_{rid}_头部_50"] = True  # 头部只有 ~17 圈
    at.run()
    assert f"chk_{rid}_头部_50" not in at.session_state
    assert not at.exception


def test_backup_import_restores_result():
    """备份 JSON 粘贴导入 → 重建为新结果（跨会话持久化路径）。"""
    import json as _json

    at = AppTest.from_file(_APP, default_timeout=30)
    at.run()
    at.button(key="btn_manual").click().run()
    src = at.session_state["manual_result"]
    rid1 = src["result_id"]
    # 构造备份（模拟从下载的备份文件粘贴回来）
    backup = _json.dumps({
        "analysis": src["analysis"],
        "structure": src["structure"],
        "params": {**{k: v for k, v in src["params"].items() if k != "parts"},
                   "parts": [p.model_dump() for p in src["params"]["parts"]]},
    }, ensure_ascii=False)

    at2 = AppTest.from_file(_APP, default_timeout=30)  # 全新会话（无历史状态）
    at2.run()
    rid_seed = "seed-x"
    at2.session_state["manual_result"] = _mock_result(rid_seed)
    at2.run()
    at2.text_area(key=f"import_{rid_seed}").set_value(backup).run()
    at2.button(key=f"importbtn_{rid_seed}").click().run()
    assert not at.exception

    restored = at2.session_state["manual_result"]
    assert restored["result_id"] not in (rid_seed, rid1)
    assert [p.name for p in restored["params"]["parts"]] == ["头部", "身体"]
    assert restored["params"]["estimated_time_minutes"] > 0
    # 旧 seed 的 widget 状态已被清理
    assert f"import_{rid_seed}" not in at2.session_state


def test_backup_import_rejects_malformed_backup():
    """备份的 analysis/structure 无效时必须在导入处报错（N5）。

    回归：旧版只重建 params，analysis/structure 原样入库——坏备份要到
    下一次 rerun 的渲染层才崩（import 的 try 管不到），表现为异常页。
    """
    import json as _json

    at = AppTest.from_file(_APP, default_timeout=30)
    at.run()
    at.button(key="btn_manual").click().run()
    rid = at.session_state["manual_result"]["result_id"]
    src = at.session_state["manual_result"]

    # structure 整个是错的（list 而非 dict）——analysis 用合法值以隔离分支
    bad = _json.dumps({
        "analysis": src["analysis"],
        "structure": ["头部", "身体"],
        "params": {**{k: v for k, v in src["params"].items() if k != "parts"},
                   "parts": [p.model_dump() for p in src["params"]["parts"]]},
    }, ensure_ascii=False)
    at.text_area(key=f"import_{rid}").set_value(bad).run()
    at.button(key=f"importbtn_{rid}").click().run()
    assert not at.exception
    assert any("导入失败" in str(e.value) for e in at.error)
    assert at.session_state["manual_result"]["result_id"] == rid  # 未被替换

    # analysis 缺必填字段（pydantic 校验失败）同样在导入处拦截
    bad2 = _json.dumps({"analysis": {"body_type": "标准"},
                        "structure": src["structure"], "params": {}})
    at.text_area(key=f"import_{rid}").set_value(bad2).run()
    at.button(key=f"importbtn_{rid}").click().run()
    assert not at.exception
    assert any("导入失败" in str(e.value) for e in at.error)


def test_mock_result_shows_watermark():
    """Mock 来源的结果渲染时必须带演示数据标记（fable5 F9）。"""
    at = AppTest.from_file(_APP, default_timeout=30)
    result = _mock_result("mock-1")
    result["vision_meta"] = {"source": "mock", "note": "Mock 演示数据，与照片内容无关"}
    at.session_state["result"] = result
    at.run()
    assert not at.exception
    assert any("Mock 演示数据" in str(c.value) for c in at.caption)


# ── 前端深优化（F1/F2/F3）回归 ────────────────────────────────────────────

def test_recommended_colors_show_yarn_swatch():
    """推荐色板胶囊带真实毛线色样（F1）：红色 → #ff0000 色点。"""
    at = AppTest.from_file(_APP, default_timeout=30)
    result = _mock_result("chip-1")
    result["analysis"]["recommended_colors"] = ["红色"]
    at.session_state["result"] = result
    at.run()
    assert not at.exception
    md_values = [str(m.value) for m in at.markdown]
    chip_md = [v for v in md_values if "ff0000" in v]
    assert chip_md, "未找到带真实色样的胶囊"


def test_structure_section_renders_readable_table():
    """结构区渲染可读表格（F2）：dataframe + 名称列，而非裸 JSON。"""
    at = AppTest.from_file(_APP, default_timeout=30)
    at.session_state["result"] = _mock_result("tbl-1")
    at.run()
    assert not at.exception
    assert len(at.dataframe) >= 1


def test_structure_json_edit_regenerates_locally():
    """结构尺寸修正应通过 v2 校验并重算针法，不调用照片识别。"""
    import json as _json

    at = AppTest.from_file(_APP, default_timeout=30)
    at.session_state["result"] = _mock_result("structure-edit-1")
    at.run()
    assert not at.exception

    result = at.session_state["result"]
    old_arm = next(part for part in result["params"]["parts"]
                   if part.name == "手臂")
    old_height = old_arm.height_cm
    edited = _json.loads(_json.dumps(result["structure"], ensure_ascii=False))
    arm_structure = next(part for part in edited["parts"]
                         if part["name"] == "手臂")
    arm_structure["length_cm"] = 8.0

    at.text_area(key="struct_edit_structure-edit-1").set_value(
        _json.dumps(edited, ensure_ascii=False)).run()
    at.button(key="struct_go_structure-edit-1").click().run()
    assert not at.exception

    regenerated = at.session_state["result"]
    assert regenerated["result_id"] != "structure-edit-1"
    new_arm = next(part for part in regenerated["params"]["parts"]
                   if part.name == "手臂")
    assert new_arm.height_cm > old_height
    assert new_arm.quantity == 2
    assert any("修正后的部件结构" in str(item.value) for item in at.success)


def test_structure_json_edit_rejects_count_instance_mismatch():
    """修改 count 却不补 instances 时留在当前结果，并显示可理解错误。"""
    import json as _json

    at = AppTest.from_file(_APP, default_timeout=30)
    at.session_state["result"] = _mock_result("structure-edit-bad")
    at.run()
    edited = _json.loads(_json.dumps(
        at.session_state["result"]["structure"], ensure_ascii=False))
    arms = next(part for part in edited["parts"] if part["name"] == "手臂")
    arms["count"] = 1

    at.text_area(key="struct_edit_structure-edit-bad").set_value(
        _json.dumps(edited, ensure_ascii=False)).run()
    at.button(key="struct_go_structure-edit-bad").click().run()
    assert not at.exception
    assert at.session_state["result"]["result_id"] == "structure-edit-bad"
    assert any("结构校验或重生成失败" in str(item.value) for item in at.error)


def test_quick_size_regen_without_ai():
    """快速调整尺寸（F3）：改头径/身高 → 不调 AI 重生成，style/色带保持。

    手动 Tab 无照片（color_bands=None）→ 重生成仍为 None；塑形选项
    原样透传；result_id 换新（旧 widget 状态不串档）。
    """
    at = AppTest.from_file(_APP, default_timeout=30)
    at.run()
    at.button(key="btn_manual").click().run()
    rid = at.session_state["manual_result"]["result_id"]
    old_style = dict(at.session_state["manual_result"]["style"])
    old_geometry = dict(at.session_state["manual_result"]["geometry"])

    at.slider(key=f"sz_head_{rid}").set_value(12.0).run()
    at.slider(key=f"sz_height_{rid}").set_value(24.0).run()
    at.button(key=f"sz_go_{rid}").click().run()
    assert not at.exception

    new_result = at.session_state["manual_result"]
    assert new_result["result_id"] != rid
    assert new_result["analysis"]["head_diameter_cm"] == 12.0
    assert new_result["analysis"]["height_cm"] == 24.0
    assert [p.name for p in new_result["params"]["parts"]] == ["头部", "身体"]
    assert new_result["style"] == old_style           # 塑形选项透传
    assert new_result["color_bands"] is None          # 无照片路径
    assert new_result["sizing"]["source"] == "user_resize"
    assert new_result["geometry"] == old_geometry
    # 头部实际变大：最大针数应高于 9cm 头的 36 针
    head = [p for p in new_result["params"]["parts"] if p.name == "头部"][0]
    assert max(r.stitches for r in head.rounds) > 36
    # 成功提示可见
    assert any("新尺寸" in str(s.value) for s in at.success)


def test_photo_result_carries_style_and_bands():
    """照片路径 result 携带 style 与照片色带（F3 前提，本地视觉模式）。"""
    from PIL import Image as _PILImage

    from app.models.orchestrator import PipelineOrchestrator

    orch = PipelineOrchestrator()
    result = orch.run_full_pipeline(
        _PILImage.new("RGB", (60, 60), (245, 194, 158)), local_vision=True)
    assert result["style"]["sphere_mode"] in ("ladder", "ideal", "egg")
    assert result["style"]["skirt_style"] in ("ring", "attached")
    assert result["color_bands"] is None or isinstance(result["color_bands"], list)
