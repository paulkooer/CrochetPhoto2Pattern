"""JSON Schema 文档漂移测试：docs/schemas/*.schema.json 必须与模型同步。

外部工具（评测、试钩记录、第三方渲染器）以这些 schema 为对接面；
改契约字段而忘记重新生成文档时，此测试报警。
"""
import json
from pathlib import Path

from app.utils.schema_docs import build_schema_docs

_REPO = Path(__file__).resolve().parent.parent
_DOCS = _REPO / "docs" / "schemas"


def test_schema_docs_exist_and_in_sync():
    schemas = build_schema_docs()
    assert set(schemas) == {
        "pattern_result", "structure_geometry", "image_analysis", "crochet_part"}
    for name, schema in schemas.items():
        path = _DOCS / f"{name}.schema.json"
        assert path.is_file(), f"{path} 缺失——运行 write_schema_docs 重新生成"
        committed = json.loads(path.read_text(encoding="utf-8"))
        assert committed == schema, (
            f"{path} 与模型不同步——请重新运行 "
            "app/utils/schema_docs.py 的 write_schema_docs(docs/schemas)")


def test_schema_docs_are_stable_serializations():
    # sort_keys + 尾随换行：保证重复生成零 diff（CI/本地可复现）
    for name, schema in build_schema_docs().items():
        text = json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        assert (_DOCS / f"{name}.schema.json").read_text(encoding="utf-8") == text


def test_optional_dimension_bounds_use_standard_json_schema_keywords():
    schemas = build_schema_docs()
    structure = schemas["structure_geometry"]["$defs"]["PartGeometry"]["properties"]
    pattern = schemas["crochet_part"]["properties"]
    for properties, fields, maximum in (
        (structure, ("diameter_cm", "height_cm", "length_cm"), 200.0),
        (pattern, ("diameter_cm", "height_cm"), 200.0),
    ):
        for field in fields:
            number = next(branch for branch in properties[field]["anyOf"] if branch["type"] == "number")
            assert number["exclusiveMinimum"] == 0
            assert "gt" not in number and "le" not in number
            if maximum is not None:
                assert number["maximum"] == maximum
