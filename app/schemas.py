from pydantic import BaseModel, Field
from typing import List, Literal, Optional

class CrochetStitch(BaseModel):
    row: int = Field(gt=0)
    stitches: int = Field(ge=1)
    increase: int = Field(default=0, ge=0)
    decrease: int = Field(default=0, ge=0)
    notes: Optional[str] = None

class CrochetPart(BaseModel):
    name: str
    type: str  # sphere, cylinder, cone, etc.
    diameter_cm: Optional[float] = None
    height_cm: Optional[float] = None
    rows: int
    rounds: List[CrochetStitch]
    color: str
    notes: Optional[str] = None
    magic_ring: bool = False

class ImageAnalysis(BaseModel):
    body_type: str
    head_diameter_cm: float = Field(gt=0, le=50, description="Head diameter in cm")
    height_cm: float = Field(gt=0, le=200, description="Total height in cm")
    main_features: List[str]
    pose: str
    difficulty: Literal["easy", "medium", "hard"]
    parts: List[str]
    recommended_colors: Optional[List[str]] = Field(
        default=None, description="Dominant colors extracted from image, mapped to yarn names"
    )
