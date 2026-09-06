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
    Stitch,
    glossary_note_lines,
)

_FAMILIES = {"基础针", "加减针", "簇生针", "边缘针", "挑针与钩位"}
_COUNTS = {
    "1→1", "0→1（新基底）", "—（连接）", "1→2", "2→1", "3→1", "4→1",
    "跳过（不钩）", "中性（进出各1）", "装饰（不入针数）", "1→1（反向）",
    "修饰",
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
