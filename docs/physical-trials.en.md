# Physical Trial Records and Calibration

[简体中文](physical-trials.md) | **English** | [Documentation index](README.md)

The trial tooling turns “size may need adjustment” into traceable evidence. It never
modifies production constants automatically. Raw records and reports belong in the
Git-ignored `trial_data/` and `trial_outputs/` directories.

Trials need not be performed by the project author. Other makers may work an exact
system-exported pattern and submit its hash, measured swatch, dimensions, yarn usage,
scoped timing and anonymous maker record under the same protocol. Calibration and
validation cohorts must remain separate. Online tutorials and similar finished objects
provide rule or scale references; current `external_evidence` summaries are not promoted
automatically into qualifying trials. See [online evidence scope](SOURCES.en.md).

## 1. Create a draft from an exact pattern

### Record and restore in the web UI

Expand **🧪 实体试钩记录** on a result page, enter a trial ID, stable anonymous maker ID and
cohort, then choose **以当前图解新建试钩**. The original pattern snapshot stays fixed while
you enter measurements.

1. Enter the measured swatch, hook and yarn details, save, and download the draft ZIP.
   Initial gauge values come from the pattern; replace them with actual measurements before
   checking **已实际测量小样**.
2. Enter dimensions, usage, timing and notes in stages, leaving unmeasured values blank and
   saving as a draft. Once finished, check **标记为完成（需填写必填测量）** and provide the
   completion date, height, yarn grams and active minutes. Timing defaults to the full project;
   select the round-only scope only when that
   matches the measured operations. Declare any pattern changes, one per line. Saving shows
   measured height deviation from the original target.
3. Download the updated ZIP. Downloads contain the last successfully saved state; unsaved or
   invalid inputs do not replace it. Saving a completed record as a draft retains its measurements
   for further work. Fields stay visible when completion status changes; blank dates are not
   silently replaced with today's date.
4. In a fresh session, use the sidebar's **🧪 打开试钩包** to reopen the ZIP without generating
   another pattern. This replaces the Photo result and its active trial, leaving the Manual
   result alone. The restore control inside a result's trial panel replaces only that trial,
   preserving the current pattern.

Editing the live pattern does not rebind an existing trial: the panel flags the difference and
retains its original source. Declare changes actually used in the physical work; for a new design,
download the old trial before closing it and starting another. Each result page edits one trial
at a time, with independent Photo and Manual workspaces.

### Undo or redo saved records

After saving, use **↶ 撤销保存** or **↷ 重做保存** to restore swatches, yarn, measurements and
draft/completed status. The form, comparison table and download switch together, preserving the
current pattern, crochet progress and project notes. Unsaved changes or invalid fields block
undo/redo while retaining your input; save first, or restore the fields to their saved values.
Saving changed content after undo clears redo. Saving identical content adds no history and
preserves redo.

History stays in the current session: undo and redo share a limit of eight snapshots and 2 MiB,
dropping earlier retained entries when needed. The source pattern is kept only once. Reopening
a trial bundle or closing the record clears history; ZIP downloads omit it. To keep a particular
version permanently, switch to it and download.

### Bundle format and saved content

The ZIP contains `pattern.json` and `<trial-id>.trial.json`, retaining trial schema 2. Partial
measurements add optional `draft.json` using independent schema 1; see its
[JSON Schema](schemas/trial_draft_state.schema.json). Its `record_sha256` binds the exact trial
JSON bytes, which in turn bind the original pattern. Do not mix files from different downloads.
Draft measurements may be missing, but supplied values still obey ranges and length limits. Restoration
verifies the exact source-byte SHA-256 and its target height, gauge, physical stitch/round counts
and estimated time. Limits are 20 MiB for the pattern and 512 KiB each for the trial JSON and optional
draft. ZIP members are read with bounds in memory, never extracted to disk. Corrupt, duplicate,
undefined extra members, path-bearing,
non-finite or mismatched contents leave current work intact.

Partial observations stay outside completed evidence: `*.trial.json` remains `status="draft"`
with `observation=null`, excluded from finished-item comparisons and calibration. Marking complete
and saving validates the full record before moving observations into it and removing `draft.json`.
Returning to draft moves measurements back without deleting them. Swatch/yarn-only drafts and
completed records still use the original two-file ZIP. The new version reads old bundles; restoring
a three-file draft bundle requires this version. Older CLI tools can still read its formal record
and ignore the draft-status sample.

Trial bundles omit crochet progress, project notes and undo history. Trial records are separate
from ordinary pattern backups, projects and share links; save a crochet project separately to
retain progress. Download before closing the session. Restoring a record does not independently
verify the physical measurements or change generator constants.

### Compare measurements and regenerate at measured density

The comparison table uses the last successfully saved measurements: stitch/row gauge, finished
height, yarn and time. Differences are measured/reference minus one. Unconfirmed swatches are
not presented as measurements; missing legacy yarn estimates remain unavailable. Full-project
time is labelled as a different scope, without a baseline-time percentage. Modified trials can
still show deviations, but these also include the changes made to the pattern.

Drafts with a saved measured swatch and completed trials can both drive density regeneration:

1. Enter measured stitches/rows per 10 cm, confirm the swatch was measured, and save the record.
2. The current pattern must match the trial's original source and its density must differ.
   Reopen the original trial bundle from the sidebar if necessary.
3. Choose **预览按实测密度重算** and inspect the density, stitch/material totals and progress
   impact under local edits, then apply or cancel. Preview again after changing inputs or records.
4. Save the updated pattern. Download and close the old trial before starting a trial of the new pattern.

Regeneration retains target dimensions, structure, color-generation inputs, yarn specifications
and the pinned waist fraction, while rebuilding rounds and exact joins. It replaces manual round
edits. A density change clears completed-round marks for review while keeping project notes;
undo restores the old density, pattern and progress. An identical density does not regenerate or
erase custom instructions. The original trial and its ZIP remain unchanged. This uses measured
gauge, without inferring a scaling factor from one finished height or changing global yarn/time
constants; another physical trial is still needed to assess the result.

### Create and aggregate with the CLI

Extract the web bundle's `*.trial.json` into `trial_data/` to use the existing `analyze` command.
Keep its `pattern.json` bytes unchanged for review. With `draft.json`, the trial JSON bytes are also
checked; complete and save through the UI instead of editing or reformatting archive members.
Drafts do not become completed samples. Alternatively, create a draft with the CLI:

Generate complete pattern JSON, then bind a trial record to its SHA-256:

```bash
uv run crochet2pattern --mock --out pattern.json --quiet
mkdir -p trial_data trial_outputs
uv run crochet2pattern-trials init \
  --pattern pattern.json \
  --trial-id classic-001 \
  --maker-id maker-a \
  --cohort calibration \
  --out trial_data/classic-001.trial.json
```

Use a stable anonymous `maker_id`, never a name, email, or account. The tool recomputes
entity-aware total stitches and rounds from the pattern body instead of trusting stale
derived fields.

## 2. Complete the record

After crocheting, edit the generated `*.trial.json`:

```json
{
  "status": "completed",
  "swatch": {
    "measured": true,
    "stitches_per_10cm": 13,
    "rows_per_10cm": 16,
    "hook_mm": 4,
    "yarn_brand": "example brand",
    "yarn_line": "example line",
    "yarn_lot": "anonymous lot",
    "fiber": "cotton"
  },
  "observation": {
    "completed_on": "2026-08-30",
    "overall_height_cm": 18.7,
    "yarn_used_grams": 92.4,
    "yarn_used_meters": null,
    "active_minutes": 162,
    "time_scope": "round_crochet_baseline",
    "pattern_modified": false,
    "modifications": [],
    "notes": "reproduction-relevant information only"
  }
}
```

Keep the generated `schema_version`, `trial_id`, `maker_id`, `cohort`, and `pattern`
fields. The current schema is version 2. Version 1 completed records must add `time_scope`
and migrate to version 2. Older v2 records without a cohort are read as `calibration`, but
holdout records must explicitly set `cohort="validation"`.

- `active_minutes` excludes pauses. Use `round_crochet_baseline` only for round crochet
  and transitions. If it includes sewing, stuffing, color changes, embroidery, or other
  finishing, use `full_project`; it will be reported but cannot produce seconds per stitch.
- `yarn_used_grams` counts yarn only, excluding stuffing, safety eyes, hardware, and unused remnants.
- Fill `yarn_used_meters` only when starting and remaining lengths were measured reliably.
- Any changed round, stitch count, or part requires `pattern_modified=true` plus a
  `modifications` entry. Modified trials remain visible but are excluded from calibration.

## 3. Aggregate analysis

```bash
uv run crochet2pattern-trials analyze \
  --records trial_data \
  --out trial_outputs/baseline.json
```

- `0`: both yarn-weight and baseline-time groups contain at least five completed,
  unmodified trials, covering at least three pattern hashes and two anonymous makers.
- `1`: invalid record schema, ranges, duplicate ID, or JSON.
- `2`: report created, but quantity or diversity is insufficient.

`--allow-insufficient` is available for exploration, but
`summary.calibration_ready` remains false.

### Independent holdout validation

Candidate constants may use only `calibration` records. Prepare at least three additional
completed, unmodified `validation` records with baseline time scope, at least two pattern
hashes, and two anonymous makers. Holdout hashes must not appear in calibration:

```bash
uv run crochet2pattern-trials init \
  --pattern unseen-pattern.json \
  --trial-id holdout-001 \
  --maker-id maker-b \
  --cohort validation \
  --out trial_data/holdout-001.trial.json

uv run crochet2pattern-trials analyze \
  --records trial_data \
  --require-validation \
  --out trial_outputs/release-review.json
```

`--require-validation` exits `2` for an undersized holdout or overlapping hashes.
Distinct patterns and cohort isolation use the **design fingerprint** (normalized gauge and
per-round stitch structure, excluding diagnostics timing, thumbnails, colors and yarn labels
that do not change the physical piece). Regenerating one design or changing only colors or
yarn labels therefore no longer counts as several independent patterns; earlier versions used
the volatile byte hash (audit F-03).
`independent_validation.sample_ready=true` proves only quantity, design diversity, and isolation;
it does not prove that current or candidate constants are accurate. Review the size,
weight, and time error distributions manually.

## 4. Report semantics

- Size: actual overall height / target overall height.
- Gauge: measured stitch/row gauge / pattern gauge.
- Weight: actual grams / entity-aware total stitches, normalized by stitch width × row height.
- Time: actual seconds minus the current ten-second per-round overhead, divided by total stitches.
- Length: used only when both measured metres and grams are available, normalized per 100 g.

Aggregates use medians and also report median absolute deviation, minimum, and maximum.
Candidate values are suppressed when normalized weight or per-stitch time has relative
MAD above 25%. Weight and baseline time have separate `ready` values and blockers.
Full-project time does not block a weight candidate but cannot produce a per-stitch candidate.

A candidate is not permission to change production constants immediately. Review the raw
cases, make a deliberate code change, and then test it on independent patterns that did
not participate in calibration.

The tool does not yet model maker speed, stitch type, stuffing tension, fibre moisture,
or dye-lot variation. Larger samples should be stratified by maker, yarn/hook, and pattern
complexity instead of collapsed into one constant.

## 5. External trial evidence

The wheel contains a small curated
[`external-trial-evidence.json`](../app/data/external-trial-evidence.json) with facts,
sources, and usage boundaries. It contains no copied pattern body, image, username, or
free-form project notes.

```bash
uv run crochet2pattern-trials external-report \
  --curated \
  --out trial_outputs/external-context.json

uv run crochet2pattern-trials analyze \
  --records trial_data \
  --curated-external-evidence \
  --out trial_outputs/baseline-with-context.json
```

For your own evidence, use `external-report --evidence path/to/evidence.json` or
`analyze --external-evidence path/to/evidence.json`. Curated and custom sources are
mutually exclusive to prevent provenance confusion.

Every external item records source URL, access date, evidence type, validation level,
raw-record availability, reuse basis, and sample claim. The schema fixes
`calibration_allowed=false`: external numbers may appear only in report context and can
never change calibration recommendations.

External evidence is useful for detecting order-of-magnitude errors and prioritizing
future local trial sizes. It cannot derive seconds per stitch from a similarly sized item;
parts, sewing, color changes, embroidery, stitches, yarn, and maker skill all differ.

CrochetBench is a pattern understanding/generation benchmark rather than a physical-trial
record and uses CC BY-NC 4.0. Ravelry content must not be copied in bulk. Any future
Ravelry integration should accept only user-authorized exports and preserve provenance
and permission information.
