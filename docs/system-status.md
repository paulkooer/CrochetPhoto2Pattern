# System Status and Release Gates

[简体中文](system-status.zh-CN.md) | **English** | [Documentation index](README.md)

> Authoritative snapshot: 2026-10-17. Current behavior is defined by source code,
> `pyproject.toml`, `uv.lock`, and reproducible checks. Audit briefs are historical snapshots.

## Current conclusion

CrochetPhoto2Pattern is a **0.2.0-beta.2 engineering candidate**. Stitch arithmetic, input
gates, exports, and packaging have substantial automated coverage. An authorized
real-photo baseline and an independent physical-trial baseline are still missing, so the
project must not claim validated dimensions, material usage, time, or finished-item crochetability.

2026-10-17 local recognition and preview exports: segmentation seeds add a YCrCb chroma tier next to the luma tier (union, additive only), so a pale subject no longer loses foreground where its luma overlaps a translucent shadow. Ears are inferred only when the top rows split into ≥2 segments; ear width is the narrower lobe and ear length uses the measured **lower bound** `max(measured, 2.4×ear width)`, always generated as a long tube. Colour voting samples the lit surface only (pixels darker than the background **and part of a coherent area** count as shading) while review evidence keeps the complete interior pixels and region colours. The CLI gains `--preview` (.svg/.png, same renderer as the result page) and `--assemble` (CrochetPARADE assembly block); the result-page assembly preview and that block share one anatomical layout. New regressions cover chroma seeds, ear inference, lit-surface sampling, coherent shading versus thin stripes, output preflight and preview rasterisation (`tests/test_chroma_seeds.py`, `tests/test_ear_inference.py`, `tests/test_cli_preview_export.py`, and others). Full suite **1332 passed, 2 skipped, 1 failed**: the single failure is the pre-existing output-safety case that needs symlink privileges withheld on this Windows machine (it passes on Linux CI and is unrelated to this change); Ruff app/tests, mypy app (65 files) and diff checks pass. All runs above used local authorized or synthetic photos; originals are not committed. No real-photo accuracy evaluation, remote CI, or physical trial was run, and G3/G4 remain blocked. Band decisions got one more layer: an adjacent band is merged into the lit band's colour (never inventing a colour) only when all three hold — the luma ratio sits in the lighting-explainable window, the luma-normalised chromaticities agree, and the dark band's own yarn vote is not decisive. Black/white, white/light-grey and a genuine colour change are each blocked by one condition. Measured on the same photo, bands went from 3 to 1 and materials from two to one, and the independent checker passed all 59 rounds. Known boundary: a near-neutral two-tone (white + light grey) under strong uneven light splits its vote the same way and may still be merged into one colour; raw per-band counts stay in the evidence so review can undo it.

2026-10-15 foreground correction: add a local brush with add/erase, sizing, overlay toggle, 20-stroke undo and reset. Corrected masks independently update geometry, palette and generated bands before body selection. Corrections are bound to the crop and size-validated; backups and resizing retain them. Empty manual selections block generation, while explicit reset restores the original flow; users can create a selection after failed segmentation. Fourteen new regressions; final full suite **1252 passed, 1 skipped in 38.47s**, Ruff app/tests/scripts, mypy app/tests (123 files), JavaScript syntax and diff checks pass. Chrome verified brush/erase/continuous strokes/undo/reset, and an actual Streamlit page verified corrected generation and reset. An offline wheel built in a temporary directory contains editor/model assets byte-identical to the final working tree; CI now checks canvas inclusion. Temporary local test services were stopped. No new runtime dependencies, remote CI, real-photo accuracy evaluation or physical trials. Changes remain uncommitted and G3/G4 remain blocked.

2026-10-15 follow-up: add a user-selected body box, storing its full-image-coordinate profile separately from the original silhouette. Generation and resizing prefer that profile; vertical body spans are synchronized, and head review remains independent. Reject empty/tiny boxes, missing foreground, mock geometry, and imported box/span mismatches. Backups preserve the observation; compact shares do too, subject to existing URL limits. Eleven new regressions including AppTest interaction; full suite **1238 passed, 1 skipped in 39.34s**, Ruff app/tests, mypy app/tests (120 files), and diff checks pass. Results and exports identify the manual source. Selection cannot recover missing foreground or measure cm; colors only inherit the vertical interval. No real-photo accuracy evaluation, remote CI, or physical trial was run. Changes remain uncommitted and G3/G4 remain blocked.

2026-10-15: separate un-eroded geometry masks from cached interior color masks while retaining one segmentation per pipeline run. Both segmentation and background-distance fallback measure the longest contiguous foreground run per pixel row, avoiding the addition of detached arms to torso width. Eight new regressions; full suite **1227 passed, 1 skipped in 38.47s**, Ruff app/tests, mypy app/tests (119 files), and diff checks pass. Synthetic thin/body width ratio remains 0.20 (about 0.167 after the former erosion); equal-area layouts are distinguishable. This heuristic does not identify body regions or separate touching limbs. No real-photo accuracy evaluation, remote CI, or physical trial was run; changes remain uncommitted and G3/G4 remain blocked.

2026-10-14 follow-up: cloud LLM integration removed at the user's request. Photo, batch CLI and parser default to local analysis; credential/Base URL fields and AI mode are gone. Remove provider requests/retries, prompts and SDK dependencies: 13 packages removed from the lockfile (two SDKs plus 11 unused transitive packages). Historical provenance, usage and semantic colors remain compatible. `--local` is retained; library `ai` mode raises explicitly.

Final source validation: **1219 passed, 1 skipped in 63.59s; coverage 92.26%**. Repository Ruff, mypy app/tests (119 files), lock consistency and diff checks pass. Retired provider tests were removed and seven local-runtime/compatibility/dependency tests added. A clean wheel was checked for absence of old prompts and SDK dependencies; CI now asserts the same. No remote CI or physical trials; changes remain uncommitted, G3/G4 blocked. Optional pose support may still download weights; no LLM does not imply fully offline operation for every configuration.

After syncing the dev/pdf/pose environment to the lockfile, both SDKs are confirmed absent. Full suite in the actual SDK-free environment: **1219 passed, 1 skipped in 37.45s**.

2026-10-14 source review and profile fitting: replace the greedy clamp with constrained dynamic programming while preserving the first round and round count. Twelve of 18 synthetic cases reduce squared quantized stitch-count error; six straight profiles stay exact. Six new regressions include an independent exhaustive optimality oracle. Full suite: **1264 passed, 1 skipped in 42.12s**; changed-code Ruff and algorithm/diagnostic mypy pass. See [sources and LLM removal assessment](SOURCES.en.md#2026-10-14-symbol-and-profile-shaping-review) and [comparison](profile-fit-comparison-20261014.json). Provider interfaces, required SDKs and defaults remain. No cloud calls, photo-accuracy claim or physical trials; changes are uncommitted and G3/G4 remain blocked.

2026-10-11 review fixes preserve reviewed part selections, propagate manual head boxes
to color spans, and reject recognizable instruction/count contradictions at edit, import
and printable-export boundaries. Custom prose still needs manual review. Report schema 3 /
release policy 2 scores delivered parts, checks cross-stage counts, and adds exact match,
per-part/per-flare-class recall, five-case group minimums and a fixed-template baseline.
Nine new regressions; full suite **1201 passed, 1 skipped in 38.92s**; Ruff and mypy pass.
This is local evidence for an uncommitted working tree, not remote CI, package, cloud vision,
real-photo or physical-trial validation. G3/G4 remain blocked; prior G1/G2 passes do not
validate this working tree.

## Latest verification

2026-10-11 spatial-color follow-up: photo generation now retains complete per-band yarn
counts and up to 64 spatial regions, with mask provenance and omitted-region accounting.
The two original synthetic patch layouts remain identical as majority bands but now differ
in spatial observations. UI and printable exports flag unsupported local colorwork; backup,
size-change and bounded-share tests preserve the evidence. No in-round colorwork, applied
patch construction, improved segmentation or real-photo accuracy is claimed.
Eleven new regressions; **1227 passed, 1 skipped in 39.45s**, Ruff and mypy (117 files) pass.
See [comparison evidence](color-layout-observation-20261011.json). This is local verification
of uncommitted changes; release gates are unchanged.


2026-10-11 follow-up: unsupported anatomy no longer becomes a small sphere. Photo review
retains unknown labels for correction and blocks generation until the selection is supported
and nonempty; explicitly authored custom-structure backups remain importable. Instruction
checks now recognize standalone clauses, avoiding false positives about other rounds and
handling long decimal strings without integer conversion. Evaluation rejects boolean,
fractional and out-of-range quantities; head/body expansion requires a onepiece pattern.
Fifteen new regressions; **1216 passed, 1 skipped in 38.63s**, Ruff, mypy (115 files) and
diff checks pass. A mixed-shaping fixture now updates its stale no-shaping prose while
retaining the valid mixed-increase/decrease assertion. Changes remain uncommitted, with
no new cloud-vision, real-photo or physical-trial evidence.


2026-10-10: existing 15 photos drove a round-color algorithm change. Foreground yarn
coverage voting replaces mean RGB; both segmentation paths fill empty bands from the
nearest observed foreground band and validate mask dimensions. Image-relative coordinates
remain compatible with measured pose spans. Same-image, same-parameter reruns changed
colors in 14/15 cases (46 parts); arithmetic remains 15/15 and exact canonical part sets
remain 0/9. Bee output recovers black/gold and bear head output recovers gold. Bunny and
mermaid remain grey; cat still includes black/grey. Changes are not color accuracy scores.
Segmentation, shadows, horizontal detail and anatomy remain unresolved. See the
[paired comparison](public-pair-color-comparison-20261010.json).
Four regression tests added; full suite: **1192 passed, 1 skipped in 40.00s**. Ruff and mypy (113 files) pass.

A second acquisition batch adds five actual photo/pattern runs, bringing the total to
15 distinct photos across nine sites. All five pass arithmetic, with 0/3 exact canonical
part sets and two separately recorded boundary cases. A sixth mushroom candidate returned
HTTP 403 during acquisition and is not counted as tested. See the [second batch report](public-pair-probe-wave2-20261009.json).
Only evidence/docs changed this round; application/probe code and the prior full-suite
verification remain unchanged.

The 2026-10-09 paired-case fixes reject unsuitable head candidates before proportion
inference and retain silhouette flare only as a review hint. Photo review requires user
selection of one representable subject before generation; unknown, multiple or unsupported
selections disable the button. CLI/direct calls can still emit unreviewed templates with
explicit metadata and portable export notices. On the same ten cases, two false skirt
additions disappear and five of six head candidates are rejected; exact canonical-part
matches remain 0/6. See the [guarded report](public-pair-probe-guarded-20261009.json).
Eight regressions added; full suite: **1188 passed, 1 skipped in 36.20s**, including the
previous round's three probe tests. Ruff, mypy app/tests (113 files) and diff checks pass.
Changes are uncommitted; remote CI, package rebuilds and physical trials were not run.
G3/G4 remain blocked.

The same-day expansion covers 10 distinct photos from five publishers. All 10 pass
stitch validation, but canonical part sets match in 0/6 scored single-animal cases;
four boundary cases are kept separate. Bear/pigeon face boxes fall on legs/abdomen.
See the [expanded report](public-pair-probe-expanded-20261009.json) and [sources](SOURCES.md).
Three new probe-accounting tests, Ruff and script mypy pass; application code is unchanged.

A 2026-10-09 public photo/pattern pair probe actually ran two source-site photos:
AKIHIRO misses ears/tail, and Bunny misses ears and gains a skirt; both pass stitch
validation. See the [raw report](public-pair-probe-20261009.json) and [sources](SOURCES.md).
This tests only the local path, not cloud vision or physical results. These development
cases are not a release holdout. Application code is unchanged; the 1177-test snapshot
below is the previous run, not a newly executed full suite.

Further review fixes on 2026-10-09 paginate patterns above 500 physical rounds into
50-round pages with durable progress. CLI exports reject input/output aliases before
generation, prepare all formats and stage all files before replacement, and roll back
ordinary replacement failures. Failed rollback preserves recovery backups. Edit/undo/redo
prepare snapshots, metrics and progress before changing session state. Accessories follow
physical quantities while reusable tools remain single items. Evaluation adds `--release`
with content deduplication, complete labels, minimum scene coverage and fixed quality floors;
`--allow-fail` cannot bypass strict checks. Automated readiness is separate from release
approval; G3/G4 remain blocked. Multi-file exports are not crash-atomic as a group.
This round adds 25 regressions. Latest full suite: **1177 passed, 1 skipped in 35.85s**;
Ruff, mypy (111 files), and diff checks pass. Changes remain uncommitted; remote CI,
package rebuilds and physical trials were not run.

Further edit-consistency fixes on 2026-10-09 update the following round's generated
staggering hint when its preceding increase changes, while preserving unchanged custom
instructions. JSON downloads and history now use the applied pattern, matching Markdown,
backup and sharing; the editor labels unapplied drafts explicitly. Four regressions added.
Latest full suite: **1152 passed, 1 skipped in 33.22s**; Ruff, mypy (109 files), and diff
checks pass. Changes remain uncommitted; no real-photo or physical-trial evidence was added.

Further local optimization on 2026-10-09 caches Markdown/Parade exports by content,
within each session/result. Retained serialized UTF-8 values are capped at 2 MiB
(not a total Python heap cap). Content/provenance changes invalidate exports; replacing
a result purges its cache. Failures cannot reuse stale values; oversized outputs remain
downloadable without retention. Three identical full renders now invoke each exporter
once instead of three times. Online methods are labeled rule references, and Parade
export no longer implies that an external simulation ran. Latest full suite:
**1148 passed, 1 skipped in 32.40s**; Ruff, mypy (109 files), and diff checks pass.
Four cache regressions were added. Changes remain uncommitted; G3/G4 are unchanged.

The 2026-10-09 local fixes on `8b5b4f2` preserve round progress across yarn edits,
invalidate only changed parts (all progress for gauge changes), and restore progress
with undo/redo. Legacy backups containing `instances` are rejected before import;
ordinary legacy backups remain supported. Numeric round edits preserve recognized
finishing instructions; unfamiliar/custom instructions require a simultaneous text edit.
Derived assembly text is refreshed afterwards. Evaluation hashes and decodes the same
bounded byte snapshot. Local verification: **1144 passed, 1 skipped in 32.29s**, Ruff,
mypy app tests (107 files), and diff checks pass; 13 regressions were added. Coverage
was not remeasured. These changes are uncommitted; remote matrices, wheel/container
builds, online vulnerability audits, and physical trials were not rerun. Historical
release evidence below does not certify this working tree; G3/G4 remain blocked.
See the [review record (Chinese)](optimization-review-20260907.md).

> New in 0.2.0-beta.2: CrochetPARADE DSL export (`--parade` / result page) with the second-tier executable-correctness metric `parade_export_rate`, a structure-v2 3D preview, core-contract JSON Schemas (docs/schemas/) and a grid dithering option.

The current pre-PR checkout passes the complete local suite, Ruff, mypy, and diff checks.
The table below remains the latest published multi-Python/extras snapshot and is tied to its
named commit; the new branch must repeat the protected checks before merge.

The 2026-10-04 round-9 working tree fixes validation messages, rejects arithmetic
errors at edit/import/printable-export boundaries, validates nested imported metadata,
requires complete Parade exports for evaluation, and preserves source/version labels in
Markdown/PDF. History is now disabled by default; only trusted single-user installations
may set `CROCHET_HISTORY_MODE=single_user`. Shared deployments must keep it disabled.
This local snapshot precedes the GitHub publication PR. Remote matrix results must be
checked on that PR before merge; the table below remains historical commit-bound evidence.
Local validation: **1103 passed, 1 skipped in 48.39s** (Python 3.12.13); Ruff,
mypy app tests (99 files), schema-document synchronization and diff checks pass.
See the [review record (Chinese)](optimization-review-20260907.md).

The 2026-10-04 round-10 checkout adds photo crop/review, part forms and round-table editing,
bounded undo/redo, single-count yarn purchases with measured swatches, and runtime/API-attempt
diagnostics. It also corrects deployment-host privacy wording and removes uncalibrated confidence defaults.
Final local verification: **1131 passed, 1 skipped in 81.31s; 91.49% coverage** (Python 3.12.13).
Ruff, mypy app tests (105 files), schema-document synchronization, and diff checks pass.
The 28 new regressions cover review without another API call, crop invalidation, preserved results
on failures, undo/redo, yarn accounting, and budget boundaries. This snapshot does not substitute
for this PR's remote CI. Publication also updates only `urllib3` to 2.8.0 and `GitPython` to
3.1.62 for four newly reported GitHub alerts; pip-audit 2.10.1 finds no known vulnerabilities
after synchronizing locked core/dev/pdf/pose dependencies. The previous audit was merged through
[PR #10](https://github.com/paulkooer/CrochetPhoto2Pattern/pull/10).

The prior round-8 local snapshot was 1079 passed, 1 skipped (Python 3.12.13). The real-photo
skip still requires `CROCHET_EVAL_DIR`; no authorized-photo or physical-trial baseline is
present in this workspace. G3/G4 remain blocked. Earlier syntax-only Parade reports must
be rerun before claiming 100% complete export.

| Check | Result | Notes |
|---|---|---|
| Core | 739 passed, 1 skipped | remote Python 3.11–3.14 matrix; missing optional/runtime data skips by design |
| PDF extra | 741 passed, 1 skipped | Python 3.11; PDF tests execute, pose smoke and authorized photos skip by design |
| Pose extra | 738 passed, 2 skipped | Python 3.11; MediaPipe 1.0.1, EGL/GLESv2, and the real `mp.Image` bridge pass |
| Coverage | 89.9% | clean core environment; threshold is 80% |
| Static checks | Passed | `ruff check .` and `git diff --check` |
| Lock | Passed | `uv lock --check` |
| Dependency audit | Passed | combined environment has no known finding; GitHub marks the Protobuf high alert fixed |
| Wheel | Passed | metadata, MIT license, three CLIs, prompts, and curated evidence included |

Commit `bb24995` passed the real Python matrix
([run 33364513189](https://github.com/paulkooer/CrochetPhoto2Pattern/actions/runs/33364513189)),
PDF/pose extras
([run 33364513168](https://github.com/paulkooer/CrochetPhoto2Pattern/actions/runs/33364513168)),
and locked dependency audit
([run 33364673171](https://github.com/paulkooer/CrochetPhoto2Pattern/actions/runs/33364673171)).

## Release gates

| Gate | Status | Pass condition |
|---|---|---|
| G1 Reproducible source | **Historical pass; current tree pending commit/review** | reviewed commit, version, lock, changelog, and remote `main` agree |
| G2 Supported-version automation | **Historical pass; current tree pending remote checks** | core 3.11–3.14, PDF/pose, and security audit are green |
| G3 Authorized-photo baseline | **Blocked** | at least 30 stratified schema-v2 cases with per-image rights/subject evidence, passing all `evaluation.en.md` thresholds including 100% Parade export |
| G4 Physical-trial baseline | **Blocked** | isolated calibration and holdout pattern hashes pass `physical-trials.en.md` rules |
| G5 Distribution package | **Locally passed** | wheel content, metadata, CLIs, and package data validated |
| G6 Product claims | **Beta-compliant** | UI/docs/exports retain single-photo, template, estimate, and trial boundaries |

Do not create a formal release tag until G1–G4 pass. Synthetic inputs, web articles,
published yarn estimates, and more unit tests cannot substitute for authorized photos or
independent physical samples.

The repository has no corpus-ingestion, model-weight training, or fine-tuning pipeline.
Public pattern sources contribute narrowly extracted stitch/round facts to deterministic
reference tests; this does not make unlicensed web images eligible for G3.

## Delivered capabilities

- Local photo analysis, human review, manual input, and 2D grid entry points.
- Subject segmentation, profiles, palettes, optional pose landmarks, and versioned geometry.
- Gauge-driven round generation, six-section shaping, bridge logic, and deterministic gates.
- Materials, base time, assembly, ring charts, Markdown/PDF, history, and share links.
- Authorized-photo evaluation, physical-trial analysis, and non-calibrating external evidence.

## Remaining product boundaries

- One image cannot reliably recover the back, depth, hidden attachments, or absolute scale.
- Local vision may degrade on seated, occluded, close-up, multi-person, or low-contrast inputs.
- Yarn weight and time constants lack local independent calibration.
- Multi-view fusion, cross-device history, full internationalization, and GPU 3D
  reconstruction are not delivered.

## Reproduction commands

```bash
uv sync --locked --extra dev
uv run --locked --extra dev ruff check .
uv run --locked --extra dev pytest -q --cov=app --cov-report=term-missing
uv lock --check
uv build --wheel --out-dir dist/
uv run crochet2pattern-trials external-report --curated
git status --short
```
