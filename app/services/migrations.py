"""Upgrade stored pattern results to the current format, one version at a time.

Backups, share links, history records, project files and trial bundles all
become session results through ``upgrade_result`` (via ``import_backup``). A
newer or unknown format is rejected rather than guessed; an older one runs every
step from its version to the current one.

To change the stored format: bump ``SCHEMA_VERSION`` in ``app.schemas`` and
register a step from the previous version here. A step takes and returns a plain
dict and must not call code that may change later, so old files keep upgrading
the same way. A project file binds its progress to the pattern revision of the
stored data, so ``read_project_state`` checks the revision before the upgraded
pattern is used.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from app.schemas import SCHEMA_VERSION

# Records written before results carried a version.
UNVERSIONED = "0"


class UnsupportedFormatError(ValueError):
    """The record was written in a format this version cannot read."""

    def __init__(self, version: object) -> None:
        self.version = version
        super().__init__(f"不支持的图解格式版本 schema_version={version!r}（当前 {SCHEMA_VERSION}）；"
                         "更新版本保存的文件请用更新版本的应用打开")


def _label_unversioned(data: dict[str, Any]) -> dict[str, Any]:
    # Version 1 readers default every key that unversioned records may lack.
    return data


def _upgrade_v1(data: dict[str, Any]) -> dict[str, Any]:
    # Version 2 adds optional authored color assignments; old results carry no
    # such assignments and must not acquire guessed provenance during import.
    return data


# Each stored version → (next version, step producing it).
_STEPS: dict[str, tuple[str, Callable[[dict[str, Any]], dict[str, Any]]]] = {
    UNVERSIONED: ("1", _label_unversioned),
    "1": ("2", _upgrade_v1),
}


def result_format_version(data: Mapping[str, Any]) -> str:
    version = data.get("schema_version")
    if version is None:
        return UNVERSIONED
    # UNVERSIONED is never written; only a missing field means an unversioned record.
    if not isinstance(version, str) or (
            version != SCHEMA_VERSION and (version == UNVERSIONED or version not in _STEPS)):
        raise UnsupportedFormatError(version)
    return version


def upgrade_result(data: Mapping[str, Any]) -> dict[str, Any]:
    """A copy of a stored result in the current format; the input is not modified."""
    version = result_format_version(data)
    upgraded = dict(data)
    while version != SCHEMA_VERSION:
        version, step = _STEPS[version]
        upgraded = step(upgraded)
        upgraded["schema_version"] = version
    return upgraded
