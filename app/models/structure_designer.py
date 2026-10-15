import logging
from typing import Any, Literal

from ..schemas import PART_LABELS_ZH, PART_NAMES, ImageAnalysis
from .geometry import (
    PROPORTIONS_HEAD_BODY_PREFIX,
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

    # 中文规范名 → 结构 v2 英文 part_id：从 PartKind 标签表派生
    # （schemas.PART_LABELS_ZH 是单一来源；新增部件只改枚举与标签）
    _PART_IDS = {zh: kind.value for kind, zh in PART_LABELS_ZH.items()}

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
        method: Literal["sewn", "worn", "crocheted_or_sewn"] = "sewn",
    ) -> list[AttachmentSpec]:
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
    def _instances(part_id: str, available: set) -> dict[str, Any]:
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
    def design_3d_structure(analysis: ImageAnalysis, *, infer_missing_parts: bool = True) -> dict[str, Any]:
        """Convert image analysis to 3D part specifications.

        Maps each identified part to a basic 3D shape with
        proportions derived from the analysis.

        G4 口径说明：此处的 height_cm / diameter_cm 是**设计意图比例**
        （Q 版先验），不是最终交付尺寸——参数层 generate_params 会按
        gauge/塑形选项/照片剖面重新计算实际值。结构表展示的是设计骨架，
        与图解正文的数字不同属预期行为。
        """
        unknown = [name for name in analysis.parts if name not in PART_NAMES]
        if unknown:
            raise ValueError("不支持自动生成这些部件：" + "、".join(unknown)
                             + "。请在确认页移除误识别部件或选择对应的受支持部件；真实特殊结构需另行设计。")
        head_d = analysis.head_diameter_cm
        total_h = analysis.height_cm
        body_h = max(total_h - head_d, 0.1)  # protect against zero/negative

        dim = StructureDesigner._dimension
        shape_map: dict[str, dict[str, Any]] = {
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

        part_names = list(analysis.parts)

        # 语义服装：LLM 判定穿裙但 parts 漏了裙子 → 按身体比例补上
        if (infer_missing_parts and getattr(analysis, "clothing_type", None) in ("裙子", "连衣裙")
                and "裙子" not in part_names):
            part_names.append("裙子")
            logger.info("Added 裙子 part from clothing_type=%s", analysis.clothing_type)

        part_ids = [StructureDesigner._PART_IDS[name] for name in part_names]
        available = set(part_ids)

        parts: list[PartGeometry] = []
        if len(part_names) != len(part_ids):
            raise RuntimeError("part identifier count does not match part names")
        for part_name, part_id in zip(part_names, part_ids):  # noqa: B905 - length checked above
            base = shape_map[part_name]
            parts.append(PartGeometry(
                part_id=part_id,
                name=part_name,
                **base,
                **StructureDesigner._instances(part_id, available),
            ))

        body_ratio = round(head_d / max(body_h * 0.5, 0.1), 1)
        return StructureGeometry(
            parts=parts,
            proportions=f"{PROPORTIONS_HEAD_BODY_PREFIX}{body_ratio} 倍，Q 版卡通比例",
            notes=(
                "基于单图语义与模板先验；位置、旋转、背面深度和连接锚点"
                "不是照片实测值，生成前可人工确认"
            ),
        ).model_dump(exclude_none=True)
