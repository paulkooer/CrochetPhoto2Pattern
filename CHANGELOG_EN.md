# Changelog

[简体中文](CHANGELOG.md) | **English**

This project follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
[Semantic Versioning](https://semver.org/). Backup, structure, and editable-project
formats may still evolve during Beta; incompatible changes must include migration notes.

## Unreleased

### Changed — 2026-11-13 Image dependency lock update

- Update headless OpenCV to 4.14, NumPy on Python 3.11 to 2.4.6, and use locked NumPy 2.5.2 on 3.12+. Use equivalent module-level functions for two integer-array reductions to support NumPy 2 typing; segmentation and color strategies are unchanged.

### Fixed — 2026-11-13 Release receipt consistency

- Offline receipt status checks both candidate commit and tree, the scope flag, passing check groups, and the audit tree. Evidence generation writes a companion SHA-256 file; status and tests reject missing or mismatched checksums. This verifies local consistency, not remote-run authenticity or release readiness.
- Status examples use the selected candidate SHA. Record the upstream security-update exception for type-only Dependabot ignores, and move PR #15's open split follow-up out of the historical archive.

### Changed — 2026-11-13 Stylesheet sections

- Compose `build_css` from token, page, navigation, control, pattern, hero, section-heading, note, reduced-motion and print helpers. Preserve complete CSS bytes and dynamic token/ring variants.

### Changed — 2026-11-13 Grid UI sections

- Extract project restore, inputs, generation, history, editing, preview and downloads into rendering helpers. Preserve widget keys, text, call order, caching and state protection when preparation fails.

### Changed — 2026-11-13 Trial tool modules

- Move trial schemas, bounded JSON/file I/O, draft/fingerprint handling, external evidence, calibration analysis and CLI handling into `app.trial_tools`. `app.trials` remains a compatibility facade with the same public names and CLI entry point. Record/report schemas, fingerprint rules, calibration/holdout isolation and conservative release decisions retain their behavior.

### Changed — 2026-11-13 Evaluation stages

- Separate one-image scoring, per-run accumulators and report aggregation from `evaluate_dataset`. Frozen-image reads, rights validation, failed-case accounting, report schema and release thresholds retain their behavior.

### Changed — 2026-11-13 Assembly part identity

- Assembly routing and default connection templates use `PartKind`; saved labels are resolved at the boundary. Existing prose, per-copy quantities, openings, custom names and one-piece target regions retain their behavior.

### Changed — 2026-11-13 Generator part identity

- Generator dispatch, semantic colors, bottom-up color direction and attached-skirt handling use `PartKind`. Saved Chinese names remain the wire format; English or custom legacy names are not reinterpreted. Existing serialized snapshot fixtures are unchanged.

### Changed — 2026-11-13 Generator shape dispatch

- Move sphere, skirt, cup, profiled-body, body-cylinder and limb-cylinder generation into separate helpers. The main generator retains preparation, dispatch and shared postprocessing. Serialized results, branch priority, colors, openings, materials and assembly remain unchanged; the 102 frozen cases are preserved.

### Changed — 2026-11-13 Repository and release evidence maintenance

- Status pages link to the saved release receipt instead of repeating its commit hashes and check counts. The bilingual release process generates evidence only for a selected candidate; `bind_release_evidence.py --status` checks an exact commit offline without rewriting evidence. Existing evidence remains historical, and G3/G4 remain blocked.
- Move dated review documents, public-pair catalogs, probes, and synthetic comparisons into `docs/archive/`, preserving JSON bytes and updating navigation and reproduction paths.
- Ignore routine OpenCV major-version updates for both runtime and pose distributions while keeping 4.x updates enabled. OpenCV 5 requires an explicit API migration review.

### Fixed — 2026-11-12 Photo corrections and round references

- Recalculate prior-derived part spans after a subject-mask correction, preserving pose measurements and reviewed head/body boxes in image coordinates. Background strips at the top and sides no longer overwrite definite foreground; the resulting segmentation still needs review.
- The round-table editor rejects renumbering or reordering round identifiers, preventing opening and one-piece neck references from silently shifting. Deliberate round changes remain available in advanced JSON.

### Fixed — 2026-11-12 Gauge-aware ladder spheres

- Newly generated ladder spheres estimate meridian rounds from quantized circumference, stitch width and row height, then distribute changes of at most six stitches along the model profile instead of simply extending a cylindrical belt. Extreme gauges that cannot meet the target with six-stitch steps carry a part-level warning. Existing backups keep their rounds; size or gauge regeneration uses the new rule and may affect progress. Physical trials remain outstanding.
- Share links compress compact JSON to reduce URL length pressure from extra rounds, retaining every existing field and the same length and decoding limits.

### Changed — 2026-11-12 Automatic part delivery evaluation

- The noninteractive CLI and default evaluator add ear, skirt and tail contour candidates to the four-part template; explicit part selection wins. These candidates are uncalibrated and can be wrong; the Photo review still uses explicit selection. Missing contour observations are unavailable, not negative hints. Evaluation report schema 6 records the selection path; release floors are unchanged and real-photo evidence remains pending.

### Added — 2026-11-11 Review-hint evaluation

- Evaluation report schema 5 measures precision/recall, TP/FP/FN and unavailable cases for ear, skirt and tail review prompts. Missing or non-boolean hints and pipeline failures are not treated as negatives. These metrics do not change delivery or the G3 gate. Older reports must be rerun for the new metrics; an authorized real-photo dataset is still unavailable.

### Fixed — 2026-11-11 Local body-type labels

- Local photo analysis no longer infers physique from head-to-height ratio; body type is reported as unassessed. A manual label is descriptive and does not change sizes or stitches. Existing results retain their original label, with the legacy inference explained in the UI. Diagnostics no longer show an empty API-usage entry.
- For structured openings, reject standalone closing directives and known generated closure instructions without treating negated or incidental author notes as closure.

### Fixed — 2026-11-11 Subject spans and structural joins

- Map default part proportions through the silhouette's estimated subject extent into image coordinates, then overlay pose measurements and reviewed boxes. Round colours and body profiles use the same spans and can be regenerated from a backup. The low-resolution silhouette remains a heuristic, not part recognition. [MediaPipe pose coordinates](https://github.com/google-ai-edge/mediapipe/blob/master/docs/solutions/pose.md) are image-normalized, so measured spans are not transformed again.
- New patterns record whether a connection is open, its joining round, and the one-piece neck round. Assembly, section colours, skirt joins and crochetability use the structured records. Backup schema is now 3; unversioned, version 1 and version 2 patterns retain their legacy interpretation without invented fields, and old project progress remains bound.
- When an ideal-sphere or egg head ends at six stitches, the finishing note states the actual count and asks for a physical trial instead of also saying not to decrease to six. Stitch counts are unchanged. Cross-gauge ladder-sphere shape is recorded for G4 trials. Export cache is now 23.
- Evaluation manifests accept JPEG and PNG, matching the upload decoder, and reject WebP during validation instead of recording a guaranteed pipeline error.

### Changed — 2026-11-11 Leaner status documentation

- The bilingual status pages now cover current conclusions, evidence, and gates. Historical per-round records remain accessible at a fixed Git revision. New tests are grouped by module or behavior.

### Added — 2026-11-11 Replace a grid colour throughout

- Inspired by [SpriteStitcher's whole-pattern replacement](https://github.com/Jesterace/SpriteStitcherv4), the grid editor can replace every cell of one palette colour with another. It shows the source count first and supports undo, redo, and project restore. The unused source stays in the palette with a zero count; a no-op does not create history.

### Fixed — 2026-11-11 Colour form and display-swatch preview

- Switching custom yarn names now loads each name's saved display swatch; a new name starts with neutral gray. Switching copies initializes the form from the selected copy rather than carrying over another copy's choice. A built-in name typed as custom uses its fixed yarn-table swatch.
- The edit preview shows old and new display swatches and explains that a name shares its swatch across the pattern. Materials still use the yarn name. The per-copy guidance now matches the 3D preview: each copy uses its own colour, while round stripes are not drawn.

### Changed — 2026-11-08 Chart letters for taller stitches

- The stitch calculator accepts a complete formula using T, F, E, B, SL, NX or S-SC. Each consumes and produces one stitch and keeps its own symbol; it is not rewritten as single crochet. FV is a taller increase (1→2) and FA a taller together (2→1). K is a skip: it consumes 1, produces 0, and the decrease count stays 0. K2 is two skips; 12FV is still twelve taller increases; 4*FV repeats the next stitch four times; 4x is still four single crochets. Chain spaces, skips and bobbles written in words, empty-stitch prose and same-stitch clusters stay unrecognized. Printed legends say these stitches are not sc. A round that uses them fails validation and is not translated to sc by CrochetPARADE. Export cache is now **22**.
- The default working note now says hair and garments are often separate flat pieces or taller stitches. A hat may be joined and then worked flat. A sole may be a chain oval, an inner-loop round and a firm insert. Sleeves and trouser tubes may be separate, reversed, or worked into an earlier round to make a fold. Hair strands may be worked into loops left on a flat cap. None of that is a flare of the body spiral.

### Changed — 2026-11-06 G1/G2 evidence

- `docs/release-evidence.json` now binds `main` `ba65b8d` (tree `b2c18d71`). That push is 12/12. pip-audit comes from the same tree, PR #61 head `9063635`, which is 13/13. G3 and G4 stay blocked. The file does not cover later commits, and no release tag is created.

### Changed — 2026-11-07 Release evidence uses the latest run

- `scripts/bind_release_evidence.py` selects the latest run of each check by `created_at`, or by `started_at` when creation time is absent. That run must be completed, concluded `success`, and carry the requested `head_sha`. An unfinished latest run rejects the file instead of reusing an older success. The evidence schema is now 2: `commit_date` is the commit date, `checks_completed_at` is the latest completion time among the adopted runs, and `run_refs` keeps check-run ids, workflow-run ids, and links. The bound `ba65b8d` pass, tree, and pip-audit source are unchanged.
- `--commit` and `--audit-commit` are now required, so a bare run no longer rewrites the `ba65b8d` binding. A run counts as completed only when `status` is `completed`, and a run without `head_sha` is not evidence for that commit. The status snapshot date is 2026-11-07. The page says this binding was `main` when generated and does not cover later commits.

### Changed — 2026-11-06 Display swatches and the structure-table colour

- The structure table has two colour columns. The current base colour is read from `params.parts[].color`. The original structure colour stays the photo or template record and is not rewritten by a manual recolour.
- The 3D preview, ring chart, PDF chips and CrochetPARADE share `present_color()`. It returns the screen hex, the exportable hex, and whether the colour is a placeholder, a custom name, or exportable. `resolve_display_color` only reads one of those hex fields. It accepts yarn-table names, `skin`/`body` placeholders, `#RGB`/`#RRGGBB`, and a screen swatch recorded for a custom name in `params.display_colors`. A custom name with no swatch is painted neutral gray in 3D and no longer keeps the part's previous yarn colour. Parade still refuses a custom name it cannot express, and it does not emit `COLOR:` for an unselected placeholder. A screen-swatch comment names the same colour as the `COLOR:` line it precedes; when the first round differs from the part base colour, the comment is not attached to the base colour. One custom name has one shared display hex.
- A display swatch is only for the screen and for export colouring. It is not a brand colour code. Materials stay aggregated by the text name. A custom name has its own swatch picker, which defaults to neutral gray.
- Changing only `display_colors` counts as a pure colour change and keeps completed rounds. The export cache is now **20**. The browser regression adds a custom display-swatch flow; the full app script is now 28 checks.

### Changed — 2026-11-06 Per-copy colours in the 3D preview

- The 3D structure preview paints each copy from `instance_colors`. When `instance_color_ids` is present, colour follows the copy ID rather than a reordered list. A copy without its own colour, or with a name outside the yarn table, keeps the part colour. Round stripes are still not drawn. Backup format and the export cache are unchanged.

### Changed — 2026-11-06 Result-page renderer split

- The result page is split by chapter into `result_analysis`, `result_structure`, `result_progress` and `result_assembly`. `result_renderer` only orchestrates the page and still exports `md_safe`, `purge_result_state` and `render_results`. The page, widget keys, backups and progress semantics are unchanged.

### Added — 2026-11-05 Contour head candidate and review-only part hints

- When the face candidate is missing or rejected, a head separated at the top of the subject silhouette (a gap, or a clear neck) becomes an unconfirmed head box with source `silhouette-head`. A nearly straight column does not invent a head and keeps the default 9 cm head and 18 cm height.
- Ears are suggested only for a symmetric widening above the face equator, or two symmetric lobes at the crown. Sewn ears usually share the head's pixels, so this does not split components, measure ear length, or generate an ear tube. Unmerged PR #15 explores ear measurement separately and is not a dependency.
- A flared hem stays an observation, not evidence of a skirt. The review page offers "add a skirt?" and leaves it unchecked, consistent with the 2026-10-09 decision that stopped automatic skirts.
- A tail is suggested only for a short one-sided lower bump whose row still covers the torso, and it stays unchecked. A hem that widens on both sides, or a leg detached from the torso, is not a tail. One front photo cannot tell back from side.
- None of these hints are written into `analysis.parts` before confirmation. The CLI path still sets `requires_subject_review` and still delivers head, body, arms and legs. The G3 macro-F1 gate is unchanged.

### Changed — 2026-11-05 Result-page reading order and on-demand JSON editors

- Chapter 1 of the result page folds provenance captions, mask/silhouette notes, pose priors, legacy usage and the local colour-block table into a collapsed "sources and limitations" panel; alerts (unrecognized review records, colour blocks needing review) stay visible outside it. Chapter 3 folds the stitch legend, working and placement guidance, the time-estimate disclaimer and the shaping note into the stitch reference; the metrics, self-check badge, materials and round list stay in the body.
- The structure table drops the developer "position / rotation" column; the coordinate legend moves into "view structure JSON". The connection column stays, marked as template-inferred.
- "Advanced editing (JSON)" now mounts on demand: until enabled, neither editor is rendered and the full pattern/structure JSON is not reserialised on every rerun. After the enable click both editors stay mounted for the tab, including across regeneration, so unapplied drafts keep their preview/cancel/retention guarantees.
- The photo page drops the "multi-angle photos (planned)" placeholder; the roadmap stays documented in docs/flow.md.
- Widget keys, backup format and progress semantics are unchanged; the browser suite adds checks for the collapsed sources panel, the coordinate-free structure table and the absence of editor textareas before enabling (27 flows).

### Documentation — 2026-11-05 English interface descriptions

- Translate interface references in the English README and the colour-selection and physical-trial guides. Clarify that the application interface, CLI help and generated patterns currently use Chinese; the CLI example now uses default parts, and links to Chinese guides are labelled.

### Documentation — 2026-11-04 Bilingual project overview

- Document part-level colour selection, legacy identity and 3D preview limits; clarify which exports are blocked by a failed self-check and how the current `main` branch relates to the version badge. Record PR #49's local and remote validation in both system-status pages.

### Fixed — 2026-11-04 Photo data warnings for older trial bundles

- New trial bundles still omit thumbnails and brush masks. Restored older bundles retain exact source bytes to preserve the trial's hash binding; the sidebar and trial panel warn when those bytes contain a thumbnail or mask, and explain that a new trial does not inherit old measurements.
- Clarify that backups cannot restore the brush selection or retain its correction provenance, although the resulting pattern and silhouette summary remain. Other original fields can also remain in older trial bundles.

### Fixed — 2026-11-04 Backup and colour-selection guidance after review

- Correct both READMEs: backups, shares, projects and new trial bundles omit the brush mask and photo thumbnail but can still contain photo-derived analysis, silhouette and colour summaries. Saving to enabled single-user history keeps the mask and thumbnail on the application host. The result page explains share contents and the boundary for brush-corrected results.
- The colour preview explains that explicit rounds matching the old base are kept, and warns when no effective round colour changes. Parts without stable copy identities offer whole-part guidance and explain the condition for new patterns. The READMEs describe both Parade export and strict completeness rates; unsupported constructions remain unchanged.

### Added — 2026-11-04 Part-level yarn colour selection V1

- Result chapter 5 gains a "yarn colour" panel: colour a whole part, colour a single physical instance (only the left arm, say), or colour the head and body sections of a one-piece head-and-body separately. The data flow, data model, compatibility plan, interaction, exports and acceptance checklist are in the [part-level colour selection specification](docs/part-color-selection.en.md).
- "Set the base colour and keep existing stripes" changes inherited rounds while retaining all explicit round colours. "Recolour uniformly" replaces all rounds and copy overrides after a per-copy, per-round preview. A part choice records `color_origin="manual"`; a per-copy choice records the colour and stable instance ID so reordering preserves attribution. Missing legacy origin is not guessed; photo evidence is unchanged.
- The material list attributes stitches per copy, so recolouring one copy counts that colour for one copy only. Markdown/PDF list per-copy colours and state that the round colour-change steps describe the shared pattern; the CrochetPARADE export emits a whole-copy `COLOR:` for an individually coloured copy and no per-round colour boundaries for it. The 3D preview still shows one base colour per part and now says plainly that it shows neither stripes nor per-copy colours.
- Progress rule change: verified pure colour changes preserve completed rounds; reserved-loop joins and instance reordering remain conservative, and construction edits clear affected progress as before. Every preview warns that yarn already worked keeps its original colour. Resizing or gauge regeneration retains safely mappable manual colours and rejects ambiguous mappings rather than losing them silently.
- Adds a [specification](docs/part-color-selection.en.md) and four proposed evaluation metrics; whole-image Top-3 does not establish part-level colour accuracy. Report "not evaluated" when the required real data is missing.
- Pattern backup format is now **2**: old patterns and projects migrate, while older applications explicitly reject new files instead of silently dropping colour choices. Project-state and trial-record formats remain independently versioned.
- Export cache is now **18**, so Markdown/PDF/Parade from older sessions must be regenerated; `docs/schemas/crochet_part.schema.json` is regenerated with the model.
- Not implemented: per-round colour origins, in-round changes, per-colour swatches or yarn densities, and per-round/per-copy 3D colours. Parade reports unconvertible custom colours as incomplete; ring starts and reserved half-stitch joins remain unsupported (specification §12).

### Fixed — 2026-11-04 Parade complete-part count

- An open-start skirt tube still produces an incomplete DSL approximation with a warning, but no longer counts as a faithfully complete exported part. The emitted-round count still counts generated DSL rounds, and repeated copies register the unsupported construction once. Evaluation thresholds and strict completeness remain unchanged; the export cache is now 17.

### Fixed — 2026-11-04 Unselected yarn colors and PDF part colors

- The result page, structure table, progress rows, Markdown and PDF display the internal `skin` and `body` placeholders as unselected skin and body yarn colors, including recorded automatic color-change notes and summaries. Handwritten notes, explicit colors and custom names remain unchanged; the 3D preview identifies placeholder colors as illustrative.
- PDF now shows each part's base color so readers can interpret rounds with no color override; the round-table color column is wider. The round editor retains the original values and explains the placeholders. Pattern data, backups and material aggregation are unchanged; the export-cache version is now 16.

### Fixed — 2026-11-04 OpenCV version for optional pose dependencies

- Explicitly require `opencv-contrib-python>=4.8,<5` for the Python 3.11–3.12 `pose` extra. The base `opencv-python-headless<5` constraint cannot constrain the separate distribution required by MediaPipe. Unlocked installs can no longer resolve contrib 5.x; existing locked package versions remain unchanged.
- Add declaration and lock checks, and exercise unlocked pose installs, OpenCV and MediaPipe in clean Python 3.11 and 3.12 CI environments. The two distributions still share `cv2` and do not follow OpenCV's recommendation to install only one; the READMEs explain the isolated-environment and recovery guidance.

### Changed — 2026-11-03 UI information architecture: sidebar and local corrections

- The sidebar now reads creation settings (gauge → shaping) → "打开已有工作" (open backup, open trial bundle, my history). The gauge no longer sits below two import panels, the three dividers are down to one, and the sidebar's own divider margin is narrower. The two open entries keep their own panels, grouped by a subheading rather than nested: Streamlit 1.66 does allow nested expanders, but nesting only costs an extra click before the uploader.
- The "history disabled" notice used to `return` from inside the panel and ended the whole sidebar; now it only ends that panel's body. A new AppTest checks both open entries are usable with history disabled and actually opens a trial bundle.
- Result chapter 5 ("局部修正") is layered: undo/redo, then quick size, visual part editor, round table, material estimate, then the special-purpose tools (neck opening, independent swatches, waist join, per-stitch connections, leg bridge), and one collapsed "高级编辑（JSON）" panel holding the output-JSON editor and the former structure-JSON panel. Both JSON editors stay rendered rather than switching behind a selector — Streamlit drops the state of widgets it does not render, which would lose an unapplied draft; the draft notice appears both under the editor and above the downloads. Preview-vs-apply wording and progress/notes impact notes are unchanged.
- Common exits are collected under a visible "下载与保存" heading: backup, JSON, Markdown, PDF, and history naming/share/save/import; the CrochetPARADE export moved below them. No download sits inside a collapsed panel.
- The progress pair "重置进度 / 全部完成", undo/redo, the preview apply/cancel pair and the JSON editor pairs now sit left-aligned in horizontal containers (`st.columns(2)` spread content-width buttons half a panel apart). The two sidebar captions are merged into one line and chapter 5's duplicate "也可使用下方尺寸滑块或高级 JSON 编辑" is gone.
- Widget keys, pattern/project/trial-bundle formats and behaviour are unchanged. README and the physical-trial docs now name the trial entry as it appears and place it under "打开已有工作".
- Tests: new `tests/test_frontend_information_architecture.py` (sidebar order, both entries with history disabled, chapter-5 layering and download placement, a JSON draft surviving preview and cancel); browser regression adds the sidebar order, the collapsed advanced panel with downloads outside it, the draft flow and a 390 px sidebar drawer, for 21 flows in total.
- `skin` / `body` placeholder colours were investigated only, with a written plan and no change to stored patterns or material totals; see the [frontend design review](docs/archive/frontend-design-review-20261103.md) (Chinese).

### Fixed — 2026-11-03 Declared Streamlit support floor

- `pyproject.toml` declared `streamlit>=1.40.0,<2.0`. That range resolved to 1.66.1 in the tested unpinned installation, but it also included versions incompatible with the other project requirements: tested `streamlit==1.40.0` and `1.48.0` require `pillow<12` and `1.66.0` requires `pillow<13`, each conflicting with the `pillow>=13.0.0` needed to decode uploads. The `protobuf<7` cap in the sampled Streamlit 1.45.0 and 1.55.0 releases still overlaps the project's `>=6.33.5,<8` via 6.x; 1.56.0 widens the cap to `<8`, allowing 7.x. The UI calls `width="stretch"`, which first exists in 1.48.0 (the UI also uses `st.container(horizontal=True)`), so 1.40 failed at run time as well. The declared floor is now `>=1.66.1`, the verified locked version; no security floor was lowered.
- `uv.lock` records the new range and the marker annotations the resolver tightens for it; every package version and artifact hash was compared and is unchanged (no incidental upgrades).
- New `tests/test_dependency_floor.py`: the declared floor may not drop below the verified minimum, `uv.lock` must record the same range as `pyproject.toml`, the installed environment must satisfy every declared floor, and the installed Streamlit must accept the arguments the UI passes (including the string semantics of `width`).
- New `streamlit-floor` CI job: installs the declared floor plus project dependencies from PyPI in a clean environment without the lock file, asserts the floor environment (Streamlit equal to the floor, Pillow ≥13), boots a real server, and runs the UI smoke tests (boot, result page, buttons, import paths). Because the job pins the declared floor, the previous `>=1.40.0` declaration makes it install `streamlit==1.40.0` and fail at that step; the wheel metadata check now asserts the recorded Streamlit range too.
- `packaging>=24.0` added to `[dev]`: the new test uses its `Requirement`/`SpecifierSet` directly instead of relying on pytest's transitive dependency.

### Fixed — 2026-11-03 UI: marker and round checklist

- Ticking a round no longer collapses its part panel: the live completion count in the `st.expander` label changed on every tick, so the element remounted collapsed. The label is now stable and the count lives in the panel's progress bar.
- Streamlit 1.60 changed the tab and radio DOM (`div[data-testid=stTab]`, `label[data-testid=stRadioOption]`), which silently disabled the marker rules. The active tab wears the stitch-marker yellow again (with a keyboard focus ring), the chosen radio option its pale highlight, and round rows are highlighted edge to edge.
- Phones: the fixed app bar is paper-coloured so content no longer shows through it when scrolled; `client.toolbarMode = "minimal"` removes the Deploy button; the hero title no longer breaks mid-word.
- The subject-mask canvas iframe now uses the token system: Python passes the `theme.py` ink/edge/font values as component args, and the fallbacks in `index.html` are guarded by `tests/test_theme_tokens.py`.
- Part panels show the Chinese shape name instead of the internal enum.
- Browser regression covers keyboard focus and selected tab/radio colors, repeated progress changes with an open full-width highlighted panel, the theme received by the mask canvas, and the title and header at a 390 px viewport.

### Changed — 2026-11-03 Emoji removed from UI chrome

- Decorative emoji are removed from tabs, headings, sidebar titles, expander titles and buttons (about 60 places): the pattern-sheet concept reserves the marker yellow as the only highlight and yarn colours as the only other colour, and colourful emoji contradicted it. Status glyphs inside message bodies are unchanged. Tests, the browser script and the READMEs that quoted those labels are updated. Review notes: [Frontend design review](docs/archive/frontend-design-review-20261103.md) (Chinese).

### Fixed — 2026-11-03 Review provenance

- The result page and Markdown/PDF no longer treat strings, numbers, explicit `null` or unknown subject markers as human confirmation. Unrecognized records prompt rechecking and remain intact in backups; missing legacy fields remain supported. A head box is labeled as user-selected only when its coordinates are valid and match the recorded head span.
- Bump the export-cache version to **15** so live sessions do not reuse old confirmation text. Normal reviewed and pending records retain their existing labels; records are not independently authenticated.

### Changed — 2026-11-03 Static structure-data types

- Add `TypedDict` contracts for structures, parts, instances, positions and attachments across result, generation and rebuild paths. Unconstrained legacy metadata retains broad types and custom fields survive normalization; v2 continues to use the existing model validation and runtime data remains plain dicts.
- Add contract tests for model fields, serialization, legacy numeric values and custom fields. The static types do not add runtime validation; callers constructing `PatternResult` directly remain responsible for valid nested data.

### Fixed — 2026-11-03 Legacy structure result page

- A legacy backup with a dict or list in its custom `part_id` no longer crashes the result page after import. The custom value is retained, and v2 attachments still show the target part name.

### Changed — 2026-11-03 Static analysis-data type

- Add `AnalysisData` for the session result's `analysis` field, matching `ImageAnalysis` so mypy can check field names and value types. `ImageAnalysis.to_data()` returns the same plain serialized dict; imports and size regeneration retain their existing validation and data formats.
- Tests compare model fields, value types and required keys, and cover typed access and legacy backups missing optional fields. The type adds no runtime validation; callers constructing `PatternResult` directly remain responsible for valid nested data.

### Changed — 2026-11-02 Static result types

- Add static types for session results in `app.schemas`: `ResultData`, `PatternParams`, `PartData` and `RoundData` (`TypedDict`). At runtime results remain plain dicts; the types are for mypy only. `tests/test_result_types.py` checks that their fields match `CrochetStitch`, `CrochetPart` and `RESULT_KEYS`, and that generators produce only declared keys.
- The service layer (regeneration, import, progress, workspace, projects), edit history, result page and editors, CLI and orchestrator use these types. Read-only model functions (validation, exports, assembly, materials, preview) accept `Mapping[str, Any]`. Casts describe serialization and rebuilding boundaries, plus one temporary in-place skirt restore. `PatternResult` validates the top level only; rebuilding validates parts and pattern constraints, while other legacy parameter fields are only partly checked. `HEAD_OPENING_KEY` and `WAIST_POSITION_KEY` are `Final` so they work as typed keys.
- Repository-wide mypy (206 files) stays at 0 errors. Behavior is unchanged, except that an attached-skirt reservation row without a `notes` field now gets the same message as a row without a stitch formula instead of a `KeyError`.

### Changed — 2026-11-02 Pattern format migration chain

- Add a pattern-format migration chain (`app/services/migrations.py`). Backup import, share links, local history, project files and trial bundles all upgrade the pattern to the current format before validation and rebuilding. Records without a version field are upgraded to `schema_version="1"` and read exactly as before.
- Version checks now live in one place: newer, unknown or non-string versions are refused with "unsupported pattern format version". Previously share links, history and backup import each checked the version separately.
- Future changes to the stored format must bump `SCHEMA_VERSION` and register a step from the previous version. New tests check that every registered version upgrades to the current one, and that the frozen files in `tests/fixtures` import identically without their version field. The format version stays 1; files are unchanged.

### Changed — 2026-11-02 Per-tab workspace object

- Each tab keeps one workspace record (`workspace_{slot}`) bound to the current result ID. It holds the result state that is not a widget value: export cache and timings, PDF, share link, success/info messages, pending edit preview, personal notes, history-title draft and legacy-recovery notice. Reading it for a different result ID starts a fresh one, so a new generation, import or history load invalidates the old exports and previews without per-key cleanup.
- Edits and undo/redo carry only the notes, history title and recovery notice to the new result instead of copying widget keys between result IDs. The notes and title inputs start from the workspace, and reads take the input's latest value, so the text survives even if Streamlit discards the input's state.
- Remove the `_WIDGET_KEY_PREFIXES` registry. Replacing a result clears every session key that has the old result ID as one `_`-separated segment, so new widgets need no registration; result IDs are random tokens and cannot match per-tab records. User-visible behavior and project/backup formats are unchanged.
- Tests follow the new contract: cases that seeded or asserted legacy keys such as `pdf_*`, `share_token_*`, `export_cache_*`, `edit_*_pending_preview` and `project_recovery_notice_*` now read and write the workspace. New workspace unit tests cover result replacement, carry-over on edit, recovery after lost input state, and keeping every tab's records during cleanup.

### Changed — 2026-11-02 Progress record as the single source of truth

- Each tab keeps one physical-progress record keyed by semantic identity (part, copy, row) as the single source of truth. Round checkboxes initialize from it and write back through callbacks; "mark all/reset" update the record and any visible checkbox. Inline and paged progress share the same record instead of a separate paged copy.
- Edits, undo/redo, project restore and imports replace the record instead of migrating completion to widget keys of the new result ID; Streamlit discards the old result's checkbox state. User-visible behavior, project file format and retention rules are unchanged.
- Tests follow the new contract: cases that built progress from widget-key dictionaries or asserted widget keys after restore now check the rounds shown as completed through the renderer's own mapping, and widget-key seeding writes the record instead.

### Changed — 2026-11-02 Layering cleanup

- Move regeneration/import logic and physical-progress logic from `app/ui` to a new `app/services` package (`result_logic`, `progress_state`). Streamlit upload helpers move to `app/ui/uploads.py`, and `app/utils/images.py` no longer imports Streamlit. The CLI, evaluation, trial tools and project module no longer load Streamlit or the UI package: `import app.cli` drops from about 885 modules and 370 ms to about 397 modules and 270 ms (local measurement).
- Add a layering guard: `app/models`, `app/utils`, `app/services` and headless entry points may not import `app.ui` or Streamlit.
- Package discovery now includes only `app*`, so local ignored directories such as `eval_outputs/` no longer break wheel builds with "multiple top-level packages". Behavior and data formats are unchanged.

### Changed — 2026-11-02 Proportion styles and head-box prior

- Photo generation gains proportion styles. By default, the photo head ratio (clamped to 1:2–1:8) is compressed linearly into a Q-style 1:2–1:3 doll range; balanced (1:2–1:4.5) and photo (unchanged) are available. Review shows "photo ≈ 1:5.0 → doll ≈ 1:2.5", the stitch preview follows the style, and a blocked photo-style preview suggests switching back to Q. At the default classic gauge and 18 cm, photo ratios from 1:2 to 1:10 now produce heads of at least 24 stitches (1:5 previously gave 12).
- Sizing provenance adds `sizing.proportion_style`; the original ratio stays in `photo_head_to_height_ratio`. Older backups without the field import unchanged, and unknown values are rejected. Explicit dimensions such as quick resizing are not styled.
- The face box is expanded into a whole-head box (height ×1.5 upward from the chin, width ×1.2) for the head ratio, head span and the review page's default head box. The "too small" rejection now uses head size, while bounds and position checks keep the raw detection. The prior is not calibrated on authorized photos and must be reviewed with G3 data.
- The CLI adds `--proportion-style q|balanced|photo` for photo and mock modes (default `q`); evaluation reports record the default runner's style in `evaluator.proportion_style`.

### Added / Changed — 2026-11-02 Crochetability gate and evaluation policy 3

- Photo review, manual input and the CLI refuse a first generation when the widest head or body round (including a one-piece head section) has fewer than 18 stitches, and warn below 24; 6-stitch limb, tail and small-ear tubes only receive notes. Thresholds follow the repository's reference patterns (smallest full head 24 stitches, smallest body 30). Previously, at the default classic gauge and 18 cm, a 1:5 head ratio produced a 12-stitch head and 1:8 a two-round, 6-stitch "ball" that still passed the self-check. Edits, imports and regeneration of existing work only warn and never rewrite content.
- Photo review and manual input preview each part's widest round before generation. When blocked, the generate button is disabled and the page suggests the smallest single change of target height, head ratio or gauge preset. The CLI exits with code 2 and names `--height` or `--head` according to mode.
- Evaluation report schema 4 uses release policy 3: each case records `crochetable` and `crochetability`, and `crochetable_rate` is added (threshold defaults to 1.0). Parade ring starts and cross-part reserved-loop joins are reported as constructions the exporter declares unsupported; `parade_export_rate` fails only other translation gaps, and `parade_complete_rate` keeps the strict rate. The default evaluation runner does not apply the gate, so degenerate results keep their other metrics. The input manifest format is unchanged.
- Fix disabled primary buttons that still looked clickable. Share the one-piece neck marker and gauge preset labels as constants.

### Fixed — 2026-11-02 Physical-copy progress identities

- Separate progress when a graph instance ID collides with an ordinal ID for an extra copy. Structural edits match actual instances by ID and extra copies by ordinal, preventing completion from moving to another piece.
- When a legacy project contains ambiguous completed rounds, retain the current workspace and offer explicit recovery of unambiguous progress and notes; the affected rounds must be checked against the physical work. Legacy undo snapshots are handled conservatively too. New projects with an identity collision include `progress_identity_version="2"` and need a supporting reader; other projects retain their existing format.
- Map completed rounds directly and reuse the impact calculation to reduce preview work for large, sparsely completed patterns. See the [synthetic comparison](docs/archive/progress-identity-review-20261102.md).
- Fix circular imports when a fresh Python process imports `app.schemas` or `app.utils.project` first. Gauge constraints remain shared, and the model package's existing re-exports stay available.

### Fixed / Changed — 2026-11-02 Material bounds and CLI rollback

- Require finite ball weight, ball length and swatch weight of at least `0.000001`, and reject booleans in material measurements. Correct affected legacy files in the prior version and save a new project; normal decimals and numeric strings remain supported. Update the YarnSpec Schema and export cache to 14.
- Back up existing CLI destinations in 1 MiB chunks. Ordinary rollback restores content, permission bits and modification time; metadata failure still attempts content recovery, and failed content recovery retains a backup and reports its path. A single-output symlink cycle now produces a preparation error. See [limits](docs/image-memory.md).
- Reuse one per-color material aggregation during generation and refresh. See the [synthetic benchmark](docs/archive/optimization-review-20261102.md) for measurements and output hashes.

### Fixed / Added — 2026-11-01 Unchanged submissions and material previews

- Preserve the display ID, undo/redo snapshots, progress, notes and storage binding when the complete canonical pattern revision is unchanged. Resubmitting unchanged settings after undo no longer creates a new result and discards redo. Real instruction, color, gauge or provenance changes still create edits even when aggregate metrics match.
- Unchanged resize inputs retain the original sizing provenance when the structure and analysis agree. If an independently edited head differs, explain that synchronizing analysis can affect dependent parts. Unchanged structure, size and JSON submissions no longer show a contradictory regeneration success message.
- Add preview/cancel/apply to yarn estimates, comparing grams, metres, ball counts, allowance, labels and weighed-swatch origin. Apply retains latest progress and notes; legacy samples still require origin confirmation, and original trial bytes and record binding remain unchanged.
- Add 21 AppTest/regression cases and a thirteenth synthetic browser flow. Use a real instruction change in existing failure-injection tests to retain preparation atomicity coverage, and wait for the new upload to appear before submitting the browser import test. No new dependency, format or export-cache change.

### Fixed / Changed — 2026-11-01 Batch file protection and image-decode memory

- Resolve and validate all batch inputs/destinations together before generation. Reject cross-job symlink, hardlink, format and cyclic aliases to protect source images and prevent silent shared-output writes; retain per-job preflight, staging and rollback.
- Add `--workers 1–4`, defaulting to 1 instead of the previous fixed four to limit overlapping decodes. Explicit 4 restores that concurrency level. Invalid limits return 2; planning conflicts return 1, while ordinary per-image failures still allow other work to continue.
- Share image preparation across three loaders, applying EXIF on the decoder and detaching pixels after scaling. Cover orientations, transparency, exact pixels and closed-input ownership without changing image guards, pattern formats or export cache.
- Provide a reproducible single-process measurement tool: a local synthetic 39.69MP RGBA PNG used about 596.8→445.1 MiB on the byte path and 447.4 MiB on the file path, with matching pixel SHA. This is not a general or low-memory-container guarantee.

### Fixed — 2026-11-01 Weighed-swatch provenance and CLI gauge validation

- Record optional `params.yarn_spec.swatch_gauge` and match each part against that fixed origin. Default-gauge changes no longer move the measured basis for unchanged parts. Show origin and mixed estimates in materials/Markdown/PDF; ball-label edits retain the existing swatch density.
- Keep legacy unbound weighing data, using heuristic estimates until density is confirmed. Preserve original project revision checks, progress, notes and trial-source bytes/SHA. Cover confirmation, undo/redo, trial density previews and recovery with synthetic fixtures generated by actual old source.
- Require complete, finite and supported custom CLI density in manual, photo, mock and batch entry points. Invalid input returns code 2 before generation or file changes; existing outputs survive, with no silent fallback or clamping.
- Publish YarnSpec JSON Schema and increment export cache to 13; retain root backup/trial formats. Editing files with new provenance requires a supporting version. Add a twelfth synthetic browser flow without extending physical-result or independent-acceptance claims.

### Added — 2026-10-31 Independent hat and skirt-tube swatches

- Preview and apply independent swatches for hats and separate skirt tubes, with undo/redo and project recovery; attached skirts retain body gauge. Default-gauge changes retain explicitly set garment values and preserve manual work/progress when construction is unchanged.
- Use part gauge consistently for circumference, row height, color regions, shaping advice, materials and Markdown/PDF. Weight same-color usage by part before combining it. Measured swatch weight applies only at the default gauge; other gauges remain heuristic, with one shared ball label for all colors.
- Strictly validate optional `params.parts[].gauge`; omit unset fields so legacy project/trial identities remain unchanged. Editing files with the new field requires a supporting version. Keep root backup schema 1 and increment export cache to 12.
- Existing trials support one shared swatch: reject new records when any part differs from the default, and save work as a crochet project instead. Existing evidence stays bound to its original pattern. Add synthetic compatibility fixtures generated by actual old source and an eleventh browser flow, without physical-result claims.

### Added — 2026-10-31 Separate-head neck openings

- Preview an exact neck stitch target, apply it and restore the closed template for ladder, ideal and egg heads. Non-six-multiple targets such as 16 use executable X/A transitions and the actual final joining row. Reject one-piece construction and targets exceeding the head circumference.
- Persist optional `params.head_opening_stitches` through resizing, structure/gauge changes and backup/project/trial recovery. Assembly lists actual head/body joining rows and counts, with a manual alignment notice for different counts. Edit, import and printable-export gates reject contradictory targets, rows or closing instructions.
- Show declared openings in Markdown/PDF; increment export cache to 11 while retaining backup schema 1. The head is regenerated, other manual work follows existing preservation rules, and preview, undo/redo and progress isolation remain available. No physical dimensions, round-count replication, support or finished-result claim.

### Changed — 2026-10-31 Retain unrelated manual work during resizing

- Compare old and new generated constructions during size/structure edits, retaining manual rounds, colors and notes in unaffected parts. Materials, assembly, Markdown/PDF and backups use the combined actual content.
- Include one-piece construction, inferred dimensions and reserved skirt loops; reapply pinned waist placement. Changed global gauge or an unreproducible legacy template retains full regeneration. Revalidate the combined pattern before replacing current work.
- Exercise preview, apply, undo/redo and project restoration with progress on both arms. This preserves editing work without changing swatch/trial identities or file formats or claiming physical fit.

### Fixed / Added — 2026-10-30 Browser regression and history title retention

- Preserve saved history names and unsaved name drafts across undo, redo and older preview application; keep tabs isolated and retain explicit clearing.
- Keep the stored title column and serialized record consistent so cleared names do not reappear on load. Add five AppTest/storage regressions.
- Add separately locked Playwright tooling and browser CI using synthetic input and an isolated history database to exercise upload, embedded canvas, review, actual downloads, history isolation and project recovery in a fresh context. See the [browser guide](docs/browser-regression.md).
- Separate current gates from historical status entries. A private single-design reference diagnostic remains in ignored local output and does not establish an authorized-photo or physical-trial baseline; Beta status is unchanged.

### Fixed — 2026-10-30 Three independent-review boundary follow-ups

- Record explicit CLI part selection as `cli_explicit`, separately from complete human review. Photo and batch choices remain authoritative; UI, terminal and exports preserve outstanding subject, head and proportion checks. Full photo review still records confirmation.
- Retain raw trial-pattern bytes, SHA and record binding while deriving the session comparison baseline from the already validated, normalized import. Legacy trials can use saved swatch density; actual edits and tampered evidence remain rejected.
- Inherit the live workspace's history binding across undo, redo and previously prepared previews after first save. New generation/import resets the binding as before.
- Add a synthetic bundle generated by the actual `4a19d70` source and full AppTest regressions. Final independent acceptance at `55280fb` passed for all eight original issues and three follow-ups: 2076 passed, 2 skipped, with Ruff, mypy and diff checks passing. These software issues may close; merge CI must match the PR's current head, while product validation remains separate.

### Fixed — 2026-10-30 Pattern, instruction and saved-state consistency

- Derive yarn changes, adjacent-round transitions and color summaries from current round colors, preserving maker notes and migrating recognized legacy generated text on import.
- Join a skirt at its first round, including ruffled hems, and store its opening reference. Record radial bases and axial wall ranges so height and photo color mapping use the same wall; bases inherit the end color.
- Allocate a fresh display ID on history load and retain a separate history ID for updates. Photo/manual controls remain independent; escape both sidebar titles and generated summaries.
- Honor explicit CLI `--parts` in photo, batch, mock and manual modes while retaining defaults when omitted. Preserve the head diameter in merged head/body patterns for materials and backup recovery.
- Preserve edited stitches when only position or rotation changes. Dimensions, counts and joins still use generation checks. Derived color summaries alone no longer clear an entire part's progress.
- Add optional fields with backward-compatible reading, keeping backup schema version 1; update JSON Schemas and export cache version 10. These software checks do not establish photo accuracy or physical trial success.

### Fixed — 2026-10-30 Shaping intervals follow actual stitch order

- Check explicit “one increase/decrease every N plain stitches” claims against actual gaps, including the round boundary. Reject unequal gaps with the right average, non-integral averages and W/M operations that change two stitches at once.
- Preserve correct staggered groups, nested repeats, FLO/BLO and invisible decreases. Inspect the compact operation tree without expanding thousands of repeats. Edits, imports and exports share checks; failed edits/imports preserve current work.
- Export cache version 9 revalidates old Markdown, Parade and PDF outputs; pattern and project formats are unchanged.

### Fixed — 2026-10-29 Whole-round prose and formula consistency

- Reject claims such as `6V，均匀减6针` or `6X，隔2针加1针` when the formula contains no corresponding shaping. Check outer increase/decrease repetition counts, direction and every-stitch wording so correct arithmetic cannot hide contradictory technique instructions.
- Compare normalized decimal strings instead of converting untrusted prose counts to integers. Excessive digits produce bounded diagnostics; equivalent zero-padded counts remain accepted.
- Share checks across edits, imports and exports. Failed imports retain the current pattern, progress and notes for retry. Conditional/future-round prose retains its existing interpretation; pattern/project formats and export-cache version are unchanged.

### Fixed — 2026-10-29 Trial identity migration and independent-sample gates

- Upgrade legacy bundles only after verifying exact source bytes, original metadata and any legacy fingerprint. Retain observations, partial measurements and source bytes; rebind sidecars when resaving.
- Version 1 canonicalizes gauge and physical round-sequence multiplicity, ignoring part order, labels and equivalent copy grouping while preserving round order and quantities. Cosmetic reordering cannot establish design diversity or holdout independence.
- Always check source-SHA overlap across cohorts. Legacy records remain reportable, but unverified identity blocks readiness and calibration candidates; expose identity completeness and pending-upgrade counts.
- Add `crochet2pattern-trials migrate` for standalone records with their exact source. Retain measurements, forbid input overwrites and preserve existing output on replacement failure. Trial/report root schemas remain 2/3.

### Security — 2026-10-29 Effective dependency audit and patched dependencies

- The dependency audit now exports the fixed requirements of every extra from `uv.lock` and checks each package, fails when that export is empty, and runs on every pull request. The former `--local` invocation audited no packages inside the uv overlay yet reported success.
- Upgrade Pillow to 13.0.0 (uploads decode untrusted images), Streamlit to 1.66.1 (which no longer depends on GitPython) and certifi to 2026.10.23, clearing the known advisories in the lock. The Pillow lower bound is now 13.0.0.
- Uploads are decoded only as JPEG/PNG, matching the uploader. The Docker production image starts with `--client.showErrorDetails=none`, so uncaught exceptions no longer show types, messages or tracebacks in the browser; local development keeps full tracebacks.

### Security — 2026-10-29 Escaped external text and host-only thumbnails and brush masks

- Free text from share links and imported backups, such as part names, colors and notes, is escaped on result pages and in Markdown exports, so it can no longer render external images or disguised links. Markdown table cells additionally escape pipes and fold line breaks.
- Share links, backups, project files and newly created trial bundles omit the 96 px `preview` thumbnail and the hand-corrected `mask_review` brush mask. In-session results and local history keep thumbnails, and history accepts only locally generated JPEG data URLs.
- Pattern revision hashes exclude the photo thumbnail and brush mask. Projects saved earlier with a thumbnail still restore their progress and notes and omit the thumbnail when saved again; the project format remains schema 1.

### Fixed — 2026-10-29 Generation correctness and export consistency

- One-piece head-and-body generation now refuses, with advice to use separate parts, when the body top is wider than the head, instead of silently producing a pattern that only increases and has no head ball; safety eyes use the head's own peak. Ideal ball/egg rows follow the meridian arc πD/2, fixing flattened shapes and consecutive +12 jumps.
- Parts started from a ring or chain (such as a separate skirt tube) are reported as partial CrochetPARADE exports instead of complete magic-ring exports. Datasets with skirts therefore cannot meet the G3 complete-Parade-export floor yet; see [evaluation](docs/evaluation.en.md). Bodies and limbs that start from a magic ring are flagged accordingly.
- C2C row arrows now match the color reading order, and contradictions between "increase/decrease 1 every N stitches" or "evenly increase/decrease N" notes and the formula are reported. Skirt joins state the FLO/BLO orientation premise, and the profiled body's last round is sewn to the head's closed bottom. Export cache version 8 regenerates old Markdown and Parade caches.

### Fixed — 2026-10-29 Import validation and resource limits

- Share-link decoding rejects NaN/Infinity and duplicate keys, matching backup import. Legacy structure shape, type and color fields must be scalars, preventing persistent result-page errors after import.
- Add a 16,000-round total across parts (the 2,000-round per-part and 64-part limits are unchanged), bounding import, export and progress costs for oversized backups.
- Grids over 10,000 cells use a raster preview without symbols and build the SVG only when its download is clicked, with unchanged content. An 80,000-cell grid's session footprint drops from about 15 MiB to 1.2 MiB; common sizes generated with default ratios keep the vector preview.
- Grid dithering caches the nearest color per rounded RGB value and diffuses error with scalar arithmetic, producing identical cells. Photos dither about 1.5–4.5× faster and flat or noisy areas over 20× faster (a 48,000-cell noise image drops from about 17 s to 0.5 s).

### Fixed — 2026-10-29 G4 trial gates count design fingerprints

- Distinct patterns and calibration/validation isolation now use a design fingerprint (normalized gauge and per-round stitch structure) instead of byte hashes that change with diagnostics timing, thumbnails, colors or yarn labels, so regenerating one design counts once. Byte hashes still verify integrity, and older records without fingerprints fall back to them.

### Changed — 2026-10-29 Container image and CI

- The CI Docker job now runs the built container: it probes health, checks the non-root user and production flags, and calls OpenCV GrabCut, Haar and color conversion, failing on missing libraries or startup errors.
- The runtime stage no longer installs libglib through apt: the opencv-python-headless wheel bundles its libraries, so builds no longer depend on deb.debian.org.
- Share-link wording now says no extra backend or database is needed while the token is still sent to the host running the app; the post-load notice no longer claims permanent automatic saving.

### Fixed — 2026-10-29 Custom-part and bulk-progress isolation

- Disambiguate checkbox identifiers across the complete pattern when a custom name such as `practice_copy2` aliases another part's second copy. This fixes duplicate-widget errors and restoration of one completion as two, while retaining existing session identifiers for ordinary names.
- Share the mapping across inline/paginated progress, project saving/restoration, edits and undo. Removing stale rounds no longer deletes similarly named parts' completions. Saved part names, instance IDs, round numbers and project formats remain unchanged.
- Update bulk completion, reset and resume navigation through callbacks before rendering, avoiding interrupted reruns that discard other parts' progress or project notes. Files that already contain incorrect completions still need review against the physical work.

### Fixed — 2026-10-29 Grid generation, project saving and failure preservation

- Convert NumPy assignment indices to native integers in both plain and dithered generation. This fixes project JSON serialization errors that also interrupted UI generation; the project format remains 1.0.
- Prepare the complete preview and downloads before changing the current grid or histories during generation, restoration, cell/rectangle recoloring and undo/redo. Preparation failures display an error and preserve the grid, editor inputs and both history stacks for retry.
- Reset history and coordinates only after successful replacement. No-op edits retain redo and cached output; SVG, Markdown and project JSON stay aligned with the preview after edits and history switches.

### Fixed — 2026-10-29 Invisible-decrease identity and actual round labels

- Preserve `inv-sc2tog` in the operation tree, iteration and canonical notation instead of merging it into A because both consume two stitches and produce one. Counting, edits and existing backups remain supported.
- Explicitly report invisible decreases and their prose cues outside the current DSL/chart subset. DSL stops at that round and reports partial export; Markdown retains the technique or requests review, and PDF retains original notes. Skirt editing rejects automatic FLO reservation on these rounds.
- Use recorded round numbers in ring charts, symbol strips and truncated-strip headings, with positional fallback for legacy missing labels. Increment export cache version to 7 to regenerate old reports and PDF caches.

### Added — 2026-10-29 Stitch-parent connection inspector

- Add an opt-in adjacent-round inspector informed by connectivity and explicit-domain conventions in CrochetPARADE, stitch-grapher and related GitHub projects. Preserve ordered X/V/A/W/M operations and scoped FLO/BLO while displaying source and produced stitch indices.
- Show 24 operations per page, skipping repeated subtrees by counts. Download the current SVG window or JSON bound to the pattern hash. Explain missing formulas, first rounds and unsupported techniques without inferring positions from totals.
- Inspection preserves patterns, progress and notes; edits reset the view. No dependencies or pattern/project formats changed. The diagram is not a physical layout or tension simulation.

### Fixed — 2026-10-29 Result replacement and leg-join state cleanup

- Release the old result's leg-join restore preview, inputs and part selections when generation, successful import or editing replaces it, preventing session-state accumulation. Failed operations retain the current plan.
- Match complete result-ID boundaries during cleanup so another result with the same ID prefix keeps its progress, notes and export cache.
- Replace leg-join preview and calculation output together, clearing old controls after edits so users can continue entering plans. Photo and Manual results remain independent.

### Fixed — Stable part selection for leg-join comparison

- Track selected part names rather than list positions: reordering keeps the selected part, deletion or renaming clears it with a prompt, and copy-count changes are rechecked.

### Changed — Remind users about later rounds and finishing

- During leg-join comparison, flag later rounds and finishing-related wording for manual review. Matching counts only establishes agreement with the pattern record; it does not infer an open edge or physical feasibility.

### Added — Preview leg-join plan restoration

- Compare current and proposed inputs before applying or cancelling a restore. Changing the source file, restore method or current inputs invalidates the preview and preserves the inputs until a fresh preview is made.

### Added — Leg-join count diagram

- Display and download an SVG of both leg openings, the two chain sides and the resulting stitch count. The diagram follows current inputs and explicitly does not depict actual stitch positions, direction or physical proportions; patterns and projects remain unchanged.

### Added — Compare leg-join plans with the current pattern

- Choose the two corresponding pattern parts to compare round numbers and stitch counts. Check at least two copies when both sides use the same part; report missing rounds, mismatched counts and insufficient copies.
- Comparison changes neither pattern nor progress and does not verify real openings, markers or direction. Part choices are not included in the standalone plan.

### Added — Restore manual leg-join plans

- Upload or paste a previously downloaded plan. Validate version, fields, values, markers and recalculated totals before restoring the form. The 16 KiB limit, duplicate-key rejection and atomic validation preserve current inputs on failure; successful restoration leaves pattern and progress unchanged.
- Standalone plans are not bound to a pattern or interchangeable with project backups; openings and direction still require manual review.

### Added — Manual chain-bridge leg-join plan

- Add a separate planning aid to record each open leg round, stitch count and marker, plus bridge chains. Validate input ranges and calculate a round with one single crochet per opening stitch and on both sides of every chain; download a standalone JSON plan.
- The tool does not verify that openings or stitch locations exist and does not generate or change patterns. Plans cannot be imported as patterns or projects; other techniques and physical results need manual review.

### Added — 2026-10-28 Trial save history

- Add independent undo/redo for saved swatches, yarn, partial measurements and completion status. Restore the form, comparison and download together while preserving the current pattern, crochet progress and project notes.
- Unsaved or invalid input blocks switching and is retained. Identical saves preserve history and redo; changed saves after undo clear redo. Validation or serialization failures leave the active record and history intact.
- Keep at most eight snapshots and 2 MiB combined in the session, sharing the source pattern. Reopening or closing a record clears history; ZIPs omit it. Trial formats and dependencies are unchanged.

### Added — 2026-10-28 Resumable partial trial measurements

- Save dimensions, yarn, timing and notes in stages with missing values left blank, then restore in a later session. Keep fields visible across completion-state changes and leave completion dates blank until entered.
- Returning a completed record to draft retains observations. Completion still requires a measured swatch, date, required measurements and consistent modification details. Partial measurements stay out of finished-item comparisons and calibration.
- Add optional schema-1 `draft.json` to ZIP bundles, bound to the exact trial JSON bytes with separate type/range checks and a 512 KiB limit. Failed saves/imports preserve current work. Publish the draft JSON Schema.
- Formal trial records remain schema 2. Original two-file bundles and completed records stay compatible; three-file draft restoration requires this version. No new dependencies or physical-trial evidence.

### Added — 2026-10-27 Saved measurement comparisons and density previews

- Compare saved swatch density, height, yarn and timing with the original pattern. Keep unmeasured/missing values explicit, distinguish full-project time from the baseline, and identify modification effects.
- Preview regeneration of the original pattern from a saved measured swatch, retaining target dimensions, structure, yarn specifications and pinned waist placement while rebuilding rounds and joins. Equal density preserves custom edits; a different source cannot use this action.
- Show stitch/row density in edit previews. Applying changed density clears completed rounds for review, preserves notes and supports undo. Trial records/downloads stay unchanged; unsaved form values do not drive regeneration.
- Existing formats, generator constants and dependencies remain unchanged. No new physical measurements or finished-item validation.

### Added — 2026-10-27 Physical trial recording in the web UI

- Add draft/completed trial forms for anonymous IDs, swatches, yarn, measured size/usage, scoped timing and pattern modifications, with a height-deviation display. Retain trial schema 2 and existing calibration rules.
- Download the exact source pattern and record together as ZIP. Reopen both from the sidebar in a fresh session or restore only the record within a result panel. Live edits never rebind measurements; Photo and Manual trials remain separate.
- Verify source hashes and derived metadata, bound archive reads and reject damaged or mismatched contents without replacing current work. Trial records remain separate from backups, projects and shares; downloads reflect the last successful save.
- Share draft creation from one bounded byte snapshot between CLI and UI, preventing metadata/hash reads from seeing different file states. Reject duplicate JSON keys, non-finite numbers and oversized input. No new dependencies or physical-trial evidence.

### Fixed — 2026-10-27 Preserve waist preferences across regeneration

- Save a manually selected waist's relative position in the candidate sequence. Size and structure regeneration map it to a new candidate while retaining the original fraction across repeated resizes. Pattern backups and projects retain the preference; older patterns remain automatic.
- Add impact previews for pinning the current waist and unpinning it. Policy-only changes retain current stitches and progress, support undo, and take effect on the next regeneration. Explicit skirt removal also drops the preference.
- Validate optional `params.skirt_waist_position` and its attached-skirt context. Retain schematic downloads and show a review message for valid imported joins outside the adjustable body region. Pattern/project schemas remain at 1 with no new dependencies.

### Added — 2026-10-27 Edit impact previews and skirt waist placement

- Retain completed rounds before the first changed instruction, color or row. Insertions, deletions and reordering never transfer progress to shifted work; gauge, part-wide, dependent joins and physical-pair changes remain conservative.
- Preview part, round, size and advanced JSON edits with affected ranges, retained/cleared counts and derived changes. Apply the reviewed candidate using current progress or cancel; preview application and undo/redo run before rendering to prevent stale widgets.
- Add a connection schematic and actual waist-round selector. Restore generated reservation instructions, create the new FLO reservation and resize recognized generated skirt shaping when needed. Reject unsafe custom rewrites, existing loop techniques and occupied reservations.
- Download SVG schematics and include matching sequence tables in Markdown/PDF. Bump export cache to 6; pattern/project formats stay unchanged. No new runtime dependencies or physical-trial evidence.

### Fixed — 2026-10-26 Progress dependencies and resume navigation

- Fix order-dependent progress retention in deeper reserved-loop join chains. Collect direct changes first, then propagate invalidation until no further dependents are affected. Preserve independent parts and unchanged foundations.
- Show the selected part's next unfinished physical copy and round in paginated patterns, with a navigation button that does not alter progress. Disable it when complete and return to the first round after reset.
- Keep empty imported colors out of paginated round labels instead of displaying `None`.
- Add connection-order permutations, transitive invalidation, reorder-only preservation, directionality and restored cross-copy navigation regressions. Project formats and dependencies are unchanged.

### Added — 2026-10-26 Explicit skirt joins and saved crochet projects

- Record the actual foundation round, following FLO reservation round and skirt's first-round BLO range. Generate the waist against real body stitches, use merged one-piece numbering and recompute after resizing. Waist placement remains a template choice requiring a physical trial.
- Check referenced rounds, adjacency, counts, loop scope and matching physical copies. Reject contradictory joins during edits, imports and printable export. Render Markdown/PDF assembly from current references; legacy backups remain readable with a review notice. DSL explicitly reports unsupported cross-component reserved-loop joins.
- Add a project-save dialog capturing current per-copy progress, personal notes, software version and a SHA-256 pattern revision. Reopening restores this state; mismatched revisions or invalid round identities leave existing work untouched.
- Edits retain unaffected progress and notes, report cleared completed rounds, and invalidate dependent skirt progress when its body changes. Undo restores progress; paginated progress is portable too.
- Keep pattern backup schema 1 and add independently versioned `project_state`. Share links and ordinary pattern backups omit personal state. Publish two JSON Schemas, bump export cache format to 5, and add no runtime dependencies.

### Fixed — 2026-10-25 Fresh-session recovery and printed guidance

- Add a sidebar backup opener without requiring a seed result or enabled history. Accept UTF-8 JSON uploads up to 20 MiB, or pasted JSON up to 2 MiB, including BOM. Reuse it on result pages while retaining the existing paste interaction.
- Enforce byte limits and reject duplicate JSON keys, non-finite numbers, invalid encoding and incomplete backups. Replace only the target result after format and pattern validation; failures retain existing work and caches. The backup schema is unchanged.
- Share stitch guidance across the UI, Markdown and PDF. Include FLO/BLO/W/M, distinguish sc2tog from invisible decreases, and identify letters as project conventions. Follow explicit placement without an extra automatic stitch shift; switching to joined rounds requires checking counts and positions.
- Bump export cache format to 4 and require regeneration of old PDFs in surviving sessions. Add recovery, malformed-input, tab-isolation, print-consistency and cache-upgrade regressions without new runtime dependencies.

### Added — 2026-10-24 Scoped front/back-loop notation

- Support `FLO(...)`, `BLO(...)`, `FLO: ...`, stitch suffixes such as `sc-FLO`, and standalone whole-round loop directives. Preserve counts, shaping and local loop positions.
- Retain qualifiers in Markdown, label chart positions F/B with tooltips, and emit CrochetPARADE `scfl`/`scbl` plus shaping suffixes. Bump export cache format to 3.
- Reject conflicting scopes. Unresolved loop prose and first-round loops without a supported foundation no longer fall back to ordinary sc. Manual notes remain saveable; partial DSL exports retain the valid prefix and other parts. Distinguish generated tail-threading closures from crochet-loop instructions and qualify general invisible-decrease advice.
- Recheck the original bee pattern and correct fixture/glossary BLO labels to FLO. Export tests check actual loop types and separately report inferred placement in the remaining aggregate rounds.
- Synthetic tests cover limits, independent counts, placement, edits, backups, printable exports and calculator interaction. No third-party patterns, new dependencies, external simulation or physical trial were added.

### Changed — 2026-10-24 Generate explicit increase placement

- For consecutive +6 rounds, split even plain-stitch gaps around V: 18→24 uses `(X,V,X)×6` and 30→36 uses `(2X,V,2X)×6`; odd gaps retain end-of-group increases. New patterns no longer append a separate vague half-group shift instruction.
- Numeric edits update affected neighboring placement while preserving finishing actions and custom arrangements. Legacy backups retain their original notes on import.
- Cover ladder/ideal/egg heads, gauge presets, one-piece construction, edit restoration and idempotence. This specifies operations; it does not establish an improvement in physical shape.

### Fixed — 2026-10-24 Preserve stitch placement

- Retain ordered repeat groups in the notation parser. Markdown stitch columns, symbol strips and CrochetPARADE exports now preserve explicit placement instead of replacing staggered or clustered shaping with uniform groups.
- Export explicit mixed shaping, W/M stitches, uneven placement and nested groups, keeping each source round on one line. Contradictory or ambiguous instructions stop that part at its valid prefix; other parts still export.
- Report physical `inferred_rounds` for aggregate-only uniform fallback. Free prose and textual placement hints still require review; Markdown no longer invents formulas alongside custom prose. Mixed rounds without explicit placement display a review marker.
- Reuse compiled rounds across identical copies and expand only visible chart symbols. Keep large repeats compact, version export caches independently of package releases, and prevent metadata line breaks from becoming DSL instructions.

### Added — 2026-10-24 Round-notation checks

- Count X/V/A/W/M, US sc/inc/dec aliases (including sc-inc, sc2tog and inv-sc2tog), and repeat groups, including split positions, mixed shaping and non-six-sector rounds.
- Edits, backup imports and Markdown/PDF exports compare consumed stitches, output stitches, increases and decreases against numeric fields. Previously accepted contradictory notation must be corrected before applying or exporting.
- Add an optional calculator to the round editor. It displays all four counts without changing the pattern. Unknown techniques and free prose still require manual review.
- Bound repeat counts, nesting and expression size without expanding repeats. Clarify four ambiguous increase abbreviations in historical fixtures. New tests use synthetic examples; local reference files are not included. No new dependencies.

### Added — 2026-10-15 Foreground correction brush

- Add a local photo canvas with add/erase, brush sizing, overlay visibility, undo for the last 20 strokes and reset to automatic segmentation. Each completed stroke updates the selection.
- Corrected masks drive geometry, palette and generated color bands through independent observations with fresh color caches; body boxes apply afterward.
- Bind corrections to the cropped photo and validate dimensions up to 160×160. Empty selections block generation; failed segmentation can be manually recovered. Backups and resizing preserve corrections and provenance; existing share-size limits remain.
- Package the HTML/JS assets without external scripts. Add 14 regressions and verify brush operations plus Streamlit generation/reset in a real browser. Real-photo accuracy and physical crochetability remain unverified.

### Added — 2026-10-15 Reviewed body region

- Add a blue body box to photo review, measuring existing foreground inside the selected region. Reject empty/tiny regions, unavailable foreground and mock geometry.
- Retain the original silhouette alongside the body box and body profile in full-image coordinates. Generation, backup import and resizing reuse the body profile and synchronize its vertical span; head and body review work together.
- Reject imported body-box/span mismatches and label the manual source in results and printable exports. Legacy backups remain compatible; existing URL size limits still apply.
- The box constrains shape only; colors use the updated vertical interval without horizontal resampling. No automatic part-recognition, real-photo accuracy or physical-validation claim is made.

### Fixed — 2026-10-15 Separate geometry and color masks

- Preserve the un-eroded subject mask for geometry; palette and bands share a derived interior mask, with one segmentation per pipeline run.
- Both segmentation and background-threshold fallback measure the longest contiguous foreground run per pixel row, then average bands and normalize by the peak. Detached arms and noise are no longer added to torso width.
- Add regressions for thin features, equal-area layouts, detached arms, translation, and fallback consistency. This remains a geometric approximation, not part recognition; touching limbs and physical accuracy remain unverified.

### Changed — 2026-10-14 Remove cloud LLM integration

- Photo and batch CLI default to local vision; `--local` remains compatible. UI offers local analysis and explicit mock data, followed by review and deterministic generation.
- Remove provider requests, retries, prompts, credentials and Base URL settings; remove both SDKs and 11 unused transitive packages from the lockfile.
- Ignore legacy provider environment variables and purge stale session credentials/AI selection. Historical provenance, usage and semantic-color fields remain importable.
- Library migration: constructors no longer accept provider arguments; `vision_mode="ai"` raises explicitly. Use parameterless constructors and `vision_mode="local"`.
- Replace retired provider tests with no-network/no-SDK runtime, legacy-key isolation, backup and distribution regressions. Recognition and physical-validation limits remain.

### Fixed — 2026-10-14 Profile fitting

- Fit complete profiles on a six-stitch lattice under gauge/source-stitch constraints, preserving the first round and round count while reducing greedy lag.
- Add an exhaustive optimality oracle and 18 reproducible synthetic comparisons; review original pear, staggered-increase, CYC and AmiGo sources.
- Document local operation and LLM removal scope; provider interfaces, SDK dependencies and invocation defaults remain unchanged.

### Fixed — 2026-10-12 Narrow color stripes

- Round colors now maximize interval coverage instead of sampling a single midpoint, reducing
  magnification of tiny color slivers. Unrepresented blocks trigger review notes in patterns and exports.
  Summaries use the actual working direction and dominant-color ties are deterministic.
  Ordinary color changes no longer promise to eliminate spiral-round jogs.
- Refine coarse photo color bands using sustained row majorities with sufficient foreground support.
  Nine original synthetic narrow-stripe cases improve from 0/9 to 9/9 exact stripe recovery;
  single-row noise, sparse foreground and minority patches have regression coverage.
  Raw spatial evidence is retained. This is a development diagnostic, not real-photo or physical validation.

### Added — 2026-10-04 reviewable editing workflow

- Crop photos and review subject/head overlays, proportions, and parts before generating without a second AI call.
- Part forms, round-table edits, bounded session undo/redo, and before/after comparisons; failed edits preserve results.
- Count yarn once per color with a separate subtotal; ball labels, weighed swatches, and allowances drive purchasing.
  Preserve specifications through resizing and backups; preserve matching one-piece quantities and reject mismatches.
- Cooperative active-stage budgets, timings, fallback reasons, and explicit API retry accounting with unknown usage marked.
- Correct deployment-host privacy wording and remove uncalibrated confidence defaults. Legacy numeric values remain
  importable but are not displayed as probabilities. New optional metadata keeps old backups readable.

### Fixed — 2026-10-04 audit

- Address four additional GitHub alerts reported while publishing PR #13: lock `urllib3 2.8.0`
  (GHSA-8988-9cw3-xx77, GHSA-vxq7-64xx-v4gw, GHSA-gh4c-6fx4-qh6g) and `GitPython 3.1.62`
  (GHSA-59cr-6r3x-644w). Only these two packages change; the combined environment audit finds no known vulnerabilities.

- Patch GHSA-8xx6-hgc6-gc2m discovered during GitHub publication: update locked
  `httpx2` and matching `httpcore2` from 2.11.0 to 2.12.0; other dependency versions stay unchanged.

- Correct validation messages and reject arithmetic errors before applying edits, imports,
  or printable exports; failed edits preserve the current result and cached exports.
- Route shares, history, and backups through one import boundary with nested metadata
  validation/normalization. Missing legacy fields remain supported; invalid fields require repair.
- Separate Parade syntax checks from complete export; truncated exports cannot pass release gates.
- Include source, dimension provenance, generator/exporter versions, and physical-validation
  limits in Markdown/PDF. New results record optional `generator_version`; legacy versions
  remain unknown without changing the schema version.
- Disable history by default; only explicit `CROCHET_HISTORY_MODE=single_user` enables it.
  Shared/public deployments must keep it disabled. Existing databases are preserved;
  this does not implement multi-user authentication or ownership isolation.

### Changed

- **crochet_params module split** (1396 → 892 lines): materials, assembly,
  time estimation, and the one-piece merge moved into dedicated
  `materials` / `assembly` / `time_estimate` / `onepiece` modules, with the
  micro part-access helpers and part-name constants sunk into a
  dependency-free `parts` base. Previously public names remain importable
  via re-exports; zero behavior change.

### Fixed

- **External-audit adoptions**: the Lab conversion no longer builds the same
  xyz array three times via `np.stack` (grid-quantization hot path);
  "未收口/没收口/别收口" closing-note variants are no longer misjudged as
  closed, which silently dropped real openings from assembly text; the
  history LIKE ESCAPE clause is a named constant and `load_result` drops
  preview values that are not JPEG data URLs; thumbnail generation moved to
  `utils.images` with pose optional-dependency failures logged separately
  from runtime errors; the Docker base image is pinned by OCI digest with
  an in-file refresh procedure.

- **Round-7 review (UI and auxiliary layers)**: the "silhouette verification"
  visualization had been silently disabled by a dict/attribute access mismatch and
  now renders again with graceful degradation. Invalid provenance values in
  imported backups (`geometry`/`sizing` confidence and photo ratio) render
  escaped instead of crashing the whole page. Trial CLI: JSON `Infinity`/`1e400`
  payloads that escaped raw `int()` with OverflowError now produce the friendly
  error; booleans and fractional numbers are no longer silently coerced (trial
  model numeric fields follow the project-wide decoding convention); unwritable
  output paths exit 1 with a message. The evaluation loop re-verifies the frozen
  SHA256 before scoring each case, so sources replaced mid-run are never scored.
  Silhouette rendering degrades for pure-dome parts instead of raising. Source
  labels are escaped, the Parade download key is purged with its result, the
  delete escape hatch for corrupted history records is reachable again, and
  pre-upgrade grid caches fall back instead of raising KeyError.

- **Assembly prose, download backoff, and resource-bound review**: edited assembly
  text no longer leaks internal instance ids (e.g. "尾巴（tail）") into the Chinese
  prose; lone instances merge into one complete sentence while custom ids of multiple
  edited copies are kept for distinguishability. After one failed pose-model download,
  the process skips further attempts for 300 seconds (a valid cache always bypasses
  this; success clears it). Pattern part dimensions now share the structure layer's
  (0, 200] bound, and the schema documents emit `maximum`. Legacy structures reject
  duplicate part names and non-string names; both formats cap parts at 64. Validation
  and rebuild gain resource bounds of 2000 rounds per part and 100000 stitches per
  round, reporting the excess instead of grinding through pathological JSON. The
  head/body proportions line is generated and rewritten through one shared prefix
  constant, and the share decompression limit constant is renamed to reflect its
  byte semantics.

- **Physical input bounds and preview rotation**: generation validates both legacy
  and v2 structure dimensions before building rounds. Boolean, non-finite, non-positive,
  and over-200cm dimensions are rejected; legacy numeric strings are normalized and
  optional null dimensions use the existing fallback. Direct `Gauge` construction
  enforces the existing 6–40 stitches / 8–50 rows per 10cm bounds; mapping/UI fallback
  and clamping remain supported. Pattern dimensions must be finite and positive;
  invalid backups require correction before import. The preview now applies Y rotation
  after Z and X, retaining previous two-axis orientations.

- **Edited counts and assembly connections**: model rebuilding, validation, and Parade
  share lossless integer decoding; booleans cannot become valid stitch or part counts.
  Empty rounds and duplicate row/part identities are rejected before edits/imports
  replace the current result or its cached exports. Legacy integer strings and integral
  floats remain supported; backups with empty parts or duplicate identities need JSON
  correction before import. Assembly text follows edited anchors, methods, and individual
  copies, distinguishes head/body regions in one-piece patterns, and reports quantity/graph mismatches.

- **Shared, repeatable photo observations**: silhouette, palette, and color bands reuse
  one segmentation per generation, including failed extraction. New runs recompute
  observations after image edits. Seeded GrabCut initialization prevents repeat-run
  drift, and out-of-bounds face seeds are ignored. Pose downloads use unique staging
  files, verified atomic replacement, an in-process thread lock, size/deadline checks,
  and cleanup on failure. Explicit head resizing now uses the requested absolute
  diameter; size controls retain existing values outside their usual slider ranges.

- **Gauge and structure edit consistency**: edited `params.gauge` now drives materials,
  exports, previews, and regeneration, with legacy result-level fallback and normalized
  numeric strings. Non-finite and boolean gauge inputs use the default. Resizing scales
  the existing graph while retaining quantities, poses, connections, colors, and part
  edits. Cylinder diameters, cup depths, skirt hems, and explicit colors now affect the
  pattern. Tapered skirts use valid decreasing rounds; an empty edited structure fails
  explicitly instead of restoring the detected parts.
  Applying local edits clears stale PDF/share caches; complete backups carry their
  schema version and oversized shares direct users to the backup download.

- **2026-09-07 input, batch, and export review**: allocate collision-free batch output
  names even when generated suffixes collide with source stems; isolate corrupt-image
  `SystemExit` failures, skip directories with image extensions, and validate the input
  directory before creating outputs. Reject fractional, boolean, non-finite, negative,
  and empty stitch inputs without changing valid non-six-sector or compound-decrease
  semantics. Fix Parade plain-round arithmetic, invalid starts, first-round colors,
  and dangling part separators. Require complete single-stream share payloads and
  symmetric byte limits; reject unknown backup versions and non-object history JSON.
  Evidence: [review record (Chinese)](docs/archive/optimization-review-20260907.md).

- **Executable correctness is now a gate, not only a reported metric**: authorized-photo
  evaluation adds `min_parade_export_rate` (100% by default). A failed complete
  CrochetPARADE export now makes both the case and overall `passed=false`, preventing an
  algebraically valid but unrepresentable result from becoming a release false positive.

- **External AI (GPT) audit and second-review remediation (all 7 findings addressed)**:
  ① **the 5th prior correction** — decrease exceeding the pure-A
  pairing limit (dec > prev//2) downgraded from hard error to note:
  the mechanical counterexample is 4 stitches closed by a single
  sc4tog (3 > 2 yet fully hookable); M (3-to-1), sc4tog and loop
  decreases are all real combined decreases in our own glossary; the
  decrease field means "net stitch drop" and cannot double as "the
  number of A stitches"; blocking errors retain broken algebra, empty
  rounds, non-numeric fields, and stitch counts below one (with a new
  sc4tog counterexample test).
  ② Minion leg R3 comment errata: the composition is 5×sc2tog +
  sc4tog for a net decrease of 8 (not 4×sc2tog), corrected across the
  relevant tests and bilingual documents with the errata kept.
  ③ Stitch-glossary fact fixes: slip stitch UK is "ss";
  ladder end dtr→trtr (current CYC chart; "ttr" noted as regional);
  bobble (bo) and cluster (CL) split into two entries (different
  structures); the "full CYC chart" claim narrowed to "common
  entries"; the Tunisian "13 entries" clarified as 12 stitches plus a
  merged FwP/RetP row. ④ **one-piece gating gap** (real bug): the
  merged "head+body (one piece)" name slipped past exact-match gates,
  silently dropping the safety-eye row and its age warning — gates now
  explicitly recognize the one-piece semantic name without misclassifying
  accessories such as head covers (positive and negative tests added).
  ⑤ Safety wording hardened:
  "prefer embroidered eyes" → "forbidden under 3 and for pets — must
  use embroidered eyes"; the wire row's children alternative no
  longer mentions bamboo sticks (no rigid internal armatures).
  ⑥ Export consistency: markdown now renders single inc/dec groups
  without the ×n suffix (same convention as parade); the "all notes
  are skipped" documentation wording corrected (non-6-multiples and
  wide jumps only warn; mixed and over-expression rounds are skipped);
  second review fixed the shared Markdown/Parade decrease-group offset
  (sc2tog consumes two source stitches, so 12→6 is `(A)×6` / `6sc2tog`
  rather than a group with an extra X/sc);
  Parade now stops each part at its first untranslatable round and emits
  only the continuous valid prefix, avoiding virtual-count drift.
  ⑦ Count-drift prevention: documents no longer hand-maintain fixture
  counts (pytest collection is the source of truth); grid fixtures
  split into `tests/test_reference_grid.py` (source notes migrated,
  the heart test's cross-file dependency localized). A new SVG-channel
  regression gate bans st.html calls in app/. 844 passed + 1 skipped,
  ruff/mypy clean.

- **`st.html` sanitizer strips SVG and scripts (found by in-browser
  inspection, two fixes)**: Streamlit 1.60 sanitizes `st.html` with
  DOMPurify — the **entire `<svg>` element is removed** (the hero ring
  mark vanished and the lead text collapsed into the 88px mark column;
  ring charts, symbol strips and silhouettes on the result page were
  blank), and `<script>` is stripped even with
  `unsafe_allow_javascript=True` (the 3D preview never drew, and the old
  canvas's fixed focal length rendered an 18 cm doll at ~44 px — two
  latent defects that sat undiscovered while the "visual check of
  st.html graphics" item stayed open). Fixes: 1) all static SVG content
  (hero, ring chart, symbol strip, silhouette, grid legend) now renders
  via `st.markdown unsafe_allow_html` (no sanitizer; block-level inline
  SVG without blank lines bypasses markdown re-flow); 2) the 3D preview
  is rewritten as a **server-side static isometric SVG** (painter's
  algorithm + back-face culling + Lambert shading, 276 front polygons)
  with height-normalized scaling (fixes the tiny-figure defect) sharing
  the design tokens — at the cost of drag rotation, since no script
  channel remains; 3) the deprecated components.v1.html iframe is no
  longer depended on. Pixel-level browser inspection passes: theme,
  hero, pattern-sheet rows, check progress, materials (CYC label,
  10 mm eyes) and assembly (openings + flat-seam hint) all render
  correctly.

### Changed

- **Visual redesign: the pattern sheet (图解纸)**. The app's look moves
  from a generic warm-craft theme to a printed pattern sheet: cool paper,
  navy ink, and a single stitch-marker yellow reserved for "where you
  are / what you have done" (active tab, chosen option, checked rounds,
  progress); yarn colours stay the only other colour on the page. A new
  leaf token module `app/theme.py` is the single colour source for
  `.streamlit/config.toml`, the injected CSS, and every SVG/canvas
  renderer (ring chart, symbol strip, silhouette, grid, 3D preview) —
  leaf means no Streamlit import, avoiding a models→ui cycle;
  `tests/test_theme_tokens.py` keeps the four surfaces in sync and guards
  against legacy-palette regressions. The result page is re-laid-out as
  numbered sections 1–5: each part's rounds render as pattern-sheet rows
  (serif rows, a marker-yellow sweep on check), round labels pass
  notes/colour through md_safe before Markdown rendering (same
  injection defence), and yarn chips get ruled-border styling. The hero
  is a one-shot draw animation of the first six rounds of a +6 sphere
  (equal rings — r grows linearly; st.html's sanitizer strips the
  pathLength attribute, so inline dash values are used instead), fully
  degraded under prefers-reduced-motion. No web fonts (offline/privacy
  stance; Google Fonts unreliable in the mainland): system sans for
  body, Charter/Palatino falling through to Songti for headings, lining
  tabular digits. Print styles hide app chrome and output a clean
  black-on-white sheet. Contrast: body ≈14:1, secondary 5.3:1, control
  borders 3:1 (WCAG 1.4.11). The PDF exporter's table header/stripes now
  share the tokens (legacy terracotta removed).

### Added

- **Per-image authorization evidence and rights-response process**: evaluation manifests move
  to schema v2 and require every image to record its copyright basis, creator/rightsholder,
  verification date, permission or license evidence, identifiable-subject status and separate
  consent, evaluation approval, and redistribution scope. Dataset declarations must match the
  per-case evidence. New bilingual third-party-content and notice/takedown policies plus a
  structured Rights issue form make clear that credit, thanks, disclaimers, and “remove on
  notice” promises are not authorization. The documentation also distinguishes current
  stitch/round facts encoded as reference fixtures from model training: this repository has no
  weight-training or fine-tuning pipeline, and web articles remain non-calibrating context only.

- **Batch expansion (+2 full patterns / +4 fixtures)**: ① Stringy
  DingDing's "Scraptacular Bunnies" (no-sew scrap bunnies, verbatim) —
  a neck pinch 24->12->24 ("dec around" = 12 sc2tog, exactly 24//2),
  **eye markers placed during round 3** (colored stitch markers while
  increasing — the earliest eye anchor in the corpus), a mixed-height
  flat oval ear [15] (hdc/dc blended in one piece — the T/F rows of
  our glossary made real), and an MR10 short tail (the bounded
  counterexample to toruyuri's "10 leaves a hole" — closed and
  stuffed); the comment section carries the designer's own **resizing
  rule** (every 2 extra increase rounds -> 3 extra plain rounds). ②
  Spin a Yarn's "Goose" (verbatim) — a **new FLO/BLO front/back
  layering topology**: the split round's single-round algebra is not
  unique, so it is honestly recorded rather than fixtured (same
  boundary class as across-parts pickup), while the total-count series
  around the layering point is still verified. 4 fixtures (68 in
  file, 838 total).

- **Weighted-base materials row and assembly step** (Grace and Yarn /
  The Loopy Lamb verbatim): body-bearing patterns gain an **optional
  weighted-pellets row** (~3/4 cup poly pellets) and an assembly step —
  pour the pellets into a knotted stocking (color close to the doll so
  it doesn't show through), place it at the bottom while the decrease
  opening still admits a hand, then stuff normally; safety framing:
  not for under-3s (pellets can work through stitches), washable as
  normal. Same optional-hardware pattern as the armature-wire row.
  1 test (present with a body, absent without; 835 total).

- **Needle sculpting enters the assembly notes** (PlanetJune's tutorial
  page verbatim — the third PlanetJune page in the corpus): for
  head-bearing patterns the assembly now includes an **optional step**
  after the safety eyes / embroidered features — run a long needle
  with matching yarn in at one eye position, across the whole head,
  out at the other eye and back, then pull both ends tight from the
  same hole, knot and hide them to form the eye-socket indents; with
  the note that this pattern's shaping is already built in, so the
  step is only for more sculpted features (PlanetJune's own framing:
  patterns with built-in shaping don't need it — it's a fix/enhance
  technique). 1 test (step appears with a head, absent without;
  834 total).

- **North-American major-brand anchor (Yarnspirations Red Heart Bear,
  official PDF verbatim)**: designed by Sarah Zimmerman (Repeat
  Crafter Me). ① The big-brand house style of a **10-stitch start with
  joined rounds throughout** (original notes: "All rnds are joined
  with sl st to first sc"; the turning Ch 1 does not count) — a
  professional register coexisting with the community's 6-start
  spirals; ② a one-piece (bottom-up) with the deepest waist pinch in
  the corpus: 30->24->18->**12 (waist)**->doubled back to 24 at the
  neck->36->closed to 6; ③ the **eye gap = max/6 rule confirmed
  exactly**: "approx 6 sts apart" on a 36-st head, the same ratio as
  Zepiany (5 on 30) — two independent sources for the max_st//6
  heuristic; eyes "between Rnds 24-25, centered over the snout"; ④
  official materials: **12mm safety eyes on a 23cm toy** (matching our
  eye ladder) and the official **13 sc/10cm gauge at 5mm** (center of
  CYC #4); ⑤ feet "stick out sideways to give Bear support to sit up"
  — independent corroboration of the sitting-support craft with the
  Russian bear's tail counterweight; ears unstitched/unstuffed, sewn
  ~4 rounds from the top. 2 fixtures (64 in file, 830 total).

- **Heavyweight Russian verification (AmiguRoom bear, Yulia Deinega)**:
  full text verbatim plus 78 comment threads of trial-crochet
  discussion. ① The **complete 6<->3 sector transition** — after
  growing in 6 sectors to 72, the head switches to 3 sectors via
  (23 sc, inc) x 3 (72->75->78, +3/round), with the mirrored 3-sector
  decrease on closing and the body tapering the same way — a
  cross-language corroboration of Mr. Orange's 3-sector hat and the
  corpus's first fixture with the transition in both directions (full
  34-round head); ② the **longest drifting-decrease run** in the
  corpus: leg rounds 13-30 decrease by 1-6 per round with the decrease
  point shifting every round (ankle shaping), and 8 more rounds on the
  arms; ③ a third 5-start tail (works as a sitting counterweight per
  the comments — into the assembly notes); ④ **the assembly notes now
  say to pack the neck firmly to keep the head from tipping forward**
  (both the name-based and assembly-graph paths), test-pinned; ⑤ the
  comment thread where readers misread пр as one stitch (12≠18)
  re-confirms the increase semantics the validator enforces.
  3 fixtures (62 in the file, 828 total).

- **Chart-symbol glyphs + loop-stitch texture family (real-method
  verification)**: ① the quick-reference expander now opens with a
  **crochet chart symbol strip** — the ten base notation glyphs
  (CH ellipse / SL dot / X / V / A / W / T / F / E / B teardrop) drawn
  as inline SVGs, mirroring real pattern charts (routed through the
  markdown channel per the established st.html-sanitizer lesson); ②
  the glossary gains a **texture family of 3 entries** (verified
  against cbfiberworks/Yarnhild verbatim): loop stitch (1→1 with loops
  on the wrong side — turn inside out or use front-side variants,
  never start the magic ring with loops, yarn-hungry), double loop
  stitch (curl-inward craft warning), loop decrease (4 loops on hook
  pulled through, 2→1); ③ one more real-pattern fixture: the loop
  practice circle 6→24 (+6/round, passes clean — loop stitches count
  as single crochets). 2 new tests (9 in the file, 825 total).

- **Glossary completion and in-app surfacing**: ① added the missing W
  "three-in-one" entry (3 sc in one stitch, 1→3 — the notation was in
  our own legend but had no glossary entry; oval end caps and petal
  thickening, per Patchy Bear's snout [10]), and the decrease entry now
  notes its other-height siblings (CYC's hdc2tog/dc2tog/tr2tog, notated
  per pattern); ② a **Tunisian sub-table of 13 entries** (CYC chart
  verbatim: tss/tks/tps/tsc/tdc/thdc/trs/tslst/ttr/tfs/etss/ttw plus
  the FwP/RetP pass structure; Japanese generic name afghan stitching;
  marked as row-based — round algebra does not apply); ③ the result
  page's "crochet parameters" section gains a **"stitch quick
  reference" expander** — the main table plus the Tunisian sub-table
  (symbol/name/US/UK/Japanese/count semantics/notes columns, each with
  its source anchor), browsable on screen rather than only in exports.
  3 new tests (7 in the file, 824 total).

- **System-wide stitch glossary** (`app/models/stitches.py`, 18 entries
  × 5 systems): previously scattered stitch knowledge consolidated
  into a single source — Chinese letter notation (X/T/F/E/V/A/W/M/B),
  official US abbreviations (checked against CYC's full chart verbatim,
  including pc/ps/bo/CL, FLO/BLO, FP/BP families), UK traditional terms
  (one-level offset: US sc=UK dc, US dc=UK tr, per Shelley Husband/
  KnitPro charts), Japanese names (saibi/cho/mashime), and each
  stitch's **count semantics** (consumed→produced ratio: the inc/dec
  family 1→2/2→1/3→1/4→1; the cluster family — bobble/puff/popcorn —
  count-neutral; edge decoration — picot/crab — not counted). The
  export legend gains two lines (height ladder + cluster/edge
  families); entry integrity, the US↔UK pairing invariant, cluster
  neutrality, and the export wiring all have tests (4 new, 821 total).

- **Spanish-language verification (5th notation system) + safety-eye
  age warning**: Zepiany's ES-Bee and Melonchillo's magic-circle law,
  captured verbatim (vuelta/pb/aum/dis/AM). ① a symmetric 30-peak
  sphere (6→30, 8 plain rounds, mirror back to 6 — zero notes); ② the
  **3rd real published contradiction** — round 1 notation "sc x 6 (6)"
  vs prose "Vamos a tejer 8 puntos bajos": an 8-start breaks round 2
  algebra (8+6≠12), so (6) is the self-consistent reading — the kind
  of transcription error the validator catches (fixture records the
  ruling); round 17's sloppy "(6dec) x 6 (6)" resolved to dec 6 by
  algebra; ③ a third eye-placement anchor (between rounds 3-4, 5
  stitches apart); ④ the start-count-per-stitch-height law (sc 6 /
  hdc 8 / dc 12 / double-treble 18) and the +12/round dc circle
  (corroborating the granny rhythm); ⑤ **the safety-eye materials row
  now carries "for children under 3 or pet toys, prefer embroidered
  eyes"** (from Zepiany's safety warning). 2 fixtures (55 in file,
  817 total).

- **Japanese-language verification (4th notation system) + increase
  offset reminder**: toruyuri's "circle increase law" captured in full
  verbatim — the Japanese formulation of staggered increases (odd
  rounds place the pair at the unit's end, even rounds mid-unit;
  staggered placement yields a circle, same-position yields a hexagon,
  with photo proof); a ring-start experiment (3 is the minimum, 10
  leaves a hole, 5–6 most common), corroborating the existing MR5/MR7/
  MR8 fixtures. Changes: ① the export preamble gains an
  "increase placement" note (in spiral hooking the start drifts by one
  stitch per round so corners do not form; in joined rounds you must
  stagger manually or you get a hexagon); ② one Japanese-notation
  fixture (dan/me/saibi/mashime) — 53 in the file, 815 total. Hamanaka's
  official PDF proved unstable to download twice — recorded in the
  reachability backlog.

- **External calibration evidence-chain doc + optional wire-armature
  materials row**: ① new [`docs/SOURCES.md`](docs/SOURCES.md)
  (bilingual): the evidence chain for all 27 verbatim sources — what
  each verified, the driving evidence for the four prior corrections
  and the decrease rule then thought to hold (a historical conclusion
  superseded by the fifth-prior correction at the top of this section),
  fixture mapping, transcription
  errata history, and the reachability backlog — also enforced by the
  repo-hygiene bilingual-pair test; ② when the structure has limbs
  (arms/legs/tail) the materials list gains an **optional armature-wire
  row** (root count follows limb count): spec anchored to Crafty
  Intentions' designer spec (paper-wrapped 18-gauge 18-inch floral
  wire; cloth-wrapped same gauge is too soft) and the r/CrochetHelp
  16–20-gauge consensus; safety requirements from Maclafersa's guide
  (bend ends into closed loops and wrap them, tape alone unreliable,
  use pipe cleaners/dowels for children's toys).

- **Positive verification of the decrease hard rule (historical;
  superseded by the counterexample at the top of this section)**
  (Chibiscraft's
  Cute Minion via AlwaysFreeAmigurumi, full text verbatim): leg round
  3 "BLO 2sc, 2dec, sc4tog, 2dec, 2sc, dec (10)" is the densest real
  decrease round in our corpus — one sc4tog plus five sc2tog across
  18 source stitches, a decrease equivalent of 8, exactly within the
  prev//2 = 9 limit: **the "dec <= prev//2" hard rule survives the
  densest real round and stays hard** (an instructive asymmetry with
  inc-exceeding-source, which granny space increases did break). Also
  pinned: the sole-turning BLO/FLO alternation (R3 BLO dec / R5 FLO
  inc / R6 BLO dec, with the source note "use a normal, not invisible,
  decrease when working BLO"); the body taper 54->45->36->27->18->9
  decreasing by 9 per round with R39 exactly at the 18//2 boundary;
  and a third verbatim oval start (ch 6 -> [12]). 2 fixtures (52 in
  the file, 812 total).

- **Granny flat-motif topology and the 4th validator prior correction**
  (Lion Brand's classic granny square + Marching North's solid granny
  square, full text verbatim): ① the classic grows 12->24->36->48
  (+12 per round: four (3dc, ch2, 3dc) corners, one new side group
  per side per round) with a self-reported 76-st border round; ② the
  solid version grows 12->28->44->60 (+16 per round) — round 2 adds
  16 stitches onto only 12 source stitches, tripping the hard
  "inc <= prev" rule. Mechanical verification shows the increases go
  into chain corner spaces, not stitches: **inc-exceeding-source is
  downgraded from a hard error to a note** (same family as W
  "3 sc in one st" and shell stitches — fully hookable; the exporter
  skips such rounds). The decrease rule stays hard. 2 new granny
  fixtures (50 in the file, 810 total).

- **Joined-round (non-spiral) part verification** (Tiny Curl's
  "Monsieur Bear" + Squirrel Picnic's "Motley the Bear", full text
  verbatim): ① the beret is explicitly labeled "joined rnds, not
  continuous spiral", with the turning-chain-counts convention
  "Ch 3 (count as st)" — round totals include the turning chain
  (11->22->33->44->44->33, symmetric +/-11 verified round by round;
  non-6-multiples correctly downgraded to notes); ② a joined, turned
  ear (MR 7, ch 1 counts + turn, half double crochet) enters the
  fixtures for the first time; ③ the muzzle switches to "Join with
  slst, ch 1" from round 2 (turning chain does **not** count —
  contrast between the two sources) while mixed with spiral rounds in
  the same piece — confirming that joined rounds keep the same stitch
  rhythm as spirals; ④ skip-based closing `(1 sc, skip 1) x 6`
  (12->6, same counts as sc2tog, different technique); ⑤ the head's
  R29 FLO neck round corroborates the bee's BLO neck round
  (count-neutral neck divider). The export preamble now notes that
  the starting chain usually does not count as a stitch unless the
  pattern says so. 3 tests (48 in the file, 808 total).

- **Chain-joined-legs body and oval-start verification** (Craftably Ever
  After's "Patchy Bear" sit-down bear, full text captured verbatim):
  ① the standard sitting-amigurumi body start — chain-bridge leg join
  R15=36 (the source self-reports 13 sc (leg 2) + 2 ch + 16 sc (leg 1) +
  2 sc in ch + 3 sc; mechanically verified, distinct from the direct
  24+24->48 leg merge and from sewing); ② the snout oval start with its
  verbatim count (ch 4, 2nd ch from hook, 3 sc end caps -> [10]; the
  validator correctly downgrades it to a note); ③ one more eye-placement
  anchor — 2 rows above the cap edge, 2 stitches apart (an anatomical
  anchor, not a round-ratio rule); craft corroboration: arms stuffed
  only halfway, ears flattened unstuffed, seamless closing (front
  loops). 2 tests (45 total).

- **Reference-pattern verification tests** (`tests/test_reference_patterns.py`,
  24 items): external calibration against professional/community patterns —
  Clover's official AKIHIRO doll (22-st legs / 16-st arms / 9-st tail /
  14-st ears), the community sphere formula (6-sc ring start, +6 per round),
  the Lovable Loops cherry mini C2C chart (9x9, full written block rows),
  Spin a Yarn Crochet's 8-stitch ring start (8->16->24 doubling), a
  sin-profile property verification of Ms Premise-Conclusion's "The Ideal
  Crochet Sphere" (per-row comparison against independently recomputed
  N=C/s values) including its craft-warning handling, Craft Yarn Council
  abbreviation alignment (sc2tog), DROPS Design Children 23-60 apple toy
  (Garnstudio professional pattern: 7-st ring start, +7 increase rounds,
  9 plain rounds, symmetric decreases to 6, 4-st chain-start stem; its
  R17 errata history — a decrease once misprinted as an increase in 2012 —
  forms the first "published errata" fixture), StringyDingDing's kangaroo +
  joey (a plain round right after the ring, one-piece asymmetric shaping
  with odd 21/15-stitch rounds, a 4-increase ear round; the mamma leg R5
  increase-instruction-vs-(24)-count contradiction is the second), and
  Supergurumi's "The Chubby Bee" (a German professional design studio:
  55-round one-piece body peaking at 66 stitches, per-round yellow/black
  stripe color changes, BLO ridge rounds, "1 single crochet" spiral shift
  rounds, staggered shaping repeats, and an odd-count 3-decrease tail
  sequence 33->...->9->6; all 55 rounds mechanically verified, fully
  passing the validator and translating to CrochetPARADE including COLOR
  stripe directives).
- **Difficulty labels aligned with CYC Project Levels** (`app/schemas.py`):
  the official four levels Basic/Easy/Intermediate/Complex (fetched and
  quoted verbatim 2026-09) map onto our easy/medium/hard — the generator
  only produces single-crochet toys, so CYC's Complex (multiple techniques
  simultaneously) has no counterpart by design. The result-page metric,
  the manual-tab slider, and the Markdown/PDF exports all switch from raw
  English enum values to CYC-aligned labels (unknown legacy values fall
  back to verbatim display).
- **CYC yarn-weight category mapping** (`Gauge.cyc_label`): maps stitch
  density onto the Craft Yarn Council Standard Yarn Weight System (official
  "single crochet per 4 inch" categories, fetched and cross-checked 2026-09)
  and reports each category's standard hook range; the materials list shows
  the amigurumi-tight hook advice next to the CYC standard category. The
  scope is explicit: this is a "density -> category" mapping, not a
  "yarn -> category" one (tight-gauge amigurumi can reach the same density
  with a thicker yarn). Cross-validation: DROPS Children 23-60
  (18 sc/10 cm, 4.5 mm hook) lands exactly on CYC #2 fine, with 4.5 mm at
  the top of that category's official 3.5-4.5 mm hook range.
- **C2C starting convention**: the grid export's written C2C rows now state
  the standard block construction (ch 6, dc beginning in the 4th ch from
  hook, 3 dcs total, turn) — identical across two independent tutorial
  sources (Craftematics and Crochet.com).
- **"Stitch notation" column in the rounds table** (Markdown export):
  aggregate counts (+6/-6) are now also rendered in the legend's X/V/A
  repeat notation (e.g. (4X,V)x6), matching how professional patterns
  write "[4 sc, 1 inc] repeat" (Supergurumi, DROPS). Non-uniform rounds,
  single-increment rounds, inconsistent aggregates, or JSON-corrupted
  rows degrade to a dash.
- **CrochetPARADE color-stream cleanup**: consecutive same-color rounds
  no longer repeat the COLOR directive (striped pieces drop from one
  directive per round to one per stripe boundary, bee 23->6), and each
  quantity copy resets to the part color instead of inheriting the
  previous copy's ending color.
- **Finest-gauge yarn meterage recalibrated to cotton** (fine bucket
  320->250 m/100g): anchored on Schachenmayr Catania used by the bee
  pattern (100% cotton, 125 m/50 g, labeled Sport/Fine(2), 2.5 mm hook) —
  exactly the bucket's "2.0-2.5 mm + fine cotton" configuration; the old
  320 was a wool-sport figure ~28% high. The other three buckets await
  physical-trial (G4) calibration; purchase per actual yarn label.
- **Safety-eye size now scales with head diameter** (`_safety_eye_mm`,
  materials list): the old fixed "8 mm" ignored doll size — an 8 mm pair
  is clearly off on a 16 cm head. The new ladder aligns with the
  r/Amigurumi eyes wiki community ranges (mini 5-6 mm / regular 8-12 mm /
  large 14-20 mm+, fetched 2026-09); professional anchors: ~10 cm heads
  with 12 mm eyes (Supergurumi bee 32 cm and StringyDingDing kangaroo
  23 cm both use 12 mm). The default 9 cm head moves 8 -> 10 mm; legacy
  results without a head diameter fall back to 8 mm.
- **Ring-start alternative in the export preamble**: two common
  substitutes for crocheters struggling with the magic ring — chain 4,
  sl st into a ring (Supergurumi's written form) and chain 2, work the
  first round into the 2nd ch (community standard, Hobbii's "Easy
  Alternative to the Magic Ring").
- **Cross-language verification from the Russian tradition**
  (kruchcom.ru teddy finger puppet, verbatim): КА (amigurumi ring)
  6-stitch start, 6 ПРИБ (increases), plain 24-st rounds — the same
  community standard in another language; the same site's big teddy head
  uses ВПП (lifting chain) joined rounds, whose aggregate counts are
  identical to spiral work, so the validator needs no distinction.
- **Opening stitch counts flow into the assembly text** (`build_assembly`
  gains an `openings` parameter): professional assembly sections state
  the opening size before sewing ("sew the remaining 12 sts"). Limb
  steps now read "sew ... (opening: N sts)" with N = the part's last
  round; hat brims and skirt waists report their exact stitch counts;
  the fully cinched sphere head honestly reports none. Recomputed by
  refresh_derived after JSON edits; callers without the parameter keep
  the previous wording.
- **Closing technique upgraded to the seamless close**: the final-round
  note on spheres/eggs/one-piece bodies changes from the plain "cinch
  tight" to the community-standard technique — "thread the tail through
  the front loops of every remaining stitch and pull tight" (Chinese
  community term 无痕收口, seen on Bianzhirensheng; English counterpart
  is PlanetJune's Fastening Off front-loops method). Reachability of CN
  sources is documented too: Xiaohongshu requires login and hosts
  image-based charts; Bianzhirensheng's full text sits behind its share
  platform (persistent 502/500) with image charts on the main site —
  text-level calibration sources essentially don't exist in fetchable
  form in the CN community, which is exactly the gap a photo->pattern
  system fills there.

### Fixed

- **Head notes now use the same safety-eye sizing as the materials
  list**: the head note hardcoded "install safety eyes (8 mm...)",
  conflicting with the diameter-based materials ladder (10 mm for a
  9 cm head, 14 mm for 15 cm) — both now go through `_safety_eye_mm`,
  pinned by a regression test.
- **Image-chart vision transcription unlocked (first Chinese-community
  fixture)**: the Ziyou Shouzuo "Bone Dumpling" image chart reposted on
  Bianzhirensheng's CDN was transcribed visually into aggregate counts —
  its notation (X/V/A/CH/SL) matches our export legend exactly, and its
  4-ply yarn + 1.8/2.0 mm hook corroborates the fine preset's "4-ply
  cotton" label. Five new tests pin: the symmetric 6->42->6 body worked
  in joined rounds (zero notes), the bone's 18->36 doubling round
  (written as "36X"), the 10/8-stitch bang ring starts, the headcover's
  30-stitch opening feeding the openings map, and a new preamble note
  bridging joined rounds (CN mainstream) and spiral work.
- **Opening-filter fix**: last-round notes saying "do not close"
  (不收口/勿收口 — an explicit opening statement, e.g. the headcover's
  "keep the opening... do not close") are no longer misclassified as
  closed by the substring "收口" — a negative-lookbehind regex
  `(?<![不勿])收口` handles it.
- **Third validator-prior correction: mixed increase/decrease rounds
  downgrade to notes**: the lop-rabbit eye-socket round
  `7X,7V,A,7V,7X` (30->43) mixes increases and decreases within one
  round in a real chart, algebraically sound — the old validator
  hard-rejected it. Executability stays guaranteed by inc<=prev /
  dec<=prev/2 (hard checks); mixed rounds exceed this generator's
  uniform-group expression, so the CrochetPARADE export honestly skips
  them.
- **Channel sweep harvest (vision transcription at scale)**: the lop
  rabbit (face shaping / sc3tog / a flat oval ear on a foundation
  chain / a 6-stitch tube arm / a 3-mm tiny-eyes data point), Mr. Orange
  (a **three-sector hat topology** at +3/round, a 7-start headcover with
  a doubling round and slip-stitch edging, feet decreasing to odd 7, and
  a same-round join of feet+arms = one-piece), and AllAboutAmi's
  Elephant (a cone trunk at -3/round; oval foundation-start bodies and
  pick-up legs are documented as beyond the aggregate model). The export
  legend gains the CN-standard W (3 sc in one st) and M (sc3tog)
  symbols.
- **C2C written rows upgraded to the professional format** (aligned
  with Juniper & Oakes and peers): every diagonal row now carries a
  direction arrow (odd rows ↙ on the right side / even rows ↗ on the
  wrong side) and a right-side/wrong-side label alternating with the
  turns; the header states the convention's provenance. The direction
  was cross-checked line-by-line against two independent sources
  (Juniper & Oakes, Lovable Loops) — the first implementation had it
  inverted and the heart chart's asymmetric rows caught it.
- **Second published grid-chart fixture (Lovable Loops heart 9x9)**:
  its 17 written color rows were transcribed into a grid, rendered
  through this system's C2C writer, and reproduced row for row
  (including asymmetric rows 7/8/9) — complementing the cherry fixture's
  cluster-count check by pinning the in-row color reading direction.
- **Flat-seam hint for tiny openings in assembly text**: limb steps with
  an opening of 6 stitches or fewer now add "small openings can be
  flattened and sewn" (community practice, e.g. the lop-rabbit arms).
- **Eye-placement note anchored in words**: head notes now say "near the
  widest round" — professional charts place eyes relative to landmarks
  (Supergurumi bee: "2 stitch rows after the nose" — the BLO ridge —
  with spacing down to 1 stitch), and this generator has no landmarks,
  so the geometric approximation is stated and the maker is told to
  adjust for eye size and face.
- **Bulk channel enumeration**: Bianzhirensheng's sitemap shards
  (25k URLs) are enumerable and chart posts are locatable by ID range;
  the Gummy-series mini-charm chart (vision transcription) adds the
  bobble B (5-dc cluster, in-and-out of one stitch — stitch-count
  neutral) to the export legend, plus fixtures for a full 24->12
  decrease round and an in-round color change on BLO (beyond this
  model's per-round color granularity, documented as such).
- **Two-leg join and shoulder-shaping fixtures (first Xiaohongshu-native
  chart)**: Qing Yi Shouzuo's "Little Rabbit Sister" (watermark confirms
  Xiaohongshu origin, reposted on Bianzhirensheng) — the overalls start
  from two separately ringed 24-stitch legs joined in the round into a
  48-stitch body (matching this system's body-R1 join semantics); the
  big carrot narrows then re-widens (12->9->12, an in-part direction
  reversal); the small carrot starts with 5 stitches and closes 9->5
  with "4 dec, 1 sc". International: 53stitches' "Low sew Bunny" — MR 8
  start with popcorn-stitch limbs (neutral, same family as the bobble).
  The validator again caught two transcription misreads on the spot
  (a v/a mix-up on the carrot; an elided-row discontinuity on the
  bunny) — the transcribe-verify loop keeps paying off.

- **Validator domain confusion (found by the calibration, two instances)**:
  real patterns contain 22/16/9/14-stitch rounds that are perfectly
  crochetable, and professional designers' 8->16 doubling rounds (one
  increase per stitch, always executable) were rejected by the +-6 smooth-
  shaping cap. Both downgrade to `notes` — executability is guaranteed by
  inc<=prev / dec<=prev/2 (kept as hard checks); six-section topology and
  smooth-shaping cadence are generator priors, not crochetability
  requirements. The result page shows notes as info captions.
- **Grid pipeline externally verified**: the cherry chart (white 57 / red 18 /
  green 6) maps through nearest sampling with each cluster landing on a
  single yarn color, cluster sizes exactly matching the published chart.

## 0.2.0-beta.2 - 2026-09-05

### Added

- Versioned real-photo evaluation protocol covering rights, retention, SHA-256, scene
  tags, aggregate gates, and JSON reports.
- `crochet2pattern-eval`, which evaluates only the local-vision path.
- `crochet2pattern-trials`, with pattern hashes, measured gauge/size/yarn/time, conservative
  calibration candidates, and separate calibration/holdout cohorts.
- Curated external trial evidence packaged with the wheel and prohibited from automatic calibration.
- MIT license, contribution/security/conduct policies, structured issue forms, and a PR template.
- Full English entry points for user, contributor, security, evidence, and status documentation.

### Changed

- English is now the default GitHub and package landing page; complete Chinese docs remain
  at `README_ZH.md` and `docs/system-status.zh-CN.md`, with compatibility redirects for old links.
- README now separates structural correctness, photo generalization, and physical crochetability.
- Secret checks cover staged untracked files and common GitHub, AWS, and private-key patterns.
- Core tests no longer rely on the optional PDF extra; Streamlit tests use stable absolute paths.
- Weekly and lock-change dependency auditing now tests the environment installed from `uv.lock`.
- CI forces each declared interpreter through `UV_PYTHON`, preventing a false matrix that
  silently reused the local default.
- GitHub Actions use `checkout@v7` and `setup-python@v7`.
- Pose is limited to Python 3.11–3.12 and upgraded to MediaPipe 1.0.1, removing the old
  vulnerable `protobuf<5` constraint. Every core environment uses Protobuf 6+; Python
  3.13+ also uses NumPy 2.x.
- Dependency security installs and audits core, PDF, and pose extras together.
- Linux pose checks for EGL/GLESv2 before constructing MediaPipe objects and safely
  falls back when missing; extras CI installs the runtime and exercises the real image bridge.

### Fixed

- On shared deployments a user's API key can no longer be silently captured by the
  server's `OPENAI_BASE_URL` / `ANTHROPIC_BASE_URL`: a user key without a custom base
  URL is now explicitly paired with the official default endpoint (the SDK no longer
  falls back to reading those environment variables).
- Upload resource limits now bite: `.streamlit/config.toml` sets
  `server.maxUploadSize = 20`, decoded images are immediately downsampled to 2048px
  before white-compositing and caching, and JPEGs use proportional `draft()` decoding.
  The measured +650MB decode/composite peak for a legal 39.7MP PNG is gone, and the
  result page no longer transfers full-resolution frames on every rerun.
- Honest Mock labeling: UI, CLI, and `vision_meta` now say "body and parts are fixed
  demo values, colors and spans come from the photo" (the old "unrelated to the photo"
  wording contradicted actual behavior).
- Vision mode is an explicit three-state `vision_mode` (ai / local / mock): the library
  no longer infers it from "is a key present", Mock never calls any API regardless of
  keys, and `.env.example` placeholder keys (`sk-your-key-here`) no longer count as
  configured.
- Model-controlled free text (main features, identified parts, assembly instructions,
  materials fallback lines) renders as plain text or escaped output, so in-image text
  injection can no longer reach the page through Markdown link/image syntax.
- SQLite history connections are closed via `contextlib.closing` (removes the
  Python 3.13+ ResourceWarning) and schema creation/migration runs once per file.

### Changed

- New `PatternResult` pydantic model as the single contract for the result dict:
  all six hand-written literals (orchestrator, both CLI branches, manual input, quick
  resize, backup import) now converge on it; backups and share tokens carry a
  `schema_version`, and share decoding rejects future versions.
- Vision structured outputs now use a dedicated `VisionOutput` contract (separate
  from the internal `ImageAnalysis`): enum fields are `Literal`-constrained, the
  model no longer receives `recommended_colors` (which it must never fill), and the
  schema directly requests `head_to_height_ratio` instead of the indirect "fixed
  18.0 canvas" conversion. Legacy centimetre-shaped prompts are tolerated only in
  the schema-less fallback path.
- New `PartKind` `StrEnum` plus Chinese/English label tables: the English domain key
  (= structure-v2 part_id) and the canonical Chinese names now derive from a single
  source, preparing the i18n migration; `PART_NAMES` values are unchanged.
- CI gains a `type-check` job: `mypy` joins the dev extra with a zero-error baseline
  across all 37 app files (see `[tool.mypy]`) to prevent type regressions.
- The three local result-page flows (quick resize / structure edit / backup import)
  move out of button callbacks into a pure-function layer (`app/ui/result_logic.py`)
  that is unit-testable offline; the per-round progress section is now an
  `st.fragment`, so ticking a round no longer reruns the whole page.
- Product display name unified to `CrochetPhoto2Pattern`: a single
  `app.PRODUCT_NAME` source now feeds the page title, hero, footer, and
  Markdown/PDF exports (the UI previously said Photo2Amigurumi while the
  repo and package say CrochetPhoto2Pattern).

### Security

- Second review pass closes the remaining cross-user injection surfaces: share
  tokens / backup imports carry other people's content, and three spots in
  `params` still rendered Markdown (part `notes` via `st.info`, the
  shape/color line via `st.write`, validator issues via `st.warning`). They now
  go through `md_safe` (strip zero-width/BiDi, backslash-escape `[]` to kill
  link/image syntax, HTML-escape), as do spans_measured, sizing/vision_meta
  notes and all exception interpolations.
- Backup import gains a 2MB paste-size gate (aligned with the share token's
  2MB decompression cap).

### Added

- **CrochetPARADE DSL exporter** (P1 from the external对标 review): translate
  round-by-round patterns into the crochetparade.org text grammar (`ring`,
  `scNinc`, `N[sc,sc2inc]`, `start_anew`, `COLOR:` — a verified subset checked
  against the official manual and examples). Available via CLI `--parade` and
  the result page, with emitter-level syntax lint. Users paste it into their
  locally-run web app for independent 3D rendering, stitch-tension analysis and
  Blender-importable models — a verification layer beyond our algebra gate.
  License boundary: text output only, no GPLv3 code pulled in.
- Evaluation protocol gains a second-tier executable-correctness metric
  `parade_export_rate` (CrochetBench methodology), reported alongside
  `pattern_valid_rate`.
- Structure v2 -> 3D preview (`app/ui/preview3d.py`): a self-contained canvas
  software renderer (triangle faces, painter's algorithm, Lambert shading, no
  external CDN); instance positions/rotations and part sizes/colors render
  directly, drag to rotate, wheel to zoom; cylinder radii derive from stitch
  counts and gauge, profile parts lathe per round (same math as the ring chart).
- `docs/schemas/` publishes JSON Schemas for the core contracts (PatternResult,
  StructureGeometry, ImageAnalysis, CrochetPart) with a drift test — following
  the open-intermediate-format playbook of Knitout.
- Grid tab gains an optional Floyd–Steinberg dithering toggle (keeps gradients
  under small palettes; default off), matching common photo-to-grid tools.

### Fixed

- `st.components.v1.html` passed Streamlit's deprecation deadline (2026-06-01);
  the four SVG renders (ring chart, symbol strip, silhouette verification, grid
  canvas) migrate to `st.html`, with fixed height and scrolling provided by an
  `html_box` wrapper inside the content (st.html has no height/scrolling).
- Dependabot ecosystem switched from `pip` to `uv` (officially supported since
  2025-12); the pip ecosystem has a known "updates pyproject without
  regenerating uv.lock" failure mode for uv projects.
- History SQLite first-connect DDL is now lock-guarded across Streamlit session
  threads, and `commit` no longer sits inside a `suppress` block (a fully
  migrated database — where every ALTER fails — still commits and marks the
  file initialized; regression test included).
- History blobs carry `schema_version` and the loader rejects future versions
  (legacy blobs without a version keep loading).
- Share tokens are generated on demand (button click, cached in session
  state) instead of re-compressing the whole result on every rerun.

### Changed

- `py.typed` ships in the wheel (library consumers get type hints); the CI
  wheel check asserts it.
- mypy enables `check_untyped_defs` (zero errors across app); tests/ use a
  documented override checking only module top level and call signatures —
  tests deliberately poke internals with dicts and fake SDKs.
- CI gains a `docker` job (build only, no push, GHA-cached) to keep the
  Dockerfile and dependency graph honest.
- `params["parts"]` is uniformly dict-shaped in memory (matching disk/share/history):
  the dict/model dual-state branches in `_part_name`, `_part_rounds`,
  `_part_quantity`, `_round_stitches`, the validator, exporters, PDF export, and the
  ring chart are all removed; CrochetPart/CrochetStitch remain validation-only.
- Vision SDK timeout budget tightened from 60s×3 retries to 40s×1 (worst case across
  both providers ≈2.7 minutes instead of ~8); `openai` gains an upper bound `<4` and
  `anthropic` `<1` (1.x is a breaking httpx2-based upgrade).
- Dockerfile rebuilt as a multi-stage build: dependencies installed exactly from
  `uv.lock` (no more live resolution via `pip install .`), cached dependency layers,
  non-root user, and a built-in `/_stcore/health` HEALTHCHECK.
- All three CI workflows migrate to `astral-sh/setup-uv@v7` with caching enabled
  (`setup-python`'s pip cache never helped uv-managed environments); Dependabot added
  for pip and GitHub Actions; ruff now enforces the UP/SIM rule sets with all existing
  findings cleaned up.
- Historical review snapshots (audit-brief*, handoff-review, optimization-brief,
  audits) moved to `docs/archive/`; round-numbered test files renamed by coverage
  (test_round12/14/15 → test_validator_c2c_materials / test_exports_share_cli /
  test_export_disclaimers_history).
- Test history databases use per-case `tmp_path`, so parallel/multi-user runs no
  longer share a fixed `/tmp` path.

### Planned

- Collect an authorized real-photo baseline and an independent physical-trial baseline.
- Split the largest parameter-generation, result-rendering, grid, and provider-adapter modules.
- Publish the first Beta tag only after the G3 and G4 evidence gates pass.

## 0.2.0-beta.1 - 2026-08-30

### Added

- Provider-independent single-image observations, user target-size transforms, and
  StructureGeometry v2.
- Part instances, mirrored quantities, attachment anchors, assembly plans, and multiplicity-aware totals.
- Gauge-driven shaping limits, round arithmetic, six-section topology, and V/A executability checks.
- Profile shaping, ideal sphere/egg heads, one-piece head/body, and advanced structure correction.
- Pre-generation crop, grid editing, undo/redo, editable project JSON, and complete Markdown export.
- CLI, SQLite history, share links, PDF export, ring charts, and versioned backup validation.

### Changed

- Minimum Python is 3.11; CI covers Python 3.11–3.14.
- Yarn matching uses a real palette and CIEDE2000; imported grids must use trusted color names/RGB.
- Beta, single-image, estimate, and physical-test boundaries are explicit.

### Security

- Uploaded images, share payloads, backups, structure JSON, and grid projects have size and schema gates.
- API key/relay sources are isolated, exceptions are redacted, and tracked files are scanned for secrets.
