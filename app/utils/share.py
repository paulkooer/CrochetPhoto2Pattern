"""分享链接（U8）——结果压缩进 URL query 参数，无服务器分享。

方案：zlib 压缩 + base64url 编码进 `?p=`。图解 JSON 体积差异大，
超过 URL 实用长度（~6000 字符）时返回 None，调用方提示改用备份文件。
恢复时做与备份导入同级的校验（analysis 过 pydantic、structure 形状）。
"""
from __future__ import annotations

import base64
import json
import zlib
from typing import Any

from ..schemas import RESULT_KEYS, SCHEMA_VERSION, PatternResult

_MAX_TOKEN_CHARS = 6000
# 解压后 2MB 上限（F29）。按字节计：blob 已 UTF-8 编码，zlib 的
# max_length 与 len(unpacked) 都以字节为单位。
_MAX_DECOMPRESSED_BYTES = 2 << 20


# F24/F26/F27 根因修复：结果 dict 的顶层键集此前在 6 条路径（生成/
# 备份/导入/分享/调尺寸/存历史）各自手抄——谁抄漏谁丢数据（F24 备份
# 丢九键、F26 调尺寸丢 preview）。现在键集从 PatternResult（schemas.py）
# 单一契约派生，新增顶层键改模型字段即可：
# - _BACKUP_KEYS：备份文件/历史 blob 的完整键集（含 preview）；
# - _SHARE_KEYS：分享 token 键集 = 备份键集 − preview（6000 门控，
#   preview 仅供本机历史缩略图）。
# 键集相等断言见 tests/test_key_sets.py。
_BACKUP_KEYS = RESULT_KEYS
_SHARE_KEYS = tuple(k for k in _BACKUP_KEYS if k != "preview")


def encode_result(result: dict[str, Any]) -> str | None:
    """结果 → 分享 token；过大返回 None。

    序列化走 PatternResult：pydantic 部件对象自动 dump，schema_version
    随 token 下发供未来版本识别。
    """
    payload = PatternResult.from_result(result).to_backup()
    payload.pop("preview", None)
    blob = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    if len(blob) > _MAX_DECOMPRESSED_BYTES:
        return None
    token = base64.urlsafe_b64encode(zlib.compress(blob, 9)).decode()
    if len(token) > _MAX_TOKEN_CHARS:
        return None
    return token


def decode_result(token: str) -> dict[str, Any] | None:
    """token → 结果 dict；格式/校验失败返回 None（导入侧再深度校验）。

    F29：decode 端与 encode 端对称门控——token 长度上限 + zlib 解压
    上限，防压缩放大的内存尖峰；同时要求完整的单一 zlib 流，
    避免截断、缺失校验和或尾随数据被当成有效分享。
    """
    if not token or len(token) > _MAX_TOKEN_CHARS:
        return None
    try:
        raw = base64.b64decode(token.encode(), altchars=b"-_", validate=True)
        decoder = zlib.decompressobj()
        unpacked = decoder.decompress(raw, _MAX_DECOMPRESSED_BYTES + 1)
        if (len(unpacked) > _MAX_DECOMPRESSED_BYTES or not decoder.eof
                or decoder.unused_data or decoder.unconsumed_tail):
            return None
        blob = unpacked.decode("utf-8", errors="strict")
        data = json.loads(blob)
        if not isinstance(data, dict) or not all(
                isinstance(data.get(k), dict) for k in ("analysis", "structure", "params")):
            return None
        # 未来 schema 版本的结果不猜测兼容性；旧 token（无版本键）
        # 保留兼容，缺 V4 新键时由渲染层默认值兜底。
        version = data.get("schema_version")
        if version is not None and version != SCHEMA_VERSION:
            return None
        return data
    except Exception:
        return None
