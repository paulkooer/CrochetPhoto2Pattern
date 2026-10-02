"""CrochetPARADE DSL 导出器（app/utils/parade_export.py）的单测。

语法映射依据官方手册与论坛 sphere 示例（ring / sc8inc / 8sc2inc /
8[sc,sc2inc]），这里把生成器的典型圈形态钉死在可译子集内。
"""
import pytest
from PIL import Image

from app.models.orchestrator import PipelineOrchestrator
from app.utils.parade_export import export_parade_dsl, lint_parade_dsl


def _result() -> dict:
    return PipelineOrchestrator().run_full_pipeline(
        Image.new("RGB", (40, 80)), local_vision=True)


def test_export_contains_ring_and_uniform_repeats():
    text = export_parade_dsl(_result())
    assert "ring" in text
    assert "sc6inc" in text          # 首圈 6 针入环
    assert "6[sc,sc2inc]" in text    # (1X,V)×6 → 官方示例同款写法
    assert "36sc" in text            # 不加不减圈
    assert lint_parade_dsl(text) == []


def test_export_translates_decreases():
    text = export_parade_dsl(_result())
    # 头部收口：36→30→24…；每个 sc2tog 消费 2 个源针，普通 sc 数
    # 必须比加针圈再少 1。
    assert "6[4sc,sc2tog]" in text
    assert "6[sc,sc2tog]" in text
    assert "6sc2tog" in text
    assert lint_parade_dsl(text) == []


def test_export_quantity_duplicates_with_start_anew():
    r = _result()
    arms = [p for p in r["params"]["parts"] if p["name"] == "手臂"]
    assert arms and arms[0].get("quantity", 1) == 2
    text = export_parade_dsl(r)
    # 每份实体前有 start_anew 分隔（两份手臂 + 腿部成对）
    assert text.count("start_anew") >= 4


def test_export_color_directive_uses_hex():
    r = _result()
    head = next(p for p in r["params"]["parts"] if p["name"] == "头部")
    head["color"] = "蓝色"  # 色表内名字 → 必须转成 hex（官方 COLOR: 接受 hex）
    text = export_parade_dsl(r)
    assert "COLOR: #" in text


def test_export_rejects_empty_result():
    with pytest.raises(ValueError):
        export_parade_dsl({"params": {}})


def test_export_warns_on_untranslatable_round():
    r = _result()
    head = next(p for p in r["params"]["parts"] if p["name"] == "头部")
    # 人造的不可整除加针（36→41，无法均分为组）→ 记 warning 而非瞎译
    head["rounds"][8]["increase"] = 5
    head["rounds"][8]["stitches"] = 41
    text = export_parade_dsl(r)
    assert "超出可译子集" in text
    assert lint_parade_dsl(text) == []


def test_untranslatable_round_stops_part_before_virtual_count_drift():
    """跳过结构变化后只能保留有效前缀，不得从虚拟前圈继续发射。"""
    result = {"params": {"parts": [{
        "name": "异形件", "magic_ring": True,
        "rounds": [
            {"row": 1, "stitches": 6},
            {"row": 2, "stitches": 10, "increase": 4},
            {"row": 3, "stitches": 10},
        ],
    }]}}
    text = export_parade_dsl(result)
    assert "该圈及后续圈已跳过" in text
    assert "\n10sc\n" not in text
    assert lint_parade_dsl(text) == []


def test_lint_flags_unknown_tokens():
    issues = lint_parade_dsl("ring\nsc6inc\nfrobnicate\n")
    assert any("frobnicate" in i for i in issues)


@pytest.mark.parametrize("rd", [
    {"stitches": 12}, {"stitches": 6.9},
    {"stitches": 6, "increase": -1, "decrease": -1},
])
def test_export_stops_on_invalid_plain_round(rd):
    text = export_parade_dsl({"params": {"parts": [{
        "magic_ring": True, "rounds": [{"stitches": 6}, rd, {"stitches": 6}],
    }]}})
    assert "该圈及后续圈已跳过" in text
    instructions = [line for line in text.splitlines() if line and not line.startswith("#")]
    assert instructions == ["ring", "sc6inc"]


def test_first_round_color_is_used_for_every_copy():
    text = export_parade_dsl({"params": {"parts": [{
        "magic_ring": True, "quantity": 2, "color": "#000000",
        "rounds": [{"stitches": 6, "color": "#ff0000"},
                   {"stitches": 6, "color": "#0000ff"}],
    }]}})
    assert text.count("COLOR: #ff0000\nring\nsc6inc") == 2
    assert "COLOR: #000000" not in text


def test_empty_trailing_part_does_not_create_dangling_start():
    text = export_parade_dsl({"params": {"parts": [
        {"magic_ring": True, "rounds": [{"stitches": 6}]}, {"rounds": []},
    ]}})
    assert not text.rstrip().endswith("start_anew")


@pytest.mark.parametrize("count", [0, -6, 6.9, True, float("inf")])
def test_invalid_first_round_is_not_exported(count):
    with pytest.raises(ValueError, match="未能导出"):
        export_parade_dsl({"params": {"parts": [{"rounds": [{"stitches": count}]}]}})
