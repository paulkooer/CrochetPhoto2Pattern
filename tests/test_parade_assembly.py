"""装配块（app/utils/parade_assembly.py）与 --assemble 导出的单测。

布局只依赖部件自身的圈数/针数：头在身体上方、耳在头顶、手臂在两侧、
腿在下方，左右镜像（第一份在 -x）。装配块本身是 `DOT: separate=0`
加每个实体一行 `TRANSFORM_OBJECT`。
"""
import pytest
from PIL import Image

from app.models.orchestrator import PipelineOrchestrator
from app.utils.parade_assembly import assembly_lines, layout_positions, part_extent, part_role
from app.utils.parade_export import export_parade_report, lint_parade_dsl


def _sphere(peak: int, rows: int) -> dict:
    """球体部件：长到 peak 再收回来（圈数/针数都是合法图解形态）。"""
    up = [6 * (i + 1) for i in range(peak // 6)]
    down = list(reversed(up))[1:]
    counts = up + [peak] * max(1, rows - len(up) - len(down)) + down
    rounds, prev = [], counts[0]
    for i, n in enumerate(counts):
        rd = {"row": i + 1, "stitches": n}
        if i:
            diff = n - prev
            if diff > 0:
                rd["increase"] = diff
            elif diff < 0:
                rd["decrease"] = -diff
        rounds.append(rd)
        prev = n
    return {"magic_ring": True, "rounds": rounds}


def _tube(stitches: int, rows: int) -> dict:
    counts = [6, 6] + [stitches] * rows
    rounds, prev = [], counts[0]
    for i, n in enumerate(counts):
        rd = {"row": i + 1, "stitches": n}
        if i:
            diff = n - prev
            if diff > 0:
                rd["increase"] = diff
            elif diff < 0:
                rd["decrease"] = -diff
        rounds.append(rd)
        prev = n
    return {"magic_ring": True, "rounds": rounds}


def _parts() -> list[dict]:
    return [
        {"name": "头部", "quantity": 1, **_sphere(36, 18)},
        {"name": "身体", "quantity": 1, **_sphere(42, 17)},
        {"name": "手臂", "quantity": 2, **_tube(12, 10)},
        {"name": "腿部", "quantity": 2, **_tube(12, 11)},
        {"name": "耳朵", "quantity": 2, **_tube(12, 15)},
    ]


@pytest.mark.parametrize("name,role", [
    ("头部", "head"), ("身体", "body"), ("手臂", "arm"),
    ("腿部", "leg"), ("耳朵", "ear"), ("尾巴", "tail"),
    ("帽子", "hat"), ("裙子", "skirt"),
    ("head", "head"), ("Ears", "ear"), ("Hat", "hat"), ("Skirt", "skirt"),
    ("unknown-thing", "other"),
])
def test_part_role_by_name(name, role):
    assert part_role(name) == role


def test_layout_puts_hat_on_head_and_skirt_on_body():
    parts = [
        {"name": "头部", "quantity": 1, **_sphere(36, 18)},
        {"name": "身体", "quantity": 1, **_sphere(42, 17)},
        {"name": "帽子", "quantity": 1, **_sphere(18, 8)},
        {"name": "裙子", "quantity": 1, **_tube(30, 6)},
    ]
    head, body, hat, skirt = layout_positions(parts)
    assert hat[1] > head[1]                 # 帽子戴在头顶之上
    assert body[1] == pytest.approx(0.0)
    assert skirt[1] < body[1]               # 裙子围在身体下段
    assert hat[0] == pytest.approx(0.0) and skirt[0] == pytest.approx(0.0)


def test_part_extent_uses_circumference_and_rows():
    radius, height = part_extent([{"stitches": 36}, {"stitches": 36}])
    assert radius == pytest.approx(36 / (2 * 3.14159265), rel=1e-6)
    assert height == pytest.approx(1.4)
    assert part_extent([]) == (0.0, 0.0)


def test_layout_stacks_head_ears_body_and_limbs():
    positions = layout_positions(_parts())
    assert len(positions) == 8          # 1 头 + 1 身 + 2 臂 + 2 腿 + 2 耳
    head, body, arm_l, arm_r, leg_l, leg_r, ear_l, ear_r = positions
    body_y = body[1]
    assert head[1] > body_y                                   # 头在身体上方
    assert ear_l[1] > head[1] and ear_r[1] > head[1]          # 耳在头顶
    assert leg_l[1] < body_y and leg_r[1] < body_y            # 腿在下方
    assert arm_l[0] < 0 < arm_r[0]                            # 手臂左右镜像
    assert leg_l[0] < 0 < leg_r[0]
    assert ear_l[0] < 0 < ear_r[0]
    assert arm_l[0] == pytest.approx(-arm_r[0])
    assert arm_l[1] == pytest.approx(arm_r[1])
    assert arm_l[1] > leg_l[1]                                # 手在腿上方
    assert head[0] == pytest.approx(0.0) and body[0] == pytest.approx(0.0)


def test_layout_is_deterministic_and_independent_of_order():
    first = layout_positions(_parts())
    assert first == layout_positions(_parts())


def test_layout_without_body_falls_back_to_tallest_part():
    # 只有头和耳朵：不得抛异常，仍然给出可用位置
    positions = layout_positions([
        {"name": "头部", "quantity": 1, **_sphere(36, 18)},
        {"name": "耳朵", "quantity": 2, **_tube(12, 15)},
    ])
    assert len(positions) == 3
    assert positions[1][1] > positions[0][1]


def test_assembly_lines_emit_separate_and_one_transform_per_object():
    lines = assembly_lines(_parts())
    assert lines
    body = [ln for ln in lines if not ln.startswith("#")]
    assert body[0] == "DOT: separate=0"
    transforms = [ln for ln in body if ln.startswith("TRANSFORM_OBJECT:")]
    assert len(transforms) == 8
    for index, line in enumerate(transforms):
        fields = line.split(":", 1)[1].split(",")
        assert len(fields) == 7
        assert int(fields[0]) == index
        [float(value) for value in fields[1:]]
    assert lint_parade_dsl("\n".join(lines)) == []


def test_assembly_lines_empty_for_no_parts():
    assert assembly_lines([]) == []


def test_lint_accepts_assembly_block_and_flags_bad_transform():
    assert lint_parade_dsl("DOT: separate=0\nTRANSFORM_OBJECT: 0,1,2,3,0,0,0\n") == []
    issues = lint_parade_dsl("TRANSFORM_OBJECT: 0,1,2,0,0,0\n")
    assert any("7 个数值" in issue for issue in issues)
    issues = lint_parade_dsl("TRANSFORM_OBJECT: 0,1,2,3,0,x,0\n")
    assert any("非数值" in issue for issue in issues)


def test_export_without_assemble_has_no_transform_block():
    report = export_parade_report({"params": {"parts": _parts()}})
    assert "TRANSFORM_OBJECT" not in report.text
    assert "DOT: " not in report.text


def test_export_with_assemble_appends_block_and_stays_lint_clean():
    report = export_parade_report({"params": {"parts": _parts()}}, assemble=True)
    assert report.complete
    assert lint_parade_dsl(report.text) == []
    assert "DOT: separate=0" in report.text
    # 8 个实体 → 8 行 TRANSFORM_OBJECT，且在图纸之后
    assert report.text.count("TRANSFORM_OBJECT:") == 8
    assert report.text.index("TRANSFORM_OBJECT:") > report.text.index("ring")


def test_assemble_counts_every_exported_object():
    parts = [
        {"name": "头部", "quantity": 1, **_sphere(36, 12)},
        {"name": "怪件", "quantity": 1, "magic_ring": True, "rounds": [
            {"stitches": 6}, {"stitches": 10, "increase": 4},
            {"stitches": 10}]},
        {"name": "身体", "quantity": 1, **_sphere(42, 15)},
    ]
    report = export_parade_report({"params": {"parts": parts}}, assemble=True)
    assert lint_parade_dsl(report.text) == []
    # 被截断的部件在 CP 里仍是一个独立实体，也要拿到位置
    assert report.text.count("TRANSFORM_OBJECT:") == 3


def test_assemble_matches_full_pipeline_export():
    result = PipelineOrchestrator().run_full_pipeline(
        Image.new("RGB", (40, 80)), local_vision=True)
    report = export_parade_report(result, assemble=True)
    assert lint_parade_dsl(report.text) == []
    assert "DOT: separate=0" in report.text
    physical = sum(int(p.get("quantity", 1)) for p in result["params"]["parts"])
    assert report.text.count("TRANSFORM_OBJECT:") == physical
