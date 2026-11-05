# Part-level yarn colour selection V1: specification and acceptance checklist

**English** | [Simplified Chinese](part-color-selection.md) | [Documentation index](README.md)

**Language:** The application interface and exported pattern labels are currently in
Simplified Chinese. Interface names in this guide are English translations, not the labels
shown in the application.

This document is the V1 specification for part-level yarn colour selection: the data flow,
the compatibility plan, the interaction and the acceptance checklist are written first, and
the implementation follows them. Implementation status is in the final section; current
behaviour is always defined by source code, `pyproject.toml`, `uv.lock` and reproducible
checks. Related documents: [projects and formats](project-format.md),
[authorized real-photo evaluation](evaluation.en.md),
[third-party content policy](../THIRD_PARTY_CONTENT_EN.md).

## 1. Goals and non-goals

**Goals**: the user can choose yarn colours deliberately, and the round-by-round pattern,
the colour-change instructions, the material list and every faithfully expressible export
stay consistent. Concretely: colour a whole part; colour a single physical instance (for
example only the left arm); colour the head section and the body section of a one-piece
head-and-body separately; provide two explicit operations, "set the base colour and keep
existing stripes" and "recolour uniformly"; preview before applying, with cancel, undo and
redo; and aim to retain completed rounds for pure colour changes while stating plainly that
yarn already worked keeps its original colour.

**Explicitly out of scope for V1** (not omissions; see §11):

- per-colour swatches and per-yarn densities (the project keeps one shared yarn spec);
- in-round (local) colour changes, or automatic conversion of motifs such as eye patches;
- treating RGB values as real yarn colour numbers, dye lots or usage evidence;
- collecting user telemetry (manual-recolour rate and correction time are reported as
  "not evaluated" until real data exists);
- faithful expression of CrochetPARADE ring starts and reserved half-stitch joins (§12
  explains why these are not implemented).

## 2. Three distinct concepts

The specification separates the following, so that an approximate display is never taken
as purchasing or recognition evidence:

| Concept | Where it lives | Meaning and boundary |
| --- | --- | --- |
| **Colour role** | `params.parts[].name` plus `_SKIN_PARTS`/`_BODY_PARTS` in `app/models/parts.py`; the placeholders `skin`/`body` | The semantic placeholder for "which kind of yarn belongs here" (skin yarn, main yarn). It is not a colour and not a colour number. V1 adds **no** role field: part names and placeholders already express the role, and a new field would only invite reading it as colour evidence. |
| **Actual colour** | `params.parts[].color`, `params.parts[].rounds[].color`, `params.parts[].instance_colors` | A yarn colour name (or a user's custom name) from user choice or photo recognition. This is the pattern's only actual colour source. |
| **Yarn product** | `params.yarn_spec` (ball weight/length, swatch) plus verified colour numbers from `brand_code()` in `app/models/colors.py` | Purchasing information. V1 still applies **one** yarn spec to every colour; `brand_code()` returns a number only for verified entries and `None` otherwise, never inventing one. |

The RGB values in the colour table are used for swatches and approximate matching
(CIEDE2000 nearest neighbour) only. They are **not** evidence of colour number, dye lot or
usage. Grams and meters stay labelled as estimates when no yarn spec or measured swatch
exists.

## 3. Data flow

**Generation path (existing)**: photo → `vertical_color_bands` (per-band voting) →
`color_blocks_for_part` (slicing by each part's longitudinal share) → `round_color_plan`
(picking a colour per round by overlap) → `rounds[].color` →
`refresh_color_instructions` (writing the part's dominant colour and automatic colour-change
fragments) → `yarn_requirements` (per-colour usage) → Markdown/PDF/Parade/preview.

**Manual path (new in V1)**: colour selection on the result page → pure functions in
`app/services/color_selection.py` → rewrite `rounds[].color` / `parts[].color` /
`parts[].instance_colors` / `parts[].color_origin` → `refresh_color_instructions` →
`refresh_derived` (recomputing materials, total stitches and time) → `rebuild_params`
(`CrochetPart` validation plus `require_valid_pattern`) → the progress rule (§7) → the
existing `edit_history` preview/apply/undo/redo → every export.

The manual path **must not** write back photo evidence: `result["color_bands"]`,
`vision_meta.color_observation`, `analysis.recommended_colors` and
`analysis.hair_color`/`top_color`/`bottom_color` keep their values. A manual choice is
visible only in `rounds[].color`/`parts[].color`/`instance_colors` and `color_origin`; it is
never disguised as photo recognition, and it does not rewrite prose that the photo semantic
path wrote.

## 4. Data model and single source of truth

**Precedence for one round's actual colour, highest first**:

1. `parts[].instance_colors[i]` when that entry is not `null` (an explicit choice for that
   physical copy);
2. `rounds[].color` (the round-level colour, the highest-precedence per-round source);
3. `parts[].color` (the part's base/dominant colour, a fallback only).

**New fields (all optional and omittable)**:

| Field | Type and constraint | When it is written | Meaning |
| --- | --- | --- | --- |
| `params.parts[].color_origin` | `"manual"` or absent | Only when the user explicitly chooses the part's base colour | Records a manual base colour. An absent field means the origin was not recorded; it may be generated or an earlier manual edit. No per-round origin is recorded (§4.1). |
| `params.parts[].instance_colors` | An array of `quantity` colour strings or `null` | When the user colours a copy separately | `null` inherits the round or part colour. Omitted when empty or all `null`; copy IDs keep colours aligned when instances move. |
| `params.parts[].instance_color_ids` | Unique copy IDs, same length as `instance_colors` | Saved with per-copy choices when stable graph IDs are available | Rebinds colours by ID after reordering. Removing a separately coloured copy is rejected until its override is cleared. |
| `params.parts[].color_section_mode` | `"head_body"` or absent | Set when colouring the head and body of a one-piece part | Allows regeneration to remap section colours using the neck marker; ambiguous mappings are rejected. |

**The meaning of `color`**: generated colours may derive a dominant colour from the rounds;
a manually chosen base colour remains the user's choice even if a stripe covers more
rounds. The effective colour follows the precedence above.

### 4.1 Why no per-round colour origin is recorded

Legacy data does not record whether a round's colour came from photo analysis or from a
manual edit. The existing fields cannot reliably distinguish the two: `rounds[].color` has
the same shape on both paths, and `auto_color_note` only covers **colour-change boundaries**,
which is not the same question as "who chose this round's colour". Any heuristic would claim
"manual" on rounds the user never touched, or "photo" on rounds they did.

V1 therefore takes the conservative route: it writes **no** per-round origin marker and
overwrites no round on the strength of one. "Keep existing stripes" changes only rounds
inheriting the base colour; all explicit round colours are preserved, even when equal to the
old base. "Recolour uniformly" overwrites by explicit choice with each affected copy and
round listed in the preview.

## 5. Compatibility and migration

- **The backup root moves to `schema_version="2"`.** Unversioned and version 1 patterns are
  migrated without guessing colour origin. Older applications reject version 2 explicitly,
  preventing a re-save from silently discarding fields they do not understand.
- **They must be declared on `CrochetPart`.** `rebuild_params` runs
  `CrochetPart(**part_input)` then `to_data()`, and undeclared keys are silently dropped by
  pydantic (verified: with `instance_colors`/`color_origin` absent from the model, `to_data()`
  does not contain those keys). The fields belong in the model and are guarded by the
  `docs/schemas/crochet_part.schema.json` drift test.
- **Older backups read in**: their quantities and existing round colours are retained;
  nothing is guessed and no origin is back-filled.
- **Validation**: `instance_colors` must have exactly `quantity` entries; otherwise
  `rebuild_params` rejects at the boundary (no silent truncation) naming the part and the
  length. Copy IDs must also have matching length and be unique. New per-copy selection
  requires stable graph IDs. Clear a copy's override before removing that copy. Legacy data
  without IDs can only be aligned to its current order; historical attribution is unverified.
- **Carrier coverage**: backups, share tokens, local history, project files and trial bundles
  all travel through the same `PatternResult`/`rebuild_params` contract, so the fields
  round-trip with `params.parts[]`. Project progress binds to the pattern revision
  (`pattern_revision`); a manual colouring changes the pattern, so progress is judged by §7.
  Backups, shares, projects and new trial bundles strip `preview` and `geometry.mask_review`;
  enabled single-user history stores both on the application host. Restored old trial bundles
  preserve the original pattern bytes and may still contain those fields.
- **Export cache**: raised whenever exported content changes (including per-colour and
  per-copy colours). This round raises it from **17 to 18**, so Markdown/PDF/Parade from
  older sessions must be regenerated. The current value is
  `EXPORT_CACHE_VERSION` in `app/ui/export_cache.py`.
- **Project revisions**: migration from version 1 to 2 preserves old pattern semantics and
  accepts their original revision hashes. `project_state` and trial records remain separately
  versioned and unchanged.

## 6. Interaction

Entry point: result page chapter 5 (**Local corrections**) → the **Yarn colour selection** panel, at the
same level as the neck-opening, independent-swatch, skirt-join and other special-purpose
tools. Every submission goes through the existing `edit_history`: preview the impact, apply,
cancel, undo, redo.

1. **Choose a part**: a dropdown listing every part, labelled with its name and current base
   colour (placeholders are shown as unselected skin or body colours via
   `app/utils/color_labels.py`).
2. **Choose a colour**: the colour-table dropdown (`YARN_COLORS` in
   `app/models/colors.py`) or a "custom" text input, which preserves a user's own name just
   like the round-table editor.
3. **Choose an operation** (one of two, always explicit):
   - **Set the base colour and keep existing stripes**: rounds inheriting the base take the
     new one; all explicitly coloured rounds are kept and listed in the preview.
   - **Recolour uniformly**: every round takes the new colour. This overwrites existing
     per-round colours, including stripes and manual edits, so the preview lists every
     round's old and new colour and the user must confirm before applying.
4. **Instance colouring** (when `quantity > 1` and stable IDs exist): choose the single-copy
   uniform option and the instance, or restore that copy to its part colours. Whole-part
   uniform recolouring clears copy overrides after an explicit notice. Without stable IDs,
   new single-copy colouring is unavailable, and the panel offers whole-part colouring.
   A newly generated pattern can offer single-copy colouring if it has stable IDs; the
   correspondence to old physical copies still needs review.
5. **One-piece head-and-body sections**: when the part name matches
   `app.models.parts._ONE_PIECE_NAME`, two colours are
   offered, one for the head section and one for the body section. The boundary comes from
   `ONE_PIECE_NECK_MARKER` in `app/models/parts.py` (the generator writes that marker into
   the notes of exactly one round, and `crochetability` and `skirt_edit` already parse it the
   same way). **A missing or non-unique marker refuses the operation with an explanation**;
   the boundary is never guessed from prose.
6. **Preview** (required before applying): part, instance, affected rounds (row, old colour,
   new colour), kept rounds, per-colour material usage before and after, and the progress
   impact (reusing `progress_state.progress_impact`), plus the notices from item 7.
7. **Notices that must be shown**:
   - Yarn already worked keeps its old colour; a checked-off row does not mean the finished
     piece needs no rework.
   - Uniform recolouring overwrites existing per-round colours, and an overwritten round
     cannot be restored from the interface afterwards (only undone back to the previous
     state).
   - The 3D preview shows one illustrative colour per part and does not show stripes or
     per-instance colours (§8).
   - A custom colour outside the table is used for the pattern and its display only; it
     provides no colour number or usage evidence.

## 7. Progress rule

**Default (the existing conservative rule is unchanged)**: `progress_state.progress_limits`
compares a part's full instructions (colours included) and each round's instructions
(colours included, falling back to the part colour); completed records are cleared from the
first affected round onward, and joins and assembly dependencies propagate as before.

**The new V1 exception applies only to a verified pure colour change**: when two patterns are
identical apart from colour-bearing fields, every completed round is retained. All of the
following must hold:

- `parts[].color`, `rounds[].color`, `parts[].instance_colors`, `parts[].instance_color_ids`,
  `parts[].color_section_mode` and `parts[].color_origin` may differ;
- per-round `auto_color_note`, the part's `auto_color_summary`, and the part of `notes` that
  is **exactly** those recorded automatic fragments may differ (they are re-derived from the
  colours);
- everything else must be identical: `name`, `type`, `quantity`, each round's row, stitches,
  increase, decrease, `region`, `height_range_cm`, `allow_wide_jump`, the hand-written part
  of `notes`, `opening_row`, `magic_ring`, `gauge`, `params.gauge`, `stitch_attachments` and
  `assembly_plan`, as well as each part's physical copy order (the structure instance IDs).

Any change to stitches, techniques, joins or other construction keeps the conservative rule.

**Two deliberately conservative exceptions**:

- Parts involved in a **cross-part reserved half-stitch join** keep the existing conservative
  rule even when only their colour changed: such a part's stitch identity depends on the part
  it joins, and existing tests pin that contract. The whole-section retention only applies to
  parts that take part in no join; joined parts still go through the per-round comparison and
  the join dependency propagation.
- **A change of instance order or count** is not a pure colour change: not a single stitch
  count need differ, yet the physical copy a completed record belongs to has moved. The test
  includes each part's physical copy order, so reordering structure instances still clears the
  affected parts' records.

**Why the rule is not relaxed globally**: comparing colours is precisely what prevents the
false impression that a recoloured pattern still matches finished work, and existing tests
pin the conservative invalidation of joined parts. Relaxing only for a provable pure colour
change retains completed rounds without letting any construction change slip through.

**Duty to warn**: whether or not progress is retained, the interface must say that yarn
already worked keeps its original colour. Retaining progress only means the **rest of the
pattern** needs no re-checking; it does not mean the finished piece matches the pattern.

## 8. Exports and consistency

| Carrier | Reflects the colour change | Notes and limits |
| --- | --- | --- |
| Markdown | Yes | The part colour line and round-table colour column are updated; with `instance_colors`, each copy's colour is listed and the quantity note makes clear that copies share the same stitches but can have different colours. |
| PDF | Yes | Same part colour and round-table colour column as Markdown (PDF additionally shows each part's base colour). |
| Material list | Yes | Grams/meters/balls per colour; with `instance_colors`, stitch counts are attributed per copy and summarised per copy colour. Still labelled as estimates without a yarn spec or measured swatch. |
| CrochetPARADE DSL | Yes, within the subset this project has verified | Each copy emits its own `COLOR:` prefix plus per-round colour-change boundaries. Unconvertible custom colours (including legacy colours with unrecorded origins) or unsupported constructions are reported as incomplete instead of silently exporting the old colour. |
| 3D structure preview | No | Still one illustrative base colour per part; the interface **states plainly** that stripes and per-instance colours are not shown. |
| Trial bundles | Yes | They embed a pattern backup with its colours; trial records remain separately versioned. |
| Flat grid projects | Unchanged | They have their own grid and palette format. |

Verifiable meaning of consistency: generating Markdown, PDF material rows and DSL text from
the same `result` must agree on per-round colours and per-colour totals; a disagreement is a
defect. A colour change does not alter stitches, total stitches, estimated time or construction
instructions (generated colour transitions and summaries are refreshed).

## 9. Evaluation metrics

The four metrics below are designed for later evaluation. Each lists its definition,
denominator, missing-label handling and data source. **Manual recolour rate** and
**colour correction time** must come from real user activity and cannot be inferred from
synthetic tests.

| Metric | Definition | Denominator | Missing labels | Data source |
| --- | --- | --- | --- | --- |
| **Part colour match rate** | Compare the predicted colour of each annotated part or instance with its corresponding human label; a missing or wrongly matched prediction fails. Report automatic and manually corrected results separately. | Parts or instances with comparable part-level ground truth | Exclude and count missing labels; report "not evaluated" when none exist | Future authorized part-level annotations and pipeline artefacts. Whole-image `dominant_colors` cannot substitute for part labels. |
| **Manual recolour rate** | Share of observable parts or instances changed at least once by a user in real sessions. | Observable parts or instances in those sessions | Report "not evaluated" without real sessions or reconstructable actions; a missing origin marker is not proof of no edit | Consented before/after session records. V1 collects no telemetry; a saved pattern alone cannot establish all past actions. |
| **Colour correction time** | Actual elapsed time from seeing the generated colours to applying the final choice. | Real user sessions that completed a colour choice | Reported as "not evaluated" when no real session exists | **Not collected in V1.** If implemented later it must be local, clearly disclosed, and opted into by the user; never enabled by default |
| **Page/pattern/PDF/material-list consistency** | Share of parts and colour entries that agree exactly on per-round colours and per-colour totals across the page, Markdown, PDF and the material list, for one `result`. | Parts and colour entries compared | A case missing one carrier is excluded and the reason is recorded | Automated consistency assertions (`tests/*`) plus browser-regression evidence |

Further constraints: the Beta positioning stands; authorized photos, physical trials and
independent verification are still missing, so automated tests or synthetic images **must
not** stand in for G3/G4 evidence. These metrics measure software behaviour and do not prove
actual size, yarn usage, time or crochetability.

## 10. Acceptance checklist

- [ ] Part colouring: "keep stripes" preserves all explicit round colours; "recolour uniformly" covers every round and copy override and lists them in the preview.
- [ ] Instance colouring: with `quantity > 1` only the target copy is written; `parts[].color` is unchanged; materials split per copy; the interface shows the instance ID.
- [ ] One-piece head-and-body: split by `ONE_PIECE_NECK_MARKER`; a missing or non-unique marker refuses the operation (no guessing).
- [ ] Preview: part, instance, rounds, old and new colour, per-colour material usage and progress impact are all present; cancelling leaves no side effects.
- [ ] Apply/undo/redo: applying can be undone back to the previous state; undo and redo lose neither personal notes nor completed progress.
- [ ] Progress: a verified pure colour change retains every completed round; any construction change still clears records conservatively.
- [ ] Notices: yarn already worked keeps its colour; uniform recolouring overwrites; 3D shows base colours only.
- [ ] Evidence retained: `color_bands`/`vision_meta.color_observation`/`analysis.recommended_colors` are not rewritten.
- [ ] Consistency: Markdown/PDF/material list/DSL agree on per-round and per-colour values.
- [ ] Compatibility: legacy backups (without the new fields) load; the new fields survive backups/share/projects/history/trial bundles; a wrong length is rejected at the rebuild boundary.
- [ ] Documentation: `docs/schemas/crochet_part.schema.json` is regenerated; the export-cache bump is documented.

## 11. Unfinished work and known limits

- **Legacy copy attribution may be unverifiable**: new per-copy choices bind stable graph IDs.
  Earlier data containing only ordinals can be aligned only to its current order, so historical
  attribution cannot be proved. New per-copy choices require stable IDs.
- **One-piece section colouring depends on the neck marker**: hand-built one-piece patterns
  without it cannot use section colouring.
- **The 3D preview stays part-level**: it shows an illustrative base colour and no stripes or
  per-copy colours.
- **No per-round colour origin** (§4.1): the interface cannot tell whether a round's colour
  came from the photo or a manual edit.
- **No per-colour swatches or differing yarn densities**; one yarn spec still applies to all
  colours.
- **No in-round (local) colour changes**; local patches in the photo remain evidence only.
- **Manual recolour rate and colour correction time** are reported as "not evaluated" until
  real user data exists; no zeroes and no accuracy-improvement claims.
- **CrochetPARADE ring starts and reserved half-stitch joins** remain export gaps (§12).

## 12. CrochetPARADE gap: verification result (not implemented)

**Conclusion: this round does not implement faithful ring/chain starts**, because no evidence
proving the semantics could be obtained.

Every piece of evidence reviewed comes from this repository's existing source records
([SOURCES.md](SOURCES.md)) and is **not** a fresh verification: the official HTML manual's
stitch table, `stitch_nameNinc/Ntog` and capabilities §1.5 for `scfl`/`scbl` and shaping
suffixes; `Manual.md` for "each line is one round, joined in the previous round's order, and
repeat groups"; and `start_anew` meaning the next stitch has no connection to the previous
one. Those same records state that "a first round picking up stitches without a translatable
base is likewise not guessed as a magic ring" and that "misplacement notes, loop technique,
**non-magic-ring starts** and closing actions still need checking against the original
instructions" — that is, the construct is a **known untranslated** item, matching the F-10
flag in `parade_export.py`.

Attempts to re-check the official manual and capability notes over the network this round
were rejected by the server with HTTP 429, so **no** re-verification was possible and there is
no new official syntax evidence for an open-tube start.

Why it is not implemented:

1. No instruction in the current DSL subset has a **verified meaning** of "open foundation".
   `ring` on its own is a magic ring (no fixed default stitch count), so emitting it for an
   open tube substitutes a closed disc for an opening, which is wrong.
2. Emitting `ch`/`ss` tokens is not evidence. The linter's token whitelist is this project's
   own verified subset, **not** the official CrochetPARADE parser (the module documents that
   it is not). A token appearing in the word list does not mean the upstream translator
   executes "chain joined into a ring, then stitches worked into the ring" as an open tube.
3. Silently approximating an open tube with a closed disc would produce a wrong 3D model and
   wrong tension findings, which is more harmful than honestly skipping it.

**Implementation plan (conditional, to run once evidence exists)**: the evidence needed is
(a) an instruction in the official manual or capability notes whose documented meaning is
explicitly an open foundation (a chain ring, a slip-stitch joined ring, or documented support
for working stitches into a chain) and (b) something showing the upstream translator actually
executes that construct (an official example or official statement), both citable line by
line. Once available: choose the foundation instruction per part construction in
`_part_lines`; emit it for open tubes instead of `ring`+`scNinc`; stop registering the
corresponding `unsupported_constructions` entry; and update the source records in
`docs/SOURCES.md`, the wording in `docs/evaluation.md`, and the convention tests in
`test_parade_export_counts.py`. **Until then the exporter keeps registering the construct as
`ring_start`, keeps it out of the complete-export part count, and neither invents DSL
instructions nor silently replaces an open tube with a closed disc.**

## Implementation status

See the [changelog](../CHANGELOG_EN.md) and the latest reproducible validation in
[system status](system-status.en.md); both record what this round actually completed and what
it did not. This document describes the V1 specification, and anything listed as unfinished in
§11/§12 is treated as unfinished until implemented.
