# Authorized Real-Photo Evaluation

[简体中文](evaluation.md) | **English** | [Documentation index](README.md)

Real-photo evaluation runs only the local-vision path. It does not call OpenAI,
Anthropic, or a third-party relay. Photos, identifying filenames, and reports belong in
Git-ignored `eval_data/` and `eval_outputs/`. Manifest declarations are audit records;
they do not replace legally valid consent where required.
Disclaimers, credits, and "remove on notice" promises are not authorization; see the
[Third-Party Content Policy](../THIRD_PARTY_CONTENT_EN.md).

## 1. Create a dataset

```bash
mkdir -p eval_data/release-01 eval_outputs
cp docs/eval_manifest.example.json eval_data/release-01/eval_manifest.json
shasum -a 256 eval_data/release-01/standing-plain-001.jpg
```

Put the 64-character hash in the manifest. Every file is checked before evaluation. A
replaced, recompressed, or rotated image requires a new version and hash.

The manifest must include:

- `schema_version`: currently `2`. Version 1 lacks per-image rights evidence and is no
  longer acceptable as a G3 release record. Migration requires checking every image;
  do not infer evidence from the old dataset-level declaration.
- `dataset`: name, version, rights basis, approved evaluation purpose, personal-data flag,
  and retention policy.
- `thresholds`: minimum sample size and release-quality thresholds.
- `cases`: stable IDs, relative paths, SHA-256 values, per-image rights evidence, scene tags,
  and human ground truth.

Every case's `rights` object records:

- `copyright_basis`: `self_owned`, `written_permission`, `open_license`, or `public_domain`;
  set `dataset.rights_basis` to `mixed` when cases use more than one basis.
- `author_or_rightsholder` and `verified_on`.
- A non-personal `permission_reference` for self-owned/written permission, or the original
  `source_url`, exact `license_identifier`, and `license_url` for open-license/public-domain
  sources.
- `depicts_identifiable_person` and the separate `subject_authorization`. An identifiable
  person requires `self` or `documented_consent`; an open license does not satisfy this field.
- `evaluation_use_approved=true` and `redistribution_allowed`. Even `true` does not instruct
  maintainers to commit raw images.

Search results, reposts, credit, thanks, or takedown promises alone are ineligible. A web image
must first be traced to its original asset page and verified field by field; otherwise keep it
outside the evaluation set.

Parts and colors must use canonical project names. `dominant_colors` may list up to three
acceptable colors; any top-three prediction match succeeds. Tags are lowercase ASCII for
stable aggregation.

## 2. Stratify the dataset

The first release baseline should contain at least 30 images without inflating the sample
with near-duplicate photos of the same person. Cover at least:

- full body, half body/close-up, seated, and occluded subjects;
- plain, cluttered indoor, and low-contrast backgrounds;
- with/without flared clothing, varied skin tones, and light/dark clothing;
- landscape, portrait, and EXIF-rotated phone photos.

The report emits `tag_counts`, but a release reviewer must judge whether the distribution
is meaningful and confirm that the test set was not used for targeted tuning.

Strict `--release` mode requires at least 30 distinct SHA-256 hashes and rejects duplicate
image content. Every case needs flare and dominant-color labels, with both flare classes.
Required scene groups: `full-body`; `half-body` or `close-up`; `seated` or `occluded`;
`plain-background`; `complex-background`; and `low-contrast`.
Hashes cannot detect cropped/transcoded near-duplicates, and tags require human review.

Strict thresholds are the higher of manifest values and these floors: 30 cases, 0.5 case
part recall, 0.6 macro F1, 0.8 case pass/flare/color accuracy, and 1.0 pattern validity and
complete Parade export rates. `release_readiness.automated_passed` reports automated
readiness separately from `summary.passed` quality metrics.

> **Known limitation (audit F-10)**: parts started from a ring or foundation chain (a
> separate skirt tube's waist) cannot yet be exported faithfully to Parade. Exporting them
> as a magic-ring `scNinc` would close the open tube into a flat disc, so these parts report
> `complete=False`. Because the release dataset must include skirt cases (flare accuracy) and
> the complete-Parade-export floor is fixed at 1.0, **a dataset with skirts cannot pass that
> floor automatically yet**. G3 can pass with skirts only after a faithful chain-ring start
> lands in the Parade exporter, or after that floor is explicitly lowered or waived for
> ring-start parts. Earlier versions counted these parts as complete and overstated G3 readiness.

`release_approved` remains false: photo authenticity, labels, rights evidence and physical
trials require review.

As of 2026-10-11, report schema 3 (input manifest remains 2) uses release policy 2.
Part precision/recall/F1 score final `params.parts`. Every case must agree across
analysis, structure and delivered part names, with matching structure/delivery quantities;
quantities follow the shared integer contract (1–20, no booleans or fractional values).
Only a delivered head/body with `type=onepiece` is expanded for comparison; the name alone is insufficient. Strict checks additionally require
part-set exact match >=0.8, recall >=0.8 for every expected part and each flare class,
at least five examples in each flare class and scene group, and delivered macro F1
strictly above a fixed head/body/arms/legs baseline. Metrics appear under
`release_readiness.quality_metrics`. These are engineering acceptance floors, not
measured accuracy claims. A dataset that merely ties the fixed template cannot establish
visual benefit and remains blocked. Older reports must be rerun.

## 3. Run and interpret exit codes

```bash
uv run crochet2pattern-eval \
  --dataset eval_data/release-01 --release \
  --out eval_outputs/release-01.json
```

- `0`: selected automated checks pass, including strict evidence checks with `--release`.
- `1`: invalid manifest, path, rights field, image, or hash.
- `2`: evaluation completed but quality or strict evidence checks failed.

`--allow-fail` keeps exit code `0` during exploration, but `summary.passed` remains false
and may not be used as release evidence. `--allow-fail` cannot bypass `--release` failures.
The real-photo pytest gate also uses strict mode.

Optional pytest gate:

```bash
CROCHET_EVAL_DIR=eval_data/release-01 \
CROCHET_EVAL_REPORT=eval_outputs/pytest-release-01.json \
uv run pytest -q tests/test_eval_real.py
```

## 4. Metrics

- `macro_part_f1`: macro-average per-image part-set F1; penalizes omissions and extras.
- `case_pass_rate`: rate of cases meeting part recall, annotated flare/color checks, and
  deterministic pattern validation.
- `flare_accuracy`: calculated only for cases with flare ground truth.
- `color_top3_accuracy`: calculated only for cases with dominant-color ground truth.
- `pattern_valid_rate`: rate passing stitch arithmetic and shaping gates; release default is 100%.
- `parade_export_rate`: rate exporting completely and passing the CrochetPARADE DSL syntax
  check; release default is 100%. It now contributes to per-case and overall `passed`.
- `parade_syntax_rate`: rate passing this project's emitter-level syntax check. A truncated
  prefix may pass, so this cannot replace complete export rate. Each case's `parade_export`
  includes completeness, exported/requested rounds, fully exported/requested physical
  parts, and warnings; counts include every copy of paired parts.

The 2026-10-04 fix prevents truncated exports from counting as successful. Earlier
syntax-only reports must be rerun before claiming 100% complete export. These checks
do not execute the third-party official parser.

These metrics measure software behavior from photo to pattern. They do not prove actual
size, yarn usage, time, or crochetability. Physical trials must independently record yarn
lot, measured gauge, actual size, materials, active time, and manual modifications.
