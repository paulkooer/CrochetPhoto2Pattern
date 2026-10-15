"""Local-only runtime, CLI, and historical backup compatibility."""
import builtins
import socket
import tomllib
from pathlib import Path

import pytest
from PIL import Image

from app.cli import build_parser, run
from app.models.image_parser import ImageParser
from app.models.orchestrator import PipelineOrchestrator
from app.ui.result_logic import import_backup


@pytest.mark.parametrize("entry", ["parser", "pipeline", "cli", "cli_local"])
def test_legacy_keys_cannot_trigger_sdk_imports_or_network(monkeypatch, tmp_path, entry):
    for provider in ("OPENAI", "ANTHROPIC"):
        monkeypatch.setenv(f"{provider}_API_KEY", "obsolete-key")
        monkeypatch.setenv(f"{provider}_BASE_URL", "https://invalid.example")
    attempted = []
    original_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name.split(".")[0] in ("openai", "anthropic"):
            attempted.append(name)
            raise AssertionError("Cloud SDK import")
        return original_import(name, *args, **kwargs)

    def forbidden(*args, **kwargs):
        attempted.append("network")
        raise AssertionError("Network request")

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    image = Image.new("RGB", (60, 100), "white")
    if entry == "parser":
        parser = ImageParser()
        assert parser.parse_image(image).parts
        meta, usage = parser.last_local_meta, parser.last_usage
    else:
        if entry.startswith("cli"):
            path = tmp_path / "photo.png"
            image.save(path)
            args = ["--image", str(path)] + (["--local"] if entry == "cli_local" else [])
            result = run(build_parser().parse_args(args))
        else:
            result = PipelineOrchestrator().run_full_pipeline(image)
        meta, usage = result["vision_meta"], result["usage"]
        assert result["params"]["parts"]
    assert meta["source"] in ("default", "opencv-face")
    assert usage == {}
    assert attempted == []  # Also catches requests swallowed by fallback handlers.


def test_removed_ai_mode_fails_explicitly():
    with pytest.raises(ValueError, match="vision_mode"):
        PipelineOrchestrator().prepare_photo(Image.new("RGB", (30, 30)), vision_mode="ai")


def test_historical_cloud_provenance_survives_import():
    result = run(build_parser().parse_args(["--mock"]))
    result["vision_meta"] = {"source": "openai", "note": "Historical result"}
    result["usage"] = {"provider": "openai", "input_tokens": 100, "output_tokens": 20}
    restored = import_backup(result, "historical")
    assert restored["vision_meta"] == result["vision_meta"]
    assert restored["usage"] == result["usage"]


def test_distribution_has_no_cloud_sdks_or_prompts():
    root = Path(__file__).resolve().parents[1]
    project = tomllib.loads((root / "pyproject.toml").read_text())
    lock = tomllib.loads((root / "uv.lock").read_text())
    assert not any(dep.startswith(("openai", "anthropic"))
                   for dep in project["project"]["dependencies"])
    assert not {"openai", "anthropic"} & {p["name"] for p in lock["package"]}
    assert not (root / "app/prompts/vision_parser.txt").exists()
