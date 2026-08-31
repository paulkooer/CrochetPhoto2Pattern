import base64
import io
import ipaddress
import json
import logging
import os
import re
from pathlib import Path
from typing import Optional
from urllib.parse import urlsplit

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


def _sanitize_secrets(text: str, *keys: Optional[str]) -> str:
    """异常/日志文本脱敏（F14/F32）。

    依次替换当前实例持有的 Key（含前后缀级——服务端 401 回显常用
    "前 5 位 + ***…*** + 后 4 位"的半遮蔽形态，字面替换不命中）、
    sk-* token（收 * 进字符类且门限降至 4——覆盖半遮蔽回显）、
    Authorization 头。不遮蔽 URL/状态码/request id——保持可诊断性。
    """
    if not text:
        return text
    for key in keys:
        if key:
            text = text.replace(key, "***")
            if len(key) > 12:
                text = text.replace(key[:8], "sk-***").replace(
                    key[-6:], "***")
    text = re.sub(r"sk-[A-Za-z0-9_\-*]{4,}", "sk-***", text)
    text = re.sub(r"(?i)(authorization\s*:\s*bearer\s+)\S+", r"\1***", text)
    return text


def _validate_user_base_url(value: str, provider: str) -> str:
    """Validate an untrusted, caller-supplied API endpoint.

    Admin-controlled environment URLs intentionally are not passed through this
    check: private company gateways are a legitimate deployment configuration.
    UI/library supplied URLs, however, must not target obvious local/private
    services.  Deployment egress rules remain the authoritative DNS-rebinding
    defence; application URL parsing alone cannot provide that guarantee.
    """
    value = value.strip()
    parsed = urlsplit(value)
    if parsed.scheme.lower() != "https" or not parsed.hostname:
        raise ValueError(f"{provider} Base URL 必须是有效的 HTTPS 地址")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError(f"{provider} Base URL 不得包含凭据、查询参数或片段")

    host = parsed.hostname.rstrip(".").lower()
    blocked_names = {"localhost", "localhost.localdomain"}
    blocked_suffixes = (".localhost", ".local", ".internal", ".home.arpa")
    if host in blocked_names or host.endswith(blocked_suffixes):
        raise ValueError(f"{provider} Base URL 不得指向本机或私有网络")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address is not None and not address.is_global:
        raise ValueError(f"{provider} Base URL 不得指向本机或私有网络")
    return value


def _provider_config(
    provider: str,
    supplied_key: Optional[str],
    supplied_base_url: Optional[str],
    key_env: str,
    base_url_env: str,
) -> tuple[Optional[str], Optional[str]]:
    """Resolve one provider without mixing credentials from different sources.

    A user-controlled URL paired with a server environment key would send the
    server secret to that URL.  Keep UI/library credentials and endpoints as one
    pair; otherwise use the admin-controlled environment pair.
    """
    user_key = (supplied_key or "").strip() or None
    user_base_url = (supplied_base_url or "").strip() or None
    if user_base_url and not user_key:
        raise ValueError(
            f"自定义 {provider} Base URL 必须同时提供同来源的 API Key，"
            "不能与服务器环境变量中的 Key 混用"
        )
    if user_key:
        validated = (_validate_user_base_url(user_base_url, provider)
                     if user_base_url else None)
        return user_key, validated

    env_key = (os.getenv(key_env) or "").strip() or None
    env_base_url = (os.getenv(base_url_env) or "").strip() or None
    return env_key, env_base_url


def _image_to_base64(image: Image.Image, max_size: int = 1024) -> str:
    """Convert PIL Image to base64, resizing if needed for API limits."""
    # Resize large images to reduce API costs
    # Ensure RGB mode (RGBA/P/L → RGB) for JPEG compatibility
    if image.mode != "RGB":
        image = image.convert("RGB")

    if max(image.size) > max_size:
        image = image.copy()
        image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)

    buffered = io.BytesIO()
    image.save(buffered, format="JPEG", quality=85)
    return base64.b64encode(buffered.getvalue()).decode("utf-8")


def extract_color_palette(image: Image.Image, n_colors: int = 5) -> list[str]:
    """Extract dominant colors from an image and map to yarn color names.

    主体像素上做 S3 直量化（coverage 直选毛线色 + CIEDE2000 分配）——
    调色板每一色都是可购买毛线，背景不入板；分割不可用时回退全图。
    Returns a deduplicated list of yarn color names sorted by dominance.
    """
    try:
        import numpy as np

        from .colors import pick_yarn_palette
        img = image.convert("RGB")
        # thumbnail 保纵横比：固定 resize((150,150)) 会让全景图的横向颜色
        # 占比被人为放大。thumbnail 原地修改，需先 copy。
        img = img.copy()
        img.thumbnail((150, 150))
        source = img
        # 主体掩码可用 → 只统计主体像素（背景剔除比色彩距离阈值更稳）
        try:
            from .subject import extract_subject
            res = extract_subject(image, max_side=150)
            if res is not None:
                mask, small = res
                subj = np.asarray(small)[mask]
                if len(subj) >= 50:  # 主体像素太少时统计无意义，回退全图
                    source = Image.fromarray(
                        subj.reshape(len(subj), 1, 3).astype(np.uint8))
        except Exception as e:
            logger.debug("subject-guided palette skipped: %s", e)
        pixels = [tuple(int(v) for v in px) for px in np.asarray(
            source, dtype=np.uint8).reshape(-1, 3)]
        rgbs = pick_yarn_palette(pixels, n_colors)
        names: list[str] = []
        seen: set[str] = set()
        for rgb in rgbs:
            name = nearest_yarn(*rgb)[0]
            if name not in seen:
                seen.add(name)
                names.append(name)
        return names
    except Exception as e:
        logger.warning("Color palette extraction failed: %s", e)
        return []


class ImageParser:
    """Parse character photos using Vision API (OpenAI or Anthropic)."""

    # 模型名可用环境变量覆盖，升级/换模型不必改代码。
    DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-5"
    DEFAULT_OPENAI_MODEL = "gpt-4o"

    def __init__(
        self,
        openai_key: Optional[str] = None,
        anthropic_key: Optional[str] = None,
        openai_base_url: Optional[str] = None,
        anthropic_base_url: Optional[str] = None,
    ):
        # 以库形式使用时 main.py 可能尚未执行 load_dotenv()；此处幂等补一次。
        load_dotenv()
        self.openai_key, self.openai_base_url = _provider_config(
            "OpenAI", openai_key, openai_base_url,
            "OPENAI_API_KEY", "OPENAI_BASE_URL")
        self.anthropic_key, self.anthropic_base_url = _provider_config(
            "Anthropic", anthropic_key, anthropic_base_url,
            "ANTHROPIC_API_KEY", "ANTHROPIC_BASE_URL")
        self.anthropic_model = os.getenv("ANTHROPIC_VISION_MODEL", self.DEFAULT_ANTHROPIC_MODEL)
        self.openai_model = os.getenv("OPENAI_VISION_MODEL", self.DEFAULT_OPENAI_MODEL)
        # 最近一次成功调用的 token 用量（供 UI 展示/成本估算）
        self.last_usage: dict = {}
        # 最近一次本地视觉估算的 meta（无 LLM 路径）
        self.last_local_meta: dict = {}
        self._prompt = _load_prompt("vision_parser.txt")
        self._span_hints: Optional[str] = None

    def _sanitize(self, text: str) -> str:
        return _sanitize_secrets(text, self.openai_key, self.anthropic_key)

    def _prompt_with_hints(self) -> str:
        """主 prompt + 可选的实测 span 参考段（T6）。"""
        if self._span_hints:
            return f"{self._prompt}\n\n{self._span_hints}"
        return self._prompt

    def parse_image_local(
        self,
        image: Image.Image,
        geometry_profile: Optional[list[float]] = None,
        geometry_observed: bool = False,
    ) -> ImageAnalysis:
        """Local no-LLM analysis: face detection + proportion estimation.

        与 parse_image 的 LLM 路径互不影响；估算依据记录在
        self.last_local_meta 供 UI 透明展示。
        """
        # 延迟导入避免 local_vision ↔ image_parser 循环依赖
        from .local_vision import analyze

        analysis, meta = analyze(
            image,
            geometry_profile=geometry_profile,
            geometry_observed=geometry_observed,
        )
        self.last_local_meta = meta
        return analysis

    def parse_image(self, image: Image.Image,
                    span_hints: Optional[str] = None) -> ImageAnalysis:
        """Parse an image and return structured analysis.

        Tries Anthropic first; if that call fails, falls back to OpenAI.
        Mock data is used only when no API key is configured at all —
        if keys were provided but every provider failed, we raise so the
        user knows the result is not real.

        span_hints（T6）：姿态关键点实测的分段参考文案，附加进 prompt
        供模型交叉验证 parts 判断（S1×LLM 协同）。
        """
        self.last_local_meta = {}  # 每次解析重置，防止上次的来源信息泄漏
        self._span_hints = span_hints
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
                errors.append(self._sanitize(str(e)))
                logger.warning("Anthropic parse failed, trying next provider: %s",
                               self._sanitize(str(e)))
        if result is None and self.openai_key:
            try:
                result = self._parse_with_openai(img_b64)
                provider = "openai"
            except Exception as e:
                errors.append(self._sanitize(str(e)))
                logger.warning("OpenAI parse failed: %s", self._sanitize(str(e)))
        if result is not None:
            # LLM 来源也写入 vision_meta：渲染层可区分 AI/本地/Mock
            self.last_local_meta = {
                "source": provider,
                "note": "AI 语义解析（视觉模型）",
            }
        if result is None:
            if errors:
                raise RuntimeError(
                    "Vision 解析失败（所有可用渠道均已尝试）: "
                    + self._sanitize(" | ".join(errors))
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
        """Call OpenAI Vision with strict structured outputs (S2).

        `chat.completions.parse` 把 pydantic 模型转成 strict json_schema，
        服务端保证输出符合 ImageAnalysis——与 Anthropic `messages.parse`
        路径对称。失败时带错误反馈重试一次（让模型自修，而非盲目重掷）。
        旧版 SDK 无 parse 时回退 json_object 路径（_parse_with_openai_legacy）。
        """
        from openai import OpenAI

        client = OpenAI(api_key=self.openai_key, base_url=self.openai_base_url,
                        timeout=60.0, max_retries=3)
        try:
            if not hasattr(client.chat.completions, "parse"):
                return self._parse_with_openai_legacy(client, img_b64)

            base_messages = [{
                "role": "user",
                "content": [
                    {"type": "text", "text": self._prompt_with_hints()},
                    {"type": "image_url", "image_url": {
                        "url": f"data:image/jpeg;base64,{img_b64}"
                    }}
                ]
            }]
            messages = base_messages
            last_err: Exception = RuntimeError("unreachable")
            for attempt in range(2):
                response = client.chat.completions.parse(
                    model=self.openai_model,
                    messages=messages,
                    max_tokens=2000,
                    temperature=0.2,
                    response_format=ImageAnalysis,
                )
                usage = getattr(response, "usage", None)
                if usage is not None:
                    self.last_usage = {
                        "provider": "openai",
                        "input_tokens": getattr(usage, "prompt_tokens", None),
                        "output_tokens": getattr(usage, "completion_tokens", None),
                    }
                message = response.choices[0].message
                refusal = getattr(message, "refusal", None)
                if refusal:
                    raise RuntimeError(f"模型拒绝了该请求 (refusal): "
                                       f"{self._sanitize(str(refusal))}")
                parsed = getattr(message, "parsed", None)
                if parsed is not None:
                    return parsed
                # 服务端 strict 校验仍失败（极少数：长度截断等）→ 带反馈重试
                last_err = RuntimeError(
                    f"响应未能解析为 ImageAnalysis（原始内容前 200 字: "
                    f"{(message.content or '')[:200]}）")
                logger.warning("OpenAI parse attempt %d failed: %s", attempt + 1, last_err)
                messages = base_messages + [
                    {"role": "assistant", "content": message.content or ""},
                    {"role": "user", "content":
                        f"上一次输出无法通过 schema 校验（{last_err}）。"
                        "请严格按照字段要求重新输出完整 JSON。"},
                ]
            raise last_err
        except RuntimeError:
            raise
        except Exception as e:
            logger.error("OpenAI Vision API error: %s", self._sanitize(str(e)))
            raise RuntimeError(
                f"OpenAI Vision API 调用失败: {self._sanitize(str(e))}") from e

    def _parse_with_openai_legacy(self, client, img_b64: str) -> ImageAnalysis:
        """旧 SDK 回退路径：json_object + 本地解析（S2 之前的实现）。"""
        try:
            response = client.chat.completions.create(
                model=self.openai_model,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": self._prompt_with_hints()},
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
            logger.error("OpenAI Vision API error: %s", self._sanitize(str(e)))
            raise RuntimeError(
                f"OpenAI Vision API 调用失败: {self._sanitize(str(e))}") from e

    def _parse_with_anthropic(self, img_b64: str) -> ImageAnalysis:
        """Call Anthropic Claude vision with structured outputs.

        `messages.parse` enforces the ImageAnalysis JSON schema server-side
        and validates client-side, so no manual JSON extraction is needed.
        429/5xx are retried by the SDK itself (max_retries).
        """
        import anthropic

        client = anthropic.Anthropic(
            api_key=self.anthropic_key, base_url=self.anthropic_base_url,
            timeout=60.0, max_retries=3
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
                        {"type": "text", "text": self._prompt_with_hints()},
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
            logger.error("Anthropic Vision API error: %s",
                         self._sanitize(str(e)))
            raise RuntimeError(
                f"Anthropic Vision API 调用失败: {self._sanitize(str(e))}") from e

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
