# System Status and Release Gates

[简体中文](system-status.zh-CN.md) | **English** | [Documentation index](README.md)

> Authoritative snapshot: 2026-10-02. Current behavior is defined by source code,
> `pyproject.toml`, `uv.lock`, and reproducible checks. Audit briefs are historical snapshots.

## Current conclusion

CrochetPhoto2Pattern is a **0.2.0-beta.2 engineering candidate**. Stitch arithmetic, input
gates, exports, and packaging have substantial automated coverage. An authorized
real-photo baseline and an independent physical-trial baseline are still missing, so the
project must not claim validated dimensions, material usage, time, or finished-item crochetability.

## Latest verification

> New in 0.2.0-beta.2: CrochetPARADE DSL export (`--parade` / result page) with the second-tier executable-correctness metric `parade_export_rate`, a structure-v2 3D preview, core-contract JSON Schemas (docs/schemas/) and a grid dithering option.

The current pre-PR checkout passes the complete local suite, Ruff, mypy, and diff checks.
The table below remains the latest published multi-Python/extras snapshot and is tied to its
named commit; the new branch must repeat the protected checks before merge.

Local review through 2026-10-04 (Python 3.12.13): after input/export, gauge/structure,
shared photo observation, model-cache, edited-count, assembly-connection, physical-input,
preview-rotation fixes, two follow-up review rounds (rounds 6-7: assembly prose,
pose-download backoff, resource bounds, provenance hardening, trials CLI decoding,
evaluation re-hashing), and an external-audit round (round 8: crochet_params split
into parts/materials/assembly/time_estimate/onepiece with zero behavior change,
Lab-conversion allocation fix, closing-note variants, history/preview hardening,
digest-pinned base image), the full suite reports **1079 passed, 1 skipped in 23.45s**.
Ruff, mypy app tests (96 files), schema-document synchronization, and `git diff --check` pass.
In a synthetic comparison, shared segmentation reduced median pipeline time from
0.1074s to 0.0543s; this does not establish real-photo quality.
The skipped test requires `CROCHET_EVAL_DIR`.
These changes are committed on the local main branch but have not run through the remote
matrix and do not replace
the commit-bound evidence below. See the [review record (Chinese)](optimization-review-20260907.md).

| Check | Result | Notes |
|---|---|---|
| Core | 739 passed, 1 skipped | remote Python 3.11–3.14 matrix; missing optional/runtime data skips by design |
| PDF extra | 741 passed, 1 skipped | Python 3.11; PDF tests execute, pose smoke and authorized photos skip by design |
| Pose extra | 738 passed, 2 skipped | Python 3.11; MediaPipe 1.0.1, EGL/GLESv2, and the real `mp.Image` bridge pass |
| Coverage | 89.9% | clean core environment; threshold is 80% |
| Static checks | Passed | `ruff check .` and `git diff --check` |
| Lock | Passed | `uv lock --check` |
| Dependency audit | Passed | combined environment has no known finding; GitHub marks the Protobuf high alert fixed |
| Wheel | Passed | metadata, MIT license, three CLIs, prompts, and curated evidence included |

Commit `bb24995` passed the real Python matrix
([run 33364513189](https://github.com/paulkooer/CrochetPhoto2Pattern/actions/runs/33364513189)),
PDF/pose extras
([run 33364513168](https://github.com/paulkooer/CrochetPhoto2Pattern/actions/runs/33364513168)),
and locked dependency audit
([run 33364673171](https://github.com/paulkooer/CrochetPhoto2Pattern/actions/runs/33364673171)).

## Release gates

| Gate | Status | Pass condition |
|---|---|---|
| G1 Reproducible source | **Passed** | reviewed commit, version, lock, changelog, and remote `main` agree |
| G2 Supported-version automation | **Passed** | core 3.11–3.14, PDF/pose, and security audit are green |
| G3 Authorized-photo baseline | **Blocked** | at least 30 stratified schema-v2 cases with per-image rights/subject evidence, passing all `evaluation.en.md` thresholds including 100% Parade export |
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
