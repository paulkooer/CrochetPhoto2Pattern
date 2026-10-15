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
    lines = [
        f"解析来源（记录值，未经独立认证）：{label}",
        f"尺寸来源：{sizing.get('source') or '未记录'}；厘米数值为目标尺寸，非照片实测",
        f"生成版本（记录值）：{result.get('generator_version') or '未记录'}；"
        f"导出软件版本：{software_version()}",
        "验证状态：仅通过针数代数自检；未验证实际可钩性、成品尺寸或材料用量，需试钩核对。",
        "说明检查：仅拦截可识别的针数矛盾；自由文字和自定义工艺仍需人工复核。",
    ]

    if meta.get("requires_subject_review"):
        lines.append("主体复核：尚未确认主体类型、头部与部件；当前部件来自默认模板，不能视为照片识别结果。")
    elif meta.get("subject_scope_review"):
        lines.append("主体复核：用户已确认单个可表达主体及部件；并非自动识别准确性的验证。")
    if (result.get("geometry") or {}).get("body_region"):
        lines.append("身体轮廓来源：用户框选区域内的主体掩码；不是自动部件识别，未做实物校准。")
    if (result.get("geometry") or {}).get("mask_review"):
        lines.append("主体掩码已由用户补选／擦除，轮廓与配色使用修正后的选区；部件仍需人工确认。")
    if meta.get("color_observation"):
        from app.models.color_observation import ColorObservation

        observation = ColorObservation.model_validate(meta["color_observation"])
        if observation.requires_review:
            lines.append("局部配色待复核：照片中存在横向并列颜色；当前图解仅生成整圈配色，"
                         "局部斑块尚未转成圈内换色或附着装饰，不应按整圈颜色直接复刻。")
    return lines
