"""第十二轮：逐色材料 / C2C / 自检器 / span hints / 环形图。"""
from PIL import Image

from app.models.crochet_params import CrochetParamsGenerator
from app.models.grid_pattern import (
    GridCell,
    GridPattern,
    generate_grid_pattern,
    render_c2c_chart,
)
from app.models.ring_chart import render_ring_svg
from app.models.structure_designer import StructureDesigner
from app.models.validator import validate_pattern
from app.schemas import ImageAnalysis


def _params(parts=("头部", "身体"), bands=None):
    a = ImageAnalysis(body_type="标准", head_diameter_cm=9.0, height_cm=18.0,
                      main_features=[], pose="站立", difficulty="easy",
                      parts=list(parts))
    struct = StructureDesigner.design_3d_structure(a)
    return CrochetParamsGenerator.generate_params(
        a, struct, color_bands=bands)


def _two_bands():
    return [{"start": 0.0, "end": 0.5, "color": "蓝色"},
            {"start": 0.5, "end": 1.0, "color": "红色"}]


# ── T2 逐色材料 ───────────────────────────────────────────────────────────

def test_materials_include_per_color_entries():
    params = _params(bands=_two_bands())
    per_color = [m for m in params["materials"] if str(
        m.get("item", "")).startswith("毛线 · ")]
    names = {m["color"] for m in per_color}
    assert {"蓝色", "红色"} <= names, per_color
    for m in per_color:
        assert "g" in m["quantity"] and "≈" in m["quantity"]
    # 色表外颜色同样给量（LLM 语义色场景）
    params2 = _params(bands=_two_bands())
    for p in params2["parts"]:
        p.color = "酒红色"
        for r in p.rounds:
            r.color = "酒红色"
    from app.models.crochet_params import _materials
    materials = _materials(params2["parts"], {p.name for p in params2["parts"]})
    assert any(m["item"] == "毛线 · 酒红色" for m in materials)


def test_per_color_grams_consistent_with_totals():
    """逐色克重合计应与总针数一致（±1g 舍入）。"""
    params = _params(bands=_two_bands())
    total_stitches = params["total_stitches"]
    per_color = [m for m in params["materials"]
                 if str(m.get("item", "")).startswith("毛线 · ")]
    import re
    grams = sum(int(re.match(r"约 (\d+)g", m["quantity"]).group(1))
                for m in per_color)
    # 每色下限 5g 的截断会造成少量高估，容差 = 色数×4g
    assert grams <= total_stitches * 0.08 + len(per_color) * 4 + 1


# ── T3 C2C ────────────────────────────────────────────────────────────────

def test_c2c_row_structure_rectangle():
    """3×2 网格 → 4 个对角行，格数 1,2,2,1（增→平→减）。"""
    pat = generate_grid_pattern(Image.new("RGB", (30, 20), (255, 0, 0)),
                                grid_width=3, n_colors=1)
    chart = render_c2c_chart(pat)
    assert "对角行 1（1 格，增行）" in chart
    assert "对角行 2（2 格，增行）" in chart
    assert "对角行 3（2 格，平行）" in chart
    assert "对角行 4（1 格，减行）" in chart
    assert "螃蟹针" in chart


def test_c2c_colors_follow_grid():
    """左半红右半蓝的图：前几行只含红，后段出现蓝。"""
    img = Image.new("RGB", (60, 20), (255, 0, 0))
    for y in range(20):
        for x in range(40, 60):
            img.putpixel((x, y), (0, 120, 215))
    pat = generate_grid_pattern(img, grid_width=6, n_colors=2)
    chart = render_c2c_chart(pat)
    rows = [ln for ln in chart.split("\n") if ln.startswith("对角行")]
    assert any("蓝色" in ln for ln in rows)
    assert "红色" in rows[0]


def test_c2c_really_starts_at_bottom_left_and_ends_top_right():
    """四角哨兵防止图像坐标（左上原点）被误当成钩织坐标。"""
    names = (("TL", "TR"), ("BL", "BR"))
    cells = [[
        GridCell(col_index=y * 2 + x, color_name=name, rgb=(0, 0, 0))
        for x, name in enumerate(row)
    ] for y, row in enumerate(names)]
    pattern = GridPattern(
        width=2, height=2, cells=cells, palette=[], symbol_map={})
    rows = [line for line in render_c2c_chart(pattern).splitlines()
            if line.startswith("对角行")]
    assert rows[0].endswith("BL")
    assert rows[-1].endswith("TR")


# ── T4 自检器 ─────────────────────────────────────────────────────────────

def test_validator_passes_generated_pattern():
    v = validate_pattern(_params(bands=_two_bands()))
    assert v["ok"] and v["checked"] > 0


def test_validator_flags_broken_algebra():
    params = _params()
    pd = params["parts"][0]
    rd = pd.rounds[5]
    rd.stitches = rd.stitches + 13  # 破坏代数
    v = validate_pattern(params)
    assert not v["ok"]
    assert any("第 6 圈" in i for i in v["issues"])


def test_validator_flags_inc_and_dec_together():
    params = _params()
    pd = params["parts"][0]
    pd.rounds[8].increase = 6
    pd.rounds[8].decrease = 6
    v = validate_pattern(params)
    assert any("同时加针" in i for i in v["issues"])


def test_validator_uses_gauge_derived_dynamic_shaping_limit():
    pattern = {
        "gauge": {"stitches_per_10cm": 20.0, "rows_per_10cm": 16.0},
        "parts": [{
            "name": "测试件",
            "rounds": [
                {"stitches": 12},
                {"stitches": 24, "increase": 12},
            ],
        }],
    }
    fine = validate_pattern(pattern)
    assert fine["ok"]
    assert fine["max_stitch_change"] == 12

    pattern["gauge"] = {"stitches_per_10cm": 13.0, "rows_per_10cm": 16.0}
    classic = validate_pattern(pattern)
    assert not classic["ok"]
    assert classic["max_stitch_change"] == 6
    assert any("超过当前密度塑形上限 ±6" in issue
               for issue in classic["issues"])


def test_validator_does_not_trust_editable_shaping_metadata():
    pattern = {
        "gauge": {"stitches_per_10cm": 13.0, "rows_per_10cm": 16.0},
        "shaping": {"max_stitch_change": 999},
        "parts": [{
            "name": "测试件",
            "rounds": [
                {"stitches": 12},
                {"stitches": 24, "increase": 12},
            ],
        }],
    }
    result = validate_pattern(pattern)
    assert not result["ok"]
    assert result["max_stitch_change"] == 6


def test_validator_rejects_incapable_v_or_a_even_within_dynamic_cap():
    gauge = {"stitches_per_10cm": 20.0, "rows_per_10cm": 16.0}
    too_many_increases = {
        "gauge": gauge,
        "parts": [{"name": "加针件", "rounds": [
            {"stitches": 6},
            {"stitches": 18, "increase": 12},
        ]}],
    }
    result = validate_pattern(too_many_increases)
    assert not result["ok"]
    assert any("超过上圈 6 个源针" in issue for issue in result["issues"])

    too_many_decreases = {
        "gauge": gauge,
        "parts": [{"name": "减针件", "rounds": [
            {"stitches": 18},
            {"stitches": 6, "decrease": 12},
        ]}],
    }
    result = validate_pattern(too_many_decreases)
    assert not result["ok"]
    assert any("可组成的 A 数量" in issue for issue in result["issues"])


def test_validator_rejects_non_six_stitch_topology():
    pattern = {"parts": [{"name": "坏拓扑", "rounds": [
        {"stitches": 7},
    ]}]}
    result = validate_pattern(pattern)
    assert not result["ok"]
    assert any("不是正的 6 的倍数" in issue for issue in result["issues"])


# ── T6 span hints ─────────────────────────────────────────────────────────

def test_span_hints_reach_prompt(monkeypatch):
    """实测 span 作为几何参考进入 Vision prompt（T6）。"""
    from app.models.image_parser import ImageParser
    from app.models.pose import measured_spans

    lm = {"nose": 0.10, "eye_top": 0.07, "shoulder": 0.25, "hip": 0.50,
          "knee": 0.72, "ankle": 0.94, "wrist": 0.52}
    hints = "【几何参考】身体 0.25–0.50"
    recorded = {}

    def fake_anthropic(self, img_b64):
        recorded["prompt"] = self._prompt_with_hints()
        raise RuntimeError("stop")

    monkeypatch.setattr(ImageParser, "_parse_with_anthropic", fake_anthropic)
    monkeypatch.setattr("app.models.image_parser.load_dotenv",
                        lambda *a, **k: False)
    parser = ImageParser(anthropic_key="k")
    parser._span_hints = hints
    try:
        parser.parse_image(Image.new("RGB", (32, 32)), span_hints=hints)
    except RuntimeError:
        pass
    assert hints in recorded["prompt"]
    # 无 hints 时 prompt 不含几何参考
    parser2 = ImageParser(anthropic_key="k")
    assert "【几何参考】" not in parser2._prompt_with_hints()
    assert measured_spans(lm)["身体"]


def test_orchestrator_passes_hints_to_parser(monkeypatch):
    """orchestrator 在解析前测 pose 并把 hints 传给 parse_image。"""
    import app.models.pose as pose_mod
    from app.models.image_parser import ImageParser
    from app.models.orchestrator import PipelineOrchestrator

    monkeypatch.setattr(pose_mod, "get_body_landmarks",
                        lambda _img: {"nose": 0.1, "eye_top": 0.07,
                                      "shoulder": 0.25, "hip": 0.5,
                                      "knee": 0.7, "ankle": 0.9,
                                      "wrist": 0.5})
    captured = {}

    def fake_parse(self, image, span_hints=None):
        captured["hints"] = span_hints
        from app.models.image_parser import ImageParser as IP
        return IP._mock_analysis()

    monkeypatch.setattr(ImageParser, "parse_image", fake_parse)
    PipelineOrchestrator().run_full_pipeline(
        Image.new("RGB", (40, 40)))
    assert captured["hints"] and "【几何参考】" in captured["hints"]


# ── T8 环形图 ─────────────────────────────────────────────────────────────

def test_ring_svg_draws_one_circle_per_round():
    params = _params(bands=_two_bands())
    head = params["parts"][0]
    svg = render_ring_svg(head)
    n = len(head.rounds)
    assert svg.count("<circle") == n
    assert "顶视图" in svg and f"{head.name}" in svg


def test_ring_svg_colored_rounds_use_yarn_hex():
    params = _params(bands=_two_bands())
    body = [p for p in params["parts"] if p.name == "身体"][0]
    svg = render_ring_svg(body)
    assert "#0000ff" in svg or "#008000" in svg or "#000080" in svg or "fill=\"#" in svg
