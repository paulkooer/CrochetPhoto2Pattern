"""Guard the declared Streamlit support range against the rest of the dependency set.

`pyproject.toml` used to declare `streamlit>=1.40.0,<2.0`. A plain install resolved that
range to 1.66.1 and succeeded, but the declaration advertised versions that cannot be
installed next to the project's own floors and others that cannot run, so the metadata
promised support the project could not deliver. The upstream facts behind the current
bound:

* `pillow>=13.0.0` protects the upload path, which decodes untrusted images (the
  dependency-security workflow tracks it). The sampled 1.40.0 and 1.48.0 releases
  require `pillow<12`, 1.66.0 requires `pillow<13`, and 1.66.1 allows `pillow<14`.
  The floor is the lowest version verified in this work, not a claim about future releases.
* `protobuf>=6.33.5,<8` overlaps with the `protobuf<7` cap in the sampled 1.45.0
  and 1.55.0 releases via 6.x; 1.56.0 allows 7.x by widening its cap to `<8`.
  The `<6` caps in 1.40.0 and 1.44.0 conflict with the project floor.
* The UI calls `width="stretch"` on buttons, images and dataframes, and uses
  `st.container(horizontal=True)` for button groups. Both
  first exist in 1.48.0; earlier releases take an int `width` and `use_container_width`
  only, which is why the 1.40 probe also failed at run time rather than at install time.

These tests keep the declaration honest in three directions: the declared floor may not
drop below the verified minimum, `uv.lock` and `pyproject.toml` must record the same
range, and the installed environment must satisfy it. The `streamlit-floor` CI job
covers the direction a unit test cannot: it installs the declared floor from PyPI in a
clean environment (no lock file) and runs the UI smoke tests against it.
"""
from __future__ import annotations

import importlib.metadata
import inspect
import tomllib
from pathlib import Path

import streamlit as st
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.version import Version

ROOT = Path(__file__).resolve().parent.parent

# This is the verified support floor, not an exhaustive claim about every historical
# release. Lowering it requires installation and UI evidence with all current floors.
MIN_VERIFIED_FLOOR = Version("1.66.1")

# Arguments the UI passes straight to Streamlit. `width` also changed meaning in
# 1.48.0 (int → "stretch"/"content" strings), so the string default is part of the check.
REQUIRED_API_ARGUMENTS = {
    # Button groups and the other three calls are used by the current UI.
    "container": ("horizontal", "width"),
    "button": ("width",),                   # tabs and editors pass width="stretch"
    "image": ("width",),                    # app/ui/tab_photo.py, app/ui/tab_grid.py
    "dataframe": ("width",),                # app/ui/result_renderer.py
}


def _pyproject() -> dict:
    with open(ROOT / "pyproject.toml", "rb") as handle:
        return tomllib.load(handle)


def _declared() -> list[Requirement]:
    """Base runtime requirements as declared, one entry per declaration."""
    return [Requirement(raw) for raw in _pyproject()["project"]["dependencies"]]


def _declared_one(name: str) -> Requirement:
    return next(req for req in _declared() if req.name == name)


def _lock() -> dict:
    with open(ROOT / "uv.lock", "rb") as handle:
        return tomllib.load(handle)


def _locked_project_specifiers() -> dict[str, str]:
    """The ranges uv.lock records for the project's own base dependencies."""
    project = _pyproject()["project"]["name"]
    entry = next(p for p in _lock()["package"] if p["name"] == project)
    recorded = entry.get("metadata", {}).get("requires-dist")
    assert recorded, "uv.lock 没有记录项目自身的 requires-dist，锁定文件已过期？"
    return {item["name"]: item.get("specifier", "") for item in recorded
            if not item.get("marker")}


def test_declared_floor_never_drops_below_the_verified_minimum():
    """The declared lower bound must not fall below the verified support floor."""
    requirement = _declared_one("streamlit")
    floors = [Version(spec.version) for spec in requirement.specifier
              if spec.operator in (">=", ">")]
    assert floors, f"streamlit 缺少下限声明：{requirement}"
    floor = min(floors)
    assert floor >= MIN_VERIFIED_FLOOR, (
        f"声明的 streamlit 下限 {floor} 低于已验证下限 {MIN_VERIFIED_FLOOR}："
        f"已抽查的旧版本与 pillow>=13.0.0 不兼容。降低下限必须先给出"
        f"完整依赖解析和界面运行证据。")
    assert Version("2.0") not in requirement.specifier, (
        "Streamlit 2.x 需要人工验证后才能放开上界")


def test_lock_records_the_declared_range_and_locks_a_version_inside_it():
    requirement = _declared_one("streamlit")
    recorded = _locked_project_specifiers()
    assert "streamlit" in recorded, "uv.lock 未记录 streamlit 依赖"
    assert SpecifierSet(recorded["streamlit"]) == requirement.specifier, (
        f"uv.lock 记录的 streamlit 范围 {recorded['streamlit']!r} 与 pyproject.toml 的 "
        f"{str(requirement.specifier)!r} 不一致：改动了依赖声明后需要重新运行 uv lock")

    locked = next(p["version"] for p in _lock()["package"]
                  if p["name"] == "streamlit" and p.get("version"))
    assert Version(locked) in requirement.specifier, (
        f"uv.lock 锁定的 streamlit {locked} 不在声明范围 {requirement.specifier} 内")


def test_installed_environment_satisfies_every_declared_floor():
    """An installed environment must satisfy the metadata it was installed from."""
    for requirement in _declared():
        if requirement.marker and not requirement.marker.evaluate():
            continue
        installed = importlib.metadata.version(requirement.name)
        assert Version(installed) in requirement.specifier, (
            f"已安装的 {requirement.name} {installed} 不满足声明的 "
            f"{requirement.specifier}（来源：pyproject.toml）")


def test_installed_streamlit_supports_the_arguments_the_ui_passes():
    """The UI's calls must exist in the installed version, not only in the metadata."""
    version = Version(importlib.metadata.version("streamlit"))
    assert version in _declared_one("streamlit").specifier

    for name, arguments in REQUIRED_API_ARGUMENTS.items():
        parameters = inspect.signature(getattr(st, name)).parameters
        for argument in arguments:
            assert argument in parameters, (
                f"st.{name} 在 Streamlit {version} 上没有 {argument!r} 参数，"
                f"界面会直接失败（1.48.0 之前缺少该参数）")

    for name in ("container", "button", "image", "dataframe"):
        default = inspect.signature(getattr(st, name)).parameters["width"].default
        assert isinstance(default, str), (
            f"Streamlit {version} 的 st.{name}(width=...) 仍是整数语义"
            f"（默认 {default!r}），不接受界面传入的 width=\"stretch\"")
