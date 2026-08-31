"""S5：合成真值评测基线——把"改代码没破坏识别质量"变成数字断言。

方法论（对齐 CrochetBench arXiv:2511.09483 的执行式评测思想）：
程序渲染已知参数的标准人形（头/上衣/下装颜色与几何完全受控），跑完整
本地管线，断言识别输出与真值的偏差 ≤ 容差。这是"质量回归"而非常规
单测——容忍小误差，锁定系统性漂移。
"""
import math

import pytest
from PIL import Image, ImageDraw

from app.models.pose import measured_spans

# 真值（与 _doll 渲染严格对应）
_HEAD_TOP, _HEAD_BOTTOM = 0.06, 0.20     # 头部纵向 span（全图 0..1）
_SHOULDER, _HIP = 0.25, 0.52
_KNEE, _ANKLE = 0.72, 0.93
_SHIRT_RGB = (0, 120, 215)               # 蓝
_SKIRT_RGB = (220, 50, 50)               # 红


def _doll(skirt=True, arms=True):
    """标准人形（400×200）：肤色头 + 蓝上衣 + 红裙/蓝腿。"""
    img = Image.new("RGB", (200, 400), (245, 245, 245))
    d = ImageDraw.Draw(img)
    d.ellipse([75, 24, 125, 74], fill=(230, 180, 150))            # 头 y24-74
    d.rounded_rectangle([80, 85, 120, 195], radius=10,
                        fill=_SHIRT_RGB)                          # 上衣 y85-195
    if skirt:
        d.polygon([(70, 195), (130, 195), (140, 240), (60, 240)],
                  fill=_SKIRT_RGB)                                # 裙 y195-240
        d.rounded_rectangle([78, 240, 122, 372], radius=10,
                            fill=_SHIRT_RGB)                      # 腿
    else:
        d.rounded_rectangle([78, 195, 122, 372], radius=10,
                            fill=_SHIRT_RGB)                      # 腿
    if arms:
        d.rounded_rectangle([60, 90, 72, 205], radius=6, fill=_SHIRT_RGB)
        d.rounded_rectangle([128, 90, 140, 205], radius=6, fill=_SHIRT_RGB)
    return img


def _pose_for_image():
    """与 _doll 几何一致的伪关键点（真值注入，测 pose→span 映射精度）。"""
    return {
        "nose": 0.115, "eye_top": 0.085,
        "shoulder": _SHOULDER, "hip": _HIP,
        "knee": _KNEE, "ankle": _ANKLE, "wrist": 0.52,
    }


def _full_image():
    img = Image.new("RGB", (200, 400), (245, 245, 245))
    d = ImageDraw.Draw(img)
    d.ellipse([75, 24, 125, 74], fill=(230, 180, 150))
    d.rounded_rectangle([80, 85, 120, 195], radius=10, fill=_SHIRT_RGB)
    d.polygon([(70, 195), (130, 195), (140, 240), (60, 240)], fill=_SKIRT_RGB)
    d.rounded_rectangle([78, 240, 122, 372], radius=10, fill=_SHIRT_RGB)
    d.rounded_rectangle([60, 90, 72, 205], radius=6, fill=_SHIRT_RGB)
    d.rounded_rectangle([128, 90, 140, 205], radius=6, fill=_SHIRT_RGB)
    return img


def test_eval_measured_spans_match_ground_truth():
    """评测 1：pose→span 映射与渲染真值偏差 ≤ 0.06（全图归一）。"""
    spans = measured_spans(_pose_for_image())
    assert spans["身体"][0] == pytest.approx(_SHOULDER, abs=0.06)
    assert spans["身体"][1] == pytest.approx(_HIP, abs=0.06)
    assert spans["腿部"][0] == pytest.approx(_HIP, abs=0.06)
    assert spans["腿部"][1] == pytest.approx(_ANKLE, abs=0.06)
    # 真值头部 y24-74 → 0.06-0.185
    assert spans["头部"][0] == pytest.approx(_HEAD_TOP, abs=0.06)
    assert spans["头部"][1] == pytest.approx(_HEAD_BOTTOM + 0.02, abs=0.08)


def test_eval_color_bands_identify_shirt_and_skirt():
    """评测 2：色带必须把蓝上衣/红裙分开（配色映射的输入质量）。"""
    from app.models.color_design import vertical_color_bands
    bands = vertical_color_bands(_full_image(), n_bands=10)
    assert bands, "色带提取失败"
    colors = [b["color"] for b in bands]
    # 裙色 (220,50,50) 是色表"暗红色"的精确锚点
    assert "蓝色" in colors, f"上衣色缺失: {colors}"
    skirt_colors = [c for c in colors if c in ("红色", "暗红色")]
    assert skirt_colors, f"裙色缺失: {colors}"
    assert colors.index("蓝色") < colors.index(skirt_colors[0])


def test_eval_skirt_detected_via_profile():
    """评测 3：下摆展开延伸到主体底部 → flare 检出（管线级质量回归）。

    注：flare 的适用前提是展开延到主体下缘（A 字裙型）；裙摆悬在
    人体中部的场景由 S1 的 pose span（髋→膝）覆盖，不依赖轮廓。
    """
    from PIL import ImageDraw

    import app.models.local_vision as lv

    # 干净的 A 字裙真值：裙摆自腰部展开直达主体底部（无人工空洞）
    img = Image.new("RGB", (200, 400), (245, 245, 245))
    d = ImageDraw.Draw(img)
    d.ellipse([75, 24, 125, 74], fill=(230, 180, 150))
    d.rounded_rectangle([80, 85, 120, 195], radius=10, fill=(0, 120, 215))
    d.polygon([(55, 195), (145, 195), (155, 372), (45, 372)],
              fill=(220, 50, 50))
    prof = lv._silhouette_profile(img)
    assert prof is not None
    assert lv._has_bottom_flare(prof), "裙摆展开未检出"


def test_eval_end_to_end_stability():
    """评测 4：同一输入两次跑管线，图解逐字节一致（确定性保证）。"""
    from app.models.crochet_params import CrochetParamsGenerator
    from app.models.gauge import DEFAULT
    from app.models.structure_designer import StructureDesigner
    from app.schemas import ImageAnalysis

    a = ImageAnalysis(body_type="标准", head_diameter_cm=9.0, height_cm=18.0,
                      main_features=[], pose="站立", difficulty="easy",
                      parts=["头部", "身体", "手臂", "腿部"])
    struct = StructureDesigner.design_3d_structure(a)
    p1 = CrochetParamsGenerator.generate_params(a, struct, gauge=DEFAULT)
    p2 = CrochetParamsGenerator.generate_params(a, struct, gauge=DEFAULT)
    dump1 = [(p.name, p.type, [(r.stitches, r.color) for r in p.rounds])
             for p in p1["parts"]]
    dump2 = [(p.name, p.type, [(r.stitches, r.color) for r in p.rounds])
             for p in p2["parts"]]
    assert dump1 == dump2


def test_eval_gauge_consistency():
    """评测 5：密度换算自洽——同一头径在任何密度下物理尺寸一致（±0.3cm）。"""
    from app.models.crochet_params import CrochetParamsGenerator
    from app.models.gauge import PRESETS
    from app.models.structure_designer import StructureDesigner
    from app.schemas import ImageAnalysis

    a = ImageAnalysis(body_type="标准", head_diameter_cm=9.0, height_cm=18.0,
                      main_features=[], pose="站立", difficulty="easy",
                      parts=["头部"])
    for name in ("classic", "dk", "fine"):
        g = PRESETS[name]
        params = CrochetParamsGenerator.generate_params(
            a, StructureDesigner.design_3d_structure(a), gauge=g)
        head = params["parts"][0]
        max_st = max(r.stitches for r in head.rounds)
        physical_d = max_st * g.stitch_w_cm / math.pi
        # 容差 = 6 的倍数量化的半步（领域惯例的固有精度下限）
        tol = 6 * g.stitch_w_cm / math.pi / 2 + 0.02
        assert physical_d == pytest.approx(9.0, abs=tol), \
            f"{name} 密度下头部物理直径 {physical_d:.2f}cm 偏离 9cm"
