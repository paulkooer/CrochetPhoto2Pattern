import os
import io
import json
import re
import base64
import logging
from pathlib import Path
from typing import Optional

from PIL import Image

from ..schemas import ImageAnalysis

logger = logging.getLogger(__name__)

# Load prompt template
_PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts"


# Hardcoded fallback in case prompt file is missing
_FALLBACK_VISION_PROMPT = """分析这张照片中的人物，输出严格 JSON 格式（不要输出任何其他文字）：
{"body_type": "标准", "head_diameter_cm": 9.0, "height_cm": 18.0,
 "main_features": ["..."], "pose": "站立", "difficulty": "easy",
 "parts": ["头部", "身体", ...]}"""


def _load_prompt(name: str) -> str:
    """Load a prompt template from the prompts directory."""
    path = _PROMPT_DIR / name
    if path.exists():
        return path.read_text(encoding="utf-8")
    logger.warning("Prompt template %s not found, using fallback", name)
    return _FALLBACK_VISION_PROMPT


def _image_to_base64(image: Image.Image, max_size: int = 1024) -> str:
    """Convert PIL Image to base64, resizing if needed for API limits."""
    # Resize large images to reduce API costs
    # Ensure RGB mode (RGBA/P/L → RGB) for JPEG compatibility
    if image.mode != "RGB":
        image = image.convert("RGB")

    if max(image.size) > max_size:
        image = image.copy()
        image.thumbnail((max_size, max_size), Image.LANCZOS)

    buffered = io.BytesIO()
    image.save(buffered, format="JPEG", quality=85)
    return base64.b64encode(buffered.getvalue()).decode("utf-8")


# Yarn color name lookup table: (R, G, B) → yarn name
_YARN_COLORS = [
    ((255, 228, 196), "米色"),
    ((255, 218, 185), "桃肤色"),
    ((245, 194, 158), "浅肤色"),
    ((210, 140,  80), "棕肤色"),
    ((139,  90,  43), "深棕色"),
    ((255, 255, 255), "白色"),
    ((240, 240, 240), "浅灰色"),
    ((180, 180, 180), "灰色"),
    ((100, 100, 100), "深灰色"),
    (( 30,  30,  30), "黑色"),
    ((255,   0,   0), "红色"),
    ((220,  50,  50), "暗红色"),
    ((255, 150, 150), "粉红色"),
    ((255, 105, 180), "玫红色"),
    ((255, 200,   0), "金黄色"),
    ((255, 165,   0), "橙色"),
    ((255, 255,   0), "黄色"),
    (( 50, 205,  50), "草绿色"),
    ((  0, 128,   0), "深绿色"),
    ((  0, 200, 200), "青色"),
    ((  0, 120, 215), "蓝色"),
    (( 70, 130, 180), "钢蓝色"),
    ((128,   0, 128), "紫色"),
    ((216, 191, 216), "薰衣草色"),
]


def _nearest_yarn(r: int, g: int, b: int) -> str:
    """Find the nearest yarn color name using Euclidean distance in RGB space."""
    best_name, best_dist = "未知色", float("inf")
    for (cr, cg, cb), name in _YARN_COLORS:
        dist = (r - cr) ** 2 + (g - cg) ** 2 + (b - cb) ** 2
        if dist < best_dist:
            best_dist, best_name = dist, name
    return best_name


def extract_color_palette(image: Image.Image, n_colors: int = 5) -> list[str]:
    """Extract dominant colors from an image and map to yarn color names.

    Uses PIL's built-in median-cut quantization — no extra dependencies.
    Returns a deduplicated list of yarn color names sorted by dominance.
    """
    try:
        img = image.convert("RGB").resize((150, 150))
        quantized = img.quantize(colors=n_colors * 2, method=Image.Quantize.MEDIANCUT)
        # getcolors() on quantized image: returns (count, palette_index)
        pixel_counts: list[tuple[int, int]] = quantized.getcolors(maxcolors=n_colors * 2 + 50) or []
        # Sort by count descending
        pixel_counts.sort(key=lambda x: x[0], reverse=True)

        palette = quantized.getpalette()  # flat [R,G,B, R,G,B, ...]
        seen: set[str] = set()
        names: list[str] = []
        for _count, idx in pixel_counts:
            r, g, b = palette[idx * 3], palette[idx * 3 + 1], palette[idx * 3 + 2]
            name = _nearest_yarn(r, g, b)
            if name not in seen:
                seen.add(name)
                names.append(name)
            if len(names) >= n_colors:
                break
        return names
    except Exception as e:
        logger.warning("Color palette extraction failed: %s", e)
        return []


class ImageParser:
    """Parse character photos using Vision API (OpenAI or Anthropic)."""

    def __init__(self, openai_key: Optional[str] = None, anthropic_key: Optional[str] = None):
        self.openai_key = openai_key or os.getenv("OPENAI_API_KEY")
        self.anthropic_key = anthropic_key or os.getenv("ANTHROPIC_API_KEY")
        self._prompt = _load_prompt("vision_parser.txt")

    def parse_image(self, image: Image.Image) -> ImageAnalysis:
        """Parse an image and return structured analysis.

        Tries Anthropic first; if that call fails, falls back to OpenAI.
        Mock data is used only when no API key is configured at all —
        if keys were provided but every provider failed, we raise so the
        user knows the result is not real.
        """
        img_b64 = _image_to_base64(image)
        colors = extract_color_palette(image)

        result: Optional[ImageAnalysis] = None
        errors: list[str] = []
        if self.anthropic_key:
            try:
                result = self._parse_with_anthropic(img_b64)
            except Exception as e:
                errors.append(str(e))
                logger.warning("Anthropic parse failed, trying next provider: %s", e)
        if result is None and self.openai_key:
            try:
                result = self._parse_with_openai(img_b64)
            except Exception as e:
                errors.append(str(e))
                logger.warning("OpenAI parse failed: %s", e)
        if result is None:
            if errors:
                raise RuntimeError(
                    "Vision 解析失败（所有可用渠道均已尝试）: " + " | ".join(errors)
                )
            logger.warning("No API key provided, returning mock analysis")
            result = self._mock_analysis()

        # Attach color palette (override only if not already set)
        if colors and not result.recommended_colors:
            result = result.model_copy(update={"recommended_colors": colors})
        return result

    def _parse_with_openai(self, img_b64: str) -> ImageAnalysis:
        """Call OpenAI GPT-4o Vision API."""
        from openai import OpenAI

        client = OpenAI(api_key=self.openai_key, timeout=60.0, max_retries=3)
        try:
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": self._prompt},
                        {"type": "image_url", "image_url": {
                            "url": f"data:image/jpeg;base64,{img_b64}"
                        }}
                    ]
                }],
                max_tokens=1000,
                temperature=0.2,
            )
            content = response.choices[0].message.content
            return self._parse_response(content)
        except Exception as e:
            logger.error("OpenAI Vision API error: %s", e)
            raise RuntimeError(f"OpenAI Vision API 调用失败: {e}") from e

    def _parse_with_anthropic(self, img_b64: str) -> ImageAnalysis:
        """Call Anthropic Claude vision with structured outputs.

        `messages.parse` enforces the ImageAnalysis JSON schema server-side
        and validates client-side, so no manual JSON extraction is needed.
        429/5xx are retried by the SDK itself (max_retries).
        """
        import anthropic

        client = anthropic.Anthropic(
            api_key=self.anthropic_key, timeout=60.0, max_retries=3
        )
        try:
            response = client.messages.parse(
                model="claude-sonnet-5",
                # Sonnet 5 runs adaptive thinking by default and max_tokens
                # caps thinking + answer together, so leave headroom.
                max_tokens=4000,
                output_config={"effort": "low"},
                output_format=ImageAnalysis,
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": img_b64,
                            },
                        },
                        {"type": "text", "text": self._prompt},
                    ],
                }],
            )
            if response.stop_reason == "refusal":
                raise RuntimeError("模型拒绝了该请求 (refusal)")
            if response.parsed_output is None:
                raise RuntimeError("响应未能解析为 ImageAnalysis 结构")
            return response.parsed_output
        except Exception as e:
            logger.error("Anthropic Vision API error: %s", e)
            raise RuntimeError(f"Anthropic Vision API 调用失败: {e}") from e

    @staticmethod
    def _parse_response(content: str) -> ImageAnalysis:
        """Parse JSON from LLM response, handling markdown fences and extra text."""
        text = content.strip()

        # Strategy 1: Strip markdown code fences
        if text.startswith("```"):
            lines = text.split("\n")
            end = -1 if lines[-1].strip() == "```" else len(lines)
            text = "\n".join(lines[1:end])

        # Strategy 2: Try direct parse first
        try:
            data = json.loads(text)
            return ImageAnalysis(**data)
        except (json.JSONDecodeError, ValueError):
            pass

        # Strategy 3: Extract first {...} block via regex
        match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group())
                return ImageAnalysis(**data)
            except (json.JSONDecodeError, ValueError):
                pass

        logger.error("Failed to parse Vision response. Content: %s", content[:500])
        raise RuntimeError("Vision 返回格式解析失败: 无法从响应中提取有效 JSON")

    @staticmethod
    def _mock_analysis() -> ImageAnalysis:
        """Return mock analysis for demo/testing without API keys."""
        return ImageAnalysis(
            body_type="标准",
            head_diameter_cm=9.0,
            height_cm=18.0,
            main_features=["大眼睛", "小鼻子", "圆脸"],
            pose="站立",
            difficulty="easy",
            parts=["头部", "身体", "手臂", "腿部"]
        )
