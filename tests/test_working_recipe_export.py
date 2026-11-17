"""Readable rows retain actual anchors, attachments, control order and uncertainty."""
import json

import pytest

from app.models.working_path import (
    ExistingEdge,
    FinishEdge,
    FoundationChain,
    Route,
    Span,
    Work,
    WorkingPath,
    armhole_path_demo,
    compile_working_path,
)
from app.utils.working_recipe_export import export_working_recipe_pdf, recipe_rows, route_formula
from app.working_paths import MAX_PLAN_BYTES, main, read_path


def _plan():
    return WorkingPath(title="独立的小衣片", input_origin="manual_instructions",
                       review_notes=["尺寸尚未实测"], steps=[
        FoundationChain(id="chain", label="起链", chains=4, work_face="underside", other_face="top"),
        Route(id="first", label="衣片 第 1 行", section="panel", row_number=1,
              mode="flat", side="RS", row_direction="forward", turn="counterclockwise", turning_chains=1,
              expected_sites=3,
              operations=[Work(source=Span(edge="chain", first=1, last=3, face="underside"))]),
        Route(id="second", label="衣片 第 2 行", section="panel", row_number=2,
              mode="flat", side="WS", row_direction="reverse", expected_sites=3,
              operations=[Work(source=Span(edge="first", first=1, last=3, direction="reverse"))]),
        FinishEdge(id="unused", label="起链留边", source=Span(edge="chain", first=1, last=3),
                   reason="unused_chain_face"),
    ], final_edges=["second"])


def test_recipes_show_single_crochets_and_binding_slips_as_different_instructions():
    row = Route(id="rib", label="练习", expected_sites=3, operations=[
        Work(source=Span(edge="a", first=1, last=3), loop="back"),
        Work(source=Span(edge="b", first=5, last=6), stitch="slst", disposition="binding"),
    ])
    formula, binding = route_formula(row)
    assert formula == "3X-BLO"
    assert "2引拔" in binding and "b第5–6位" in binding
    assert "2SL" not in formula


def test_nonprevious_sources_are_not_silently_printed_as_ordinary_next_rows():
    plan = _plan()
    rows = recipe_rows([plan.steps[1], plan.steps[2]], {})
    assert "chain第1–3位" in rows[0].controls
    assert rows[0].formula == "3X（里山）"
    assert rows[1].formula == "3X"


def test_missing_row_numbers_and_wrong_reverse_work_are_rejected():
    data = _plan().model_dump()
    data["steps"][2]["row_number"] = 3
    with pytest.raises(ValueError, match="漏行"):
        compile_working_path(WorkingPath.model_validate(data))
    data["steps"][2]["row_number"] = 2
    data["steps"][2]["operations"][0]["source"]["direction"] = "forward"
    with pytest.raises(ValueError, match="反向工作"):
        compile_working_path(WorkingPath.model_validate(data))


def test_pdf_retains_review_notes_real_stitch_counts_and_does_not_invent_missing_gauge(monkeypatch):
    pytest.importorskip("reportlab")
    from reportlab.platypus import Paragraph

    captured = []
    init = Paragraph.__init__

    def record(self, text, *args, **kwargs):
        if isinstance(text, str):
            captured.append(text)
        init(self, text, *args, **kwargs)

    monkeypatch.setattr(Paragraph, "__init__", record)
    pdf = export_working_recipe_pdf(_plan())
    assert pdf.startswith(b"%PDF-")
    text = " ".join(captured)
    assert "尺寸尚未实测" in text and "未实钩" in text and "未填" in text
    assert "里山" in text and "行" in text and "工作针位包含锁针桥" in text


def test_cli_reads_manual_paths_without_replacing_them_with_the_demo(tmp_path):
    source = tmp_path/"source.json"
    source.write_text(_plan().model_dump_json())
    out = tmp_path/"result"
    assert main(["--plan", str(source), "--out-dir", str(out)]) == 0
    saved = json.loads((out/"path-result.json").read_text())
    assert saved["plan"]["title"] == "独立的小衣片"
    assert len(saved["final_edges"]["second"]) == 3
    assert saved["physical_execution_verified"] is False


@pytest.mark.parametrize("raw", [b'{"title":"a","title":"b"}', b'{"x":NaN}', b'\xff',
                                  b' '*(MAX_PLAN_BYTES+1)])
def test_plan_reader_rejects_duplicate_nonfinite_invalid_utf8_and_oversized_input(raw):
    with pytest.raises(ValueError):
        read_path(raw)


def test_invalid_import_writes_no_partial_outputs(tmp_path):
    source = tmp_path/"bad.json"
    source.write_text('{"schema_version":"invented"}')
    out = tmp_path/"result"
    with pytest.raises(SystemExit) as error:
        main(["--plan", str(source), "--out-dir", str(out)])
    assert error.value.code == 2 and not out.exists()


def test_reserved_row_ends_cannot_be_taken_twice_by_two_borders():
    from app.models.working_path import RowEdges, RowEnd

    plan = WorkingPath(title="行端复用", existing_edges=[ExistingEdge(id="seed", count=2)], steps=[
        Route(id="row", label="片钩行", mode="flat", side="RS", row_direction="forward", expected_sites=2,
              operations=[Work(source=Span(edge="seed", first=1, last=2))]),
        RowEdges(id="side_a", label="边A", rows=[RowEnd(row="row", side="left")]),
        Route(id="worked", label="挑一次", expected_sites=1,
              operations=[Work(source=Span(edge="side_a", first=1, last=1))]),
        RowEdges(id="side_b", label="边B", rows=[RowEnd(row="row", side="left")]),
    ], final_edges=["row", "worked"])
    with pytest.raises(ValueError, match="已使用"):
        compile_working_path(plan)


def test_oversized_pdf_layout_is_reported_as_an_export_failure(monkeypatch):
    pytest.importorskip("reportlab")
    from reportlab.platypus import SimpleDocTemplate
    from reportlab.platypus.doctemplate import LayoutError

    def fail(*args, **kwargs):
        raise LayoutError("too tall")

    monkeypatch.setattr(SimpleDocTemplate, "build", fail)
    with pytest.raises(ValueError, match="Markdown"):
        export_working_recipe_pdf(_plan())


def test_alias_working_edges_do_not_hide_chain_undersides_in_printed_instructions():
    data = armhole_path_demo().model_dump()
    for operation in data["steps"][0]["operations"]:
        if operation["kind"] == "chain":
            operation["route_face"] = "underside"
    for hold in data["steps"][1:3]:
        hold["spans"][1]["face"] = "top"
    data["steps"].append({"kind": "route", "id": "next_body", "label": "沿衣身继续", "expected_sites": 22,
                          "operations": [{"kind": "work", "source": {"edge": "body_edge", "first": 1,
                                                                     "last": 22}}]})
    data["final_edges"][0] = "next_body"
    result = compile_working_path(WorkingPath.model_validate(data))
    row = result.plan.steps[-1]
    assert route_formula(row, events=result.events)[0] == "4X，3X（里山），8X，3X（里山），4X"
    from app.utils.working_path_export import export_working_path_markdown

    assert "3X（里山）" in export_working_path_markdown(result.plan)


def test_alias_opening_corners_are_printed_as_pickups_instead_of_an_undifferentiated_sc_run():
    data = armhole_path_demo().model_dump()
    for operation in data["steps"][0]["operations"]:
        if operation["kind"] == "chain":
            operation["corner_sites"] = True
    for hold_index, route_index, bridge in [(1, 3, "left_bridge"), (2, 4, "right_bridge")]:
        data["steps"][hold_index]["spans"] += [
            {"edge": bridge, "first": 1, "last": 1, "face": "corner_start"},
            {"edge": bridge, "first": 1, "last": 1, "face": "corner_end"},
        ]
        data["steps"][route_index]["expected_sites"] = 11
        data["steps"][route_index]["operations"][0]["source"]["last"] = 11
    result = compile_working_path(WorkingPath.model_validate(data))
    row = next(step for step in result.plan.steps if step.id == "left_sleeve")
    assert route_formula(row, events=result.events)[0] == "6X，3X（里山），2X（转角）"
    with pytest.raises(ValueError, match="事件"):
        route_formula(row, events=[])
