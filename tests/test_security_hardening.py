"""独立审核修复的回归测试：上传格式白名单、Markdown 注入转义、照片衍生
数据外泄、历史缩略图校验。对应审核发现 F-02 / F-04 / F-05 / F-15。"""
from __future__ import annotations

import json
from io import BytesIO

import pytest
from PIL import Image

from app.schemas import strip_photo_derived
from app.utils import history
from app.utils.exporters import export_markdown
from app.utils.images import load_image_bytes
from app.utils.project import project_backup
from app.utils.share import decode_result, encode_result
from app.utils.trial_bundle import create_trial_bundle
from tests.test_app_smoke import _mock_result

_PREVIEW = "data:image/jpeg;base64,/9j/AAAQSkZJRg=="
_MASK = {"source": "user_brush", "image_token": "a" * 64, "width": 2, "height": 1, "pixels": "10"}


def _img_bytes(fmt: str) -> bytes:
    buf = BytesIO()
    Image.new("RGB", (8, 8), (180, 90, 40)).save(buf, format=fmt)
    return buf.getvalue()


# ── F-02：上传解码只接受 JPEG/PNG ──────────────────────────────────────
@pytest.mark.parametrize("fmt", ["PNG", "JPEG"])
def test_upload_accepts_jpeg_and_png(fmt):
    assert load_image_bytes(_img_bytes(fmt)) is not None


@pytest.mark.parametrize("fmt", ["TIFF", "BMP", "GIF"])
def test_upload_rejects_other_formats_even_with_image_bytes(fmt):
    # 即便是合法的 TIFF/BMP/GIF 图像字节，也不应进入对应解码器（收窄攻击面）。
    assert load_image_bytes(_img_bytes(fmt)) is None


# ── F-04：导出 Markdown 中和注入的链接/图片/HTML ────────────────────────
def _malicious_result() -> dict:
    result = _mock_result("sec-md")
    parts = result["params"]["parts"]
    parts[0]["name"] = "![x](http://beacon.example/p.png)"
    parts[0]["color"] = "[红](http://beacon.example/c)"
    result["analysis"]["parts"] = [p["name"] for p in parts]
    result["params"]["assembly_instructions"] = "缝合 <img src=http://beacon.example/a> 到身体"
    return result


def test_export_markdown_neutralizes_injection():
    md = export_markdown(None, None, result=_malicious_result())
    # 原始图片/链接/HTML 语法不得原样出现——方括号转义、尖括号 HTML 转义。
    assert "![x](http://beacon.example/p.png)" not in md
    assert "[红](http://beacon.example/c)" not in md
    assert "<img src=http://beacon.example/a>" not in md
    assert "\\[x\\]" in md  # 已转义的字面形式
    assert "&lt;img" in md


# ── F-05：照片衍生数据不随备份/分享/工程/试钩包外泄 ─────────────────────
def test_strip_photo_derived_removes_preview_and_mask_only():
    backup = {"preview": _PREVIEW, "params": {},
              "geometry": {"mask_review": dict(_MASK), "silhouette": {"ok": 1}}}
    cleaned = strip_photo_derived(backup)
    assert "preview" not in cleaned
    assert "mask_review" not in cleaned["geometry"]
    assert cleaned["geometry"]["silhouette"] == {"ok": 1}  # 非照片字段保留
    assert "preview" in backup and "mask_review" in backup["geometry"]  # 不改原对象


def _result_with_photo_data() -> dict:
    result = _mock_result("sec-leak")
    result["preview"] = _PREVIEW
    result["geometry"]["mask_review"] = dict(_MASK)
    return result


def test_share_token_excludes_photo_derived():
    token = encode_result(_result_with_photo_data())
    assert token is not None
    decoded = decode_result(token)
    assert decoded.get("preview") is None
    assert "mask_review" not in (decoded.get("geometry") or {})


def test_project_backup_excludes_photo_derived():
    backup = project_backup(_result_with_photo_data(), {}, "私人备注")
    blob = json.dumps(backup, ensure_ascii=False)
    assert "data:image/jpeg" not in blob
    assert "mask_review" not in blob
    assert backup.get("preview") is None


def test_trial_bundle_excludes_photo_derived():
    bundle = create_trial_bundle(_result_with_photo_data(), trial_id="sec-a", maker_id="maker-a")
    text = bundle.source.decode("utf-8")
    assert "data:image/jpeg" not in text
    assert "mask_review" not in text


def test_in_memory_result_keeps_photo_data_for_local_history():
    # 剔除只发生在导出边界——会话内结果与本机历史缩略图仍保留 preview。
    result = _result_with_photo_data()
    history.save_result(result)
    rows = history.list_results()
    assert any(r["preview"] == _PREVIEW for r in rows)


# ── F-15：历史缩略图字段只接受本机 JPEG data URL ────────────────────────
# 非字符串 preview 由 PatternResult 契约（preview: str|None）更早拦下并拒绝保存；
# 这里覆盖的是“合法字符串但非本机 JPEG data URL”的注入向量，由 _safe_preview 收口。
@pytest.mark.parametrize("bad", [
    "http://beacon.example/track.png",
    "javascript:alert(1)",
    "data:text/html,<img src=x>",
    "<img src=http://beacon.example/a>",
])
def test_history_rejects_non_jpeg_preview(bad):
    result = _mock_result("sec-preview")
    result["preview"] = bad
    history.save_result(result)
    rows = history.list_results()
    row = next(r for r in rows if r["rid"] == "sec-preview")
    assert row["preview"] is None
    restored = history.load_result("sec-preview")
    assert restored["preview"] is None


def test_history_keeps_valid_jpeg_preview():
    result = _mock_result("sec-preview-ok")
    result["preview"] = _PREVIEW
    history.save_result(result)
    assert history.load_result("sec-preview-ok")["preview"] == _PREVIEW
