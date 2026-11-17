"""Check manually specified construction paths or generate the synthetic demo."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.models.working_path import WorkingPath, armhole_path_demo, compile_working_path
from app.utils.backup import loads_strict
from app.utils.working_path_export import export_working_path_markdown, export_working_path_pdf
from app.utils.working_recipe_export import export_working_recipe_pdf

MAX_PLAN_BYTES = 2 * 1024 * 1024


def read_path(data: bytes) -> WorkingPath:
    if len(data) > MAX_PLAN_BYTES:
        raise ValueError("工序文件超过 2 MiB 上限")
    try:
        raw = loads_strict(data.decode("utf-8-sig"))
    except RecursionError as exc:
        raise ValueError("工序 JSON 嵌套过深") from exc
    return WorkingPath.model_validate(raw)


def write_path(plan: WorkingPath, directory: Path, *, pdf: bool = False) -> list[Path]:
    result = compile_working_path(plan)
    outputs = {
        "path-plan.json": plan.model_dump_json(indent=2).encode(),
        "path-result.json": (json.dumps(result.to_dict(), ensure_ascii=False, indent=2) + "\n").encode(),
        "path-explanation.md": export_working_path_markdown(plan).encode(),
    }
    if pdf:
        outputs["path-explanation.pdf"] = (
            export_working_recipe_pdf(plan)
            if plan.input_origin in ("manual_instructions", "parametric_design")
            else export_working_path_pdf(plan))
    paths = [directory / name for name in outputs]
    if any(path.exists() for path in paths):
        raise ValueError("目标文件已存在，请使用新目录；不会覆盖现有工序记录")
    directory.mkdir(parents=True, exist_ok=True)
    for path, data in zip(paths, outputs.values(), strict=True):
        with path.open("xb") as stream:
            stream.write(data)
    return paths


def write_demo(directory: Path, *, pdf: bool = False) -> list[Path]:
    return write_path(armhole_path_demo(), directory, pdf=pdf)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, help="人工工序 working-path-v1/v2 JSON；不指定则运行数字演示")
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--pdf", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.plan is None:
            paths = write_demo(args.out_dir, pdf=args.pdf)
        else:
            with args.plan.open("rb") as source:
                plan = read_path(source.read(MAX_PLAN_BYTES + 1))
            paths = write_path(plan, args.out_dir, pdf=args.pdf)
    except (ValueError, OSError, ImportError) as exc:
        parser.exit(2, f"工序演示未导出：{exc}\n")
    for path in paths:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
