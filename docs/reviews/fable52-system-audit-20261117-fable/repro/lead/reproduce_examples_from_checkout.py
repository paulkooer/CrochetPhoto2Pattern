"""Re-run the packaged example jobs against the pinned checkout (HEAD 6c88b7d).

Mirrors the package's reproduce_examples.py job list, but runs the CLIs with the
repository root as cwd instead of the extracted package's source/ directory, and
then compares every produced file with the package's examples/generated/.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', required=True, type=Path)
    parser.add_argument('--package', required=True, type=Path)
    parser.add_argument('--out-dir', required=True, type=Path)
    args = parser.parse_args()
    repo = args.repo.resolve()
    package = args.package.resolve()
    inputs = package / 'examples/inputs'
    packaged = package / 'examples/generated'
    output = args.out_dir.resolve()
    if output.exists():
        parser.error('Use a new output directory.')
    output.mkdir(parents=True)

    jobs = [
        ('armhole-demo', ['app.working_paths']),
        ('doll-wide-brim', ['app.doll_cli', '--starter', 'wide_brim_curls']),
        ('doll-folded-cap', ['app.doll_cli', '--starter', 'folded_cap_layers']),
        ('attached-ribbing', ['app.ribbing_design', '--target', str(inputs / 'ribbing-target.json'),
                             '--base-plan', str(inputs / 'ribbing-base.json'),
                             '--method', str(inputs / 'ribbing-method.json')]),
    ]
    jobs += [(name, ['app.cardigan_design', '--design', str(inputs / f'{name}.json')]) for name in (
        'cardigan-open', 'cardigan-seamed', 'cardigan-missing-gauge', 'cardigan-depth-quantization')]

    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    probe = subprocess.run([sys.executable, '-c', 'import app; print(app.__file__)'], cwd=repo,
                           capture_output=True, text=True, env=env)
    print('app module:', probe.stdout.strip())
    assert probe.stdout.strip().startswith(str(repo)), 'app does not resolve to the pinned checkout'

    summary = []
    for name, options in jobs:
        command = [sys.executable, '-m', *options, '--out-dir', str(output / name), '--pdf']
        process = subprocess.run(command, cwd=repo, capture_output=True, text=True, env=env)
        (output / f'{name}.stdout.txt').write_text(process.stdout)
        (output / f'{name}.stderr.txt').write_text(process.stderr)
        produced = sorted(p.relative_to(output / name).as_posix()
                          for p in (output / name).rglob('*') if p.is_file()) if (output / name).exists() else []
        expected = sorted(p.relative_to(packaged / name).as_posix()
                          for p in (packaged / name).rglob('*') if p.is_file())
        rows = []
        for relative in sorted(set(produced) | set(expected)):
            mine, theirs = output / name / relative, packaged / name / relative
            if not mine.exists():
                state = 'MISSING_IN_RERUN'
            elif not theirs.exists():
                state = 'EXTRA_IN_RERUN'
            elif digest(mine) == digest(theirs):
                state = 'identical'
            else:
                state = f'DIFFERENT ({mine.stat().st_size} vs {theirs.stat().st_size} bytes)'
            rows.append((relative, state))
        summary.append({'case': name, 'exit_code': process.returncode, 'files': rows})
        print(f'\n== {name}: exit {process.returncode}')
        if process.stdout.strip():
            print('   stdout:', process.stdout.strip().replace('\n', '\n           '))
        if process.stderr.strip():
            print('   stderr:', process.stderr.strip().replace('\n', '\n           '))
        for relative, state in rows:
            print(f'   {relative}: {state}')
    (output / 'comparison.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')


if __name__ == '__main__':
    main()
