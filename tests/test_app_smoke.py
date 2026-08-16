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
    }


def test_app_boots_without_exception():
    """The script must run top-to-bottom with no uncaught exception."""
    at = AppTest.from_file(_APP, default_timeout=30)
    at.run()
    assert not at.exception


def test_both_tabs_with_results_render_together():
    """照片 Tab 与手动 Tab 的结果同屏渲染时不得发生 widget key 冲突。"""
    at = AppTest.from_file(_APP, default_timeout=30)
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
        "chart": "R03: ■■■■",
    }
    at.run()
    assert not at.exception
    assert any("4 列 × 3 行" in str(s.value) for s in at.success)


def test_sidebar_key_can_be_cleared():
    """侧栏清空 Key 后 session_state 必须同步清空（回归：旧实现残留旧值）。"""
    at = AppTest.from_file(_APP, default_timeout=30)
    at.run()
    at.text_input(key="openai_key_input").set_value("sk-old").run()
    assert at.session_state["openai_key"] == "sk-old"
    at.text_input(key="openai_key_input").set_value("").run()
    assert at.session_state["openai_key"] == ""


def test_nokey_mode_radio_renders():
    """无 Key 时照片 Tab 应出现"本地视觉估算 / Mock"模式选择。"""
    at = AppTest.from_file(_APP, default_timeout=30)
    at.run()
    assert not at.exception
    # 无 Key（测试环境无 .env）→ radio 存在且默认本地估算
    radio = at.radio(key="nokey_mode")
    assert radio is not None
    assert radio.value.startswith("🧮")


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


def test_mock_result_shows_watermark():
    """Mock 来源的结果渲染时必须带演示数据标记（fable5 F9）。"""
    at = AppTest.from_file(_APP, default_timeout=30)
    result = _mock_result("mock-1")
    result["vision_meta"] = {"source": "mock", "note": "Mock 演示数据，与照片内容无关"}
    at.session_state["result"] = result
    at.run()
    assert not at.exception
    assert any("Mock 演示数据" in str(c.value) for c in at.caption)
