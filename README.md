# 🧶 CrochetPhoto2Pattern

[简体中文](README_ZH.md) | **English**

[![CI](https://github.com/paulkooer/CrochetPhoto2Pattern/actions/workflows/ci.yml/badge.svg)](https://github.com/paulkooer/CrochetPhoto2Pattern/actions/workflows/ci.yml) [![Version: 0.2.0 beta 2](https://img.shields.io/badge/version-0.2.0--beta.2-orange.svg)](CHANGELOG_EN.md) [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> A local amigurumi design tool: analyze a photo, review proportions and parts, then generate a crochet draft.

> **Release status: Beta.** Automated checks prove only that a pattern satisfies the
> current stitch arithmetic and shaping rules. They do not replace gauge swatches or
> physical test crochets. Verify dimensions, tension, and assembly before publishing a
> generated pattern. See [System Status and Release Gates](docs/system-status.md).

Photo analysis now runs locally by default. Cloud LLM interfaces, credential settings, and SDK dependencies have been removed. Review proportions and parts before generating; `--local` remains compatible with older commands.

Migration: remove provider key/Base URL arguments from library constructors and replace `vision_mode="ai"` with `"local"`. Historical patterns retain provenance and usage on import. Run `uv sync --locked` to update the installed dependency environment.

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

**Why "executable correctness" matters here:** research on vision-language models for
crochet ([CrochetBench, ACL 2026](https://arxiv.org/abs/2511.09483)) shows model
performance drops sharply when evaluation moves from surface-level similarity to
executable correctness — models describe well but rarely produce workable instructions.
This project therefore treats the pattern as a checkable artifact: every generated
pattern passes an algebra/self-check gate before download, and the evaluation protocol
reports a second-tier `parade_export_rate` — whether the result can be translated into
the [CrochetPARADE](https://crochetparade.org) pattern language (independent
structural analysis, 3D rendering, and stitch-tension checks; paste the exported DSL
into their locally-run web app). This does not establish physical correctness of a generated object.

## Features

Unknown part names remain available for review. Remove mistaken labels or select supported parts before generation; unsupported anatomy is no longer replaced by a small sphere. Existing custom-structure backups remain importable.

- Photo upload, plus manual and 2D grid workflows.
- Local photo analysis: candidate head-box checks and silhouette analysis without
  an LLM API key. Parts are an unconfirmed template; silhouette flare only suggests a skirt.
- GrabCut subject segmentation shared once per generation across palette, profile,
  and color bands, with repeatable initialization and fallback when extraction fails.
- Optional pose landmarks on Python 3.11–3.12 for shoulder/hip/knee measurement; Linux
  also requires EGL/GLESv2 and safely falls back when the native runtime is unavailable.
- Photo-derived yarn palettes, longitudinal color bands, and CIEDE2000 color matching.
- Versioned template geometry with part instances, mirrored pairs, rotations, attachment
  anchors, and explicit inference provenance. Heuristics are uncalibrated; no confidence
  percentage is claimed. This is not full 3D reconstruction.
- Gauge-aware, round-by-round stitch generation with executable six-section shaping.
- **CrochetPARADE export:** translate the pattern into the
  [CrochetPARADE](https://crochetparade.org) DSL (result page / `--parade`) for
  independent 3D rendering and stitch-tension analysis — a second-tier
  executable-correctness check reported by the evaluation protocol
  (`parade_export_rate`).
- Correct multiplicity accounting for paired arms, legs, and ears across stitches,
  materials, time estimates, exports, and progress.
- Photo recognition pauses for review: crop the subject, inspect the outline/head box,
  correct head proportions and parts, then generate locally.
- An optional blue body box excludes foreground outside the selected region from
  shape measurement. Backups and resizing retain both the original silhouette and
  reviewed body profile. The box cannot recover missing foreground or measure cm;
  body colors only inherit its vertical interval.
- Enable the foreground brush to add missed regions or erase background directly
  on the photo. Each completed stroke updates geometry and colors; undo the last
  20 strokes or restore automatic segmentation. Backups retain the corrected mask.
  Part names still need review; hidden or cropped-out anatomy cannot be recovered.
- Form-based part size/quantity/position/attachment editing and a per-round stitch table,
  plus session undo/redo (up to 12 snapshots / 8 MB) and before/after comparisons.
- One per-color yarn purchase list with a separate subtotal; optional ball labels and
  weighed swatches refine grams, metres, and whole-ball counts. Estimates include a
  configurable allowance (10% by default), and the same yarn specification applies to all colors.
- Stage timings, fallback reasons, and a runtime budget. Historical imported results retain their original usage metadata.
- Strictly validated advanced structure editing with local regeneration.
- Separate-head neck openings: preview an exact stitch target such as 16, with executable
  final decreases, actual joining-round references, matching assembly/exports and project
  recovery. Applies to separate heads; resizing retains the target and rejects incompatible
  smaller heads. See the [opening guide](docs/project-format.md#独立头部留口).
- Resizing preserves edited structures; explicit diameters, cup depths, and colors affect generation. Edited pattern gauge is shared by materials, exports, previews, and regeneration.
- Editable 2D grid projects for tapestry, C2C, and cross-stitch workflows. Failed generation,
  restoration or editing preserves the current grid and undo/redo history; downloads match
  the displayed result. See the [Chinese grid-project guide](docs/project-format.md#平面网格工程与修色历史).
- Stitch-arithmetic and supported round-notation checks, an editor calculator for
  consumed/output stitches and increases/decreases, ring charts, progress tracking, per-color bills of
  materials, share links, SQLite history, JSON backup, Markdown, and optional PDF export.
- Explicit stitch order is preserved in Markdown, symbol strips and CrochetPARADE,
  including mixed shaping and nested repeats. Aggregate-only export counts inferred
  placement separately; prose-only placement hints and special techniques still need review.
- Opt-in stitch-parent inspection maps explicit formulas to the preceding round's stitch
  indices, including scoped FLO/BLO. Browse 24 operations per page and download that window
  as SVG/JSON; this shows associations rather than physical shape or tension. See the
  [Chinese inspection guide](docs/project-format.md#逐针连接核对).
- Scoped front/back-loop notation, such as `BLO((2X,V)×6)` or `4sc-FLO`, retains
  counts and exact loop positions through checks, charts and exports. F/B labels mark
  chart positions; unresolved loop instructions stop that part's DSL export for review.
- Preserve explicit `inv-sc2tog` technique identity in counting, edits, backups and printed
  notation. The current DSL/chart subset requests review for invisible decreases instead of
  substituting ordinary decreases. Charts retain the pattern's actual round numbers.
- Consecutive +6 rounds specify end/center placement directly, such as `(X,V,X)×6`.
  Numeric edits update affected neighboring instructions while retaining finishing steps.
- EXIF orientation correction and defensive image/input size limits.
- Authorized-photo evaluation and independent physical-trial tooling.

## Technology

- Python 3.11–3.14
- Streamlit
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

No API key or model service is needed. Optionally copy `.env.example` to `.env` to
configure trusted single-user history. Legacy provider environment variables are ignored.

Photos provide relative proportions; the target height in centimetres comes from you.
Optional pose landmarks may download model weights on first use; provide
`CROCHET_POSE_MODEL` for a local model file. Photos are processed on the application host.

### Data and privacy

- Uploads reach the machine hosting Streamlit. Processing stays on your own computer
  only when you host the application there; “local vision” means no LLM call.
- Local vision, manual input, and grid mode do not send photos to an LLM provider.
- Only use images you are authorized to process.
- Pattern history is disabled by default. Only trusted single-user installations may
  set `CROCHET_HISTORY_MODE=single_user` to use the server's local SQLite database.
  Shared/public deployments must keep `disabled`; history has no user authentication
  or ownership isolation. Existing databases are preserved. Share links embed compressed
  pattern data in the URL; opening one still sends the token to the host running the app,
  so links should not contain sensitive material.
- `.env`, authorized evaluation photos, evaluation outputs, and physical-trial records
  are ignored by Git by default. Always review staged files for credentials, private
  photos, and personal information.
- Public visibility is not authorization; disclaimers, credit, or "remove on notice" promises
  cannot replace permission. See the [Third-Party Content Policy](THIRD_PARTY_CONTENT_EN.md)
  and [Notice and Takedown Process](NOTICE_AND_TAKEDOWN_EN.md).

### Run the UI

```bash
uv run streamlit run app/main.py
```

### Save and reopen a pattern

Choose **💾 备份完整结果** (back up the complete result) on a result page to save JSON.
In a fresh session, expand **📂 打开备份图解** in the sidebar, upload that file, and click
**导入并打开图解**. The restored pattern appears in the local Photo tab without generating
a seed pattern or enabling history. Uploads accept UTF-8 JSON up to 20 MiB; the paste
option accepts up to 2 MiB. A parameters-only JSON download is not a complete backup.

Import validates the format, stitch counts and explicit operations before replacing the
Photo result. Failed imports preserve current work, and sidebar imports leave the Manual
tab's result untouched. The import panel on each result page replaces that page's result.
To retain actual crochet progress, expand **🧺 我的钩织工程**, enter personal notes, choose
**💾 保存工程（含进度）**, and download the project JSON from the dialog. Projects save
completed rounds for each physical copy, notes and a pattern revision. Reopen them through
the same sidebar uploader. Save again after working: each file captures the state when Save
was clicked. Edits report affected progress resets; undo restores progress. Ordinary pattern
backups and share links omit personal notes/progress; undo history remains session-only.
Backups, share links, project files and trial bundles also omit photo-derived data (the 96 px
`preview` thumbnail and the hand-corrected `mask_review` silhouette).
Similarly named custom parts, including names ending in `copy2`, track each physical copy
independently. Bulk completion and reset affect only the selected part and preserve project notes.
For paginated patterns, **前往下一未完成圈** jumps to the selected part's first unchecked
round, including later physical copies, without changing progress. For multiple layers of
reserved-loop joins, editing a foundation clears all dependent progress regardless of record order.
Round edits retain completed work before the first changed round; part-wide or gauge changes
remain conservative. Use each edit control's **预览…修改影响** button to review affected parts,
starting rounds and retained/cleared counts, then apply or cancel the preview. Preview again
after changing inputs; applying a preview uses the latest progress.

Under local edits, **锁针并腿方案（手动核对）** records each leg's open round, stitch count and
marker, plus the bridge chain count. It calculates a join round with one single crochet per
opening stitch and on each side of each chain. View and download a count-only SVG diagram;
download the standalone plan and preview it before restoring by upload or JSON paste. Optionally select two current pattern parts to compare round
numbers, stitch counts and copy counts, with reminders for later rounds and finishing instructions.
Generating or importing a new result, applying an edit, undoing or redoing clears this tool's
inputs, preview and part selections. Download the plan first to restore it afterward; failed
operations retain the current plan.
Manually verify the openings, start and direction; the
plan does not modify the pattern and cannot be imported as a pattern or project. See the
[Chinese guide](docs/project-format.md#手动规划锁针并腿).

### Crochet an attached skirt

The sidebar's attached-skirt option now identifies a body foundation round, the following
FLO reservation round, and the exact BLO range used by the skirt's first round. Body and skirt
copy counts must match. One-piece construction uses merged round numbers; resizing recomputes
the connection, and Markdown/PDF render the same record. For example, a 36-stitch foundation
at body round 11 is reserved by working round 12 into its front loops; the skirt then uses
round 11's 36 remaining back loops. Follow the generated numbers; the waist location is a
template choice requiring a physical trial. Legacy backups remain readable with a review
notice when exact references are missing. The current CrochetPARADE subset skips attached
components and reports partial export because cross-component reserved-loop joins are not implemented.
Under local edits, **接裙位置图示与调整** shows the foundation/reservation/join sequence and
lets you preview a different foundation round. Applying restores the old reservation, creates
the new one and adjusts generated skirt shaping when waist counts differ. Custom instructions
that cannot be safely reconstructed are preserved by rejecting the edit. Download the schematic
as SVG; Markdown/PDF include the same connection sequence as a table.
Applying a new waist pins its relative position in the candidate-round sequence. You can also
choose **预览固定当前腰位** to pin the current round. Pattern backups and projects retain this
preference; size and structure regeneration map it to the nearest new candidate. This fraction
describes candidate order, not measured waist height. **预览取消腰位固定** previews a return to
automatic placement on the next regeneration, preserving current stitches and progress. Both
pinning and unpinning support undo.

### Review and runtime limits

The Photo tab uses **recognize → review → generate**. Changing the crop or mode invalidates
its recognition draft; changing target size or review fields reuses local observations.
The default active-work budget is 180 seconds (15–600 in the UI), excluding time spent
reviewing. It is checked between stages but
cannot interrupt native image processing or guarantee a hard wall-clock cutoff.
Each export has a separate 60-second cooperative budget; export timings stay in the session,
while photo-stage diagnostics travel with backups. Failed edits keep the current result.
Size and structure edits retain manual rounds, colors and notes for parts whose old and new
generated constructions agree. Changed constructions, including one-piece and skirt-join
dependencies, are recalculated; a changed gauge recalculates every part. If a legacy template
cannot be reproduced, regeneration replaces all parts. Preview the impact before applying;
undo can restore the previous version. See the [editing details](docs/project-format.md#尺寸编辑与手改保留).

### Headless CLI

```bash
uv run crochet2pattern --image photo.jpg --gauge dk --out pattern.json --md pattern.md
uv run crochet2pattern --head 9 --height 18 --parts 头部,身体 --sphere-mode egg --out p.json
uv run crochet2pattern --mock --out demo.json
uv run crochet2pattern --batch-dir photos/ --out-dir patterns/
```

Canonical part values in the current schema are Chinese (`头部`, `身体`, and so on), so
the manual CLI example intentionally retains them. Photo mode always uses local vision, regardless of provider environment variables. A pattern that violates stitch
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
docker run -p 8501:8501 crochet-photo2pattern
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

The evaluation command records per-image copyright evidence, subject authorization,
purpose approval, SHA-256, and scene tags. It runs only local vision and does not send
evaluation photos to an LLM provider:

```bash
uv run crochet2pattern-eval --dataset eval_data/release-01 \
  --out eval_outputs/release-01.json
```

See the [Authorized Real-Photo Evaluation Protocol](docs/evaluation.en.md). Evaluation
photos and reports are ignored by Git, and passing software metrics still does not prove
physical crochetability.

## Physical-trial loop

Use **🧪 实体试钩记录** on a result page to enter swatch/yarn details, measured dimensions,
usage and scoped timing, then save and download a ZIP with its original pattern. Reopen it
through the sidebar's **🧪 打开试钩包** without generating a seed result. Live pattern edits do
not rebind existing measurements. Downloads reflect the last successful save; trial bundles
and crochet projects are separate. Their `*.trial.json` files work with the CLI below.
Save partial measurements as drafts and resume them later; required measurements are checked
when marking complete. Returning to draft retains observations, while incomplete data stays out
of finished-item comparisons and calibration. ZIP bundles with partial drafts require this version to restore.
Undo/redo saved records restores both the form and download; unsaved input blocks switching and
is retained. History is session-only, limited to eight snapshots and 2 MiB combined, and omitted from ZIPs.
The panel compares saved measurements with the source pattern. After saving a measured swatch,
use **预览按实测密度重算** to review new stitch counts and progress impact at unchanged target
dimensions. Regeneration retains pinned waist placement, supports undo, and leaves trial evidence
unchanged. It replaces manual round edits and clears progress for review when density changes.
Full-project timing is not treated as comparable to the original round-crochet baseline.

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
