"""Keep the optional MediaPipe installation within the supported OpenCV major."""

from __future__ import annotations

import tomllib
from pathlib import Path

from packaging.markers import Marker
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.version import Version

ROOT = Path(__file__).resolve().parent.parent


def _read_toml(name: str) -> dict:
    with (ROOT / name).open("rb") as file:
        return tomllib.load(file)


def _requirements(entries: list[str]) -> dict[str, Requirement]:
    requirements = [Requirement(entry) for entry in entries]
    return {requirement.name: requirement for requirement in requirements}


def test_pose_extra_constrains_mediapipes_own_opencv_distribution():
    """The base headless constraint cannot constrain the separate contrib package."""
    project = _read_toml("pyproject.toml")["project"]
    base = _requirements(project["dependencies"])
    pose = _requirements(project["optional-dependencies"]["pose"])
    contrib = pose["opencv-contrib-python"]

    assert contrib.specifier == base["opencv-python-headless"].specifier
    assert Version("4.11.0.86") in contrib.specifier
    assert Version("5.0.0.93") not in contrib.specifier
    for dependency in (pose["mediapipe"], contrib):
        assert dependency.marker is not None
        for version in ("3.11", "3.12"):
            assert dependency.marker.evaluate({"python_version": version})
        for version in ("3.13", "3.14"):
            assert not dependency.marker.evaluate({"python_version": version})


def test_lock_records_the_pose_constraint_and_a_matching_distribution():
    project = _read_toml("pyproject.toml")["project"]
    contrib = _requirements(project["optional-dependencies"]["pose"])["opencv-contrib-python"]
    packages = _read_toml("uv.lock")["package"]
    project_lock = next(package for package in packages if package["name"] == project["name"])
    recorded = next(
        entry for entry in project_lock["metadata"]["requires-dist"]
        if entry["name"] == "opencv-contrib-python"
    )
    assert SpecifierSet(recorded["specifier"]) == contrib.specifier
    marker = Marker(recorded["marker"])
    assert marker.evaluate({"python_full_version": "3.12.0", "extra": "pose"})
    assert not marker.evaluate({"python_full_version": "3.13.0", "extra": "pose"})
    assert not marker.evaluate({"python_full_version": "3.12.0", "extra": ""})

    locked = next(package["version"] for package in packages
                  if package["name"] == "opencv-contrib-python")
    assert Version(locked) in contrib.specifier
