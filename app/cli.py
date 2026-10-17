"""CLI 无头模式（U3）——同类工具的脚本化形态，批量/CI 评测的地基。

用法：
  crochet2pattern --image photo.jpg --gauge dk --out pattern.json
  crochet2pattern --head 9 --height 18 --parts 头部,身体 --out p.json
  crochet2pattern --image photo.jpg --local --format all --out-dir out/

照片默认使用本地视觉；--local 保留为兼容选项，--mock 使用演示数据。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app import software_version
from app.models.crochet_params import CrochetParamsGenerator
from app.models.gauge import ShapingStyle, gauge_from_ui
from app.models.geometry import mock_geometry, no_photo_geometry
from app.models.orchestrator import PipelineOrchestrator
from app.models.sizing import scale_analysis_to_target_height, sizing_meta_for_analysis
from app.models.structure_designer import StructureDesigner
from app.schemas import PART_NAMES, ImageAnalysis, PatternResult
from app.utils.exporters import export_markdown
from app.utils.images import load_image_file
from app.utils.preview_export import PREVIEW_SUFFIXES


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="crochet2pattern",
        description="照片 → Amigurumi 钩织图解（无头模式）")
    src = parser.add_mutually_exclusive_group()
    src.add_argument("--image", help="照片路径（省略则用手动参数）")
    src.add_argument("--mock", action="store_true",
                     help="演示数据（CLI 无照片参与，配色为默认值）")
    src.add_argument("--batch-dir", help="批量模式：目录内所有 jpg/png 逐个生成")
    parser.add_argument("--local", action="store_true",
                        help="本地视觉估算（默认启用；保留此参数兼容旧命令）")
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
    parser.add_argument("--parade", help="额外输出 CrochetPARADE DSL 路径"
                        "（粘贴到 crochetparade.org 可得 3D 渲染与针目张力分析）")
    parser.add_argument("--assemble", action="store_true",
                        help="在 --parade 的 DSL 末尾追加装配块：DOT: separate=0 "
                             "把独立部件收回原点，再按解剖布局给出 TRANSFORM_OBJECT "
                             "平移（旋转需在 CP 的 Object Transform 面板摆正）")
    parser.add_argument("--pdf", help="额外输出 PDF 路径（需 reportlab）")
    parser.add_argument("--preview", help="额外输出成品预览图路径（.svg 矢量 / .png 位图；"
                                          "与结果页同一渲染器：真实圈数旋转体 + 解剖布局）")
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
    orch = PipelineOrchestrator()

    if args.mock:
        analysis = orch.parser.parse_image_mock()
        analysis, sizing = scale_analysis_to_target_height(
            analysis, args.height, source="cli_target")
        structure = StructureDesigner.design_3d_structure(analysis)
        params = CrochetParamsGenerator.generate_params(
            analysis, structure, gauge=gauge, style=style)
        result = PatternResult(
            generator_version=software_version(),
            analysis=analysis.model_dump(), structure=structure,
            params=params,
            # CLI --mock 无照片参与：配色为生成器默认值（与照片路径的
            # "配色来自照片"标注不同，诚实区分）
            vision_meta={"source": "mock",
                         "note": "Mock 演示数据（CLI 无照片参与，配色为默认值）"},
            gauge={"stitches_per_10cm": gauge.stitches_per_10cm,
                   "rows_per_10cm": gauge.rows_per_10cm},
            style={"sphere_mode": style.sphere_mode, "one_piece": style.one_piece,
                   "skirt_style": style.skirt_style, "ruffle_hem": style.ruffle_hem},
            spans_measured=[],
            sizing=sizing,
            geometry=mock_geometry().model_dump(),
        ).to_result_dict()
    elif args.image:
        image = load_image_file(args.image)
        if image is None:
            raise SystemExit(f"无法读取图片: {args.image}")
        result = orch.run_full_pipeline(image,
                                        vision_mode="local",
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
        result = PatternResult(
            generator_version=software_version(),
            analysis=analysis.model_dump(), structure=structure,
            params=params, vision_meta={},
            gauge={"stitches_per_10cm": gauge.stitches_per_10cm,
                   "rows_per_10cm": gauge.rows_per_10cm},
            style={"sphere_mode": style.sphere_mode, "one_piece": style.one_piece,
                   "skirt_style": style.skirt_style, "ruffle_hem": style.ruffle_hem},
            spans_measured=[],
            sizing=sizing_meta_for_analysis(analysis, "manual_dimensions"),
            geometry=no_photo_geometry().model_dump(),
        ).to_result_dict()

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
    from unicodedata import normalize

    in_dir = _P(args.batch_dir)
    out_dir = _P(args.out_dir) if args.out_dir else in_dir
    try:
        images = sorted(p for p in in_dir.iterdir()
                        if p.is_file() and p.suffix.lower() in (".jpg", ".jpeg", ".png"))
    except OSError as e:
        print(f"无法读取批量目录 {in_dir}: {e}", file=sys.stderr)
        return 1
    if not images:
        print(f"目录中没有图片: {in_dir}", file=sys.stderr)
        return 1
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        print(f"无法创建输出目录 {out_dir}: {e}", file=sys.stderr)
        return 1

    # Allocate every name before starting workers. Reserve natural candidates
    # too: doll.png + doll.jpg + doll_png.png must not race on doll_png.json.
    # Normalize/casefold so allocations also work on macOS/Windows volumes.
    def name_key(name: str) -> str:
        return normalize("NFC", name).casefold()

    from collections import Counter

    stem_counts = Counter(name_key(img.stem) for img in images)
    candidates = {
        img: (img.stem if stem_counts[name_key(img.stem)] == 1
              else f"{img.stem}_{img.suffix.lstrip('.')}")
        for img in images
    }
    reserved = {name_key(name) for name in candidates.values()}
    allocated: set[str] = set()
    output_stems: dict[Path, str] = {}
    for img, candidate in candidates.items():
        stem = candidate
        suffix = 2
        while name_key(stem) in allocated or (stem != candidate and name_key(stem) in reserved):
            stem = f"{candidate}_{suffix}"
            suffix += 1
        output_stems[img] = stem
        allocated.add(name_key(stem))

    def _one(img):
        stem = output_stems[img]
        ns = argparse.Namespace(**{**vars(args), "image": str(img),
                                   "out": str(out_dir / f"{stem}.json"),
                                   "md": str(out_dir / f"{stem}.md"),
                                   "pdf": (str(out_dir / f"{stem}.pdf")
                                           if args.pdf else None),
                                   "parade": (str(out_dir / f"{stem}.parade.txt")
                                              if args.parade else None),
                                   "preview": (str(out_dir / f"{stem}.preview"
                                                   f"{Path(args.preview).suffix}")
                                               if getattr(args, "preview", None)
                                               else None),
                                   "batch_dir": None})
        try:
            rc = main(ns)
            return img.name, rc, None
        except (Exception, SystemExit) as e:
            return img.name, 1, e

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
    args = (argv if isinstance(argv, argparse.Namespace)
            else build_parser().parse_args(argv))
    preview = getattr(args, "preview", None)
    if preview and Path(preview).suffix.lower() not in PREVIEW_SUFFIXES:
        # 格式在生成前就判：不合法的后缀不该先跑完整条管线再失败。
        print(f"预览格式不支持: {preview}（用 .svg 或 .png）", file=sys.stderr)
        return 1
    if args.batch_dir:
        if args.pdf:
            print("--pdf 在批量模式下按每图 <stem>.pdf 导出", file=sys.stderr)
        if args.parade:
            print("--parade 在批量模式下按每图 <stem>.parade.txt 导出", file=sys.stderr)
        if preview:
            print("--preview 在批量模式下按每图 <stem>.preview<ext> 导出",
                  file=sys.stderr)
        if args.assemble and not args.parade:
            print("--assemble 需要 --parade，已忽略", file=sys.stderr)
        return run_batch(args)
    if args.assemble and not args.parade:
        print("--assemble 需要 --parade，已忽略", file=sys.stderr)
    from app.utils.output_files import output_paths, write_outputs

    try:
        paths = output_paths(args)
    except (OSError, ValueError) as exc:
        print(f"输出准备失败: {exc}", file=sys.stderr)
        return 1
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
    if result.get("vision_meta", {}).get("requires_subject_review") and not args.quiet:
        print("注意：本地结果的主体类型未确认，部件来自默认模板；请在界面确认头部、部件和数量后使用。",
              file=sys.stderr)
    payload = result  # 完整 result（含 vision_meta/gauge/style 等，与备份同构）
    blob = json.dumps(payload, ensure_ascii=False, default=lambda o: (
        o.model_dump() if hasattr(o, "model_dump") else str(o)), indent=2)
    try:
        exports = {"out": blob.encode("utf-8")}
        if args.md:
            exports["md"] = export_markdown(
                result["params"], result["analysis"], result=result).encode("utf-8")
        if args.parade:
            from app.utils.parade_export import export_parade_dsl
            exports["parade"] = export_parade_dsl(
                result, assemble=args.assemble).encode("utf-8")
        if args.pdf:
            from app.utils.pdf_export import export_pdf
            exports["pdf"] = export_pdf(result["params"], result["analysis"], result=result)
        if preview:
            from app.utils.preview_export import export_preview
            exports["preview"] = export_preview(result, paths["preview"])
        write_outputs({path: exports[kind] for kind, path in paths.items()})
    except Exception as exc:
        print(f"导出失败: {exc}", file=sys.stderr)
        return 1
    if not args.out:
        print(blob)
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
