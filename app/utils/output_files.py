"""Preflight and staged CLI exports; each replacement is atomic, not the group."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unicodedata import normalize


def output_paths(args) -> dict[str, Path]:
    paths: dict[str, Path] = {}
    source = Path(args.image).resolve() if args.image else None
    for kind in ("out", "md", "parade", "pdf"):
        value = getattr(args, kind, None)
        if not value:
            continue
        path = Path(value).resolve()
        if not path.parent.is_dir() or (path.exists() and not path.is_file()):
            raise ValueError(f"输出路径不可用: {path}")
        for other in [*paths.values(), *([source] if source else [])]:
            same_name = normalize("NFC", str(path)).casefold() == normalize("NFC", str(other)).casefold()
            if same_name or (path.exists() and other.exists() and path.samefile(other)):
                raise ValueError(f"输入/输出路径冲突: {path}")
        paths[kind] = path
    return paths


def write_outputs(outputs: dict[Path, bytes]) -> None:
    """Stage all contents and backups before replacing any destination.

    Roll back ordinary replacement errors. Power loss/process termination can
    still interrupt a group; filesystem APIs do not offer multi-file atomicity.
    """
    staged: dict[Path, Path] = {}
    backups: dict[Path, Path] = {}
    replaced: list[Path] = []
    temporary: list[Path] = []

    def stage(path: Path, data: bytes) -> Path:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".crochet-", delete=False) as handle:
            name = Path(handle.name)
            temporary.append(name)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        return name

    try:
        for path, data in outputs.items():
            staged[path] = stage(path, data)
            if path.exists():
                backups[path] = stage(path, path.read_bytes())
        try:
            for path, pending in staged.items():
                os.replace(pending, path)
                replaced.append(path)
        except OSError:
            recovery_errors = []
            for path in reversed(replaced):
                if path in backups:
                    backup = backups[path]
                    # Keep recovery bytes if rollback itself fails.
                    temporary.remove(backup)
                    try:
                        os.replace(backup, path)
                    except OSError as exc:
                        recovery_errors.append(f"原文件备份保留于 {backup}: {exc}")
                else:
                    try:
                        path.unlink()
                    except OSError as exc:
                        recovery_errors.append(f"未能移除新文件 {path}: {exc}")
            if recovery_errors:
                raise OSError("恢复失败；" + "；".join(recovery_errors)) from None
            raise
    finally:
        for path in temporary:
            path.unlink(missing_ok=True)
