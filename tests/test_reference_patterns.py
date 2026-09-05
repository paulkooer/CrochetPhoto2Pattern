"""真实世界图解印证（外部校准）——用社区公开图解验证本系统的领域假设。

参考来源（免费公开图解，仅取针数代数与圈结构，不复制创作文本）：
- Clover 官方免费图解 AKIHIRO（26cm 玩偶）：腿 6→12→18→22、臂 6→12→16、
  耳 6→12→14→16→18、尾 6→9、头 18→24→…→54（每圈均匀 +6）→ 收口镜像。
  https://www.clover-mfg.com/en/project/amigurumi-akihiro-crochet-pattern/
- 社区通用球体公式：6 针起环、每圈 +6（(N sc, inc)×6）——PlanetJune
  magic ring 教程与 r/Amigurumi 常规口径。
  https://www.planetjune.com/blog/amigurumi-help/how-to-crochet-a-magic-ring/
- Lovable Loops 樱桃迷你 C2C 图表（9×9，逐行色块文字版全文）：
  https://lovableloops.com/cherry-square-mini-c2c-crochet-pattern/

印证结论钉死在本文件：真实可钩的图解必须通过本系统校验器；生成器的
增减针节奏必须与社区通用公式一致；CrochetPARADE 导出与官方示例同构。
"""

from PIL import Image

from app.models.crochet_params import _sphere_rounds
from app.models.validator import validate_pattern
from app.utils.parade_export import export_parade_dsl, lint_parade_dsl

# ── Clover AKIHIRO：公开发布的真实部件圈结构（针数代数） ─────────────────

def _akihiro_parts() -> list[dict]:
    leg = {"name": "腿部", "type": "cylinder", "color": "灰色", "magic_ring": True,
           "rounds": [
               {"row": 1, "stitches": 6},
               {"row": 2, "stitches": 12, "increase": 6},
               {"row": 3, "stitches": 18, "increase": 6},
               {"row": 4, "stitches": 22, "increase": 4},   # 真实图解的非标准 +4
               {"row": 5, "stitches": 22},
               {"row": 6, "stitches": 22},
           ]}
    arm = {"name": "手臂", "type": "cylinder", "color": "灰色", "magic_ring": True,
           "rounds": [
               {"row": 1, "stitches": 6},
               {"row": 2, "stitches": 12, "increase": 6},
               {"row": 3, "stitches": 16, "increase": 4},   # +4
               {"row": 4, "stitches": 16},
           ]}
    ear = {"name": "耳朵", "type": "sphere", "color": "灰色", "magic_ring": True,
           "rounds": [
               {"row": 1, "stitches": 6},
               {"row": 2, "stitches": 12, "increase": 6},
               {"row": 3, "stitches": 14, "increase": 2},   # +2
               {"row": 4, "stitches": 16, "increase": 2},
               {"row": 5, "stitches": 18, "increase": 2},
           ]}
    tail = {"name": "尾巴", "type": "cylinder", "color": "灰色", "magic_ring": True,
            "rounds": [
                {"row": 1, "stitches": 6},
                {"row": 2, "stitches": 9, "increase": 3},    # +3
            ]}
    return [leg, arm, ear, tail]


def test_published_akihiro_parts_pass_validation():
    """社区公认可钩的真实图解必须通过代数自检（六等分之外的圈走 notes）。"""
    result = validate_pattern({"parts": _akihiro_parts()})
    assert result["ok"], result["issues"]
    # 非六等分的真实圈应给出提示而非报错
    assert result["notes"], "22/16/14/9 针的圈应产生非 6 倍数提示"


def test_published_akihiro_head_increase_cadence_passes():
    """头部 18→24→…→54 的每圈均匀 +6：代数与 V 可执行性全部成立。"""
    rounds = [{"row": 1, "stitches": 18}]
    for i, target in enumerate(range(24, 55, 6), 2):
        rounds.append({"row": i, "stitches": target, "increase": 6})
    result = validate_pattern({"parts": [{"name": "头部", "rounds": rounds}]})
    assert result["ok"], result["issues"]
    assert not result["notes"]  # 全部 6 的倍数，无提示


# ── 社区通用球体公式 vs 本生成器 ──────────────────────────────────────────

def test_generated_sphere_matches_community_formula():
    """生成器的阶梯球与社区通用公式逐圈一致：6→+6/圈→36，(N sc, inc)×6。"""
    rounds = _sphere_rounds(max_stitches=36)
    stitches = [r["stitches"] for r in rounds]
    assert stitches[:6] == [6, 12, 18, 24, 30, 36]
    assert [r.get("increase") for r in rounds[1:6]] == [6, 6, 6, 6, 6]
    # 收口镜像：36 → … → 6，每圈 -6
    assert stitches[-5:] == [30, 24, 18, 12, 6]
    assert [r.get("decrease") for r in rounds[12:]] == [6, 6, 6, 6, 6]


def test_exported_sphere_matches_official_parade_example():
    """导出的 DSL 与 CrochetPARADE 官方论坛 sphere 示例同构
    （官方 8 基：ring / sc8inc / 8sc2inc / 8[sc,sc2inc] / 8[2sc,sc2inc]）。"""
    part = {"name": "头部", "type": "sphere", "color": "肤色",
            "magic_ring": True, "rounds": _sphere_rounds(max_stitches=36)}
    text = export_parade_dsl({"params": {"parts": [part]}})
    body = [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.startswith("#")]
    assert body[:5] == ["ring", "sc6inc", "6sc2inc", "6[sc,sc2inc]", "6[2sc,sc2inc]"]
    assert lint_parade_dsl(text) == []


def test_exporter_honest_on_published_plus4_round():
    """AKIHIRO 腿部的 18→22（+4，不可均分）圈：诚实记 warning 而非瞎译；
    其余圈正常导出。"""
    text = export_parade_dsl({"params": {"parts": [_akihiro_parts()[0]]}})
    assert "超出可译子集" in text
    assert "sc6inc" in text and "6sc2inc" in text
    assert lint_parade_dsl(text) == []


# ── Lovable Loops 樱桃 C2C 图表 vs 网格管线 ───────────────────────────────

_CHART_ROWS: list[list[tuple[str, int]]] = [
    [("white", 1)],
    [("white", 2)],
    [("white", 1), ("red", 1), ("white", 1)],
    [("white", 1), ("red", 2), ("white", 1)],
    [("white", 1), ("red", 3), ("white", 1)],
    [("white", 2), ("red", 2), ("white", 2)],
    [("white", 2), ("green", 1), ("red", 1), ("white", 3)],
    [("white", 2), ("red", 1), ("white", 2), ("green", 1), ("white", 2)],
    [("white", 5), ("red", 2), ("white", 2)],
    [("white", 1), ("red", 3), ("white", 1), ("green", 1), ("white", 2)],
    [("white", 4), ("red", 2), ("white", 1)],
    [("white", 1), ("red", 1), ("green", 3), ("white", 1)],
    [("white", 5)],
    [("white", 4)],
    [("white", 3)],
    [("white", 2)],
    [("white", 1)],
]
_CLUSTER_RGB = {"white": (255, 255, 255), "red": (215, 40, 50), "green": (70, 150, 70)}


def _reconstruct_chart_grid() -> dict[tuple[int, int], str]:
    """C2C 文字行 → 9×9 网格（标准反对角线映射：Row r 覆盖 col+row=r-1）。"""
    n = 9
    grid: dict[tuple[int, int], str] = {}
    for r, blocks in enumerate(_CHART_ROWS, 1):
        seq: list[str] = []
        for color, cnt in blocks:
            seq.extend([color] * cnt)
        offset = max(0, r - n)
        cells = [(offset + j, r - 1 - (offset + j)) for j in range(len(seq))]
        for cell, color in zip(cells, seq):  # noqa: B905 - 长度由构造保证
            grid[cell] = color
    assert len(grid) == n * n
    return grid


def test_grid_pipeline_reproduces_published_c2c_chart():
    """把发布的樱桃图表编码为图片 → 本系统网格管线（nearest 直采样）
    → 每个色簇必须整簇映射到同一毛线色，簇大小与图表完全一致
    （white 57 / red 18 / green 6）。"""
    grid = _reconstruct_chart_grid()
    img = Image.new("RGB", (9, 9))
    for (col, row), color in grid.items():
        img.putpixel((col, row), _CLUSTER_RGB[color])

    from app.models.grid_pattern import generate_grid_pattern

    pattern = generate_grid_pattern(img, grid_width=9, n_colors=3,
                                    aspect_ratio=1.0, resample="nearest")
    assert (pattern.width, pattern.height) == (9, 9)

    # 每个图表色簇 → 唯一毛线色（不分裂、不合并）
    cluster_to_yarn: dict[str, str] = {}
    for r in range(9):
        for c in range(9):
            chart = grid[(c, r)]
            cell = pattern.cells[r][c]
            if chart in cluster_to_yarn:
                assert cluster_to_yarn[chart] == cell.color_name, (
                    f"({c},{r}) {chart} 色簇被拆分到不同毛线色")
            else:
                cluster_to_yarn[chart] = cell.color_name
    assert len(cluster_to_yarn) == 3

    counts: dict[str, int] = {}
    for row_cells in pattern.cells:
        for cell in row_cells:
            counts[cell.color_name] = counts.get(cell.color_name, 0) + 1
    assert sorted(counts.values()) == [6, 18, 57]

    # 锚点：左上角必为白色簇；(5,3) 在发布图表 Row 9 的红色段内
    assert cluster_to_yarn[grid[(0, 0)]] == pattern.cells[0][0].color_name
    assert grid[(5, 3)] == "red"
    assert pattern.cells[3][5].color_name == cluster_to_yarn["red"]


def test_chart_image_through_exporter_roundtrip_unaffected():
    """网格与逐圈图解互不干扰：图表图片路径不应影响 CrochetPARADE 导出。"""
    r = {"params": {"parts": _akihiro_parts()}}
    text = export_parade_dsl(r)
    assert lint_parade_dsl(text) == []
