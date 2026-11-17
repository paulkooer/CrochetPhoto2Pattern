import json
from copy import deepcopy

import pytest

from app.doll_cli import build_parser, read_design, run
from app.models.dressed_doll import DollDesign, build_doll_plan, starter_design
from app.utils.dressed_doll_export import (
    export_doll_graph,
    export_doll_markdown,
    export_doll_pdf,
    foundation_text,
    step_groups,
)


def test_exports_keep_rows_rounds_foundations_and_assembly_distinct():
    plan = build_doll_plan(DollDesign())
    md = export_doll_markdown(plan)
    assert "未实钩验证" in md and "不是照片自动识别" in md
    assert "翻转锁针不计入本行针数" in md
    assert "锁针另一侧" in md and "鞋头收窄" in md
    assert "| 行 |" in md and "| 圈 |" in md
    assert "袖窿" in md and "包袋背带" in md and "发帽底座" in md
    graph = export_doll_graph(plan)
    assert "hair -> hair_cap" in graph and "shoes -> legs" in graph and "head -> body" in graph
    for part in plan.components:
        expanded = [n for group in step_groups(part) for n in range(group.first, group.last + 1)]
        assert expanded == list(range(1, len(part.steps) + 1))


def test_pdf_and_markdown_share_foundations_and_every_component(monkeypatch):
    pytest.importorskip("reportlab")
    from reportlab.platypus import Paragraph

    plan = build_doll_plan(starter_design("folded_cap_layers"))
    texts = []

    def capture(text, *args, **kwargs):
        texts.append(text)
        return Paragraph(text, *args, **kwargs)

    monkeypatch.setattr("reportlab.platypus.Paragraph", capture)
    data = export_doll_pdf(plan)
    assert data.startswith(b"%PDF")
    for part in plan.components:
        assert any(part.name in text for text in texts)
        assert foundation_text(part) in texts
    assert any("未实钩验证" in text for text in texts)


def test_free_text_cannot_inject_markdown_images_or_html():
    plan = build_doll_plan(DollDesign())
    data = plan.model_dump()
    data["components"][0]["name"] = '<img src="x">![remote](https://example.com/x)'
    from app.models.dressed_doll import DollPlan

    md = export_doll_markdown(DollPlan.model_validate(data))
    assert '<img src="x">' not in md and "![remote]" not in md


def test_cli_roundtrip_and_existing_destinations_are_preserved(tmp_path):
    root = tmp_path / "generated"
    args = build_parser().parse_args(["--starter", "wide_brim_curls", "--out-dir", str(root)])
    summary = run(args)
    assert summary["status"] == "unverified_prototype"
    raw = (root / "design.json").read_bytes()
    assert read_design(raw) == starter_design("wide_brim_curls")
    first = {p.name: p.read_bytes() for p in root.iterdir()}
    with pytest.raises(ValueError, match="已存在"):
        run(args)
    assert first == {p.name: p.read_bytes() for p in root.iterdir()}
    args = build_parser().parse_args(["--design", str(root / "design.json"),
                                     "--out-dir", str(tmp_path / "reopened")])
    run(args)
    assert (root / "plan.json").read_bytes() == (tmp_path / "reopened/plan.json").read_bytes()


def test_failed_optional_pdf_leaves_no_partial_output(tmp_path, monkeypatch):
    def missing(_plan):
        raise ImportError("pdf missing")

    monkeypatch.setattr("app.doll_cli.export_doll_pdf", missing)
    root = tmp_path / "no-output"
    args = build_parser().parse_args(["--starter", "wide_brim_curls", "--out-dir", str(root), "--pdf"])
    with pytest.raises(ImportError):
        run(args)
    assert not root.exists()


@pytest.mark.parametrize("raw", [b'{"height_cm":24,"height_cm":30}', b'{"height_cm":NaN}',
                                 b'{"height_cm":true}', b"[]", b"\xff"])
def test_design_input_rejects_ambiguous_or_nonfinite_json(raw):
    with pytest.raises(ValueError):
        read_design(raw)


def test_design_input_is_bounded_and_does_not_accept_a_plan_as_a_design():
    with pytest.raises(ValueError, match="512"):
        read_design(b" " * (512 * 1024 + 1))
    with pytest.raises(ValueError):
        read_design(build_doll_plan(DollDesign()).model_dump_json().encode())
    with pytest.raises(ValueError):
        read_design(b"[" * 5000 + b"0" + b"]" * 5000)


def test_explicit_design_does_not_silently_take_starter_overrides(tmp_path):
    source = tmp_path / "input.json"
    source.write_text(json.dumps(DollDesign().model_dump()))
    args = build_parser().parse_args(["--design", str(source), "--height", "30",
                                     "--out-dir", str(tmp_path / "output")])
    before = deepcopy(source.read_bytes())
    with pytest.raises(ValueError, match="明确修改"):
        run(args)
    assert source.read_bytes() == before and not (tmp_path / "output").exists()
