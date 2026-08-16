import logging
from typing import Any, Callable, Dict, Optional

from PIL import Image

from ..schemas import ImageAnalysis  # noqa: F401 – kept for re-export convenience
from .crochet_params import CrochetParamsGenerator
from .image_parser import ImageParser
from .structure_designer import StructureDesigner

logger = logging.getLogger(__name__)

# 进度回调：(percent, text)，直接对接 st.progress(...).progress
ProgressCB = Callable[..., None]


class PipelineOrchestrator:
    """Orchestrate the full photo-to-pattern pipeline."""

    def __init__(
        self,
        openai_key: Optional[str] = None,
        anthropic_key: Optional[str] = None,
    ):
        self.parser = ImageParser(
            openai_key=openai_key,
            anthropic_key=anthropic_key,
        )
        self.structure_designer = StructureDesigner()
        self.params_generator = CrochetParamsGenerator()

    def run_full_pipeline(
        self,
        image: Image.Image,
        progress_cb: Optional[ProgressCB] = None,
        local_vision: bool = False,
        gauge=None,
    ) -> Dict[str, Any]:
        """Run the complete pipeline: parse → design → generate params.

        Args:
            image:        PIL Image to analyze
            progress_cb:  optional callback invoked as progress_cb(percent, text)
                          after each stage (UI 进度条由调用方注入，模型层不依赖 Streamlit)
            local_vision: True 时第一步改走无 LLM 的本地视觉估算
                          （人脸检测 + 比例推算），其余阶段不变

        Returns:
            Dict with 'analysis', 'structure', 'params', 'usage' and
            'vision_meta' keys
        """

        def _report(pct: int, text: str) -> None:
            if progress_cb is not None:
                progress_cb(pct, text=text)

        logger.info("Pipeline started (local_vision=%s)", local_vision)

        if local_vision:
            _report(10, "Step 1/3: 本地视觉估算中（无 LLM）...")
            analysis = self.parser.parse_image_local(image)
            self.parser.last_usage = {}
        else:
            _report(10, "Step 1/3: AI 视觉解析中...")
            analysis = self.parser.parse_image(image)
        logger.info("Image parsed: %s body, %d parts", analysis.body_type, len(analysis.parts))

        _report(40, "Step 2/3: 3D 结构设计中...")
        structure = self.structure_designer.design_3d_structure(analysis)
        logger.info("Structure designed: %d parts", len(structure.get("parts", [])))

        _report(70, "Step 3/3: 生成钩织参数...")
        # 照片纵向色带 → 逐圈配色（让针法配色来自照片本身）
        from .color_design import vertical_color_bands
        from .gauge import DEFAULT as DEFAULT_GAUGE

        gauge = gauge or DEFAULT_GAUGE
        color_bands = vertical_color_bands(image)
        # M1.1：照片宽度剖面 → 身体轮廓驱动（AmiGo 旋转体范式的单图简化）
        body_profile = None
        sil = (self.parser.last_local_meta or {}).get("silhouette") or {}
        if isinstance(sil.get("profile"), list) and sil["profile"]:
            body_profile = [float(v) for v in sil["profile"]]
        params = self.params_generator.generate_params(
            analysis, structure, color_bands=color_bands or None,
            body_profile=body_profile, gauge=gauge,
        )
        logger.info("Parameters generated: %d parts, difficulty=%s, %d color bands",
                    len(params.get("parts", [])), params.get("difficulty"),
                    len(color_bands))

        return {
            "analysis": analysis.model_dump(),
            "structure": structure,
            "params": params,
            # 最近一次 Vision 调用的 token 用量（无 key/Mock/本地路径为空 dict）
            "usage": self.parser.last_usage,
            # 本地视觉估算的依据（LLM 路径为空 dict）
            "vision_meta": self.parser.last_local_meta,
            # 本次使用的 gauge（渲染轮廓 SVG 时需要针宽/行高）
            "gauge": {"stitches_per_10cm": gauge.stitches_per_10cm,
                      "rows_per_10cm": gauge.rows_per_10cm},
        }
