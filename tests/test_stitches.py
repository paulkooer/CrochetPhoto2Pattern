"""针法速查表（app.models.stitches）——词表完整性与导出接线。

词表内容的外部校准来源（逐字核对）：
- CYC 官方缩写全表（sc/hdc/dc/tr/dtr/trtr、pc/ps/bo/CL、FLO/BLO、
  FP/BP 族）——US 记号口径；
- 中文图解 X/T/F/E 体系（社区新手指南与既有图解惯例）；
- US↔UK 错位一级（Shelley Husband / KnitPro 对照表）；
- 日语名称（toruyuri / Hamanaka 系教程）；
- 簇生针"中性"语义（软糖枣形 / 53stitches 爆米花逐字）；
- sc4tog（Minion）、picot/逆短针（边缘装饰，社区通用）。
"""

from app.models.stitches import (
    _HEIGHT_LADDER_US_UK,
    STITCH_GLOSSARY,
    TUNISIAN_GLOSSARY,
    Stitch,
    glossary_note_lines,
    glossary_table_markdown,
)

_FAMILIES = {"基础针", "加减针", "簇生针", "边缘针", "挑针与钩位",
             "纹理针", "突尼斯针"}
_COUNTS = {
    "1→1", "0→1（新基底）", "—（连接）", "1→2", "1→3", "2→1", "3→1",
    "4→1", "跳过（不钩）", "中性（进出各1）", "装饰（不入针数）",
    "1→1（反向）", "修饰", "1→1（按前进程）", "—（行结构）",
    "1→1（反面起圈）", "2→1（挂4环并拉过）",
}


def test_glossary_entries_are_unique_and_well_formed():
    symbols = [s.symbol for s in STITCH_GLOSSARY]
    assert len(symbols) == len(set(symbols))
    zh_names = [s.zh for s in STITCH_GLOSSARY]
    assert len(zh_names) == len(set(zh_names))
    for s in STITCH_GLOSSARY:
        assert isinstance(s, Stitch)
        assert all((s.zh, s.symbol, s.us, s.uk, s.jp, s.count, s.family,
                    s.note)), s
        assert s.family in _FAMILIES, s
        assert s.count in _COUNTS, s


def test_height_ladder_us_uk_offset_invariant():
    """US↔UK 错位一级：配对表与 Shelley Husband/KnitPro 公布对照逐项一致；
    UK 名恒比 US 名"高一级"（US sc=UK dc、US dc=UK tr、US dtr=UK ttr）。"""
    published_chart = {
        "sc": "dc", "hdc": "htr", "dc": "tr", "tr": "dtr", "dtr": "ttr",
    }
    assert dict(_HEIGHT_LADDER_US_UK) == published_chart
    # 词表中的短/中/长/长长针与配对表一致
    by_symbol = {s.symbol: s for s in STITCH_GLOSSARY}
    for symbol in ("X", "T", "F", "E"):
        stitch = by_symbol[symbol]
        assert stitch.uk == published_chart[stitch.us], stitch
    # "高一级"方向不变量：US 名的 UK 名不会是同级或更低针高的 US 名
    rank = {us: i for i, (us, _) in enumerate(_HEIGHT_LADDER_US_UK)}
    for us, uk in _HEIGHT_LADDER_US_UK:
        assert uk not in {u for u, i in rank.items() if i <= rank[us]}


def test_cluster_stitches_are_count_neutral():
    """簇生针族必须全部为中性（进出各1）——软糖枣形/低缝兔爆米花印证。"""
    cluster = [s for s in STITCH_GLOSSARY if s.family == "簇生针"]
    assert {s.zh for s in cluster} == {"枣形针", "泡芙针", "爆米花针"}
    assert all(s.count == "中性（进出各1）" for s in cluster)


def test_glossary_lines_render_into_export():
    """导出图例接线：针高阶梯行与变化/边缘针族行进入 markdown。"""
    from app.utils.exporters import export_markdown
    from tests.test_exporters import _sample_params

    params, analysis = _sample_params()
    md = export_markdown(params, analysis)
    assert "针高阶梯" in md and "US sc=UK dc" in md
    assert "变化针族（枣形针、泡芙针、爆米花针）" in md
    assert "边缘装饰（狗牙针、逆短针）" in md
    lines = glossary_note_lines()
    assert len(lines) == 2 and all(line.startswith("> ") for line in lines)


def test_w_three_in_one_entry_exists():
    """W（1针目3短针，1→3）必须入表——图例既有记号，椭圆端盖/花瓣加厚。"""
    by_symbol = {s.symbol: s for s in STITCH_GLOSSARY}
    w = by_symbol["W"]
    assert w.count == "1→3" and w.family == "加减针"
    assert "3 sc" in w.us


def test_tunisian_family_matches_cyc_chart():
    """突尼斯 13 条 = CYC 官方表逐字（12 针 + FwP/RetP 行结构）。"""
    assert len(TUNISIAN_GLOSSARY) == 13
    cyc = {"tss", "tks", "tps", "tsc", "tdc", "thdc", "trs", "tslst",
           "ttr", "tfs", "etss", "ttw", "FwP/RetP"}
    assert {s.symbol for s in TUNISIAN_GLOSSARY} == cyc
    # 全族同分族；除行结构条目外均为"1→1（按前进程）"
    assert all(s.family == "突尼斯针" for s in TUNISIAN_GLOSSARY)
    for s in TUNISIAN_GLOSSARY:
        if s.symbol != "FwP/RetP":
            assert s.count == "1→1（按前进程）", s


def test_glossary_table_markdown_renders_both_tables():
    """结果页「针法速查」数据：两张表 + 每表表头 + 来源指针。"""
    md = glossary_table_markdown()
    assert "钩针针法（五体系对照）" in md
    assert "突尼斯针族" in md and "圈代数不适用" in md
    assert md.count("| 记号 | 针法 | US | UK | 日语 | 针数 | 说明 |") == 2
    assert "docs/SOURCES.md" in md
    assert "| W | 三放一 |" in md and "| tss | 突尼斯简单针 |" in md


def test_loop_stitch_family_entries():
    """纹理针族（圈圈针三词条）——反面起圈语义 + 挂4环减针。"""
    texture = [s for s in STITCH_GLOSSARY if s.family == "纹理针"]
    assert {s.symbol for s in texture} == {"loop st", "double loop",
                                           "loop dec"}
    loop = next(s for s in texture if s.symbol == "loop st")
    assert loop.count == "1→1（反面起圈）"
    assert "反面" in loop.note and "front-side" in loop.note
    dec = next(s for s in texture if s.symbol == "loop dec")
    assert dec.count == "2→1（挂4环并拉过）"


def test_symbol_strip_renders_chart_glyphs():
    """符号条：inline SVG 走 markdown 通道；十个基础记号图形齐全。"""
    from app.models.stitches import symbol_strip_html
    html = symbol_strip_html()
    assert html.count("<svg") == 10
    for label in ("锁针 CH", "引拔 SL", "短针 X", "加针 V", "减针 A",
                  "三放一 W", "中长针 T", "长针 F", "长长针 E", "枣形针 B"):
        assert label in html
