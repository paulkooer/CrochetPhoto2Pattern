"""Shared harness for the state/restore area reproductions (read-only audit).

Every script imports this FIRST. It redirects HOME, the history DB and the pose
model to a fresh temp directory before anything from `app` is imported, and
asserts that `app` resolves to the audited checkout.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

REPO = Path("<repo>").resolve()
SCRATCH = Path(__file__).resolve().parent
TMP = Path(tempfile.mkdtemp(prefix="fable-state-restore-"))

os.environ["HOME"] = str(TMP / "home")
(TMP / "home").mkdir()
os.environ["CROCHET_HISTORY_DB"] = str(TMP / "history.db")
os.environ["CROCHET_HISTORY_MODE"] = "single_user"
os.environ["CROCHET_POSE_MODEL"] = str(TMP / "unconfigured-pose.task")
os.environ["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"
for name in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_BASE_URL", "ANTHROPIC_BASE_URL"):
    os.environ.pop(name, None)

if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import app  # noqa: E402

assert str(Path(app.__file__).resolve()).startswith(str(REPO)), app.__file__
APP_MAIN = str(REPO / "app" / "main.py")


def git_head() -> str:
    import subprocess

    return subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"],
                          capture_output=True, text=True, check=True).stdout.strip()


def banner(name: str) -> None:
    print(f"=== {name} ===")
    print(f"python {sys.version.split()[0]} | app {app.__file__} | version {app.software_version()}")
    print(f"HEAD {git_head()} | tmp {TMP}")


def mock_result(result_id: str) -> dict:
    """Same construction as tests/test_app_smoke._mock_result (default template doll)."""
    from app.models.crochet_params import CrochetParamsGenerator
    from app.models.image_parser import ImageParser
    from app.models.structure_designer import StructureDesigner

    analysis = ImageParser._mock_analysis()
    structure = StructureDesigner.design_3d_structure(analysis)
    params = CrochetParamsGenerator.generate_params(analysis, structure)
    return {
        "analysis": analysis.model_dump(), "structure": structure, "params": params,
        "result_id": result_id, "usage": {}, "vision_meta": {},
        "gauge": {"stitches_per_10cm": 13.0, "rows_per_10cm": 16.0},
        "style": {"sphere_mode": "ladder", "one_piece": False, "skirt_style": "ring", "ruffle_hem": False},
        "color_bands": None, "spans": None, "spans_measured": [], "preview": None,
        "sizing": {"source": "test", "absolute_scale_from_photo": False, "note": "测试显式尺寸"},
        "geometry": {"schema_version": "1.0", "silhouette": None, "used_for_generation": False,
                     "limitations": []},
    }


def manual_result(parts=("头部", "身体", "手臂", "腿部"), head=9.0, height=18.0, result_id=None,
                  one_piece=False, skirt_style="ring") -> dict:
    """The legacy manual-tab generation path without Streamlit (tab_manual._run_pipeline_from_analysis)."""
    import uuid

    from app import software_version
    from app.models.crochet_params import CrochetParamsGenerator
    from app.models.gauge import ShapingStyle, gauge_from_ui
    from app.models.geometry import no_photo_geometry
    from app.models.sizing import sizing_meta_for_analysis
    from app.models.structure_designer import StructureDesigner
    from app.schemas import ImageAnalysis, PatternResult

    analysis = ImageAnalysis(body_type="标准", head_diameter_cm=head, height_cm=height,
                             main_features=["卡通风格"], pose="站立", difficulty="easy", parts=list(parts))
    style = ShapingStyle(sphere_mode="ladder", one_piece=one_piece, skirt_style=skirt_style, ruffle_hem=False)
    structure = StructureDesigner.design_3d_structure(analysis)
    params = CrochetParamsGenerator.generate_params(analysis, structure,
                                                    gauge=gauge_from_ui("classic", None, None), style=style)
    return PatternResult(
        generator_version=software_version(), analysis=analysis.model_dump(), structure=dict(structure),
        params=dict(params), result_id=result_id or uuid.uuid4().hex[:12],
        style={"sphere_mode": style.sphere_mode, "one_piece": style.one_piece,
               "skirt_style": style.skirt_style, "ruffle_hem": style.ruffle_hem},
        spans_measured=[], sizing=sizing_meta_for_analysis(analysis, "manual_dimensions"),
        geometry=no_photo_geometry().model_dump(),
    ).to_result_dict()
