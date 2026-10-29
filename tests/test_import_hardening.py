"""导入/校验加固回归测试：分享解码严格解析、旧格式结构非法字段、圈号
乱序、跨部件圈数总量上限。对应审核发现 F-06 / F-07。"""
from __future__ import annotations

import base64
import zlib

import pytest

from app.models.geometry import normalize_structure
from app.models.validator import validate_pattern
from app.schemas import MAX_TOTAL_ROUNDS
from app.utils.backup import loads_strict
from app.utils.share import decode_result, encode_result
from tests.test_app_smoke import _mock_result


def _token(blob: str) -> str:
    return base64.urlsafe_b64encode(zlib.compress(blob.encode("utf-8"), 9)).decode()


def _rounds(n: int) -> list[dict]:
    return [{"row": r, "stitches": 6, "notes": "魔法环起6针（X×6）" if r == 1 else "6X"}
            for r in range(1, n + 1)]


# ── F-06a：分享解码与备份同口径，拒绝 NaN/Infinity 与重复键 ──────────────
def test_loads_strict_rejects_nan_and_duplicate_keys():
    with pytest.raises(ValueError):
        loads_strict('{"a": NaN}')
    with pytest.raises(ValueError):
        loads_strict('{"a": 1, "a": 2}')
    assert loads_strict('{"a": 1}') == {"a": 1}


def test_share_decode_rejects_nan():
    blob = '{"analysis": {"x": NaN}, "structure": {"parts": []}, "params": {}}'
    assert decode_result(_token(blob)) is None


def test_share_decode_rejects_duplicate_keys():
    blob = '{"analysis": {}, "analysis": {}, "structure": {"parts": []}, "params": {}}'
    assert decode_result(_token(blob)) is None


def test_share_round_trip_still_works():
    token = encode_result(_mock_result("share-ok"))
    assert token is not None
    decoded = decode_result(token)
    assert decoded is not None and "params" in decoded


# ── F-06b：旧格式结构的展示字段必须是标量（否则渲染层 dict 键查找崩溃）──
def test_legacy_structure_rejects_non_scalar_shape():
    bad = {"parts": [{"name": "头部", "shape": {"evil": 1}}]}
    with pytest.raises(ValueError, match="shape"):
        normalize_structure(bad)


def test_legacy_structure_rejects_list_color():
    bad = {"parts": [{"name": "头部", "color": ["红", "蓝"]}]}
    with pytest.raises(ValueError, match="color"):
        normalize_structure(bad)


def test_legacy_structure_accepts_scalar_fields():
    ok = {"parts": [{"name": "头部", "shape": "sphere", "color": "红色", "diameter_cm": 9}]}
    out = normalize_structure(ok)
    assert out["parts"][0]["shape"] == "sphere"


# 注：圈号「递增」未作强制。插入/重排圈的编辑会产生非递增但唯一的标签，
# 进度按位置标识跟踪而非圈号（见 test_edit_impact），应允许其往返保存；
# 重复圈号仍被拒（唯一性由 validate_pattern 与 CrochetPart 双重保证）。
def test_validator_still_rejects_duplicate_row_labels():
    params = {"parts": [{"name": "头部", "color": "红色",
                         "rounds": [{"row": 1, "stitches": 6}, {"row": 1, "stitches": 6}]}]}
    assert not validate_pattern(params, check_notes=False)["ok"]


# ── F-07：跨部件圈数总量上限 ────────────────────────────────────────────
def test_validator_rejects_total_rounds_over_aggregate_cap():
    # 32 件 × 600 圈 = 19,200 > 16,000；单件与部件数都在各自上限内。
    parts = [{"name": f"p{i}", "color": "白色", "rounds": _rounds(600)} for i in range(32)]
    result = validate_pattern({"parts": parts}, check_notes=False)
    assert not result["ok"]
    assert any("总量上限" in issue for issue in result["issues"])


def test_validator_accepts_realistic_total_rounds():
    parts = [{"name": f"p{i}", "color": "白色", "rounds": _rounds(200)} for i in range(10)]
    assert validate_pattern({"parts": parts}, check_notes=False)["ok"]
    assert MAX_TOTAL_ROUNDS > 10 * 200
