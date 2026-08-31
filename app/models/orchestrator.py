import logging
from typing import Any, Callable, Dict, Optional

from PIL import Image

from ..schemas import ImageAnalysis  # noqa: F401 – kept for re-export convenience
from .crochet_params import CrochetParamsGenerator
from .geometry import mock_geometry, observe_geometry
from .image_parser import ImageParser
from .sizing import scale_analysis_to_target_height
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
        openai_base_url: Optional[str] = None,
        anthropic_base_url: Optional[str] = None,
    ):
        self.parser = ImageParser(
            openai_key=openai_key,
            anthropic_key=anthropic_key,
            openai_base_url=openai_base_url,
            anthropic_base_url=anthropic_base_url,
        )
        self.structure_designer = StructureDesigner()
        self.params_generator = CrochetParamsGenerator()

    def run_full_pipeline(
        self,
        image: Image.Image,
        progress_cb: Optional[ProgressCB] = None,
        local_vision: bool = False,
        gauge=None,
        style=None,
        target_height_cm: float = 18.0,
        target_height_source: str = "default_reference",
    ) -> Dict[str, Any]:
        """Run the complete pipeline: parse → design → generate params.

        Args:
            image:        PIL Image to analyze
            progress_cb:  optional callback invoked as progress_cb(percent, text)
                          after each stage (UI 进度条由调用方注入，模型层不依赖 Streamlit)
            local_vision: True 时第一步改走无 LLM 的本地视觉估算
                          （人脸检测 + 比例推算），其余阶段不变
            target_height_cm: 用户选择的成品目标高度；照片仅提供头身比例

        Returns:
            Dict with 'analysis', 'structure', 'params', 'usage' and
            'vision_meta' keys
        """

        def _report(pct: int, text: str) -> None:
            if progress_cb is not None:
                progress_cb(pct, text=text)

        logger.info("Pipeline started (local_vision=%s)", local_vision)

        # 真正的 AI/本地照片路径先做一次 provider-neutral 几何观测；明确
        # 无 Key 的 Mock 路径跳过，保证演示数据不消费照片几何且不浪费分割。
        geometry_observation = None
        if local_vision or self.parser.openai_key or self.parser.anthropic_key:
            geometry_observation = observe_geometry(image)

        # S1：姿态关键点实测部件 span（可选能力，失败回退 PART_SPAN 先验）。
        # 对本地/LLM 两条路径同样适用——span 是纯几何量，与解析方式无关；
        # 在解析**之前**计算，实测分段作为 hints 进入 Vision prompt（T6）。
        spans = None
        spans_measured: list = []
        span_hints = None
        try:
            from .pose import format_span_hints, get_body_landmarks, measured_spans
            _lm = get_body_landmarks(image)
            if _lm is not None:
                measured = measured_spans(_lm)
                # F15：有效 span = 先验 ∪ 实测（实测覆盖先验）。旧实现把
                # 部分实测 dict 直接下传——未测部件（如膝盖不可见时无
                # 腿部/裙子）会失去照片配色，比不启用 pose 更差。
                from .color_design import PART_SPAN
                spans = {**PART_SPAN, **measured}
                spans_measured = sorted(measured)
                span_hints = format_span_hints(measured)
                logger.info("Pose spans measured: %s", spans_measured)
        except Exception as e:
            logger.debug("pose spans unavailable: %s", e)

        if local_vision:
            _report(10, "Step 1/3: 本地视觉估算中（无 LLM）...")
            profile = (geometry_observation.silhouette.profile
                       if geometry_observation is not None
                       and geometry_observation.silhouette is not None else None)
            analysis = self.parser.parse_image_local(
                image, geometry_profile=profile, geometry_observed=True)
            self.parser.last_usage = {}
        else:
            _report(10, "Step 1/3: AI 视觉解析中...")
            analysis = self.parser.parse_image(image, span_hints=span_hints)
        analysis, sizing = scale_analysis_to_target_height(
            analysis, target_height_cm, source=target_height_source)
        source = (self.parser.last_local_meta or {}).get("source")
        if source == "mock":
            geometry_observation = mock_geometry()
        elif geometry_observation is None:
            # Library/tests may inject a parser without provider keys; keep the
            # contract correct even when source provenance is supplied externally.
            geometry_observation = observe_geometry(image)
        logger.info("Image parsed: %s body, %d parts", analysis.body_type, len(analysis.parts))

        _report(40, "Step 2/3: 部件结构设计中...")
        structure = self.structure_designer.design_3d_structure(analysis)
        logger.info("Structure designed: %d parts", len(structure.get("parts", [])))

        _report(70, "Step 3/3: 生成钩织参数...")
        # 照片纵向色带 → 逐圈配色（让针法配色来自照片本身）
        from .color_design import vertical_color_bands
        from .gauge import DEFAULT as DEFAULT_GAUGE
        from .gauge import DEFAULT_STYLE

        gauge = gauge or DEFAULT_GAUGE
        style = style or DEFAULT_STYLE
        color_bands = vertical_color_bands(image)
        # U8：小缩略图（历史列表/分享预览用），随 result 持久化
        preview = None
        try:
            import base64
            import io as _io
            _thumb = image.convert("RGB").copy()
            _thumb.thumbnail((96, 96))
            _buf = _io.BytesIO()
            _thumb.save(_buf, format="JPEG", quality=70)
            preview = ("data:image/jpeg;base64,"
                       + base64.b64encode(_buf.getvalue()).decode())
        except Exception as e:
            logger.debug("preview thumbnail failed: %s", e)
        # Provider-neutral geometry：AI/本地真实照片共用同一剖面；Mock
        # 明确不读照片。旧版只从 local vision_meta 取值，AI 模式静默丢失。
        body_profile = None
        if geometry_observation.silhouette is not None:
            body_profile = [float(value) for value in
                            geometry_observation.silhouette.profile]
        params = self.params_generator.generate_params(
            analysis, structure, color_bands=color_bands or None,
            body_profile=body_profile, gauge=gauge, style=style, spans=spans,
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
            # 本次使用的塑形选项与照片色带：结果页"快速调整尺寸"重生成
            # 参数时复用（不重新调用 AI，配色/塑形行为与首次一致）
            "style": {"sphere_mode": style.sphere_mode,
                      "one_piece": style.one_piece,
                      "skirt_style": style.skirt_style,
                      "ruffle_hem": style.ruffle_hem},
            "color_bands": color_bands or None,
            "preview": preview,
            # S1 实测部件 span（None = 回退先验）；配色映射与快速调尺寸共用。
            # spans 是"先验 ∪ 实测"的完整有效集；spans_measured 记录哪些
            # 来自关键点实测（UI 诚实标注，不把先验误称为实测）
            "spans": spans,
            "spans_measured": spans_measured,
            # 单图只测相对比例；厘米目标的来源与变换必须随结果持久化。
            "sizing": sizing,
            "geometry": geometry_observation.model_dump(),
        }
