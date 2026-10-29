"""G4 设计指纹回归测试：同一设计重复生成（或仅改配色/线材/诊断）不得被
误计为多个独立图解。对应审核发现 F-03。"""
from __future__ import annotations

import copy
from datetime import date

from app.trials import TrialRecord, _design_fingerprint, analyze_trials
from app.utils.trial_bundle import create_trial_bundle
from tests.test_app_smoke import _mock_result


def _completed(bundle, i, cohort):
    rec = bundle.record.model_dump(mode="json")
    rec["status"] = "completed"
    rec["swatch"]["measured"] = True
    rec["observation"] = {
        "completed_on": date.today().isoformat(),
        "overall_height_cm": 18.0 + i * 0.1,
        "yarn_used_grams": 60.0 + i,
        "active_minutes": rec["pattern"]["estimated_time_minutes"],
        "time_scope": "round_crochet_baseline",
        "pattern_modified": False,
    }
    rec["cohort"] = cohort
    return TrialRecord.model_validate(rec)


def test_fingerprint_ignores_non_structural_fields():
    base = _mock_result("fp")["params"]
    same = copy.deepcopy(base)
    # 改配色与首圈 notes 文案不改结构 → 同一指纹
    same["parts"][0]["color"] = "完全不同的颜色"
    same["parts"][0]["rounds"][0]["notes"] = "随便改改说明"
    assert _design_fingerprint(base) == _design_fingerprint(same)
    # 改某圈针数 → 不同指纹
    changed = copy.deepcopy(base)
    changed["parts"][0]["rounds"][-1]["stitches"] += 6
    assert _design_fingerprint(changed) != _design_fingerprint(base)


def test_same_design_regenerated_shares_fingerprint_not_byte_hash():
    result = _mock_result("fp-a")
    variant = copy.deepcopy(result)
    variant["diagnostics"] = {"timings": {"total_ms": 999}}  # 诊断耗时不同
    b1 = create_trial_bundle(result, trial_id="t-1", maker_id="maker-a")
    b2 = create_trial_bundle(variant, trial_id="t-2", maker_id="maker-b")
    assert b1.record.pattern.sha256 != b2.record.pattern.sha256      # 字节哈希不同
    assert b1.record.pattern.design_fingerprint is not None
    assert b1.record.pattern.design_fingerprint == b2.record.pattern.design_fingerprint


def test_gate_counts_repeated_single_design_as_one():
    result = _mock_result("fp-gate")
    records = []
    for i in range(5):
        variant = copy.deepcopy(result)
        variant["diagnostics"] = {"timings": {"total_ms": i}}  # 每次“重新生成”诊断不同
        bundle = create_trial_bundle(variant, trial_id=f"t-{i}", maker_id=f"maker-{'ab'[i % 2]}")
        records.append(_completed(bundle, i, "calibration"))
    report = analyze_trials(records)
    summary = report["summary"]
    assert summary["calibration_eligible"] == 5
    # 同一设计重复生成 → 仅 1 个不同图解 → 达不到 MIN_DISTINCT_PATTERNS
    assert summary["distinct_patterns"] == 1
    assert summary["calibration_ready"] is False
    # 同一设计跨校准/验证队列 → 队列哈希不再互斥（防自证独立）
    cross = [
        _completed(
            create_trial_bundle(copy.deepcopy(result), trial_id=f"v-{i}",
                                maker_id=f"maker-{'ab'[i % 2]}", cohort="validation"),
            i, "validation")
        for i in range(3)
    ]
    overlap_report = analyze_trials(records + cross)
    assert overlap_report["independent_validation"]["cohort_pattern_hashes_disjoint"] is False
