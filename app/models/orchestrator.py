"""Photo analysis and deterministic generation, with an optional human review pause."""

from __future__ import annotations

import logging
from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass, replace
from typing import Any

from PIL import Image

from app import software_version

from ..schemas import ImageAnalysis, PatternParams, PatternResult, ResultData, StructureData
from .crochet_params import CrochetParamsGenerator
from .crochetability import require_crochetable
from .geometry import GeometryObservation, mock_geometry, observe_geometry
from .image_parser import ImageParser
from .runtime import RunTrace
from .sizing import DEFAULT_PROPORTION_STYLE, scale_analysis_to_target_height
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


def _automatic_contour_draft(draft: PhotoDraft) -> PhotoDraft:
    """Use contour candidates in headless delivery without claiming user review.

    The booleans are uncalibrated visual heuristics, not probabilities. The
    interactive draft stays unchanged so its user can still choose each part.
    """
    if draft.vision_meta.get("source") not in {"default", "silhouette-head", "opencv-face"}:
        return draft
    flags = (("possible_ears", "耳朵"), ("possible_skirt", "裙子"), ("possible_tail", "尾巴"))
    added = [name for flag, name in flags
             if draft.vision_meta.get(flag) is True and name not in draft.analysis.parts]
    if not added:
        return draft
    meta = deepcopy(draft.vision_meta)
    meta.update(
        parts_source="automatic_contour",
        automatic_parts=added,
        note=("基础部件来自模板，自动加入轮廓候选：" + "、".join(added)
              + "；候选未经真实照片校准，可能误判，主体、头部及比例仍需核对。"),
    )
    analysis = draft.analysis.model_copy(update={"parts": [*draft.analysis.parts, *added]})
    return replace(draft, analysis=analysis, vision_meta=meta)


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
        measured, measured_names = {}, []
        with trace.stage("pose"):
            try:
                from .pose import get_body_landmarks, measured_spans

                landmarks = get_body_landmarks(image)
                if landmarks is not None:
                    measured = measured_spans(landmarks)
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
        # Color bands, silhouette profiles, and pose landmarks use image
        # coordinates. Only the fallback part proportions are subject-relative.
        from .color_design import resolved_part_spans

        extent = geometry.silhouette.subject_extent if geometry.silhouette else None
        spans = resolved_part_spans(measured, extent)
        if source == "default":
            trace.fallbacks.append("没有通过检查的头部候选框；比例来自默认模板，请人工确认")
        elif source == "silhouette-head":
            trace.fallbacks.append("头部候选来自主体轮廓而非人脸检测；比例和部件仍需人工确认")
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
    def _design(
        draft: PhotoDraft,
        analysis: ImageAnalysis | None,
        parts: list[str] | None,
        target_height_cm: float,
        target_height_source: str,
        progress_cb: ProgressCB | None = None,
        proportion_style: str = DEFAULT_PROPORTION_STYLE,
    ) -> tuple[ImageAnalysis, dict[str, Any], StructureData]:
        """Scale the chosen analysis and design its template structure."""
        chosen_data = (analysis or draft.analysis).model_dump()
        if parts is not None:
            chosen_data["parts"] = parts
        chosen = ImageAnalysis.model_validate(chosen_data)
        if not chosen.parts:
            raise ValueError("请至少保留一个部件")
        chosen, sizing = scale_analysis_to_target_height(
            chosen, target_height_cm, source=target_height_source, proportion_style=proportion_style
        )
        if progress_cb:
            progress_cb(40, text="Step 2/3: 部件结构设计中...")
        structure = StructureDesigner.design_3d_structure(
            chosen, infer_missing_parts=analysis is None and parts is None)
        return chosen, sizing, structure

    @staticmethod
    def _body_profile(draft: PhotoDraft) -> list[float] | None:
        if draft.geometry.body_region is not None:
            return draft.geometry.body_region.profile
        return draft.geometry.silhouette.profile if draft.geometry.silhouette else None

    @staticmethod
    def preview_params(
        draft: PhotoDraft,
        *,
        analysis: ImageAnalysis,
        gauge=None,
        style=None,
        target_height_cm: float = 18,
        proportion_style: str = DEFAULT_PROPORTION_STYLE,
    ) -> PatternParams:
        """The rounds generate_from_draft would produce, without colors or the gate.

        Colors never change stitch counts, so the review page can show exact
        per-part counts and crochetability before the user confirms generation.
        """
        from .gauge import DEFAULT, DEFAULT_STYLE

        chosen, _sizing, structure = PipelineOrchestrator._design(
            draft, analysis, None, target_height_cm, "review_preview", proportion_style=proportion_style)
        return CrochetParamsGenerator.generate_params(
            chosen,
            structure,
            body_profile=PipelineOrchestrator._body_profile(draft),
            gauge=gauge or DEFAULT,
            style=style or DEFAULT_STYLE,
            spans=draft.spans,
        )

    @staticmethod
    def generate_from_draft(
        draft: PhotoDraft,
        *,
        analysis: ImageAnalysis | None = None,
        parts: list[str] | None = None,
        gauge=None,
        style=None,
        target_height_cm: float = 18,
        target_height_source: str = "default_reference",
        progress_cb: ProgressCB | None = None,
        run_trace: RunTrace | None = None,
        enforce_crochetability: bool = True,
        proportion_style: str = DEFAULT_PROPORTION_STYLE,
    ) -> ResultData:
        """Generate locally from reviewed data; never contacts a vision provider.

        Budget covers active stages only, so time spent by the user reviewing the
        draft does not exhaust it. Local native calls stop at the next checkpoint.
        ``analysis`` supplies a fully reviewed analysis; ``parts`` only overrides
        the CLI selection and must not certify subject or proportion review.
        Degenerate head/body sizes raise ``PatternCrochetabilityError`` unless
        ``enforce_crochetability`` is false (evaluation scores them separately).
        ``proportion_style`` maps the photo head ratio into a doll range (Q by default).
        """
        trace = run_trace or deepcopy(draft.trace)
        from .color_design import vertical_color_bands
        from .gauge import DEFAULT, DEFAULT_STYLE

        gauge, style = gauge or DEFAULT, style or DEFAULT_STYLE
        with trace.stage("structure"):
            chosen, sizing, structure = PipelineOrchestrator._design(
                draft, analysis, parts, target_height_cm, target_height_source, progress_cb,
                proportion_style=proportion_style)
        with trace.stage("colors"):
            color_observation: dict = {}
            bands = vertical_color_bands(draft.image, subject=draft.subject, observation=color_observation)
            if not bands:
                trace.fallbacks.append("未取得纵向配色；使用部件语义色或默认色")
        with trace.stage("pattern"):
            if progress_cb:
                progress_cb(70, text="Step 3/3: 生成钩织参数...")
            params = CrochetParamsGenerator.generate_params(
                chosen,
                structure,
                color_bands=bands or None,
                body_profile=PipelineOrchestrator._body_profile(draft),
                gauge=gauge,
                style=style,
                spans=draft.spans,
            )
            if enforce_crochetability:
                require_crochetable(params)
        with trace.stage("preview"):
            from ..utils.images import thumbnail_data_url

            preview = thumbnail_data_url(draft.image)
        meta = deepcopy(draft.vision_meta)
        if color_observation:
            meta["color_observation"] = color_observation
        if parts is not None:
            meta["parts_source"] = "cli_explicit"
        if analysis is not None:
            meta["reviewed_by_user"] = True
        elif parts is not None:
            # Selecting parts does not confirm the subject, head or proportions.
            meta.pop("reviewed_by_user", None)
            meta["requires_subject_review"] = True
        return PatternResult(
            generator_version=software_version(),
            analysis=chosen.model_dump(),
            structure=dict(structure),
            params=dict(params),
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
        enforce_crochetability: bool = True,
        proportion_style: str = DEFAULT_PROPORTION_STYLE,
    ) -> ResultData:
        # Keep the original public API and explicit mode validation.
        if vision_mode not in VISION_MODES:
            raise ValueError(f"vision_mode 必须是 {'/'.join(VISION_MODES)}，得到 {vision_mode!r}")
        draft = self.prepare_photo(
            image,
            vision_mode="local" if local_vision is True else vision_mode,
            progress_cb=progress_cb,
            budget_seconds=budget_seconds,
        )
        if parts is None:
            draft = _automatic_contour_draft(draft)
        trace = deepcopy(draft.trace)
        try:
            return self.generate_from_draft(
                draft,
                parts=parts,
                gauge=gauge,
                style=style,
                target_height_cm=target_height_cm,
                target_height_source=target_height_source,
                progress_cb=progress_cb,
                run_trace=trace,
                enforce_crochetability=enforce_crochetability,
                proportion_style=proportion_style,
            )
        finally:
            self.last_diagnostics = trace.payload()
