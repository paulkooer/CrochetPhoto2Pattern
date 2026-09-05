"""Markdown export for generated crochet patterns."""
from __future__ import annotations

import re as _re

from app import PRODUCT_NAME
from app.schemas import difficulty_label

# U30：双语记号对照（X/V/A 日式 Amigurumi 惯例 ↔ CYC 西方体系，
# 对应关系经 craftyarncouncil.com/standards/crochet-chart-symbols 核实）
_LEGEND_BILINGUAL = (
    "> **记号对照（Stitch Key）**：X = sc (single crochet) · "
    "V = 2 sc in same st (increase) · A = sc2tog (invisible decrease) · "
    "SL = sl st · CH = ch。X/V/A 为日式 Amigurumi 惯例记号，与西方 "
    "CYC 图解体系对照如上。"
)

_INVISIBLE = _re.compile("[\u200b-\u200f\u202a-\u202e\u2066-\u2069]")


def _md_cell(value) -> str:
    """表格单元格转义（V1）+ 零宽/BiDi 剥离（G6/E1 同源补全）：
    竖线破坏列数、换行破坏行结构——GFM 表格单元格内不允许换行。
    与 PDF 路径的 esc() 同一工程惯例。"""
    text = _INVISIBLE.sub("", str(value))
    return text.replace("\\", "\\\\").replace("|", "\\|").replace(
        "\r\n", " ").replace("\n", " ").replace("\r", " ")


def _repeat_notation(st: int, prev: int, inc: int, dec: int) -> str | None:
    """聚合计数 → 专业图解的重复写法（如 (4X,V)×6）；非均匀形态返回 None。

    专业图解（Supergurumi/DROPS 等）以 "[4 sc, 1 inc] repeat" 表达均匀
    分组圈，X/V/A 记号约定见导出图例；均匀分组前提与 parade 导出器的
    _round_tokens 一致。单针增量无重复语义，同样返回 None。
    """
    if (inc and dec) or (not inc and not dec):
        return None
    groups = inc or dec
    if groups < 2 or prev % groups:
        return None
    base = prev // groups - 1
    if base < 0:
        return None
    produced = groups * (base + 2 if inc else base)
    if produced != st:
        return None
    if base == 0:
        head = ""
    elif base == 1:
        head = "X,"   # 与 parade 发射器 base==1 → "sc" 的约定一致
    else:
        head = f"{base}X,"
    op = "V" if inc else "A"
    return f"({head}{op})×{groups}"


def export_markdown(params: dict, analysis: dict | None = None) -> str:
    """Convert crochet params dict to a printable Markdown pattern."""
    lines: list[str] = []
    lines.append("# 🧶 Amigurumi 钩织图解")
    lines.append("")
    if analysis:
        lines.append(f"> 体型：{analysis.get('body_type', '—')}  ·  "
                     f"目标头径：{analysis.get('head_diameter_cm', '—')} cm  ·  "
                     f"目标高度：{analysis.get('height_cm', '—')} cm  ·  "
                     f"难度：{difficulty_label(str(analysis.get('difficulty', '—')))}")
        lines.append("")
    # U24（升级）：密度是复现图解的第一要素（所有针数由它推导），
    # 必须随图解导出——缺失时给兜底声明并提示重新生成
    g = params.get("gauge") or {}
    st_g, rw_g = g.get("stitches_per_10cm"), g.get("rows_per_10cm")
    if st_g and rw_g:
        lines.append(f"> 密度（小样）：10cm × {st_g:g} 针 × {rw_g:g} 行——"
                     f"请先试钩核对，所有 cm 标注由它推导。"
                     f"若你的小样密度不同，请在侧栏改密度后重新生成")
        lines.append("")
    else:
        lines.append("> 密度（小样）：未记录（按经典图解默认 13 针 × 16 行 / 10cm）")
        lines.append("")
    from app.models.validator import shaping_policy_for_pattern
    shaping = shaping_policy_for_pattern(params)
    lines.append(
        f"> 塑形：当前密度的连续几何变化率约 "
        f"{shaping['continuous_delta']:.2f} 针/圈，按六等分针法向上量化为每圈 "
        f"±{shaping['max_stitch_change']} 针；较平缓轮廓仍可使用 6 针步长")
    lines.append("")
    physical_parts = sum(
        max(1, int(part.get("quantity", 1)))
        for part in params.get("parts", []))
    minutes = max(0, int(params.get("estimated_time_minutes") or 0))
    lines.append(
        f"> 工作量：{physical_parts} 个实体部件 · "
        f"{int(params.get('total_stitches') or 0):,} 针 · "
        f"基础操作估时 {minutes} 分钟（约 {minutes / 60:.1f} 小时）")
    lines.append(
        "> 工时是未校准的低置信度经验值，只按针数与实体圈次计算；"
        "不含缝合、填充、换色、刺绣、返工和休息")
    lines.append("")
    lines.append("---")

    # Materials
    lines.append(
        "> 记号：X=短针，V=加针（1针目钩2短针），A=减针（2针并1针）；"
        "(4X,V)×6 = “4短针+1加针”重复 6 次"
    )
    lines.append(">")
    lines.append(
        "> 钩法：螺旋钩（不引拔、不翻转），每圈第一针挂记号扣；"
        "减针建议用隐形减针（只挑两针目的前半针）"
    )
    lines.append(">")
    lines.append(_LEGEND_BILINGUAL)
    lines.append("")
    lines.append("## 🧵 所需材料")
    lines.append("")
    lines.append("> 克重/米数为估算值（请以实际线标为准）；品牌色号仅收录已核实条目")
    lines.append("")
    for mat in params.get("materials", []):
        # 与渲染层同口径：JSON 编辑器改坏材料（纯字符串/缺字段）时降级为
        # '?' 或原样输出，导出不崩溃
        if isinstance(mat, dict):
            lines.append(f"- **{_md_cell(mat.get('item', '?'))}**："
                         f"{_md_cell(mat.get('quantity', '?'))}")
        else:
            lines.append(f"- **{_md_cell(mat)}**")
    lines.append("")
    lines.append("---")

    # Each part
    for part in params.get("parts", []):
        pd = part
        n_rounds = len(pd.get("rounds", []))
        quantity = max(1, int(pd.get("quantity", 1)))
        qty_label = f" × {quantity} 个" if quantity > 1 else ""
        round_label = f"{n_rounds} 圈/个" if quantity > 1 else f"{n_rounds} 圈"
        lines.append(
            f"## 🧶 {_md_cell(pd.get('name', '?'))}{qty_label} ({round_label})")
        lines.append("")
        if quantity > 1:
            lines.append(f"- **制作数量**：{quantity} 个相同部件")
        lines.append(f"- **形状**：{pd.get('type', '—')}")
        lines.append(f"- **颜色**：{pd.get('color', '—')}")
        if pd.get("diameter_cm"):
            lines.append(f"- **直径**：{pd['diameter_cm']} cm")
        if pd.get("height_cm"):
            lines.append(f"- **高度/长度**：{pd['height_cm']} cm")
        if pd.get("magic_ring"):
            lines.append("- ✨ 魔法环起针")
        if pd.get("notes"):
            lines.append("\n> " + _md_cell(pd["notes"]))
        lines.append("")

        # Rounds table
        rounds = pd.get("rounds", [])
        if rounds:
            lines.append("| 圈数 | 针数 | 加针 | 减针 | 针法写法 | 配色 | 说明 |")
            lines.append("|:----:|:----:|:----:|:----:|:----:|:----:|------|")
            prev_st: int | None = None
            for r in rounds:
                rd = r
                try:
                    st_n = int(rd.get("stitches") or 0)
                    inc_n = int(rd.get("increase") or 0)
                    dec_n = int(rd.get("decrease") or 0)
                except (TypeError, ValueError):
                    st_n = inc_n = dec_n = 0
                inc = f"+{inc_n}" if inc_n else "—"
                dec = f"-{dec_n}" if dec_n else "—"
                # 专业写法列：聚合数翻译为图例约定的重复记号（均匀分组时）；
                # JSON 改坏/非均匀形态降级为 '—'
                rep = "—"
                if prev_st is not None and st_n and (inc_n or dec_n):
                    rep = _repeat_notation(st_n, prev_st, inc_n, dec_n) or "—"
                lines.append(
                    f"| {_md_cell(rd.get('row',''))} | {_md_cell(rd.get('stitches',''))} | "
                    f"{_md_cell(inc)} | {_md_cell(dec)} | {_md_cell(rep)} | "
                    f"{_md_cell(rd.get('color') or '—')} | "
                    f"{_md_cell(rd.get('notes', ''))} |")
                prev_st = st_n or None
        lines.append("")
        lines.append("---")

    # Assembly
    assembly = params.get("assembly_instructions", "")
    if assembly:
        lines.append("## 🔧 装配说明")
        lines.append("")
        for step in assembly.split("\n"):
            lines.append(step)
        lines.append("")

    lines.append("---")
    lines.append(f"*由 {PRODUCT_NAME} AI 自动生成 — 部分比例可能需要试钩调整*")
    return "\n".join(lines)
