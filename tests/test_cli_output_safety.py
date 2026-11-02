import os
import stat
import tracemalloc
from pathlib import Path

import pytest

from app import cli
from app.utils import output_files


@pytest.mark.parametrize("collision", ["same", "symlink", "hardlink", "input"])
def test_output_aliases_rejected_before_generation(tmp_path, monkeypatch, collision):
    target = tmp_path / "original"
    target.write_bytes(b"original")
    alias = tmp_path / "alias"
    if collision == "symlink":
        alias.symlink_to(target)
    elif collision == "hardlink":
        alias.hardlink_to(target)
    else:
        alias = target
    args = ["--image", str(target)] if collision == "input" else ["--mock"]
    args += ["--out", str(target), "--md", str(alias), "--quiet"]
    monkeypatch.setattr(cli, "run", lambda _: pytest.fail("must preflight before pipeline"))
    assert cli.main(args) == 1
    assert target.read_bytes() == b"original"


def test_missing_output_directory_does_not_write_first_file(tmp_path):
    target = tmp_path / "pattern.json"
    assert cli.main(["--mock", "--out", str(target), "--md", str(tmp_path / "absent/p.md")]) == 1
    assert not target.exists()


def test_export_failure_preserves_existing_outputs(tmp_path, monkeypatch):
    target = tmp_path / "pattern.json"
    target.write_bytes(b"original")

    def fail(*args, **kwargs):
        raise ValueError("cannot export")

    monkeypatch.setattr(cli, "export_markdown", fail)
    assert cli.main(["--mock", "--out", str(target), "--md", str(tmp_path / "p.md")]) == 1
    assert target.read_bytes() == b"original"
    assert not (tmp_path / "p.md").exists()


@pytest.mark.parametrize("existing", [False, True])
def test_replace_failure_rolls_back_group(tmp_path, monkeypatch, existing):
    first, second = tmp_path / "first", tmp_path / "second"
    if existing:
        first.write_bytes(b"original")
    second.write_bytes(b"second original")
    replace = output_files.os.replace

    def fail_second(source, destination):
        if Path(destination) == second:
            raise OSError("injected replacement failure")
        replace(source, destination)

    monkeypatch.setattr(output_files.os, "replace", fail_second)
    with pytest.raises(OSError, match="injected"):
        output_files.write_outputs({first: b"new", second: b"new"})
    assert first.read_bytes() == b"original" if existing else not first.exists()
    assert second.read_bytes() == b"second original"
    assert not list(tmp_path.glob(".crochet-*"))


def test_nonexistent_case_aliases_rejected(tmp_path):
    args = cli.build_parser().parse_args([
        "--mock", "--out", str(tmp_path / "pattern.json"), "--md", str(tmp_path / "PATTERN.JSON")])
    with pytest.raises(ValueError, match="冲突"):
        output_files.output_paths(args)


def test_staging_failure_leaves_destinations_untouched(tmp_path, monkeypatch):
    first, second = tmp_path / "first", tmp_path / "second"
    first.write_bytes(b"original")
    fsync = output_files.os.fsync
    calls = 0

    def fail_late(fd):
        nonlocal calls
        calls += 1
        if calls == 3:
            raise OSError("staging disk failure")
        fsync(fd)

    monkeypatch.setattr(output_files.os, "fsync", fail_late)
    with pytest.raises(OSError, match="staging"):
        output_files.write_outputs({first: b"new", second: b"new"})
    assert first.read_bytes() == b"original"
    assert not second.exists()
    assert not list(tmp_path.glob(".crochet-*"))


def test_failed_rollback_keeps_recovery_bytes(tmp_path, monkeypatch):
    first, second = tmp_path / "first", tmp_path / "second"
    first.write_bytes(b"original")
    second.write_bytes(b"second original")
    replace = output_files.os.replace
    calls = 0

    def fail_after_first(source, destination):
        nonlocal calls
        calls += 1
        if calls > 1:
            raise OSError("disk failure")
        replace(source, destination)

    monkeypatch.setattr(output_files.os, "replace", fail_after_first)
    with pytest.raises(OSError, match="备份保留") as error:
        output_files.write_outputs({first: b"new", second: b"new"})
    backups = list(tmp_path.glob(".crochet-*"))
    assert len(backups) == 1
    assert backups[0].read_bytes() == b"original"
    assert str(backups[0]) in str(error.value)


@pytest.mark.skipif(os.name == "nt", reason="POSIX file permissions")
def test_failed_group_write_restores_original_permissions_and_mtime(tmp_path, monkeypatch):
    first, second = tmp_path / "first", tmp_path / "second"
    first.write_bytes(b"original")
    first.chmod(0o640)
    os.utime(first, ns=(1_600_000_000_000_000_000, 1_600_000_001_000_000_000))
    original = first.stat()
    replace = output_files.os.replace

    def fail_second(source, destination):
        if Path(destination) == second:
            raise OSError("injected replacement failure")
        replace(source, destination)

    monkeypatch.setattr(output_files.os, "replace", fail_second)
    with pytest.raises(OSError, match="injected"):
        output_files.write_outputs({first: b"new", second: b"new"})
    restored = first.stat()
    assert first.read_bytes() == b"original"
    assert stat.S_IMODE(restored.st_mode) == stat.S_IMODE(original.st_mode)
    assert restored.st_mtime_ns == original.st_mtime_ns


def test_existing_large_output_is_backed_up_with_bounded_python_memory(tmp_path):
    if tracemalloc.is_tracing():
        pytest.skip("the test needs its own tracemalloc session")
    target = tmp_path / "large-output"
    with target.open("wb") as handle:
        handle.truncate(16 * 1024 * 1024)
    tracemalloc.start()
    try:
        output_files.write_outputs({target: b"replacement"})
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert target.read_bytes() == b"replacement"
    assert peak < 6 * 1024 * 1024


def test_interrupted_backup_copy_keeps_original_and_cleans_partial_files(tmp_path, monkeypatch):
    target = tmp_path / "original"
    target.write_bytes(b"original data")

    def fail_copy(source, destination, length):
        destination.write(source.read(4))
        raise OSError("injected backup failure")

    monkeypatch.setattr(output_files.shutil, "copyfileobj", fail_copy)
    with pytest.raises(OSError, match="backup failure"):
        output_files.write_outputs({target: b"replacement"})
    assert target.read_bytes() == b"original data"
    assert not list(tmp_path.glob(".crochet-*"))


@pytest.mark.parametrize("failure", ["chmod", "utime"])
def test_metadata_restore_failure_still_restores_original_content(tmp_path, monkeypatch, failure):
    first, second = tmp_path / "first", tmp_path / "second"
    first.write_bytes(b"original")
    replace = output_files.os.replace

    def fail_second(source, destination):
        if Path(destination) == second:
            raise OSError("injected replacement failure")
        replace(source, destination)

    def fail_metadata(*args, **kwargs):
        raise OSError("injected metadata failure")

    monkeypatch.setattr(output_files.os, "replace", fail_second)
    monkeypatch.setattr(output_files.os, failure, fail_metadata)
    with pytest.raises(OSError, match="内容已恢复") as error:
        output_files.write_outputs({first: b"new", second: b"new"})
    assert first.read_bytes() == b"original"
    assert not second.exists() and not list(tmp_path.glob(".crochet-*"))
    assert ("权限" if failure == "chmod" else "时间") in str(error.value)


@pytest.mark.parametrize("simulated_non_strict", [False, True])
def test_single_image_output_symlink_cycle_is_reported(tmp_path, capsys, monkeypatch, simulated_non_strict):
    target = tmp_path / "loop"
    target.symlink_to(target)
    if simulated_non_strict:
        # Some Python versions return the unresolved path in non-strict mode.
        resolve = Path.resolve

        def resolve_cycle(self, *args, **kwargs):
            return self if self == target else resolve(self, *args, **kwargs)

        monkeypatch.setattr(Path, "resolve", resolve_cycle)
    assert cli.main(["--mock", "--out", str(target), "--quiet"]) == 1
    assert "输出准备失败" in capsys.readouterr().err
    assert target.is_symlink()
