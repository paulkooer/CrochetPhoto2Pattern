"""Experimental size-to-method synthesis for attached ribbing, outside the photo path."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.models.attached_ribbing import RibbingMethod, RibbingTarget, design_attached_ribbing, propose_ribbing
from app.models.working_path import WorkingPath, compile_working_path
from app.utils.backup import loads_strict
from app.utils.working_path_export import export_working_path_markdown
from app.utils.working_recipe_export import export_working_recipe_pdf
from app.working_paths import MAX_PLAN_BYTES, read_path


def _read_json(path: Path):
    with path.open("rb") as stream:
        data = stream.read(MAX_PLAN_BYTES + 1)
    if len(data) > MAX_PLAN_BYTES:
        raise ValueError("设计输入超过2 MiB")
    try:
        return loads_strict(data.decode("utf-8-sig"))
    except RecursionError as exc:
        raise ValueError("设计输入嵌套过深") from exc


def write_design(target: RibbingTarget, directory: Path, *, base: WorkingPath | None = None,
                 method: RibbingMethod | None = None, pdf: bool = False) -> list[Path]:
    if (base is None) != (method is None):
        raise ValueError("基底工序与构造做法须一起提供")
    generated = None
    if base is not None and method is not None:
        proposal, generated = design_attached_ribbing(base, method, target)
    else:
        proposal = propose_ribbing(target)
    outputs = {"design-proposal.json": (
        json.dumps(proposal.to_dict(), ensure_ascii=False, indent=2) + "\n").encode()}
    if generated is not None:
        result = compile_working_path(generated)
        outputs.update({
            "path-plan.json": generated.model_dump_json(indent=2).encode(),
            "path-result.json": (json.dumps(result.to_dict(), ensure_ascii=False, indent=2) + "\n").encode(),
            "path-explanation.md": export_working_path_markdown(generated).encode(),
        })
        if pdf:
            outputs["path-explanation.pdf"] = export_working_recipe_pdf(generated)
    paths = [directory / name for name in outputs]
    if any(path.exists() for path in paths):
        raise ValueError("目标文件已存在，请使用新目录")
    directory.mkdir(parents=True, exist_ok=True)
    for path, data in zip(paths, outputs.values(), strict=True):
        with path.open("xb") as stream:
            stream.write(data)
    return paths


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--base-plan", type=Path)
    parser.add_argument("--method", type=Path)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--pdf", action="store_true")
    args = parser.parse_args(argv)
    if bool(args.base_plan) != bool(args.method):
        parser.error("--base-plan 与 --method 须一起提供")
    try:
        target = RibbingTarget.model_validate(_read_json(args.target))
        base = None
        if args.base_plan is not None:
            with args.base_plan.open("rb") as stream:
                base = read_path(stream.read(MAX_PLAN_BYTES + 1))
        method = None if args.method is None else RibbingMethod.model_validate(_read_json(args.method))
        paths = write_design(target, args.out_dir, base=base, method=method, pdf=args.pdf)
    except (ValueError, OSError, ImportError) as exc:
        parser.exit(2, f"构造设计未导出：{exc}\n")
    for path in paths:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
