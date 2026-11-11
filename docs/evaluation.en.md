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
The same formats as photo upload are supported: JPEG (`.jpg`, `.jpeg`) and PNG. WebP is
rejected during manifest validation.

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
part recall, 0.6 macro F1, 0.8 case pass/flare/color accuracy, and 1.0 pattern validity,
crochetability and Parade export rates. `release_readiness.automated_passed` reports automated
readiness separately from `summary.passed` quality metrics.

> **Ring starts (audit F-10, reported separately since policy 3)**: parts started from a
> ring or foundation chain (a separate skirt tube's waist) cannot yet be exported faithfully
> to Parade. Exporting them as a magic-ring `scNinc` would close the open tube into a flat
> disc, so they still report `complete=False`. The release dataset must include skirt cases,
> so policy 2's strict 1.0 complete-export floor was logically unreachable. Policy 3 records
> ring starts and cross-part reserved-loop joins as constructions the exporter declares
> unsupported (`parade_export.unsupported_constructions`); the floor requires everything else
> to translate completely, and `parade_complete_rate` still reports the strict rate. Once a
> faithful chain-ring start lands, these parts should export completely again.
>
> The default local runner always delivers the fixed head/body/arms/legs template and never
> delivers a skirt automatically. The review page may show a contour head, ears, a hem flare
> or a one-sided lower bump as hints, but it does not preselect them or write them into
> `analysis.parts` before confirmation. The macro-F1-above-template floor and flare-positive recall
> therefore keep G3 blocked until photo analysis recognizes parts beyond the template. That is
> the intended visual-benefit bar, not a calculation error.

`release_approved` remains false: photo authenticity, labels, rights evidence and physical
trials require review.

As of 2026-11-02, report schema 4 uses release policy 3 (input manifest remains 2; the new
crochetability threshold is optional). It adds the crochetability rate and reports declared
Parade constructions separately; rerun older reports. The default runner uses the product's
Q proportion style, recorded in `evaluator.proportion_style` (`null` for custom runners). The
rules below date from policy 2.
Since 2026-10-11, part precision/recall/F1 score final `params.parts`. Every case must agree across
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
- `crochetable_rate`: rate whose head and body (including a one-piece head section) have at
  least 18 stitches in the widest round. `min_crochetable_rate` defaults to, and is fixed for
  release at, 100%. Each case lists blocking, warning and note findings in `crochetability`.
  The default runner does not apply the generation gate, so degenerate results keep their other
  metrics instead of becoming pipeline errors.
- `parade_export_rate`: rate exporting everything except declared unsupported constructions
  and passing the CrochetPARADE DSL syntax check; release default is 100%. It contributes to
  per-case and overall `passed`.
- `parade_complete_rate`: strict complete-export rate, counting declared constructions as
  incomplete; reported for comparison only.
- `parade_syntax_rate`: rate passing this project's emitter-level syntax check. A truncated
  prefix may pass, so this cannot replace complete export rate. Each case's `parade_export`
  includes completeness, exported/requested rounds, fully exported/requested physical
  parts, and warnings; counts include every copy of paired parts.
  `exported_rounds` counts the rounds actually written into the DSL (including parts that
  are not faithfully expressed), while `exported_parts` counts only faithful, complete
  exports. The 2026-11-04 fix corrects a counting error: a declared unsupported
  construction (such as a separate skirt tube's ring start) used to be counted as a
  completely exported part, reporting 3/3 for three parts. Thresholds and the
  `unsupported_constructions` convention are unchanged.

### Part-level colour metrics (V1)

These are future measures defined in the [part-level colour selection specification](part-color-selection.en.md)
§9. Part-level ground truth and real user activity have not yet been collected; report
"not evaluated" whenever the required evidence is missing.

- `part_color_match_rate`: share of individually annotated parts or instances whose predicted
  colours match their corresponding human labels; missing or wrongly matched predictions fail.
  Denominator: parts or instances with comparable ground truth. Exclude and count missing
  labels; report "not evaluated" if all are missing. Report automatic and manually corrected
  results separately. Whole-image `dominant_colors` and Top-3 cannot substitute for part-level
  labels; new authorized annotations are needed.
- `manual_recolor_rate`: share of observable parts or instances recoloured at least once by a
  user in real sessions. Denominator: observable parts or instances in those sessions. Report
  "not evaluated" without real sessions or reconstructable actions. A missing `color_origin`
  is not proof of no edit, and a saved pattern alone cannot establish every past action; V1
  collects no telemetry.
- `color_correction_seconds`: actual elapsed time from seeing the generated colours to applying
  the final choice. Denominator: real user sessions that completed a colour choice.
  **Not collected in V1**; reported as "not evaluated" without real data. Any future collection
  must be local, clearly disclosed and explicitly opted into, never enabled by default.
- `color_consistency_rate`: share of parts and colour entries that agree on per-round colours
  and per-colour totals across the page, Markdown, PDF and the material list for one result.
  Denominator: parts and colour entries compared; a case missing one carrier is excluded and
  the reason recorded. Source: automated consistency assertions and browser-regression evidence.

The 2026-10-04 fix prevents truncated exports from counting as successful. Earlier
syntax-only reports must be rerun before claiming 100% complete export. These checks
do not execute the third-party official parser.

These metrics measure software behavior from photo to pattern. They do not prove actual
size, yarn usage, time, or crochetability. Physical trials must independently record yarn
lot, measured gauge, actual size, materials, active time, and manual modifications.
