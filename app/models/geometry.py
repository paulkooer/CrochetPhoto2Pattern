"""Provider-independent geometric observations from a single front photo."""
from __future__ import annotations

import logging
from typing import Annotated, Any, Literal

from PIL import Image
from pydantic import BaseModel, BeforeValidator, Field, model_validator

from ..schemas import MAX_PART_DIMENSION_CM, MAX_PATTERN_PARTS, IntegerCount
from ..utils.counts import integer_count
from ..utils.numbers import finite_float
from .color_design import _BG_DIST_THRESHOLD
from .mask_review import MaskReview
from .subject import SubjectObservation

logger = logging.getLogger(__name__)

PartDimension = Annotated[
    float, Field(gt=0, le=MAX_PART_DIMENSION_CM), BeforeValidator(finite_float)]
ProfileFraction = Annotated[float, Field(ge=0, le=1), BeforeValidator(finite_float)]

# 头身比说明行由 StructureDesigner 生成、调尺寸时按新比例重写；两端共享
# 前缀常量，避免文案一处改动后另一端的 startswith 识别静默失灵。
PROPORTIONS_HEAD_BODY_PREFIX = "头部直径约为身体高度的 "


class SilhouetteObservation(BaseModel):
    """Normalized subject width profile, top-to-bottom."""

    profile: list[ProfileFraction] = Field(min_length=8, max_length=2000)
    flare: bool = False
    source: Literal["segmentation_pipeline"] = "segmentation_pipeline"
    # Legacy numeric values remain readable; no probability has been calibrated.
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class BodyRegionObservation(BaseModel):
    """User-selected crop coordinates and full-image-coordinate body profile."""

    box: tuple[ProfileFraction, ProfileFraction, ProfileFraction, ProfileFraction]
    profile: list[ProfileFraction] = Field(min_length=8, max_length=2000)
    source: Literal["user_body_box"] = "user_body_box"

    @model_validator(mode="after")
    def valid_region(self) -> BodyRegionObservation:
        x0, y0, x1, y1 = self.box
        if x0 >= x1 or y0 >= y1 or not any(self.profile):
            raise ValueError("身体框必须具有面积及有效轮廓")
        return self


class GeometryObservation(BaseModel):
    """Versioned geometry IR shared by every real-photo parser mode."""

    schema_version: Literal["1.0"] = "1.0"
    view_mode: Literal["single_front_assumed"] = "single_front_assumed"
    silhouette: SilhouetteObservation | None = None
    body_region: BodyRegionObservation | None = None
    mask_review: MaskReview | None = None
    used_for_generation: bool = True
    limitations: list[str] = Field(default_factory=lambda: [
        "单张正面图没有背面或深度信息",
        "宽度剖面按圆形截面近似为旋转体",
        "部件遮挡可能使轮廓宽度偏大",
        "逐行最长连续前景段只是身体宽度近似，无法分开贴合身体的手臂或识别部件",
    ])


class NormalizedPosition(BaseModel):
    """Template-space part centre; deliberately carries no fake cm depth."""

    x: float = Field(ge=-1.0, le=1.0, description="left (-) to right (+)")
    y: float = Field(ge=0.0, le=1.0, description="bottom (0) to top (1)")
    z: float = Field(ge=-1.0, le=1.0, description="back (-) to front (+)")


class EulerRotation(BaseModel):
    """Approximate template orientation in degrees; applied in Z → X → Y order."""

    x: float = Field(default=0.0, ge=-180.0, le=180.0)
    y: float = Field(default=0.0, ge=-180.0, le=180.0)
    z: float = Field(default=0.0, ge=-180.0, le=180.0)


class AttachmentSpec(BaseModel):
    """One instance's connection to a named anchor on another logical part."""

    target_part_id: str = Field(min_length=1)
    target_anchor: str = Field(min_length=1)
    self_anchor: str = Field(min_length=1)
    method: Literal["sewn", "worn", "crocheted_or_sewn"] = "sewn"


class PartInstance(BaseModel):
    """A concrete copy of a logical part, including mirror/attachment data."""

    instance_id: str = Field(min_length=1)
    position: NormalizedPosition
    rotation_deg: EulerRotation = Field(default_factory=EulerRotation)
    mirror_of: str | None = None
    attachments: list[AttachmentSpec] = Field(default_factory=list)


class PartGeometry(BaseModel):
    """Version-2 logical part while retaining all legacy dimension keys."""

    part_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    shape: str = Field(min_length=1)
    diameter_cm: PartDimension | None = None
    height_cm: PartDimension | None = None
    length_cm: PartDimension | None = None
    color: str = Field(default="body", min_length=1)
    count: IntegerCount = Field(default=1, ge=1, le=20)
    mirror_group: str | None = None
    instances: list[PartInstance] = Field(min_length=1)
    source: Literal["template_inferred"] = "template_inferred"
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _instances_match_count(self) -> PartGeometry:
        if len(self.instances) != self.count:
            raise ValueError("part count must equal the number of concrete instances")
        if self.diameter_cm is None and self.height_cm is None and self.length_cm is None:
            raise ValueError("a part must declare at least one physical dimension")
        ids = [instance.instance_id for instance in self.instances]
        if len(ids) != len(set(ids)):
            raise ValueError("instance_id values must be unique within a part")
        for instance in self.instances:
            if instance.mirror_of and instance.mirror_of not in ids:
                raise ValueError("mirror_of must reference an instance of the same part")
            if instance.mirror_of == instance.instance_id:
                raise ValueError("an instance cannot mirror itself")
        return self


class StructureCoordinateSystem(BaseModel):
    """Machine-readable convention for normalized template coordinates."""

    units: Literal["normalized_template_space"] = "normalized_template_space"
    origin: Literal["subject_bottom_center"] = "subject_bottom_center"
    x_axis: Literal["left_negative_right_positive"] = "left_negative_right_positive"
    y_axis: Literal["bottom_zero_top_one"] = "bottom_zero_top_one"
    z_axis: Literal["back_negative_front_positive"] = "back_negative_front_positive"


class StructureGeometry(BaseModel):
    """Versioned editable part graph produced by :class:`StructureDesigner`."""

    schema_version: Literal["2.0"] = "2.0"
    coordinate_system: StructureCoordinateSystem = Field(
        default_factory=StructureCoordinateSystem)
    parts: list[PartGeometry]
    proportions: str
    notes: str

    @model_validator(mode="after")
    def _validate_graph_references(self) -> StructureGeometry:
        part_ids = [part.part_id for part in self.parts]
        if len(part_ids) != len(set(part_ids)):
            raise ValueError("part_id values must be unique")
        part_names = [part.name for part in self.parts]
        if len(part_names) != len(set(part_names)):
            raise ValueError("part names must be unique in structure v2")

        instance_ids = {
            instance.instance_id
            for part in self.parts
            for instance in part.instances
        }
        for part in self.parts:
            for instance in part.instances:
                if instance.mirror_of and instance.mirror_of not in instance_ids:
                    raise ValueError(
                        f"mirror_of references unknown instance {instance.mirror_of!r}")
                for attachment in instance.attachments:
                    if attachment.target_part_id not in part_ids:
                        raise ValueError(
                            "attachment references unknown part "
                            f"{attachment.target_part_id!r}")
        return self


def normalize_structure(structure: Any) -> dict[str, Any]:
    """Validate a structure payload while preserving pre-v2 backup support.

    Declaring schema_version=2.0 opts into the complete graph contract.  Older
    payloads remain readable with their historical minimal ``parts/name``
    contract without inventing graph nodes. Physical dimensions and quantities
    are decoded before any generation loops, including legacy inputs.
    """
    if (not isinstance(structure, dict)
            or not isinstance(structure.get("parts"), list)
            or not all(isinstance(part, dict)
                       and isinstance(part.get("name"), str) and part["name"]
                       for part in structure["parts"])):
        raise ValueError("structure 字段无效（应为含 parts 列表的对象）")
    if len(structure["parts"]) > MAX_PATTERN_PARTS:
        raise ValueError(
            f"部件数量 {len(structure['parts'])} 超过上限 {MAX_PATTERN_PARTS}")
    if structure.get("schema_version") == "2.0":
        return StructureGeometry(**structure).model_dump(exclude_none=True)
    names: set[str] = set()
    parts = []
    for source in structure["parts"]:
        name = source["name"]
        if name in names:
            raise ValueError(f"部件名称不能重复: {name}")
        names.add(name)
        part = dict(source)
        if "instances" in part:
            raise ValueError("旧格式部件不能包含 instances；请使用完整的 schema_version=2.0 结构")
        for field in ("diameter_cm", "height_cm", "length_cm"):
            if part.get(field) is None:
                part.pop(field, None)
                continue
            value = finite_float(part[field])
            if not 0 < value <= MAX_PART_DIMENSION_CM:
                raise ValueError(f"{part['name']} 的 {field} 必须大于 0 且不超过 200 cm")
            part[field] = value
        if "count" in part:
            part["count"] = integer_count(part["count"])
            if not 1 <= part["count"] <= 20:
                raise ValueError("部件数量必须是 1–20 的整数")
        parts.append(part)
    return {**structure, "parts": parts}


def _mask_width_profile(mask, n_rows: int) -> list[float] | None:
    """Measure the longest contiguous foreground run in each pixel row.

    Disconnected arms/noise must not be added to torso width. This is a
    geometric heuristic, not part recognition: touching limbs and occlusion
    still require review. Average pixel-row widths before peak normalization,
    preserving image coordinates and empty rows for existing part spans.
    """
    import numpy as np

    if mask.ndim != 2 or n_rows < 1:
        return None
    height, width = mask.shape
    if height < n_rows or width < 4:
        return None
    row_widths = []
    for row in mask:
        edges = np.diff(np.pad(row.astype(bool).astype(np.int8), (1, 1)))
        starts = np.flatnonzero(edges == 1)
        ends = np.flatnonzero(edges == -1)
        row_widths.append(float((ends - starts).max()) if len(starts) else 0.0)
    widths = [float(np.mean(row_widths[height * i // n_rows:height * (i + 1) // n_rows]))
              for i in range(n_rows)]
    peak = max(widths)
    if peak / width < 0.05:
        return None
    return [value / peak for value in widths]


def silhouette_profile(image: Image.Image, n_rows: int = 40, *,
                       subject: SubjectObservation | None = None) -> list[float] | None:
    """Measure normalized subject width from top to bottom.

    GrabCut subject extraction is preferred; a corner-background colour model
    is the deterministic fallback. Both paths measure contiguous row widths
    on un-eroded masks, normalized by the widest band without metric scale.
    """
    try:
        import numpy as np
    except ImportError:
        return None
    try:
        from .subject import extract_subject
        res = subject.extract(image) if subject is not None else extract_subject(image, max_side=120)
        if res is not None:
            mask, small = res
            if mask.shape != (small.height, small.width):
                return None
            if mask.shape[0] >= n_rows and mask.shape[1] >= 4:
                return _mask_width_profile(mask, n_rows)

        img = image.convert("RGB")
        img.thumbnail((120, 120))
        pixels = np.asarray(img, dtype=np.int16)
        height, width = pixels.shape[:2]
        if height < n_rows or width < 4:
            return None
        from .color_design import estimate_background
        background = np.array(estimate_background(pixels), dtype=pixels.dtype)
        mask = np.abs(pixels - background).sum(axis=2) > _BG_DIST_THRESHOLD
        return _mask_width_profile(mask, n_rows)
    except Exception as exc:
        logger.debug("silhouette extraction failed: %s", exc)
        return None


def _row_runs(row, min_len: int = 2) -> list[tuple[int, int]]:
    """一行的前景连续段 (start, end)；宽度 <min_len 的段落按噪声丢弃。"""
    import numpy as np

    edges = np.diff(np.pad(row.astype(bool).astype(np.int8), (1, 1)))
    starts = np.flatnonzero(edges == 1)
    ends = np.flatnonzero(edges == -1)
    return [(int(s), int(e)) for s, e in zip(starts, ends, strict=True)
            if e - s >= min_len]


def measure_ears(mask, *, narrow_ratio: float = 0.5,
                 min_band_fraction: float = 0.08,
                 max_band_fraction: float = 0.45,
                 min_run: int = 3) -> tuple[float, float] | None:
    """正面掩码 → (耳长占比, 耳宽占比)，均以"主体可见高度"为分母。

    耳朵在正面掩码里有两种确定性几何特征，任一成立即算耳波段：

      A. **窄**：并拢/细长的耳朵，顶部合计宽度 ≤ narrow_ratio × 最宽行。判据是
         这段窄带能持续多长——任何圆头都是从窄长起来的（球顶第 1 行最窄），但
         球顶只在很短几行里低于峰值一半，长耳能占到主体高度的 30%+。
      B. **分**：外张的长耳（两耳合计宽度已接近头宽），顶部几行分裂成 ≥2 段
         （耳间缺口），向下合并成一段即结束。

    耳宽取每行"单耳宽"在耳波段上的中位数：单段行 = 该段宽，分裂行 = 较窄的
    那一叶（耳根与头合并的那一叶明显更宽，取它会把耳宽算胖）。耳长是**下界**：
    正面轮廓里缺口通常在耳根之前就闭合，真实耳长可能更长——结构层据此只设
    下限、不设上限。

    上下界（8%–45%）既排掉圆头（窄段过短）也排掉没分开主体/背景的掩码
    （窄段一路到底）。测不到返回 None，调用方不凭空加耳朵。
    """
    import numpy as np

    if getattr(mask, "ndim", 0) != 2 or mask.shape[0] < 8:
        return None

    def _lobe_width(runs) -> float:
        """该行的"单耳宽"：单段行 = 该段宽；分裂行 = **较窄的那一叶**。

        分裂行里通常有一叶是"耳 + 已与耳根合并的头顶"，明显更宽；取它会把
        耳宽算胖（实测真照片 4.0cm vs 实际 ~3cm）。只把 ≥ 最宽叶一半的段算
        作叶，滤掉噪点碎片。
        """
        widths = [e - s for s, e in runs]
        if not widths:
            return 0.0
        return float(min(w for w in widths if w >= 0.5 * max(widths)))

    runs_per_row = [_row_runs(row, min_len=min_run) for row in mask]
    total = [sum(e - s for s, e in runs) for runs in runs_per_row]
    lobe_width = [_lobe_width(runs) for runs in runs_per_row]
    occupied = [bool(runs) for runs in runs_per_row]
    rows = [i for i, seen in enumerate(occupied) if seen]
    if len(rows) < 8:
        return None
    top, bottom = rows[0], rows[-1]
    height = bottom - top + 1
    peak = max(total)
    if peak <= 0:
        return None
    narrow = narrow_ratio * peak
    band: list[int] = []
    for i in range(top, bottom + 1):
        if not occupied[i]:
            continue                       # 段内空洞不结束（噪声/高光水印）
        if total[i] > narrow and len(runs_per_row[i]) < 2:
            break
        band.append(i)
    if len(band) < max(3, int(min_band_fraction * height)):
        return None
    if len(band) > max_band_fraction * height:
        # 耳朵不可能占主体高度的一大半：掩码没分开主体与背景时窄段会一路走到底
        return None
    width_ratio = float(np.median([lobe_width[i] for i in band])) / height
    if width_ratio <= 0:
        return None
    return len(band) / height, width_ratio


def has_bottom_flare(profile: list[float]) -> bool:
    """Detect a lower-quarter flare within the occupied subject rows."""
    rows = [i for i, width in enumerate(profile) if width > 0.08]
    if not rows:
        return False
    subject = profile[rows[0]:rows[-1] + 1]
    count = len(subject)
    if count < 8:
        return False
    lower = subject[int(count * 0.72):int(count * 0.95)]
    middle = subject[int(count * 0.42):int(count * 0.62)]
    if not lower or not middle:
        return False
    return (sum(lower) / len(lower)) > 1.25 * (sum(middle) / len(middle))


def observe_geometry(image: Image.Image, *, subject: SubjectObservation | None = None) -> GeometryObservation:
    """Build the provider-neutral geometry observation used by shaping."""
    profile = silhouette_profile(image, subject=subject)
    if profile is None:
        return GeometryObservation(
            silhouette=None,
            limitations=[
                "未能从图片中稳定分离主体轮廓，身体将回退模板形状",
                "单张正面图没有背面或深度信息",
            ],
        )
    rounded = [round(float(value), 3) for value in profile]
    return GeometryObservation(silhouette=SilhouetteObservation(
        profile=rounded,
        flare=has_bottom_flare(rounded),
    ))


def mock_geometry() -> GeometryObservation:
    """Geometry contract for Mock mode: never consume the uploaded photo."""
    return GeometryObservation(
        silhouette=None,
        used_for_generation=False,
        limitations=["Mock 演示数据不读取照片几何信息"],
    )


def no_photo_geometry() -> GeometryObservation:
    """Geometry contract for manual designs that have no source image."""
    return GeometryObservation(
        silhouette=None,
        used_for_generation=False,
        limitations=["手动设计没有照片几何输入，使用部件模板与用户尺寸"],
    )
