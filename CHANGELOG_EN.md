# Changelog

[简体中文](CHANGELOG.md) | **English**

This project follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
[Semantic Versioning](https://semver.org/). Backup, structure, and editable-project
formats may still evolve during Beta; incompatible changes must include migration notes.

## Unreleased

### Fixed

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
  Evidence: [review record (Chinese)](docs/optimization-review-20260907.md).

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
