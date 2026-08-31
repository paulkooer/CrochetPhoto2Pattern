"""分享链接（U8）——结果压缩进 URL query 参数，无服务器分享。

方案：zlib 压缩 + base64url 编码进 `?p=`。图解 JSON 体积差异大，
超过 URL 实用长度（~6000 字符）时返回 None，调用方提示改用备份文件。
恢复时做与备份导入同级的校验（analysis 过 pydantic、structure 形状）。
"""
from __future__ import annotations

import base64
import json
import zlib
from typing import Any, Dict, Optional

_MAX_TOKEN_CHARS = 6000
_MAX_DECOMPRESSED_CHARS = 2 << 20  # 解压后 2MB 上限（F29）


# F24/F26/F27 根因修复：结果 dict 的顶层键集此前在 6 条路径（生成/
# 备份/导入/分享/调尺寸/存历史）各自手抄——谁抄漏谁丢数据（F24 备份
# 丢九键、F26 调尺寸丢 preview）。此处为单一事实来源：
# - _BACKUP_KEYS：备份文件/历史 blob 的完整键集（含 preview）；
# - _SHARE_KEYS：分享 token 键集 = 备份键集 − preview（6000 门控，
#   preview 仅供本机历史缩略图）。
# 新增 result 顶层键时必须改这里，键集相等断言见
# tests/test_round16.py::test_result_key_sets_consistent。
_BACKUP_KEYS = ("analysis", "structure", "params", "style", "gauge",
                "color_bands", "spans", "spans_measured", "vision_meta",
                "preview", "usage", "sizing", "geometry")
_SHARE_KEYS = tuple(k for k in _BACKUP_KEYS if k != "preview")


def encode_result(result: Dict[str, Any]) -> Optional[str]:
    """结果 → 分享 token；过大返回 None。"""
    payload = {k: result.get(k) for k in _SHARE_KEYS}
    blob = json.dumps(payload, ensure_ascii=False,
                      default=lambda o: (o.model_dump()
                                         if hasattr(o, "model_dump") else str(o)))
    token = base64.urlsafe_b64encode(zlib.compress(blob.encode("utf-8"), 9)).decode()
    if len(token) > _MAX_TOKEN_CHARS:
        return None
    return token


def decode_result(token: str) -> Optional[Dict[str, Any]]:
    """token → 结果 dict；格式/校验失败返回 None（导入侧再深度校验）。

    F29：decode 端与 encode 端对称门控——token 长度上限 + zlib 解压
    上限（decompressobj.decompress(data, max_length) 在 3.9 可用），
    防 ~770× 压缩放大的内存尖峰；超限截断后 json.loads 必然失败，
    走既有 except 兜底。
    """
    if not token or len(token) > _MAX_TOKEN_CHARS:
        return None
    try:
        raw = base64.urlsafe_b64decode(token.encode())
        blob = zlib.decompressobj().decompress(
            raw, _MAX_DECOMPRESSED_CHARS).decode("utf-8", errors="strict")
        data = json.loads(blob)
        if not all(k in data for k in ("analysis", "structure", "params")):
            return None
        # 旧 token 兼容：缺 V4 新键时由渲染层默认值兜底（不拒绝）
        return data
    except Exception:
        return None
