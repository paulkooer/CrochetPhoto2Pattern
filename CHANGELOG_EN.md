# Changelog

[简体中文](CHANGELOG.md) | **English**

This project follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
[Semantic Versioning](https://semver.org/). Backup, structure, and editable-project
formats may still evolve during Beta; incompatible changes must include migration notes.

## Unreleased

### Fixed

- **`st.html` sanitizer strips SVG and scripts (found by in-browser
  inspection, two fixes)**: Streamlit 1.60 sanitizes `st.html` with
  DOMPurify — the **entire `<svg>` element is removed** (the hero ring
  mark vanished and the lead text collapsed into the 88px mark column;
  ring charts, symbol strips and silhouettes on the result page were
  blank), and `<script>` is stripped even with
  `unsafe_allow_javascript=True` (the 3D preview never drew, and the old
  canvas's fixed focal length rendered an 18 cm doll at ~44 px — two
  latent defects that sat undiscovered while the "visual check of
  st.html graphics" item stayed open). Fixes: 1) all static SVG content
  (hero, ring chart, symbol strip, silhouette, grid legend) now renders
  via `st.markdown unsafe_allow_html` (no sanitizer; block-level inline
  SVG without blank lines bypasses markdown re-flow); 2) the 3D preview
  is rewritten as a **server-side static isometric SVG** (painter's
  algorithm + back-face culling + Lambert shading, 276 front polygons)
  with height-normalized scaling (fixes the tiny-figure defect) sharing
  the design tokens — at the cost of drag rotation, since no script
  channel remains; 3) the deprecated components.v1.html iframe is no
  longer depended on. Pixel-level browser inspection passes: theme,
  hero, pattern-sheet rows, check progress, materials (CYC label,
  10 mm eyes) and assembly (openings + flat-seam hint) all render
  correctly.

### Changed

- **Visual redesign: the pattern sheet (图解纸)**. The app's look moves
  from a generic warm-craft theme to a printed pattern sheet: cool paper,
  navy ink, and a single stitch-marker yellow reserved for "where you
  are / what you have done" (active tab, chosen option, checked rounds,
  progress); yarn colours stay the only other colour on the page. A new
  leaf token module `app/theme.py` is the single colour source for
  `.streamlit/config.toml`, the injected CSS, and every SVG/canvas
  renderer (ring chart, symbol strip, silhouette, grid, 3D preview) —
  leaf means no Streamlit import, avoiding a models→ui cycle;
  `tests/test_theme_tokens.py` keeps the four surfaces in sync and guards
  against legacy-palette regressions. The result page is re-laid-out as
  numbered sections 1–5: each part's rounds render as pattern-sheet rows
  (serif rows, a marker-yellow sweep on check), round labels pass
  notes/colour through md_safe before Markdown rendering (same
  injection defence), and yarn chips get ruled-border styling. The hero
  is a one-shot draw animation of the first six rounds of a +6 sphere
  (equal rings — r grows linearly; st.html's sanitizer strips the
  pathLength attribute, so inline dash values are used instead), fully
  degraded under prefers-reduced-motion. No web fonts (offline/privacy
  stance; Google Fonts unreliable in the mainland): system sans for
  body, Charter/Palatino falling through to Songti for headings, lining
  tabular digits. Print styles hide app chrome and output a clean
  black-on-white sheet. Contrast: body ≈14:1, secondary 5.3:1, control
  borders 3:1 (WCAG 1.4.11). The PDF exporter's table header/stripes now
  share the tokens (legacy terracotta removed).

### Added

- **Granny flat-motif topology and the 4th validator prior correction**
  (Lion Brand's classic granny square + Marching North's solid granny
  square, full text verbatim): ① the classic grows 12->24->36->48
  (+12 per round: four (3dc, ch2, 3dc) corners, one new side group
  per side per round) with a self-reported 76-st border round; ② the
  solid version grows 12->28->44->60 (+16 per round) — round 2 adds
  16 stitches onto only 12 source stitches, tripping the hard
  "inc <= prev" rule. Mechanical verification shows the increases go
  into chain corner spaces, not stitches: **inc-exceeding-source is
  downgraded from a hard error to a note** (same family as W
  "3 sc in one st" and shell stitches — fully hookable; the exporter
  skips such rounds). The decrease rule stays hard. 2 new granny
  fixtures (50 in the file, 810 total).

- **Joined-round (non-spiral) part verification** (Tiny Curl's
  "Monsieur Bear" + Squirrel Picnic's "Motley the Bear", full text
  verbatim): ① the beret is explicitly labeled "joined rnds, not
  continuous spiral", with the turning-chain-counts convention
  "Ch 3 (count as st)" — round totals include the turning chain
  (11->22->33->44->44->33, symmetric +/-11 verified round by round;
  non-6-multiples correctly downgraded to notes); ② a joined, turned
  ear (MR 7, ch 1 counts + turn, half double crochet) enters the
  fixtures for the first time; ③ the muzzle switches to "Join with
  slst, ch 1" from round 2 (turning chain does **not** count —
  contrast between the two sources) while mixed with spiral rounds in
  the same piece — confirming that joined rounds keep the same stitch
  rhythm as spirals; ④ skip-based closing `(1 sc, skip 1) x 6`
  (12->6, same counts as sc2tog, different technique); ⑤ the head's
  R29 FLO neck round corroborates the bee's BLO neck round
  (count-neutral neck divider). The export preamble now notes that
  the starting chain usually does not count as a stitch unless the
  pattern says so. 3 tests (48 in the file, 808 total).

- **Chain-joined-legs body and oval-start verification** (Craftably Ever
  After's "Patchy Bear" sit-down bear, full text captured verbatim):
  ① the standard sitting-amigurumi body start — chain-bridge leg join
  R15=36 (the source self-reports 13 sc (leg 2) + 2 ch + 16 sc (leg 1) +
  2 sc in ch + 3 sc; mechanically verified, distinct from the direct
  24+24->48 leg merge and from sewing); ② the snout oval start with its
  verbatim count (ch 4, 2nd ch from hook, 3 sc end caps -> [10]; the
  validator correctly downgrades it to a note); ③ one more eye-placement
  anchor — 2 rows above the cap edge, 2 stitches apart (an anatomical
  anchor, not a round-ratio rule); craft corroboration: arms stuffed
  only halfway, ears flattened unstuffed, seamless closing (front
  loops). 2 tests (45 total).

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

- **Head notes now use the same safety-eye sizing as the materials
  list**: the head note hardcoded "install safety eyes (8 mm...)",
  conflicting with the diameter-based materials ladder (10 mm for a
  9 cm head, 14 mm for 15 cm) — both now go through `_safety_eye_mm`,
  pinned by a regression test.
- **Image-chart vision transcription unlocked (first Chinese-community
  fixture)**: the Ziyou Shouzuo "Bone Dumpling" image chart reposted on
  Bianzhirensheng's CDN was transcribed visually into aggregate counts —
  its notation (X/V/A/CH/SL) matches our export legend exactly, and its
  4-ply yarn + 1.8/2.0 mm hook corroborates the fine preset's "4-ply
  cotton" label. Five new tests pin: the symmetric 6->42->6 body worked
  in joined rounds (zero notes), the bone's 18->36 doubling round
  (written as "36X"), the 10/8-stitch bang ring starts, the headcover's
  30-stitch opening feeding the openings map, and a new preamble note
  bridging joined rounds (CN mainstream) and spiral work.
- **Opening-filter fix**: last-round notes saying "do not close"
  (不收口/勿收口 — an explicit opening statement, e.g. the headcover's
  "keep the opening... do not close") are no longer misclassified as
  closed by the substring "收口" — a negative-lookbehind regex
  `(?<![不勿])收口` handles it.
- **Third validator-prior correction: mixed increase/decrease rounds
  downgrade to notes**: the lop-rabbit eye-socket round
  `7X,7V,A,7V,7X` (30->43) mixes increases and decreases within one
  round in a real chart, algebraically sound — the old validator
  hard-rejected it. Executability stays guaranteed by inc<=prev /
  dec<=prev/2 (hard checks); mixed rounds exceed this generator's
  uniform-group expression, so the CrochetPARADE export honestly skips
  them.
- **Channel sweep harvest (vision transcription at scale)**: the lop
  rabbit (face shaping / sc3tog / a flat oval ear on a foundation
  chain / a 6-stitch tube arm / a 3-mm tiny-eyes data point), Mr. Orange
  (a **three-sector hat topology** at +3/round, a 7-start headcover with
  a doubling round and slip-stitch edging, feet decreasing to odd 7, and
  a same-round join of feet+arms = one-piece), and AllAboutAmi's
  Elephant (a cone trunk at -3/round; oval foundation-start bodies and
  pick-up legs are documented as beyond the aggregate model). The export
  legend gains the CN-standard W (3 sc in one st) and M (sc3tog)
  symbols.
- **C2C written rows upgraded to the professional format** (aligned
  with Juniper & Oakes and peers): every diagonal row now carries a
  direction arrow (odd rows ↙ on the right side / even rows ↗ on the
  wrong side) and a right-side/wrong-side label alternating with the
  turns; the header states the convention's provenance. The direction
  was cross-checked line-by-line against two independent sources
  (Juniper & Oakes, Lovable Loops) — the first implementation had it
  inverted and the heart chart's asymmetric rows caught it.
- **Second published grid-chart fixture (Lovable Loops heart 9x9)**:
  its 17 written color rows were transcribed into a grid, rendered
  through this system's C2C writer, and reproduced row for row
  (including asymmetric rows 7/8/9) — complementing the cherry fixture's
  cluster-count check by pinning the in-row color reading direction.
- **Flat-seam hint for tiny openings in assembly text**: limb steps with
  an opening of 6 stitches or fewer now add "small openings can be
  flattened and sewn" (community practice, e.g. the lop-rabbit arms).
- **Eye-placement note anchored in words**: head notes now say "near the
  widest round" — professional charts place eyes relative to landmarks
  (Supergurumi bee: "2 stitch rows after the nose" — the BLO ridge —
  with spacing down to 1 stitch), and this generator has no landmarks,
  so the geometric approximation is stated and the maker is told to
  adjust for eye size and face.
- **Bulk channel enumeration**: Bianzhirensheng's sitemap shards
  (25k URLs) are enumerable and chart posts are locatable by ID range;
  the Gummy-series mini-charm chart (vision transcription) adds the
  bobble B (5-dc cluster, in-and-out of one stitch — stitch-count
  neutral) to the export legend, plus fixtures for a full 24->12
  decrease round and an in-round color change on BLO (beyond this
  model's per-round color granularity, documented as such).
- **Two-leg join and shoulder-shaping fixtures (first Xiaohongshu-native
  chart)**: Qing Yi Shouzuo's "Little Rabbit Sister" (watermark confirms
  Xiaohongshu origin, reposted on Bianzhirensheng) — the overalls start
  from two separately ringed 24-stitch legs joined in the round into a
  48-stitch body (matching this system's body-R1 join semantics); the
  big carrot narrows then re-widens (12->9->12, an in-part direction
  reversal); the small carrot starts with 5 stitches and closes 9->5
  with "4 dec, 1 sc". International: 53stitches' "Low sew Bunny" — MR 8
  start with popcorn-stitch limbs (neutral, same family as the bobble).
  The validator again caught two transcription misreads on the spot
  (a v/a mix-up on the carrot; an elided-row discontinuity on the
  bunny) — the transcribe-verify loop keeps paying off.

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
