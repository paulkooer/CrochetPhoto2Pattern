"""Batch preflight must protect every input and destination before starting work."""
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from PIL import Image

from app import cli
from tests.test_exports_share_cli import _full_result


def inputs(folder):
    folder.mkdir()
    for name,color in [("a","red"),("b","blue")]:
        Image.new("RGB",(40,80),color).save(folder/f"{name}.png")
    return {p.name:p.read_bytes() for p in folder.iterdir()}


@pytest.mark.parametrize("workers",[1,4])
@pytest.mark.parametrize("kind",["input-symlink","input-hardlink","output-symlink","output-hardlink"])
def test_cross_job_alias_rejected_before_generation_preserves_files(tmp_path,monkeypatch,capsys,workers,kind):
    source,out=tmp_path/"in",tmp_path/"out"
    originals=inputs(source)
    out.mkdir()
    victim=source/"b.png" if kind.startswith("input") else out/"b.json"
    if kind.startswith("output"):
        victim.write_bytes(b"original destination")
    alias=out/"a.json"
    if kind.endswith("symlink"):
        alias.symlink_to(victim)
    else:
        alias.hardlink_to(victim)
    before=victim.read_bytes()
    monkeypatch.setattr(cli,"run",lambda *_:pytest.fail("must not start any generator"))
    assert cli.main(["--batch-dir",str(source),"--out-dir",str(out),"--workers",str(workers),"--quiet"])==1
    assert {p.name:p.read_bytes() for p in source.iterdir()}==originals
    assert victim.read_bytes()==before
    assert not list(out.glob("*.md"))
    assert "路径冲突" in capsys.readouterr().err


@pytest.mark.parametrize("kind",["md","pdf","parade"])
def test_cross_format_output_aliases_are_included_in_global_plan(tmp_path,monkeypatch,kind):
    source,out=tmp_path/"in",tmp_path/"out"
    inputs(source)
    out.mkdir()
    suffix={"md":"md","pdf":"pdf","parade":"parade.txt"}[kind]
    (out/f"a.{suffix}").symlink_to(out/"b.json")
    monkeypatch.setattr(cli,"run",lambda *_:pytest.fail("must preflight every format"))
    flags=[] if kind=="md" else [f"--{kind}","enabled"]
    assert cli.main(["--batch-dir",str(source),"--out-dir",str(out),*flags,"--quiet"])==1
    assert not (out/"a.json").exists() and not (out/"b.json").exists()


def test_symlink_cycle_is_reported_without_partial_batch_outputs(tmp_path,monkeypatch,capsys):
    source,out=tmp_path/"in",tmp_path/"out"
    inputs(source)
    out.mkdir()
    (out/"a.json").symlink_to(out/"b.json")
    (out/"b.json").symlink_to(out/"a.json")
    monkeypatch.setattr(cli,"run",lambda *_:pytest.fail("must reject cyclic destination"))
    assert cli.main(["--batch-dir",str(source),"--out-dir",str(out),"--quiet"])==1
    assert "批量输出准备失败" in capsys.readouterr().err
    assert not list(out.glob("*.md"))


def test_distinct_aliases_remain_supported_and_jobs_use_canonical_targets(tmp_path,monkeypatch):
    source,out,real=tmp_path/"in",tmp_path/"out",tmp_path/"real"
    originals=inputs(source)
    out.mkdir()
    real.mkdir()
    for name in ("a","b"):
        (out/f"{name}.json").symlink_to(real/f"{name}.json")
    def generate(args):
        assert Path(args.out).parent==real
        result=_full_result()
        result["analysis"]["body_type"]=Path(args.image).name
        return result
    monkeypatch.setattr(cli,"run",generate)
    assert cli.main(["--batch-dir",str(source),"--out-dir",str(out),"--workers","4","--quiet"])==0
    for name in ("a","b"):
        assert json.loads((real/f"{name}.json").read_text())["analysis"]["body_type"]==f"{name}.png"
    assert {p.name:p.read_bytes() for p in source.iterdir()}==originals


def test_actual_cli_refuses_output_link_to_other_input(tmp_path):
    source,out=tmp_path/"in",tmp_path/"out"
    originals=inputs(source)
    out.mkdir()
    (out/"a.json").symlink_to(source/"b.png")
    proc=subprocess.run([sys.executable,"-m","app.cli","--batch-dir",str(source),
        "--out-dir",str(out),"--quiet"],cwd=Path(__file__).resolve().parents[1],
        capture_output=True,text=True,timeout=30)
    assert proc.returncode==1 and "路径冲突" in proc.stderr
    assert "Traceback" not in proc.stderr and "完成 2/2" not in proc.stderr
    assert {p.name:p.read_bytes() for p in source.iterdir()}==originals


@pytest.mark.parametrize("workers",[None,2,4])
def test_requested_worker_limit_reaches_executor_and_keeps_every_result(tmp_path,monkeypatch,workers):
    source,out=tmp_path/"in",tmp_path/"out"
    inputs(source)
    recorded=[]
    class Executor(ThreadPoolExecutor):
        def __init__(self,*args,**kwargs):
            recorded.append(kwargs["max_workers"])
            super().__init__(*args,**kwargs)
    monkeypatch.setattr("concurrent.futures.ThreadPoolExecutor",Executor)
    def generate(args):
        result=_full_result()
        result["analysis"]["body_type"]=Path(args.image).name
        return result
    monkeypatch.setattr(cli,"run",generate)
    extra=[] if workers is None else ["--workers",str(workers)]
    assert cli.main(["--batch-dir",str(source),"--out-dir",str(out),*extra,"--quiet"])==0
    assert recorded==[1 if workers is None else workers]
    assert sorted(json.loads(p.read_text())["analysis"]["body_type"] for p in out.glob("*.json"))==[
        "a.png","b.png"]


@pytest.mark.parametrize("workers",[0,-1,5])
def test_invalid_worker_limit_is_rejected_before_mkdir_or_generation(tmp_path,monkeypatch,capsys,workers):
    output=tmp_path/"new-output"
    monkeypatch.setattr(cli,"run_batch",lambda *_:pytest.fail("must not enter batch"))
    assert cli.main(["--batch-dir",str(tmp_path),"--out-dir",str(output),"--workers",str(workers)])==2
    assert not output.exists() and "并发参数无效" in capsys.readouterr().err
