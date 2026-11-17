"""CLI for explicit dressed-doll construction prototypes, without photo inference."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.models.dressed_doll import DollDesign, build_doll_plan, starter_design
from app.models.dressed_doll.planner import STARTER_LABELS
from app.models.gauge import Gauge
from app.utils.backup import loads_strict
from app.utils.dressed_doll_export import export_doll_graph, export_doll_markdown, export_doll_pdf

MAX_DESIGN_BYTES = 512 * 1024


def read_design(data: bytes) -> DollDesign:
    if len(data) > MAX_DESIGN_BYTES:
        raise ValueError("设计文件超过 512 KiB 上限")
    try:
        raw = loads_strict(data.decode("utf-8-sig"))
    except RecursionError as exc:
        raise ValueError("设计 JSON 嵌套过深") from exc
    return DollDesign.model_validate(raw)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--starter", choices=list(STARTER_LABELS))
    source.add_argument("--design", type=Path, help="Explicit dressed-doll-design-v1 JSON")
    parser.add_argument("--height", type=float, help="Starter target height, excluding hat; default 24cm")
    parser.add_argument("--stitches", type=float, help="Starter stitches per 10cm; default 22")
    parser.add_argument("--rows", type=float, help="Starter rows per 10cm; default 28")
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--pdf", action="store_true", help="Also create a PDF (requires reportlab)")
    return parser


def run(args: argparse.Namespace) -> dict[str, str | int]:
    if args.design is not None:
        if any(v is not None for v in (args.height, args.stitches, args.rows)):
            raise ValueError("使用 --design 时，请在设计 JSON 中明确修改尺寸与密度")
        with args.design.open("rb") as source:
            design = read_design(source.read(MAX_DESIGN_BYTES + 1))
    else:
        design = starter_design(args.starter, height_cm=24 if args.height is None else args.height,
                                gauge=Gauge(22 if args.stitches is None else args.stitches,
                                            28 if args.rows is None else args.rows))
    plan = build_doll_plan(design)
    artifacts: dict[str, bytes] = {
        "design.json": (design.model_dump_json(indent=2) + "\n").encode(),
        "plan.json": (plan.model_dump_json(indent=2) + "\n").encode(),
        "plan.md": export_doll_markdown(plan).encode(),
        "assembly.dot": export_doll_graph(plan).encode(),
    }
    if args.pdf:
        artifacts["plan.pdf"] = export_doll_pdf(plan)
    # Check every destination and optional export before any output mutation.
    root = args.out_dir
    conflicts = [name for name in artifacts if (root / name).exists()]
    if conflicts:
        raise ValueError("输出文件已存在，请另选目录：" + ", ".join(conflicts))
    root.mkdir(parents=True, exist_ok=True)
    for name, data in artifacts.items():
        with (root / name).open("xb") as output:
            output.write(data)
    return {"output": str(root), "status": plan.status, "components": len(plan.components),
            "physical_parts": sum(p.quantity for p in plan.components),
            "stitch_outputs_and_chains": plan.total_operations}


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        summary = run(args)
    except (ValueError, OSError, ImportError) as exc:
        parser.exit(2, f"无法生成结构原型：{exc}\n")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
