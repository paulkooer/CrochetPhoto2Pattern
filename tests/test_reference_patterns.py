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
- DROPS Design（Garnstudio，欧洲最大免费图解库）Children 23-60 苹果玩偶：
  环形起针 7 针、7/14/21/28/35/42 对称增、9 圈平针、对称减到 6；4.5mm、
  官方密度 18 短针 = 10cm（柄为 4 针锁针起点小筒）。按 DROPS 版权声明
  仅取针数代数。
  https://www.garnstudio.com/pattern.php?id=5888&cid=17
- CYC（Craft Yarn Council）Standard Yarn Weight System：官方密度分档
  （短针/4 英寸）——gauge 层 cyc_label 映射以此核对。
  https://www.craftyarncouncil.com/standards/yarn-weight-system

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


# ── Ms Premise-Conclusion《The Ideal Crochet Sphere》理想球方法印证 ─────────
# 原文（2010，本系统 M2.6 的引用出处）："dividing the circumference (C) by the
# size of a single stitch (s): N = C/s"，圆周按 sin(θ) 分布；实测样例含
# 39/16 等非 6 倍数圈（再次佐证校验器降级为 notes 的决定）。
# https://mspremiseconclusion.wordpress.com/2010/03/14/the-ideal-crochet-sphere/

def test_ideal_sphere_follows_source_sin_profile():
    """理想球的 sin 轮廓性质：先升后降、峰在赤道、上下对称（量化/钳制容差）、
    全部圈可执行。"""
    import math

    from app.models.crochet_params import _ideal_sphere_rounds
    from app.models.gauge import Gauge

    gauge = Gauge(13.0, 16.0)
    diameter = 9.0
    rounds = _ideal_sphere_rounds(diameter, gauge)
    seq = [r["stitches"] for r in rounds]
    n = len(seq)
    assert n == int(diameter / gauge.row_h_cm + 0.5)

    peak = seq.index(max(seq))
    assert abs(peak - (n - 1) / 2) <= max(2, n // 6)   # 峰在赤道附近
    assert seq[: peak + 1] == sorted(seq[: peak + 1])   # 升
    assert seq[peak:] == sorted(seq[peak:], reverse=True)  # 降
    for j in range(n // 2):                             # sin 对称（±1 档容差）
        assert abs(seq[j] - seq[n - 1 - j]) <= 6

    # 理论 sin 目标 N = π·D·sin(π·y/D)/s（原文 N = C/s），本输出落在其
    # 6 等分量化 + 动态钳制的可行域内
    for j, st in enumerate(seq, 1):
        y = (j - 0.5) * gauge.row_h_cm
        theta = math.pi * min(y, diameter) / diameter
        raw = math.pi * diameter * math.sin(theta) / gauge.stitch_w_cm
        assert abs(st - raw) <= 6 + 6, (j, st, raw)

    result = validate_pattern({"parts": [{"name": "头部", "rounds": rounds}]})
    assert result["ok"], result["issues"]


def test_ideal_sphere_honors_source_craft_warning():
    """原文工艺警告（勿收针到 6 针，穿线勒紧收口）落实在收尾圈备注。"""
    from app.models.crochet_params import _ideal_sphere_rounds
    from app.models.gauge import Gauge

    rounds = _ideal_sphere_rounds(9.0, Gauge(13.0, 16.0))
    assert "勒紧收口" in (rounds[-1].get("notes") or "")


def test_parade_tokens_align_with_cyc_abbreviations():
    """Craft Yarn Council 缩写规范（行业权威）中 `sc2tog` 是标准减针缩写；
    CrochetPARADE 的增针形式 sc2inc 与之对称。导出 token 与规范同源。
    https://www.craftyarncouncil.com/standards/crochet-abbreviations"""
    part = {"name": "头部", "type": "sphere", "color": "肤色",
            "magic_ring": True, "rounds": _sphere_rounds(max_stitches=36)}
    text = export_parade_dsl({"params": {"parts": [part]}})
    assert "sc2tog" in text   # CYC 官方缩写
    assert "sc2inc" in text   # CrochetPARADE 对称增针


# ── Spin a Yarn Crochet（专业设计师 Jillian Hewitt）8 针起环印证 ────────────
# 其免费图解（Rudolph Ornament 等）的首圈形如 "Rnd 1: Work 8 hdc into a
# magic ring (8 sts)"——专业设计师同样使用非 6 起针。
# https://spinayarncrochet.com/rudolph-ornament-free-crochet-pattern/

def test_professional_eight_stitch_ring_start_passes_validation():
    """8 hdc 起环的专业图解通过校验（非 6 倍数 → notes 而非错误）。"""
    head = {"name": "头部", "type": "sphere", "color": "棕色", "magic_ring": True,
            "rounds": [
                {"row": 1, "stitches": 8},
                {"row": 2, "stitches": 16, "increase": 8},
                {"row": 3, "stitches": 24, "increase": 8},
                {"row": 4, "stitches": 24},
            ]}
    result = validate_pattern({"parts": [head]})
    assert result["ok"], result["issues"]
    assert any("非 6 的倍数" in note for note in result["notes"])


# ── DROPS Design / Garnstudio（欧洲最大免费图解库，专业级）──────────────────
# DROPS Children 23-60「Ambrosia」苹果玩偶：DROPS Paris 棉线、4.5mm 钩针、
# 官方密度 18 短针 × 20 圈 = 10×10cm。环形起针 7 针、7/14/21/28/35/42
# 对称增、9 圈平针（42）、R17–R22 对称减 42→36→30→24→18→12→6；
# 果柄 = 锁针起点 4 短针 × 4 圈（非魔法环）。按 DROPS 版权声明仅取
# 针数代数，不复制图解文本。
# https://www.garnstudio.com/pattern.php?id=5888&cid=17
# （历史注脚：该图解 2012-12 曾把 R17 的减针误印为加针并官方更正——
#   出版图解也有代数错，正是本系统逐圈自检的价值所在。）

def _drops_apple_parts() -> list[dict]:
    apple = {"name": "苹果", "type": "sphere", "color": "红色", "magic_ring": True,
             "rounds": [
                 {"row": 1, "stitches": 7},   # DROPS 7 针环形起针（非 6 针体系）
                 {"row": 2, "stitches": 14, "increase": 7},
                 {"row": 3, "stitches": 21, "increase": 7},
                 {"row": 4, "stitches": 28, "increase": 7},
                 {"row": 5, "stitches": 35, "increase": 7},
                 {"row": 6, "stitches": 35},
                 {"row": 7, "stitches": 42, "increase": 7},
                 *({"row": r, "stitches": 42} for r in range(8, 17)),
                 {"row": 17, "stitches": 36, "decrease": 6},
                 {"row": 18, "stitches": 30, "decrease": 6},
                 {"row": 19, "stitches": 24, "decrease": 6},
                 {"row": 20, "stitches": 18, "decrease": 6},
                 {"row": 21, "stitches": 12, "decrease": 6},
                 {"row": 22, "stitches": 6, "decrease": 6},
             ]}
    stem = {"name": "果柄", "type": "cylinder", "color": "棕色",
            "magic_ring": False,
            "rounds": [{"row": r, "stitches": 4} for r in range(1, 5)]}
    return [apple, stem]


def test_published_drops_apple_passes_validation():
    """DROPS 苹果（7 针起环、+7 增圈、非 6 倍数平针）必须通过校验。

    默认 gauge（classic）的平滑上限 ±6：+7 圈与 7/14/21/28/35 非等分圈
    都应降级为 notes；可执行性硬检查（代数/inc≤prev/dec≤prev/2）全过。
    """
    result = validate_pattern({"parts": _drops_apple_parts()})
    assert result["ok"], result["issues"]
    notes = "\n".join(result["notes"])
    assert "非 6 的倍数" in notes           # 7/14/21/28/35/…/4 针圈
    assert "相邻圈跳变" in notes            # 35→42 等 +7 圈（超 ±6 平滑先验）


def test_drops_apple_exports_clean_parade_dsl():
    """专业图解 → CrochetPARADE DSL 全圈可译且过 emitter lint。"""
    dsl = export_parade_dsl({"params": {"parts": _drops_apple_parts()}})
    assert lint_parade_dsl(dsl) == []
    assert "sc7inc" in dsl            # 7 针环形起针（scNinc 形式）
    assert "7[sc,sc2inc]" in dsl      # 14→21：base=1 对齐官方示例写法
    assert "6[sc,sc2tog]" in dsl      # 12→6 收口（sc2tog 与 CYC 缩写一致）


def test_drops_stem_chain_start_exports_with_honest_warning():
    """果柄 4 针锁针起点（非魔法环）：可导出但带人工核对提示。"""
    stem = _drops_apple_parts()[1]
    dsl = export_parade_dsl({"params": {"parts": [stem]}})
    assert lint_parade_dsl(dsl) == []
    assert "非魔法环" in dsl and "sc4inc" in dsl
