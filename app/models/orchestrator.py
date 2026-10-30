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
VISION_MODES = ("local", "mock")


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
    def __init__(self):
        self.parser = ImageParser()
        self.structure_designer = StructureDesigner()
        self.params_generator = CrochetParamsGenerator()
        self.last_diagnostics: dict = {}

    def prepare_photo(
        self,
        image: Image.Image,
        *,
        vision_mode: str = "local",
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
            if vision_mode != "mock":
                geometry = observe_geometry(image, subject=subject)
        spans, measured_names = None, []
        with trace.stage("pose"):
            try:
                from .pose import get_body_landmarks, measured_spans

                landmarks = get_body_landmarks(image)
                if landmarks is not None:
                    from .color_design import PART_SPAN

                    measured = measured_spans(landmarks)
                    spans = {**PART_SPAN, **measured}
                    measured_names = sorted(measured)
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
            source = (self.parser.last_local_meta or {}).get("source")
            if source == "mock":
                geometry = mock_geometry()
            elif geometry is None:
                geometry = observe_geometry(image, subject=subject)
        if source == "default":
            trace.fallbacks.append("没有通过检查的头部候选框；比例来自默认模板，请人工确认")
        if source != "mock" and geometry.silhouette is None:
            trace.fallbacks.append("主体分割不可用；形状回退模板")
        if source != "mock" and geometry.silhouette is not None and subject.segmentation is None:
            trace.fallbacks.append("主体分割不可用；轮廓采用背景颜色差异启发式")
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
            structure = StructureDesigner.design_3d_structure(chosen, infer_missing_parts=analysis is None)
        with trace.stage("colors"):
            color_observation: dict = {}
            bands = vertical_color_bands(draft.image, subject=draft.subject, observation=color_observation)
            if not bands:
                trace.fallbacks.append("未取得纵向配色；使用部件语义色或默认色")
        with trace.stage("pattern"):
            if progress_cb:
                progress_cb(70, text="Step 3/3: 生成钩织参数...")
            profile = draft.geometry.silhouette.profile if draft.geometry.silhouette else None
            if draft.geometry.body_region is not None:
                profile = draft.geometry.body_region.profile
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
        if color_observation:
            meta["color_observation"] = color_observation
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
        vision_mode: str = "local",
        budget_seconds: float = 180,
        parts: list[str] | None = None,
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
                analysis=draft.analysis.model_copy(update={"parts": parts}) if parts is not None else None,
                gauge=gauge,
                style=style,
                target_height_cm=target_height_cm,
                target_height_source=target_height_source,
                progress_cb=progress_cb,
                run_trace=trace,
            )
        finally:
            self.last_diagnostics = trace.payload()
