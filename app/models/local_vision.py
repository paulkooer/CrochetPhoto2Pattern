"""Local (no-LLM) photo analysis — the default photo-analysis path.

默认本地分析：OpenCV 人脸检测给出头部像素框，按
"头径锚点 × 人体比例" 推算 ImageAnalysis。

能力边界（如实声明）：
- 比例（身高/头径的倍数）来自人脸框，或无人脸时来自轮廓顶部的头部候选
- 绝对尺度（头径是多少厘米）单张照片无参照无法得到；这里用 9cm
  作为内部比例参考，PipelineOrchestrator 随后按用户目标高度重新缩放
- 部件列表仍是四部件模板。耳朵、裙摆、尾巴只作为确认页提示，默认不勾选
"""
from __future__ import annotations

import logging
from typing import Any

from PIL import Image

from ..schemas import ImageAnalysis
from .geometry import ear_hint_from_mask as _ear_hint
from .geometry import has_bottom_flare as _has_bottom_flare
from .geometry import head_box_from_mask as _head_box_from_mask
from .geometry import scale_box as _scale_box
from .geometry import silhouette_profile as _silhouette_profile
from .geometry import tail_hint_from_mask as _tail_hint
from .image_parser import extract_color_palette
from .subject import SubjectObservation

logger = logging.getLogger(__name__)

DEFAULT_HEAD_CM = 9.0      # 内部比例参考；不是照片实测，管线随后按目标高度缩放
FRAME_FILL_RATIO = 0.9     # 假设主体大致占满画面高度（全身玩偶照常见构图）
MIN_BODY_RATIO = 2.0       # 身高/头径 的合理区间（大头 Q 版 … 全身成人照）
MAX_BODY_RATIO = 8.0
# Haar 正脸框大致覆盖眉毛到下巴，不含额头上部、头顶与头发。按人体测量学经验扩展为
# 整头：高度 ×1.5（下巴为底边，向上延伸）、宽度 ×1.2（左右各放宽 10%）。这是未经
# 授权照片校准的先验，系数须在 G3 数据上复核；确认页可以手动调整头部框。
HEAD_HEIGHT_PER_FACE = 1.5
HEAD_WIDTH_PER_FACE = 1.2

_CANONICAL_PARTS = ["头部", "身体", "手臂", "腿部"]


def _detect_face(img: Image.Image) -> tuple[int, int, int, int] | None:
    """Frontal-face detection via OpenCV haar cascade (fully offline).

    Returns the largest (x, y, w, h) in pixels, or None
    (cv2 未安装 / 未检出人脸)。
    """
    try:
        import cv2
        import numpy as np
        # OpenCV 5.x 移除了 legacy CascadeClassifier——缺 API 视同不可用
        if not hasattr(cv2, "CascadeClassifier") or not hasattr(cv2, "data"):
            raise ImportError("legacy CascadeClassifier unavailable")
    except ImportError:
        logger.info("opencv 不可用或缺少 haar API，本地视觉走纯默认值路径")
        return None
    arr = np.array(img.convert("RGB"))[:, :, ::-1]  # RGB → BGR
    gray = cv2.cvtColor(arr, cv2.COLOR_BGR2GRAY)
    cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades  # type: ignore[attr-defined]  # opencv 无官方类型桩
        + "haarcascade_frontalface_default.xml"
    )
    faces = cascade.detectMultiScale(
        gray, scaleFactor=1.1, minNeighbors=5, minSize=(24, 24)
    )
    if len(faces) == 0:
        return None
    x, y, w, h = max(faces, key=lambda f: int(f[2]) * int(f[3]))  # 取主体（最大脸）
    return int(x), int(y), int(w), int(h)


def _subject_vertical_extent(profile: list[float] | None, height: int) -> tuple[float, float]:
    from .geometry import profile_extent

    extent = profile_extent(profile)
    if extent:
        return extent[0] * height, extent[1] * height
    return 0.0, height * FRAME_FILL_RATIO


def _head_size_px(box) -> float:
    """Whole-head diameter implied by a face box (not clipped by the image edge)."""
    _x, _y, width, height = box
    return max(width * HEAD_WIDTH_PER_FACE, height * HEAD_HEIGHT_PER_FACE, 1)


def head_box_from_face(box, image_width: int, image_height: int) -> tuple[int, int, int, int]:
    """Expand a face box upward and sideways into a head box inside the image."""
    x, y, width, height = box
    margin = width * (HEAD_WIDTH_PER_FACE - 1) / 2
    left, right = max(0.0, x - margin), min(float(image_width), x + width + margin)
    top, bottom = max(0.0, y + height - height * HEAD_HEIGHT_PER_FACE), min(float(image_height), y + height)
    return round(left), round(top), round(right - left), round(bottom - top)


def _face_rejection_reason(image: Image.Image, box, profile: list[float] | None) -> str | None:
    """Conservative checks for an upright subject, not semantic face verification.

    Sideways poses and unusual proportions require manual review. These bounds
    reject unsuitable candidates rather than clamp them into plausible measurements.
    Bounds and position use the raw detection; the size rule uses the implied head.
    """
    x, y, width, height = box
    if width <= 0 or height <= 0 or x < 0 or y < 0 or x + width > image.width or y + height > image.height:
        return "检测框超出图片或没有面积"
    top, bottom = _subject_vertical_extent(profile, image.height)
    center = y + height / 2
    if center < top or center > top + (bottom - top) / 2:
        return "检测框不在主体上半部，不能自动作为直立玩偶头部"
    if (bottom - top) / _head_size_px(box) > MAX_BODY_RATIO:
        return "检测框相对主体过小，无法可靠推算头身比例"
    return None


def _mask_pair(image: Image.Image, subject: SubjectObservation | None, *, allow_extract: bool):
    """Return ``(mask, small_image)`` without a second GrabCut when possible."""
    if subject is not None:
        try:
            segmentation = subject.segmentation
        except Exception as exc:
            logger.debug("subject mask unavailable: %s", exc)
            segmentation = None
        if segmentation is not None:
            mask, small = segmentation
            if getattr(mask, "shape", None) == (small.height, small.width):
                return mask, small
    if not allow_extract:
        return None
    try:
        from .subject import extract_subject

        segmentation = extract_subject(image, max_side=120)
    except Exception as exc:
        logger.debug("standalone mask unavailable: %s", exc)
        return None
    if segmentation is None:
        return None
    mask, small = segmentation
    if mask.shape != (small.height, small.width):
        return None
    return mask, small


def _clip_box(box: tuple[int, int, int, int], width: int, height: int) -> tuple[int, int, int, int] | None:
    x, y, box_w, box_h = box
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(width, x + box_w), min(height, y + box_h)
    if x1 - x0 < 2 or y1 - y0 < 2:
        return None
    return x0, y0, x1 - x0, y1 - y0


def _silhouette_head_ok(image: Image.Image, box: tuple[int, int, int, int],
                        profile: list[float] | None) -> bool:
    """Same upper-half and minimum-size rules as a face box, without face expansion."""
    _x, y, width, height = box
    top, bottom = _subject_vertical_extent(profile, image.height)
    center = y + height / 2
    if center < top or center > top + (bottom - top) / 2:
        return False
    return (bottom - top) / max(width, height, 1) <= MAX_BODY_RATIO


def analyze(
    image: Image.Image,
    n_colors: int = 5,
    geometry_profile: list[float] | None = None,
    geometry_observed: bool = False,
    *,
    subject: SubjectObservation | None = None,
) -> tuple[ImageAnalysis, dict[str, Any]]:
    """Estimate an ImageAnalysis from the photo without any LLM call.

    Returns (analysis, meta)；meta 描述估算来源与依据，供 UI 透明展示。
    """
    colors = extract_color_palette(image, n_colors=n_colors, subject=subject)
    H = image.size[1]
    box = _detect_face(image)
    # A widened silhouette is an observation, not evidence of a garment.
    # Orchestrator 已建立 provider-neutral geometry 时复用同一观测，避免
    # GrabCut/背景分割做两遍。直接调用 analyze() 仍保持原有独立行为。
    profile = geometry_profile if geometry_observed else _silhouette_profile(image, subject=subject)
    parts = list(_CANONICAL_PARTS)
    if box is not None:
        rejection = _face_rejection_reason(image, box, profile)
        if rejection:
            rejected_face = (list(box), rejection)
            box = None
        else:
            rejected_face = None
    else:
        rejected_face = None

    # geometry_observed means the caller already measured the photo. Do not
    # start a second extraction when that caller did not pass the subject.
    mask_pair = _mask_pair(image, subject, allow_extract=not geometry_observed)
    possible_ears = False
    possible_tail = False
    silhouette_head: tuple[int, int, int, int] | None = None
    if mask_pair is not None:
        mask, small = mask_pair
        possible_tail = _tail_hint(mask)
        if box is None:
            mask_head = _head_box_from_mask(mask)
            if mask_head is not None:
                scaled = _clip_box(
                    _scale_box(mask_head, small.size, image.size), image.size[0], image.size[1])
                if scaled is not None and _silhouette_head_ok(image, scaled, profile):
                    silhouette_head = scaled
                    ear_box = _clip_box(mask_head, small.size[0], small.size[1])
                else:
                    ear_box = None
            else:
                ear_box = None
        else:
            face_head = head_box_from_face(box, image.size[0], H)
            ear_box = _clip_box(
                _scale_box(face_head, image.size, small.size), small.size[0], small.size[1])
        if ear_box is not None:
            possible_ears = _ear_hint(mask, ear_box)
    candidate_meta: dict[str, Any] = {
        "parts_source": "default_template", "requires_subject_review": True,
        "subject_type": "unclassified",
        "possible_skirt": bool(profile is not None and _has_bottom_flare(profile)),
        "possible_ears": possible_ears,
        "possible_tail": possible_tail,
    }
    if rejected_face is not None:
        candidate_meta.update(rejected_face_box=rejected_face[0], face_rejection_reason=rejected_face[1])

    if box is None and silhouette_head is None:
        meta: dict[str, Any] = {
            **candidate_meta,
            "source": "default",
            "note": ("头部候选框未通过检查，使用默认 Q 版比例；请手动确认头部和部件"
                     if candidate_meta.get("face_rejection_reason") else
                     "未检测到人脸，使用默认 Q 版比例；部件来自模板，请手动确认"),
        }
        return ImageAnalysis(
            body_type="标准",
            head_diameter_cm=DEFAULT_HEAD_CM,
            height_cm=18.0,
            main_features=["本地估算（未检出人脸）"],
            pose="站立",
            difficulty="easy",
            parts=parts,
            recommended_colors=colors or None,
        ), meta

    if box is None:
        head_box = silhouette_head
        assert head_box is not None
        head_px = float(max(head_box[2], head_box[3], 1))
        source_name = "silhouette-head"
        source_note = (
            "比例来自待确认的轮廓头部候选（不是人脸检测），部件来自模板；"
            "耳朵、裙摆和尾巴只作为提示，默认不加入。"
            "单图没有绝对尺度，厘米尺寸由生成时选择的目标高度决定"
        )
        face_fields: dict[str, Any] = {}
    else:
        head_px = _head_size_px(box)
        head_box = head_box_from_face(box, image.size[0], H)
        source_name = "opencv-face"
        source_note = (
            "比例来自待确认的头部候选框（由人脸框按经验比例扩展），部件来自模板；"
            "单图没有绝对尺度，厘米尺寸由生成时选择的目标高度决定"
        )
        face_fields = {"face_box": [int(v) for v in box]}
    top, bottom = _subject_vertical_extent(profile, H)
    subject_px = bottom - top
    ratio = min(max(subject_px / head_px, MIN_BODY_RATIO), MAX_BODY_RATIO)
    height_cm = round(DEFAULT_HEAD_CM * ratio, 1)
    body_type = "胖" if ratio <= 3.0 else ("标准" if ratio <= 5.5 else "瘦")
    head_span = (round(head_box[1] / H, 3), round((head_box[1] + head_box[3]) / H, 3))
    meta = {
        **candidate_meta,
        **face_fields,
        "source": source_name,
        "head_box": list(head_box),
        "head_span": head_span,  # M1.3：实测头部纵向占比（先展示，暂不替代先验）
        "body_ratio": round(ratio, 2),
        "head_cm_anchor": DEFAULT_HEAD_CM,
        "note": source_note,
    }
    features = [f"主色调 {c}" for c in colors[:2]] or ["本地视觉估算"]
    return ImageAnalysis(
        body_type=body_type,
        head_diameter_cm=DEFAULT_HEAD_CM,
        height_cm=height_cm,
        main_features=features,
        pose="站立",
        difficulty="easy",
        parts=parts,
        recommended_colors=colors or None,
    ), meta
