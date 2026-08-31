"""授权真实图片评测门禁（CROCHET_EVAL_DIR 存在时才运行）。"""
import json
import os
from pathlib import Path

import pytest

_EVAL_DIR = os.getenv("CROCHET_EVAL_DIR")
pytestmark = pytest.mark.skipif(
    not _EVAL_DIR or not Path(_EVAL_DIR).is_dir(),
    reason="未设置 CROCHET_EVAL_DIR（真实图片评测集本地目录）")


def test_real_images_meet_baseline():
    """版本化清单、逐图证据与聚合阈值必须同时通过。"""
    from app.evaluation import evaluate_dataset, write_evaluation_report

    report = evaluate_dataset(_EVAL_DIR)
    output = os.getenv("CROCHET_EVAL_REPORT")
    if output:
        write_evaluation_report(report, output)
    failures = [case for case in report["cases"] if not case["passed"]]
    assert report["summary"]["passed"], json.dumps(
        {"summary": report["summary"], "failed_cases": failures},
        ensure_ascii=False,
        indent=2,
    )
