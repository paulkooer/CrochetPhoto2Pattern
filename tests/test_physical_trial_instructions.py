"""Instructions must preserve usable construction order across generated exports."""
import pytest

from app.cli import build_parser, run
from app.models.stitches import AMIGURUMI_SWATCH_GUIDANCE, FINISHED_HEIGHT_GUIDANCE
from app.utils.exporters import export_markdown


@pytest.mark.parametrize("mode", ["ladder", "ideal", "egg"])
def test_head_workflow_uses_part_eye_round_before_stuffing(mode):
    result = run(build_parser().parse_args([
        "--head", "9", "--height", "22", "--sphere-mode", mode,
        "--parts", "头部,身体,耳朵",
    ]))
    head = next(p for p in result["params"]["parts"] if p["name"] == "头部")
    ears = next(p for p in result["params"]["parts"] if p["name"] == "耳朵")
    notes = head["notes"]
    assert notes.index("垫片") < notes.index("分次填充") < notes.index("按末圈说明收口")
    assert "第 1 圈为头顶" in notes
    assert "最后几圈前少量填棉" in ears["notes"]
    assembly = result["params"]["assembly_instructions"]
    assert "具体圈号" in assembly and "2/3" not in assembly
    assert assembly.index("安全眼") < assembly.index("分次填充")


@pytest.mark.parametrize("one_piece", [False, True])
def test_skirt_fit_precedes_stuffing_and_head_attachment(one_piece):
    result = run(build_parser().parse_args([
        "--head", "8", "--height", "20", "--parts", "头部,身体,手臂,腿部,裙子",
    ] + (["--one-piece"] if one_piece else [])))
    assembly = result["params"]["assembly_instructions"]
    assert assembly.index("独立裙筒先试套") < assembly.index("分次填充")
    if one_piece:
        assert "一体件在身体底端收口前从底端套入" in assembly
        assert "从颈口一端套入" not in assembly
    else:
        assert assembly.index("独立裙筒先试套") < assembly.index("头部接合到身体顶部")
    assert "过紧勿强拉" in assembly
    target = "一体件身体段" if one_piece else "身体"
    assert f"预先套入{target}的裙筒" in assembly


def test_both_print_formats_include_the_same_measurement_protocol(monkeypatch):
    pytest.importorskip("reportlab")
    from reportlab.platypus import Paragraph

    import app.utils.pdf_export as pdf_export

    result = run(build_parser().parse_args(["--head", "8", "--height", "20"]))
    markdown = export_markdown(result["params"], result=result)
    rendered = []

    def capture(text, *args, **kwargs):
        rendered.append(text)
        return Paragraph(text, *args, **kwargs)

    monkeypatch.setattr("reportlab.platypus.Paragraph", capture)
    pdf = pdf_export.export_pdf(result["params"], result=result)
    assert pdf.startswith(b"%PDF")
    for guidance in (AMIGURUMI_SWATCH_GUIDANCE, FINISHED_HEIGHT_GUIDANCE):
        assert guidance in markdown and guidance in rendered
    assert "**目标直径**：8.0 cm" in markdown
    assert "换算直径约 7.3cm" in markdown
    purchase_lines = [m["item"] for m in result["params"]["materials"] if "钩针" in m["item"]]
    assert purchase_lines and all("CYC" not in line for line in purchase_lines)
