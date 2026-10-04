"""Common source and verification labels for portable pattern exports."""
from typing import Any

from app import software_version


def provenance_lines(result: dict[str, Any] | None = None) -> list[str]:
    result = result or {}
    meta = result.get("vision_meta") or {}
    sizing = result.get("sizing") or {}
    source = str(meta.get("source") or "")
    label = {
        "mock": "Mock 演示数据（固定体型与部件，仅供体验流程）",
        "openai": "OpenAI 视觉解析",
        "anthropic": "Anthropic 视觉解析",
        "opencv-face": "本地视觉估算（人脸检测）",
        "default": "本地默认估算",
    }.get(source, "未记录")
    if not source and sizing.get("source") == "manual_dimensions":
        label = "手动输入"
    return [
        f"解析来源（记录值，未经独立认证）：{label}",
        f"尺寸来源：{sizing.get('source') or '未记录'}；厘米数值为目标尺寸，非照片实测",
        f"生成版本（记录值）：{result.get('generator_version') or '未记录'}；"
        f"导出软件版本：{software_version()}",
        "验证状态：仅通过针数代数自检；未验证实际可钩性、成品尺寸或材料用量，需试钩核对。",
    ]
