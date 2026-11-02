"""Public modules must also import in a fresh interpreter, without test-order help."""
import os
import subprocess
import sys

import pytest


def run_python(program):
    return subprocess.run([sys.executable, "-c", program], text=True, capture_output=True,
                          env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})


@pytest.mark.parametrize("module", [
    "app.schemas", "app.utils.project", "app.utils.schema_docs", "app.models.gauge",
    "app.models.materials", "app.models.geometry", "app.ui.result_logic",
])
def test_public_module_imports_without_prior_package_initialization(module):
    result = run_python(f"import importlib; importlib.import_module({module!r})")
    assert result.returncode == 0, result.stderr


def test_schema_first_retains_model_package_reexports():
    result = run_python("""
from app.schemas import CrochetPart, PartGauge
from app.models import CrochetParamsGenerator, ImageParser, PipelineOrchestrator, StructureDesigner
from app.models.crochet_params import CrochetParamsGenerator as Generator
from app.models.image_parser import ImageParser as Parser
from app.models.orchestrator import PipelineOrchestrator as Orchestrator
from app.models.structure_designer import StructureDesigner as Designer
assert (CrochetParamsGenerator, ImageParser, PipelineOrchestrator, StructureDesigner) == (
    Generator, Parser, Orchestrator, Designer)
assert PartGauge(stitches_per_10cm=6, rows_per_10cm=8).stitches_per_10cm == 6
""")
    assert result.returncode == 0, result.stderr
