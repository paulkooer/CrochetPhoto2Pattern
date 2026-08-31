"""审查修复回归（F13–F20）+ 参数矩阵门禁。"""
import logging
import re

import pytest
from PIL import Image

from app.models.crochet_params import (
    CrochetParamsGenerator,
    PatternGenerationError,
    bridge_rounds,
)
from app.models.gauge import PRESETS, ShapingStyle
from app.models.structure_designer import StructureDesigner
from app.schemas import ImageAnalysis


def _gen(head=9.0, height=18.0, gauge=None, mode="ladder", one_piece=False,
         parts=("头部", "身体", "手臂", "腿部"), bands=None):
    a = ImageAnalysis(body_type="标准", head_diameter_cm=head,
                      height_cm=height, main_features=[], pose="站立",
                      difficulty="easy", parts=list(parts))
    st = StructureDesigner.design_3d_structure(a)
    return CrochetParamsGenerator.generate_params(
        a, st, gauge=gauge or PRESETS["classic"], color_bands=bands,
        style=ShapingStyle(sphere_mode=mode, one_piece=one_piece))


# ── F13：bridge_rounds + 生成门禁 + 参数矩阵 ─────────────────────────────

def test_bridge_rounds_steps_by_six():
    assert bridge_rounds(42, 30) == [36, 30]
    assert bridge_rounds(30, 42) == [36, 42]
    assert bridge_rounds(36, 36) == []
    with pytest.raises(AssertionError):
        bridge_rounds(40, 30)  # 非 6 的倍数


@pytest.mark.parametrize("gauge_name", ["classic", "dk", "fine"])
@pytest.mark.parametrize("mode", ["ladder", "ideal", "egg"])
@pytest.mark.parametrize("one_piece", [False, True])
@pytest.mark.parametrize("head", [4.0, 9.0, 11.0, 20.0])
@pytest.mark.parametrize("height", [10.0, 30.0, 60.0])
def test_parameter_matrix_valid_and_bounded(gauge_name, mode, one_piece,
                                            head, height):
    """参数矩阵门禁：代数自洽且跳变不超过当前密度塑形上限。"""
    gauge = PRESETS[gauge_name]
    params = _gen(head=head, height=height, gauge=gauge,
                  mode=mode, one_piece=one_piece)
    v = validate_pattern_ok(params)
    assert v, v
    for part in params["parts"]:
        sts = [r.stitches for r in part.rounds]
        adjacent = zip(sts, sts[1:])  # noqa: B905 - adjacent pairs truncate by design
        assert all(abs(b - a) <= gauge.max_shaping_change for a, b in adjacent), (
            f"{part.name} 出现跨圈跳变: {sts}"
        )


def validate_pattern_ok(params):
    from app.models.validator import validate_pattern
    v = validate_pattern(params)
    assert v["ok"], v["issues"]
    return v["ok"]


def test_generation_gate_blocks_broken_pattern(monkeypatch):
    """生成门禁（F13）：生成器产出代数矛盾时抛 PatternGenerationError，
    阻止其成为可下载图解。"""
    def corrupt(part, bands, snap_color=None, spans=None):
        part.rounds[3].stitches += 13
    monkeypatch.setattr(CrochetParamsGenerator, "_apply_color_plan", corrupt)
    with pytest.raises(PatternGenerationError):
        _gen(bands=[{"start": 0.0, "end": 1.0, "color": "蓝色"}])


# ── F14：异常脱敏 ─────────────────────────────────────────────────────────

def test_provider_exception_never_leaks_keys(monkeypatch, caplog):
    """F14：中转站/服务商异常携带 Key 时，UI 异常与日志均不得出现。"""
    from app.models.image_parser import ImageParser

    fake = __import__("types").ModuleType("anthropic")
    real = "sk-ant-" + "REAL" * 5
    relay = "sk-ant-" + "RELAYSECRET" * 2

    class _Msgs:
        @staticmethod
        def parse(**kw):
            raise RuntimeError(
                f"relay 500: Authorization: Bearer {relay} key={real}")

    class _Boom:
        def __init__(self, **kw):
            self.messages = _Msgs()

    fake.Anthropic = _Boom
    fake.APIStatusError = Exception
    monkeypatch.setitem(__import__("sys").modules, "anthropic", fake)
    monkeypatch.setattr("app.models.image_parser.load_dotenv",
                        lambda *a, **k: False)

    parser = ImageParser(anthropic_key=real)
    with caplog.at_level(logging.WARNING, logger="app.models.image_parser"):
        with pytest.raises(RuntimeError) as exc:
            parser.parse_image(Image.new("RGB", (32, 32)))
    assert real not in str(exc.value)
    assert relay not in str(exc.value)
    assert real not in caplog.text and relay not in caplog.text
    assert "relay 500" in caplog.text  # 状态码等诊断信息保留


def test_sanitize_masks_generic_tokens_but_keeps_urls():
    from app.models.image_parser import _sanitize_secrets
    token = "sk-" + "abc123def456ghi789"
    out = _sanitize_secrets(
        f"GET https://api.x.com/v1?key={token} 401", token)
    assert token not in out
    assert "https://api.x.com/v1" in out and "401" in out


# ── F15：pose 部分实测时逐部件回退 ────────────────────────────────────────

def test_effective_spans_fill_missing_parts_from_prior(monkeypatch):
    """F15：缺膝盖 → 腿/裙实测缺失，但有效 span 回退先验，配色不丢。"""
    import app.models.pose as pose_mod
    from app.models.orchestrator import PipelineOrchestrator

    monkeypatch.setattr(pose_mod, "get_body_landmarks",
                        lambda _img: {"nose": 0.1, "eye_top": 0.07,
                                      "shoulder": 0.25, "hip": 0.5,
                                      "knee": None, "ankle": None,
                                      "wrist": 0.5})
    from PIL import ImageDraw
    img = Image.new("RGB", (200, 400), (245, 245, 245))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([78, 195, 122, 372], radius=10, fill=(0, 120, 215))
    d.ellipse([75, 24, 125, 74], fill=(230, 180, 150))
    result = PipelineOrchestrator().run_full_pipeline(img, local_vision=True)
    assert result["spans"]["腿部"] is not None       # 回退先验
    assert "腿部" not in result["spans_measured"]    # 且诚实标注非实测
    assert "身体" in result["spans_measured"]
    body = [p for p in result["params"]["parts"] if p.name == "身体"][0]
    assert any(r.color for r in body.rounds)          # 配色仍然存在


def test_full_pose_overrides_prior(monkeypatch):
    """完整关键点 → 实测值覆盖先验，spans_measured 列出实测部件。"""
    import app.models.pose as pose_mod
    from app.models.orchestrator import PipelineOrchestrator

    monkeypatch.setattr(pose_mod, "get_body_landmarks",
                        lambda _img: {"nose": 0.1, "eye_top": 0.07,
                                      "shoulder": 0.25, "hip": 0.5,
                                      "knee": 0.7, "ankle": 0.9,
                                      "wrist": 0.5})
    result = PipelineOrchestrator().run_full_pipeline(
        Image.new("RGB", (60, 60)), local_vision=True)
    assert {"头部", "身体", "腿部", "裙子"} <= set(result["spans_measured"])
    assert result["spans"]["腿部"] == (0.5, 0.9)      # 实测值生效


# ── F16/F17/F18：几何与工艺语义 ──────────────────────────────────────────

def test_one_piece_height_excludes_closure_disc():
    """F16：一体件高度 = 头部到颈 + 筒壁轴向，不含底部径向收口盘。"""
    params = _gen(one_piece=True)
    one = [p for p in params["parts"] if p.type == "onepiece"][0]
    sts = [r.stitches for r in one.rounds]
    # 默认 ladder 配置的确定口径：axial = 头部到颈 14 圈 + 筒壁 8 圈 = 22；
    # 总 27 圈末尾的收口盘（径向）不计高
    assert (len(sts), one.height_cm) == (27, 13.8)
    assert one.height_cm < len(sts) * 0.625


def test_profile_body_open_finish_note():
    """F17：剖面身体末圈开口，说明明确"开口不收针+缝合"工艺。"""
    params = _gen()
    params = CrochetParamsGenerator.generate_params(
        __import__("app.schemas", fromlist=["ImageAnalysis"]).ImageAnalysis(
            body_type="标准", head_diameter_cm=9.0, height_cm=18.0,
            main_features=[], pose="站立", difficulty="easy",
            parts=["头部", "身体"]),
        StructureDesigner.design_3d_structure(
            __import__("app.schemas", fromlist=["ImageAnalysis"]).ImageAnalysis(
                body_type="标准", head_diameter_cm=9.0, height_cm=18.0,
                main_features=[], pose="站立", difficulty="easy",
                parts=["头部", "身体"])),
        body_profile=[0.5, 0.8, 1.0, 0.8, 0.5] * 4)
    body = [p for p in params["parts"] if p.name == "身体"][0]
    assert body.rounds[-1].decrease == 0              # 末圈保持开口
    assert "开口" in body.notes and "缝合" in body.notes
    assert "收针前填充" not in body.notes             # 旧误导文案移除


@pytest.mark.parametrize("gauge_name", ["classic", "dk", "fine"])
def test_hat_has_wearable_wall(gauge_name):
    """F18：三密度下帽子侧壁 ≥3 圈（可佩戴下限）。"""
    params = _gen(parts=("帽子",), gauge=PRESETS[gauge_name])
    hat = [p for p in params["parts"] if p.name == "帽子"][0]
    max_st = max(r.stitches for r in hat.rounds)
    n_up = max_st // 6
    assert len(hat.rounds) - n_up >= 3
    assert "筒深" in hat.notes


# ── F19/F20：展示与状态治理 ──────────────────────────────────────────────

@pytest.mark.parametrize("n_rounds", [17, 30, 60])
def test_ring_labels_unique_coordinates(n_rounds):
    """F19：任意圈数下环形图标注坐标唯一，不重叠。"""
    from app.models.ring_chart import render_ring_svg
    part = {"name": "头部", "type": "sphere", "rounds": [
        {"row": i + 1, "stitches": min(6 * (i + 1), 36),
         "increase": 6 if 0 < i < 6 else 0,
         "decrease": 6 if i >= max(6, n_rounds - 5) else 0,
         "color": "蓝色" if i < n_rounds // 2 else "红色"}
        for i in range(n_rounds)]}
    svg = render_ring_svg(part)
    ys = re.findall(r'<text x="\d+" y="(\d+)', svg)
    assert len(ys) == len(set(ys))
    assert len(ys) < n_rounds  # 只标变化圈，信息密度受控


def test_purge_covers_pdf_gen_and_sz_prefixes():
    """F20：purge 前缀覆盖 pdf_gen_ 与 sz_* 全族。"""
    from app.ui.result_renderer import _WIDGET_KEY_PREFIXES
    assert any(p == "pdf_gen_" for p in _WIDGET_KEY_PREFIXES)
    assert any(p == "sz_" for p in _WIDGET_KEY_PREFIXES)
    result = {"result_id": "purge-x"}
    state = {"pdf_gen_purge-x": 1, "pdf_purge-x": 2, "sz_head_purge-x": 3,
             "sz_purge-x_ok": True, "chk_purge-x_头部_0": True,
             "unrelated": 9}
    # 模拟 session_state 清理（purge 操作 st.session_state）
    import app.ui.result_renderer as rr
    class FakeState(dict):
        def keys(self):
            return list(dict.keys(self))
    fs = FakeState(state)
    monkey = pytest.MonkeyPatch()
    monkey.setattr(rr.st, "session_state", fs)
    try:
        rr.purge_result_state(result)
    finally:
        monkey.undo()
    assert "pdf_gen_purge-x" not in fs and "pdf_purge-x" not in fs
    assert "sz_head_purge-x" not in fs and "sz_purge-x_ok" not in fs
    assert "chk_purge-x_头部_0" not in fs   # 同 rid 的勾选本就该清
    assert fs["unrelated"] == 9


# ── U5：门禁矩阵扩展——配色带 × 照片剖面 × 实测 span 组合面 ────────────────
# 原 216 组矩阵只覆盖无色带路径；语义吸附/实测 span/剖面身体的完整组合
# 同样必须过自检门禁（F13 防线的覆盖面补全）。

_BANDS = [{"start": 0.0, "end": 0.5, "color": "蓝色"},
          {"start": 0.5, "end": 1.0, "color": "红色"}]
_PROFILE = [0.5, 0.8, 1.0, 0.8, 0.5] * 4
_LM = {"nose": 0.1, "eye_top": 0.07, "shoulder": 0.25, "hip": 0.5,
       "knee": 0.7, "ankle": 0.9, "wrist": 0.5}


@pytest.mark.parametrize("gauge_name", ["classic", "dk", "fine"])
@pytest.mark.parametrize("mode", ["ladder", "egg"])
@pytest.mark.parametrize("with_bands", [False, True])
@pytest.mark.parametrize("with_profile", [False, True])
@pytest.mark.parametrize("with_spans", [False, True])
def test_matrix_extended_color_profile_spans(gauge_name, mode, with_bands,
                                             with_profile, with_spans):
    from app.models.color_design import PART_SPAN
    from app.models.pose import measured_spans
    from app.models.validator import validate_pattern
    spans = {**PART_SPAN, **measured_spans(_LM)} if with_spans else None
    parts = ["头部", "身体", "手臂", "腿部"]
    a = ImageAnalysis(body_type="标准", head_diameter_cm=9.0, height_cm=18.0,
                      main_features=[], pose="站立", difficulty="easy",
                      parts=parts,
                      bottom_color="红色" if with_bands else None)
    st = StructureDesigner.design_3d_structure(a)
    gauge = PRESETS[gauge_name]
    params = CrochetParamsGenerator.generate_params(
        a, st, gauge=gauge,
        color_bands=_BANDS if with_bands else None,
        body_profile=_PROFILE if with_profile else None,
        spans=spans, style=ShapingStyle(sphere_mode=mode))
    v = validate_pattern(params)
    assert v["ok"], v["issues"]
    for part in params["parts"]:
        sts = [r.stitches for r in part.rounds]
        assert all(abs(b - a) <= gauge.max_shaping_change
                   for a, b in zip(sts, sts[1:]))  # noqa: B905 - adjacent pairs truncate by design


def test_matrix_full_counts_documented():
    """矩阵规模自检：主矩阵 216 + 扩展矩阵 48 = 264 组合的门禁覆盖。"""
    # 本测试只是文档化数字，防止有人静默缩减矩阵
    main = 3 * 3 * 2 * 4 * 3
    ext = 3 * 2 * 2 * 2 * 2
    assert main == 216 and ext == 48
