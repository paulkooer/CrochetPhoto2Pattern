"""Local (no-LLM) photo analysis — the default photo-analysis path.

默认本地分析：OpenCV 人脸检测给出头部像素框，按
"头径锚点 × 人体比例" 推算 ImageAnalysis。

能力边界（如实声明）：
- 比例（身高/头径的倍数）来自照片实际检测 ✓
- 绝对尺度（头径是多少厘米）单张照片无参照无法得到；这里用 9cm
  作为内部比例参考，PipelineOrchestrator 随后按用户目标高度重新缩放
- 部件列表/姿态/难度无法本地语义推断，按规范默认值填充
"""
from __future__ import annotations

import logging
from typing import Any

from PIL import Image

from ..schemas import ImageAnalysis
from .geometry import has_bottom_flare as _has_bottom_flare
from .geometry import silhouette_profile as _silhouette_profile
from .image_parser import extract_color_palette
from .subject import SubjectObservation

logger = logging.getLogger(__name__)

DEFAULT_HEAD_CM = 9.0      # 内部比例参考；不是照片实测，管线随后按目标高度缩放
FRAME_FILL_RATIO = 0.9     # 假设主体大致占满画面高度（全身玩偶照常见构图）
MIN_BODY_RATIO = 2.0       # 身高/头径 的合理区间（大头 Q 版 … 全身成人照）
MAX_BODY_RATIO = 8.0

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
    rows = [i for i, width in enumerate(profile or []) if width > 0.08]
    if rows and profile:
        return rows[0] / len(profile) * height, (rows[-1] + 1) / len(profile) * height
    return 0.0, height * FRAME_FILL_RATIO


def _face_rejection_reason(image: Image.Image, box, profile: list[float] | None) -> str | None:
    """Conservative checks for an upright subject, not semantic face verification.

    Sideways poses and unusual proportions require manual review. These bounds
    reject unsuitable candidates rather than clamp them into plausible measurements.
    """
    x, y, width, height = box
    if width <= 0 or height <= 0 or x < 0 or y < 0 or x + width > image.width or y + height > image.height:
        return "检测框超出图片或没有面积"
    top, bottom = _subject_vertical_extent(profile, image.height)
    center = y + height / 2
    if center < top or center > top + (bottom - top) / 2:
        return "检测框不在主体上半部，不能自动作为直立玩偶头部"
    if (bottom - top) / max(width, height) > MAX_BODY_RATIO:
        return "检测框相对主体过小，无法可靠推算头身比例"
    return None


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
    candidate_meta: dict[str, Any] = {
        "parts_source": "default_template", "requires_subject_review": True,
        "subject_type": "unclassified",
        "possible_skirt": bool(profile is not None and _has_bottom_flare(profile)),
    }
    if box is not None:
        rejection = _face_rejection_reason(image, box, profile)
        if rejection:
            candidate_meta.update(rejected_face_box=list(box), face_rejection_reason=rejection)
            box = None

    if box is None:
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

    _x, _y, face_w, face_h = box
    head_px = max(face_w, face_h, 1)
    top, bottom = _subject_vertical_extent(profile, H)
    subject_px = bottom - top
    ratio = min(max(subject_px / head_px, MIN_BODY_RATIO), MAX_BODY_RATIO)
    height_cm = round(DEFAULT_HEAD_CM * ratio, 1)
    body_type = "胖" if ratio <= 3.0 else ("标准" if ratio <= 5.5 else "瘦")
    head_span = (round(box[1] / H, 3), round((box[1] + box[3]) / H, 3))
    meta = {
        **candidate_meta,
        "source": "opencv-face",
        "face_box": [int(v) for v in box],
        "head_span": head_span,  # M1.3：实测头部纵向占比（先展示，暂不替代先验）
        "body_ratio": round(ratio, 2),
        "head_cm_anchor": DEFAULT_HEAD_CM,
        "note": (
            "比例来自待确认的人脸候选框，部件来自模板；单图没有绝对尺度，"
            "厘米尺寸由生成时选择的目标高度决定"
        ),
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
