from typing import Dict, List

from ..schemas import ImageAnalysis


class StructureDesigner:
    """Design 3D structure from 2D image analysis."""

    @staticmethod
    def design_3d_structure(analysis: ImageAnalysis) -> Dict:
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
            "帽子": {"shape": "sphere", "diameter_cm": round(head_d * 1.05, 1), "color": "body"},
            "裙子": {"shape": "cylinder", "height_cm": round(body_h * 0.25, 1), "color": "body"},
        }
        # Unknown parts default to a small accessory sphere, not a body-sized tube
        default_part = {"shape": "sphere", "diameter_cm": round(head_d * 0.4, 1), "color": "body"}

        parts: List[Dict] = []
        for part_name in analysis.parts:
            base = shape_map.get(part_name, default_part)
            parts.append({"name": part_name, **base})

        body_ratio = round(head_d / (body_h * 0.5), 1)
        return {
            "parts": parts,
            "proportions": f"头部直径约为身体高度的 {body_ratio} 倍，Q 版卡通比例",
            "notes": "基于单图推理，背面厚度用常识补充，存在一定不确定性",
        }
