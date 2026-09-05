# Changelog

[简体中文](CHANGELOG.md) | **English**

This project follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
[Semantic Versioning](https://semver.org/). Backup, structure, and editable-project
formats may still evolve during Beta; incompatible changes must include migration notes.

## Unreleased

### Added

- Versioned real-photo evaluation protocol covering rights, retention, SHA-256, scene
  tags, aggregate gates, and JSON reports.
- `crochet2pattern-eval`, which evaluates only the local-vision path.
- `crochet2pattern-trials`, with pattern hashes, measured gauge/size/yarn/time, conservative
  calibration candidates, and separate calibration/holdout cohorts.
- Curated external trial evidence packaged with the wheel and prohibited from automatic calibration.
- MIT license, contribution/security/conduct policies, structured issue forms, and a PR template.
- Full English entry points for user, contributor, security, evidence, and status documentation.

### Changed

- English is now the default GitHub and package landing page; complete Chinese docs remain
  at `README_ZH.md` and `docs/system-status.zh-CN.md`, with compatibility redirects for old links.
- README now separates structural correctness, photo generalization, and physical crochetability.
- Secret checks cover staged untracked files and common GitHub, AWS, and private-key patterns.
- Core tests no longer rely on the optional PDF extra; Streamlit tests use stable absolute paths.
- Weekly and lock-change dependency auditing now tests the environment installed from `uv.lock`.
- CI forces each declared interpreter through `UV_PYTHON`, preventing a false matrix that
  silently reused the local default.
- GitHub Actions use `checkout@v7` and `setup-python@v7`.
- Pose is limited to Python 3.11–3.12 and upgraded to MediaPipe 1.0.1, removing the old
  vulnerable `protobuf<5` constraint. Every core environment uses Protobuf 6+; Python
  3.13+ also uses NumPy 2.x.
- Dependency security installs and audits core, PDF, and pose extras together.
- Linux pose checks for EGL/GLESv2 before constructing MediaPipe objects and safely
  falls back when missing; extras CI installs the runtime and exercises the real image bridge.

### Fixed

- On shared deployments a user's API key can no longer be silently captured by the
  server's `OPENAI_BASE_URL` / `ANTHROPIC_BASE_URL`: a user key without a custom base
  URL is now explicitly paired with the official default endpoint (the SDK no longer
  falls back to reading those environment variables).
- Upload resource limits now bite: `.streamlit/config.toml` sets
  `server.maxUploadSize = 20`, decoded images are immediately downsampled to 2048px
  before white-compositing and caching, and JPEGs use proportional `draft()` decoding.
  The measured +650MB decode/composite peak for a legal 39.7MP PNG is gone, and the
  result page no longer transfers full-resolution frames on every rerun.
- Honest Mock labeling: UI, CLI, and `vision_meta` now say "body and parts are fixed
  demo values, colors and spans come from the photo" (the old "unrelated to the photo"
  wording contradicted actual behavior).
- Vision mode is an explicit three-state `vision_mode` (ai / local / mock): the library
  no longer infers it from "is a key present", Mock never calls any API regardless of
  keys, and `.env.example` placeholder keys (`sk-your-key-here`) no longer count as
  configured.
- Model-controlled free text (main features, identified parts, assembly instructions,
  materials fallback lines) renders as plain text or escaped output, so in-image text
  injection can no longer reach the page through Markdown link/image syntax.
- SQLite history connections are closed via `contextlib.closing` (removes the
  Python 3.13+ ResourceWarning) and schema creation/migration runs once per file.

### Changed

- New `PatternResult` pydantic model as the single contract for the result dict:
  all six hand-written literals (orchestrator, both CLI branches, manual input, quick
  resize, backup import) now converge on it; backups and share tokens carry a
  `schema_version`, and share decoding rejects future versions.
- Vision structured outputs now use a dedicated `VisionOutput` contract (separate
  from the internal `ImageAnalysis`): enum fields are `Literal`-constrained, the
  model no longer receives `recommended_colors` (which it must never fill), and the
  schema directly requests `head_to_height_ratio` instead of the indirect "fixed
  18.0 canvas" conversion. Legacy centimetre-shaped prompts are tolerated only in
  the schema-less fallback path.
- New `PartKind` `StrEnum` plus Chinese/English label tables: the English domain key
  (= structure-v2 part_id) and the canonical Chinese names now derive from a single
  source, preparing the i18n migration; `PART_NAMES` values are unchanged.
- CI gains a `type-check` job: `mypy` joins the dev extra with a zero-error baseline
  across all 37 app files (see `[tool.mypy]`) to prevent type regressions.
- The three local result-page flows (quick resize / structure edit / backup import)
  move out of button callbacks into a pure-function layer (`app/ui/result_logic.py`)
  that is unit-testable offline; the per-round progress section is now an
  `st.fragment`, so ticking a round no longer reruns the whole page.
- Product display name unified to `CrochetPhoto2Pattern`: a single
  `app.PRODUCT_NAME` source now feeds the page title, hero, footer, and
  Markdown/PDF exports (the UI previously said Photo2Amigurumi while the
  repo and package say CrochetPhoto2Pattern).

### Security

- Second review pass closes the remaining cross-user injection surfaces: share
  tokens / backup imports carry other people's content, and three spots in
  `params` still rendered Markdown (part `notes` via `st.info`, the
  shape/color line via `st.write`, validator issues via `st.warning`). They now
  go through `md_safe` (strip zero-width/BiDi, backslash-escape `[]` to kill
  link/image syntax, HTML-escape), as do spans_measured, sizing/vision_meta
  notes and all exception interpolations.
- Backup import gains a 2MB paste-size gate (aligned with the share token's
  2MB decompression cap).

### Added

- **CrochetPARADE DSL exporter** (P1 from the external对标 review): translate
  round-by-round patterns into the crochetparade.org text grammar (`ring`,
  `scNinc`, `N[sc,sc2inc]`, `start_anew`, `COLOR:` — a verified subset checked
  against the official manual and examples). Available via CLI `--parade` and
  the result page, with emitter-level syntax lint. Users paste it into their
  locally-run web app for independent 3D rendering, stitch-tension analysis and
  Blender-importable models — a verification layer beyond our algebra gate.
  License boundary: text output only, no GPLv3 code pulled in.
- Evaluation protocol gains a second-tier executable-correctness metric
  `parade_export_rate` (CrochetBench methodology), reported alongside
  `pattern_valid_rate`.
- Structure v2 -> 3D preview (`app/ui/preview3d.py`): a self-contained canvas
  software renderer (triangle faces, painter's algorithm, Lambert shading, no
  external CDN); instance positions/rotations and part sizes/colors render
  directly, drag to rotate, wheel to zoom; cylinder radii derive from stitch
  counts and gauge, profile parts lathe per round (same math as the ring chart).
- `docs/schemas/` publishes JSON Schemas for the core contracts (PatternResult,
  StructureGeometry, ImageAnalysis, CrochetPart) with a drift test — following
  the open-intermediate-format playbook of Knitout.
- Grid tab gains an optional Floyd–Steinberg dithering toggle (keeps gradients
  under small palettes; default off), matching common photo-to-grid tools.

### Fixed

- `st.components.v1.html` passed Streamlit's deprecation deadline (2026-06-01);
  the four SVG renders (ring chart, symbol strip, silhouette verification, grid
  canvas) migrate to `st.html`, with fixed height and scrolling provided by an
  `html_box` wrapper inside the content (st.html has no height/scrolling).
- Dependabot ecosystem switched from `pip` to `uv` (officially supported since
  2025-12); the pip ecosystem has a known "updates pyproject without
  regenerating uv.lock" failure mode for uv projects.
- History SQLite first-connect DDL is now lock-guarded across Streamlit session
  threads, and `commit` no longer sits inside a `suppress` block (a fully
  migrated database — where every ALTER fails — still commits and marks the
  file initialized; regression test included).
- History blobs carry `schema_version` and the loader rejects future versions
  (legacy blobs without a version keep loading).
- Share tokens are generated on demand (button click, cached in session
  state) instead of re-compressing the whole result on every rerun.

### Changed

- `py.typed` ships in the wheel (library consumers get type hints); the CI
  wheel check asserts it.
- mypy enables `check_untyped_defs` (zero errors across app); tests/ use a
  documented override checking only module top level and call signatures —
  tests deliberately poke internals with dicts and fake SDKs.
- CI gains a `docker` job (build only, no push, GHA-cached) to keep the
  Dockerfile and dependency graph honest.
- `params["parts"]` is uniformly dict-shaped in memory (matching disk/share/history):
  the dict/model dual-state branches in `_part_name`, `_part_rounds`,
  `_part_quantity`, `_round_stitches`, the validator, exporters, PDF export, and the
  ring chart are all removed; CrochetPart/CrochetStitch remain validation-only.
- Vision SDK timeout budget tightened from 60s×3 retries to 40s×1 (worst case across
  both providers ≈2.7 minutes instead of ~8); `openai` gains an upper bound `<4` and
  `anthropic` `<1` (1.x is a breaking httpx2-based upgrade).
- Dockerfile rebuilt as a multi-stage build: dependencies installed exactly from
  `uv.lock` (no more live resolution via `pip install .`), cached dependency layers,
  non-root user, and a built-in `/_stcore/health` HEALTHCHECK.
- All three CI workflows migrate to `astral-sh/setup-uv@v7` with caching enabled
  (`setup-python`'s pip cache never helped uv-managed environments); Dependabot added
  for pip and GitHub Actions; ruff now enforces the UP/SIM rule sets with all existing
  findings cleaned up.
- Historical review snapshots (audit-brief*, handoff-review, optimization-brief,
  audits) moved to `docs/archive/`; round-numbered test files renamed by coverage
  (test_round12/14/15 → test_validator_c2c_materials / test_exports_share_cli /
  test_export_disclaimers_history).
- Test history databases use per-case `tmp_path`, so parallel/multi-user runs no
  longer share a fixed `/tmp` path.

### Planned

- Collect an authorized real-photo baseline and an independent physical-trial baseline.
- Split the largest parameter-generation, result-rendering, grid, and provider-adapter modules.
- Publish the first Beta tag only after the G3 and G4 evidence gates pass.

## 0.2.0-beta.1 - 2026-08-30

### Added

- Provider-independent single-image observations, user target-size transforms, and
  StructureGeometry v2.
- Part instances, mirrored quantities, attachment anchors, assembly plans, and multiplicity-aware totals.
- Gauge-driven shaping limits, round arithmetic, six-section topology, and V/A executability checks.
- Profile shaping, ideal sphere/egg heads, one-piece head/body, and advanced structure correction.
- Pre-generation crop, grid editing, undo/redo, editable project JSON, and complete Markdown export.
- CLI, SQLite history, share links, PDF export, ring charts, and versioned backup validation.

### Changed

- Minimum Python is 3.11; CI covers Python 3.11–3.14.
- Yarn matching uses a real palette and CIEDE2000; imported grids must use trusted color names/RGB.
- Beta, single-image, estimate, and physical-test boundaries are explicit.

### Security

- Uploaded images, share payloads, backups, structure JSON, and grid projects have size and schema gates.
- API key/relay sources are isolated, exceptions are redacted, and tracked files are scanned for secrets.
