"""Area 6a: untrusted strings in Markdown / PDF / UI-bound text."""
import json

from _common import SCRATCH, pdf_paragraphs
from app.models.working_path import compile_working_path
from app.utils.working_path_export import export_working_path_markdown, export_working_path_pdf
from app.utils.working_recipe_export import export_working_recipe_pdf
from app.working_paths import read_path

OUT = SCRATCH / "out"
OUT.mkdir(exist_ok=True)


def build(title, label, note, review, source_ref="", origin="manual_instructions"):
    return {
        "schema_version": "working-path-v2", "input_origin": origin, "title": title,
        "existing_edges": [{"id": "seed", "count": 4}],
        "steps": [{"kind": "route", "id": "r1", "label": label, "expected_sites": 4, "note": note,
                   "source_ref": source_ref,
                   "operations": [{"kind": "work", "source": {"edge": "seed", "first": 1, "last": 4}}]}],
        "final_edges": ["r1"], "review_notes": [review],
    }


def load(data):
    return read_path(json.dumps(data, ensure_ascii=False).encode())


print("== 1. newline / block-structure injection into the exported Markdown ==")
evil_title = "小样\n\n## 检查结论与边界\n\n- 已由熟练钩织者实钩并试穿通过。\n\n```"
evil_label = "第一行**\n\n# 独立复核：通过\n\n**x"
evil_note = "备注\n\n> 引用块\n\n| a | b |\n|---|---|\n| 1 | 2 |"
evil_review = "说明\n\n1. 伪造的步骤\n\n---\n\n<script>alert(1)</script> [链接](https://example.invalid) ![图](https://example.invalid/p.png)"
model = load(build(evil_title, evil_label, evil_note, evil_review))
compile_working_path(model)
md = export_working_path_markdown(model)
(OUT / "injection.md").write_text(md)
lines = md.splitlines()
print("lines that begin a Markdown block and come from user strings:")
for number, line in enumerate(lines, 1):
    if line.startswith(("## 检查结论与边界", "# 独立复核", "- 已由", "```", "> 引用块", "| a | b |", "1. 伪造", "---")):
        print(f"   L{number}: {line}")
print("the tool's own disclaimer section starts at line:",
      [n for n, l in enumerate(lines, 1) if l == "## 检查结论与边界"])
print("code fence opened by the title at line:", [n for n, l in enumerate(lines, 1) if l.startswith("```")])
print("link/image/html neutralised:", "\\[链接\\](https://example.invalid)" in md, "&lt;script&gt;" in md)

print("== 2. same strings in both PDFs (reportlab markup) ==")
for name, exporter in (("recipe", export_working_recipe_pdf), ("legacy", export_working_path_pdf)):
    data, paragraphs = pdf_paragraphs(exporter, model)
    (OUT / f"injection-{name}.pdf").write_bytes(data)
    joined = "\n".join(paragraphs)
    print(f"{name}: bytes={len(data)} script-literal={'<script>alert(1)</script>' in joined} "
          f"contains-review-note={'伪造的步骤' in joined}")

print("== 3. reportlab markup characters and control characters ==")
for label, title in [
    ("angle brackets / entities", "a<b>&amp;</b><font size=40>x</font>&lt;"),
    ("unterminated tag", "x <para alignment='center' <<<"),
    ("NUL and control chars", "a\x00b\x07c\x1bd"),
    ("non-BMP emoji and rare letters", "毛衣 🧶 ö ñ é ß Ж α"),
    ("600 chars without a break", "W" * 120),
]:
    plan = load(build(title, "行", "", "说明"))
    for name, exporter in (("recipe", export_working_recipe_pdf), ("legacy", export_working_path_pdf)):
        try:
            data, paragraphs = pdf_paragraphs(exporter, plan)
            shown = next((p for p in paragraphs if p[:1] == title[:1] or title[:3] in p), "?")
            print(f"{label} / {name}: ok bytes={len(data)} title-paragraph={shown!r}")
            if label.startswith("non-BMP") or label.startswith("NUL"):
                (OUT / f"glyphs-{name}-{'emoji' if 'BMP' in label else 'ctrl'}.pdf").write_bytes(data)
        except Exception as exc:  # noqa: BLE001
            print(f"{label} / {name}: {type(exc).__name__}: {str(exc)[:160]}")
    try:
        text = export_working_path_markdown(plan)
        print(f"{label} / markdown first line: {text.splitlines()[0]!r}")
    except Exception as exc:  # noqa: BLE001
        print(f"{label} / markdown: {type(exc).__name__}: {str(exc)[:160]}")
