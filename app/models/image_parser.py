import base64
import io
import json
import logging
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from PIL import Image

from ..schemas import ImageAnalysis
from .colors import nearest_yarn

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


def extract_color_palette(image: Image.Image, n_colors: int = 5) -> list[str]:
    """Extract dominant colors from an image and map to yarn color names.

    Uses PIL's built-in median-cut quantization — no extra dependencies.
    Returns a deduplicated list of yarn color names sorted by dominance.
    """
    try:
        img = image.convert("RGB")
        # thumbnail 保纵横比：固定 resize((150,150)) 会让全景图的横向颜色
        # 占比被人为放大。thumbnail 原地修改，需先 copy。
        img = img.copy()
        img.thumbnail((150, 150))
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
            name = nearest_yarn(r, g, b)[0]
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

    # 模型名可用环境变量覆盖，升级/换模型不必改代码。
    DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-5"
    DEFAULT_OPENAI_MODEL = "gpt-4o"

    def __init__(self, openai_key: Optional[str] = None, anthropic_key: Optional[str] = None):
        # 以库形式使用时 main.py 可能尚未执行 load_dotenv()；此处幂等补一次。
        load_dotenv()
        self.openai_key = openai_key or os.getenv("OPENAI_API_KEY")
        self.anthropic_key = anthropic_key or os.getenv("ANTHROPIC_API_KEY")
        self.anthropic_model = os.getenv("ANTHROPIC_VISION_MODEL", self.DEFAULT_ANTHROPIC_MODEL)
        self.openai_model = os.getenv("OPENAI_VISION_MODEL", self.DEFAULT_OPENAI_MODEL)
        # 最近一次成功调用的 token 用量（供 UI 展示/成本估算）
        self.last_usage: dict = {}
        # 最近一次本地视觉估算的 meta（无 LLM 路径）
        self.last_local_meta: dict = {}
        self._prompt = _load_prompt("vision_parser.txt")

    def parse_image_local(self, image: Image.Image) -> ImageAnalysis:
        """Local no-LLM analysis: face detection + proportion estimation.

        与 parse_image 的 LLM 路径互不影响；估算依据记录在
        self.last_local_meta 供 UI 透明展示。
        """
        # 延迟导入避免 local_vision ↔ image_parser 循环依赖
        from .local_vision import analyze

        analysis, meta = analyze(image)
        self.last_local_meta = meta
        return analysis

    def parse_image(self, image: Image.Image) -> ImageAnalysis:
        """Parse an image and return structured analysis.

        Tries Anthropic first; if that call fails, falls back to OpenAI.
        Mock data is used only when no API key is configured at all —
        if keys were provided but every provider failed, we raise so the
        user knows the result is not real.
        """
        self.last_local_meta = {}  # 每次解析重置，防止上次的来源信息泄漏
        img_b64 = _image_to_base64(image)
        colors = extract_color_palette(image)

        result: Optional[ImageAnalysis] = None
        provider: Optional[str] = None
        errors: list[str] = []
        if self.anthropic_key:
            try:
                result = self._parse_with_anthropic(img_b64)
                provider = "anthropic"
            except Exception as e:
                errors.append(str(e))
                logger.warning("Anthropic parse failed, trying next provider: %s", e)
        if result is None and self.openai_key:
            try:
                result = self._parse_with_openai(img_b64)
                provider = "openai"
            except Exception as e:
                errors.append(str(e))
                logger.warning("OpenAI parse failed: %s", e)
        if result is not None:
            # LLM 来源也写入 vision_meta：渲染层可区分 AI/本地/Mock
            self.last_local_meta = {
                "source": provider,
                "note": "AI 语义解析（视觉模型）",
            }
        if result is None:
            if errors:
                raise RuntimeError(
                    "Vision 解析失败（所有可用渠道均已尝试）: " + " | ".join(errors)
                )
            logger.warning("No API key provided, returning mock analysis")
            # Mock 水印：渲染/导出/备份链路都能看出这是演示数据（F9）
            self.last_local_meta = {
                "source": "mock",
                "note": "Mock 演示数据，与照片内容无关（仅供体验流程）",
            }
            result = self._mock_analysis()

        # 本地直接从原图量化的色板是唯一可信来源，永远优先于模型输出
        # （模型字段可能缺失，也可能被图片内文字注入污染）。
        if colors:
            result = result.model_copy(update={"recommended_colors": colors})
        return result

    def _parse_with_openai(self, img_b64: str) -> ImageAnalysis:
        """Call OpenAI GPT-4o Vision API."""
        from openai import OpenAI

        client = OpenAI(api_key=self.openai_key, timeout=60.0, max_retries=3)
        try:
            response = client.chat.completions.create(
                model=self.openai_model,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": self._prompt},
                        {"type": "image_url", "image_url": {
                            "url": f"data:image/jpeg;base64,{img_b64}"
                        }}
                    ]
                }],
                # parts 列表较长的 JSON 容易超 1000 tokens 被截断，留足余量；
                # JSON mode 强制响应为合法 JSON（gpt-4o 起支持，prompt 含
                # "JSON" 字样是其前置要求——vision_parser.txt 已满足）。
                max_tokens=2000,
                temperature=0.2,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content
            usage = getattr(response, "usage", None)
            if usage is not None:
                self.last_usage = {
                    "provider": "openai",
                    "input_tokens": getattr(usage, "prompt_tokens", None),
                    "output_tokens": getattr(usage, "completion_tokens", None),
                }
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
                model=self.anthropic_model,
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
            usage = getattr(response, "usage", None)
            if usage is not None:
                self.last_usage = {
                    "provider": "anthropic",
                    "input_tokens": getattr(usage, "input_tokens", None),
                    "output_tokens": getattr(usage, "output_tokens", None),
                }
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

        # Strategy 3: Scan for the first {...} via raw_decode — handles any
        # nesting depth (the old regex only coped with one level).
        decoder = json.JSONDecoder()
        for start, ch in enumerate(text):
            if ch != "{":
                continue
            try:
                obj, _end = decoder.raw_decode(text, start)
            except (json.JSONDecodeError, ValueError):
                continue
            if isinstance(obj, dict):
                try:
                    return ImageAnalysis(**obj)
                except ValueError:
                    continue

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
