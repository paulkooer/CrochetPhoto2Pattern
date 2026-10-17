"""Local photo analysis and yarn palette extraction; no remote providers."""
import logging

from PIL import Image

from ..schemas import ImageAnalysis
from .colors import nearest_yarn
from .subject import SubjectObservation

logger = logging.getLogger(__name__)


def extract_color_palette(image: Image.Image, n_colors: int = 5, *,
                          subject: SubjectObservation | None = None) -> list[str]:
    """Extract dominant colors from an image and map to yarn color names.

    主体像素上做 S3 直量化（coverage 直选毛线色 + CIEDE2000 分配）——
    调色板每一色都是可购买毛线，背景不入板；分割不可用时回退全图。
    Returns a deduplicated list of yarn color names sorted by dominance.
    """
    try:
        import numpy as np

        from .colors import pick_yarn_palette
        img = image.convert("RGB")
        # thumbnail 保纵横比：固定 resize((150,150)) 会让全景图的横向颜色
        # 占比被人为放大。thumbnail 原地修改，需先 copy。
        img = img.copy()
        img.thumbnail((150, 150))
        source = img
        # 主体掩码可用 → 只统计主体像素（背景剔除比色彩距离阈值更稳）。
        # 取色用受光面：成片的阴影/水印会把单色玩偶读成两色（见 subject.shaded_area）。
        try:
            from .subject import color_interior, extract_subject
            res = (subject.extract_lit_colors(image) if subject is not None
                   else color_interior(extract_subject(image, max_side=150),
                                       lit_only=True))
            if res is not None:
                mask, small = res
                subj = np.asarray(small)[mask]
                if len(subj) >= 50:  # 主体像素太少时统计无意义，回退全图
                    source = Image.fromarray(
                        subj.reshape(len(subj), 1, 3).astype(np.uint8))
        except Exception as e:
            logger.debug("subject-guided palette skipped: %s", e)
        pixels = [tuple(int(v) for v in px) for px in np.asarray(
            source, dtype=np.uint8).reshape(-1, 3)]
        rgbs = pick_yarn_palette(pixels, n_colors)
        names: list[str] = []
        seen: set[str] = set()
        for rgb in rgbs:
            name = nearest_yarn(*rgb)[0]
            if name not in seen:
                seen.add(name)
                names.append(name)
        return names
    except Exception as e:
        logger.warning("Color palette extraction failed: %s", e)
        return []


class ImageParser:
    """Estimate photo proportions locally; parts remain subject to review."""

    def __init__(self):
        self.last_usage: dict = {}  # Retained for historical result compatibility.
        self.last_local_meta: dict = {}

    def parse_image(self, image: Image.Image, *,
                    subject: SubjectObservation | None = None) -> ImageAnalysis:
        """Default entry point always uses local analysis."""
        return self.parse_image_local(image, subject=subject)

    def parse_image_local(
        self,
        image: Image.Image,
        geometry_profile: list[float] | None = None,
        geometry_observed: bool = False,
        *,
        subject: SubjectObservation | None = None,
    ) -> ImageAnalysis:
        """Local no-LLM analysis: face detection + proportion estimation.

        估算依据记录在
        self.last_local_meta 供 UI 透明展示。
        """
        # 延迟导入避免 local_vision ↔ image_parser 循环依赖
        from .local_vision import analyze

        self.last_usage = {}
        analysis, meta = analyze(
            image,
            geometry_profile=geometry_profile,
            geometry_observed=geometry_observed,
            subject=subject,
        )
        self.last_local_meta = meta
        return analysis

    def parse_image_mock(self) -> ImageAnalysis:
        """Return explicitly requested demonstration data."""
        self.last_usage = {}
        self.last_local_meta = {
            "source": "mock",
            "note": "Mock 演示数据：体型与部件为固定演示值，"
                    "配色与分段参考照片（仅供体验流程）",
        }
        return self._mock_analysis()

    @staticmethod
    def _mock_analysis() -> ImageAnalysis:
        """Return mock analysis for demo/testing without interpreting the photo."""
        return ImageAnalysis(
            body_type="标准",
            head_diameter_cm=9.0,
            height_cm=18.0,
            main_features=["大眼睛", "小鼻子", "圆脸"],
            pose="站立",
            difficulty="easy",
            parts=["头部", "身体", "手臂", "腿部"]
        )
