# Changelog

[简体中文](CHANGELOG.md) | **English**

This project follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
[Semantic Versioning](https://semver.org/). Backup, structure, and editable-project
formats may still evolve during Beta; incompatible changes must include migration notes.

## Unreleased

### Added

- **Reference-pattern verification tests** (`tests/test_reference_patterns.py`,
  24 items): external calibration against professional/community patterns —
  Clover's official AKIHIRO doll (22-st legs / 16-st arms / 9-st tail /
  14-st ears), the community sphere formula (6-sc ring start, +6 per round),
  the Lovable Loops cherry mini C2C chart (9x9, full written block rows),
  Spin a Yarn Crochet's 8-stitch ring start (8->16->24 doubling), a
  sin-profile property verification of Ms Premise-Conclusion's "The Ideal
  Crochet Sphere" (per-row comparison against independently recomputed
  N=C/s values) including its craft-warning handling, Craft Yarn Council
  abbreviation alignment (sc2tog), DROPS Design Children 23-60 apple toy
  (Garnstudio professional pattern: 7-st ring start, +7 increase rounds,
  9 plain rounds, symmetric decreases to 6, 4-st chain-start stem; its
  R17 errata history — a decrease once misprinted as an increase in 2012 —
  forms the first "published errata" fixture), StringyDingDing's kangaroo +
  joey (a plain round right after the ring, one-piece asymmetric shaping
  with odd 21/15-stitch rounds, a 4-increase ear round; the mamma leg R5
  increase-instruction-vs-(24)-count contradiction is the second), and
  Supergurumi's "The Chubby Bee" (a German professional design studio:
  55-round one-piece body peaking at 66 stitches, per-round yellow/black
  stripe color changes, BLO ridge rounds, "1 single crochet" spiral shift
  rounds, staggered shaping repeats, and an odd-count 3-decrease tail
  sequence 33->...->9->6; all 55 rounds mechanically verified, fully
  passing the validator and translating to CrochetPARADE including COLOR
  stripe directives).
- **Difficulty labels aligned with CYC Project Levels** (`app/schemas.py`):
  the official four levels Basic/Easy/Intermediate/Complex (fetched and
  quoted verbatim 2026-09) map onto our easy/medium/hard — the generator
  only produces single-crochet toys, so CYC's Complex (multiple techniques
  simultaneously) has no counterpart by design. The result-page metric,
  the manual-tab slider, and the Markdown/PDF exports all switch from raw
  English enum values to CYC-aligned labels (unknown legacy values fall
  back to verbatim display).
- **CYC yarn-weight category mapping** (`Gauge.cyc_label`): maps stitch
  density onto the Craft Yarn Council Standard Yarn Weight System (official
  "single crochet per 4 inch" categories, fetched and cross-checked 2026-09)
  and reports each category's standard hook range; the materials list shows
  the amigurumi-tight hook advice next to the CYC standard category. The
  scope is explicit: this is a "density -> category" mapping, not a
  "yarn -> category" one (tight-gauge amigurumi can reach the same density
  with a thicker yarn). Cross-validation: DROPS Children 23-60
  (18 sc/10 cm, 4.5 mm hook) lands exactly on CYC #2 fine, with 4.5 mm at
  the top of that category's official 3.5-4.5 mm hook range.
- **C2C starting convention**: the grid export's written C2C rows now state
  the standard block construction (ch 6, dc beginning in the 4th ch from
  hook, 3 dcs total, turn) — identical across two independent tutorial
  sources (Craftematics and Crochet.com).
- **"Stitch notation" column in the rounds table** (Markdown export):
  aggregate counts (+6/-6) are now also rendered in the legend's X/V/A
  repeat notation (e.g. (4X,V)x6), matching how professional patterns
  write "[4 sc, 1 inc] repeat" (Supergurumi, DROPS). Non-uniform rounds,
  single-increment rounds, inconsistent aggregates, or JSON-corrupted
  rows degrade to a dash.
- **CrochetPARADE color-stream cleanup**: consecutive same-color rounds
  no longer repeat the COLOR directive (striped pieces drop from one
  directive per round to one per stripe boundary, bee 23->6), and each
  quantity copy resets to the part color instead of inheriting the
  previous copy's ending color.
- **Finest-gauge yarn meterage recalibrated to cotton** (fine bucket
  320->250 m/100g): anchored on Schachenmayr Catania used by the bee
  pattern (100% cotton, 125 m/50 g, labeled Sport/Fine(2), 2.5 mm hook) —
  exactly the bucket's "2.0-2.5 mm + fine cotton" configuration; the old
  320 was a wool-sport figure ~28% high. The other three buckets await
  physical-trial (G4) calibration; purchase per actual yarn label.
- **Safety-eye size now scales with head diameter** (`_safety_eye_mm`,
  materials list): the old fixed "8 mm" ignored doll size — an 8 mm pair
  is clearly off on a 16 cm head. The new ladder aligns with the
  r/Amigurumi eyes wiki community ranges (mini 5-6 mm / regular 8-12 mm /
  large 14-20 mm+, fetched 2026-09); professional anchors: ~10 cm heads
  with 12 mm eyes (Supergurumi bee 32 cm and StringyDingDing kangaroo
  23 cm both use 12 mm). The default 9 cm head moves 8 -> 10 mm; legacy
  results without a head diameter fall back to 8 mm.
- **Ring-start alternative in the export preamble**: two common
  substitutes for crocheters struggling with the magic ring — chain 4,
  sl st into a ring (Supergurumi's written form) and chain 2, work the
  first round into the 2nd ch (community standard, Hobbii's "Easy
  Alternative to the Magic Ring").
- **Cross-language verification from the Russian tradition**
  (kruchcom.ru teddy finger puppet, verbatim): КА (amigurumi ring)
  6-stitch start, 6 ПРИБ (increases), plain 24-st rounds — the same
  community standard in another language; the same site's big teddy head
  uses ВПП (lifting chain) joined rounds, whose aggregate counts are
  identical to spiral work, so the validator needs no distinction.
- **Opening stitch counts flow into the assembly text** (`build_assembly`
  gains an `openings` parameter): professional assembly sections state
  the opening size before sewing ("sew the remaining 12 sts"). Limb
  steps now read "sew ... (opening: N sts)" with N = the part's last
  round; hat brims and skirt waists report their exact stitch counts;
  the fully cinched sphere head honestly reports none. Recomputed by
  refresh_derived after JSON edits; callers without the parameter keep
  the previous wording.
- **Closing technique upgraded to the seamless close**: the final-round
  note on spheres/eggs/one-piece bodies changes from the plain "cinch
  tight" to the community-standard technique — "thread the tail through
  the front loops of every remaining stitch and pull tight" (Chinese
  community term 无痕收口, seen on Bianzhirensheng; English counterpart
  is PlanetJune's Fastening Off front-loops method). Reachability of CN
  sources is documented too: Xiaohongshu requires login and hosts
  image-based charts; Bianzhirensheng's full text sits behind its share
  platform (persistent 502/500) with image charts on the main site —
  text-level calibration sources essentially don't exist in fetchable
  form in the CN community, which is exactly the gap a photo->pattern
  system fills there.

### Fixed

- **Validator domain confusion (found by the calibration, two instances)**:
  real patterns contain 22/16/9/14-stitch rounds that are perfectly
  crochetable, and professional designers' 8->16 doubling rounds (one
  increase per stitch, always executable) were rejected by the +-6 smooth-
  shaping cap. Both downgrade to `notes` — executability is guaranteed by
  inc<=prev / dec<=prev/2 (kept as hard checks); six-section topology and
  smooth-shaping cadence are generator priors, not crochetability
  requirements. The result page shows notes as info captions.
- **Grid pipeline externally verified**: the cherry chart (white 57 / red 18 /
  green 6) maps through nearest sampling with each cluster landing on a
  single yarn color, cluster sizes exactly matching the published chart.

## 0.2.0-beta.2 - 2026-09-05

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
