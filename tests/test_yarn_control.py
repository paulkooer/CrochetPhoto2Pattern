"""Control the hook loop separately from the reusable-site inventory."""
import pytest

from app.models.working_path import (
    FastenOff,
    FinishEdge,
    FoundationChain,
    FreeLoops,
    Hold,
    NewYarn,
    ParkYarn,
    ResumeYarn,
    Route,
    Seam,
    Span,
    WeaveEnds,
    Work,
    WorkingPath,
    compile_working_path,
)
from app.utils.working_path_export import export_working_path_markdown


def _flat():
    return WorkingPath(title="显式用线练习", yarn_tracking=True, steps=[
        NewYarn(id="start", label="另起工作线", yarn="main", method="foundation_chain", side="RS"),
        FoundationChain(id="chain", label="起链", chains=4, work_face="underside", other_face="top"),
        Route(id="row", label="首行", mode="flat", side="RS", row_direction="forward", expected_sites=3,
              operations=[Work(source=Span(edge="chain", first=1, last=3, face="underside"))]),
        Hold(id="outside", label="起链外侧", spans=[Span(edge="chain", first=1, last=3)]),
    ], final_edges=["row", "outside"])


def _end():
    return FastenOff(id="end", label="收线", yarn="main", source=Span(edge="row", first=3, last=3),
                     tail_cm=15.0)


def test_fasten_and_weave_have_explicit_instructions_without_consuming_the_border():
    plan = _flat()
    baseline = compile_working_path(plan)
    plan.steps += [_end(), WeaveEnds(id="weave", label="藏线", yarn="main", ends="both")]
    result = compile_working_path(plan)
    assert result.created_sites == baseline.created_sites == 9
    assert result.consumed_sites == baseline.consumed_sites == 3
    assert result.final_edges == baseline.final_edges
    assert result.yarn_accounting["all_fasten_off_steps_present"] is True
    assert result.yarn_accounting["all_weave_steps_present"] is True
    assert result.to_dict()["physical_execution_verified"] is False
    assert {e.yarn_id for e in result.events if e.role == "working"} == {"main"}
    text = export_working_path_markdown(plan)
    assert "15cm尾线" in text and "分向穿藏" in text


def test_a_closed_site_inventory_is_not_a_fasten_off():
    plan = _flat()
    plan.steps += [
        FinishEdge(id="border", label="声明留边", source=Span(edge="row", first=1, last=3),
                   reason="finished_border"),
        FinishEdge(id="chain_border", label="起链外侧留边", source=Span(edge="outside", first=1, last=3),
                   reason="unused_chain_face"),
    ]
    plan.final_edges = []
    result = compile_working_path(plan)
    assert result.created_sites == result.consumed_sites
    assert result.yarn_accounting["all_fasten_off_steps_present"] is False
    plan.steps.append(_end())
    assert compile_working_path(plan).yarn_accounting["all_fasten_off_steps_present"] is True


def test_fasten_off_must_be_at_the_active_loop_and_cannot_happen_twice():
    plan = _flat()
    wrong = _end()
    wrong.source = Span(edge="row", first=1, last=1)
    plan.steps.append(wrong)
    with pytest.raises(ValueError, match="当前位置|当前工作环"):
        compile_working_path(plan)
    plan.steps[-1] = _end()
    duplicate = _end()
    duplicate.id = "end_again"
    plan.steps.append(duplicate)
    with pytest.raises(ValueError, match="当前已有"):
        compile_working_path(plan)


def test_weaving_an_uncut_end_or_declaring_the_same_end_twice_is_rejected():
    plan = _flat()
    plan.steps.append(WeaveEnds(id="weave", label="提前藏线", yarn="main", ends="both"))
    with pytest.raises(ValueError, match="尚未断线"):
        compile_working_path(plan)
    plan.steps[-1] = _end()
    plan.steps += [WeaveEnds(id="weave", label="藏线", yarn="main", ends="starting"),
                   WeaveEnds(id="repeat", label="重复", yarn="main", ends="both")]
    with pytest.raises(ValueError, match="重复登记"):
        compile_working_path(plan)


def test_pause_resume_preserves_loop_and_only_the_remaining_end_is_woven():
    plan = _flat()
    plan.steps += [
        WeaveEnds(id="weave_start", label="起线端", yarn="main", ends="starting"),
        ParkYarn(id="park", label="暂停", yarn="main", source=Span(edge="row", first=3, last=3)),
    ]
    assert compile_working_path(plan).yarn_accounting["segments"]["main"]["declared_status"] == "parked"
    plan.steps += [ResumeYarn(id="resume", label="恢复", yarn="main"), _end(),
                   WeaveEnds(id="weave_end", label="结束端", yarn="main", ends="finishing")]
    assert compile_working_path(plan).yarn_accounting["all_weave_steps_present"] is True


def test_new_yarn_cannot_silently_replace_a_working_loop():
    plan = _flat()
    plan.steps.append(NewYarn(id="other", label="另接", yarn="other", method="standing_sc", side="RS",
                              anchor=Span(edge="row", first=1, last=1)))
    with pytest.raises(ValueError, match="收掉或暂停"):
        compile_working_path(plan)


def test_a_standing_start_must_use_its_declared_anchor():
    plan = _flat()
    plan.steps += [_end(), NewYarn(id="new", label="另接", yarn="other", method="standing_sc", side="RS",
                                 anchor=Span(edge="row", first=1, last=1)),
                   Route(id="wrong", label="错误位置", expected_sites=1,
                         operations=[Work(source=Span(edge="row", first=2, last=2), stitch="standing_sc")])]
    with pytest.raises(ValueError, match="声明位置"):
        compile_working_path(plan)


def test_declared_sides_are_checked_even_when_section_names_change():
    plan = _flat()
    plan.steps.append(Route(id="next", label="没有翻面却改变朝向", mode="flat", side="WS",
                            row_direction="reverse", expected_sites=3,
                            operations=[Work(source=Span(edge="row", first=1, last=3, direction="reverse"))]))
    with pytest.raises(ValueError, match="朝向"):
        compile_working_path(plan)


def test_seam_cannot_start_from_the_far_end_of_the_last_row():
    plan = _flat()
    row = next(s for s in plan.steps if s.id == "row")
    row.turn = "counterclockwise"
    plan.steps += [
        Route(id="last", label="末行", mode="flat", side="WS", row_direction="reverse", expected_sites=3,
              operations=[Work(source=Span(edge="row", first=1, last=3, direction="reverse"), loop="back")]),
        FreeLoops(id="lip", label="首行预留", source=Span(edge="row", first=1, last=3), loop="front"),
        Seam(id="seam", label="接合", left=Span(edge="last", first=1, last=3),
             right=Span(edge="lip", first=1, last=3, direction="reverse")),
    ]
    plan.final_edges = ["outside"]
    with pytest.raises(ValueError, match="当前工作环一端"):
        compile_working_path(plan)
    plan.steps[-1].left.direction = "reverse"
    plan.steps[-1].right.direction = "forward"
    compile_working_path(plan)


def test_legacy_paths_are_marked_untracked_and_cannot_claim_yarn_checks():
    plan = _flat()
    plan.yarn_tracking = False
    with pytest.raises(ValueError, match="须启用"):
        compile_working_path(plan)
    plan.steps.pop(0)
    result = compile_working_path(plan)
    assert result.yarn_accounting["mode"] == "legacy_untracked"
    assert result.yarn_accounting["all_fasten_off_steps_present"] is False
