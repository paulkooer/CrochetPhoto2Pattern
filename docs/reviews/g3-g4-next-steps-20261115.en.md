# G3 strict-evaluation gaps and G4 startup plan (2026-11-15)

[简体中文](g3-g4-next-steps-20261115.md) | [System status](../system-status.md)

Pause additional refactoring and prioritize real evidence. Only de-identified aggregates are
published here. Personal originals, filenames, per-image manifests and reports stay in ignored
local directories and are excluded from Git, Beta packages and release attachments.

## G3: strict runs completed; the gate still fails

Run `crochet2pattern-eval --release` against the existing 30-image primary and 34-image extension
datasets, using default local vision, policy 3 and report schema 6. No custom runner, `--allow-fail`
or threshold changes were used. Both runs completed with exit 2, zero pipeline errors,
`automated_passed=false` and `release_approved=false`. Images were not sent to external services.
The datasets overlap and do not represent 64 independent cases.
The application tree matches fix commit `7df29371c23066af0ec1226907bf047ecb160eda`, using
Python 3.12.13 and runtime package version 0.2.0b2. Beta 3 preparation does not change vision algorithms.

| Metric | Primary: 30 | Extension: 34 | Strict requirement |
|---|---:|---:|---|
| Unique image SHA-256 hashes | 30 | 34 | ≥30, without duplicate contents |
| Macro part F1 | 0.8492 | 0.8467 | ≥0.6 and strictly above the fixed template |
| Fixed-template macro F1 | 0.8763 | 0.8699 | The automatic pipeline must exceed this; both fail |
| Case pass rate | 0.3333 | 0.2941 | ≥0.8 |
| Flare accuracy | 0.7000 | 0.6765 | ≥0.8 |
| Top-3 color accuracy | 0.4000 | 0.3824 | ≥0.8 |
| Valid-pattern rate | 1.0000 | 1.0000 | 1.0 |
| Software crochetability-rule pass rate | 0.9667 | 0.9706 | 1.0; not physical validation |
| Supported-construction Parade export rate | 1.0000 | 1.0000 | 1.0 |
| Exact delivered-part match rate | 0.2667 | 0.2353 | ≥0.8 |
| Flare-positive recall | 0.3333 | 0.3333 | ≥0.8 |
| Flare-negative recall | 0.7407 | 0.7500 | ≥0.8 |

Each expected part also needs recall ≥0.8. Hat and ear recall are zero in both datasets;
skirt recall is 0.3333. Head, body, arm and leg recall are 1.0. Software validity and export
passes do not compensate for these visual-quality failures.

| Coverage group | Primary: 30 | Extension: 34 | Minimum |
|---|---:|---:|---:|
| Full body | 29 | 33 | 5 |
| Half body or close-up | 1 | 1 | 5 |
| Seated or occluded | 4 | 6 | 5 |
| Plain background | 8 | 8 | 5 |
| Complex background | 22 | 26 | 5 |
| Low contrast | 5 | 5 | 5 |
| Flare positive / negative | 3 / 27 | 6 / 28 | 5 each |

Next evidence work:

1. Start from the existing 34-image extension and add at least four authorized, genuinely
   distinct half-body or close-up photos. Crops, transcodes, repeated subjects or unverified
   relabeling must not be used to fill the count.
2. If retaining the 30-image primary set, also add at least one seated/occluded case and two
   flare-positive cases. Genuine scene conditions may overlap within a new image.
3. Obtain maintainer confirmation of part, flare, color and scene ground truth; the current
   labels remain exploratory and have not received complete human confirmation. Review rights,
   near duplicates, orientation/phone EXIF and clothing/subject diversity as well.
4. Keep thresholds unchanged and independently freeze data when checking colors, hat/ear/skirt
   recall, flare negatives, exact part sets and degenerate patterns. More photos can address
   coverage but do not themselves fix quality. Repeated tuning against this observed set
   cannot turn it into an independent validation set.

Raw execution logs and per-image reports remain local. Reproduce using:

```bash
crochet2pattern-eval --dataset <private-authorized-dataset> --release --out <private-report.json>
```

## G4: deliver a single-maker starter kit; recruit a second maker later

The maintainer confirmed there is currently one maker. All starter records use the same stable
anonymous ID, `maker-a`, remain drafts and contain no invented measurements or second identity.
Patterns are generated from manual parameters and contain no personal photos.

| Tasks | Cohort | Design | Maker |
|---|---|---|---|
| cal-01, cal-02 | Calibration | C1 | maker-a |
| cal-03, cal-04 | Calibration | C2 | maker-a |
| cal-05 | Calibration | C3 | maker-a |
| val-01, val-02 | Independent-design validation | V1 | maker-a |
| val-03 | Independent-design validation | V2 | maker-a |

Calibration and validation must have disjoint design fingerprints and original pattern hashes.
Repeated designs require separately made items, not copies of one item's measurements. Each ZIP
binds the exact `pattern.json`; readable patterns and measurement instructions accompany it.
Measure a swatch first, then record finished height, net yarn grams, active minutes, time scope
and modifications. Full-project time cannot calibrate the round-only baseline, and modified
patterns cannot calibrate constants. All estimates still await physical measurements.

One maker completing all eight items still cannot meet the two-maker requirement. A second
participant must independently complete at least one calibration design and one validation
design using their own stable anonymous ID, while preserving cohort design separation.
Calibration needs at least five eligible completed records, three designs and two makers;
validation needs three records, two independent designs and two makers. Human review of error
distributions remains necessary after sample eligibility passes.

## Scope decisions

- Merge the entry and layering fixes through a separate PR with a full pre-merge test run.
- Preserve existing `app.trials` exports; defer import consolidation and long-function splits.
- No further refactor is planned now, so do not expand one-off tree-diff scripts into a generic
  framework. Retain the original acceptance material.
- Bind new G1/G2 evidence to the selected Beta candidate and disclose blocked G3/G4. Stable
  release gates are unchanged.
