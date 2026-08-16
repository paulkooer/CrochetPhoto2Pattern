"""Tests for ImageParser — covers pure functions and mocked provider flows."""
import io
import json
import sys
import types

import pytest
from PIL import Image

from app.models.colors import nearest_yarn
from app.models.image_parser import (
    ImageParser,
    _image_to_base64,
    _load_prompt,
    extract_color_palette,
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


def test_parse_response_skips_invalid_leading_object():
    """前文出现无法通过校验的 {...} 时应继续扫描后面的有效对象。"""
    content = "oops {\"foo\": 1} then " + json.dumps(VALID_JSON)
    result = ImageParser._parse_response(content)
    assert result.body_type == "标准"


def test_parse_response_deeply_nested_extra_text():
    """raw_decode 扫描不受嵌套深度限制（旧正则只支持一层嵌套）。"""
    obj = dict(VALID_JSON)
    obj["main_features"] = ["大眼睛"]
    wrapped = {"outer": {"deep": {"deeper": [1, 2]}}, **obj}
    content = "prefix " + json.dumps(wrapped) + " suffix"
    result = ImageParser._parse_response(content)
    assert result.body_type == "标准"


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


def test_color_palette_sorted_by_dominance_and_dedup():
    """占比高的颜色排在前；映射到同名毛线色的簇应去重。"""
    img = Image.new("RGB", (100, 100))
    px = img.load()
    for y in range(100):
        for x in range(100):
            px[x, y] = (255, 0, 0) if x < 70 else (0, 0, 255)
    colors = extract_color_palette(img, n_colors=3)
    assert colors[0] == "红色"  # 70% 占比必须排第一
    assert len(colors) >= 2  # 蓝色区域也应被提取
    assert len(colors) == len(set(colors))  # 同名毛线色去重


def test_nearest_yarn_black():
    assert nearest_yarn(0, 0, 0)[0] == "黑色"


def test_nearest_yarn_white():
    assert nearest_yarn(255, 255, 255)[0] == "白色"


def test_mock_analysis_has_no_colors_by_default():
    """Mock analysis without image has no recommended_colors."""
    result = ImageParser._mock_analysis()
    assert result.recommended_colors is None


# ── provider 降级与 mock 流程（monkeypatch，不发真实请求）────────────────────


def _img() -> Image.Image:
    return Image.new("RGB", (60, 60), (245, 194, 158))


def _analysis(**over) -> ImageAnalysis:
    base = dict(
        body_type="标准", head_diameter_cm=9.0, height_cm=18.0,
        main_features=["大眼睛"], pose="站立", difficulty="easy",
        parts=["头部", "身体"],
    )
    base.update(over)
    return ImageAnalysis(**base)


def test_no_keys_uses_mock_and_attaches_local_palette(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    # 隔离真实 .env（ImageParser.__init__ 会 load_dotenv），
    # 否则本机有 .env 的开发者跑测试会打真实 API。
    monkeypatch.setattr("app.models.image_parser.load_dotenv", lambda *a, **k: False)
    parser = ImageParser()
    result = parser.parse_image(_img())
    assert result.body_type == "标准"  # mock 数据
    # 本地量化色板必须被附加（纯肤色图 → 浅肤色）
    assert result.recommended_colors and result.recommended_colors[0] == "浅肤色"


def test_anthropic_failure_falls_back_to_openai(monkeypatch):
    parser = ImageParser(openai_key="k-oai", anthropic_key="k-ant")
    monkeypatch.setattr(
        parser, "_parse_with_anthropic",
        lambda _b64: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    monkeypatch.setattr(
        parser, "_parse_with_openai",
        lambda _b64: _analysis(recommended_colors=["模型幻觉色<img>"]),
    )
    result = parser.parse_image(_img())
    assert result.pose == "站立"
    # 本地色板永远优先于模型输出的颜色字段
    assert result.recommended_colors[0] == "浅肤色"


def test_all_providers_fail_raises(monkeypatch):
    """有 key 但全渠道失败时必须抛错，而不是静默给 Mock 数据。"""
    parser = ImageParser(openai_key="k", anthropic_key="k")
    monkeypatch.setattr(
        parser, "_parse_with_anthropic",
        lambda _b64: (_ for _ in ()).throw(RuntimeError("ant down")),
    )
    monkeypatch.setattr(
        parser, "_parse_with_openai",
        lambda _b64: (_ for _ in ()).throw(RuntimeError("oai down")),
    )
    with pytest.raises(RuntimeError, match="ant down"):
        parser.parse_image(_img())


def test_anthropic_refusal_raises(monkeypatch):
    """stop_reason=refusal 应转为明确的 RuntimeError。"""
    fake_mod = types.ModuleType("anthropic")

    class _Resp:
        stop_reason = "refusal"
        parsed_output = None

    class _Messages:
        def parse(self, **_kw):
            return _Resp()

    class _Client:
        messages = _Messages()

    fake_mod.Anthropic = lambda **_kw: _Client()
    monkeypatch.setitem(sys.modules, "anthropic", fake_mod)

    parser = ImageParser(anthropic_key="k")
    with pytest.raises(RuntimeError, match="refusal|拒绝"):
        parser._parse_with_anthropic("x")


def test_openai_call_uses_json_mode_and_parses(monkeypatch):
    """OpenAI 调用必须开 JSON mode 并能解析响应（此前该函数 0 覆盖）。"""
    fake_mod = types.ModuleType("openai")
    recorded = {}

    class _Message:
        content = json.dumps(VALID_JSON)

    class _Choice:
        message = _Message()

    class _Resp:
        choices = [_Choice()]

    class _Completions:
        def create(self, **kwargs):
            recorded.update(kwargs)
            return _Resp()

    class _Chat:
        completions = _Completions()

    class _Client:
        chat = _Chat()

    fake_mod.OpenAI = lambda **_kw: _Client()
    monkeypatch.setitem(sys.modules, "openai", fake_mod)

    parser = ImageParser(openai_key="k")
    result = parser._parse_with_openai("b64")
    assert result.body_type == "标准"
    assert recorded["model"] == "gpt-4o"
    assert recorded["response_format"] == {"type": "json_object"}
    assert recorded["max_tokens"] >= 2000  # 防 parts 列表截断
    assert recorded["temperature"] <= 0.2


def test_anthropic_success_records_usage(monkeypatch):
    """成功解析后 token 用量应记录到 last_usage（UI 成本展示依赖）。"""
    fake_mod = types.ModuleType("anthropic")

    class _Usage:
        input_tokens = 1200
        output_tokens = 340

    class _Resp:
        stop_reason = "end_turn"
        parsed_output = _analysis()
        usage = _Usage()

    class _Messages:
        def parse(self, **_kw):
            return _Resp()

    class _Client:
        messages = _Messages()

    fake_mod.Anthropic = lambda **_kw: _Client()
    monkeypatch.setitem(sys.modules, "anthropic", fake_mod)

    parser = ImageParser(anthropic_key="k")
    result = parser._parse_with_anthropic("x")
    assert result.body_type == "标准"
    assert parser.last_usage == {
        "provider": "anthropic", "input_tokens": 1200, "output_tokens": 340,
    }


def test_openai_success_records_usage(monkeypatch):
    fake_mod = types.ModuleType("openai")

    class _Usage:
        prompt_tokens = 900
        completion_tokens = 210

    class _Message:
        content = json.dumps(VALID_JSON)

    class _Choice:
        message = _Message()

    class _Resp:
        choices = [_Choice()]
        usage = _Usage()

    class _Completions:
        def create(self, **_kwargs):
            return _Resp()

    class _Chat:
        completions = _Completions()

    class _Client:
        chat = _Chat()

    fake_mod.OpenAI = lambda **_kw: _Client()
    monkeypatch.setitem(sys.modules, "openai", fake_mod)

    parser = ImageParser(openai_key="k")
    parser._parse_with_openai("b64")
    assert parser.last_usage == {
        "provider": "openai", "input_tokens": 900, "output_tokens": 210,
    }


def test_mock_path_sets_watermark_meta(monkeypatch):
    """无 Key 走 Mock 时 vision_meta 标记 mock，全链路可辨演示数据（fable5 F9）。"""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr("app.models.image_parser.load_dotenv", lambda *a, **k: False)
    parser = ImageParser()
    parser.parse_image(_img())
    assert parser.last_local_meta["source"] == "mock"
    assert "与照片内容无关" in parser.last_local_meta["note"]


def test_installed_anthropic_sdk_contract():
    """契约测试：已安装 SDK 的 messages.parse 必须支持 structured outputs 参数。

    缩小 fake-SDK 假信心面：不再只靠 mock 替身，直接对已装包做签名断言
    （fable5 用此法实测 0.95.0 支持 output_format/output_config）。
    """
    anthropic = pytest.importorskip("anthropic")
    import inspect

    client = anthropic.Anthropic(api_key="contract-test")
    params = inspect.signature(client.messages.parse).parameters
    assert "output_format" in params
    assert "output_config" in params


def test_parse_response_carries_semantic_fields():
    data = dict(VALID_JSON, hair_color="深棕色", top_color="蓝色",
                bottom_color=None, clothing_type="裙子")
    result = ImageParser._parse_response(json.dumps(data))
    assert result.hair_color == "深棕色"
    assert result.clothing_type == "裙子"
    assert result.bottom_color is None


def test_llm_success_sets_provider_meta(monkeypatch):
    """LLM 成功路径 vision_meta 记录 provider（渲染层区分 AI/本地/Mock）。"""
    parser = ImageParser(anthropic_key="k")
    monkeypatch.setattr(parser, "_parse_with_anthropic", lambda _b: _analysis())
    parser.parse_image(_img())
    assert parser.last_local_meta["source"] == "anthropic"
