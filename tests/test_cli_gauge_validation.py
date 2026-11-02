"""New CLI inputs must be rejected before generation, mkdir or output changes."""
import json
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image

from app import cli

INVALID = [[],["--stitches","26"],["--stitches","nan","--rows","28"],
           ["--stitches","0","--rows","28"],["--stitches","100","--rows","28"],
           ["--stitches","26","--rows","inf"],["--stitches","26","--rows","7"]]


@pytest.mark.parametrize("mode",["manual","mock","photo","batch"])
@pytest.mark.parametrize("values",INVALID)
def test_invalid_custom_gauge_rejected_before_work_or_file_write(tmp_path,monkeypatch,capsys,mode,values):
    existing = tmp_path/"pattern.json"
    existing.write_bytes(b"keep original")
    output = tmp_path/"not-created"
    source = tmp_path/"photo.png"
    mode_args = {"manual":[],"mock":["--mock"],"photo":["--image",str(source)],
                 "batch":["--batch-dir",str(tmp_path),"--out-dir",str(output)]}[mode]
    monkeypatch.setattr(cli,"run",lambda *_:pytest.fail("must not generate"))
    monkeypatch.setattr(cli,"run_batch",lambda *_:pytest.fail("must not enter batch"))
    assert cli.main([*mode_args,"--gauge","custom",*values,"--out",str(existing),"--quiet"]) == 2
    assert existing.read_bytes() == b"keep original"
    assert not output.exists() and not source.exists()
    assert "密度参数无效" in capsys.readouterr().err


@pytest.mark.parametrize("stitches,rows",[(6,8),(40,50),(26,28)])
def test_supported_custom_values_reach_the_generated_pattern_without_clamping(tmp_path,stitches,rows):
    output = tmp_path/"pattern.json"
    # 10 cm 头在最粗的 6 针/10cm 下仍有 18 针，不触发可钩性门禁
    assert cli.main(["--parts","头部,身体","--head","10","--height","18",
        "--gauge","custom","--stitches",str(stitches),"--rows",str(rows),
        "--out",str(output),"--quiet"]) == 0
    assert json.loads(output.read_text())["params"]["gauge"] == {
        "stitches_per_10cm":stitches,"rows_per_10cm":rows}


@pytest.mark.parametrize("batch",[False,True])
def test_real_cli_process_exits_two_and_keeps_outputs_on_nan(tmp_path,batch):
    existing = tmp_path/"pattern.json"
    existing.write_bytes(b"original")
    target = tmp_path/"new-output"
    args = (["--batch-dir",str(tmp_path),"--out-dir",str(target)] if batch else [])
    proc = subprocess.run([sys.executable,"-m","app.cli",*args,"--gauge","custom",
        "--stitches","nan","--rows","28","--out",str(existing),"--quiet"],
        cwd=Path(__file__).resolve().parents[1],capture_output=True,text=True,timeout=30)
    assert proc.returncode == 2 and "密度参数无效" in proc.stderr
    assert "Traceback" not in proc.stderr and not proc.stdout
    assert existing.read_bytes() == b"original" and not target.exists()


@pytest.mark.parametrize("batch",[False,True])
def test_valid_photo_and_batch_keep_custom_gauge_and_explicit_parts(tmp_path,monkeypatch,batch):
    image = tmp_path/"input.png"
    Image.new("RGB",(80,160),"white").save(image)
    monkeypatch.setenv("CROCHET_POSE_MODEL",str(tmp_path/"unconfigured.task"))
    out_dir = tmp_path/"out"
    out_dir.mkdir()
    args = (["--batch-dir",str(tmp_path),"--out-dir",str(out_dir)] if batch else
            ["--image",str(image),"--out",str(out_dir/"input.json")])
    assert cli.main([*args,"--gauge","custom","--stitches","26","--rows","28",
        "--parts","头部,身体","--quiet"]) == 0
    result = json.loads((out_dir/"input.json").read_text())
    assert result["params"]["gauge"] == {"stitches_per_10cm":26,"rows_per_10cm":28}
    assert {p["name"] for p in result["params"]["parts"]} == {"头部","身体"}
    assert result["vision_meta"]["parts_source"] == "cli_explicit"
    assert result["vision_meta"]["requires_subject_review"]
