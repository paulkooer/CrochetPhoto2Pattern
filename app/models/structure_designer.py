import logging
from typing import Any, Dict, List

from ..schemas import PART_NAMES, ImageAnalysis

logger = logging.getLogger(__name__)


class StructureDesigner:
    """Design 3D structure from 2D image analysis."""

    @staticmethod
    def design_3d_structure(analysis: ImageAnalysis) -> Dict[str, Any]:
        """Convert image analysis to 3D part specifications.

        Maps each identified part to a basic 3D shape with
        proportions derived from the analysis.
        """
        head_d = analysis.head_diameter_cm
        total_h = analysis.height_cm
        body_h = max(total_h - head_d, 0.1)  # protect against zero/negative

        shape_map = {
            "头部": {"shape": "sphere", "diameter_cm": head_d, "color": "skin"},
            "身体": {"shape": "cylinder", "height_cm": round(body_h * 0.5, 1), "color": "body"},
            "手臂": {"shape": "cylinder", "length_cm": round(body_h * 0.35, 1), "color": "skin"},
            "腿部": {"shape": "cylinder", "length_cm": round(body_h * 0.4, 1), "color": "skin"},
            "尾巴": {"shape": "cylinder", "length_cm": round(body_h * 0.3, 1), "color": "body"},
            "耳朵": {"shape": "sphere", "diameter_cm": round(head_d * 0.35, 1), "color": "skin"},
            # cup = 开口帽形：闭口球戴不进去；1.15× 松量避免帽围=头围卡死
            "帽子": {"shape": "cup", "diameter_cm": round(head_d * 1.15, 1), "color": "body"},
            "裙子": {"shape": "cup", "height_cm": round(body_h * 0.25, 1), "color": "body"},
        }
        # Unknown parts default to a small accessory sphere, not a body-sized tube
        default_part = {"shape": "sphere", "diameter_cm": round(head_d * 0.4, 1), "color": "body"}

        parts: List[Dict[str, Any]] = []
        for part_name in analysis.parts:
            if part_name not in shape_map:
                # LLM 输出了规范名之外的部件（如"双手"）→ 降级为小球，
                # 记 warning 以便在日志中发现 prompt 约束失效。
                logger.warning(
                    "Unknown part %r (canonical: %s) — falling back to accessory sphere",
                    part_name, "、".join(PART_NAMES),
                )
            base = shape_map.get(part_name, default_part)
            parts.append({"name": part_name, **base})

        # 语义服装：LLM 判定穿裙但 parts 漏了裙子 → 按身体比例补上
        if getattr(analysis, "clothing_type", None) in ("裙子", "连衣裙"):
            if not any(p["name"] == "裙子" for p in parts):
                parts.append({"name": "裙子", **shape_map["裙子"]})
                logger.info("Added 裙子 part from clothing_type=%s", analysis.clothing_type)

        body_ratio = round(head_d / max(body_h * 0.5, 0.1), 1)
        return {
            "parts": parts,
            "proportions": f"头部直径约为身体高度的 {body_ratio} 倍，Q 版卡通比例",
            "notes": "基于单图推理，背面厚度用常识补充，存在一定不确定性",
        }
