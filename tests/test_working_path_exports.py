"""The demonstrator exports its real scope and never overwrites review evidence."""
import json

import pytest

from app.models.working_path import armhole_path_demo
from app.utils.working_path_export import (
    CHECK_SCOPE,
    export_working_path_markdown,
    export_working_path_pdf,
)
from app.working_paths import main, write_demo


def test_explanation_distinguishes_held_sites_chain_faces_and_unverified_physical_work():
    text = export_working_path_markdown(armhole_path_demo())
    assert "已有织片上人工声明的 28" in text
    assert "反面工作位第 1–3 位（反向）" in text
    assert "body_edge`：22" in text
    assert "left_sleeve`：9" in text
    assert "不能当作" in text and "闭合接头" in text and "跨圈外钩" in text
    assert "两个工作位不代表锁了两针" in text
    assert CHECK_SCOPE in text and "已建模" in CHECK_SCOPE and "几何" in CHECK_SCOPE


def test_optional_pdf_contains_explanation_without_claiming_a_finished_garment(monkeypatch):
    pytest.importorskip("reportlab")
    from reportlab.platypus import Paragraph

    captured = []
    init = Paragraph.__init__

    def record(self, text, *args, **kwargs):
        if text is not None:
            captured.append(text)
        init(self, text, *args, **kwargs)

    monkeypatch.setattr(Paragraph, "__init__", record)
    pdf = export_working_path_pdf(armhole_path_demo())
    assert pdf.startswith(b"%PDF-")
    text = " ".join(captured)
    assert "工序校验演示" in text and "实体试钩" in text and "不是完整衣物图解" in text
    assert "反面工作位" in text and "body_edge" in text
    assert CHECK_SCOPE in text


def test_cli_outputs_round_trip_and_keep_existing_evidence(tmp_path, capsys):
    target = tmp_path / "demo"
    assert main(["--out-dir", str(target)]) == 0
    data = json.loads((target / "path-plan.json").read_text())
    assert data == armhole_path_demo().model_dump()
    result = json.loads((target / "path-result.json").read_text())
    assert result["physical_execution_verified"] is False
    assert {key: len(sites) for key, sites in result["final_edges"].items()} == {
        "body_edge": 22, "left_sleeve": 9, "right_sleeve": 9,
    }
    before = {p.name: p.read_bytes() for p in target.iterdir()}
    with pytest.raises(SystemExit) as error:
        main(["--out-dir", str(target)])
    assert error.value.code == 2
    assert {p.name: p.read_bytes() for p in target.iterdir()} == before
    assert "不会覆盖" in capsys.readouterr().err


def test_optional_pdf_failure_does_not_write_partial_evidence(tmp_path, monkeypatch):
    def fail(plan):
        raise ValueError("PDF unavailable")

    monkeypatch.setattr("app.working_paths.export_working_path_pdf", fail)
    with pytest.raises(ValueError, match="PDF unavailable"):
        write_demo(tmp_path / "not_created", pdf=True)
    assert not (tmp_path / "not_created").exists()


def test_exports_reject_corrupt_route_rather_than_printing_it():
    plan = armhole_path_demo()
    plan.steps[0].expected_sites = 20
    with pytest.raises(ValueError, match="实际 22"):
        export_working_path_markdown(plan)
    with pytest.raises(ValueError, match="实际 22"):
        export_working_path_pdf(plan)
