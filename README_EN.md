# 🧶 CrochetPhoto2Pattern

[简体中文](README.md) | **English**

[![CI](https://github.com/paulkooer/CrochetPhoto2Pattern/actions/workflows/ci.yml/badge.svg)](https://github.com/paulkooer/CrochetPhoto2Pattern/actions/workflows/ci.yml) [![Version: 0.2.0 beta 1](https://img.shields.io/badge/version-0.2.0--beta.1-orange.svg)](CHANGELOG_EN.md) [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> An AI-assisted amigurumi pattern generator that turns a single photo into a complete crochet draft.

> **Release status: Beta.** Automated checks prove only that a pattern satisfies the
> current stitch arithmetic and shaping rules. They do not replace gauge swatches or
> physical test crochets. Verify dimensions, tension, and assembly before publishing a
> generated pattern. See [System Status and Release Gates](docs/system-status.en.md).

## Project scope and evidence levels

The project aims to generate reviewable patterns, not to present model output as a
finished, validated product. Its evidence is split into three non-interchangeable levels:

1. **Structural correctness (covered):** round-by-round stitch counts, increase/decrease
   topology, input boundaries, exports, and packages are checked automatically.
2. **Photo generalization (not established):** this requires a stratified, authorized
   real-photo dataset; synthetic images are not a substitute.
3. **Physical crochetability (not established):** this requires separate calibration and
   holdout trials measuring size, yarn consumption, and active time.

Generated results are design drafts and starting points for test crocheting. Until levels
2 and 3 are complete, size, material usage, and physical crochetability must not be
described as validated outcomes.

## Features

- Photo upload, plus manual and 2D grid workflows.
- Free local-vision fallback: face-based proportion estimation and silhouette analysis
  without an LLM API key.
- GrabCut subject segmentation for body-focused palette and profile extraction.
- Optional pose landmarks on Python 3.11–3.12 for shoulder/hip/knee measurement; Linux
  also requires EGL/GLESv2 and safely falls back when the native runtime is unavailable.
- Photo-derived yarn palettes, longitudinal color bands, and CIEDE2000 color matching.
- OpenAI and Anthropic vision providers with structured validation and safe fallback.
- Versioned template geometry with part instances, mirrored pairs, rotations, attachment
  anchors, and explicit inference confidence. This is not full 3D reconstruction.
- Gauge-aware, round-by-round stitch generation with executable six-section shaping.
- Correct multiplicity accounting for paired arms, legs, and ears across stitches,
  materials, time estimates, exports, and progress.
- Strictly validated advanced structure editing without another AI call.
- Editable 2D grid projects for tapestry, C2C, and cross-stitch workflows.
- Stitch-arithmetic validation, ring charts, progress tracking, per-color bills of
  materials, share links, SQLite history, JSON backup, Markdown, and optional PDF export.
- EXIF orientation correction and defensive image/input size limits.
- Authorized-photo evaluation and independent physical-trial tooling.

## Technology

- Python 3.11–3.14
- Streamlit
- OpenAI / Anthropic APIs (optional)
- Pydantic v2
- OpenCV / Pillow / NumPy

## Quick start

### Install

```bash
git clone https://github.com/paulkooer/CrochetPhoto2Pattern.git
cd CrochetPhoto2Pattern
uv sync --locked
# Alternative: python -m pip install -e .
```

### Configure

Copy `.env.example` to `.env` and add an API key if you want cloud vision:

```bash
cp .env.example .env
# Edit .env and set OPENAI_API_KEY or ANTHROPIC_API_KEY
```

Key precedence is **sidebar input > `.env`**. Clearing the sidebar field does not disable
an `.env` key; the provider may still be called and billed. With no key in either place,
the Photo tab uses local vision or mock mode.

For a third-party API relay, enter your own key and matching Base URL together in the
sidebar. Deployments may pair `OPENAI_API_KEY` with `OPENAI_BASE_URL`, or
`ANTHROPIC_API_KEY` with `ANTHROPIC_BASE_URL`. Sources are never mixed, so a server key is
not sent to a user-controlled endpoint. Models can be overridden with
`OPENAI_VISION_MODEL` and `ANTHROPIC_VISION_MODEL`.

> A photo has no reliable absolute scale. The target height in centimetres always comes
> from the user. Shared deployments should also restrict outbound traffic at the network
> layer; application URL checks cannot fully prevent DNS rebinding.

### Data and privacy

- Local vision, manual input, and grid mode do not send photos to an LLM provider.
- OpenAI/Anthropic vision mode sends the selected photo to that provider. A custom Base
  URL sends it to that third party. Use only images you are authorized to process.
- Pattern history is stored in a local SQLite database. Share links embed compressed
  pattern data in the URL and should not contain sensitive material.
- `.env`, authorized evaluation photos, evaluation outputs, and physical-trial records
  are ignored by Git by default. Always review staged files for credentials, private
  photos, and personal information.

### Run the UI

```bash
uv run streamlit run app/main.py
```

### Headless CLI

```bash
uv run crochet2pattern --image photo.jpg --gauge dk --out pattern.json --md pattern.md
uv run crochet2pattern --head 9 --height 18 --parts 头部,身体 --sphere-mode egg --out p.json
uv run crochet2pattern --mock --out demo.json
uv run crochet2pattern --batch-dir photos/ --out-dir patterns/
```

Canonical part values in the current schema are Chinese (`头部`, `身体`, and so on), so
the manual CLI example intentionally retains them. AI mode reads provider keys from the
environment; without a key it falls back to local vision. A pattern that violates stitch
arithmetic or the active gauge's shaping limit exits with code `2`.

### Optional extras

```bash
python -m pip install -e '.[pdf]'   # PDF export
python -m pip install -e '.[pose]'  # pose landmarks; Python 3.11–3.12 only
```

On Linux, install the packages that provide `libEGL.so.1` and `libGLESv2.so.2` (for
example `libegl1` and `libgles2` on Ubuntu) before using pose landmarks. The application
falls back to template spans when either native library is unavailable.

### Docker

```bash
docker build -t crochet-photo2pattern .
docker run -p 8501:8501 -e ANTHROPIC_API_KEY=your-placeholder crochet-photo2pattern
```

### Tests

```bash
uv sync --locked --extra dev
uv run --locked --extra dev ruff check .
uv run --locked --extra dev pytest tests/ -v
```

GitHub Actions runs the locked core suite on Python 3.11, 3.12, 3.13, and 3.14, plus
separate PDF, pose, wheel, coverage, and dependency-security checks.

## Authorized real-photo evaluation

The evaluation command records usage rights, purpose approval, SHA-256, and scene tags.
It runs only local vision and does not send evaluation photos to an LLM provider:

```bash
uv run crochet2pattern-eval --dataset eval_data/release-01 \
  --out eval_outputs/release-01.json
```

See the [Authorized Real-Photo Evaluation Protocol](docs/evaluation.en.md). Evaluation
photos and reports are ignored by Git, and passing software metrics still does not prove
physical crochetability.

## Physical-trial loop

Create a trial record tied to the exact pattern SHA-256, record actual gauge, dimensions,
yarn, and active time, then generate conservative calibration candidates:

```bash
uv run crochet2pattern-trials init --pattern pattern.json \
  --trial-id classic-001 --maker-id maker-a --cohort calibration \
  --out trial_data/classic-001.trial.json
uv run crochet2pattern-trials analyze --records trial_data \
  --out trial_outputs/baseline.json
```

Curated external evidence can be attached only as non-calibrating context:

```bash
uv run crochet2pattern-trials external-report --curated \
  --out trial_outputs/external-context.json
```

See [Physical Trial Records and Calibration](docs/physical-trials.en.md).

## Processing flow

```text
photo → geometric/semantic observations → user target size → part structure
      → crochet parameters → deterministic validation → user corrections/exports
```

See [Processing Flow](docs/flow.en.md).

## Repository layout

```text
CrochetPhoto2Pattern/
├── app/
│   ├── main.py              # Streamlit entry point
│   ├── cli.py               # headless pattern generator
│   ├── evaluation.py        # authorized-photo evaluation
│   ├── trials.py            # physical-trial records and analysis
│   ├── schemas.py           # Pydantic contracts
│   ├── models/              # vision, geometry, sizing, pattern generation, validation
│   ├── ui/                  # Streamlit tabs and renderers
│   ├── utils/               # image loading, history, and exporters
│   ├── prompts/             # packaged LLM prompts
│   └── data/                # curated, non-calibrating external evidence
├── tests/
├── docs/
├── pyproject.toml
└── uv.lock
```

## Current limitations

- A single photo cannot reliably recover the back, depth, hidden attachments, or absolute scale.
- Template geometry is explicit but inferred; it is not a measured 3D mesh.
- Local vision can degrade on seated, occluded, close-up, multi-person, or low-contrast images.
- Yarn weight and time constants do not yet have a local independent physical-trial baseline.
- Multi-view fusion, cross-device history, full internationalization, and GPU 3D
  reconstruction are not implemented.

## Documentation

The bilingual documentation index is at [docs/README.md](docs/README.md). Historical audit
snapshots remain in their original Chinese because they are immutable records of earlier
review rounds, not current operating instructions.

## License and contributing

[MIT](LICENSE). Read the [Contributing Guide](CONTRIBUTING_EN.md) before opening a pull
request. Report security issues privately according to the [Security Policy](SECURITY_EN.md).
