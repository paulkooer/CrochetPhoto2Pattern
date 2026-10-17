"""Shared segmentation is scoped to one image and one pipeline run."""
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pytest
from PIL import Image, ImageDraw

from app.models import subject
from app.models.orchestrator import PipelineOrchestrator
from app.models.subject import SubjectObservation


@pytest.mark.parametrize("mode", ["local", "mock"])
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
    result = PipelineOrchestrator().run_full_pipeline(
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


def test_geometry_keeps_thin_parts_while_colors_use_cached_interior(monkeypatch):
    image = Image.new("RGB", (100, 80))
    mask = np.zeros((80, 100), dtype=bool)
    mask[5:35, 45:55] = True
    mask[35:75, 25:75] = True
    mask[10:30, 70:71] = True  # one-pixel appendage must survive geometry
    original = mask.copy()
    calls = []

    def extract(*args, **kwargs):
        calls.append(1)
        return mask, image

    monkeypatch.setattr(subject, "extract_subject", extract)
    observation = SubjectObservation(image)
    colors = observation.extract_colors(image)
    geometry = observation.extract(image)
    assert colors is not None and geometry is not None
    assert colors is observation.extract_colors(image)
    assert calls == [1]
    np.testing.assert_array_equal(geometry[0], original)
    assert geometry[0][20, 70] and not colors[0][20, 70]
    assert geometry[0][20, 45:55].sum() / geometry[0][50].sum() == 0.2
    assert colors[0][20].sum() / colors[0][50].sum() == pytest.approx(8 / 48)
    with pytest.raises(ValueError, match="图片"):
        observation.extract_colors(image.copy())


def test_color_interior_empty_or_misaligned_is_unavailable():
    image = Image.new("RGB", (40, 80))
    mask = np.zeros((80, 40), dtype=bool)
    mask[10:70, 20] = True
    assert subject.color_interior((mask, image)) is None
    assert mask.sum() == 60
    assert subject.color_interior((mask[:, :20], image)) is None
    assert subject.color_interior(None) is None


def _lit_and_shaded_single_colour_subject():
    """浅背景上的单色主体，下半身在阴影里——真实照片里兔子耳朵变深灰的成因。"""
    image = Image.new("RGB", (40, 40), (240, 240, 240))
    draw = ImageDraw.Draw(image)
    draw.rectangle((8, 8, 31, 31), fill=(216, 200, 184))   # 受光面
    draw.rectangle((8, 24, 31, 31), fill=(120, 120, 104))  # 同一表面的阴影
    mask = np.zeros((40, 40), dtype=bool)
    mask[8:32, 8:32] = True
    return image, mask


def test_color_interior_default_keeps_the_complete_evidence_sampling():
    """默认取样不剔除任何像素：证据记录要完整，深色细节交给人工复核。"""
    image, mask = _lit_and_shaded_single_colour_subject()
    interior, _ = subject.color_interior((mask, image))
    assert interior[15, 20] and interior[28, 20]
    assert interior.sum() == 22 * 22


def test_color_interior_samples_the_lit_part_only():
    """阴影不是毛线本色：投票取样只读受光面，几何掩码原样保留阴影。"""
    image, mask = _lit_and_shaded_single_colour_subject()
    interior, _ = subject.color_interior((mask, image), lit_only=True)
    assert interior[15, 20]                 # 受光面保留
    assert not interior[28, 20]             # 成片的暗区被剔出投票取样
    assert mask.sum() == 24 * 24            # 输入掩码未被修改


def test_shaded_area_keeps_thin_dark_stripes_as_features():
    """细条纹是真实特征（黑眼珠、衣服条纹），不能被当成阴影剔掉。"""
    image = Image.new("RGB", (100, 137), "white")
    ImageDraw.Draw(image).rectangle((0, 45, 99, 48), fill="black")   # 4px 条纹
    mask = np.ones((137, 100), dtype=bool)
    assert not subject.shaded_area(mask, image).any()


def test_shaded_area_treats_a_large_dark_region_as_shading():
    """成片的暗区才算阴影：核取短边/24，跨过核尺度的暗区被剔出投票取样。"""
    image = Image.new("RGB", (100, 137), "white")
    ImageDraw.Draw(image).rectangle((0, 45, 99, 95), fill="black")   # 成片暗区
    mask = np.ones((137, 100), dtype=bool)
    shaded = subject.shaded_area(mask, image)
    assert shaded[70, 50] and not shaded[10, 50]


def test_color_interior_guard_keeps_a_subject_darker_than_the_background():
    """主体本身比背景暗时阴影与本色分不开——护栏放弃剔除，整块保留。"""
    image = Image.new("RGB", (40, 40), (250, 250, 250))
    ImageDraw.Draw(image).rectangle((8, 8, 31, 31), fill=(40, 40, 40))
    mask = np.zeros((40, 40), dtype=bool)
    mask[8:32, 8:32] = True
    interior, _ = subject.color_interior((mask, image), lit_only=True)
    assert interior.sum() == 22 * 22


def test_color_interior_keeps_a_subject_lighter_than_a_dark_background():
    """暗背景上的浅色主体：没有"比背景暗"的取样像素，取样集合不变。"""
    image = Image.new("RGB", (40, 40), (40, 40, 40))
    ImageDraw.Draw(image).rectangle((8, 8, 31, 31), fill=(216, 200, 184))
    mask = np.zeros((40, 40), dtype=bool)
    mask[8:32, 8:32] = True
    interior, _ = subject.color_interior((mask, image), lit_only=True)
    assert interior.sum() == 22 * 22


def test_grabcut_output_is_not_eroded(monkeypatch):
    import cv2

    image = Image.new("RGB", (100, 80), "white")
    expected = np.zeros((80, 100), dtype=bool)
    expected[10:70, 40:60] = True
    expected[15:35, 60] = True

    def grabcut(arr, mask, *args):
        mask[:] = cv2.GC_BGD
        mask[expected] = cv2.GC_FGD

    monkeypatch.setattr(cv2, "grabCut", grabcut)
    monkeypatch.setattr(subject, "_face_box", lambda image: None)
    result = subject.extract_subject(image)
    assert result is not None
    np.testing.assert_array_equal(result[0], expected)
