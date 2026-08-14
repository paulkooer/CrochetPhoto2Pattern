"""Tests for ImageParser — covers pure functions that don't need a live API."""
import io
import json

import pytest
from PIL import Image

from app.models.image_parser import (
    ImageParser, _image_to_base64, _load_prompt,
    extract_color_palette, _nearest_yarn,
)
from app.schemas import ImageAnalysis


# ── _image_to_base64 ────────────────────────────────────────────────────────

def _make_image(mode: str = "RGB", size: tuple = (200, 200)) -> Image.Image:
    return Image.new(mode, size, color=(128, 64, 32))


def test_base64_rgb_image():
    img = _make_image("RGB")
    result = _image_to_base64(img)
    assert isinstance(result, str)
    assert len(result) > 100  # non-trivial base64


def test_base64_rgba_image_no_crash():
    """PNG with alpha channel must not crash on JPEG save."""
    img = _make_image("RGBA")
    result = _image_to_base64(img)  # should not raise
    assert isinstance(result, str)


def test_base64_large_image_is_resized():
    """Images larger than max_size should be resized."""
    big = _make_image("RGB", size=(2048, 2048))
    result = _image_to_base64(big, max_size=512)
    # Decode and check dimensions
    import base64
    raw = base64.b64decode(result)
    reopened = Image.open(io.BytesIO(raw))
    assert max(reopened.size) <= 512


# ── _load_prompt ─────────────────────────────────────────────────────────────

def test_load_prompt_returns_string():
    prompt = _load_prompt("vision_parser.txt")
    assert isinstance(prompt, str)
    assert len(prompt) > 10  # non-empty


def test_load_prompt_missing_file_returns_fallback():
    result = _load_prompt("nonexistent_file_xyz.txt")
    assert isinstance(result, str)
    assert len(result) > 0  # fallback, not empty


# ── _parse_response ──────────────────────────────────────────────────────────

VALID_JSON = {
    "body_type": "标准",
    "head_diameter_cm": 9.0,
    "height_cm": 18.0,
    "main_features": ["大眼睛"],
    "pose": "站立",
    "difficulty": "easy",
    "parts": ["头部", "身体"],
}


def test_parse_response_plain_json():
    content = json.dumps(VALID_JSON)
    result = ImageParser._parse_response(content)
    assert isinstance(result, ImageAnalysis)
    assert result.body_type == "标准"


def test_parse_response_markdown_fence():
    content = f"```json\n{json.dumps(VALID_JSON)}\n```"
    result = ImageParser._parse_response(content)
    assert result.difficulty == "easy"


def test_parse_response_with_extra_text():
    """Should extract JSON even if LLM adds explanation text around it."""
    content = f"Here is the analysis:\n{json.dumps(VALID_JSON)}\nHope that helps!"
    result = ImageParser._parse_response(content)
    assert result.height_cm == 18.0


def test_parse_response_invalid_raises():
    with pytest.raises(RuntimeError):
        ImageParser._parse_response("This is not JSON at all.")


# ── _mock_analysis ───────────────────────────────────────────────────────────

def test_mock_analysis_returns_valid_schema():
    result = ImageParser._mock_analysis()
    assert isinstance(result, ImageAnalysis)
    assert result.difficulty in ("easy", "medium", "hard")
    assert result.head_diameter_cm > 0
    assert len(result.parts) > 0

# ── extract_color_palette ────────────────────────────────────────────────────

def test_color_palette_white_image():
    """Pure white image → 白色 in palette."""
    img = Image.new("RGB", (80, 80), (255, 255, 255))
    colors = extract_color_palette(img, n_colors=3)
    assert "白色" in colors


def test_color_palette_red_image():
    """Pure red image → 红色 in palette."""
    img = Image.new("RGB", (80, 80), (255, 0, 0))
    colors = extract_color_palette(img, n_colors=3)
    assert "红色" in colors


def test_color_palette_skin_tone():
    """Skin-tone image → 浅肤色 in palette."""
    img = Image.new("RGB", (80, 80), (245, 194, 158))
    colors = extract_color_palette(img, n_colors=3)
    assert "浅肤色" in colors


def test_color_palette_rgba_no_crash():
    """RGBA image should not crash and return at least one color."""
    img = Image.new("RGBA", (80, 80), (70, 130, 180, 200))
    colors = extract_color_palette(img, n_colors=3)
    assert len(colors) >= 1


def test_nearest_yarn_black():
    assert _nearest_yarn(0, 0, 0) == "黑色"


def test_nearest_yarn_white():
    assert _nearest_yarn(255, 255, 255) == "白色"


def test_mock_analysis_has_no_colors_by_default():
    """Mock analysis without image has no recommended_colors."""
    result = ImageParser._mock_analysis()
    assert result.recommended_colors is None
