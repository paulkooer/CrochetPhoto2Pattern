from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

# 规范部件名（vision prompt、手动输入、结构设计三方共用的单一来源）。
# 不用 Literal 硬约束 parts 字段：LLM 输出变体（如"双手"）时宁可走
# StructureDesigner 的默认小球降级，也不要让整次解析因校验失败而报错。
PART_NAMES = ("头部", "身体", "手臂", "腿部", "尾巴", "耳朵", "帽子", "裙子")


class CrochetStitch(BaseModel):
    row: int = Field(gt=0)
    stitches: int = Field(ge=1)
    increase: int = Field(default=0, ge=0)
    decrease: int = Field(default=0, ge=0)
    notes: Optional[str] = None
    # 本圈使用的毛线色（照片配色设计；无图/单色部件为 None）
    color: Optional[str] = None
    # V2：装饰性宽跳变显式白名单（如波浪裙摆"每针放2针"——工艺正确但
    # 违反平盘 |Δ|≤6 物理极限）。生成器对唯一合法场景显式置位；
    # validator 对未置位的宽跳变报错（与代数自洽解耦的物理检查）。
    allow_wide_jump: bool = False

class CrochetPart(BaseModel):
    name: str
    type: str  # sphere, cylinder, cone, etc.
    # 一个逻辑图解可要求制作多个相同实物（如左右手臂/腿/耳朵）。
    # 旧备份没有该字段时按 1 兼容；派生针数、材料和时长必须乘此数量。
    quantity: int = Field(default=1, ge=1, le=20)
    diameter_cm: Optional[float] = None
    height_cm: Optional[float] = None
    # 圈数不再作为存储字段：一律由 len(rounds) 派生，避免两者失同步
    # （历史 JSON 中多余的 "rows" 键会被 pydantic 静默忽略）。
    rounds: List[CrochetStitch]
    color: str
    notes: Optional[str] = None
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
    main_features: List[str]
    pose: str
    difficulty: Literal["easy", "medium", "hard"]
    parts: List[str] = Field(
        description="Identified body parts. Expected values: " + "、".join(PART_NAMES)
    )
    recommended_colors: Optional[List[str]] = Field(
        default=None, description="Dominant colors extracted from image, mapped to yarn names"
    )
    # ── 语义配色（LLM 路径可选；本地/手动路径为 None）────────────────────
    # 值为常见毛线色名（如"深棕色"/"蓝色"）；未知色名原样保留供用户修正。
    hair_color: Optional[str] = Field(
        default=None, description="Hair color as a yarn color name, null if not visible")
    top_color: Optional[str] = Field(
        default=None, description="Upper garment main color as a yarn color name")
    bottom_color: Optional[str] = Field(
        default=None, description="Lower garment (pants/skirt) main color as a yarn color name")
    clothing_type: Optional[str] = Field(
        default=None, description="裤子 | 裙子 | 连衣裙 | 其他 | null")

    @field_validator("parts")
    @classmethod
    def _dedupe_parts(cls, value: List[str]) -> List[str]:
        """LLM 偶尔输出重复部件名；重名会生成冲突的 widget key 使 UI 崩溃，
        去重（保序）比报错更符合"尽力生成图解"的产品语义。"""
        return list(dict.fromkeys(value))
