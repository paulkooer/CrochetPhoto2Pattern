"""Pose-driven measured spans（S1）——姿态关键点 → 部件纵向占比实测。

依据（已联网核实）：MediaPipe Pose Landmarker（Google AI Edge，Apache-2.0，
33 个 3D 关键点，CPU 实时）——肩(11/12)、髋(23/24)、膝(25/26)、踝(27/28)、
腕(15/16)、鼻(0)、眼(2/5)。作为可选依赖（pip install
crochet-photo2pattern[pose]），缺失/失败时回退 PART_SPAN 先验。

版本约束 0.10.20–0.10.21（选型与 CI 结论）：1.0.1 在 macOS arm64 上原生
崩溃（Metal 图初始化 Check failed: service_，强制 CPU 代理同样崩溃）；
0.10.30 起的 ctypes Image 绑定又在 Linux 出现构造失败后的析构异常。旧绑定
版本的 Tasks API 满足当前能力，并由 extras CI 固定验证。

为什么需要：PART_SPAN 是"常规 Q 版比例"先验，坐姿/特写/仰拍照片的
部件分段会偏（handoff §4.1 残留）。实测 span 用照片里真实的人体关键点
（归一化到全图 0..1，与色带坐标同系），先验只兜底。

工程约束（选型实验记录）：新版本 mediapipe 依赖 opencv-contrib-python 5.0，
与项目 opencv-python-headless<5 冲突——因此 mediapipe 必须保持**可选**，
主依赖不引入；模型文件（~5.8MB）首次使用时下载缓存，离线/失败 → None。
"""
from __future__ import annotations

import logging
import os
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

MODEL_URL = ("https://storage.googleapis.com/mediapipe-models/"
             "pose_landmarker/pose_landmarker_lite/float16/1/"
             "pose_landmarker_lite.task")

# 供应链完整性：固定版本模型（float16/1）的 SHA256（T1）。下载后不匹配
# 即删除并回退先验 span——绝不使用被篡改的权重。
MODEL_SHA256 = "59929e1d1ee95287735ddd833b19cf4ac46d29bc7afddbbf6753c459690d574a"

# 关键点 index（MediaPipe Pose 规范）
_NOSE, _EYE_L, _EYE_R = 0, 2, 5
_SHOULDER_L, _SHOULDER_R = 11, 12
_WRIST_L, _WRIST_R = 15, 16
_HIP_L, _HIP_R = 23, 24
_KNEE_L, _KNEE_R = 25, 26
_ANKLE_L, _ANKLE_R = 27, 28

# 关键点可见性阈值：被遮挡/置信度低的部位不参与实测
_MIN_VISIBILITY = 0.5


def _sha256_of(path: Path) -> str:
    import hashlib

    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def model_path() -> Optional[Path]:
    """模型文件路径；缺失时下载缓存（含 SHA256 校验）。失败返回 None。

    CROCHET_POSE_MODEL 指向用户自备模型时不校验（信任本地文件）。
    """
    env = os.getenv("CROCHET_POSE_MODEL")
    if env:
        p = Path(env)
        return p if p.is_file() else None
    cache = Path.home() / ".cache" / "crochet_photo2pattern"
    path = cache / "pose_landmarker_lite.task"
    if path.is_file():
        if _sha256_of(path) == MODEL_SHA256:
            return path
        logger.warning("缓存的 pose 模型校验失败，重新下载")
        path.unlink()
    try:
        cache.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        urllib.request.urlretrieve(MODEL_URL, tmp)  # noqa: S310 固定 URL
        if _sha256_of(tmp) != MODEL_SHA256:
            logger.warning("pose 模型校验和不匹配，拒绝使用（回退先验 span）")
            tmp.unlink()
            return None
        tmp.replace(path)
        return path
    except Exception as e:
        logger.info("pose 模型下载失败（回退先验 span）: %s", e)
        return None


def get_body_landmarks(image) -> Optional[Dict[str, Any]]:
    """照片 → 归一化关键点（0..1，全图坐标）。

    Returns {"nose": (y), "eye_top", "shoulder", "hip", "knee",
             "ankle", "wrist", "points": [(y, visibility), ...]}
    mediapipe 不可用 / 模型缺失 / 未检出人形 → None。
    """
    try:
        import mediapipe as mp
        import numpy as np
    except ImportError:
        logger.debug("mediapipe 未安装（可选依赖 [pose]），回退先验 span")
        return None
    path = model_path()
    if path is None:
        return None
    try:
        from mediapipe.tasks import python as mp_python
        from mediapipe.tasks.python import vision

        arr = np.asarray(image.convert("RGB"))
        rgb = mp.Image(image_format=mp.ImageFormat.SRGB, data=arr)
        opts = mp_python.BaseOptions(model_asset_path=str(path))
        with mp_python.PoseLandmarker.create_from_options(
                vision.PoseLandmarkerOptions(
                    base_options=opts,
                    running_mode=vision.RunningMode.IMAGE,
                    num_poses=1)) as landmarker:
            result = landmarker.detect(rgb)
        if not result.pose_landmarks:
            return None
        pts = result.pose_landmarks[0]

        def y(idx: int) -> Optional[float]:
            p = pts[idx]
            if p.visibility is not None and p.visibility < _MIN_VISIBILITY:
                return None
            return float(min(max(p.y, 0.0), 1.0))

        def mid(a: int, b: int) -> Optional[float]:
            ya, yb = y(a), y(b)
            if ya is None or yb is None:
                return None
            return (ya + yb) / 2.0

        lm: Dict[str, Any] = {
            "nose": y(_NOSE),
            "eye_top": min(v for v in (y(_EYE_L), y(_EYE_R)) if v is not None)
            if any(y(i) is not None for i in (_EYE_L, _EYE_R)) else None,
            "shoulder": mid(_SHOULDER_L, _SHOULDER_R),
            "hip": mid(_HIP_L, _HIP_R),
            "knee": mid(_KNEE_L, _KNEE_R),
            "ankle": mid(_ANKLE_L, _ANKLE_R),
            "wrist": mid(_WRIST_L, _WRIST_R),
        }
        required = ("nose", "shoulder", "hip")
        if any(lm[k] is None for k in required):
            return None
        return lm
    except Exception as e:
        logger.debug("pose landmark failed: %s", e)
        return None


def measured_spans(lm: Dict[str, Any]) -> Dict[str, Any]:
    """关键点 → 部件纵向 span（0 顶 → 1 底，与 PART_SPAN 同坐标系）。

    人体学映射（近似的比例系数按美术常识，元数据透明展示）：
      头部 = 眼上缘 ≈ 眼距鼻同长的头顶估算 → 鼻与肩之间偏下
      身体 = 肩中 → 髋中稍下；手臂 = 肩 → 腕（垂手）；
      腿部 = 髋 → 踝；裙子 = 髋 → 膝；帽子/耳朵取头部区间的上/下段；
      尾巴无法从正面关键点测得 → 调用方回退先验。
    """
    nose, eye_top = lm["nose"], lm.get("eye_top")
    shoulder, hip = lm["shoulder"], lm["hip"]
    knee, ankle, wrist = lm.get("knee"), lm.get("ankle"), lm.get("wrist")

    head_top = eye_top - (nose - eye_top) if eye_top is not None else None
    if head_top is None or head_top < 0:
        head_top = max(0.0, nose - (shoulder - nose) * 0.6)
    head_bottom = nose + (shoulder - nose) * 0.4
    head = (head_top, head_bottom)
    head_len = head_bottom - head_top

    # 髋 = 身体/腿部精确分界（不得重叠——重叠段会让色带被两个部件重复取用）
    spans: Dict[str, Any] = {
        "头部": head,
        "身体": (shoulder, hip),
        "手臂": (shoulder, max(wrist or hip, hip)),
    }
    if knee is not None:
        spans["腿部"] = (hip, max(ankle or knee, knee))
        spans["裙子"] = (hip, knee)
    spans["帽子"] = (head_top, head_top + head_len * 0.55)
    spans["耳朵"] = (head_top + head_len * 0.35, head_bottom)
    # 净化：s<e 且在 0..1 内，非法部件回退先验（调用方按缺失处理）
    clean: Dict[str, Any] = {}
    for name, (s, e) in spans.items():
        s, e = min(max(s, 0.0), 1.0), min(max(e, 0.0), 1.0)
        if e - s > 0.02:
            clean[name] = (round(s, 4), round(e, 4))
    return clean


def format_span_hints(spans: Dict[str, Any]) -> Optional[str]:
    """实测 span → prompt 附加参考文案（T6，S1×LLM 协同）。

    让 Vision 模型的 parts 判断与几何实测交叉验证；无实测返回 None。
    """
    if not spans:
        return None
    segs = "、".join(
        f"{name} {s:.2f}–{e:.2f}" for name, (s, e) in sorted(
            spans.items(), key=lambda kv: kv[1][0]))
    return ("【几何参考】已从照片测得人物各部位的纵向占比（0=图顶，1=图底，"
            f"供 parts 判断交叉验证）: {segs}。")
