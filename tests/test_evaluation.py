import hashlib
import json
from pathlib import Path

import pytest
from PIL import Image

from app.evaluation import (
    EvaluationDatasetError,
    evaluate_dataset,
    load_evaluation_dataset,
    main,
)


def _write_image(path: Path, color: tuple[int, int, int]) -> str:
    Image.new("RGB", (32, 48), color).save(path)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _manifest(cases, **dataset_overrides):
    dataset = {
        "name": "authorized-private-smoke",
        "version": "1",
        "rights_basis": "self_owned",
        "evaluation_use_approved": True,
        "contains_personal_data": False,
        "retention_policy": "Delete source images after the evaluation cycle.",
    }
    dataset.update(dataset_overrides)
    return {
        "schema_version": 1,
        "dataset": dataset,
        "thresholds": {
            "min_cases": 2,
            "min_case_part_recall": 0.5,
            "min_macro_part_f1": 0.6,
            "min_case_pass_rate": 0.8,
            "min_flare_accuracy": 0.8,
            "min_color_top3_accuracy": 0.8,
            "min_pattern_valid_rate": 1.0,
        },
        "cases": cases,
    }


def _case(case_id, filename, digest, parts, *, flare=None, colors=None, tags=None):
    return {
        "id": case_id,
        "file": filename,
        "sha256": digest,
        "tags": tags or ["test-fixture"],
        "expected": {
            "parts": parts,
            "flare": flare,
            "dominant_colors": colors or [],
        },
    }


def _valid_result(parts, colors, *, flare):
    structure_parts = [{"name": name} for name in parts if name != "裙子"]
    if flare:
        structure_parts.append({"name": "裙子"})
    return {
        "analysis": {"parts": parts, "recommended_colors": colors},
        "structure": {"parts": structure_parts},
        "params": {
            "parts": [{
                "name": "头部",
                "rounds": [{"row": 1, "stitches": 6, "increase": 0, "decrease": 0}],
            }]
        },
    }


def test_evaluation_aggregates_frozen_cases(tmp_path):
    blue_hash = _write_image(tmp_path / "blue.png", (0, 120, 215))
    red_hash = _write_image(tmp_path / "red.png", (220, 50, 50))
    cases = [
        _case("blue-doll", "blue.png", blue_hash, ["头部", "身体"], flare=False, colors=["蓝色"]),
        _case(
            "red-skirt",
            "red.png",
            red_hash,
            ["头部", "身体", "裙子"],
            flare=True,
            colors=["暗红色"],
        ),
    ]
    (tmp_path / "eval_manifest.json").write_text(
        json.dumps(_manifest(cases), ensure_ascii=False), encoding="utf-8"
    )

    def runner(image):
        if image.getpixel((0, 0))[2] > image.getpixel((0, 0))[0]:
            return _valid_result(["头部", "身体"], ["蓝色"], flare=False)
        return _valid_result(["头部", "身体", "裙子"], ["暗红色"], flare=True)

    report = evaluate_dataset(tmp_path, runner=runner)
    assert report["evaluator"]["network_images_sent"] is False
    assert report["summary"] == {
        "cases": 2,
        "tag_counts": {"test-fixture": 2},
        "pipeline_errors": 0,
        "macro_part_f1": 1.0,
        "case_pass_rate": 1.0,
        "flare_labeled_cases": 2,
        "flare_accuracy": 1.0,
        "color_labeled_cases": 2,
        "color_top3_accuracy": 1.0,
        "pattern_valid_rate": 1.0,
        "passed": True,
    }
    assert all(case["passed"] for case in report["cases"])


def test_hash_mismatch_stops_before_pipeline(tmp_path):
    _write_image(tmp_path / "photo.png", (255, 255, 255))
    case = _case("changed", "photo.png", "0" * 64, ["头部"])
    (tmp_path / "eval_manifest.json").write_text(
        json.dumps(_manifest([case]), ensure_ascii=False), encoding="utf-8"
    )
    with pytest.raises(EvaluationDatasetError, match="sha256 mismatch"):
        load_evaluation_dataset(tmp_path)


def test_corrupt_image_is_a_dataset_error(tmp_path):
    image_path = tmp_path / "broken.png"
    image_path.write_bytes(b"not-an-image")
    digest = hashlib.sha256(image_path.read_bytes()).hexdigest()
    case = _case("broken-image", "broken.png", digest, ["头部"])
    (tmp_path / "eval_manifest.json").write_text(
        json.dumps(_manifest([case]), ensure_ascii=False), encoding="utf-8"
    )
    with pytest.raises(EvaluationDatasetError, match="unable to decode image"):
        load_evaluation_dataset(tmp_path)


@pytest.mark.parametrize(
    "mutation, message",
    [
        (lambda payload: payload["dataset"].update(evaluation_use_approved=False),
         "evaluation_use_approved"),
        (lambda payload: payload["cases"][0].update(file="../outside.png"),
         "relative path"),
        (lambda payload: payload["cases"][0]["expected"].update(parts=["双手"]),
         "unknown canonical parts"),
    ],
)
def test_manifest_rejects_unsafe_or_ambiguous_contract(tmp_path, mutation, message):
    digest = _write_image(tmp_path / "photo.png", (255, 255, 255))
    payload = _manifest([_case("case-1", "photo.png", digest, ["头部"])])
    mutation(payload)
    (tmp_path / "eval_manifest.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )
    with pytest.raises(EvaluationDatasetError, match=message):
        load_evaluation_dataset(tmp_path)


def test_pipeline_error_is_reported_and_fails_gate(tmp_path):
    digest = _write_image(tmp_path / "photo.png", (255, 255, 255))
    case = _case("broken", "photo.png", digest, ["头部"], colors=["白色"])
    (tmp_path / "eval_manifest.json").write_text(
        json.dumps(_manifest([case]), ensure_ascii=False), encoding="utf-8"
    )

    def broken_runner(_image):
        raise RuntimeError("controlled failure")

    report = evaluate_dataset(tmp_path, runner=broken_runner)
    assert report["summary"]["pipeline_errors"] == 1
    assert report["summary"]["passed"] is False
    assert report["cases"][0]["error"] == {
        "type": "RuntimeError",
        "message": "controlled failure",
    }


def test_default_evaluator_runs_complete_local_pipeline(tmp_path):
    digest = _write_image(tmp_path / "photo.png", (245, 245, 245))
    case = _case("local-pipeline", "photo.png", digest, ["头部", "身体", "手臂", "腿部"])
    payload = _manifest([case])
    payload["thresholds"]["min_cases"] = 1
    (tmp_path / "eval_manifest.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )

    report = evaluate_dataset(tmp_path)
    assert report["evaluator"]["mode"] == "local_vision"
    assert report["evaluator"]["network_images_sent"] is False
    assert report["summary"]["pipeline_errors"] == 0
    assert report["summary"]["pattern_valid_rate"] == 1.0
    assert report["cases"][0]["error"] is None


def test_cli_exit_code_reflects_quality_gate(tmp_path, monkeypatch):
    report = {"summary": {"cases": 1, "macro_part_f1": 0.0, "case_pass_rate": 0.0,
                          "passed": False}}
    monkeypatch.setattr("app.evaluation.evaluate_dataset", lambda _dataset: report)
    output = tmp_path / "report.json"
    assert main(["--dataset", "unused", "--out", str(output)]) == 2
    assert json.loads(output.read_text(encoding="utf-8")) == report
    assert main(["--dataset", "unused", "--out", str(output), "--allow-fail"]) == 0
