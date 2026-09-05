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
