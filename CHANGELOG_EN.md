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
