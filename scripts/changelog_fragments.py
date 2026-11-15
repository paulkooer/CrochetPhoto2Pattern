"""Check bilingual fragments, preview them, or collect them at release preparation."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATEGORIES = ("added", "changed", "deprecated", "removed", "fixed", "security")
NAME = re.compile(r"[a-z0-9][a-z0-9-]*\.(" + "|".join(CATEGORIES) + r")\.json")
LOGS = {"zh": "CHANGELOG.md", "en": "CHANGELOG_EN.md"}


def fragments(root: Path) -> list[tuple[Path, dict[str, list[str]], str]]:
    entries = []
    for path in sorted((root / "changelog.d").iterdir()):
        if path.name == "README.md":
            continue
        if not path.is_file() or path.is_symlink() or not NAME.fullmatch(path.name):
            raise ValueError(f"invalid fragment filename: {path.name}")
        raw = path.read_bytes()
        data = json.loads(raw)
        if not isinstance(data, dict) or set(data) != {"zh", "en"}:
            raise ValueError(f"{path.name}: require exactly zh and en")
        for language, bullets in data.items():
            if (not isinstance(bullets, list) or not bullets or
                    any(not isinstance(text, str) or not text.strip() or
                        text != text.strip() or any(char in text for char in "\r\n") for text in bullets)):
                raise ValueError(f"{path.name}: {language} must contain nonempty single-line bullets")
        token = hashlib.sha256(path.name.encode() + b"\0" + raw).hexdigest()
        entries.append((path, data, token))
    return entries


def render(entries: list, language: str, stamp: str) -> str:
    if date.fromisoformat(stamp).isoformat() != stamp:
        raise ValueError("date must be YYYY-MM-DD")
    sections = []
    for category in CATEGORIES:
        matching = [entry for entry in entries if entry[0].name.endswith(f".{category}.json")]
        if matching:
            sections.append(f"### {category.title()} — {stamp}\n\n" + "\n\n".join(
                f"<!-- fragment: {token} -->\n" + "\n".join(f"- {text}" for text in data[language])
                for _, data, token in matching))
    return "\n\n".join(sections) + ("\n\n" if sections else "")


def collect(root: Path, stamp: str, *, write: bool = False) -> dict[str, str]:
    entries = fragments(root)
    outputs = {}
    for language, filename in LOGS.items():
        original = (root / filename).read_text(encoding="utf-8")
        anchor = "## Unreleased\n"
        if original.count(anchor) != 1:
            raise ValueError(f"{filename}: require one Unreleased heading")
        missing = [entry for entry in entries if f"<!-- fragment: {entry[2]} -->" not in original]
        outputs[filename] = original.replace(anchor, anchor + "\n" + render(missing, language, stamp), 1)
    if write and entries:
        # Compute/validate both languages before writing. Markers make interrupted runs retryable.
        for filename, output in outputs.items():
            path = root / filename
            if path.read_text(encoding="utf-8") != output:
                temporary = path.with_suffix(path.suffix + ".tmp")
                temporary.write_text(output, encoding="utf-8")
                temporary.replace(path)
        # A partial write leaves every fragment intact for the next invocation.
        for path, _, token in entries:
            if all(f"<!-- fragment: {token} -->" in (root / name).read_text(encoding="utf-8")
                   for name in LOGS.values()):
                path.unlink()
    return outputs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("check", "render", "collect"))
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--write", action="store_true",
                        help="collect only: update both logs and remove fragments")
    args = parser.parse_args(argv)
    try:
        entries = fragments(ROOT)
        if args.write and args.command != "collect":
            raise ValueError("--write requires collect")
        if args.command == "check":
            print(f"{len(entries)} bilingual fragments valid")
        elif args.command == "render":
            for language in LOGS:
                print(f"--- {language} ---\n{render(entries, language, args.date)}")
        else:
            outputs = collect(ROOT, args.date, write=args.write)
            if not args.write:
                for filename, output in outputs.items():
                    print(f"--- {filename} ---\n{output}")
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
