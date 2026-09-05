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
- StringyDingDing 袋鼠 + 小袋鼠免费图解（Yarn 4/Medium、4mm）：头部
  环起后先平钩一圈、一体钩非均匀增减与 21/15 奇数圈、耳朵 inc-4、
  腿部 R5 已发布印刷矛盾（加针指令 vs (24) 计数）——第二例真实出版
  错误夹具。
  https://stringydingding.com/kangaroo-amigurumi-free-crochet-pattern/
- CYC Project Levels（官方难度四级 Basic/Easy/Intermediate/Complex）：
  difficulty 显示标签（DIFFICULTY_LABELS_*）按其定义对齐。
  https://www.craftyarncouncil.com/standards/skill-levels
- kruchcom.ru 泰迪熊指偶（俄语圈逐字原文：КА 环起 6 针、6 ПРИБ、
  R5-9 平针 24——同一社区标准的跨语言验证；СБН=短针、ПРИБ=加针）。
  https://kruchcom.ru/archives/22215
- r/Amigurumi 眼睛 wiki（社区安全眼分档：迷你 5–6mm / 常规 8–12mm /
  大型 14–20mm+）——安全眼随头径分档以此校准。
  https://www.reddit.com/r/Amigurumi/wiki/faq_eyeqs/
- Supergurumi「The Chubby Bee」蜜蜂玩偶（德国专业设计工作室）：55 圈
  头身一体（66 针峰值）、黄黑条纹逐圈换色、BLO 脊线圈、"1 短针"螺旋
  移位圈、错位增减圈、3 针递减奇数收尾序列（33→…→9→6）；纱线
  Schachenmayr Catania（125m/50g=250m/100g、Sport/Fine(2)）校准
  fine 档米数估算。
  https://www.supergurumi.com/amigurumi-crochet-bee-pattern

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
    """原文工艺警告（勿收针到 6 针，穿线无痕收口）落实在收尾圈备注。"""
    from app.models.crochet_params import _ideal_sphere_rounds
    from app.models.gauge import Gauge

    rounds = _ideal_sphere_rounds(9.0, Gauge(13.0, 16.0))
    assert "无痕收口" in (rounds[-1].get("notes") or "")


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


# ── StringyDingDing（高人气免费玩偶图解站）袋鼠印证 ─────────────────────────
# 袋鼠 + 小袋鼠免费图解（Yarn 4/Medium + 4mm 钩，CYC #4 medium 紧钩惯例）。
# 三个新结构案例：① 头部环形起针后先钩 1 圈平针再增（R1: 6 → R2: 平 6）；
# ② 小袋鼠头身一体钩（对应本项目 one_piece 工艺）含非均匀增减与 21/15
# 奇数圈；③ 妈妈腿部 R5 为已发布图解的印刷矛盾（指令 *Inc, Sc in the
# next 3 st* 但计数印 (24)，按指令应 30 且后续圈均为 24）——忠实转录后
# 代数自检必须捕获（DROPS 23-60 R17 之后第二例真实出版错误）。
# https://stringydingding.com/kangaroo-amigurumi-free-crochet-pattern/

def _kangaroo_head_rounds() -> list[dict]:
    return [
        {"row": 1, "stitches": 6},
        {"row": 2, "stitches": 6},                    # 环起后先平钩一圈
        {"row": 3, "stitches": 12, "increase": 6},
        {"row": 4, "stitches": 18, "increase": 6},
        {"row": 5, "stitches": 24, "increase": 6},
        {"row": 6, "stitches": 24},
        {"row": 7, "stitches": 30, "increase": 6},
        {"row": 8, "stitches": 30},
        {"row": 9, "stitches": 36, "increase": 6},
        {"row": 10, "stitches": 36},
        {"row": 11, "stitches": 42, "increase": 6},
        {"row": 12, "stitches": 42},
        {"row": 13, "stitches": 48, "increase": 6},
        *({"row": r, "stitches": 48} for r in range(14, 19)),
    ]


def _kangaroo_baby_one_piece() -> dict:
    return {"name": "小袋鼠头身", "type": "sphere", "color": "棕色",
            "magic_ring": True, "one_piece": True,
            "rounds": [
                {"row": 1, "stitches": 6},
                {"row": 2, "stitches": 6},
                {"row": 3, "stitches": 12, "increase": 6},
                {"row": 4, "stitches": 18, "increase": 6},
                # 非均匀增：Sc 8, Inc×3, Sc 7（三处增针集中在一段）
                {"row": 5, "stitches": 21, "increase": 3},
                {"row": 6, "stitches": 18, "decrease": 3},
                {"row": 7, "stitches": 15, "decrease": 3},   # 奇数圈
                {"row": 8, "stitches": 12, "decrease": 3},
            ]}


def test_published_kangaroo_head_ring_then_plain_round_passes():
    """头部起环后先平钩一圈再增——校验器不要求起环后立刻增针。

    全程 6 倍数 + 每圈 |Δ|=6（恰在上限内）：应零 issues 零 notes。
    """
    head = {"name": "头部", "type": "sphere", "color": "棕色",
            "magic_ring": True, "rounds": _kangaroo_head_rounds()}
    result = validate_pattern({"parts": [head]})
    assert result["ok"], result["issues"]
    assert not result["notes"]


def test_published_kangaroo_baby_one_piece_asymmetric_shaping_passes():
    """一体钩的非均匀增减与 21/15 奇数圈：可钩，代数全过，走 notes。"""
    result = validate_pattern({"parts": [_kangaroo_baby_one_piece()]})
    assert result["ok"], result["issues"]
    notes = "\n".join(result["notes"])
    assert "21" in notes and "15" in notes   # 非 6 倍数圈提示


def test_kangaroo_baby_asymmetric_rounds_still_translate_to_parade():
    """非均匀塑形的聚合计数（18+3=21）仍可整体翻译为均匀分组 DSL。"""
    baby = _kangaroo_baby_one_piece()
    dsl = export_parade_dsl({"params": {"parts": [baby]}})
    assert lint_parade_dsl(dsl) == []
    assert "3[5sc,sc2inc]" in dsl    # 18→21（聚合成 3 组均匀增）
    assert "3[5sc,sc2tog]" in dsl    # 18→15
    assert "超出可译子集" not in dsl  # 全圈可译，无需诚实降级


def test_kangaroo_baby_ears_four_increases_pass_with_note():
    """耳朵 6→10（inc-4）：专业图解常见的小幅增圈。"""
    ear = {"name": "耳朵", "type": "sphere", "color": "棕色", "magic_ring": True,
           "rounds": [
               {"row": 1, "stitches": 6},
               {"row": 2, "stitches": 10, "increase": 4},
               {"row": 3, "stitches": 10},
           ]}
    result = validate_pattern({"parts": [ear]})
    assert result["ok"], result["issues"]
    assert any("非 6 的倍数" in note for note in result["notes"])


def test_validator_catches_published_kangaroo_leg_round5_contradiction():
    """忠实转录已发布 R5（加针指令 + (24) 计数互相矛盾）→ 代数捕获。

    R4=24，R5 指令 *Inc, Sc in the next 3 st* 隐含 30 但印 (24)，且 R6-8
    均为 24——按代数自检 24 ≠ 24+6。修正为其计数（平针）后通过。
    导出器同样拒绝该圈（聚合计数不自洽 → 诚实跳过）。
    """
    base = [
        {"row": 1, "stitches": 6},
        {"row": 2, "stitches": 12, "increase": 6},
        {"row": 3, "stitches": 18, "increase": 6},
        {"row": 4, "stitches": 24, "increase": 6},
    ]
    legs_bad = {"name": "腿部", "type": "cylinder", "color": "棕色",
                "magic_ring": True,
                "rounds": [*base, {"row": 5, "stitches": 24, "increase": 6},
                           *({"row": r, "stitches": 24} for r in range(6, 9))]}
    result = validate_pattern({"parts": [legs_bad]})
    assert not result["ok"]
    assert any("≠" in issue for issue in result["issues"])

    legs_fixed = {"name": "腿部", "type": "cylinder", "color": "棕色",
                  "magic_ring": True,
                  "rounds": [*base, {"row": 5, "stitches": 24},
                             *({"row": r, "stitches": 24} for r in range(6, 9))]}
    assert validate_pattern({"parts": [legs_fixed]})["ok"]

    dsl = export_parade_dsl({"params": {"parts": [legs_bad]}})
    assert "超出可译子集" in dsl and lint_parade_dsl(dsl) == []


# ── Supergurumi（德国专业设计工作室）"The Chubby Bee" 印证 ──────────────────
# 55 圈头身一体（66 针峰值）、Schachenmayr Catania 棉线（125m/50g =
# 250m/100g，标注 Sport/Fine(2)）、2.5mm 钩。专业结构全收录：黄黑条纹
# 逐圈换色（R19/25/31/37/44 五条边界）、BLO（前半针）脊线圈、"仅钩 1 短针"
# 的螺旋移位圈、错位（staggered）增减圈、收尾 3 针递减的奇数圈序列
# （33→30→27→24→21→18→15→12→9→6）。每圈代数经机械核对全部自洽。
# https://www.supergurumi.com/amigurumi-crochet-bee-pattern

def _bee_body_rounds() -> list[dict]:
    """头身一体 55 圈（逐字转录为聚合计数；黄色=Dandelion 黑色=Black）。

    BLO 圈与"1 短针移位圈"以 notes 记录：校验器只看聚合计数；移位圈
    不改变围长，按同针数转录（我们的圈=围长采样模型）。
    """
    yellow, black = "黄色", "黑色"
    return [
        {"row": 1, "stitches": 6},
        {"row": 2, "stitches": 12, "increase": 6},
        {"row": 3, "stitches": 16, "increase": 4},
        {"row": 4, "stitches": 16},
        {"row": 5, "stitches": 16},
        {"row": 6, "stitches": 20, "increase": 4,
         "notes": "前半针（BLO）：完整一圈只挑前半针——鼻线分界"},
        {"row": 7, "stitches": 24, "increase": 4},
        {"row": 8, "stitches": 30, "increase": 6},
        {"row": 9, "stitches": 36, "increase": 6},
        {"row": 10, "stitches": 42, "increase": 6},
        *({"row": r, "stitches": 42} for r in range(11, 18)),
        {"row": 18, "stitches": 36, "decrease": 6},
        {"row": 19, "stitches": 42, "increase": 6, "color": black,
         "notes": "换色至黑色 + 前半针（BLO）——第一条条纹分界"},
        {"row": 20, "stitches": 48, "increase": 6, "color": black},
        {"row": 21, "stitches": 54, "increase": 6, "color": black},
        {"row": 22, "stitches": 60, "increase": 6, "color": black},
        {"row": 23, "stitches": 66, "increase": 6, "color": black},
        {"row": 24, "stitches": 66, "color": black,
         "notes": "仅钩 1 短针——螺旋起点重对齐（移位圈，围长不变）"},
        *({"row": r, "stitches": 66, "color": yellow} for r in range(25, 30)),
        {"row": 30, "stitches": 66, "color": yellow,
         "notes": "仅钩 1 短针——移位圈"},
        *({"row": r, "stitches": 66, "color": black} for r in range(31, 36)),
        {"row": 36, "stitches": 66, "color": black,
         "notes": "仅钩 1 短针——移位圈"},
        {"row": 37, "stitches": 66, "color": yellow},
        {"row": 38, "stitches": 66, "color": yellow},
        {"row": 39, "stitches": 66, "color": yellow,
         "notes": "仅钩 1 短针——移位圈"},
        {"row": 40, "stitches": 60, "decrease": 6, "color": yellow},
        {"row": 41, "stitches": 54, "decrease": 6, "color": yellow},
        {"row": 42, "stitches": 48, "decrease": 6, "color": yellow},
        {"row": 43, "stitches": 48, "color": yellow,
         "notes": "仅钩 1 短针——移位圈"},
        {"row": 44, "stitches": 42, "decrease": 6, "color": black,
         "notes": "换色至黑色"},
        {"row": 45, "stitches": 36, "decrease": 6, "color": black},
        {"row": 46, "stitches": 33, "decrease": 3, "color": black},
        {"row": 47, "stitches": 30, "decrease": 3, "color": black},
        {"row": 48, "stitches": 27, "decrease": 3, "color": black},
        {"row": 49, "stitches": 24, "decrease": 3, "color": black},
        {"row": 50, "stitches": 21, "decrease": 3, "color": black},
        {"row": 51, "stitches": 18, "decrease": 3, "color": black},
        {"row": 52, "stitches": 15, "decrease": 3, "color": black},
        {"row": 53, "stitches": 12, "decrease": 3, "color": black},
        {"row": 54, "stitches": 9, "decrease": 3, "color": black},
        {"row": 55, "stitches": 6, "decrease": 3, "color": black},
    ]


def _bee_body_part() -> dict:
    return {"name": "头身", "type": "sphere", "color": "黄色",
            "magic_ring": True, "one_piece": True,
            "rounds": _bee_body_rounds()}


def test_published_bee_body_full_55_rounds_pass_validation():
    """蜜蜂头身 55 圈逐圈代数全过；16/20/33/27/21/15/9 等圈走 notes。"""
    result = validate_pattern({"parts": [_bee_body_part()]})
    assert result["ok"], result["issues"]
    notes = "\n".join(result["notes"])
    assert "16" in notes and "33" in notes   # 非 6 倍数圈提示


def test_bee_color_bands_export_as_parade_color_directives():
    """五条条纹边界在 DSL 中以 COLOR 指令表达（黄 #ffff00 / 黑 #1e1e1e）。"""
    dsl = export_parade_dsl({"params": {"parts": [_bee_body_part()]}})
    assert lint_parade_dsl(dsl) == []
    assert "#ffff00" in dsl and "#1e1e1e" in dsl
    # 部件级 1 条 + 边界 5 条——连续同色圈去重后不再逐圈重复
    assert dsl.count("COLOR:") == 6


def test_bee_body_translates_fully_to_parade():
    """55 圈全部可译（含 BLO 圈 R6：16→20 inc-4）——零诚实降级。"""
    dsl = export_parade_dsl({"params": {"parts": [_bee_body_part()]}})
    assert "超出可译子集" not in dsl
    assert "4[3sc,sc2inc]" in dsl    # 16→20（BLO 圈的聚合翻译）
    assert "6[10sc,sc2tog]" in dsl   # 66→60（错位圈的聚合翻译）
    assert "3[2sc,sc2tog]" in dsl    # 9→6 收尾
    assert lint_parade_dsl(dsl) == []


def test_bee_legs_and_eyes_pass_with_quantity():
    """腿（15/9 针圈、6 并减收口）与眼（12→16 inc-4）+ quantity 复制。"""
    legs = {"name": "腿部", "type": "cylinder", "color": "黑色",
            "magic_ring": True, "quantity": 6,
            "rounds": [
                {"row": 1, "stitches": 6},
                {"row": 2, "stitches": 12, "increase": 6},
                {"row": 3, "stitches": 15, "increase": 3},
                {"row": 4, "stitches": 15},
                {"row": 5, "stitches": 12, "decrease": 3},
                {"row": 6, "stitches": 6, "decrease": 6},
                {"row": 7, "stitches": 6, "notes": "前半针（BLO）"},
                {"row": 8, "stitches": 9, "increase": 3},
                {"row": 9, "stitches": 12, "increase": 3},
            ]}
    eyes = {"name": "眼睛", "type": "sphere", "color": "白色",
            "magic_ring": True, "quantity": 2,
            "rounds": [
                {"row": 1, "stitches": 6},
                {"row": 2, "stitches": 12, "increase": 6},
                {"row": 3, "stitches": 16, "increase": 4},
                {"row": 4, "stitches": 16},
            ]}
    result = validate_pattern({"parts": [legs, eyes]})
    assert result["ok"], result["issues"]
    dsl = export_parade_dsl({"params": {"parts": [legs, eyes]}})
    assert lint_parade_dsl(dsl) == []
    assert dsl.count("start_anew") >= 6
    # 每份拷贝都重置为部件色（不继承上一份结尾色）
    assert dsl.count("COLOR: #1e1e1e") == 6


def test_bee_anchor_cites_catania_cotton_meterage():
    """Catania 棉线（125m/50g=250m/100g、Sport(2)、2.5mm）校准 fine 档
    米数估算——材料清单最常用纤维从毛线口径改为棉线口径。"""
    from app.models.gauge import PRESETS, Gauge
    assert PRESETS["fine"].meters_per_100g == 250.0
    assert Gauge(18.0, 20.0).meters_per_100g == 250.0


# ── 俄语圈印证（kruchcom.ru，全球玩偶图解传播量最大的语种之一）──────────────
# 泰迪熊指偶（«Мишка-косолапый»）逐字原文：Ряд №1: 6 СБН в КА；
# Ряд №2: 6 ПРИБ. (12)；Ряды №5-9: без прибавок, 24 СБН。
# 术语对照：СБН=短针、ПРИБ=加针、УБАВ=减针、КА=кольцо амигуруми（魔法环）。
# R3-R4 按 +6 节奏补全（R2=12 → R5-9=24 区间的唯一合理解，已注明推断）。
# 另：同站大熊头部用 ВПП（起立锁针）逐圈引拔——俄语圈常见引拔钩法；
# 聚合计数与螺旋钩完全一致，校验器无需区分。
# https://kruchcom.ru/archives/22215

def test_russian_finger_puppet_rounds_pass_validation():
    """俄语圈 КА 环起 6 针 +6 节奏：跨语言验证同一社区标准，零提示。"""
    head = {"name": "头部", "type": "sphere", "color": "棕色",
            "magic_ring": True,
            "rounds": [
                {"row": 1, "stitches": 6},                    # 6 СБН в КА
                {"row": 2, "stitches": 12, "increase": 6},    # 6 ПРИБ (12)
                {"row": 3, "stitches": 18, "increase": 6},    # +6 节奏补全
                {"row": 4, "stitches": 24, "increase": 6},    # +6 节奏补全
                *({"row": r, "stitches": 24} for r in range(5, 10)),
            ]}
    result = validate_pattern({"parts": [head]})
    assert result["ok"], result["issues"]
    assert not result["notes"]   # 标准 +6 节奏：零 issues 零 notes


# ── 中文社区印证（编织人生转载·紫柚手作「骨头团子」，图片图解视觉转录）───────
# 图解为图片制图（appimg.bianzhirensheng.com CDN，2026-09 抓取），经视觉
# 识别逐字转录为聚合计数。记号与本项目导出图例完全一致：
# X=短针、V=加针、A=减针、CH=锁针、SL=引拔；线材 4 股毛线 + 1.8/2.0mm
# 钩（中文社区紧钩惯例，印证 fine 预设的"4 股棉线"标签）。
# 结构特点：① 主体为【每圈起立锁针+引拔】的引拔圈钩法（中文社区主流，
# 区别于欧美螺旋钩）——聚合计数与螺旋钩完全一致，校验器无需区分；
# ② 主体 6→42→6 对称 ±6 节奏；③ 骨头2 R6 记"36X"= 18→36 倍增圈；
# ④ 刘海环起 10 / 8（非 6 起针再+2）；⑤ 头套 R18 后留 30 针开口不收口。
# https://www.bianzhirensheng.com/a/44140_zhifa.html

def _cn_tuanzi_body_rounds() -> list[dict]:
    """主体 R1-R20：对称 +6/-6（引拔圈，聚合计数与螺旋钩一致）。"""
    return [
        {"row": 1, "stitches": 6},
        {"row": 2, "stitches": 12, "increase": 6},
        {"row": 3, "stitches": 18, "increase": 6},
        {"row": 4, "stitches": 24, "increase": 6},
        {"row": 5, "stitches": 30, "increase": 6},
        {"row": 6, "stitches": 36, "increase": 6},
        {"row": 7, "stitches": 42, "increase": 6},
        *({"row": r, "stitches": 42} for r in range(8, 15)),
        {"row": 15, "stitches": 36, "decrease": 6},
        {"row": 16, "stitches": 30, "decrease": 6},
        {"row": 17, "stitches": 24, "decrease": 6},
        {"row": 18, "stitches": 18, "decrease": 6},
        {"row": 19, "stitches": 12, "decrease": 6},
        {"row": 20, "stitches": 6, "decrease": 6,
         "notes": "留长线缝合收口（原文：留长线缝合收口）"},
    ]


def _cn_bone2_rounds() -> list[dict]:
    """骨头2 R1-R11：R6 记"36X"——18→36 倍增圈（隐含每针 2 短针）。"""
    return [
        {"row": 1, "stitches": 6},
        {"row": 2, "stitches": 12, "increase": 6},
        {"row": 3, "stitches": 18, "increase": 6},
        *({"row": r, "stitches": 18} for r in (4, 5)),
        {"row": 6, "stitches": 36, "increase": 18,
         "notes": "倍增圈（原文记 36X，每针 2 短针）"},
        {"row": 7, "stitches": 30, "decrease": 6},
        {"row": 8, "stitches": 24, "decrease": 6},
        {"row": 9, "stitches": 18, "decrease": 6},
        *({"row": r, "stitches": 18} for r in (10, 11)),
    ]


def _cn_headcover_rounds() -> list[dict]:
    """头套（大人团子）R1-R18：增到 42、9 圈平针、减到 30——留 30 针开口。"""
    return [
        {"row": 1, "stitches": 6},
        {"row": 2, "stitches": 12, "increase": 6},
        {"row": 3, "stitches": 18, "increase": 6},
        {"row": 4, "stitches": 24, "increase": 6},
        {"row": 5, "stitches": 30, "increase": 6},
        {"row": 6, "stitches": 36, "increase": 6},
        {"row": 7, "stitches": 42, "increase": 6},
        *({"row": r, "stitches": 42} for r in range(8, 17)),
        {"row": 17, "stitches": 36, "decrease": 6},
        {"row": 18, "stitches": 30, "decrease": 6,
         "notes": "开口保留（头套套入主体，不收口）"},
    ]


def test_cn_tuanzi_body_symmetric_cadence_passes():
    """中文图解主体（引拔圈钩法）：全程 6 倍数 ±6，零 issues 零 notes。"""
    body = {"name": "团子主体", "type": "sphere", "color": "白色",
            "magic_ring": True, "rounds": _cn_tuanzi_body_rounds()}
    result = validate_pattern({"parts": [body]})
    assert result["ok"], result["issues"]
    assert not result["notes"]


def test_cn_bone_doubling_round_passes_with_note():
    """骨头2 的 18→36 倍增圈（36X）：代数成立，平滑超限走 notes。"""
    bone = {"name": "骨头", "type": "cylinder", "color": "白色",
            "magic_ring": True, "rounds": _cn_bone2_rounds()}
    result = validate_pattern({"parts": [bone]})
    assert result["ok"], result["issues"]
    assert any("相邻圈跳变" in n for n in result["notes"])
    dsl = export_parade_dsl({"params": {"parts": [bone]}})
    assert lint_parade_dsl(dsl) == []
    assert "18sc2inc" in dsl   # 18→36 倍增圈可译（每针 2 短针）


def test_cn_bangs_non_six_ring_starts():
    """刘海环起 10 / 8：中文社区同样使用非 6 起针。"""
    parts = [
        {"name": "大刘海", "type": "sphere", "color": "白色",
         "magic_ring": True, "rounds": [{"row": 1, "stitches": 10}]},
        {"name": "小刘海", "type": "sphere", "color": "白色",
         "magic_ring": True, "rounds": [{"row": 1, "stitches": 8}]},
    ]
    result = validate_pattern({"parts": parts})
    assert result["ok"], result["issues"]
    assert any("非 6 的倍数" in n for n in result["notes"])


def test_cn_headcover_opening_feeds_openings_map():
    """头套留 30 针开口（不收口）——开口推导应计入，收口的主体不计入。"""
    from app.models.crochet_params import _openings_by_part
    parts = [
        {"name": "团子主体", "rounds": _cn_tuanzi_body_rounds()},
        {"name": "头套", "rounds": _cn_headcover_rounds()},
    ]
    openings = _openings_by_part(parts)
    assert openings.get("头套") == 30
    assert "团子主体" not in openings   # 末圈带收口注记 → 无开口
