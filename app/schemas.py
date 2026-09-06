import json
from collections.abc import Mapping
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

Difficulty = Literal["easy", "medium", "hard"]

# CYC Project Levels 对齐（craftyarncouncil.com/standards/skill-levels，
# 2026-09 抓取核对）。官方四级定义（逐字）：Basic——"Projects using basic
# stitches. May include basic increases and decreases."；Easy——"Projects
# may include simple stitch patterns, color work, and/or shaping."；
# Intermediate——"Projects may include involved stitch patterns, color
# work, and/or shaping."；Complex——"Projects may include complex stitch
# patterns, color work, and or/shaping using a variety of techniques and
# stitches simultaneously."。本系统只生成短针玩偶（sc + 加减针 + 配色带）：
# easy=仅基础针法与加减（Basic）、medium=多部件+配色带（Easy）、hard=
# 复杂塑形/一体钩/结构装配（Intermediate）；Complex 要求多种技法同时
# 使用——生成器不产生，故无对应档位。
DIFFICULTY_LABELS_ZH: dict[str, str] = {
    "easy": "简单（CYC Basic）",
    "medium": "中等（CYC Easy）",
    "hard": "较难（CYC Intermediate）",
}
DIFFICULTY_LABELS_EN: dict[str, str] = {
    "easy": "Easy (CYC Basic)",
    "medium": "Medium (CYC Easy)",
    "hard": "Hard (CYC Intermediate)",
}


def difficulty_label(value: str, *, zh: bool = True) -> str:
    """difficulty 裸值 → CYC 对齐显示标签；未知值（旧数据）原样返回。"""
    labels = DIFFICULTY_LABELS_ZH if zh else DIFFICULTY_LABELS_EN
    return labels.get(value, value)


class PartKind(StrEnum):
    """部件的英文领域主键（i18n 迁移锚点，取值 = 结构 v2 的 part_id）。

    中文显示名此前同时充当 dict key、CLI 参数、prompt 枚举与
    PART_SPAN 索引，是 i18n 被搁置的根因；PartKind 提供稳定锚点，
    显示名（中/英）从标签表读取，新增部件只改枚举与标签。
    """

    HEAD = "head"
    BODY = "body"
    ARMS = "arms"
    LEGS = "legs"
    TAIL = "tail"
    EARS = "ears"
    HAT = "hat"
    SKIRT = "skirt"


# 显示标签：UI/导出 i18n 的迁移起点。中文规范名仍是现行 dict key /
# prompt 枚举口径（PART_NAMES 从此派生，保持完全兼容）。
PART_LABELS_ZH: dict[PartKind, str] = {
    PartKind.HEAD: "头部",
    PartKind.BODY: "身体",
    PartKind.ARMS: "手臂",
    PartKind.LEGS: "腿部",
    PartKind.TAIL: "尾巴",
    PartKind.EARS: "耳朵",
    PartKind.HAT: "帽子",
    PartKind.SKIRT: "裙子",
}
PART_LABELS_EN: dict[PartKind, str] = {
    PartKind.HEAD: "Head",
    PartKind.BODY: "Body",
    PartKind.ARMS: "Arms",
    PartKind.LEGS: "Legs",
    PartKind.TAIL: "Tail",
    PartKind.EARS: "Ears",
    PartKind.HAT: "Hat",
    PartKind.SKIRT: "Skirt",
}

# 规范部件名（vision prompt、手动输入、结构设计三方共用的单一来源）。
# 不用 Literal 硬约束 parts 字段：LLM 输出变体（如"双手"）时宁可走
# StructureDesigner 的默认小球降级，也不要让整次解析因校验失败而报错。
PART_NAMES = tuple(PART_LABELS_ZH[k] for k in PartKind)


class CrochetStitch(BaseModel):
    row: int = Field(gt=0)
    stitches: int = Field(ge=1)
    increase: int = Field(default=0, ge=0)
    decrease: int = Field(default=0, ge=0)
    notes: str | None = None
    # 本圈使用的毛线色（照片配色设计；无图/单色部件为 None）
    color: str | None = None
    # V2：装饰性宽跳变标志（如波浪裙摆"每针放2针"——工艺正确但超出
    # 生成器平滑节奏先验）。宽跳变本身只降级为 note；置位仅抑制该
    # note（生成器对唯一合法场景显式置位以保持 notes 干净）。
    allow_wide_jump: bool = False

class CrochetPart(BaseModel):
    name: str
    type: str  # sphere, cylinder, cone, etc.
    # 一个逻辑图解可要求制作多个相同实物（如左右手臂/腿/耳朵）。
    # 旧备份没有该字段时按 1 兼容；派生针数、材料和时长必须乘此数量。
    quantity: int = Field(default=1, ge=1, le=20)
    diameter_cm: float | None = None
    height_cm: float | None = None
    # 圈数不再作为存储字段：一律由 len(rounds) 派生，避免两者失同步
    # （历史 JSON 中多余的 "rows" 键会被 pydantic 静默忽略）。
    rounds: list[CrochetStitch]
    color: str
    notes: str | None = None
    magic_ring: bool = False

    @property
    def rows(self) -> int:
        """Convenience alias — always derived, never stored."""
        return len(self.rounds)

class ImageAnalysis(BaseModel):
    body_type: str
    # 值域是"硬安全上限"，比 prompt（头径 4–20 / 身高 10–60，软目标）宽松：
    # prompt 约束指导模型输出常规玩偶尺寸，schema 只拦截明显离谱的值。
    head_diameter_cm: float = Field(
        gt=0, le=50,
        description="Head diameter on a reference scale; pipeline applies target cm")
    height_cm: float = Field(
        gt=0, le=200,
        description="Reference height from photo parser or explicit target height")
    main_features: list[str]
    pose: str
    difficulty: Difficulty
    parts: list[str] = Field(
        description="Identified body parts. Expected values: " + "、".join(PART_NAMES)
    )
    recommended_colors: list[str] | None = Field(
        default=None, description="Dominant colors extracted from image, mapped to yarn names"
    )
    # ── 语义配色（LLM 路径可选；本地/手动路径为 None）────────────────────
    # 值为常见毛线色名（如"深棕色"/"蓝色"）；未知色名原样保留供用户修正。
    hair_color: str | None = Field(
        default=None, description="Hair color as a yarn color name, null if not visible")
    top_color: str | None = Field(
        default=None, description="Upper garment main color as a yarn color name")
    bottom_color: str | None = Field(
        default=None, description="Lower garment (pants/skirt) main color as a yarn color name")
    clothing_type: str | None = Field(
        default=None, description="裤子 | 裙子 | 连衣裙 | 其他 | null")

    @field_validator("parts")
    @classmethod
    def _dedupe_parts(cls, value: list[str]) -> list[str]:
        """LLM 偶尔输出重复部件名；重名会生成冲突的 widget key 使 UI 崩溃，
        去重（保序）比报错更符合"尽力生成图解"的产品语义。"""
        return list(dict.fromkeys(value))


# 参考画布：VisionOutput 只产出比例，换算到内部 ImageAnalysis 时用它作为
# 高度画布（与旧"固定 18.0 画布"的 prompt 口径数值等价）。
_REFERENCE_CANVAS_CM = 18.0


class VisionOutput(BaseModel):
    """Vision 模型结构化输出的独立契约（与内部 ImageAnalysis 刻意分离）。

    审核意见（fable5.1）落地：
    - 枚举字段用 Literal——结构化输出下由服务端约束解码，不会导致校验失败；
    - 不携带 recommended_colors——色板永远由本地量化产生（照片像素是唯一
      可信来源），模型无权填写，也不再给图片内注入留展示位；
    - 直接索取 head_to_height_ratio，替代"固定 18.0 画布 + 头径换算"的
      间接比例索取。
    """

    body_type: Literal["瘦", "标准", "胖"]
    # 注意：结构化输出的 strict 模式只约束"结构"（字段/类型），数值区间
    # 由客户端校验——越界会触发 OpenAI 路径的带反馈重试或 provider 回退
    head_to_height_ratio: float = Field(
        gt=0, lt=1,
        description="photo head diameter divided by full visible height")
    main_features: list[str]
    pose: Literal["站立", "坐姿", "其他"]
    difficulty: Difficulty
    parts: list[str] = Field(
        description="Identified body parts. Expected values: " + "、".join(PART_NAMES)
    )
    # 值为常见毛线色名；未知色名原样保留供用户修正（语义与内部字段一致）
    hair_color: str | None = Field(
        default=None, description="Hair color as a yarn color name, null if not visible")
    top_color: str | None = Field(
        default=None, description="Upper garment main color as a yarn color name")
    bottom_color: str | None = Field(
        default=None, description="Lower garment (pants/skirt) main color as a yarn color name")
    clothing_type: Literal["裤子", "裙子", "连衣裙", "其他"] | None = None

    @field_validator("parts")
    @classmethod
    def _dedupe_parts(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(value))

    @classmethod
    def from_payload(cls, data: dict) -> "VisionOutput":
        """容忍旧 prompt 形态（head_diameter_cm/height_cm）的无 schema 回退路径。

        只服务旧 SDK json_object / 手动 JSON 解析分支；结构化输出的服务端
        schema 保持纯净（不含任何旧字段）。
        """
        if ("head_to_height_ratio" not in data
                and isinstance(data.get("height_cm"), (int, float))
                and data["height_cm"] > 0
                and isinstance(data.get("head_diameter_cm"), (int, float))):
            data = {**data,
                    "head_to_height_ratio": data["head_diameter_cm"] / data["height_cm"]}
        return cls(**data)

    def to_analysis(self) -> ImageAnalysis:
        """比例 → 内部模型的参考画布数值；recommended_colors 留空
        （parse_image 用本地量化色板回填，模型无权写入）。"""
        return ImageAnalysis(
            body_type=self.body_type,
            head_diameter_cm=round(self.head_to_height_ratio * _REFERENCE_CANVAS_CM, 2),
            height_cm=_REFERENCE_CANVAS_CM,
            main_features=self.main_features,
            pose=self.pose,
            difficulty=self.difficulty,
            parts=self.parts,
            recommended_colors=None,
            hair_color=self.hair_color,
            top_color=self.top_color,
            bottom_color=self.bottom_color,
            clothing_type=self.clothing_type,
        )


# ── PatternResult：全系统核心契约（F24/F26/F27 根因的最终收口）────────────
# result 顶层键集此前在 orchestrator、CLI 两个分支、手动输入、结果页调尺寸、
# 备份导入共 6 处手写，靠 _BACKUP_KEYS + test_key_sets 维持一致。现在统一为
# pydantic 模型：share/history 的键集从本模块派生，备份文件携带 schema_version。
SCHEMA_VERSION = "1"

# 备份/分享/历史 blob 的顶层键集（= 会话内 result dict 的运行时键集）。
# result_id/title 是会话/存储层字段，不随备份导出；schema_version 由
# to_backup 注入。字段顺序即历史备份的键序，勿打乱（快照 diff 稳定性）。
RESULT_KEYS = ("analysis", "structure", "params", "style", "gauge",
               "color_bands", "spans", "spans_measured", "vision_meta",
               "preview", "usage", "sizing", "geometry")


class PatternResult(BaseModel):
    """完整图解结果的单一契约。

    生成（orchestrator/CLI/手动）、快速调尺寸、备份导入、分享 token、
    历史持久化全部经由本模型构造与序列化；任何新顶层键必须加在这里，
    test_key_sets 会把 share 键集与 orchestrator 产物钉死在本模型上。
    """

    analysis: dict[str, Any]
    structure: dict[str, Any]
    params: dict[str, Any]
    style: dict[str, Any] | None = None
    gauge: dict[str, Any] | None = None
    color_bands: list[Any] | None = None
    spans: dict[str, Any] | None = None
    spans_measured: list[str] = Field(default_factory=list)
    vision_meta: dict[str, Any] = Field(default_factory=dict)
    preview: str | None = None
    usage: dict[str, Any] = Field(default_factory=dict)
    sizing: dict[str, Any] | None = None
    geometry: dict[str, Any] | None = None
    # 会话/存储层字段（不在 RESULT_KEYS 中）
    result_id: str | None = None
    title: str | None = None
    schema_version: str = SCHEMA_VERSION

    @classmethod
    def from_result(cls, data: Mapping[str, Any]) -> "PatternResult":
        """容忍任意来源的 result dict：缺键走默认值，pydantic 对象自动
        dump，未知键忽略（向前兼容旧备份）。"""
        plain = json.loads(json.dumps(
            dict(data), ensure_ascii=False,
            default=lambda o: (o.model_dump()
                               if hasattr(o, "model_dump") else str(o))))
        return cls.model_validate(plain)

    def to_result_dict(self) -> dict[str, Any]:
        """会话内 result dict（render_results/历史 blob 的运行时形态）。

        result_id/title 未设置时不出键，保证 orchestrator 产物与既有
        键集断言完全一致。"""
        data = self.model_dump(exclude={"schema_version"})
        return {k: v for k, v in data.items()
                if k not in ("result_id", "title") or v is not None}

    def to_backup(self) -> dict[str, Any]:
        """备份/分享用的完整键集（RESULT_KEYS + schema_version）。"""
        data = {k: getattr(self, k) for k in RESULT_KEYS}
        data["schema_version"] = self.schema_version
        return data
