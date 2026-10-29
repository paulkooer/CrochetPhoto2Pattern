"""生成正确性回归测试：一体钩不丢头、Parade 起针完整性、魔法环标志、
文字加减针间隔核对。对应审核发现 F-08 / F-10 / F-13 / F-14。"""
from __future__ import annotations

from app.models.crochet_params import _cylinder_rounds, _sphere_rounds
from app.models.gauge import PRESETS
from app.models.instruction_checks import instruction_issues
from app.models.onepiece import merge_head_body
from app.schemas import CrochetPart, CrochetStitch
from app.utils.parade_export import export_parade_report
from tests.test_app_smoke import _mock_result


def _part(name, typ, rounds_raw, color, magic_ring=False):
    return CrochetPart(name=name, type=typ, color=color, magic_ring=magic_ring,
                       rounds=[CrochetStitch(**r) for r in rounds_raw])


# ── F-08：身体比头宽时，一体钩不得丢掉头部 ─────────────────────────────
def test_one_piece_preserves_head_when_body_wider_than_head():
    g = PRESETS["classic"]
    head = _part("头部", "sphere", _sphere_rounds(g.stitches_for_diameter(9.0)), "肤色", True)
    body = _part("身体", "cylinder",
                 _cylinder_rounds(max_stitches=g.stitches_for_diameter(14.0), body_rounds=8), "红色")
    head_peak = max(r.stitches for r in head.rounds)
    sections: dict = {}
    merged = merge_head_body([head, body], g, sections=sections)
    seq = [r.stitches for r in merged[0].rounds]
    # 头部球冠（升到头部峰值）仍在序列里，而非被弹空成仅起针圈
    assert head_peak in seq
    assert sections["body"][0] >= len(_sphere_rounds(g.stitches_for_diameter(9.0))) // 2
    # 眼睛定位在头部峰值首现处附近，而非身体最大围（60）
    import re
    eye = int(re.search(r"第 (\d+) 圈安装安全眼", merged[0].notes).group(1))
    assert seq[eye - 1] <= head_peak + 6


def test_one_piece_normal_geometry_unchanged():
    g = PRESETS["classic"]
    head = _part("头部", "sphere", _sphere_rounds(g.stitches_for_diameter(12.0)), "肤色", True)
    body = _part("身体", "cylinder",
                 _cylinder_rounds(max_stitches=g.stitches_for_diameter(9.0), body_rounds=8), "红色")
    merged = merge_head_body([head, body], g)
    seq = [r.stitches for r in merged[0].rounds]
    assert max(seq) == max(r.stitches for r in head.rounds)  # 头比身宽：峰值即头部最大围


# ── F-10：Parade 导出对非魔法环起针部件标记为不完整 ─────────────────────
def test_parade_marks_ring_start_incomplete():
    ring_skirt = _part("裙子", "cylinder",
                       [{"row": 1, "stitches": 36, "notes": "腰部环形起针36X成环（引拔连接，开口勿收口）"}]
                       + [{"row": r, "stitches": 36, "notes": "36X"} for r in range(2, 6)],
                       "红色", magic_ring=False)
    report = export_parade_report({"params": {"parts": [ring_skirt.model_dump()]}})
    assert report.complete is False
    assert any("首圈非魔法环" in w for w in report.warnings)


def test_parade_magic_ring_sphere_complete():
    sphere = _part("头部", "sphere", _sphere_rounds(36), "肤色", magic_ring=True)
    report = export_parade_report({"params": {"parts": [sphere.model_dump()]}})
    assert report.complete is True


# ── F-13：以魔法环起针的生成部件，magic_ring 标志为真、Parade 无噪声告警 ──
def test_generated_parts_flag_magic_ring():
    result = _mock_result("f13")
    for part in result["params"]["parts"]:
        if str(part["rounds"][0].get("notes", "")).startswith("魔法环起"):
            assert part.get("magic_ring") is True, part["name"]
    report = export_parade_report(result)
    assert not [w for w in report.warnings if "首圈非魔法环" in w]


# ── F-14：文字“隔N针加/减1针”「均匀加/减N针」与操作式一致性 ────────────
def test_instruction_flags_wrong_interval():
    assert instruction_issues("(2X,V)×6，隔5针加1针", 24, 6, 0, previous_stitches=18)
    assert instruction_issues("(3X,A)×6，隔9针减1针", 24, 0, 6, previous_stitches=30)


def test_instruction_accepts_consistent_interval():
    assert not instruction_issues("(2X,V)×6，隔2针加1针", 24, 6, 0, previous_stitches=18)
    assert not instruction_issues("(3X,A)×6，隔3针减1针", 24, 0, 6, previous_stitches=30)


# ── F-12：C2C 行首箭头方向必须与该行颜色顺序的实际走向一致 ───────────────
def test_c2c_arrows_match_color_order_direction():
    from app.models.colors import YARN_COLORS
    from app.models.grid_pattern import GridCell, GridPattern, render_c2c_chart

    # 6 色不对称 3×2 网格（每格唯一颜色），可区分左右方向；对称夹具无法检测。
    palette = [(name, rgb) for rgb, name in YARN_COLORS[:6]]
    cells = [[GridCell(i, palette[i][0], palette[i][1]) for i in (0, 1, 2)],
             [GridCell(i, palette[i][0], palette[i][1]) for i in (3, 4, 5)]]
    pattern = GridPattern(width=3, height=2, cells=cells, palette=palette,
                          symbol_map={i: "ABCDEF"[i] for i in range(6)})
    names = {palette[i][0]: "ABCDEF"[i] for i in range(6)}
    coords = {"A": (0, 1), "B": (1, 1), "C": (2, 1), "D": (0, 0), "E": (1, 0), "F": (2, 0)}

    for line in render_c2c_chart(pattern).splitlines():
        if "对角行" not in line or "格，" not in line:
            continue
        arrow = line[0]
        seq = [names[n] for n in line.split("：", 1)[1].split("、")]
        if len(seq) < 2:
            continue
        (x0, y0), (x1, y1) = coords[seq[0]], coords[seq[-1]]
        dx, dy = x1 - x0, y1 - y0
        expected = "↘" if (dx > 0 and dy < 0) else "↖" if (dx < 0 and dy > 0) else None
        assert arrow == expected, (line, dx, dy)
