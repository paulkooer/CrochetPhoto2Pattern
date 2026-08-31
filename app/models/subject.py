"""Subject segmentation —— 照片主体掩码（配色/剖面/色板共用的单一来源）。

依据（已联网核实）：
- GrabCut（Rother, Kolmogorov & Blake, "GrabCut: Interactive Foreground
  Extraction Using Iterated Graph Cuts", SIGGRAPH 2004）——GMM 建模 +
  图割精修，OpenCV 自带实现（cv2.grabCut），本仓已依赖
  opencv-python-headless——零新依赖。
- Otsu（Nobuyuki Otsu, "A Threshold Selection Method from Gray-Level
  Histograms", IEEE Trans. SMC 1979）——种子距离阈值对图像对比度
  自适应（低对比度图固定阈值分不出主体/背景）。

分割架构：确定性背景 = 顶+左右条带（主体常贴底边）；前景种子按"到背景
色集合的距离"三档（阈值 = clamp(Otsu(距离分布), 16, 96)），haar 人脸框
（检出时）作为确定性前景种子锚定头部。失败回退：cv2 缺失/图过小/分割
退化（主体占比 <5% 或 >95%）→ None，调用方走旧的背景阈值启发式。
全流程确定性（颜色统计 + Otsu + haar 均无随机性）。
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional, Tuple

from PIL import Image

if TYPE_CHECKING:
    import numpy as np

logger = logging.getLogger(__name__)

# 主体面积占比的合理区间：低于=没分出主体，高于=背景没剔除（分割不可信）
_MIN_SUBJECT_FRAC = 0.05
_MAX_SUBJECT_FRAC = 0.95

# 种子距离阈值的界：下限 16 = 16 级/通道量化的桶距（相邻桶 L1 ≥16，量化
# 噪声 <16，低于它的"不可解释"不可信）；上限 96 = 旧固定口径 2×48，
# 高对比图（Otsu t 很大）封顶后行为与上一版一致。
_T_FLOOR = 16
_T_CEIL = 96
# FGD 确定前景的绝对下限：浅肤色 vs 白背景的 L1 距离实测仅 ~184，2T=192
# 恰好漏掉（头部被吞、色板只剩衣服色——N-G）。144 ≈ 全距的 19%，低于它
# 不足以判"确定前景"（JPEG 噪声 <48），高于它的浅色主体可靠捕获。
_FGD_FLOOR = 144


def _otsu_threshold(values) -> Optional[int]:
    """Otsu (1979) 自动阈值：类间方差最大的距离分割点。

    依据：Nobuyuki Otsu, "A Threshold Selection Method from Gray-Level
    Histograms", IEEE Trans. SMC 9(1), 1979——对双峰分布（背景可解释像素
    vs 主体像素）给出最优分割，替代对图像对比度不自适应的固定阈值。
    分布退化（单峰/空）返回 None，调用方回退固定阈值。
    """
    import numpy as np

    hist = np.bincount(values.ravel(), minlength=766).astype(np.float64)
    total = hist.sum()
    if total <= 0:
        return None
    levels = np.arange(len(hist), dtype=np.float64)
    w0 = np.cumsum(hist)
    w1 = total - w0
    valid = (w0 > 0) & (w1 > 0)
    if not valid.any():
        return None
    sum_all = (hist * levels).sum()
    cum = np.cumsum(hist * levels)
    mu0 = np.where(w0 > 0, cum / np.maximum(w0, 1), 0)
    mu1 = np.where(w1 > 0, (sum_all - cum) / np.maximum(w1, 1), 0)
    between = w0 * w1 * (mu0 - mu1) ** 2
    between[~valid] = -1
    # 双尖峰分布的类间方差在整段峰间区间持平——取最大平台的中点
    # （惯例的"峰间分割点"），而非 argmax 命中的区间起点。
    cands = np.flatnonzero(between == between.max())
    t = int(cands[len(cands) // 2])
    return t if valid[t] else None


def _face_box(small: Image.Image):
    """haar 人脸框（small 坐标系）——GrabCut 的确定性前景种子。

    检测器供种是 GrabCut 论文交互式分割的自动化等价物（框外确定背景、
    框内可能前景 → 反过来：检测框内确定前景）。haar 不可用/未检出返回
    None，种子退回颜色距离分档（行为不受影响）。
    """
    try:
        from .local_vision import _detect_face
        return _detect_face(small)
    except Exception as e:
        logger.debug("face seed unavailable: %s", e)
        return None


def extract_subject(
    image: Image.Image, max_side: int = 160
) -> Optional[Tuple["np.ndarray", Image.Image]]:
    """GrabCut 主体分割。

    Args:
        image:    任意模式 PIL 图。
        max_side: 先缩到该边长内再分割（分割质量与耗时的平衡点；
                  返回的 mask 与小图逐像素对齐，调用方直接配合使用）。

    Returns:
        (mask, small_image)：mask 是与 small_image 同尺寸的 bool 二维数组
        （True=主体像素），small_image 是缩放后的 RGB 图。
        cv2 不可用 / 图过小 / 分割退化 → None（调用方回退启发式）。
    """
    try:
        import cv2
        import numpy as np
    except ImportError:
        logger.debug("cv2/numpy 不可用，主体分割回退启发式")
        return None
    try:
        img = image.convert("RGB")
        img = img.copy()
        img.thumbnail((max_side, max_side))
        arr = np.asarray(img)[:, :, ::-1].copy()  # RGB → BGR（cv2 连续内存）
        h, w = arr.shape[:2]
        if h < 20 or w < 20:
            return None
        # 无交互分割用 mask 初始化（Rother 2004 的 incomplete labelling）。
        # 确定性背景 = 顶部整条 + 左右整条（人像/玩偶照构图先验：顶与两侧
        # 几乎总有留白），底部中央保持可能前景——主体常贴底边。
        # 前景种子按"与背景色解释力的距离"分三档（背景色集合 = 条带全部
        # 量化色，不只众数——双色背景的第二种色也在其中，不会被误标前景）：
        #   GC_FGD  确定前景：与任何背景色距离都远（GrabCut 的数据项/平滑项
        #           会把与主体断开的小孤立块整体翻成背景——实测深色头部被
        #           吞，必须强制保留）
        #   GC_PR_FGD 可能前景：启发式（四角众数）距离超阈
        #   GC_PR_BGD 其余：交给 GMM+图割精修
        rgb16 = arr[:, :, ::-1].astype(np.int16)
        from .color_design import _BG_DIST_THRESHOLD
        kt, ks = max(2, h // 12), max(2, w // 12)
        strips = np.concatenate([
            rgb16[:kt].reshape(-1, 3), rgb16[:, :ks].reshape(-1, 3),
            rgb16[:, w - ks:].reshape(-1, 3),
        ])
        # 条带颜色按 16 级/通道量化取代表色（集合，非众数——双色背景的
        # 第二种色多在侧条带占 20%+，不会漏）。覆盖率门槛 15%：条带可能被
        # 主体上沿侵入（头部贴顶的照片），小占比的主体色不得成为"可解释
        # 的背景色"，否则主体小孤立块会被数据项判回背景（实测头部被吞）。
        qb = (strips // 16).astype(np.int32)
        packed = qb[:, 0] * 256 + qb[:, 1] * 16 + qb[:, 2]
        uniq, counts = np.unique(packed, return_counts=True)
        bg_reps = np.array([[(u >> 8 & 15) * 16 + 8, (u >> 4 & 15) * 16 + 8,
                             (u & 15) * 16 + 8] for u in uniq], dtype=np.int16)
        coverage = np.array([c / len(strips) for c in counts])
        if (coverage >= 0.15).any():
            bg_reps = bg_reps[coverage >= 0.15]

        img_q = (rgb16 // 16).astype(np.int32)
        img_packed = (img_q[..., 0] * 256 + img_q[..., 1] * 16 + img_q[..., 2])
        # 距离矩阵：图像出现的桶 × 背景桶，每像素查表得最近背景距离
        img_uniq, img_inv = np.unique(img_packed, return_inverse=True)
        img_colors = np.array([[(u >> 8 & 15) * 16 + 8, (u >> 4 & 15) * 16 + 8,
                                (u & 15) * 16 + 8] for u in img_uniq],
                              dtype=np.int16)
        dmat = np.abs(img_colors[:, None, :] - bg_reps[None, :, :]).sum(axis=2)
        min_by_bucket = dmat.min(axis=1)
        px_min_dist = min_by_bucket[img_inv].reshape(h, w)

        # 三档种子只看"到背景色集合的最近距离"，阈值 T 自适应：
        #   T = clamp(Otsu(距离分布), 16, 96)，退化回退固定 48
        # Otsu 对低对比度图（主体/背景 L1 距 < 48，固定阈值分不出）自动
        # 下探；高对比图封顶 96 保持与固定阈值版一致的行为。
        #   > 2T  任何背景色都解释不了 → 确定前景
        #   > T   弱不可解释 → 可能前景（给 GMM 的前景候选带）
        #   ≤ T   背景色可解释 → 可能背景
        t_otsu = _otsu_threshold(px_min_dist)
        if t_otsu is None:
            t_seed = _BG_DIST_THRESHOLD
        else:
            t_seed = min(_T_CEIL, max(_T_FLOOR, t_otsu))
        mask = np.full((h, w), cv2.GC_PR_BGD, np.uint8)
        _fgd_t = max(1.5 * t_seed, _FGD_FLOOR)
        mask[px_min_dist > _fgd_t] = cv2.GC_FGD
        mask[(px_min_dist > t_seed)
             & (px_min_dist <= _fgd_t)] = cv2.GC_PR_FGD
        # 人脸框 = 确定性前景种子：头部颜色与背景相近（白墙前的浅色头发/
        # 近肤色背景）时颜色分档救不了头部，检测框直接锚定（GrabCut 的检测器
        # 供种用法）。面积约束防误检 dominates：过大的框（>50% 图幅）弃用。
        box = _face_box(img)
        if box is not None:
            fx, fy, fw, fh = box
            if 0.003 <= (fw * fh) / (w * h) <= 0.5:
                mask[fy:fy + fh, fx:fx + fw] = cv2.GC_FGD
        # 确定性背景条带最后强制写入：种子展开不得覆盖（否则 GMM 样本
        # 为空，grabCut 直接断言失败）
        mask[:kt, :] = cv2.GC_BGD
        mask[:, :ks] = cv2.GC_BGD
        mask[:, w - ks:] = cv2.GC_BGD
        bgd = np.zeros((1, 65), np.float64)
        fgd = np.zeros((1, 65), np.float64)
        cv2.grabCut(arr, mask, None, bgd, fgd, 5, cv2.GC_INIT_WITH_MASK)
        subject = (mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD)
        # 腐蚀 1px：thumbnail 重采样的主体边界是前景/背景混色（1–2px），
        # 是全图最不可靠的像素——会污染窄带的颜色均值。均匀内缩对剖面
        # 形状无影响（归一化后不变）。
        subject = cv2.erode(subject.astype(np.uint8),
                            np.ones((3, 3), np.uint8)).astype(bool)
        frac = float(subject.mean())
        if frac < _MIN_SUBJECT_FRAC or frac > _MAX_SUBJECT_FRAC:
            logger.debug("GrabCut 分割退化（主体占比 %.2f），回退启发式", frac)
            return None
        # G2（升级）：区域交叉校验——丢头判定不能只看 GrabCut 掩码
        # （坐姿/远景照的顶部本来就空，会误拒）。正确信号是**分歧**：
        # 启发式（背景距离）认为顶部 1/3 有非背景像素，但 GrabCut 掩码
        # 在同一区域几乎无主体 → GMM 内部翻转吞掉了头部。
        top_dist = px_min_dist[:h // 3]
        top_heuristic = float((top_dist > _BG_DIST_THRESHOLD).mean())
        top_grabcut = float(subject[:h // 3].mean())
        if top_heuristic > 0.01 and top_grabcut < 0.5 * top_heuristic:
            logger.debug(
                "GrabCut 分割丢头（顶部启发式 %.3f vs 掩码 %.3f），回退启发式",
                top_heuristic, top_grabcut)
            return None
        return subject, img
    except Exception as e:
        logger.debug("subject segmentation failed: %s", e)
        return None
