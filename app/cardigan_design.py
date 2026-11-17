"""Generate staged cardigan design candidates from explicit dimensional inputs."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.models.cardigan_design import CardiganRequest, assemble_cardigan
from app.utils.backup import loads_strict
from app.utils.working_path_export import export_working_path_markdown
from app.utils.working_recipe_export import export_working_recipe_pdf
from app.working_paths import MAX_PLAN_BYTES


def write_cardigan(request: CardiganRequest, directory: Path, *, pdf: bool = False) -> list[Path]:
    result = assemble_cardigan(request)
    outputs = {
        "design-request.json": request.model_dump_json(indent=2).encode(),
        "design-report.json": (json.dumps(result.to_dict(), ensure_ascii=False, indent=2) + "\n").encode(),
    }
    if result.plan is not None:
        outputs["path-plan.json"] = result.plan.model_dump_json(indent=2).encode()
        outputs["path-explanation.md"] = export_working_path_markdown(result.plan).encode()
        if pdf:
            outputs["path-explanation.pdf"] = export_working_recipe_pdf(result.plan)
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
    parser.add_argument("--design", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--pdf", action="store_true")
    args = parser.parse_args(argv)
    try:
        with args.design.open("rb") as stream:
            data = stream.read(MAX_PLAN_BYTES + 1)
        if len(data) > MAX_PLAN_BYTES:
            raise ValueError("设计输入超过2 MiB")
        request = CardiganRequest.model_validate(loads_strict(data.decode("utf-8-sig")))
        paths = write_cardigan(request, args.out_dir, pdf=args.pdf)
    except (ValueError, OSError, ImportError, RecursionError) as exc:
        parser.exit(2, f"开衫设计未导出：{exc}\n")
    for path in paths:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
