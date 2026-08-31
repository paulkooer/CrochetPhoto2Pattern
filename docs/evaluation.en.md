# Authorized Real-Photo Evaluation

[简体中文](evaluation.md) | **English** | [Documentation index](README.md)

Real-photo evaluation runs only the local-vision path. It does not call OpenAI,
Anthropic, or a third-party relay. Photos, identifying filenames, and reports belong in
Git-ignored `eval_data/` and `eval_outputs/`. Manifest declarations are audit records;
they do not replace legally valid consent where required.

## 1. Create a dataset

```bash
mkdir -p eval_data/release-01 eval_outputs
cp docs/eval_manifest.example.json eval_data/release-01/eval_manifest.json
shasum -a 256 eval_data/release-01/standing-plain-001.jpg
```

Put the 64-character hash in the manifest. Every file is checked before evaluation. A
replaced, recompressed, or rotated image requires a new version and hash.

The manifest must include:

- `schema_version`: currently `1`.
- `dataset`: name, version, rights basis, approved evaluation purpose, personal-data flag,
  and retention policy.
- `thresholds`: minimum sample size and release-quality thresholds.
- `cases`: stable IDs, relative paths, SHA-256 values, scene tags, and human ground truth.

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

## 3. Run and interpret exit codes

```bash
uv run crochet2pattern-eval \
  --dataset eval_data/release-01 \
  --out eval_outputs/release-01.json
```

- `0`: valid manifest and every aggregate gate passes.
- `1`: invalid manifest, path, rights field, image, or hash.
- `2`: evaluation completed but quality thresholds were missed.

`--allow-fail` keeps exit code `0` during exploration, but `summary.passed` remains false
and may not be used as release evidence.

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

These metrics measure software behavior from photo to pattern. They do not prove actual
size, yarn usage, time, or crochetability. Physical trials must independently record yarn
lot, measured gauge, actual size, materials, active time, and manual modifications.
