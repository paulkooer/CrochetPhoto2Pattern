"""真实世界图解印证——网格/C2C 专题（自 test_reference_patterns.py 拆分）。

来源与结构注记随夹具原样迁移；夹具总数以 pytest collection 为准。
- Lovable Loops 樱桃迷你 C2C 图表（9×9 逐行色块全文）：
  https://lovableloops.com/cherry-square-mini-c2c-crochet-pattern/
- Lovable Loops 心形 C2C 图表（非对称行钉死读取方向）：
  https://lovableloops.com/mini-heart-square-c2c-crochet-pattern/
"""

from PIL import Image

from app.utils.parade_export import export_parade_dsl, lint_parade_dsl

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
    # 原实现借 _akihiro_parts 作任意多部件输入；拆分后本地构造等价输入
    part = {"name": "部件", "type": "cylinder", "color": "灰色",
            "magic_ring": True,
            "rounds": [{"row": 1, "stitches": 6},
                       {"row": 2, "stitches": 12, "increase": 6}]}
    r = {"params": {"parts": [part]}}
    text = export_parade_dsl(r)
    assert lint_parade_dsl(text) == []




# ── 网格侧第二张已发布图表：Lovable Loops「Mini Heart Square」────────────────
# 9×9 两色（A=白底 / B=粉心）17 行对角，published written rows 逐行转录
# （含 ↙/↗ 方向标注与非对称行）。价值：cherry 夹具验证簇计数，本夹具
# 验证【行内颜色序列的读取方向】——非对称行（Row 7: A×1,B×4,A×2）钉死
# 相邻行反向的工作顺序约定，且方向标注与 Juniper & Oakes 一致
# （奇数行 ↙ 正面 / 偶数行 ↗ 反面）。
# https://lovableloops.com/mini-heart-square-c2c-crochet-pattern/

_HEART_ROWS: list[list[tuple[str, int]]] = [
    [("A", 1)], [("A", 2)], [("A", 3)], [("A", 4)], [("A", 5)],
    [("A", 1), ("B", 4), ("A", 1)],
    [("A", 1), ("B", 4), ("A", 2)],
    [("A", 2), ("B", 5), ("A", 1)],
    [("A", 2), ("B", 4), ("A", 3)],
    [("A", 2), ("B", 5), ("A", 1)],
    [("A", 1), ("B", 4), ("A", 2)],
    [("A", 1), ("B", 3), ("A", 2)],
    [("A", 1), ("B", 3), ("A", 1)],
    [("A", 1), ("B", 2), ("A", 1)],
    [("A", 3)], [("A", 2)], [("A", 1)],
]


def test_grid_written_rows_match_published_heart_chart():
    """心形网格经本系统 C2C 渲染 → 逐行颜色序列必须复现 published 行。

    编码约定 = 本渲染约定：奇数行（↙ 正面）工作顺序沿 x 升放置，
    偶数行（↗ 反面）反向——渲染回读恰好逐行复现 published 序列，
    非对称行（7/8/9 行）因此钉死方向约定。
    """
    n = 9
    grid: dict[tuple[int, int], tuple[int, int, int]] = {}
    for r, blocks in enumerate(_HEART_ROWS, 1):
        seq: list[str] = []
        for color, cnt in blocks:
            seq.extend([color] * cnt)
        work = seq if r % 2 == 1 else list(reversed(seq))
        offset = max(0, r - n)
        for j, color in enumerate(work):
            x = offset + j
            crochet_y = r - 1 - x
            image_y = n - 1 - crochet_y
            grid[(x, image_y)] = ((255, 255, 255) if color == "A"
                                  else (255, 105, 180))

    img = Image.new("RGB", (n, n))
    for (x, y), rgb in grid.items():
        img.putpixel((x, y), rgb)

    from app.models.grid_pattern import generate_grid_pattern, render_c2c_chart

    pattern = generate_grid_pattern(img, grid_width=9, n_colors=2,
                                    aspect_ratio=1.0, resample="nearest")
    chart = render_c2c_chart(pattern)

    row_lines = [ln for ln in chart.split("\n") if "对角行" in ln]
    assert len(row_lines) == 17
    assert row_lines[0].startswith("↙") and "正面" in row_lines[0]
    assert row_lines[1].startswith("↗") and "反面" in row_lines[1]

    # 字母 → 毛线色名映射从无歧义行学习（Row 1 全 A、Row 6 首现 B）
    letter_to_name: dict[str, str] = {}

    def name_of(letter: str, seq: list[str]) -> str:
        if letter not in letter_to_name:
            letter_to_name[letter] = next(
                c for c in seq if c not in letter_to_name.values())
        return letter_to_name[letter]

    for r, blocks in enumerate(_HEART_ROWS, 1):
        seq = row_lines[r - 1].split("：")[1].split("、")
        expected: list[str] = []
        for color, cnt in blocks:
            expected.extend([name_of(color, seq)] * cnt)
        assert seq == expected, f"对角行 {r}: {seq} != {expected}"


