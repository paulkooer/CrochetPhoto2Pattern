"""Parade 导出计数的忠实口径：DSL 圈次 ≠ 忠实完整导出的实体。

修复（2026-11-04）：生成头部、身体、独立裙筒三件时，
``export_parade_report`` 曾报 ``exported_parts=3 / requested_parts=3``，
而裙筒的环形起针被换成了 ``ring`` + ``sc36inc``——开口圆筒变闭合圆片，
语义不符。按 ``exported_parts`` 自己的定义（只计忠实完整的实体）它不该计入。

两个计数器回答不同问题，必须分开：
- ``exported_rounds``：实际写进 DSL 文本的圈次，含构造语义不符的部件；
- ``exported_parts``：忠实且完整翻译的实体份数；构造语义不符（环形/锁针
  起针）或翻译提前中断的实体都不计入。

修复只收紧 ``exported_parts``，不删警告、不改门槛：声明的不支持构造仍使
``complete=False``（严格完整率照旧计入），仍走 ``unsupported_constructions``
（评测的 ``parade_export_rate`` 依旧不把它当导出失败）。
"""
from __future__ import annotations

from copy import deepcopy

from app.utils.parade_export import export_parade_report, lint_parade_dsl

_RING_START_NOTE = "腰部环形起针36X成环（引拔连接，开口勿收口）"


def _faithful(name: str = "头部", quantity: int = 1) -> dict:
    """魔法环起针、逐圈可译的部件。"""
    return {"name": name, "quantity": quantity, "magic_ring": True, "color": "肤色",
            "rounds": [{"row": 1, "stitches": 6, "notes": "魔法环起6针（X×6）"},
                       {"row": 2, "stitches": 6, "notes": "6X"}]}


def _ring_start(name: str = "裙子", quantity: int = 1) -> dict:
    """非魔法环起针（开口筒）：DSL 里只能近似成闭合圆盘。"""
    return {"name": name, "quantity": quantity, "magic_ring": False, "color": "红色",
            "rounds": [{"row": 1, "stitches": 36, "notes": _RING_START_NOTE},
                       {"row": 2, "stitches": 36, "notes": "36X"}]}


def _report(parts: list[dict]):
    return export_parade_report({"params": {"parts": parts}})


def test_reported_reproduction_counts_two_faithful_parts_out_of_three():
    """头部 + 身体 + 独立裙筒：完整实体只有 2，不是 3。"""
    head, body = _faithful("头部"), _faithful("身体")
    body["rounds"][1]["notes"] = "6X"
    report = _report([head, body, _ring_start()])
    assert not report.complete
    assert (report.exported_parts, report.requested_parts) == (2, 3)
    assert report.unsupported_constructions == [{"part": "裙子", "construction": "ring_start"}]
    # 不是导出失败：策略 v3 把已声明不支持的构造单列，门槛不受影响。
    assert report.failures == []
    assert lint_parade_dsl(report.text) == []


def test_ring_start_still_emits_rounds_and_keeps_its_warning():
    """收紧的是计数，不是文案：圈次照旧生成，警告照旧保留。"""
    report = _report([_ring_start()])
    assert not report.complete
    assert (report.exported_parts, report.requested_parts) == (0, 1)
    # 两个计数器回答不同问题：DSL 圈次确实生成了。
    assert (report.exported_rounds, report.requested_rounds) == (2, 2)
    assert any("首圈非魔法环" in warning for warning in report.warnings)
    assert "已标记为不完整" in report.text
    # 近似的 DSL 仍在文本里，供对照原说明人工核对；不得静默声称完整。
    code = [line for line in report.text.splitlines()
            if line and not line.startswith(("#", "COLOR:"))]
    assert code[0] == "ring" and code[1] == "sc36inc"


def test_mixed_parts_count_only_faithful_copies():
    report = _report([_faithful("头部"), _ring_start(), _faithful("手臂", quantity=2)])
    assert not report.complete
    assert (report.exported_parts, report.requested_parts) == (3, 4)
    assert (report.exported_rounds, report.requested_rounds) == (8, 8)


def test_multi_copy_unsupported_part_reports_one_gap_and_count_no_copies():
    """一份图解多份实体共享同一构造缺口：登记一次，实体计数按份作废。"""
    report = _report([_ring_start(quantity=2)])
    assert (report.exported_parts, report.requested_parts) == (0, 2)
    assert report.unsupported_constructions == [{"part": "裙子", "construction": "ring_start"}]
    assert sum("首圈非魔法环" in warning for warning in report.warnings) == 1
    # 每份实体的圈次仍各自生成。
    assert (report.exported_rounds, report.requested_rounds) == (4, 4)
    assert report.text.count("start_anew") == 1


def test_unsupported_construction_and_translation_failure_are_reported_together():
    broken = _faithful("身体")
    broken["rounds"][1] = {"row": 2, "stitches": 12, "increase": 6, "notes": "(V×6"}
    report = _report([_ring_start(), broken])
    assert not report.complete
    assert report.unsupported_constructions == [{"part": "裙子", "construction": "ring_start"}]
    assert report.failures
    assert "该圈及后续圈已跳过" in report.text
    assert (report.exported_parts, report.requested_parts) == (0, 2)
    # 裙筒 2 圈 + 身体只译出魔法环 1 圈（第 2 圈中断）＝ 3 圈实际写进文本
    assert (report.exported_rounds, report.requested_rounds) == (3, 4)


def test_truncated_translation_never_counts_the_copy_as_complete():
    """翻译中断的部件早已不计入；这条把它和环起口径一起钉住。"""
    truncated = _faithful()
    truncated["rounds"][1] = {"row": 2, "stitches": 12, "increase": 6, "notes": "(V×6"}
    report = _report([truncated])
    assert (report.exported_parts, report.requested_parts) == (0, 1)
    assert (report.exported_rounds, report.requested_rounds) == (1, 2)
    assert report.unsupported_constructions == []


def test_export_cache_version_tracks_the_changed_report_semantics():
    """计数口径变了，缓存指纹必须跟着变，否则旧报告会被复用。"""
    from app.ui.export_cache import EXPORT_CACHE_VERSION

    assert EXPORT_CACHE_VERSION >= 17


def test_counting_does_not_mutate_the_result():
    parts = [_faithful("头部"), _ring_start()]
    original = deepcopy(parts)
    _report(parts)
    assert parts == original
