import logging
import re
from typing import Any, Dict, List

from ..schemas import PART_NAMES, ImageAnalysis
from .geometry import (
    AttachmentSpec,
    EulerRotation,
    NormalizedPosition,
    PartGeometry,
    PartInstance,
    StructureGeometry,
)

logger = logging.getLogger(__name__)


class StructureDesigner:
    """Map image semantics to editable-friendly primitive part specifications.

    This is a versioned template skeleton, not full 3D reconstruction.  Its
    normalized positions, rotations and anchors make assumptions explicit and
    editable, but they are not measurements recovered from a single photo.
    """

    _PART_IDS = {
        "头部": "head",
        "身体": "body",
        "手臂": "arms",
        "腿部": "legs",
        "尾巴": "tail",
        "耳朵": "ears",
        "帽子": "hat",
        "裙子": "skirt",
    }

    @staticmethod
    def _safe_part_id(name: str, index: int) -> str:
        known = StructureDesigner._PART_IDS.get(name)
        if known:
            return known
        slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
        return f"accessory_{slug or index + 1}"

    @staticmethod
    def _dimension(value: float) -> float:
        """Round template dimensions without allowing 0.0 at extreme ratios."""
        return max(0.1, round(value, 1))

    @staticmethod
    def _attachment(
        available: set,
        target: str,
        target_anchor: str,
        self_anchor: str,
        method: str = "sewn",
    ) -> List[AttachmentSpec]:
        """Return no edge rather than emitting a dangling graph reference."""
        if target not in available:
            return []
        return [AttachmentSpec(
            target_part_id=target,
            target_anchor=target_anchor,
            self_anchor=self_anchor,
            method=method,
        )]

    @staticmethod
    def _instances(part_id: str, available: set) -> Dict[str, Any]:
        """Template-space placement and attachment defaults for one logical part."""
        p = NormalizedPosition
        r = EulerRotation
        attach = StructureDesigner._attachment

        if part_id == "head":
            return {"instances": [PartInstance(
                instance_id="head",
                position=p(x=0.0, y=0.78, z=0.0),
                attachments=attach(available, "body", "top", "bottom"),
            )]}
        if part_id == "body":
            return {"instances": [PartInstance(
                instance_id="body", position=p(x=0.0, y=0.43, z=0.0),
            )]}
        if part_id in ("arms", "legs", "ears"):
            config = {
                "arms": (0.48, 0.52, 10.0, "body", "upper", "inner_end"),
                "legs": (0.20, 0.13, 4.0, "body", "bottom", "top"),
                "ears": (0.29, 0.91, 12.0, "head", "side", "base"),
            }[part_id]
            x, y, angle, target, target_anchor, self_anchor = config
            left_id, right_id = f"{part_id}_left", f"{part_id}_right"
            return {
                "count": 2,
                "mirror_group": part_id,
                "instances": [
                    PartInstance(
                        instance_id=left_id,
                        position=p(x=-x, y=y, z=0.0),
                        rotation_deg=r(z=angle),
                        attachments=attach(
                            available, target, f"{target_anchor}_left", self_anchor),
                    ),
                    PartInstance(
                        instance_id=right_id,
                        position=p(x=x, y=y, z=0.0),
                        rotation_deg=r(z=-angle),
                        mirror_of=left_id,
                        attachments=attach(
                            available, target, f"{target_anchor}_right", self_anchor),
                    ),
                ],
            }
        if part_id == "tail":
            return {"instances": [PartInstance(
                instance_id="tail",
                position=p(x=0.0, y=0.34, z=-0.45),
                rotation_deg=r(x=-20.0),
                attachments=attach(available, "body", "back", "base"),
            )]}
        if part_id == "hat":
            return {"instances": [PartInstance(
                instance_id="hat",
                position=p(x=0.0, y=0.94, z=0.0),
                attachments=attach(
                    available, "head", "top", "opening", method="worn"),
            )]}
        if part_id == "skirt":
            return {"instances": [PartInstance(
                instance_id="skirt",
                position=p(x=0.0, y=0.36, z=0.0),
                attachments=attach(
                    available, "body", "waist", "opening",
                    method="crocheted_or_sewn"),
            )]}
        return {"instances": [PartInstance(
            instance_id=part_id,
            position=p(x=0.0, y=0.50, z=0.45),
            attachments=attach(available, "body", "front", "base"),
        )]}

    @staticmethod
    def design_3d_structure(analysis: ImageAnalysis) -> Dict[str, Any]:
        """Convert image analysis to 3D part specifications.

        Maps each identified part to a basic 3D shape with
        proportions derived from the analysis.

        G4 口径说明：此处的 height_cm / diameter_cm 是**设计意图比例**
        （Q 版先验），不是最终交付尺寸——参数层 generate_params 会按
        gauge/塑形选项/照片剖面重新计算实际值。结构表展示的是设计骨架，
        与图解正文的数字不同属预期行为。
        """
        head_d = analysis.head_diameter_cm
        total_h = analysis.height_cm
        body_h = max(total_h - head_d, 0.1)  # protect against zero/negative

        dim = StructureDesigner._dimension
        shape_map = {
            "头部": {"shape": "sphere", "diameter_cm": head_d, "color": "skin"},
            "身体": {"shape": "cylinder", "height_cm": dim(body_h * 0.5), "color": "body"},
            "手臂": {"shape": "cylinder", "length_cm": dim(body_h * 0.35), "color": "skin"},
            "腿部": {"shape": "cylinder", "length_cm": dim(body_h * 0.4), "color": "skin"},
            "尾巴": {"shape": "cylinder", "length_cm": dim(body_h * 0.3), "color": "body"},
            "耳朵": {"shape": "sphere", "diameter_cm": dim(head_d * 0.35), "color": "skin"},
            # cup = 开口帽形：闭口球戴不进去；1.15× 松量避免帽围=头围卡死
            "帽子": {"shape": "cup", "diameter_cm": dim(head_d * 1.15), "color": "body"},
            "裙子": {"shape": "cup", "height_cm": dim(body_h * 0.25), "color": "body"},
        }
        # Unknown parts default to a small accessory sphere, not a body-sized tube
        default_part = {"shape": "sphere", "diameter_cm": dim(head_d * 0.4), "color": "body"}

        part_names = list(analysis.parts)

        # 语义服装：LLM 判定穿裙但 parts 漏了裙子 → 按身体比例补上
        if getattr(analysis, "clothing_type", None) in ("裙子", "连衣裙"):
            if "裙子" not in part_names:
                part_names.append("裙子")
                logger.info("Added 裙子 part from clothing_type=%s", analysis.clothing_type)

        part_ids = [StructureDesigner._safe_part_id(name, i)
                    for i, name in enumerate(part_names)]
        # Unknown names can normalize to the same slug; suffix only collisions so
        # attachments and backup validation still have stable unique identifiers.
        seen_ids: Dict[str, int] = {}
        for i, part_id in enumerate(part_ids):
            seen_ids[part_id] = seen_ids.get(part_id, 0) + 1
            if seen_ids[part_id] > 1:
                part_ids[i] = f"{part_id}_{seen_ids[part_id]}"
        available = set(part_ids)

        parts: List[PartGeometry] = []
        if len(part_names) != len(part_ids):
            raise RuntimeError("part identifier count does not match part names")
        for part_name, part_id in zip(part_names, part_ids):  # noqa: B905 - length checked above
            if part_name not in shape_map:
                # LLM 输出了规范名之外的部件（如"双手"）→ 降级为小球，
                # 记 warning 以便在日志中发现 prompt 约束失效。
                logger.warning(
                    "Unknown part %r (canonical: %s) — falling back to accessory sphere",
                    part_name, "、".join(PART_NAMES),
                )
            base = shape_map.get(part_name, default_part)
            parts.append(PartGeometry(
                part_id=part_id,
                name=part_name,
                **base,
                **StructureDesigner._instances(part_id, available),
            ))

        body_ratio = round(head_d / max(body_h * 0.5, 0.1), 1)
        return StructureGeometry(
            parts=parts,
            proportions=f"头部直径约为身体高度的 {body_ratio} 倍，Q 版卡通比例",
            notes=(
                "基于单图语义与模板先验；位置、旋转、背面深度和连接锚点"
                "不是照片实测值，生成前可人工确认"
            ),
        ).model_dump(exclude_none=True)
