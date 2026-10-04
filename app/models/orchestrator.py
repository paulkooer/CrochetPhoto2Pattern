"""Photo analysis and deterministic generation, with an optional human review pause."""

from __future__ import annotations

import logging
from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from PIL import Image

from app import software_version

from ..schemas import ImageAnalysis, PatternResult
from .crochet_params import CrochetParamsGenerator
from .geometry import GeometryObservation, mock_geometry, observe_geometry
from .image_parser import ImageParser
from .runtime import RunTrace
from .sizing import scale_analysis_to_target_height
from .structure_designer import StructureDesigner
from .subject import SubjectObservation

logger = logging.getLogger(__name__)
ProgressCB = Callable[..., Any]
VISION_MODES = ("ai", "local", "mock")


@dataclass
class PhotoDraft:
    """Session-only analysis. Contains no API credentials or parser/client objects."""

    image: Image.Image
    subject: SubjectObservation
    analysis: ImageAnalysis
    geometry: GeometryObservation
    spans: dict | None
    spans_measured: list[str]
    usage: dict
    vision_meta: dict
    trace: RunTrace


class PipelineOrchestrator:
    def __init__(
        self,
        openai_key: str | None = None,
        anthropic_key: str | None = None,
        openai_base_url: str | None = None,
        anthropic_base_url: str | None = None,
    ):
        self.parser = ImageParser(
            openai_key=openai_key,
            anthropic_key=anthropic_key,
            openai_base_url=openai_base_url,
            anthropic_base_url=anthropic_base_url,
        )
        self.structure_designer = StructureDesigner()
        self.params_generator = CrochetParamsGenerator()
        self.last_diagnostics: dict = {}

    def prepare_photo(
        self,
        image: Image.Image,
        *,
        vision_mode: str = "ai",
        progress_cb: ProgressCB | None = None,
        subject: SubjectObservation | None = None,
        budget_seconds: float = 180,
    ) -> PhotoDraft:
        if vision_mode not in VISION_MODES:
            raise ValueError(f"vision_mode 必须是 {'/'.join(VISION_MODES)}，得到 {vision_mode!r}")
        trace = RunTrace(budget_seconds)
        subject = subject or SubjectObservation(image)
        if subject.image is not image:
            raise ValueError("主体观测与照片不匹配")
        try:
            return self._prepare(image, subject, vision_mode, trace, progress_cb)
        finally:
            self.last_diagnostics = trace.payload()

    def _prepare(self, image, subject, vision_mode, trace, progress_cb) -> PhotoDraft:
        geometry = None
        with trace.stage("geometry"):
            if vision_mode != "mock" and (
                vision_mode == "local" or self.parser.openai_key or self.parser.anthropic_key
            ):
                geometry = observe_geometry(image, subject=subject)
        spans, measured_names, hints = None, [], None
        with trace.stage("pose"):
            try:
                from .pose import format_span_hints, get_body_landmarks, measured_spans

                landmarks = get_body_landmarks(image)
                if landmarks is not None:
                    from .color_design import PART_SPAN

                    measured = measured_spans(landmarks)
                    spans = {**PART_SPAN, **measured}
                    measured_names = sorted(measured)
                    hints = format_span_hints(measured)
                else:
                    trace.fallbacks.append("姿态关键点不可用；使用部件分段先验")
            except Exception:
                trace.fallbacks.append("姿态估算失败；使用部件分段先验")
        if progress_cb:
            progress_cb(10, text="Step 1/3: 解析照片中...")
        with trace.stage("vision"):
            if vision_mode == "local":
                profile = geometry.silhouette.profile if geometry and geometry.silhouette else None
                analysis = self.parser.parse_image_local(
                    image, geometry_profile=profile, geometry_observed=True, subject=subject
                )
                self.parser.last_usage = {}
            elif vision_mode == "mock":
                analysis = self.parser.parse_image_mock()
                self.parser.last_usage = {}
            else:
                self.parser.request_budget_seconds = trace.remaining()
                analysis = self.parser.parse_image(image, span_hints=hints, subject=subject)
            source = (self.parser.last_local_meta or {}).get("source")
            if source == "mock":
                geometry = mock_geometry()
            elif geometry is None:
                geometry = observe_geometry(image, subject=subject)
        if source == "default":
            trace.fallbacks.append("未检出头部；比例来自默认模板，请人工确认")
        if source != "mock" and geometry.silhouette is None:
            trace.fallbacks.append("主体分割不可用；形状回退模板")
        attempts = self.parser.last_usage.get("attempts", [])
        if any(a.get("status") != "success" for a in attempts):
            trace.fallbacks.append("视觉请求曾失败、拒绝或返回无效内容；已重试或切换服务商，详见尝试记录")
        if source != "mock" and geometry.silhouette is not None and subject.segmentation is None:
            trace.fallbacks.append("主体分割不可用；轮廓采用背景颜色差异启发式")
        if source not in ("mock", "opencv-face", "default"):
            with trace.stage("review_head_detection"):
                from .subject import _face_box

                small = image.copy()
                small.thumbnail((640, 640))
                box = _face_box(small)
                if box:
                    self.parser.last_local_meta["face_box"] = [
                        round(box[0] * image.width / small.width),
                        round(box[1] * image.height / small.height),
                        round(box[2] * image.width / small.width),
                        round(box[3] * image.height / small.height),
                    ]
        return PhotoDraft(
            image,
            subject,
            analysis,
            geometry,
            spans,
            measured_names,
            deepcopy(self.parser.last_usage),
            deepcopy(self.parser.last_local_meta),
            trace,
        )

    @staticmethod
    def generate_from_draft(
        draft: PhotoDraft,
        *,
        analysis: ImageAnalysis | None = None,
        gauge=None,
        style=None,
        target_height_cm: float = 18,
        target_height_source: str = "default_reference",
        progress_cb: ProgressCB | None = None,
        run_trace: RunTrace | None = None,
    ) -> dict[str, Any]:
        """Generate locally from reviewed data; never contacts a vision provider.

        Budget covers active stages only, so time spent by the user reviewing the
        draft does not exhaust it. Local native calls stop at the next checkpoint.
        """
        trace = run_trace or deepcopy(draft.trace)
        from .color_design import vertical_color_bands
        from .gauge import DEFAULT, DEFAULT_STYLE

        gauge, style = gauge or DEFAULT, style or DEFAULT_STYLE
        with trace.stage("structure"):
            chosen = ImageAnalysis.model_validate((analysis or draft.analysis).model_dump())
            if not chosen.parts:
                raise ValueError("请至少保留一个部件")
            chosen, sizing = scale_analysis_to_target_height(
                chosen, target_height_cm, source=target_height_source
            )
            if progress_cb:
                progress_cb(40, text="Step 2/3: 部件结构设计中...")
            structure = StructureDesigner.design_3d_structure(chosen)
        with trace.stage("colors"):
            bands = vertical_color_bands(draft.image, subject=draft.subject)
            if not bands:
                trace.fallbacks.append("未取得纵向配色；使用部件语义色或默认色")
        with trace.stage("pattern"):
            if progress_cb:
                progress_cb(70, text="Step 3/3: 生成钩织参数...")
            profile = draft.geometry.silhouette.profile if draft.geometry.silhouette else None
            params = CrochetParamsGenerator.generate_params(
                chosen,
                structure,
                color_bands=bands or None,
                body_profile=profile,
                gauge=gauge,
                style=style,
                spans=draft.spans,
            )
        with trace.stage("preview"):
            from ..utils.images import thumbnail_data_url

            preview = thumbnail_data_url(draft.image)
        meta = deepcopy(draft.vision_meta)
        if analysis is not None:
            meta["reviewed_by_user"] = True
        return PatternResult(
            generator_version=software_version(),
            analysis=chosen.model_dump(),
            structure=structure,
            params=params,
            usage=draft.usage,
            vision_meta=meta,
            gauge={"stitches_per_10cm": gauge.stitches_per_10cm, "rows_per_10cm": gauge.rows_per_10cm},
            style={
                "sphere_mode": style.sphere_mode,
                "one_piece": style.one_piece,
                "skirt_style": style.skirt_style,
                "ruffle_hem": style.ruffle_hem,
            },
            color_bands=bands or None,
            preview=preview,
            spans=draft.spans,
            spans_measured=draft.spans_measured,
            sizing=sizing,
            geometry=draft.geometry.model_dump(),
            diagnostics=trace.payload(),
        ).to_result_dict()

    def run_full_pipeline(
        self,
        image: Image.Image,
        progress_cb: ProgressCB | None = None,
        local_vision: bool | None = None,
        gauge=None,
        style=None,
        target_height_cm: float = 18.0,
        target_height_source: str = "default_reference",
        vision_mode: str = "ai",
        budget_seconds: float = 180,
    ) -> dict[str, Any]:
        # Keep the original public API and explicit mode validation.
        if vision_mode not in VISION_MODES:
            raise ValueError(f"vision_mode 必须是 {'/'.join(VISION_MODES)}，得到 {vision_mode!r}")
        draft = self.prepare_photo(
            image,
            vision_mode="local" if local_vision is True else vision_mode,
            progress_cb=progress_cb,
            budget_seconds=budget_seconds,
        )
        trace = deepcopy(draft.trace)
        try:
            return self.generate_from_draft(
                draft,
                gauge=gauge,
                style=style,
                target_height_cm=target_height_cm,
                target_height_source=target_height_source,
                progress_cb=progress_cb,
                run_trace=trace,
            )
        finally:
            self.last_diagnostics = trace.payload()
