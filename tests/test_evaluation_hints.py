"""Hints are scored separately from the runner's actual delivered parts."""
import hashlib
import json

from app.evaluation import evaluate_dataset
from tests.test_evaluation import _case, _manifest, _valid_result, _write_image
from tests.test_local_vision import _person


def test_review_hint_precision_recall_and_unavailable_cases(tmp_path):
    cases = []
    examples = [
        (["头部", "耳朵", "尾巴"], {"possible_ears": True, "possible_tail": False,
                                    "possible_skirt": False}),
        (["头部"], {"possible_ears": True, "possible_tail": False, "possible_skirt": True}),
        (["头部", "耳朵", "裙子"], {"possible_ears": False, "possible_tail": False,
                                    "possible_skirt": True}),
        (["头部", "耳朵"], {"possible_ears": "false"}),  # Non-boolean flags are unavailable.
        (["头部"], None),  # A pipeline failure must not become a negative hint.
    ]
    for index, (parts, _) in enumerate(examples):
        name = f"{index}.png"
        digest = _write_image(tmp_path / name, (index, 100, 200))
        cases.append(_case(str(index), name, digest, parts))
    (tmp_path / "eval_manifest.json").write_text(json.dumps(_manifest(cases)), encoding="utf-8")

    def run(image):
        index = image.getpixel((0, 0))[0]
        meta = examples[index][1]
        if meta is None:
            raise RuntimeError("synthetic failure")
        result = _valid_result(["头部"], [], flare=False)
        result["vision_meta"] = meta
        return result

    report = evaluate_dataset(tmp_path, runner=run)
    hints = report["summary"]["review_hint_metrics"]
    assert hints["耳朵"] == {
        "observed_cases": 3, "unavailable_cases": 2,
        "true_positives": 1, "false_positives": 1, "false_negatives": 1,
        "precision": 0.5, "recall": 0.5,
    }
    assert hints["裙子"]["precision"] == 0.5
    assert hints["裙子"]["recall"] == 1.0
    assert hints["尾巴"]["precision"] is None
    assert hints["尾巴"]["recall"] == 0.0
    assert report["cases"][3]["review_hints"] == {"耳朵": None, "裙子": None, "尾巴": None}
    assert report["cases"][4]["error"]["type"] == "RuntimeError"
    assert report["cases"][4]["review_hints"] == {"耳朵": None, "裙子": None, "尾巴": None}


def test_evaluator_does_not_infer_delivery_from_custom_runner_hints(tmp_path):
    digest = _write_image(tmp_path / "one.png", (1, 2, 3))
    case = _case("one", "one.png", digest, ["头部", "耳朵"], flare=False, colors=["蓝色"])
    (tmp_path / "eval_manifest.json").write_text(json.dumps(_manifest([case])), encoding="utf-8")

    def run(hint):
        def runner(_image):
            result = _valid_result(["头部"], ["蓝色"], flare=False)
            result["vision_meta"] = {"possible_ears": hint}
            return result
        return evaluate_dataset(tmp_path, runner=runner, release=True)

    with_hint, without_hint = run(True), run(False)
    assert with_hint["cases"][0]["actual_parts"] == without_hint["cases"][0]["actual_parts"] == ["头部"]
    assert with_hint["release_readiness"] == without_hint["release_readiness"]
    assert with_hint["summary"]["passed"] == without_hint["summary"]["passed"]
    assert with_hint["summary"]["review_hint_metrics"]["耳朵"]["recall"] == 1.0
    assert without_hint["summary"]["review_hint_metrics"]["耳朵"]["recall"] == 0.0


def test_default_automatic_runner_can_exceed_the_fixed_template(tmp_path, monkeypatch):
    """A synthetic skirt exercises actual delivery, not a hint counted as delivery."""
    monkeypatch.setattr("app.models.local_vision._detect_face", lambda _img: None)
    monkeypatch.setattr("app.models.pose.get_body_landmarks", lambda _img: None)
    image_path = tmp_path / "dress.png"
    _person(dress=True).save(image_path)
    digest = hashlib.sha256(image_path.read_bytes()).hexdigest()
    expected = ["头部", "身体", "手臂", "腿部", "裙子"]
    case = _case("dress", "dress.png", digest, expected, flare=True)
    (tmp_path / "eval_manifest.json").write_text(json.dumps(_manifest([case])), encoding="utf-8")

    report = evaluate_dataset(tmp_path)
    assert report["evaluator"]["part_selection"] == "automatic_contour_candidates"
    assert report["cases"][0]["actual_parts"] == sorted(expected)
    assert report["cases"][0]["delivery_consistent"] is True
    assert report["summary"]["macro_part_f1"] == 1.0
    assert report["release_readiness"]["quality_metrics"]["fixed_template_macro_f1"] < 1.0
    # One synthetic image is not release evidence, regardless of its F1.
    assert report["release_readiness"]["automated_passed"] is False
