"""Provider-independent geometric observations from a single front photo."""
from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Annotated, Any, Literal, cast

from PIL import Image
from pydantic import BaseModel, BeforeValidator, Field, model_validator

from ..schemas import MAX_PART_DIMENSION_CM, MAX_PATTERN_PARTS, IntegerCount, StructureData
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

    @property
    def subject_extent(self) -> tuple[float, float] | None:
        """Image-coordinate bounds derived from the existing saved profile."""
        return profile_extent(self.profile)


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

    def to_data(self) -> StructureData:
        """Serialize the validated v2 graph in its established session format."""
        return cast(StructureData, self.model_dump(exclude_none=True))


def normalize_structure(structure: Any) -> StructureData:
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
        return StructureGeometry(**structure).to_data()
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
        # 展示字段只允许标量：渲染层用 part["shape"] 做 dict 键查找，传入
        # 列表/字典会抛 TypeError 让结果页在 import 之后的 rerun 崩溃
        #（F-06：旧格式 structure 此前只校验尺寸/数量，未约束这些字段）。
        for field in ("shape", "type", "color"):
            if field in part and part[field] is not None and not isinstance(
                    part[field], (str, int, float)):
                raise ValueError(f"{name} 的 {field} 必须是文本或数值")
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
    return cast(StructureData, {**structure, "parts": parts})


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
        row_widths.append(float(np.max(ends - starts)) if len(starts) else 0.0)
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


def profile_extent(profile: Sequence[float] | None) -> tuple[float, float] | None:
    """Occupied rows of a width profile as image fractions (top, bottom).

    Uses the same 8%-of-peak row threshold as flare detection and the local
    proportion estimate, so every consumer agrees on where the subject is.
    """
    rows = [i for i, width in enumerate(profile or []) if width > 0.08]
    if not rows or not profile:
        return None
    return rows[0] / len(profile), (rows[-1] + 1) / len(profile)


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


def _median(values: list[int]) -> int:
    ordered = sorted(values)
    return ordered[len(ordered) // 2]


def _foreground_runs(mask: Any) -> list[list[tuple[int, int]]]:
    """Inclusive-exclusive foreground runs for each row, left to right."""
    import numpy as np

    rows: list[list[tuple[int, int]]] = []
    for row in np.asarray(mask, dtype=bool):
        edges = np.diff(np.pad(row.astype(np.int8), (1, 1)))
        starts = np.flatnonzero(edges == 1)
        ends = np.flatnonzero(edges == -1)
        rows.append([(int(start), int(end)) for start, end in zip(starts, ends, strict=True)])
    return rows


def _defined_runs(
    longest: list[tuple[int, int, int] | None], indexes: list[int],
) -> list[tuple[int, int, int]]:
    found: list[tuple[int, int, int]] = []
    for row in indexes:
        item = longest[row]
        if item is not None:
            found.append(item)
    return found


def _longest_run(runs: list[tuple[int, int]]) -> tuple[int, int, int] | None:
    if not runs:
        return None
    start, end = max(runs, key=lambda item: item[1] - item[0])
    return start, end, end - start


def scale_box(
    box: tuple[int, int, int, int],
    src_size: tuple[int, int],
    dst_size: tuple[int, int],
) -> tuple[int, int, int, int]:
    """Scale an ``x, y, w, h`` box between ``(width, height)`` sizes."""
    x, y, width, height = box
    src_w, src_h = src_size
    dst_w, dst_h = dst_size
    if src_w <= 0 or src_h <= 0:
        return box
    sx, sy = dst_w / src_w, dst_h / src_h
    return (
        int(round(x * sx)),
        int(round(y * sy)),
        max(1, int(round(width * sx))),
        max(1, int(round(height * sy))),
    )


def head_box_from_mask(mask: Any) -> tuple[int, int, int, int] | None:
    """Head box from the top of a foreground mask, in mask pixels.

    Prefer a top component separated by at least one empty row. Otherwise
    accept a neck pinch in the upper half. A nearly straight column returns
    None: guessing a fraction of a rectangle is not a head measurement.
    Ears that share the head's pixels stay inside this box; they are not a
    separate component. This does not measure ear length.
    """
    rows = _foreground_runs(mask)
    if len(rows) < 12:
        return None
    width = int(mask.shape[1]) if getattr(mask, "ndim", 0) == 2 else 0
    if width < 8:
        return None
    longest = [_longest_run(runs) for runs in rows]
    peak = max((item[2] for item in longest if item), default=0)
    if peak < 4 or peak / width < 0.05:
        return None
    occupied = [index for index, item in enumerate(longest) if item and item[2] > 0.08 * peak]
    if len(occupied) < 12:
        return None
    subject_top, subject_bottom = occupied[0], occupied[-1]
    subject_h = subject_bottom - subject_top + 1
    if subject_h < 12:
        return None

    groups: list[list[int]] = [[occupied[0]]]
    for previous, row in zip(occupied, occupied[1:], strict=False):
        if row - previous > 1:
            groups.append([row])
        else:
            groups[-1].append(row)

    def box_of(chosen: list[int]) -> tuple[int, int, int, int] | None:
        chosen_runs = _defined_runs(longest, chosen)
        if len(chosen_runs) < 4:
            return None
        starts = [item[0] for item in chosen_runs]
        ends = [item[1] for item in chosen_runs]
        left, right = min(starts), max(ends)
        top, bottom = chosen[0], chosen[-1] + 1
        box_w, box_h = right - left, bottom - top
        if box_w < 4 or box_h < 4:
            return None
        if not 0.08 <= box_h / subject_h <= 0.50:
            return None
        center = top + box_h / 2
        if center < subject_top or center > subject_top + subject_h / 2:
            return None
        outside_rows = [row for row in occupied if row < chosen[0] or row > chosen[-1]]
        outside = [item[2] for item in _defined_runs(longest, outside_rows)]
        body_peak = max(outside) if outside else peak
        # Compare the typical row width, not the bbox. Side ears widen the box
        # without making the head itself several times the body.
        core = _median([item[2] for item in chosen_runs])
        if body_peak <= 0 or not 0.28 <= core / body_peak <= 2.2:
            return None
        if subject_h / max(box_w, box_h) > 8:
            return None
        return left, top, box_w, box_h

    if len(groups) >= 2 and groups[0][-1] < subject_top + subject_h * 0.55:
        separated = box_of(groups[0])
        if separated is not None:
            return separated

    widths = [item[2] for item in _defined_runs(longest, occupied)]
    count = len(widths)

    def smoothed(index: int) -> int:
        window = widths[max(0, index - 1):min(count, index + 2)]
        return _median(window)

    smooth = [smoothed(index) for index in range(count)]
    for index in range(max(2, int(count * 0.12)), int(count * 0.55)):
        if smooth[index] > smooth[index - 2] or smooth[index] > smooth[min(count - 1, index + 2)]:
            continue
        head_peak = max(smooth[:index])
        if head_peak <= 0 or smooth[index] > 0.82 * head_peak:
            continue
        below = smooth[index:min(count, index + max(3, int(count * 0.15)))]
        if not below or max(below) < smooth[index] * 1.08:
            continue
        pinched = box_of(occupied[:index])
        if pinched is not None:
            return pinched
    return None


def ear_hint_from_mask(mask: Any, head_box: tuple[int, int, int, int]) -> bool:
    """True when the upper head has a symmetric side bulge or two side lobes.

    Sewn ears usually share a component with the head, so this does not split
    connected components and does not measure ear length or generate a tube.
    Unmerged PR #15 explores that measurement separately; this hint does not
    depend on it. A plain round head returns False.
    """
    rows = _foreground_runs(mask)
    height = len(rows)
    width = int(mask.shape[1]) if getattr(mask, "ndim", 0) == 2 else 0
    x, y, box_w, box_h = head_box
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(width, x + box_w), min(height, y + box_h)
    if x1 - x0 < 6 or y1 - y0 < 6:
        return False
    center = (x0 + x1) / 2

    def closest(row_index: int) -> tuple[int, int] | None:
        best: tuple[int, int] | None = None
        best_distance = 1e9
        for start, end in rows[row_index]:
            distance = abs((start + end) / 2 - center)
            if distance < best_distance:
                best_distance = distance
                best = (start, end)
        if best is None or best_distance > box_w * 0.75:
            return None
        return best

    def band(start_row: int, end_row: int) -> tuple[int, int, int] | None:
        lefts: list[int] = []
        rights: list[int] = []
        for row_index in range(max(0, start_row), min(height, end_row)):
            run = closest(row_index)
            if run is None or run[1] - run[0] < box_w * 0.25:
                continue
            lefts.append(run[0])
            rights.append(run[1])
        if len(lefts) < 2:
            return None
        left, right = _median(lefts), _median(rights)
        return left, right, right - left

    # Compare the upper sides with the face equator. A round head is widest
    # at the equator, so "upper wider than the chin" is not an ear.
    crown = band(y0, y0 + max(2, int((y1 - y0) * 0.40)))
    face = band(y0 + int((y1 - y0) * 0.35), y0 + int((y1 - y0) * 0.75))
    if crown and face:
        crown_left, crown_right, crown_width = crown
        face_left, face_right, face_width = face
        left_extra = face_left - crown_left
        right_extra = crown_right - face_right
        minimum = max(2, int(0.08 * max(face_width, 1)))
        if (left_extra >= minimum and right_extra >= minimum
                and 0.5 <= left_extra / max(right_extra, 1) <= 2.0
                and crown_width >= face_width * 1.12):
            return True

    lobe_rows = 0
    scanned = 0
    for row_index in range(max(0, y0 - int(box_h * 0.35)), min(height, y0 + int(box_h * 0.25))):
        lobes = [
            (start, end) for start, end in rows[row_index]
            if max(2, int(0.12 * box_w)) <= end - start <= 0.75 * box_w
        ]
        if not lobes:
            continue
        scanned += 1
        if len(lobes) != 2:
            continue
        (left_start, left_end), (right_start, right_end) = lobes
        gap = right_start - left_end
        left_center = (left_start + left_end) / 2
        right_center = (right_start + right_end) / 2
        width_ratio = (left_end - left_start) / max(1, right_end - right_start)
        symmetric = abs((left_center + right_center) / 2 - center) <= 0.2 * box_w
        balanced = abs((center - left_center) - (right_center - center)) <= 0.35 * box_w
        if gap >= 0.12 * box_w and symmetric and balanced and 0.5 <= width_ratio <= 2.0:
            lobe_rows += 1
    return scanned >= 3 and lobe_rows >= 3 and lobe_rows / scanned >= 0.3


def tail_hint_from_mask(mask: Any) -> bool:
    """True for a short one-sided lower bump that still covers the torso.

    A detached leg, a pair of legs, or a hem that widens on both sides is not
    a tail. A single front photo cannot tell back from side; this is an
    uncalibrated contour candidate, not a semantic certainty.
    """
    rows = _foreground_runs(mask)
    width = int(mask.shape[1]) if getattr(mask, "ndim", 0) == 2 else 0
    if width < 8 or len(rows) < 12:
        return False
    longest = [_longest_run(runs) for runs in rows]
    peak = max((item[2] for item in longest if item), default=0)
    if peak < 4:
        return False
    occupied = [index for index, item in enumerate(longest) if item and item[2] > 0.08 * peak]
    if len(occupied) < 12:
        return False
    middle = occupied[int(len(occupied) * 0.35):int(len(occupied) * 0.65)]
    if len(middle) < 3:
        return False
    torso_runs = _defined_runs(longest, middle)
    torso_left = _median([item[0] for item in torso_runs])
    torso_right = _median([item[1] for item in torso_runs])
    torso_width = torso_right - torso_left
    if torso_width < 6:
        return False
    hits: list[str] = []
    for row in occupied[int(len(occupied) * 0.75):]:
        item = longest[row]
        if item is None:
            continue
        start, end, _run_width = item
        covers = start <= torso_left + 0.15 * torso_width and end >= torso_right - 0.15 * torso_width
        if not covers:
            continue
        left_extra = torso_left - start
        right_extra = end - torso_right
        minimum = max(2, 0.12 * torso_width)
        maximum = 0.45 * torso_width
        slack = 0.08 * torso_width
        left_hit = minimum <= left_extra <= maximum and right_extra <= slack
        right_hit = minimum <= right_extra <= maximum and left_extra <= slack
        if left_hit == right_hit:
            continue
        hits.append("left" if left_hit else "right")
    if len(hits) < 3 or len(set(hits)) != 1:
        return False
    return 0.06 <= len(hits) / len(occupied) <= 0.22


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
