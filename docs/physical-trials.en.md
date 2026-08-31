# Physical Trial Records and Calibration

[简体中文](physical-trials.md) | **English** | [Documentation index](README.md)

The trial tooling turns “size may need adjustment” into traceable evidence. It never
modifies production constants automatically. Raw records and reports belong in the
Git-ignored `trial_data/` and `trial_outputs/` directories.

## 1. Create a draft from an exact pattern

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
`independent_validation.sample_ready=true` proves only quantity, diversity, and isolation;
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
