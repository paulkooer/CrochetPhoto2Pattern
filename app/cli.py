"""CLI 无头模式（U3）——同类工具的脚本化形态，批量/CI 评测的地基。

用法：
  crochet2pattern --image photo.jpg --gauge dk --out pattern.json
  crochet2pattern --head 9 --height 18 --parts 头部,身体 --out p.json
  crochet2pattern --image photo.jpg --local --format all --out-dir out/

AI 模式读取 OPENAI_API_KEY / ANTHROPIC_API_KEY 环境变量（含中转站
OPENAI_BASE_URL / ANTHROPIC_BASE_URL）；--local 强制本地视觉（免费），
--mock 演示数据。默认：无 Key 自动走本地视觉。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.models.crochet_params import CrochetParamsGenerator
from app.models.gauge import ShapingStyle, gauge_from_ui
from app.models.geometry import mock_geometry, no_photo_geometry
from app.models.orchestrator import PipelineOrchestrator
from app.models.sizing import scale_analysis_to_target_height, sizing_meta_for_analysis
from app.models.structure_designer import StructureDesigner
from app.schemas import PART_NAMES, ImageAnalysis
from app.utils.exporters import export_markdown
from app.utils.images import load_image_file


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="crochet2pattern",
        description="照片 → Amigurumi 钩织图解（无头模式）")
    src = parser.add_mutually_exclusive_group()
    src.add_argument("--image", help="照片路径（省略则用手动参数）")
    src.add_argument("--mock", action="store_true", help="演示数据（与照片无关）")
    src.add_argument("--batch-dir", help="批量模式：目录内所有 jpg/png 逐个生成")
    parser.add_argument("--local", action="store_true",
                        help="强制本地视觉估算（免费，默认无 Key 时自动启用）")
    parser.add_argument("--head", type=float, default=9.0, help="头部直径 cm（手动模式）")
    parser.add_argument("--height", type=float, default=18.0,
                        help="整体/照片目标成品高度 cm（默认 18）")
    parser.add_argument("--parts", default="头部,身体,手臂,腿部",
                        help=f"逗号分隔部件（可选：{'、'.join(PART_NAMES)}）")
    parser.add_argument("--gauge", default="classic",
                        choices=["classic", "dk", "fine", "custom"])
    parser.add_argument("--stitches", type=float, help="custom：10cm 针数")
    parser.add_argument("--rows", type=float, help="custom：10cm 行数")
    parser.add_argument("--sphere-mode", default="ladder",
                        choices=["ladder", "ideal", "egg"])
    parser.add_argument("--one-piece", action="store_true", help="头身一体钩")
    parser.add_argument("--skirt-style", default="ring", choices=["ring", "attached"])
    parser.add_argument("--ruffle", action="store_true", help="波浪裙摆")
    parser.add_argument("--out-dir", help="批量模式输出目录（默认与图片同目录）")
    parser.add_argument("--out", help="输出 JSON 路径（默认打印到 stdout）")
    parser.add_argument("--md", help="额外输出 Markdown 图解路径")
    parser.add_argument("--pdf", help="额外输出 PDF 路径（需 reportlab）")
    parser.add_argument("--quiet", action="store_true", help="不打印摘要")
    return parser


def run(args: argparse.Namespace) -> dict:
    """执行管线并返回 result dict（CLI 与测试共用）。"""
    parts = [p.strip() for p in args.parts.split(",") if p.strip()]
    bad = [p for p in parts if p not in PART_NAMES]
    if bad:
        raise SystemExit(f"未知部件: {'、'.join(bad)}（可选：{'、'.join(PART_NAMES)}）")

    gauge = gauge_from_ui(args.gauge, args.stitches, args.rows)
    style = ShapingStyle(sphere_mode=args.sphere_mode, one_piece=args.one_piece,
                         skirt_style=args.skirt_style, ruffle_hem=args.ruffle)
    orch = PipelineOrchestrator()  # Key 从环境变量读取

    if args.mock:
        analysis = orch.parser._mock_analysis()
        analysis, sizing = scale_analysis_to_target_height(
            analysis, args.height, source="cli_target")
        structure = StructureDesigner.design_3d_structure(analysis)
        params = CrochetParamsGenerator.generate_params(
            analysis, structure, gauge=gauge, style=style)
        result = {
            "analysis": analysis.model_dump(), "structure": structure,
            "params": params, "usage": {},
            "vision_meta": {"source": "mock", "note": "Mock 演示数据，与照片无关"},
            "gauge": {"stitches_per_10cm": gauge.stitches_per_10cm,
                      "rows_per_10cm": gauge.rows_per_10cm},
            "style": {"sphere_mode": style.sphere_mode, "one_piece": style.one_piece,
                      "skirt_style": style.skirt_style, "ruffle_hem": style.ruffle_hem},
            "color_bands": None, "spans": None, "spans_measured": [],
            "sizing": sizing,
            "geometry": mock_geometry().model_dump(),
        }
    elif args.image:
        image = load_image_file(args.image)
        if image is None:
            raise SystemExit(f"无法读取图片: {args.image}")
        use_local = args.local or not (
            orch.parser.openai_key or orch.parser.anthropic_key)
        result = orch.run_full_pipeline(image, local_vision=use_local,
                                        gauge=gauge, style=style,
                                        target_height_cm=args.height,
                                        target_height_source="cli_target")
    else:
        analysis = ImageAnalysis(
            body_type="标准", head_diameter_cm=args.head, height_cm=args.height,
            main_features=[], pose="站立", difficulty="easy", parts=parts)
        structure = StructureDesigner.design_3d_structure(analysis)
        params = CrochetParamsGenerator.generate_params(
            analysis, structure, gauge=gauge, style=style)
        result = {
            "analysis": analysis.model_dump(), "structure": structure,
            "params": params, "usage": {}, "vision_meta": {},
            "gauge": {"stitches_per_10cm": gauge.stitches_per_10cm,
                      "rows_per_10cm": gauge.rows_per_10cm},
            "style": {"sphere_mode": style.sphere_mode, "one_piece": style.one_piece,
                      "skirt_style": style.skirt_style, "ruffle_hem": style.ruffle_hem},
            "color_bands": None, "spans": None, "spans_measured": [],
            "sizing": sizing_meta_for_analysis(analysis, "manual_dimensions"),
            "geometry": no_photo_geometry().model_dump(),
        }

    from app.models.validator import validate_pattern
    v = validate_pattern(result["params"])
    if not v["ok"]:
        raise PatternGenerationErrorSafe(v["issues"])
    return result


class PatternGenerationErrorSafe(RuntimeError):
    pass


def run_batch(args) -> int:
    """U27：目录批量模式——每个图片独立生成 JSON+MD，失败不中断。

    U27 补全：ThreadPoolExecutor 并发（GrabCut/cv2 内部释放 GIL，能真
    并行）。每个图片用**独立 orchestrator**——parser 的 last_usage /
    last_local_meta 是实例状态，并发复用会串档（审查者预警的第一个坑）。
    """
    from concurrent.futures import ThreadPoolExecutor
    from pathlib import Path as _P

    in_dir = _P(args.batch_dir)
    out_dir = _P(args.out_dir) if args.out_dir else in_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    images = sorted(p for p in in_dir.iterdir()
                    if p.suffix.lower() in (".jpg", ".jpeg", ".png"))
    if not images:
        print(f"目录中没有图片: {in_dir}", file=sys.stderr)
        return 1

    def _one(img):
        stem = img.stem if len(stem_groups[img.stem]) == 1 \
            else f"{img.stem}_{img.suffix.lstrip('.')}"
        ns = argparse.Namespace(**{**vars(args), "image": str(img),
                                   "out": str(out_dir / f"{stem}.json"),
                                   "md": str(out_dir / f"{stem}.md"),
                                   "pdf": (str(out_dir / f"{stem}.pdf")
                                           if args.pdf else None),
                                   "batch_dir": None})
        try:
            rc = main(ns)
            return img.name, rc, None
        except Exception as e:
            return img.name, 1, e

    # F27：同名不同扩展（doll.png / doll.jpg）→ 输出名带扩展消歧，
    # 防并发写同一文件静默覆盖
    from collections import defaultdict
    stem_groups = defaultdict(list)
    for img in images:
        stem_groups[img.stem].append(img)
    ok = 0
    with ThreadPoolExecutor(max_workers=4) as pool:
        for name, rc, err in pool.map(_one, images):
            if rc == 0:
                ok += 1
                print(f"✅ {name}", file=sys.stderr)
            else:
                print(f"❌ {name}" + (f": {err}" if err else ""),
                      file=sys.stderr)
    print(f"批量完成 {ok}/{len(images)}", file=sys.stderr)
    return 0 if ok == len(images) else 1


def main(argv=None) -> int:
    # argv 可为参数列表或已构造的 Namespace（run_batch 内部复用）
    if isinstance(argv, argparse.Namespace):
        args = argv
    else:
        args = build_parser().parse_args(argv)
    if args.batch_dir:
        if args.pdf:
            print("--pdf 在批量模式下按每图 <stem>.pdf 导出", file=sys.stderr)
        return run_batch(args)
    try:
        result = run(args)
    except PatternGenerationErrorSafe as e:
        print(f"图解自检失败: {e.args[0]}", file=sys.stderr)
        return 2
    except Exception as e:
        from app.models.crochet_params import PatternGenerationError
        if isinstance(e, PatternGenerationError):
            print(f"图解自检失败: {e}", file=sys.stderr)
            return 2
        raise
    payload = result  # 完整 result（含 vision_meta/gauge/style 等，与备份同构）
    blob = json.dumps(payload, ensure_ascii=False, default=lambda o: (
        o.model_dump() if hasattr(o, "model_dump") else str(o)), indent=2)
    if args.out:
        Path(args.out).write_text(blob, encoding="utf-8")
    else:
        print(blob)
    if args.md:
        analysis = result["analysis"]
        Path(args.md).write_text(
            export_markdown(result["params"], analysis), encoding="utf-8")
    if args.pdf:
        from app.utils.pdf_export import export_pdf
        Path(args.pdf).write_bytes(export_pdf(result["params"],
                                              result["analysis"]))
    if not args.quiet:
        analysis = result["analysis"]
        parts = result["params"]["parts"]
        def _quantity(part):
            return max(1, int(part.get("quantity", 1) if isinstance(part, dict)
                              else getattr(part, "quantity", 1)))

        n_pieces = sum(_quantity(p) for p in parts)
        n_rounds = sum(
            (len(p["rounds"]) if isinstance(p, dict) else p.rows) * _quantity(p)
            for p in parts)
        print(f"✅ {analysis.get('body_type', '?')} · "
              f"头 {analysis.get('head_diameter_cm')}cm · "
              f"{n_pieces} 个实体部件 · {n_rounds} 实际圈次", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
