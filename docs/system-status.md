# System Status and Release Gates

[简体中文](system-status.zh-CN.md) | **English** | [Documentation index](README.md)

> Status snapshot: 2026-11-13. Current behavior is defined by source code,
> `pyproject.toml`, `uv.lock`, and reproducible checks. Audit briefs are historical snapshots.

## Current conclusion

CrochetPhoto2Pattern is a **0.2.0-beta.2 engineering candidate**. Stitch arithmetic, input
gates, exports, and packaging have substantial automated coverage. An authorized
real-photo baseline and an independent physical-trial baseline are still missing, so the
project must not claim validated dimensions, material usage, time, or finished-item crochetability.

## Latest reproducible validation

The saved G1/G2 evidence is [`docs/release-evidence.json`](release-evidence.json).
It is a historical receipt for the exact `commit` in that file, not a status report for
the current `main`. Its `checks_completed_at` and `run_refs` identify the adopted remote
checks. Later commits do not inherit those passes.

Generate a new receipt only after selecting and checking a release candidate, following
the [release process](release-process.md). Routine merges use their own CI results and do
not refresh this receipt or copy its hashes into this page. The generator rejects an
unfinished or unsuccessful latest check, and accepts a separate pip-audit commit only when
its tree matches the candidate's tree. G3 and G4 stay blocked.

Check whether the saved receipt covers a particular commit without network access or writes:

```bash
python scripts/bind_release_evidence.py --status --commit HEAD
```

Exit 1 means the selected commit is not covered. Exit 0 confirms the binding only; it does
not mean all release gates pass.


See the [changelog](../CHANGELOG_EN.md) for changes. The [prior status snapshot](https://github.com/paulkooer/CrochetPhoto2Pattern/blob/d12cda6e6dd02cee31c032a8341a8c58d03cd98b/docs/system-status.md) preserves the historical per-round verification records in Git.

## Independently accepted merged baseline

2026-10-30 final independent acceptance of software consistency fixes: commit
`55280fb485d9182f264402c52cbc171c957c4c51` received **PASS** for the original eight
issues and the two P2 / one P3 follow-ups; these software issues may close. The GPT Pro
report supplied by the maintainer records Python 3.12.14 with locked dev+pdf dependencies:
**2076 passed, 2 skipped in 89.35s**, Ruff, mypy (175 source files under repository settings)
and diff checks passing, with a clean review tree. Skips were the absent authorized-photo
directory and unmet MediaPipe EGL/GLESv2 conditions. The developer's separate run on the
same commit yielded 2076 passed, 2 skipped in 57.25s (Python 3.12.13, MediaPipe not installed).
Export cache is now **version 10**; backup schema remains version 1. No public remote CI
results existed for that SHA when the reviewer queried it; merging requires the repair PR's
current head checks. That acceptance round did not run real-browser tests; subsequent synthetic
browser coverage is recorded above. Authorized photos, physical trials, other browser platforms
and real-photo browser scenarios remain separate work; Beta status and G3/G4 are unchanged.
See the [acceptance handoff](archive/audit-fix-review-20261030.md).

## Release gates

| Gate | Status | Pass condition |
|---|---|---|
| G1 Reproducible source | **Candidate binding must be checked** | The exact source commit and tree are recorded in [`release-evidence.json`](release-evidence.json). Follow the [release process](release-process.md) for a new candidate; the saved receipt does not cover later commits or extend an earlier independent acceptance |
| G2 Supported-version automation | **See the bound candidate's evidence** | The latest required checks must succeed for the candidate. A separate pip-audit run requires an identical tree. Python versions, conclusions, and run links come from the evidence file; required context names are in `.github/required-checks.json` |
| G3 Authorized-photo baseline | **Blocked** | at least 30 stratified schema-v2 cases with per-image rights/subject evidence, passing all `evaluation.en.md` policy-3 thresholds. The noninteractive path can deliver uncalibrated contour candidates; synthetic improvement over the fixed template does not establish real-photo accuracy |
| G4 Physical-trial baseline | **Blocked** | isolated calibration and holdout pattern hashes pass `physical-trials.en.md` rules |
| G5 Distribution package | **Locally passed** | wheel content, metadata, CLIs, and package data validated |
| G6 Product claims | **Beta-compliant** | UI/docs/exports retain single-photo, template, estimate, and trial boundaries |

Do not create a formal release tag until G1–G4 pass. Synthetic inputs, web articles,
published yarn estimates, and more unit tests cannot substitute for authorized photos or
independent physical samples.

The repository has no corpus-ingestion, model-weight training, or fine-tuning pipeline.
Public pattern sources contribute narrowly extracted stitch/round facts to deterministic
reference tests; this does not make unlicensed web images eligible for G3.

## Delivered capabilities

- Local photo analysis, human review, manual input, and 2D grid entry points.
- Subject segmentation, profiles, palettes, optional pose landmarks, and versioned geometry.
- Gauge-driven round generation, six-section shaping, bridge logic, and deterministic gates.
- Materials, base time, assembly, ring charts, Markdown/PDF, history, and share links.
- Authorized-photo evaluation, physical-trial analysis, and non-calibrating external evidence.

## Remaining product boundaries

- One image cannot reliably recover the back, depth, hidden attachments, or absolute scale.
- Local vision may degrade on seated, occluded, close-up, multi-person, or low-contrast inputs.
- Yarn weight and time constants lack local independent calibration.
- Multi-view fusion, cross-device history, full internationalization, and GPU 3D
  reconstruction are not delivered.

## Reproduction commands

```bash
uv sync --locked --extra dev
uv run --locked --extra dev ruff check .
uv run --locked --extra dev pytest -q --cov=app --cov-report=term-missing
uv lock --check
uv build --wheel --out-dir dist/
# The declared Streamlit floor must really install and run (CI: the streamlit-floor job)
uv venv --python 3.12 /tmp/floor && uv pip install --python /tmp/floor/bin/python "streamlit==1.66.1" -e ".[dev]"
/tmp/floor/bin/python -m pytest -q tests/test_app_smoke.py tests/test_dependency_floor.py
uv run crochet2pattern-trials external-report --curated
git status --short
```

This page records current conclusions, evidence bindings, and gates; routine changes belong
in the changelog. Update this page when release evidence, support, or a gate changes.
