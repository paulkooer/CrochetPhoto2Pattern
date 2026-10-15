"""Original fixtures isolate narrow-stripe extraction from segmentation."""
import numpy as np
import pytest
from PIL import Image, ImageDraw

from app.models.color_design import color_blocks_for_part, round_color, vertical_color_bands
from app.models.color_observation import ColorObservation
from app.models.subject import SubjectObservation


def extract(image, *, mask=None, refine=True, observation=None):
    subject = SubjectObservation(image)
    if mask is None:
        mask = np.ones((image.height, image.width), dtype=bool)
    subject.__dict__["segmentation"] = (mask, image)
    return vertical_color_bands(image, subject=subject, refine_stripes=refine, observation=observation)


@pytest.mark.parametrize("height", [100, 137, 160])
@pytest.mark.parametrize("start", [31, 45, 62])
def test_narrow_stripes_survive_coarse_bin_boundaries(height, start):
    image = Image.new("RGB", (100, height), "white")
    ImageDraw.Draw(image).rectangle((0, start, 99, start + 3), fill="black")
    assert all(b["color"] == "白色" for b in extract(image, refine=False))
    bands = extract(image)
    assert bands == [
        {"start": 0, "end": start / height, "color": "白色"},
        {"start": start / height, "end": (start + 4) / height, "color": "黑色"},
        {"start": (start + 4) / height, "end": 1, "color": "白色"},
    ]
    assert extract(image) == bands
    blocks = color_blocks_for_part(bands, "身体", {"身体": (0, 1)})
    assert round_color((start + 2) / height, blocks) == "黑色"


def test_one_pixel_noise_does_not_create_color_changes():
    image = Image.new("RGB", (160, 160), "white")
    draw = ImageDraw.Draw(image)
    for y in (13, 29, 47, 78, 121):
        draw.line((0, y, 159, y), fill="black")
    assert extract(image) == [{"start": 0, "end": 1, "color": "白色"}]


def test_minority_patches_stay_in_evidence_and_do_not_become_stripes():
    image = Image.new("RGB", (160, 160), "white")
    ImageDraw.Draw(image).rectangle((40, 45, 100, 90), fill="black")
    evidence = {}
    assert extract(image, observation=evidence) == [{"start": 0, "end": 1, "color": "白色"}]
    assert ColorObservation.model_validate(evidence).requires_review
    assert any(r["color"] == "黑色" for r in evidence["regions"])


def test_sparse_foreground_rows_cannot_override_coarse_vote():
    image = Image.new("RGB", (160, 160), "white")
    mask = np.ones((160, 160), dtype=bool)
    mask[40:44] = False
    mask[40:44, 80:82] = True
    ImageDraw.Draw(image).rectangle((80, 40, 81, 43), fill="black")
    assert extract(image, mask=mask) == [{"start": 0, "end": 1, "color": "白色"}]


def test_evidence_is_identical_with_or_without_refinement():
    image = Image.new("RGB", (100, 137), "white")
    ImageDraw.Draw(image).rectangle((0, 45, 99, 48), fill="black")
    baseline, refined = {}, {}
    extract(image, refine=False, observation=baseline)
    extract(image, observation=refined)
    assert baseline == refined
    assert ColorObservation.model_validate(refined).foreground_pixels == 13700
