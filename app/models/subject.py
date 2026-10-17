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
色集合的距离"分**两个通道**取并集——亮度档（L1，阈值 = clamp(Otsu(距离
分布), 16, 96)）与色度档（YCrCb 的 |ΔCr|+|ΔCb|，阈值 = clamp(Otsu, 8, 48)），
haar 人脸框（检出时）作为确定性前景种子锚定头部。色度档只做加法：浅色主体
亮度常与半透明阴影重叠（实测兔子 L1 69–111 夹在阴影 70 里），色度却能分开；
但"比背景暗的中性像素"不能反判为背景（实测会把深灰/中灰玩偶判没，半透明
水印也照样留下），去水印仍由确认页手工修掩码。失败回退：cv2 缺失/图过小/
分割退化（主体占比 <5% 或 >95%）→ None，调用方走旧的背景阈值启发式。
颜色统计、Otsu 与 haar 不使用随机初始化；GrabCut 的 GMM 初始化固定 RNG
种子，同一运行环境内重复分割可复现（不承诺跨 OpenCV 版本逐像素一致）。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import cached_property
from typing import TYPE_CHECKING

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

# 色度分档（YCrCb 的 Cr/Cb 相对背景色度偏离之和，量纲与上面同）：
# 阴影与水印都是"背景的等比例变暗"，色度几乎不变（实测 ≤7）；浅粉/浅棕主体
# 亮度虽与阴影重叠（实测兔子 L1 69–111 夹在阴影 70 里），色度却高出数倍
# （兔子 19 vs 阴影 5、水印 7）。下限 8 取"背景/阴影/水印"实测上限之上，
# 上限 48 与亮度档同量级；确定前景下限 12 高于水印/阴影而低于浅色主体。
_T_CHROMA_FLOOR = 8
_T_CHROMA_CEIL = 48
_CHROMA_FGD_FLOOR = 12

# 配色投票时把"阴影/半透明水印"排除在外的判据：**比背景更暗**且**成片**。
# 阴影与水印都是"同一表面被等比例压暗"——色度几乎不变、亮度明显下降，单看
# 颜色与主体分不开（实测真照片的兔子暗部因此被映射成"深灰色"，凭空多出第二
# 色）。所以还必须成片：细条纹、小斑块是真实深色特征（黑眼珠、深棕口鼻、衣服
# 条纹），必须留在配色里（实测 4px 黑条纹在 k≥5 的开运算下清空，真照片的阴影
# 在 k=5~7 时仍保留 80% 以上）。**只用于配色取样**，几何掩码、证据记录与分割
# 一律用全量像素：剔除用在分割上会把深灰/中灰玩偶整只判没（见 extract_subject）。
_SHADED_LUMA_RATIO = 0.8
_SHADED_MIN_SPAN = 20     # 开运算核 ≈ 短边 / 20（160px 图上 8px，至少 5px）


@dataclass
class SubjectObservation:
    """One pipeline run's shared subject pixels, including failed extraction.

    Geometry retains the un-eroded 160px mask. Palette and bands share a
    derived interior mask, without running segmentation a second time.
    This object is transient and must not be reused after editing its image.
    """

    image: Image.Image

    @classmethod
    def from_reviewed_mask(cls, image: Image.Image, mask: np.ndarray,
                           small: Image.Image) -> SubjectObservation:
        """Own a corrected mask with fresh color caches and no re-segmentation."""
        if mask.shape != (small.height, small.width) or max(small.size) > 160:
            raise ValueError("修正掩码与图片尺寸不一致")
        observation = cls(image)
        observation.__dict__["segmentation"] = (mask.astype(bool).copy(), small.copy())
        return observation

    @cached_property
    def segmentation(self) -> tuple[np.ndarray, Image.Image] | None:
        try:
            return extract_subject(self.image, max_side=160)
        except Exception as exc:
            logger.debug("shared subject observation unavailable: %s", exc)
            return None

    def extract(self, image: Image.Image) -> tuple[np.ndarray, Image.Image] | None:
        if image is not self.image:
            raise ValueError("主体观测只能用于创建它的图片")
        return self.segmentation

    @cached_property
    def color_segmentation(self) -> tuple[np.ndarray, Image.Image] | None:
        return color_interior(self.segmentation)

    def extract_colors(self, image: Image.Image) -> tuple[np.ndarray, Image.Image] | None:
        if image is not self.image:
            raise ValueError("主体观测只能用于创建它的图片")
        return self.color_segmentation

    @cached_property
    def lit_segmentation(self) -> tuple[np.ndarray, Image.Image] | None:
        """配色投票用：剔出阴影/水印的受光面取样（证据记录仍用完整内景）。"""
        return color_interior(self.segmentation, lit_only=True)

    def extract_lit_colors(self, image: Image.Image) -> tuple[np.ndarray, Image.Image] | None:
        if image is not self.image:
            raise ValueError("主体观测只能用于创建它的图片")
        return self.lit_segmentation


def shaded_area(mask, image):
    """``mask`` 内**成片**且比背景更暗的区域——阴影/半透明水印，不是主体本色。

    阴影与水印都是"同一表面被等比例压暗"：色度几乎不变、亮度明显下降，单看
    颜色与主体分不开（实测真照片的暗部就是暖米白主体的变暗）。所以判据必须
    再加"成片"：细条纹、小斑块这类深色结构是真实特征，要留在配色里；只有大到
    一定跨度的暗区才当阴影（实测 4px 黑条纹在 k≥5 的开运算下清空，而真照片的
    阴影在 k=5~7 时仍保留 80% 以上）。
    """
    import cv2
    import numpy as np

    rgb8 = np.asarray(image.convert("RGB"), dtype=np.uint8)
    if mask.shape != rgb8.shape[:2]:
        return np.zeros(mask.shape, bool)
    _reps, rep_luma = background_reps(rgb8.astype(np.int16))
    ycc = cv2.cvtColor(rgb8[:, :, ::-1].copy(), cv2.COLOR_BGR2YCrCb).astype(np.int16)
    dark = mask & (ycc[:, :, 0] < _SHADED_LUMA_RATIO * float(np.median(rep_luma)))
    if not dark.any():
        return dark
    k = max(5, min(mask.shape[:2]) // _SHADED_MIN_SPAN)
    opened = cv2.morphologyEx(dark.astype(np.uint8), cv2.MORPH_OPEN,
                              np.ones((k, k), np.uint8))
    return opened.astype(bool)


def color_interior(
    segmentation: tuple[np.ndarray, Image.Image] | None,
    *, lit_only: bool = False, max_shaded_share: float = 0.4,
) -> tuple[np.ndarray, Image.Image] | None:
    """Remove mixed boundary pixels only for color sampling, never geometry.

    ``lit_only`` also drops the shaded area (see shaded_area), so the colour vote
    reads the lit surface: a single-colour toy photographed with shading must not
    come out as two colours. Guard: this holds only while the lit part stays a
    clear majority (more than ``1 - max_shaded_share``); a darker share
    approaching half may be a body colour rather than shading (a black-and-white
    two-tone toy), which colour alone cannot tell apart, so nothing is dropped.
    The default is the complete interior: the evidence recorded for review must
    not lose the dark details this vote filters out (callers that only vote pass
    ``lit_only=True``).

    An empty interior is unavailable evidence; callers use their existing
    fallback. The input mask is not mutated.
    """
    if segmentation is None:
        return None
    import cv2
    import numpy as np

    mask, image = segmentation
    if mask.shape != (image.height, image.width):
        return None
    interior = cv2.erode(mask.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)
    if not interior.any():
        return None
    if lit_only:
        lit = interior & ~shaded_area(interior, image)
        if lit.sum() >= (1.0 - max_shaded_share) * interior.sum():
            interior = lit
    return (interior, image) if interior.any() else None


def _otsu_threshold(values) -> int | None:
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


def _strip_bounds(h: int, w: int) -> tuple[int, int]:
    """确定性背景条带厚度：顶 h/12、左右 w/12（至少 2 像素）。"""
    return max(2, h // 12), max(2, w // 12)


def background_reps(rgb16) -> tuple[np.ndarray, np.ndarray]:
    """顶+左右条带的背景代表色集合与各代表色亮度（RGB 0-255 / float）。

    条带 = 顶部整条 + 左右整条（人像/玩偶照构图先验：顶与两侧几乎总有留白），
    量化到 16 级/通道取**集合**而非众数——双色背景的第二种色多在侧条带占
    20%+，不会漏。覆盖率门槛 15%：条带可能被主体上沿侵入（头部贴顶的照片），
    小占比的主体色不得成为"可解释的背景色"，否则主体小孤立块会被数据项判回
    背景（实测头部被吞）。

    返回 (代表色 Nx3, 各代表色亮度 N)，让亮度档、色度档与配色取样共用同一份
    背景参考，不各自重算。
    """
    import numpy as np

    kt, ks = _strip_bounds(*rgb16.shape[:2])
    strips = np.concatenate([
        rgb16[:kt].reshape(-1, 3), rgb16[:, :ks].reshape(-1, 3),
        rgb16[:, rgb16.shape[1] - ks:].reshape(-1, 3),
    ])
    qb = (strips // 16).astype(np.int32)
    packed = qb[:, 0] * 256 + qb[:, 1] * 16 + qb[:, 2]
    uniq, counts = np.unique(packed, return_counts=True)
    reps = np.array([[(u >> 8 & 15) * 16 + 8, (u >> 4 & 15) * 16 + 8,
                      (u & 15) * 16 + 8] for u in uniq], dtype=np.int16)
    coverage = np.array([c / len(strips) for c in counts])
    if (coverage >= 0.15).any():
        reps = reps[coverage >= 0.15]
    luma = 0.299 * reps[:, 0] + 0.587 * reps[:, 1] + 0.114 * reps[:, 2]
    return reps, luma


def extract_subject(
    image: Image.Image, max_side: int = 160
) -> tuple[np.ndarray, Image.Image] | None:
    """GrabCut 主体分割。

    Args:
        image:    任意模式 PIL 图。
        max_side: 先缩到该边长内再分割（分割质量与耗时的平衡点；
                  返回的 mask 与小图逐像素对齐，调用方直接配合使用）。

    Returns:
        (mask, small_image)：mask 是与 small_image 同尺寸的 bool 二维数组
        （True=主体像素，未腐蚀），small_image 是缩放后的 RGB 图。
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
        # 前景种子按"与背景色解释力的距离"分档（背景色集合 = 条带全部
        # 量化色，不只众数——双色背景的第二种色也在其中，不会被误标前景）。
        # 亮度（L1）与色度（YCrCb 的 |ΔCr|+|ΔCb|）两个通道各分两档后取并集：
        #   GC_FGD  确定前景：与任何背景色距离都远（GrabCut 的数据项/平滑项
        #           会把与主体断开的小孤立块整体翻成背景——实测深色头部被
        #           吞，必须强制保留）
        #   GC_PR_FGD 可能前景：启发式（四角众数）距离超阈
        #   GC_PR_BGD 其余：交给 GMM+图割精修
        rgb16 = arr[:, :, ::-1].astype(np.int16)
        from .color_design import _BG_DIST_THRESHOLD
        kt, ks = _strip_bounds(h, w)
        bg_reps, rep_luma = background_reps(rgb16)

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

        # ── 色度通道（YCrCb 的 Cr/Cb 相对背景色度）──────────────────────
        # 阴影与水印都是"背景的等比例变暗"，色度基本不变；浅色主体（浅粉/
        # 浅棕/浅灰蓝）亮度虽与阴影重叠，色度却高出一个量级（实测兔子 L1
        # 69–111 夹在阴影 70 里分不开，色度兔子 19 vs 阴影 5、水印 7）。
        # 背景色度取**代表色集合**（与亮度档同一口径），不用条带中位数：
        # 双色背景的色度中位数落在两色之间，会把两种背景色都判成彩色。
        ycc = cv2.cvtColor(arr, cv2.COLOR_BGR2YCrCb).astype(np.int16)
        chroma_dist = None
        for _r, _y in zip(bg_reps.astype(np.float64), rep_luma, strict=True):
            d = (np.abs(ycc[:, :, 1] - ((_r[0] - _y) * 0.713 + 128.0))
                 + np.abs(ycc[:, :, 2] - ((_r[2] - _y) * 0.564 + 128.0)))
            chroma_dist = d if chroma_dist is None else np.minimum(chroma_dist, d)
        chroma_dist = np.asarray(chroma_dist).astype(np.int16)

        # 亮度档阈值自适应（色度档同理，见上）：
        #   T = clamp(Otsu(距离分布), 16, 96)，退化回退固定 48
        # Otsu 对低对比度图（主体/背景 L1 距 < 48，固定阈值分不出）自动
        # 下探；高对比图封顶 96 保持与固定阈值版一致的行为。
        #   > 2T  任何背景色都解释不了 → 确定前景
        #   > T   弱不可解释 → 可能前景（给 GMM 的前景候选带）
        #   ≤ T   背景色可解释 → 可能背景
        t_otsu = _otsu_threshold(px_min_dist)
        t_seed = (_BG_DIST_THRESHOLD if t_otsu is None
                  else min(_T_CEIL, max(_T_FLOOR, t_otsu)))
        t_chr_otsu = _otsu_threshold(chroma_dist)
        t_chroma = (_T_CHROMA_FLOOR if t_chr_otsu is None
                    else min(_T_CHROMA_CEIL, max(_T_CHROMA_FLOOR, t_chr_otsu)))
        chroma_fgd_t = max(1.5 * t_chroma, _CHROMA_FGD_FLOOR)
        mask = np.full((h, w), cv2.GC_PR_BGD, np.uint8)
        _fgd_t = max(1.5 * t_seed, _FGD_FLOOR)
        mask[px_min_dist > _fgd_t] = cv2.GC_FGD
        mask[(px_min_dist > t_seed)
             & (px_min_dist <= _fgd_t)] = cv2.GC_PR_FGD
        # 色度档叠加（与亮度档取并集，只升不降）：浅色主体往往亮度不可分、
        # 色度可分；中性主体色度≈0 时本档不动，行为与只有亮度档时一致。
        # 不反过来把“比背景暗的中性像素”降级成背景：实测那样做会把中性主体
        # （深灰/中灰玩偶）整只判没，而半透明水印依然留在掩码里——色度不负责
        # 去水印，只负责别把有色的主体丢掉。
        mask[chroma_dist > chroma_fgd_t] = cv2.GC_FGD
        mask[(chroma_dist > t_chroma) & (chroma_dist <= chroma_fgd_t)
             & (mask != cv2.GC_FGD)] = cv2.GC_PR_FGD
        # 人脸框 = 确定性前景种子：头部颜色与背景相近（白墙前的浅色头发/
        # 近肤色背景）时颜色分档救不了头部，检测框直接锚定（GrabCut 的检测器
        # 供种用法）。面积约束防误检 dominates：过大的框（>50% 图幅）弃用。
        box = _face_box(img)
        if box is not None:
            fx, fy, fw, fh = box
            if (0 <= fx < fx + fw <= w and 0 <= fy < fy + fh <= h
                    and 0.003 <= (fw * fh) / (w * h) <= 0.5):
                mask[fy:fy + fh, fx:fx + fw] = cv2.GC_FGD
        # 确定性背景条带最后强制写入：种子展开不得覆盖（否则 GMM 样本
        # 为空，grabCut 直接断言失败）
        mask[:kt, :] = cv2.GC_BGD
        mask[:, :ks] = cv2.GC_BGD
        mask[:, w - ks:] = cv2.GC_BGD
        bgd = np.zeros((1, 65), np.float64)
        fgd = np.zeros((1, 65), np.float64)
        # GrabCut initializes GMMs with randomized k-means++. OpenCV's default
        # RNG is thread-local (core.hpp: theRNG), so this keeps repeated and
        # concurrent runs reproducible without serializing image processing.
        cv2.setRNGSeed(0)
        # rect=None 在 GC_INIT_WITH_MASK 模式下合法；opencv 无官方类型桩
        cv2.grabCut(arr, mask, None, bgd, fgd, 5, cv2.GC_INIT_WITH_MASK)  # type: ignore[call-overload]
        subject = (mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD)
        # Preserve geometry: uniform erosion disproportionately shrinks thin
        # parts. Boundary cleanup belongs to the separate color mask.
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
