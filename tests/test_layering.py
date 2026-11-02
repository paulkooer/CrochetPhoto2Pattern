"""Layering guard: domain, services and headless tools never depend on the UI or Streamlit."""
import ast
import subprocess
import sys
from pathlib import Path

import pytest

_APP = Path(__file__).resolve().parents[1] / "app"
_HEADLESS = [
    *sorted((_APP / "models").rglob("*.py")),
    *sorted((_APP / "utils").rglob("*.py")),
    *sorted((_APP / "services").rglob("*.py")),
    *(_APP / name for name in ("__init__.py", "cli.py", "evaluation.py", "trials.py",
                               "schemas.py", "gauge_constraints.py")),
]


def _imported_modules(path: Path) -> set[str]:
    package = ".".join(path.relative_to(_APP.parent).with_suffix("").parts[:-1])
    modules: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                parent = package.split(".")[: len(package.split(".")) - node.level + 1]
                base = ".".join([*parent, base]) if base else ".".join(parent)
            modules.add(base)
            modules.update(f"{base}.{alias.name}" for alias in node.names)
    return modules


@pytest.mark.parametrize("path", _HEADLESS, ids=lambda p: str(p.relative_to(_APP.parent)))
def test_headless_modules_do_not_import_ui_or_streamlit(path):
    forbidden = {m for m in _imported_modules(path)
                 if m == "streamlit" or m.startswith(("streamlit.", "app.ui"))}
    assert not forbidden, f"{path.name} imports {sorted(forbidden)}"


def test_headless_entry_points_load_without_streamlit():
    code = ("import sys, app.cli, app.evaluation, app.trials, app.utils.project; "
            "print(sorted(m for m in sys.modules if m == 'streamlit' or m.startswith('app.ui')))")
    out = subprocess.run([sys.executable, "-c", code], cwd=_APP.parent, capture_output=True,
                         text=True, check=True, timeout=60).stdout.strip()
    assert out == "[]"
