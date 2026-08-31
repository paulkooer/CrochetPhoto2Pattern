"""第十四轮（U1-U8）回归：PDF 转义 / 分享链接 / 符号条 / CLI / 色号。"""
import json
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from app.models.crochet_params import CrochetParamsGenerator
from app.models.ring_chart import _round_operation_sequence, render_symbol_strip
from app.models.structure_designer import StructureDesigner
from app.schemas import ImageAnalysis

_APP = str(Path(__file__).resolve().parents[1] / "app" / "main.py")


def _params():
    a = ImageAnalysis(body_type="标准", head_diameter_cm=9.0, height_cm=18.0,
                      main_features=[], pose="站立", difficulty="easy",
                      parts=["头部", "身体"])
    st = StructureDesigner.design_3d_structure(a)
    return CrochetParamsGenerator.generate_params(a, st)


# ── U1 PDF 转义 ───────────────────────────────────────────────────────────

def test_pdf_markup_notes_render_literally():
    """notes 含 <script>/<foo> 时 PDF 正常生成（转义后字面输出）。"""
    pytest.importorskip("reportlab")
    from app.utils.pdf_export import export_pdf
    p = _params()
    p["parts"][0].notes = "说明 <b>加粗</b> <script>alert(1)</script> <foo>"
    data = export_pdf(p, {"body_type": "标准", "head_diameter_cm": 9.0,
                          "height_cm": 18.0, "difficulty": "easy"})
    assert data[:5] == b"%PDF-"


# ── U6 品牌色号（只收录已验证条目）────────────────────────────────────────

def test_brand_codes_verified_only():
    from app.models.colors import brand_code
    assert brand_code("黑色") == "Catona 110 (Jet Black)"
    assert brand_code("白色") == "Catona 106 (Snow White)"
    assert brand_code("紫色") is None          # 未核实的色名绝不编造
    assert brand_code("不存在的色") is None


def test_materials_carry_brand_code_when_known():
    params = _params()
    for p in params["parts"]:
        for r in p.rounds:
            r.color = "黑色"
        p.color = "黑色"
    from app.models.crochet_params import _materials
    mats = _materials(params["parts"], {p.name for p in params["parts"]})
    assert any("Catona 110" in m["item"] for m in mats)


# ── U8 分享链接 ───────────────────────────────────────────────────────────

def _full_result():
    from tests.test_app_smoke import _mock_result
    return _mock_result("share-1")


def test_share_roundtrip():
    from app.utils.share import decode_result, encode_result
    token = encode_result(_full_result())
    assert token and len(token) < 6000
    data = decode_result(token)
    assert data["analysis"]["body_type"] == "标准"
    assert data["params"]["parts"][0]["name"] == "头部"
    assert decode_result("garbage!!") is None


def test_share_size_guard_returns_none():
    """超大图解 → encode 返回 None（调用方提示改用备份文件）。"""
    import uuid

    from app.utils.share import encode_result

    result = _full_result()
    part0 = result["params"]["parts"][0]
    # F35：全程保持 CrochetStitch 真类型（塞裸 dict 会在 pydantic 序列化
    # 时产生 UserWarning，污染 -W error 信号）；唯一 notes 防 zlib 压缩
    base = list(part0.rounds)
    grown = list(base)
    for r in base * 30:
        grown.append(r.model_copy(update={"notes": uuid.uuid4().hex}))
    part0.rounds = grown
    assert encode_result(result) is None


def test_share_link_loads_via_query_params(monkeypatch, tmp_path):
    """端到端：?p=<token> 打开应用 → 结果自动载入（rid 唯一 + 可另存）。"""
    import uuid

    from streamlit.testing.v1 import AppTest

    from app.ui.result_renderer import _rebuild_params
    from app.utils import history
    from app.utils.share import decode_result, encode_result

    monkeypatch.setenv("CROCHET_HISTORY_DB", str(tmp_path / "h.db"))
    token = encode_result(_full_result())
    at = AppTest.from_file(_APP, default_timeout=30)
    at.query_params["p"] = token
    at.run()
    assert not at.exception
    assert "result" in at.session_state
    # V3：rid 唯一化（不再固定 "shared"，防历史互相覆盖）
    rid = at.session_state["result"]["result_id"]
    assert rid and rid != "shared"
    assert any("分享链接" in str(i.value) for i in at.info)

    # U25：分享另存历史 → 两次载入另存为两条记录（V3 修复验证）
    for _ in range(2):
        loaded = decode_result(token)
        loaded["result_id"] = f"u25-{uuid.uuid4().hex[:8]}"
        loaded["params"] = _rebuild_params(dict(loaded["params"]))
        history.save_result(loaded)
    rids = {i["rid"] for i in history.list_results()}
    assert sum(1 for r in rids if r.startswith("u25-")) == 2


# ── U7 符号条 ─────────────────────────────────────────────────────────────

def test_symbol_strip_glyph_counts_match_rounds():
    svg = render_symbol_strip(_params()["parts"][0])
    head = _params()["parts"][0]
    n = len(head.rounds)
    assert svg.count("<path") + svg.count("<line") >= n   # 每圈至少一个记号
    assert "图例" in svg and "逐圈符号条" in svg


def test_symbol_strip_truncates_long_rounds():
    """单圈超过 max_marks 时以 +N 截断（宽度可控）。"""
    part = {"name": "头部", "type": "sphere", "rounds": [
        {"row": 1, "stitches": 60, "increase": 0, "decrease": 0}]}
    svg = render_symbol_strip(part, max_marks=18)
    assert "+42" in svg  # 60 - 18


def test_symbol_strip_compiles_evenly_distributed_consuming_operations():
    """30→36 必须在上一圈30针上工作：(4X,V)×6，而非36个操作。"""
    rounds = [
        {"stitches": 30, "increase": 0, "decrease": 0},
        {"stitches": 36, "increase": 6, "decrease": 0},
        {"stitches": 30, "increase": 0, "decrease": 6},
    ]
    increase = _round_operation_sequence(rounds, 1)
    decrease = _round_operation_sequence(rounds, 2)
    assert increase == ["X", "X", "X", "X", "V"] * 6
    assert len(increase) == 30 and increase.count("V") == 6
    assert decrease == ["X", "X", "X", "X", "A"] * 6
    assert len(decrease) == 30 and decrease.count("A") == 6


def test_symbol_strip_svg_exposes_exact_operation_kinds():
    part = {"name": "球", "rounds": [
        {"stitches": 6, "increase": 0, "decrease": 0},
        {"stitches": 12, "increase": 6, "decrease": 0},
    ]}
    svg = render_symbol_strip(part, max_marks=20)
    assert svg.count('data-kind="V"') == 6
    assert svg.count('data-kind="X"') == 6


# ── U3 CLI ────────────────────────────────────────────────────────────────

def test_cli_manual_mode_json_output(tmp_path, monkeypatch):
    from app import cli
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    out = tmp_path / "p.json"
    rc = cli.main(["--head", "11", "--height", "24", "--gauge", "fine",
                   "--sphere-mode", "egg", "--out", str(out), "--quiet"])
    assert rc == 0
    d = json.loads(out.read_text(encoding="utf-8"))
    assert d["analysis"]["head_diameter_cm"] == 11.0
    assert d["params"]["parts"][0]["name"] == "头部"


def test_cli_mock_mode_is_reachable_without_image(tmp_path, monkeypatch):
    from app import cli
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    out = tmp_path / "mock.json"
    rc = cli.main(["--mock", "--height", "24", "--out", str(out), "--quiet"])
    assert rc == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["vision_meta"]["source"] == "mock"
    assert "与照片无关" in payload["vision_meta"]["note"]
    assert payload["analysis"]["height_cm"] == 24.0
    assert payload["sizing"]["source"] == "cli_target"
    assert payload["geometry"]["used_for_generation"] is False


def test_cli_local_vision_with_image(tmp_path):
    from app import cli
    img_path = tmp_path / "doll.png"
    img = Image.new("RGB", (200, 400), (245, 245, 245))
    d = ImageDraw.Draw(img)
    d.ellipse([75, 24, 125, 74], fill=(230, 180, 150))
    d.rounded_rectangle([80, 85, 120, 195], radius=10, fill=(0, 120, 215))
    d.rounded_rectangle([78, 195, 122, 372], radius=10, fill=(0, 120, 215))
    img.save(img_path)
    out = tmp_path / "p.json"
    rc = cli.main(["--image", str(img_path), "--local", "--height", "30", "--gauge", "dk",
                   "--out", str(out), "--quiet"])
    assert rc == 0
    d = json.loads(out.read_text(encoding="utf-8"))
    assert d["vision_meta"]["source"] in ("default", "opencv-face")
    assert d["params"]["total_stitches"] > 0
    assert d["analysis"]["height_cm"] == 30.0
    assert d["sizing"]["source"] == "cli_target"


def test_cli_rejects_unknown_part():
    import pytest

    from app import cli
    with pytest.raises(SystemExit, match="未知部件"):
        cli.main(["--parts", "翅膀"])


def test_cli_gate_blocks_when_self_check_fails(monkeypatch, tmp_path):
    """CLI 同样受自检门禁约束（与 GUI 的 PatternGenerationError 对应）。"""
    import app.models.crochet_params as cp
    from app import cli

    orig = cp._cylinder_rounds

    def bad(max_stitches=24, body_rounds=15):
        rs = orig(max_stitches=max_stitches, body_rounds=body_rounds)
        rs[4]["stitches"] += 30      # 破坏代数（generate_params 内部经
        return rs                    # 模块全局查找，须补丁模块属性）

    monkeypatch.setattr(cp, "_cylinder_rounds", bad)
    out = tmp_path / "p.json"
    rc = cli.main(["--head", "9", "--height", "18", "--gauge", "classic",
                   "--out", str(out), "--quiet"])
    assert rc == 2
    assert not out.exists()


# ── U27 批量目录模式 ──────────────────────────────────────────────────────

def test_cli_batch_directory(tmp_path):
    """U27：目录批量——逐图生成 JSON+MD，非图片跳过，失败不中断。"""
    from app import cli
    in_dir = tmp_path / "in"
    in_dir.mkdir()
    for i, color in enumerate([(0, 120, 215), (220, 50, 50)]):
        img = Image.new("RGB", (100, 160), (245, 245, 245))
        d = ImageDraw.Draw(img)
        d.ellipse([30, 12, 70, 52], fill=(230, 180, 150))
        d.rounded_rectangle([35, 55, 65, 150], radius=8, fill=color)
        img.save(in_dir / f"doll{i}.png")
    (in_dir / "skip.txt").write_text("x")
    out_dir = tmp_path / "out"
    rc = cli.main(["--batch-dir", str(in_dir), "--out-dir", str(out_dir),
                   "--quiet"])
    assert rc == 0
    assert (out_dir / "doll0.json").exists()
    assert (out_dir / "doll1.md").exists()
    assert not (out_dir / "skip.json").exists()


def test_cli_batch_empty_dir(tmp_path):
    from app import cli
    empty = tmp_path / "empty"
    empty.mkdir()
    assert cli.main(["--batch-dir", str(empty), "--quiet"]) == 1


def test_cli_batch_stem_collision_disambiguated(tmp_path):
    """F27：doll.png 与 doll.jpg 并存 → 输出名带扩展消歧，不静默覆盖。"""
    from app import cli
    out_dir = tmp_path / "out"
    for ext, color in (("png", (0, 120, 215)), ("jpg", (220, 50, 50))):
        img = Image.new("RGB", (100, 160), (245, 245, 245))
        d = ImageDraw.Draw(img)
        d.ellipse([30, 12, 70, 52], fill=(230, 180, 150))
        d.rounded_rectangle([35, 55, 65, 150], radius=8, fill=color)
        img.save(tmp_path / f"doll.{ext}")
    rc = cli.main(["--batch-dir", str(tmp_path), "--out-dir", str(out_dir),
                   "--quiet"])
    assert rc == 0
    files = sorted(p.name for p in out_dir.iterdir())
    assert "doll_png.json" in files and "doll_jpg.json" in files
    assert len(files) == 4
