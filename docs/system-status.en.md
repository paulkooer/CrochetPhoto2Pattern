# System Status and Release Gates

[简体中文](system-status.md) | **English** | [Documentation index](README.md)

> Authoritative snapshot: 2026-08-31. Current behavior is defined by source code,
> `pyproject.toml`, `uv.lock`, and reproducible checks. Audit briefs are historical snapshots.

## Current conclusion

CrochetPhoto2Pattern is a **0.2.0b1 engineering candidate**. Stitch arithmetic, input
gates, exports, and packaging have substantial automated coverage. An authorized
real-photo baseline and an independent physical-trial baseline are still missing, so the
project must not claim validated dimensions, material usage, time, or finished-item crochetability.

## Latest verification

| Check | Result | Notes |
|---|---|---|
| Core | 704 passed, 6 skipped | remote Python 3.11–3.14 matrix; missing optional/runtime data skips by design |
| PDF extra | 708 passed, 2 skipped | Python 3.11; PDF tests execute, pose smoke and authorized photos skip by design |
| Pose extra | 705 passed, 5 skipped | Python 3.11; MediaPipe 1.0.1, EGL/GLESv2, and the real `mp.Image` bridge pass |
| Coverage | 88.02% | clean core environment; threshold is 80% |
| Static checks | Passed | `ruff check .` and `git diff --check` |
| Lock | Passed | `uv lock --check` |
| Dependency audit | Passed | combined environment has no known finding; GitHub marks the Protobuf high alert fixed |
| Wheel | Passed | metadata, MIT license, three CLIs, prompts, and curated evidence included |

Commit `f8af7df` passed the real Python matrix
([run 33362301107](https://github.com/paulkooer/CrochetPhoto2Pattern/actions/runs/33362301107)),
PDF/pose extras
([run 33362301109](https://github.com/paulkooer/CrochetPhoto2Pattern/actions/runs/33362301109)),
and locked dependency audit
([run 33361428729](https://github.com/paulkooer/CrochetPhoto2Pattern/actions/runs/33361428729)).

## Release gates

| Gate | Status | Pass condition |
|---|---|---|
| G1 Reproducible source | **Passed** | reviewed commit, version, lock, changelog, and remote `main` agree |
| G2 Supported-version automation | **Passed** | core 3.11–3.14, PDF/pose, and security audit are green |
| G3 Authorized-photo baseline | **Blocked** | at least 30 stratified cases passing `evaluation.en.md` thresholds |
| G4 Physical-trial baseline | **Blocked** | isolated calibration and holdout pattern hashes pass `physical-trials.en.md` rules |
| G5 Distribution package | **Locally passed** | wheel content, metadata, CLIs, and package data validated |
| G6 Product claims | **Beta-compliant** | UI/docs/exports retain single-photo, template, estimate, and trial boundaries |

Do not create a formal release tag until G1–G4 pass. Synthetic inputs, web articles,
published yarn estimates, and more unit tests cannot substitute for authorized photos or
independent physical samples.

## Delivered capabilities

- Photo, local vision, LLM, manual, and 2D grid entry points.
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
uv run crochet2pattern-trials external-report --curated
git status --short
```
