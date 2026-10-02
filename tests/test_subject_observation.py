"""Shared segmentation is scoped to one image and one pipeline run."""
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pytest
from PIL import Image, ImageDraw

from app.models import subject
from app.models.image_parser import ImageParser
from app.models.orchestrator import PipelineOrchestrator
from app.models.subject import SubjectObservation


@pytest.mark.parametrize("mode", ["local", "ai", "mock"])
@pytest.mark.parametrize("segmented", [True, False])
def test_pipeline_segments_once_including_failure(monkeypatch, mode, segmented):
    calls = []

    def extract(image, max_side=160):
        calls.append(max_side)
        if not segmented:
            return None
        small = image.copy()
        small.thumbnail((max_side, max_side))
        return np.ones((small.height, small.width), dtype=bool), small

    monkeypatch.setattr(subject, "extract_subject", extract)
    monkeypatch.setattr("app.models.pose.get_body_landmarks", lambda image: None)
    monkeypatch.setattr("app.models.local_vision._detect_face", lambda image: None)
    monkeypatch.setattr(ImageParser, "_parse_with_openai", lambda self, image: self._mock_analysis())
    result = PipelineOrchestrator(openai_key="fake-key").run_full_pipeline(
        Image.new("RGB", (80, 160), "red"), vision_mode=mode)
    assert calls == [160]
    assert result["params"]["parts"]
    if mode == "mock":
        assert result["geometry"]["used_for_generation"] is False
    elif segmented:
        assert result["geometry"]["silhouette"]["profile"] == [1.0] * 40


def test_observation_caches_exception_and_rejects_other_images(monkeypatch):
    calls = []

    def fail(*args, **kwargs):
        calls.append(1)
        raise OSError("optional runtime unavailable")

    monkeypatch.setattr(subject, "extract_subject", fail)
    image = Image.new("RGB", (40, 80))
    observed = SubjectObservation(image)
    assert observed.extract(image) is None
    assert observed.extract(image) is None
    assert calls == [1]
    with pytest.raises(ValueError, match="图片"):
        observed.extract(image.copy())


def test_parallel_pipeline_runs_do_not_share_image_observations(monkeypatch):
    calls = []

    def extract(image, max_side=160):
        calls.append(image.getpixel((0, 0)))
        return np.ones((image.height, image.width), dtype=bool), image

    monkeypatch.setattr(subject, "extract_subject", extract)
    monkeypatch.setattr("app.models.pose.get_body_landmarks", lambda image: None)
    monkeypatch.setattr("app.models.local_vision._detect_face", lambda image: None)

    def run(color):
        return PipelineOrchestrator().run_full_pipeline(
            Image.new("RGB", (80, 160), color), vision_mode="local")

    with ThreadPoolExecutor(max_workers=2) as pool:
        red, blue = list(pool.map(run, ("red", "blue")))
    assert sorted(calls) == [(0, 0, 255), (255, 0, 0)]
    assert red["color_bands"] != blue["color_bands"]
    assert red["analysis"]["recommended_colors"] != blue["analysis"]["recommended_colors"]


def test_reusing_orchestrator_after_image_edit_recomputes_subject(monkeypatch):
    calls = []

    def extract(image, max_side=160):
        calls.append(image.getpixel((0, 0)))
        return None

    monkeypatch.setattr(subject, "extract_subject", extract)
    monkeypatch.setattr("app.models.pose.get_body_landmarks", lambda image: None)
    image = Image.new("RGB", (40, 80), "red")
    pipeline = PipelineOrchestrator()
    pipeline.run_full_pipeline(image, vision_mode="mock")
    image.paste("blue", (0, 0, 40, 80))
    pipeline.run_full_pipeline(image, vision_mode="mock")
    assert calls == [(255, 0, 0), (0, 0, 255)]


@pytest.mark.parametrize("box", [(60, 30, 80, 80), (-10, 30, 40, 40), (20, 140, 40, 40)])
def test_out_of_bounds_face_seed_does_not_invent_foreground(monkeypatch, box):
    monkeypatch.setattr(subject, "_face_box", lambda image: box)
    assert subject.extract_subject(Image.new("RGB", (80, 160), (245, 194, 158))) is None


def test_segmentation_is_stable_across_prior_rng_state_and_threads(monkeypatch):
    import cv2

    monkeypatch.setattr(subject, "_face_box", lambda image: None)
    image = Image.new("RGB", (240, 480), (245, 245, 245))
    draw = ImageDraw.Draw(image)
    draw.ellipse((75, 30, 165, 120), fill=(210, 160, 120))
    draw.rectangle((65, 130, 175, 450), fill=(0, 120, 215))

    def extract(seed):
        cv2.setRNGSeed(seed)
        result = subject.extract_subject(image)
        assert result is not None
        return result[0]

    seeds = (0, 1, 7, 42, 12345)
    masks = [extract(seed) for seed in seeds]
    with ThreadPoolExecutor(max_workers=3) as pool:
        masks.extend(pool.map(extract, reversed(seeds)))
    for mask in masks[1:]:
        np.testing.assert_array_equal(mask, masks[0])
