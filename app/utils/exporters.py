"""Markdown export for generated crochet patterns."""
from __future__ import annotations


def export_markdown(params: dict, analysis: dict | None = None) -> str:
    """Convert crochet params dict to a printable Markdown pattern."""
    lines: list[str] = []
    lines.append("# 🧶 Amigurumi 钉织图解")
    lines.append("")
    if analysis:
        lines.append(f"> 体型：{analysis.get('body_type', '—')}  ·  "
                     f"头径：{analysis.get('head_diameter_cm', '—')} cm  ·  "
                     f"高度：{analysis.get('height_cm', '—')} cm  ·  "
                     f"难度：{analysis.get('difficulty', '—')}")
        lines.append("")
    lines.append("---")

    # Materials
    lines.append("## 🧵 所需材料")
    lines.append("")
    for mat in params.get("materials", []):
        lines.append(f"- **{mat['item']}**：{mat['quantity']}")
    lines.append("")
    lines.append("---")

    # Each part
    for part in params.get("parts", []):
        pd = part.model_dump() if hasattr(part, "model_dump") else part
        lines.append(f"## 🧶 {pd['name']} ({pd.get('rows', '?')} 圈)")
        lines.append("")
        lines.append(f"- **形状**：{pd.get('type', '—')}")
        lines.append(f"- **颜色**：{pd.get('color', '—')}")
        if pd.get("diameter_cm"):
            lines.append(f"- **直径**：{pd['diameter_cm']} cm")
        if pd.get("height_cm"):
            lines.append(f"- **高度/长度**：{pd['height_cm']} cm")
        if pd.get("magic_ring"):
            lines.append("- ✨ 魔法环起针")
        if pd.get("notes"):
            lines.append(f"\n> {pd['notes']}")
        lines.append("")

        # Rounds table
        rounds = pd.get("rounds", [])
        if rounds:
            lines.append("| 圈数 | 针数 | 加针 | 减针 | 说明 |")
            lines.append("|:----:|:----:|:----:|:----:|------|")
            for r in rounds:
                rd = r if isinstance(r, dict) else (r.model_dump() if hasattr(r, "model_dump") else {})
                inc = f"+{rd['increase']}" if rd.get("increase") else "—"
                dec = f"-{rd['decrease']}" if rd.get("decrease") else "—"
                lines.append(f"| {rd.get('row','')} | {rd.get('stitches','')} | "
                              f"{inc} | {dec} | {rd.get('notes', '')} |")
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
    lines.append("*由 Photo2Amigurumi AI 自动生成 — 部分比例可能需要试钩调整*")
    return "\n".join(lines)
