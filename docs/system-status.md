# System Status and Release Gates

[简体中文](system-status.zh-CN.md) | **English** | [Documentation index](README.md)

> Authoritative snapshot: 2026-10-31. Current behavior is defined by source code,
> `pyproject.toml`, `uv.lock`, and reproducible checks. Audit briefs are historical snapshots.

## Current conclusion

CrochetPhoto2Pattern is a **0.2.0-beta.2 engineering candidate**. Stitch arithmetic, input
gates, exports, and packaging have substantial automated coverage. An authorized
real-photo baseline and an independent physical-trial baseline are still missing, so the
project must not claim validated dimensions, material usage, time, or finished-item crochetability.

## Latest reproducible validation

2026-10-31 independent garment gauges, based on PR #24 head
`a64490c9d5777c714a6c02e265197d836ec81228`: hats and separate skirt tubes can retain their
own swatches while other parts use the default. Attached skirts retain body gauge. Geometry,
color regions, shaping advice, materials, previews and exports use the selected gauge; same-color
yarn totals weight each part separately. Measured default-swatch weight does not cover differing
garment gauges. Explicitly pinning/unpinning equal values retains authored rounds and progress;
later default changes retain fixed garment values. New single-swatch trial records reject differing
gauges; use crochet projects for this work. Uniform trial identities and original evidence bytes
remain unchanged, including synthetic files generated with actual `a64490c` source.

Full suite: **2184 passed, 2 skipped in 74.18s**; repository-wide Ruff, mypy (182 files) and
diff checks pass (Python 3.12.13, locked dev+pdf). The two skips remain the absent authorized-photo
directory and optional MediaPipe. All **11 local Chrome full-app flows pass**, including actual
26×28 hat / 30×32 body downloads, retained head progress, trial gating and fresh-context project
recovery. Export cache is **12**, root backup schema remains 1; new per-part fields require a
supporting version for editing. This batch is a separate follow-up branch depending on unmerged
PR #24. These are developer checks; independent review is pending and remote CI must match this
batch's fixed head. Earlier PASS/CI results do not cover the new feature. Special accessories and
physical comparisons remain future work; Beta/G3/G4 are unchanged. See the
[garment guide](project-format.md#帽子与独立裙筒密度) and [browser guide](browser-regression.md).

2026-10-31 separate-head neck openings, continuing unmerged PR #24: generate an exact target
such as 16, retaining the crown and ending the decrease section with executable X/A operations
and an actual final joining row. Regressions cover closing again, authored legacy openings,
size/structure/gauge changes, trial recovery and contradictory saved metadata. Assembly and
Markdown/PDF use actual joining rows/counts and flag different counts for manual alignment.
Export cache is **11**. Full suite: **2156 passed, 2 skipped in 64.66s**, repository-wide Ruff,
mypy (180 files) and diff checks pass (Python 3.12.13, locked dev+pdf). Skips remain the absent
authorized-photo directory and optional MediaPipe. Ten local Chrome synthetic full-app flows
pass, including opening preview/apply, project download, fresh-context restoration and closing
again. These are developer checks; the final fixed version and remote browser, matrix, container
and audit results must match PR #24's current head, not the old `ebe18b8` checks or prior
independent PASS. Review now covers both edit preservation and separate-head openings. One-piece
work is excluded and oversized neck targets are rejected. No source-pattern round-count
replication or physical-result claim; per-part gauge and special accessories remain separate
work, and Beta/G3/G4 are unchanged. See the [opening guide](project-format.md#独立头部留口).

2026-10-31 resizing/edit preservation, based on `main` commit `0933d85`: retain authored
rounds, colors and notes when old/new generated constructions and actual loop-attachment
records agree. A head-diameter edit keeps the arm's authored ninth round. One-piece work,
inferred sizes and skirt joins participate in the comparison; unpinning rebuilds actual
reservations, while pinned placement continues to map. Changed global gauge or an unreproducible
legacy template retains full regeneration. Revalidate combined parts and refresh materials,
assembly and exports; no reduced template computation or physical-fit claim. Added **19 regressions**
including progress on both arms, preview/apply, undo/redo, project restoration and actual PDF
table input. Related join checks: **73 passed in 4.48s**. Full suite: **2100 passed, 2 skipped
in 61.59s**, repository-wide Ruff, mypy (177 files) and diff checks passing (Python 3.12.13,
locked dev+pdf). Skips remain the absent authorized-photo directory and optional MediaPipe.
These are developer checks; independent review is pending and remote results must match the
new PR head. Prior independent PASS/CI results do not cover this change. Per-part gauge,
connection-opening generation and special accessories remain separate work; G3/G4 are unchanged.
See the [editing details](project-format.md#尺寸编辑与手改保留).

2026-10-30 merge update: [PR #22](https://github.com/paulkooer/CrochetPhoto2Pattern/pull/22)
was squash-merged into `main` with maintainer authorization as
`44a79fc6ba09da4ddf86397761db39894565655e`. Its tree matches checked head
`4a63745d49721509e20e90d76b26f4feb0b54e8f`, whose **10 remote checks all passed**:
[core matrix, Docker and types](https://github.com/paulkooer/CrochetPhoto2Pattern/actions/runs/41069831004),
[PDF/pose](https://github.com/paulkooer/CrochetPhoto2Pattern/actions/runs/41069831902),
[dependency audit](https://github.com/paulkooer/CrochetPhoto2Pattern/actions/runs/41069832148), and
[browser regression and synthetic evidence](https://github.com/paulkooer/CrochetPhoto2Pattern/actions/runs/41069832349).
Browser CI passed the nine full-app flows and standalone canvas regression in Chromium
156.0.8078.4, recording both the PR head and actual checked-out merge-test commit, a clean
tree and no page errors. Post-merge and later-commit CI results are recorded against their own
SHAs and do not inherit these results. The new history-title fix has no independent acceptance
report; maintainer authorization to merge does not change that fact or extend the earlier
independent PASS for `55280fb`.

2026-10-30 browser/reference diagnostic batch, based on merged `36ce5d6`: **nine full-app
workflow checks passed** in desktop Chrome 156.0.8078.74, including actual upload, embedded
canvas, review, JSON/Markdown/PDF downloads, named-history save/undo, tab isolation, restoration
in a fresh context and invalid-import preservation. Fix a newly observed history-name loss and
add five name-lifecycle regressions; independent review of this new fix is pending and does not
inherit the prior PASS. Full suite: **2081 passed, 2 skipped in 67.13s**, Ruff, mypy (176 files)
and diff checks passing (Python 3.12.13, locked dev+pdf). Skips remain the missing authorized-photo
directory and optional MediaPipe. A new browser CI workflow must pass on this batch's PR head.
The locally supplied material is one reference design represented by 83 page images and four
PDFs, without user-taken finished-item photos or measurements. It was diagnosed privately;
source material and crops stay outside the public repo and CI and do not count toward G3/G4.
Priorities from that diagnostic are per-part gauge, explicit connection openings and special
structure templates before independent physical comparison. See the [browser guide](browser-regression.md).

## Independently accepted merged baseline

2026-10-30 final independent acceptance of software consistency fixes: commit
`55280fb485d9182f264402c52cbc171c957c4c51` received **PASS** for the original eight
issues and the two P2 / one P3 follow-ups; these software issues may close. The GPT Pro
report supplied by the maintainer records Python 3.12.14 with locked dev+pdf dependencies:
**2076 passed, 2 skipped in 89.35s**, Ruff, mypy (175 source files under repository settings)
and diff checks passing, with a clean review tree. Skips were the absent authorized-photo
directory and unmet MediaPipe EGL/GLESv2 conditions. The developer's separate run on the
same commit yielded 2076 passed, 2 skipped in 57.25s (Python 3.12.13, MediaPipe not installed).
Export cache is now **version 10**; backup schema remains version 1. No public remote CI
results existed for that SHA when the reviewer queried it; merging requires the repair PR's
current head checks. That acceptance round did not run real-browser tests; subsequent synthetic
browser coverage is recorded above. Authorized photos, physical trials, other browser platforms
and real-photo browser scenarios remain separate work; Beta status and G3/G4 are unchanged.
See the [acceptance handoff](audit-fix-review-20261030.md).

## Historical validation records

The dated entries below preserve their original commits, environments and results.
Statements about pending commits or CI describe those rounds only. Consult the current
conclusion, latest validation entry and release-gate table for the merged baseline.

2026-10-30 shaping interval checks: reject unequal actual gaps with a correct average and
non-integral averages previously left unchecked. Explicit one-step interval claims now inspect
the compact operation tree, including the round boundary, while accepting staggered groups,
nested repeats, FLO/BLO and invisible decreases. W/M cannot claim a one-stitch change.
A 100,000-stitch case needs no repeat expansion. Export cache **version 9** revalidates old outputs.
Added **34 regressions**, including an independent expanded-sequence property oracle, large
rounds, edit/import/export gates, cache invalidation and UI failure preservation with correction/retry.
Full suite: **2043 passed, 2 skipped in 105.65s, coverage 94.22%** (Python 3.12.13, isolated
locked dev+pdf environment). Skips are the absent authorized-photo directory and optional mediapipe.
Repository-wide Ruff, mypy app/tests (173 files) and diff checks pass. No dependency or project-format
changes; no new real-browser, authorized-photo or physical-trial evidence, so G3/G4 remain unchanged.
Consult this repair PR's checks for remote results. See the
[Chinese validation guide](project-format.md#导入校验与编辑保留).

2026-10-29 GitHub main synchronization: [PR #18](https://github.com/paulkooer/CrochetPhoto2Pattern/pull/18)
merged into `main` as `4a19d70`; post-merge CI, extras and dependency-security checks passed.
Statements below about uncommitted/unpushed work remain historical records of their respective rounds.

2026-10-29 whole-round prose checks: reject shaping claims when the formula contains no
corresponding increases/decreases, and cross-check outer repetition counts, direction and
every-stitch wording. Compare normalized decimal strings so 5,000-digit claims return bounded
diagnostics while correct zero padding remains usable. Conditional/future-round prose and
unrecognized techniques retain their manual-review boundary. Added **31 regressions** for
contradictions, excessive digits, valid claims, edit/import/export gates, UI failure preservation
and correction/retry. Related checks: **147 passed in 4.41s**. Full suite: **2009 passed,
2 skipped in 162.90s, coverage 94.20%** (Python 3.12.13, isolated locked dev+pdf environment).
Skips are the absent authorized-photo directory and optional mediapipe. Ruff, mypy app/tests
(172 files) and diff checks pass. No dependencies or pattern/project formats changed; export
cache remains version 8. Consult feature-branch PR checks for remote results. No new authorized
photo, real-browser or physical-trial evidence; G3/G4 remain unchanged. See the
[Chinese validation guide](project-format.md#导入校验与编辑保留).

2026-10-29 trial identity fixes following review of Opus commit `83d7a50`: restore legacy ZIPs,
detect mixed-age source overlap and reject diversity created only by reordering parts. Verify
exact source SHA, original metadata, legacy fingerprints and sidecar binding before migration;
retain source bytes, observations and partial measurements. Algorithm version 1 conservatively
canonicalizes gauge and physical round-sequence multiplicity while ignoring labels, order and
equivalent copy grouping. Always check source overlap; unverified legacy identity remains
reportable but cannot establish readiness. Add standalone `migrate` with input protection and
rollback on output replacement failure. Added **25 regressions**, with frozen synthetic fixtures
from pre-fingerprint and unversioned implementations, UI restoration and CLI gate checks.
Related checks: **152 passed in 6.43s**. Full suite: **1978 passed, 2 skipped in 101.83s,
coverage 94.17%** (Python 3.12.13, dev+pdf). Skips are the absent authorized-photo directory
and optional mediapipe. Ruff, mypy app/tests (171 files) and diff checks pass. Trial/report root
schemas remain 2/3, with an optional fingerprint version; standalone legacy records can be
migrated using their exact source. These are local checks; consult the repair PR for remote
matrix, container and security results. G3/G4 remain unchanged. See the
[Chinese migration guide](physical-trials.md#升级旧试钩记录).

2026-10-29 progress isolation and bulk operations: disambiguate custom names such as
`practice_copy2` that previously aliased another part's physical copy, causing duplicate widgets
and restoration of one completion as two. Inline/paginated views, saving, restoration, edits and
undo share the complete pattern's identifier mapping; stale-round cleanup preserves similarly
named parts' valid progress. Use callbacks before rendering for bulk completion, reset and resume
navigation to preserve other parts' progress and project notes across reruns. Added **15 regressions**,
including property tests and AppTest; related checks: **101 passed in 29.60s**. Repository-wide
Ruff, mypy app/tests (164 files) and diff checks pass. Full suite: **1883 passed, 1 skipped in
120.45s, coverage 94.10%** (Python 3.12.13). No dependencies, project formats or saved
part/instance/round identities changed. Previously misrecorded completions require review against
the physical work before resaving. No new wheel build, real-browser checks, authorized-photo
evaluation or physical trials; G3/G4 remain unchanged. These results are from local verification;
consult GitHub Actions for remote CI after submission. See the
[Chinese isolation guide](project-format.md#名称相似的部件与进度隔离).

2026-10-29 grid generation and failure preservation: convert assignment indices from NumPy
scalars to native integers in plain and dithered generation, fixing project JSON serialization
errors that interrupted UI generation. Prepare complete previews, legends, written/C2C charts,
Markdown and project JSON before changing the grid or histories during generation, restoration,
cell/rectangle recoloring and undo/redo. Preparation failures retain the grid, inputs and both
histories for retry. Prepare history copies, reset coordinates/history only on successful
replacement, and retain redo for no-op edits. Added **30 regressions**, covering both sampling
and quantization choices, renderer/export failure injection, corrupt snapshots, rectangle
inputs, retries, download alignment and Photo/trial state isolation. Full suite: **1868 passed,
1 skipped in 116.72s, coverage 94.05%** (Python 3.12.13). Repository-wide Ruff, mypy app/tests
(163 files) and diff checks pass. No dependencies changed; grid projects remain format 1.0 and
pattern/crochet-project formats are unchanged. No new wheel build, real-browser checks,
authorized-photo evaluation or physical trials; G3/G4 remain unchanged. Changes are local and
uncommitted, with no new remote CI. See the [Chinese grid-project guide](project-format.md#平面网格工程与修色历史).

2026-10-29 technique and chart consistency: preserve `inv-sc2tog` in the operation tree,
iteration and canonical notation rather than merging it with ordinary A/sc2tog due to equal
2→1 arithmetic. Counting, edits and backups remain compatible. The current DSL subset stops
at invisible-decrease rounds and reports partial export; Markdown retains explicit technique
or requests review, PDF keeps original notes, and diagrams request review. Automatic skirt
reservation rejects these techniques while preserving the current pattern on failure. Ring
charts, symbol strips and truncated headings retain actual round labels, with positional
fallback for legacy missing labels and safe empty display windows. Export cache version is **7**.
Added **25 regressions**; full suite: **1838 passed, 1 skipped in 111.52s, coverage 93.47%**
(Python 3.12.13). Repository-wide Ruff, mypy app/tests (162 files) and diff checks pass. No
dependencies or pattern/project formats changed. No new wheel build, real-browser checks,
external simulation, authorized-photo evaluation or physical trials; G3/G4 remain unchanged.
Changes are local and uncommitted, with no new remote CI. See the
[rule review](SOURCES.en.md#2026-10-29-invisible-decrease-identity-and-round-label-consistency)
and [Chinese compatibility notes](project-format.md#隐形减针与图示圈号).

2026-10-29 GitHub-informed stitch-parent inspection: add an opt-in adjacent-round diagram and
table informed by CrochetPARADE/stitch-grapher connectivity and explicit technique conventions
in grid projects. Preserve X/V/A/W/M order and FLO/BLO scope; require a complete formula that
matches both rounds. Show 24 operations per page and skip repeated subtrees by counts, including
a final-page test with 100,000 produced stitches. SVG/JSON downloads match the selected window;
JSON identifies its range, coverage and pattern hash, omitting private progress and notes.
Explain first rounds, absent formulas and unsupported techniques; associations do not describe
yarn paths, physical shape or tension. Added **35 regressions**, including property tests and
AppTest. Related checks: **215 passed in 10.04s**. Full suite: **1813 passed, 1 skipped in
120.81s, coverage 93.46%** (Python 3.12.13). Repository-wide Ruff, mypy app/tests (161 files)
and diff checks pass. No dependencies or pattern/project formats changed. No new wheel build,
real-browser checks, upstream parser/simulation runs, authorized-photo evaluation or physical
trials; G3/G4 remain unchanged. Changes are local and uncommitted, with no new remote CI.
See the [project comparison](SOURCES.en.md#2026-10-29-github-comparison-and-stitch-parent-inspection)
and [Chinese user guide](project-format.md#逐针连接核对).

2026-10-29 result replacement state cleanup: release the old pattern's leg-join restore preview,
inputs and part selections, and match complete result-ID boundaries to retain other results with
the same ID prefix. Replace preview and calculation output together to clear old comparison
controls after edits and allow continued entry. Added 6 regressions; AppTest covers Photo/Manual
yarn edits, continued entry, undo, failed-import preservation, successful-import cleanup, and
isolation of progress, notes and the other tab's plan. Full suite: **1778 passed, 1 skipped in
110.63s, coverage 93.39%** (Python 3.12.13). Repository-wide Ruff, mypy app/tests (157 files) and
diff checks pass. No dependencies or file formats changed. No new real-browser checks,
authorized-photo evaluation or physical trials; G3/G4 remain unchanged. Changes are local and
uncommitted, with no new remote CI. See the [Chinese session guide](project-format.md#手动规划锁针并腿).

2026-10-28 stable leg-join comparison selections: track selected parts by name, retain selection
when reordered, clear and prompt after removal or rename, and recheck when copy counts change.
Users must still confirm selections against the physical work; selections are not saved in the
plan. Added 3 regressions; plan tests: **60 passed in 8.84s**; full suite: **1772 passed,
1 skipped in 102.47s, coverage 93.39%**. Repository-wide Ruff, mypy app/tests (157 files) and
diff checks pass. No new dependencies, real-browser checks, authorized-photo evaluation or physical
trials; G3/G4 remain unchanged. Changes are local and uncommitted, with no new remote CI. See the
[Chinese planning guide](project-format.md#手动规划锁针并腿).

2026-10-28 leg-join technique reminders: pattern comparison flags later rounds and selected-round
wording mentioning finishing for manual review. Matching numbers establish only agreement with
the pattern record, not an actual opening or feasible join. Added 3 regressions; related checks:
**89 passed in 6.83s**; full suite: **1769 passed, 1 skipped in 110.94s, coverage 93.38%**.
Repository-wide Ruff, mypy app/tests (157 files) and diff checks pass. No new dependencies,
real-browser checks, authorized-photo evaluation or physical trials; G3/G4 remain unchanged.
Changes are local and uncommitted, with no new remote CI. See the
[Chinese planning guide](project-format.md#手动规划锁针并腿).

2026-10-28 leg-join restoration preview: compare current and proposed fields before applying or
cancelling. Changes to source bytes, restore method or current input invalidate the preview and
preserve the input. Previews are session-only and do not modify patterns or progress; openings and
direction still need manual review. Added 5 regressions; related checks: **86 passed in 6.91s**;
full suite: **1766 passed, 1 skipped in 126.95s, coverage 93.38%**. Repository-wide Ruff,
mypy app/tests (157 files) and diff checks pass. No new dependencies, real-browser checks,
authorized-photo evaluation or physical trials; G3/G4 remain unchanged. Changes are local and
uncommitted, with no new remote CI. See the [Chinese planning guide](project-format.md#手动规划锁针并腿).

2026-10-28 leg-join count diagram: a valid plan displays both openings, the two chain sides and
the resulting round count; an SVG download follows the current inputs. It explicitly does not
depict physical proportions, stitch positions or direction, and does not change patterns or
projects. Added 3 regressions; related checks: **81 passed in 5.31s**; full suite: **1761 passed,
1 skipped in 139.00s, coverage 93.36%**. Repository-wide Ruff, mypy app/tests (157 files) and
diff checks pass. No new dependencies, real-browser checks, authorized-photo evaluation or
physical trials; G3/G4 remain unchanged. Work is local and uncommitted, with no new remote CI.
See the [Chinese planning guide](project-format.md#手动规划锁针并腿).

2026-10-28 compare manual leg-join plans with current pattern: select the corresponding left/right
parts and compare round numbers and stitch counts. Both sides selecting one part require at least
two copies. Missing rounds, mismatches and insufficient copies are reported. Comparison changes
neither pattern, progress nor plan, and does not verify physical openings, markers, direction or
feasibility. Added 11 regressions; plan tests: **46 passed in 1.95s**; full suite: **1758 passed,
1 skipped in 99.38s, coverage 93.35%**. Repository-wide Ruff, mypy app/tests (156 files) and diff
checks pass. No new dependencies, real-browser checks, authorized-photo evaluation or physical
trials; G3/G4 remain unchanged. Work is local and uncommitted, with no new remote CI. See the
[Chinese planning guide](project-format.md#手动规划锁针并腿).

2026-10-28 restore manual leg-join plans: upload or paste a saved plan and validate size, version,
fields, marker ranges and recomputed totals before replacing form inputs. Corrupt, duplicate,
invalid or inconsistent data preserves current input. Successful restoration leaves pattern and
progress unchanged; standalone plans are not bound to a pattern and require manual verification.
Added 19 regressions; related checks: **67 passed in 3.63s**; full suite: **1747 passed, 1 skipped
in 96.16s, coverage 93.32%**. Repository-wide Ruff, mypy app/tests (156 files) and diff checks pass.
No new dependencies, real-browser checks, authorized-photo evaluation or physical trials; G3/G4
remain unchanged. Changes are local and uncommitted, with no new remote CI. See the
[Chinese planning guide](project-format.md#手动规划锁针并腿).

2026-10-28 manual chain-bridge leg-join planning: a separate aid records two leg opening rounds,
stitch counts, markers and chain count, then calculates the joining round with one single crochet
per opening stitch and on each side of every chain. Download the plan as standalone JSON. Users
provide the references; the tool does not verify real openings or automatically generate a join.
It leaves pattern/progress intact and cannot be imported as a project. Synthetic examples were
used without copying the source images or instructions. Added 16 regressions; related tests:
**48 passed in 3.21s**; full suite: **1728 passed, 1 skipped in 96.99s, coverage 93.28%**.
Repository-wide Ruff, mypy app/tests (156 files) and diff checks pass. No new dependencies,
real-browser checks, authorized-photo evaluation or physical trials; G3/G4 remain unchanged.
Changes are local and uncommitted, with no new remote CI. See the
[Chinese planning guide](project-format.md#手动规划锁针并腿).

2026-10-28 trial save history: independent undo/redo restores forms, swatches, yarn, partial
measurements, completion status, comparisons and downloads together, preserving the live pattern,
progress and project notes. Unsaved or invalid input blocks switching and is retained. Identical
saves preserve redo; changed saves after undo clear it. Session-only history shares one source
pattern and retains at most eight snapshots and 2 MiB combined; reopen/close clears it, and ZIPs omit it.
Added 17 regressions covering capacity limits, corrupt identity/metadata, atomic save failures,
and AppTest form/download synchronization, input protection and reopening. Full suite:
**1712 passed, 1 skipped in 97.37s, coverage 93.24%**. Repository-wide Ruff, mypy app/tests (153 files)
and diff checks pass; all 81 application files in the offline wheel match source byte-for-byte.
No dependency or format changes, new real-browser checks, authorized-photo evaluation or physical
trials; G3/G4 remain unchanged. Local checks cover this submission; remote status is tracked by
the latest commit's Checks on [PR #18](https://github.com/paulkooer/CrochetPhoto2Pattern/pull/18).
See [saved-record history](physical-trials.en.md#undo-or-redo-saved-records).

2026-10-28 partial trial drafts: save and resume dimensions, yarn, timing and notes in stages.
Keep fields visible across completion-state changes and retain observations when returning to
draft. Completion dates remain blank until entered. Completed records still enforce measured
swatches and required observations; partial data is excluded from finished-item comparisons and
calibration. Optional schema-1 `draft.json` binds the exact formal trial JSON bytes, with separate
size/type/range checks; formal trial schema remains 2. Old two-file bundles remain readable;
three-file draft restoration requires this version. Publish the draft Schema with drift checks.
Added 26 regressions; full suite: **1695 passed, 1 skipped in 90.07s, coverage 93.17%**. Repository-wide
Ruff, mypy app/tests (151 files) and diff checks pass; all 80 application files in the offline wheel
match source byte-for-byte. AppTest covers partial input, status toggles, fresh-session recovery,
completion, return to draft and atomic restore failures. No new real-browser screenshots or
physical-trial evidence; G3/G4 stay unchanged. No new dependencies; work remains uncommitted and
unpushed, without new remote CI. See the [draft workflow](physical-trials.en.md#record-and-restore-in-the-web-ui).

2026-10-27 measured-density workflow: compare saved swatches, height, yarn and timing with the
original pattern, keeping unmeasured/missing values explicit and full-project time separate from
the baseline. Preview regenerating the source pattern at measured density while retaining target
dimensions, structure, yarn specifications and pinned waist placement. Previews show density and
progress changes; application clears affected completion marks, with undo/redo restoring work.
Trial records/downloads remain unchanged. Added 22 regressions; related checks: **105 passed in
5.82s**. Full suite: **1669 passed, 1 skipped in 87.65s, coverage 93.12%**. Repository-wide Ruff,
mypy app/tests (149 files) and diff checks pass; the offline wheel's 79 application files match
source byte-for-byte. AppTest covers preview/cancel/apply/undo/redo, saved-only inputs and source
mismatch disabling; separate/one-piece waist references pass regressions. No new real-browser
screenshots or physical evidence; G3/G4 remain unchanged. Formats, dependencies and global estimate
constants are unchanged. Work remains local and uncommitted, without new remote CI.
See the [measured-density guide](physical-trials.en.md#compare-measurements-and-regenerate-at-measured-density).

2026-10-27 web trial records: add swatch/yarn drafts and completed observations for dimensions,
yarn, scoped timing and modifications, with a height-deviation display. ZIP bundles retain the
exact original pattern and schema-2 record. Open both from the sidebar in a fresh session, or
restore only the record within a result panel. Live edits cannot silently rebind old trials.
Verify hashes and source metadata with bounded archive reads; failures retain existing patterns,
progress and notes. CLI/UI draft creation uses one byte snapshot, and downloaded records work
with existing analysis tools. Added 33 regressions; full suite: **1647 passed, 1 skipped in 86.06s,
coverage 93.10%**. Repository-wide Ruff, mypy app/tests (147 files) and diff checks pass. The offline
wheel contains 78 application files byte-identical to source. AppTest covers fresh-session restore,
editing/saving, source differences, tab isolation and atomic import failure. No new real-browser
screenshots, physical measurements or authorized-photo evidence; G3/G4 remain unchanged.
No new dependencies or schema changes. Work remains uncommitted/unpushed, without new remote CI.
See the [web trial guide](physical-trials.en.md#record-and-restore-in-the-web-ui).

2026-10-27 waist preference persistence: fix manual waist choices reverting to automatic placement
after size or structure regeneration. Save a relative candidate position, map it to the nearest
new candidate, and retain the original fraction across repeated resizes to avoid rounding drift.
Pattern backups and projects retain the preference. Preview pinning the current waist or unpinning
it; policy-only changes preserve current stitches, references and progress, with undo support.
Removing the skirt drops its preference; invalid values and missing attachment context are rejected.
Added 36 regressions covering separate/one-piece bodies, both regeneration paths, repeated resizes,
backup/project restoration and AppTest pin/unpin/undo flows. Full suite: **1614 passed, 1 skipped
in 90.48s, coverage 92.98%**. Repository-wide Ruff, mypy app/tests (144 files) and diff checks pass.
The offline wheel contains 76 application files byte-identical to source. This follow-up uses
AppTest for interactions; the real Chrome check below was not repeated. Changes remain local and
uncommitted, without new remote CI, dependencies, real-photo or physical-trial evidence.
Format versions are unchanged; see the [waist preference guide](project-format.md#保存腰位偏好).

2026-10-27 edit impact and waist placement: retain completed rounds before the first change;
preview part, round, size and advanced JSON edits with affected ranges and retained/cleared counts.
Apply previews and undo/redo before rendering. The skirt editor shows a connection schematic,
restores generated reservations and recomputes generated waist shaping when necessary, rejecting
unsafe custom rewrites or occupied loops. SVG and Markdown/PDF sequence tables use the same data.
Added 33 regressions, including version-5 cache invalidation; full suite: **1578 passed, 1 skipped
in 89.95s, coverage 92.91%**. Repository-wide Ruff, mypy app/tests (143 files) and diff checks pass.
An offline wheel contains 76 application files byte-identical to source. Real Chrome reopened
a synthetic project and moved the waist from round 12 to 7: the preview identified body changes
from round 8, application retained earlier progress and cleared two affected completed rounds,
and undo/redo restored the correct references. See [waist placement](images/waist-edit-synthetic.png)
and [edit impact](images/edit-impact-synthetic.png). These changes remain local and uncommitted;
no new remote CI, dependencies, real-photo evaluation or physical trials. Pattern/project formats
are unchanged; export cache version is 6. See the [project guide](project-format.md).

2026-10-26 GitHub sync: saved projects, skirt joins and progress continuity updates use
`feat/stitch-notation-fidelity` and [PR #18](https://github.com/paulkooer/CrochetPhoto2Pattern/pull/18).
The uncommitted/unpushed statements below describe each local verification snapshot;
current commits and remote check results are available on that PR.

The first remote run showed that Python 3.14 can decode the test's 10,000 nested arrays
before correctly rejecting the non-object root. Replace that interpreter-specific recursion
assumption with an injected decoder `RecursionError`, preserving application validation.
Related backup/project tests: **41 passed in 4.23s**; Ruff, mypy and diff checks pass.
Local Python 3.14.4 reproduces the original difference and verifies exception translation.
Final cross-version results are recorded in the PR's latest Checks.

2026-10-26 progress continuity review: fix order-dependent retention of outer-layer progress
in deeper reserved-loop join chains. Collect direct changes before propagating all effects;
retain independent parts and unchanged foundations. Paginated patterns now identify the next
unfinished copy/round and provide a navigation button. Empty imported colors no longer appear
as `None` in paginated round labels. Added 10 regressions; full suite:
**1545 passed, 1 skipped in 76.47s; coverage 92.82%**. Repository-wide Ruff, mypy app/tests
(138 files) and diff checks pass. Real Chrome imported a synthetic project with 307 completed
rounds and navigated to copy 2, round 8: the preceding seven rounds on that page remained checked
and round 8 remained unchecked. See the [resume screenshot](images/progress-resume-synthetic.png).
An isolated offline wheel build contains 73 application files byte-identical to source.
Project formats and dependencies are unchanged. This round remains uncommitted and unpushed,
with no remote CI, real-photo evaluation or physical trial performed.

2026-10-26 skirt joins and saved projects: bind skirt foundations to actual body rounds
and explicitly reserve their back loops with FLO operations in the following round.
Use merged one-piece numbering and recompute after resizing. Check references, ranges,
copy counts, structure-graph consistency and cyclic dependencies. Render Markdown/PDF
assembly from current references; flag legacy patterns without exact records for review.
Projects save per-copy progress, personal notes and a pattern revision; validate the binding
before import, report affected progress resets after editing, and restore progress with undo.
See the [user guide](../README.md#save-and-reopen-a-pattern) and [format details](project-format.md).

Added 54 regressions. Full suite: **1535 passed, 1 skipped in 74.50s; coverage 92.81%**.
Final repository-wide Ruff, mypy app/tests (137 files), 38 attachment regressions and diff
checks pass. Real Chrome selected different rounds on two arms, entered notes, downloaded
the actual project JSON and reopened it in a fresh session. Both physical-copy selections
and notes were restored without page exceptions; see the [save dialog](images/project-save-synthetic.png).
An isolated offline wheel rebuild contains 73 application files byte-identical to final source.
No runtime dependencies were added. Changes remain uncommitted and unpushed, with no new
remote CI run. Placement is still a template choice, DSL lacks cross-component reserved-loop
joins, and no new real-photo or physical-trial evidence was obtained; G3/G4 are unchanged.

2026-10-25 recovery and printed-guidance review: open complete backups directly from
the sidebar using a file (20 MiB) or pasted JSON (2 MiB), without a seed pattern or
enabled history. Validate encoding, JSON and pattern data before replacing the target
result; errors preserve current work. Share UI/Markdown/PDF guidance, distinguish
ordinary/invisible decreases, include loop definitions and follow explicit placement.
Cache format 4 requires old PDFs to be regenerated; the backup schema is unchanged.
See [recovery instructions](../README.md#save-and-reopen-a-pattern) and
[source review](SOURCES.en.md#2026-10-25-printed-legends-and-placement-guidance).

Added 32 regression cases; final full suite: **1481 passed, 1 skipped in 71.26s;
coverage 92.70%**. Repository-wide Ruff, mypy app/tests (132 files), offline lock
consistency and diff checks pass. Real headless Chrome verified a fresh-session BOM
JSON upload, restored FLO instructions and an exception-free page, using only synthetic
data; see the [recovery screenshot](images/backup-open-synthetic.png). An isolated offline
wheel build contains 70 application files byte-identical to the final source, including
both new backup modules. Test services are stopped. This round remains uncommitted
and unpushed, with no new remote CI run. No dependencies, real-photo or physical-trial
evidence were added; G3/G4 remain unchanged.

2026-10-25 pre-publication verification: **1449 passed, 1 skipped in 67.95s;
coverage 92.56%**. Repository-wide Ruff, mypy app/tests (128 files), offline lock
consistency and diff checks pass. An isolated wheel build in a temporary directory
contains 68 application files byte-identical to the working tree, including the notation
parser, canvas and data resources; metadata and CLI entries match the package contract.
Headless Chrome captured the [synthetic component preview](images/stitch-notation-synthetic.png),
visually checked for ordinary/local/whole-round loop placement and corresponding DSL.
No third-party images were used. Branch, PR and remote CI status are recorded on
[GitHub](https://github.com/paulkooer/CrochetPhoto2Pattern); statements such as
"uncommitted" below describe their respective historical verification snapshots.
No runtime dependencies, real-photo or physical-trial evidence were added; G3/G4 are unchanged.

2026-10-24 loop scope: Supergurumi patterns, PlanetJune comparisons and the official
CrochetPARADE HTML manual inform scoped/local FLO/BLO expressions and standalone
whole-round directives. Retain counts and qualifiers through validation, Markdown,
F/B chart labels and qualified DSL shaping. Reject conflicting scopes; unresolved loop
prose remains usable manually but stops the affected part's DSL export. Do not guess
a foundation for first-round loops or mistake generated tail closures for FLO crochet.
Correct bee fixture/glossary FLO/BLO labels and explicitly report inferred placement
in other aggregate rounds. Cache format 3 invalidates old exports; regression coverage
includes edits, backups, printable exports and the calculator.
Added 66 regression cases; final full suite: **1449 passed, 1 skipped in 69.10s;
coverage 92.56%**. Ruff app/tests/scripts, mypy app/tests (128 files) and diff checks pass.
See [online sources and scope](SOURCES.en.md#2026-10-24-online-references-and-loop-scope).
No dependencies or source images were added. No official parser execution, external
simulation, physical trial, photo-accuracy evaluation, remote CI or package rebuild
was performed. Changes are uncommitted; G3/G4 remain blocked.

2026-10-24 follow-up: preserve explicit stitch order across Markdown, symbol strips
and CrochetPARADE. Support mixed shaping, W/M and nested groups without expanding
large repeats; retain one source round per DSL line. Contradictions stop the affected
part at its valid prefix, and aggregate-only inferred placement is counted separately.
Generated consecutive +6 rounds now specify center/end placement directly, replacing
vague shift hints. Numeric edits update neighboring generated instructions while retaining
finishing notes; legacy imports keep their original text. Version export caches independently
and reuse compiled rounds across physical copies. Sixty-six new regressions cover ordered
DSL/chart comparisons, bounded rendering, all gauge/head-mode/construction combinations,
legacy edits, colors and cache upgrades. Final full suite: **1383 passed, 1 skipped in
67.40s; coverage 92.49%**. Ruff app/tests/scripts, mypy app/tests (127 files) and diff
checks pass. See [before/after cases](SOURCES.en.md#2026-10-24-stitch-order-and-export-consistency).
No external simulation, physical trial, photo-accuracy evaluation, remote CI or package
rebuild was run. Changes are uncommitted; G3/G4 remain blocked.

2026-10-24 round notation: local JOLA reference images informed checks for complete
X/V/A/W/M and US short-stitch expressions, repeat groups and split shaping positions.
Edits, backup imports and Markdown/PDF exports now reject mismatches in consumed
stitches, output stitches and separate increase/decrease counts. The round editor
includes an optional calculator; unsupported techniques remain subject to manual review.
Sixty-five new tests include an independent counting oracle and AppTest calculator
interaction; four ambiguous increase abbreviations in historical fixtures were corrected.
Full suite: **1317 passed, 1 skipped in 48.88s**; Ruff app/tests/scripts, mypy app/tests
(125 files) and diff checks pass. Source observations are recorded in
[SOURCES.en.md](SOURCES.en.md#2026-10-24-local-references-and-round-notation).
No runtime dependencies or reference assets were added. No remote CI, package rebuild,
real-photo accuracy evaluation or physical trials were run. Changes are uncommitted;
G3/G4 remain blocked.

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
| Dependency audit | Pending remote re-check | the audit now exports the lock (`uv export --locked --all-extras`) and checks every pinned package (`pip-audit --no-deps`); the former `pip-audit --local` audited zero packages in the uv overlay yet passed (audit F-01). Pillow 13.0.0, certifi 2026.10.23 and Streamlit 1.66.1 (which drops GitPython) clear the 46 earlier GHSA alerts; CI must confirm on this SHA |
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
| G1 Reproducible source | **Application/test baseline merged: `44a79fc`** | [PR #22](https://github.com/paulkooer/CrochetPhoto2Pattern/pull/22) merged into `main`; its tree matches checked head `4a63745`. Local full suite: 2081 passed, 2 skipped. Later changes require their own commit-bound evidence; new fixes do not inherit the independent PASS for `55280fb` |
| G2 Supported-version automation | **All 10 remote checks passed for PR #22** | Checked head `4a63745`: Python 3.11–3.14, Docker, PDF, pose, mypy, dependency audit and the new browser check all pass; exact run links appear above. Verify post-merge and later-commit results against their own SHAs |
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
