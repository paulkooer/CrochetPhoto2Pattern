"""核心契约的 JSON Schema 发布（对标 Knitout 的开放中间格式思路）。

PatternResult / StructureGeometry / ImageAnalysis / CrochetPart 是全系统
的数据契约，也是外部工具（评测、试钩记录、第三方渲染器）的对接面。
pydantic 自动生成的 schema 文档随仓库发布，drift 测试
（tests/test_schema_docs.py）保证文档与模型不漂移。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from app.models.geometry import StructureGeometry
from app.schemas import CrochetPart, ImageAnalysis, PatternResult

# pydantic 的 model_json_schema 定义在 ModelMetaclass 上（类方法而非实例
# 方法），mypy 需要显式的"类类型"注解
ModelType = type[BaseModel]

SCHEMA_MODELS: dict[str, ModelType] = {
    "pattern_result": PatternResult,
    "structure_geometry": StructureGeometry,
    "image_analysis": ImageAnalysis,
    "crochet_part": CrochetPart,
}


def build_schema_docs() -> dict[str, dict[str, Any]]:
    return {name: model.model_json_schema() for name, model in SCHEMA_MODELS.items()}


def write_schema_docs(directory: str | Path) -> list[Path]:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name, schema in build_schema_docs().items():
        path = directory / f"{name}.schema.json"
        path.write_text(
            json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8")
        written.append(path)
    return written
