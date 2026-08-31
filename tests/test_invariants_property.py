"""U4：hypothesis 属性测试——生成器不变量的随机域模糊化。

网格矩阵（264 组合）是采样；这里用随机域验证**不变量**在任意输入下
成立：6 的倍数、相邻圈 |Δ| 不超过密度动态上限、代数自洽、桥接无跳变。
"""
from hypothesis import given, settings
from hypothesis import strategies as st

from app.models.crochet_params import (
    CrochetParamsGenerator,
    bridge_rounds,
)
from app.models.gauge import PRESETS, ShapingStyle
from app.models.structure_designer import StructureDesigner
from app.models.validator import validate_pattern
from app.schemas import ImageAnalysis

_head = st.floats(min_value=4.0, max_value=20.0)
_height = st.floats(min_value=10.0, max_value=60.0)
_gauge = st.sampled_from(list(PRESETS.values()))
_mode = st.sampled_from(["ladder", "ideal", "egg"])
_one = st.booleans()


_parts = st.sampled_from([
        ["头部", "身体", "手臂", "腿部"],
        ["头部", "身体", "裙子"],
        ["头部", "身体", "帽子"],
        ["头部", "身体", "裙子", "帽子"],
])
_ruffle = st.booleans()


@given(head=_head, height=_height, gauge=_gauge, mode=_mode, one=_one,
       parts=_parts, ruffle=_ruffle)
@settings(max_examples=48, deadline=None)
def test_generation_invariants_hold(head, height, gauge, mode, one, parts,
                                    ruffle):
    """任意（头径, 身高, 密度, 球型, 一体, 部件, 波浪摆）组合：全部不变量。

    V2 扩域：裙子/帽子/ruffle 进入模糊域——波浪摆圈经 allow_wide_jump
    显式豁免塑形上限，其余圈仍受当前 gauge 的动态上限约束。
    """
    a = ImageAnalysis(body_type="标准", head_diameter_cm=round(head, 1),
                      height_cm=round(height, 1), main_features=[],
                      pose="站立", difficulty="easy", parts=parts)
    st = StructureDesigner.design_3d_structure(a)
    params = CrochetParamsGenerator.generate_params(
        a, st, gauge=gauge,
        style=ShapingStyle(sphere_mode=mode, one_piece=one, ruffle_hem=ruffle))
    v = validate_pattern(params)
    assert v["ok"], v["issues"]
    for part in params["parts"]:
        for r in part.rounds:
            assert r.stitches % 6 == 0            # 6 的倍数
            assert r.stitches >= 6
        sts = [r.stitches for r in part.rounds]
        for a_, b, _prev_r, cur_r in zip(  # noqa: B905 - adjacent pairs truncate by design
                sts, sts[1:],
                part.rounds, part.rounds[1:]):
            if not (getattr(cur_r, "allow_wide_jump", False)
                    or (isinstance(cur_r, dict) and cur_r.get("allow_wide_jump"))):
                assert abs(b - a_) <= gauge.max_shaping_change


@given(cur=st.integers(min_value=6, max_value=150).filter(lambda x: x % 6 == 0),
       target=st.integers(min_value=6, max_value=150).filter(lambda x: x % 6 == 0))
@settings(max_examples=100, deadline=None)
def test_bridge_rounds_invariants(cur, target):
    """桥接器不变量：逐圈 6 步、两端不重复、终点正确。"""
    out = bridge_rounds(cur, target)
    for s in out:
        assert s % 6 == 0 and s >= 6
    assert all(abs(b - a_) == 6 for a_, b in zip([cur] + out, out))  # noqa: B905
    assert not out or out[-1] == target
    assert len(out) <= abs(target - cur) // 6
