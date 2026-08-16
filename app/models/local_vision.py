"""Local (no-LLM) photo analysis — the vision-free fallback path.

无 API Key 时的本地降级：OpenCV 人脸检测给出头部像素框，按
"头径锚点 × 人体比例" 推算 ImageAnalysis。

能力边界（如实声明）：
- 比例（身高/头径的倍数）来自照片实际检测 ✓
- 绝对尺度（头径是多少厘米）单张照片无参照无法得到，按 Amigurumi
  常见值 9cm 锚定，用户应在局部修正中核对
- 部件列表/姿态/难度无法本地语义推断，按规范默认值填充
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image

from ..schemas import ImageAnalysis
from .color_design import _BG_DIST_THRESHOLD  # 统一主体判定阈值（单一来源）
from .image_parser import extract_color_palette

logger = logging.getLogger(__name__)

DEFAULT_HEAD_CM = 9.0      # 头径锚点：单张照片无尺度参照
FRAME_FILL_RATIO = 0.9     # 假设主体大致占满画面高度（全身玩偶照常见构图）
MIN_BODY_RATIO = 2.0       # 身高/头径 的合理区间（大头 Q 版 … 全身成人照）
MAX_BODY_RATIO = 8.0

_CANONICAL_PARTS = ["头部", "身体", "手臂", "腿部"]


def _detect_face(img: Image.Image) -> Optional[Tuple[int, int, int, int]]:
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
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )
    faces = cascade.detectMultiScale(
        gray, scaleFactor=1.1, minNeighbors=5, minSize=(24, 24)
    )
    if len(faces) == 0:
        return None
    x, y, w, h = max(faces, key=lambda f: int(f[2]) * int(f[3]))  # 取主体（最大脸）
    return int(x), int(y), int(w), int(h)


def _silhouette_profile(image: Image.Image, n_rows: int = 40) -> Optional[List[float]]:
    """主体宽度剖面（自上而下，0~1 归一化）——让照片轮廓参与形状设计。

    背景 = 四角众数色；每行统计"非背景像素"占比。主体过小时返回 None。
    """
    try:
        import numpy as np
    except ImportError:
        return None
    try:
        img = image.convert("RGB")
        img.thumbnail((120, 120))
        px = np.asarray(img, dtype=np.int16)
        h, w = px.shape[:2]
        if h < n_rows or w < 4:
            return None
        from .color_design import estimate_background
        bg = np.array(estimate_background(px), dtype=px.dtype)
        widths = []
        for i in range(n_rows):
            y0, y1 = h * i // n_rows, h * (i + 1) // n_rows
            row = px[y0:y1].reshape(-1, 3)
            dist = np.abs(row - bg).sum(axis=1)
            widths.append(float((dist > _BG_DIST_THRESHOLD).mean()))
        peak = max(widths)
        if peak < 0.05:  # 几乎没有主体（纯背景图）
            return None
        return [x / peak for x in widths]
    except Exception as e:
        logger.debug("silhouette extraction failed: %s", e)
        return None


def _has_bottom_flare(profile: List[float]) -> bool:
    """下摆展开判定：底部 1/4 的平均宽度明显大于中段（裙摆/A 字轮廓）。"""
    n = len(profile)
    lower = profile[int(n * 0.72):int(n * 0.95)]
    middle = profile[int(n * 0.42):int(n * 0.62)]
    if not lower or not middle:
        return False
    return (sum(lower) / len(lower)) > 1.25 * (sum(middle) / len(middle))


def analyze(image: Image.Image, n_colors: int = 5) -> Tuple[ImageAnalysis, Dict[str, Any]]:
    """Estimate an ImageAnalysis from the photo without any LLM call.

    Returns (analysis, meta)；meta 描述估算来源与依据，供 UI 透明展示。
    """
    colors = extract_color_palette(image, n_colors=n_colors)
    H = image.size[1]
    box = _detect_face(image)
    # 轮廓剖面：下摆展开 → 主体是裙形，自动补"裙子"部件
    profile = _silhouette_profile(image)
    parts = list(_CANONICAL_PARTS)
    silhouette: Dict[str, Any] = {}
    if profile is not None:
        # M1.1：完整剖面透传下游（此前只消费了一个裙摆布尔——信息漏斗）
        silhouette = {"profile": [round(v, 3) for v in profile]}
        if _has_bottom_flare(profile):
            parts.append("裙子")
            silhouette["flare"] = True
            silhouette["note"] = "检测到下摆展开的轮廓，已自动添加裙子部件"

    if box is None:
        meta: Dict[str, Any] = {
            "source": "default",
            "note": "未检测到人脸，使用默认 Q 版比例",
            **({"silhouette": silhouette} if silhouette else {}),
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
    # M1.4：主体高度取剖面首/末超阈行（此前用 0.9×图高盲设）
    if profile is not None:
        rows = [i for i, w in enumerate(profile) if w > 0.08]
        subject_px = ((rows[-1] - rows[0] + 1) / len(profile)) * H if rows else H * 0.9
    else:
        subject_px = H * FRAME_FILL_RATIO
    ratio = min(max(subject_px / head_px, MIN_BODY_RATIO), MAX_BODY_RATIO)
    height_cm = round(DEFAULT_HEAD_CM * ratio, 1)
    body_type = "胖" if ratio <= 3.0 else ("标准" if ratio <= 5.5 else "瘦")
    head_span = (round(box[1] / H, 3), round((box[1] + box[3]) / H, 3))
    meta = {
        "source": "opencv-face",
        "face_box": [int(v) for v in box],
        "head_span": head_span,  # M1.3：实测头部纵向占比（先展示，暂不替代先验）
        "body_ratio": round(ratio, 2),
        "head_cm_anchor": DEFAULT_HEAD_CM,
        "note": (
            "比例来自本地人脸检测，头径按默认 9cm 锚定——"
            "请核对后在「局部修正」中调整实际头径"
        ),
        **({"silhouette": silhouette} if silhouette else {}),
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
