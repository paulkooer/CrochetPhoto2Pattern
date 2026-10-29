# External Rule References (Pattern Source Index)

[简体中文](SOURCES.md) | **English**

## 2026-10-29 Invisible-decrease identity and round-label consistency

Rechecked the action definition in [PlanetJune's invisible-decrease tutorial](https://www.planetjune.com/blog/amigurumi-help/how-to-crochet-an-invisible-decrease/).
The tutorial describes invdec as a distinct technique. This system's glossary already separated
it from ordinary sc2tog, but the operation tree collapsed `inv-sc2tog` into A because both have
2→1 arithmetic. That lost technique identity in canonical notation and DSL output.

Keep the explicit token and compact repeats. Markdown retains it and PDF keeps original notes.
The current DSL subset stops at the affected round and reports partial export; symbol strips
and connection inspection request manual review. Do not substitute an ordinary or FLO decrease.
Standalone `invdec` and Chinese/English prose cues also request review without becoming a
guessed executable formula. Automatic skirt reservation rejects these techniques.

Synthetic examples: `2X,inv-sc2tog` on 4→3 previously became `2X,A` / `2sc,sc2tog`; it now
retains the token and stops unsupported DSL translation. Recorded rows 7, 19 and 23 previously
appeared as 1, 2 and 3 in the old charts; actual labels now survive, with positional fallback
for legacy missing labels. `tests/test_technique_fidelity.py` covers technique/count identity,
round trips, partial-copy accounting, print preservation, atomic skirt-edit rejection and chart
labels. Export cache version is 7; no physical-trial or external-simulation evidence was added.

## 2026-10-29 GitHub comparison and stitch-parent inspection

Reviewed maintainer-owned repositories and domain documents against the current local-vision,
explicit-formula and saved-project architecture:

| Primary source | Relevant idea | Decision for this system |
|---|---|---|
| [CrochetPARADE capabilities](https://github.com/stassev/CrochetPARADE/blob/main/capabilities.md) | Inspect stitch connectivity and export diagrams | Add an adjacent-round association view; retain the existing DSL export without importing its simulation code |
| [stitch-grapher README](https://github.com/bilgesucakir/stitch-grapher) | Separate working-order edges (`NEXT`) from parent associations (`PARENT`); increases/decreases branch or merge | Draw only parent associations, retaining this system's existing scoped FLO/BLO syntax |
| [KnittingPatternMaker conventions](https://github.com/John-Donnelly/KnittingPatternMaker/blob/main/docs/KNITTING_NOTES.md) | Make reading order and technique assumptions explicit | Number from the formula's starting point; do not transplant flat-knitting right/wrong-side rules into spiral crochet |
| [Tesserow documentation](https://github.com/deiussum/tesserow) | Keep editable charts and written instructions aligned under technique-specific constraints | Record as a future grid-workflow reference; do not apply mosaic constraints to C2C or amigurumi |

The independently implemented window maps X/V/A/W/M to source and produced stitch indices,
preserving order and scoped loops. Missing, ambiguous, inconsistent or unsupported formulas
produce a reason rather than inferred placement. First rounds, cross-component joins and the
detailed technique of invisible decreases are outside this view.

Repeated subtrees are skipped by counts and each UI page creates at most 24 operations. In a
synthetic `(X,V,X)×25000` case, 75,000 operations produce 100,000 stitches; the final page has
24 operations, with 2,529 UTF-8 JSON bytes and 16,917 SVG bytes. This demonstrates bounded
output, not a speed comparison with an earlier viewer or improved photo/physical accuracy.

`tests/test_stitch_connections.py` checks independent parent/child expectations, property-based
windows, nested-repeat offsets, large rounds, loop scope, unsupported techniques, SVG escaping
and session isolation. No upstream code, images, complete patterns or dependencies were added.
No upstream parser, 3D simulation or physical trial was run.

## Local reference: manual chain-bridge leg-join planning

Reviewed the user-supplied `Downloads/gz/gz2/IMG_5068.JPG` for joining two legs with a
chain bridge. The planning aid counts two complete openings and one single crochet on
each side of each chain; round and marker references are supplied by the maker. Examples
and test values are original, with no source instructions or images copied. The source
states personal-use and copyright restrictions. The tool does not verify that openings or
stitch locations exist, automatically join parts, or establish physical crochetability.

## 2026-10-25 Printed legends and placement guidance

- [Craft Yarn Council abbreviations](https://www.craftyarncouncil.com/standards/crochet-abbreviations) define sc2tog, FLO and BLO. X/V/A/W/M/B are this project's legend conventions rather than universal letter standards.
- [PlanetJune's invisible-decrease tutorial](https://www.planetjune.com/blog/amigurumi-help/how-to-crochet-an-invisible-decrease/) distinguishes ordinary sc2tog from the front-loop invisible decrease. Correct the old Markdown/PDF equivalence; explicit per-round loop instructions take precedence.

Reuse guidance in the UI, Markdown and PDF. Follow generated explicit placement without
adding the old preamble's automatic one-stitch shift. Switching to joined rounds requires
checking turning-chain counts, color boundaries and shaping positions. These are consistency
fixes, not physical shape evidence. Synthetic tests in `tests/test_printed_stitch_guidance.py`
compare wording, loop instructions and PDF cache upgrades; `tests/test_backup_open.py`
covers fresh-session recovery and preservation of existing work after invalid imports.
No source images, complete tutorials, schema changes or runtime dependencies were added.

## 2026-10-24 Online references and loop scope

Reviewed primary sources for technique and syntax facts, without copying patterns or images:

- [Supergurumi robot pattern](https://www.supergurumi.com/amigurumi-robot-crochet-pattern): whole-round front/back-loop instructions occur alongside shaping; totals alone omit technique.
- [PlanetJune loop comparison](https://www.planetjune.com/blog/amigurumi-help/fuzzy-to-brushed-crochet/): BLO and both-loop samples differ in shape, supporting retention of loop qualifiers.
- [Supergurumi bee pattern](https://www.supergurumi.com/amigurumi-crochet-bee-pattern): head/body R6/R19 and leg R7 specify front loops. Correct the fixture and glossary's mistaken BLO labels to FLO. Only these three formulas are added; the body fixture's 55 circumference samples do not reproduce all original placement or offset operations. Its export test explicitly checks 52 inferred rounds.
- [Official CrochetPARADE HTML manual](https://github.com/stassev/CrochetPARADE/blob/main/Manual.html), stitch table and `stitch_nameNinc/Ntog`, plus [capabilities §1.5](https://github.com/stassev/CrochetPARADE/blob/main/capabilities.md): verified `scfl`/`scbl` and shaping suffixes. The older `Manual.md` omits this loop vocabulary; no upstream implementation was incorporated.

The bounded syntax now accepts `BLO((X,V,X)×5)`, `FLO: 12X`, and local qualifiers
such as `2X,4sc-FLO,2X`. A standalone `BLO;12X` directive applies to the whole round.
Markdown retains qualifiers, chart symbols carry F/B labels, and DSL emits qualified
stitches. Same-position scope conflicts fail validation. Unresolved prose remains usable
manually but stops that part's DSL export, as does a first-round loop without a supported
foundation. Generated cut-tail threading is recognized as finishing, not FLO crochet.

Synthetic before/after cases: 15→20 `BLO((X,V,X)×5)` previously became ordinary
uniform sc and now emits `5[scbl,scbl2inc,scbl]`; local `2X,4sc-FLO,2X` previously
became `8sc` and now emits `2sc,4scfl,2sc`; conflicting `FLO;BLO;8X` is rejected.
`tests/test_loop_notation.py` covers independent counts, ordered scopes, bounds, copies,
edits, backup and printable exports. The calculator interaction test also covers local FLO.

Support is limited to existing X/V/A/W/M operations on the preceding round. Layered
work, returning to reserved loops and invisible-decrease/loop combinations require
review. No gauge, size or yarn calibration, official parser execution, external simulation
or physical trial was performed. This does not establish physical shape fidelity.

## 2026-10-24 Stitch order and export consistency

Generation now replaces vague half-group shift hints with explicit center/end
placement on consecutive +6 rounds with even plain-stitch gaps. For example,
`(X,V,X)×6` still consumes 18 stitches and produces 24. The split-group notation
was observed in the local references; this is a project placement rule, not a
reconstruction of that complete pattern or evidence of rounder physical results.
`tests/test_generated_stitch_placement.py` covers sequence order, idempotence,
finishing notes, legacy backups, numeric edits, all gauge presets, three head
modes and separate/one-piece construction.

Rechecked the [official CrochetPARADE manual](https://github.com/stassev/CrochetPARADE/blob/main/Manual.md)
for one-round-per-line output, consecutive source attachments and repeat groups.
The existing short-stitch increase/decrease vocabulary remains in use. No external
implementation was incorporated and no external simulation was run.

Direct before/after probes used synthetic expressions: split-position 18→24 shaping
previously became uniform groups; mixed 6→6 shaping and clustered 18→30 increases
were skipped; a contradictory formula on 6→12 was ignored. The current exporter
preserves the first three operation sequences and stops at the contradictory round.
`tests/test_notation_fidelity.py` compares emitted and drawn positions against an
independent operation sequence and a small DSL expansion oracle. It also covers
nested repeats, W/M, physical copies, valid-prefix export and bounded chart rendering.
Markdown shares the ordered expression. Aggregate-only fallback is counted separately
in the DSL report; prose-only staggering, loop techniques, non-ring starts and finishing
actions still require review. These are software checks, not physical trials.

## 2026-10-24 Local references and round notation

At the user's request, inspected the JOLA reference images in `Downloads/gz`:
`IMG_5035.JPG`, `IMG_5038.JPG`, `gz2/IMG_5053.JPG` and `gz2/IMG_5057.JPG`.
Observations include material tables, separate stitch totals, split-position
repeat groups, and the distinction between ordinary stitches and work through
multiple layers. No original images, PDFs or full pattern transcription were added.

The resulting notation checks and editor calculator use synthetic expressions in
`tests/test_stitch_notation.py`. Complete supported clauses are treated as whole
rounds; unknown stitches or prose are never partially interpreted. Layered work,
chain joins, color placement, eyes and assembly are outside this check's scope.
Four historical fixtures now use explicit `inc` instead of ambiguous `2 sc`;
this corrects fixture abbreviations, not the original published patterns.
Evidence covers counting and software boundaries, not photo accuracy or physical trials.

## 2026-10-15 Foreground correction canvas

The [Streamlit bidirectional-component guide](https://docs.streamlit.io/develop/concepts/custom-components/components-v1/intro)
and [v1.40 message interface](https://github.com/streamlit/streamlit/blob/1.40.0/component-lib/src/streamlit.ts)
were checked for the Python/JavaScript protocol. The canvas is original project code with no remote scripts.
It directly edits the final mask; it does not rerun GrabCut or generate unseen anatomy.
See `tests/test_mask_review.py` and the optional Playwright browser smoke test
`scripts/check_mask_canvas.cjs`. Local Chrome and an actual Streamlit page verified
brush, undo, reset and generation behavior; these checks do not establish real-photo accuracy.

Public patterns supply cases for checking domain assumptions; publication alone
does not prove crochetability. Necessary stitch-algebra and
round-structure facts are extracted, mechanically verified, and encoded as a runnable test
fixture ([`tests/test_reference_patterns.py`](../tests/test_reference_patterns.py),
fixture count is
whatever `uv run pytest tests/test_reference_patterns.py
tests/test_reference_grid.py --collect-only -q` reports — never
hand-maintained). Real patterns overturned five generator priors, and the
validator was corrected each time — the evidence for every correction
is in the table below. This is reference validation, not model-weight training or fine-tuning.
Only stitch algebra and round structure are taken from each source, never source images or
creative pattern prose (per each source's terms).

## 2026-10-14 Symbol and profile-shaping review

**Subsequent implementation on the same date:** cloud interfaces, SDKs, credentials and prompts have now been removed at the user's request. Local photo analysis is the default. The assessment below describes the preceding review and is superseded by this implementation. Historical provenance/usage remain compatible; remove provider constructor arguments and replace `ai` mode with `local`.

Reviewed original sources: [CYC symbols](https://www.craftyarncouncil.com/standards/crochet-chart-symbols), [Trishagurumi's pear](https://trishagurumi.com/wp-content/uploads/2021/07/crochet-pear-pattern-trishagurumi.pdf), [Geek and Yarn's staggered increases](https://geekandyarn.com/how-to-stagger-increases/), and [AmiGo](https://arxiv.org/abs/2211.01178). Pattern-specific keys remain authoritative; a pear shoulder includes plain rounds and finishing affects shape; staggering preserves totals. AmiGo takes a closed mesh, not a single photograph. Corrected its attribution to Edelstein et al., SCF 2022.

Our new dynamic program is an independent six-stitch-lattice fit, not an AmiGo implementation. It anchors the first round, preserves round count, and minimizes squared error against quantized targets under gauge and source-stitch constraints. Equal errors prefer less shaping. These constraints apply to the current single-crochet surface-of-revolution model only.

[18 original synthetic cases](profile-fit-comparison-20261014.json): 12 improve, six straight profiles remain exact. Classic shoulder error falls from 2556 to 864. This does not establish photo-recognition or physical accuracy. Reproduce with `.venv/bin/python -m scripts.diagnose_profile_fit --out /tmp/profile-fit.json`.

LLM removal assessment: generation, gauge, colors, validation and export already operate locally. Local vision plus human confirmation can be the main workflow. This change retains provider interfaces, required SDK dependencies and existing defaults; use `--local` explicitly when keys are configured. Complete removal would also cover packaging/lockfile, credentials UI, CLI/UI defaults, usage accounting and provider tests while preserving historical provenance. Local anatomy recognition remains incomplete.


## What online methods establish (primary sources checked 2026-10-09)

| Primary source | Useful evidence | Does not establish |
|---|---|---|
| [Craft Yarn Council yarn/gauge chart](https://www.craftyarncouncil.com/standards/yarn-weight-system) | Industry reference ranges, explicitly guidelines rather than a replacement for pattern gauge | Calibrated dimensions or yarn usage for this generator |
| [PlanetJune hook/tension experiment](https://www.planetjune.com/blog/stitch-tension-in-amigurumi-an-investigation/) | Changing hooks for the same cup sample changes size, stiffness and stitch gaps | Successful physical trials of our generated dolls |
| [CrochetPARADE author capability notes](https://github.com/stassev/CrochetPARADE/blob/main/capabilities.md) | An independent stitch-graph rendering, topology and tension tool | That exporting DSL alone executes a simulation or validates a physical object |

Keep reference cases, independent tool executions and physical measurements distinct.
Our `parade_export_rate` checks completeness and our emitter's syntax subset, not execution
in the external application. These references do not satisfy G3 or G4. Third-party makers
may submit traceable trials of exact system outputs under the [trial protocol](physical-trials.en.md);
finding a similar finished object is insufficient.

## Validator evolution: five prior corrections

| # | Rule | Change | Driving evidence | Fixture |
|---|------|--------|------------------|---------|
| 1 | Non-6-multiple rounds | hard error → note | Clover AKIHIRO's 22-st legs / 16-st arms / 9-st tail | `test_published_akihiro_*` |
| 2 | Adjacent-round jump ±6 | hard error → note (`allow_wide_jump` only suppresses this note) | Spin a Yarn's 8→16 doubling; Ms Premise-Conclusion's sin-profile sphere | `test_professional_eight_stitch_ring_start_passes_validation`, `test_ideal_sphere_*` |
| 3 | Mixed inc/dec in one round | hard error → note | Ziyou Handmade lop-ear rabbit eye-socket round 7X,7V,A,7V,7X | `test_cn_rabbit_head_face_shaping_passes` |
| 4 | Increase ≤ source stitches | hard error → note | solid granny round 2: +16 into 4 chain corner spaces (12 source sts) | `test_intl_solid_granny_space_increase_downgraded_to_note` |
| 5 | Decrease > half of previous (pure-A pairing) | hard error → note (external AI audit) | mechanical counterexample: 4 sts closed by one sc4tog (3 > 2, fully hookable); Minion's 8 ≤ 9 dense round still within pure-A pairing | `test_validator_downgrades_incapable_v_and_incapable_a` |

Downgrading is not loosening: hard errors still cover broken stitch
algebra, empty rounds, non-numeric fields, and stitch counts below one.
Notes have two export outcomes: non-6-multiples and wide jumps only warn
and export normally; mixed inc/dec and rounds beyond the uniform-grouping
model are skipped by the Parade exporter with a warning.

## Source list

### Official standards and professional organizations

| Source | What it verified | Fixture |
|--------|------------------|---------|
| [Clover AKIHIRO doll](https://www.clover-mfg.com/en/project/amigurumi-akihiro-crochet-pattern/) | 22-st legs / 16-st arms / 9-st tail / 14-st ears (prior fix #1); uniform +6 head | `test_published_akihiro_*` |
| [DROPS apple 23-60](https://www.garnstudio.com/pattern.php?id=5888&cid=17) | symmetric 7-start sphere, official gauge 18 sc/10cm; honest stem-chain warning | `test_published_drops_apple_*` |
| [CYC yarn weight system](https://www.craftyarncouncil.com/standards/yarn-weight-system) | gauge layer cyc_label mapping (7 categories) | `test_gauge.py` |
| [CYC project levels](https://www.craftyarncouncil.com/standards/skill-levels) | difficulty labels | `test_schemas.py` |
| [CYC abbreviations](https://www.craftyarncouncil.com/standards/crochet-abbreviations) | CrochetPARADE DSL token consistency | `test_parade_tokens_align_with_cyc_abbreviations` |
| [Shelley Husband US↔UK chart](https://shelleyhusbandcrochet.com/uk-and-us-crochet-terms-conversion-help-and-chart/) | one-level offset conversion chain (sc=dc, hdc=htr, dc=tr, tr=dtr, dtr=ttr) — the glossary's UK column | `test_height_ladder_us_uk_offset_invariant` |
| [Chinese symbol system (Zhihu/Reddit beginner guides)](https://zhuanlan.zhihu.com/p/2397749055) | X/T/F/E/V/A letter notation <-> sc/hdc/dc/tr — the glossary's Chinese and symbol columns | `tests/test_stitches.py` |
| [cbfiberworks loop stitch](https://cbfiberworks.com/how-to-make-loop-stitches-for-amigurumi/) / [Yarnhild](https://yarnhild.com/how-to-crochet-the-loop-stitch/) | texture family: loops face the wrong side (turn inside out / front-side variants), decrease holds 4 loops on hook, double-loop curl warning, yarn-hungry | `test_intl_loop_stitch_texture_rounds_pass`, `test_loop_stitch_family_entries` |
| [AmiguRoom Russian bear](https://amigurum.ru/2018/04/medvezhonok-amigurumi.html) (Yulia Deinega) | full 6<->3 sector transition in both directions (corroborates Mr. Orange's hat), 17 rounds of drifting decreases, 5-start tail; comment-section consensus: pack the neck firmly -> assembly note | `test_intl_ru_deynega_bear_*`, `test_assembly_neck_stuffing_note` |
| [Yarnspirations Red Heart Bear](https://www.yarnspirations.com/products/red-heart-bear-amigurumi) (Sarah Zimmerman) | North-American major-brand anchor: 10-start joined rounds throughout, one-piece with a 12-st waist pinch, eye gap = max/6 exactly, 12mm eyes @ 23cm, official 13 sc/10cm gauge, sideways feet for sitting support | `test_intl_red_heart_bear_*` |
| [Lion Brand classic granny](https://www.lionbrand.com/community/blog/how-to-crochet-a-classic-granny-square/) | corner topology +12/round, 76-st border | `test_intl_lionbrand_classic_granny_passes` |

### Professional studios / independent designers

| Source | What it verified | Fixture |
|--------|------------------|---------|
| [Supergurumi bee](https://www.supergurumi.com/amigurumi-crochet-bee-pattern) | 55-round one-piece head+body (peak 66), per-round color bands, BLO ridge rounds, offset shaping, odd 33→9→6 closing; Catania yarn calibrates fine-bucket meterage | `test_published_bee_*` |
| [AllAboutAmi elephant](https://www.allaboutami.com/elephantpattern/) | trunk cone −3/round; oval-chain body and across-parts legs out of the aggregate model (honestly recorded, no fixture) | `test_intl_elephant_trunk_cone_taper_passes` |
| [StringyDingDing kangaroo](https://stringydingding.com/kangaroo-amigurumi-free-crochet-pattern/) | plain round after the ring, one-piece asymmetric shaping, odd 21/15 rounds; **leg R5 published contradiction** (2nd real print error — validator catches it) | `test_published_kangaroo_*`, `test_validator_catches_published_kangaroo_leg_round5_contradiction` |
| [53stitches low-sew bunny](https://53stitches.com/low-sew-bunny-free-crochet-pattern/) | MR-8 start, popcorn limbs (5dc, count-neutral) | `test_intl_lowsew_bunny_popcorn_limbs` |
| [Tiny Curl Monsieur Bear](https://www.tinycurl.co/monsieur-bear-free-amigurumi-crochet-pattern/) | beret explicitly "joined rnds, not continuous spiral", ch-3-counts convention, MR7 turned hdc ear | `test_intl_tinycurl_*` |
| [Craftably Ever After Patchy Bear](https://craftablyeverafter.wordpress.com/2022/04/22/patchy-bear-crochet-pattern/) | chain-joined body R15=36 (13sc+2ch+16sc+2sc+3sc, self-reported); oval start [10]; eye anchor "2 rows above cap edge, 2 sts apart" | `test_intl_patchy_bear_chain_joined_body_passes`, `test_intl_snout_oval_start_verbatim` |
| [Squirrel Picnic Motley Bear](https://squirrelpicnic.com/2015/04/24/motley-the-bear-crochet-pattern/) | joined and spiral rounds mixed in one piece, uncounted turning chain, (sc,sk)×6 skip close, FLO neck round | `test_intl_squirrelpicnic_motley_joined_muzzle_and_skip_close` |
| [Marching North solid granny](https://www.marchingnorth.com/solid-crochet-granny-square-pattern/) | +16/round into chain spaces (driving source of prior fix #4) | `test_intl_solid_granny_space_increase_downgraded_to_note` |
| [Chibiscraft Minion](https://blog.alwaysfreeamigurumi.com/cute-minion-amigurumi-free-crochet-pattern/) | dense round with 5×sc2tog + sc4tog for a net decrease of 8 (the early 4× transcription note is retained as errata; no longer treated as evidence for a universal hard rule), sole BLO/FLO alternation, 54→9 taper, oval start [12] | `test_intl_minion_*` |
| [Spin a Yarn Rudolph](https://spinayarncrochet.com/rudolph-ornament-free-crochet-pattern/) | 8-st doubling start (driving source of prior fix #2) | `test_professional_eight_stitch_ring_start_passes_validation` |
| [Ms Premise-Conclusion ideal sphere](https://mspremiseconclusion.wordpress.com/2010/03/14/the-ideal-crochet-sphere/) | sin profile vs independently recomputed values; craft-warning handling | `test_ideal_sphere_*` |

### Community tutorials and forums

| Source | What it verified | Fixture |
|--------|------------------|---------|
| [PlanetJune magic ring](https://www.planetjune.com/blog/amigurumi-help/how-to-crochet-a-magic-ring/) | 6-start +6 formula; seamless closing (front loops) | `test_generated_sphere_matches_community_formula` |
| [PlanetJune needlesculpting](https://www.planetjune.com/blog/tutorials/needlesculpting/) | needle sculpting (optional assembly step): eye sockets via a pass through the whole head, both ends pulled tight from one hole and hidden; invisible weaving (under the V of each stitch); anchor placement; "patterns with built-in shaping don't need this" | `test_assembly_optional_needle_sculpting_step` |
| [Grace and Yarn weighted base](https://www.graceandyarn.com/2019/12/how-to-add-weighted-base-to-your.html) / [The Loopy Lamb](https://theloopylamb.com/how-to-use-poly-pellets-in-amigurumi/) | weighted-base method (optional): ~3/4 cup poly pellets in a knotted stocking, placed at the bottom while the decrease opening still admits a hand, stocking color close to the doll, not for under-3s, washable | `test_weighted_base_materials_and_assembly` |
| [r/Amigurumi eyes wiki](https://www.reddit.com/r/Amigurumi/wiki/faq_eyeqs/) | safety-eye size bands (mini 5–6 / regular 8–12 / large 14–20+ mm) | eye ladder in `test_crochet_params.py` |
| [kruchcom.ru finger puppet](https://kruchcom.ru/archives/22215) | Russian КА/ПРИБ/СБН verbatim — the same standard across languages | `test_russian_finger_puppet_rounds_pass_validation` |
| [Lovable Loops cherry C2C](https://lovableloops.com/cherry-square-mini-c2c-crochet-pattern/) | 9×9 written block rows, full round-trip | `test_grid_pipeline_reproduces_published_c2c_chart` |
| [Lovable Loops heart C2C](https://lovableloops.com/mini-heart-square-c2c-crochet-pattern/) | asymmetric rows pin the reading direction (↙RS / ↗WS) | `test_grid_written_rows_match_published_heart_chart` |
| [Maclafersa wire safety guide](https://maclafersa.com/how-to-add-wire-to-amigurumi-safely-for-posing/) | looped-and-wrapped ends (tape alone unreliable), hand-to-shoulder-to-hand measuring, tails slightly shorter, insert while open, nine common mistakes | `test_materials_wire_row_for_limbs_only` |
| [Crafty Intentions wire supplies](https://craftyintentions.com/blog/2019/7/8/supplies-wire) | paper-wrapped 18-gauge 18-inch floral wire spec anchor (cloth-wrapped too soft), paper-crumple friction, rust warning | `test_materials_wire_row_for_limbs_only` |
| [toruyuri circle increase law](https://toruyuri.com/2020/02/02/wanomashime/) | Japanese staggered-increase law (odd rounds at end / even rounds mid-unit; hexagon-vs-circle photo proof); ring-start experiment (3 min, 10 leaves a hole); 4th language notation (dan/me/mashime) | `test_japanese_circle_increase_law_passes`, `test_preamble_mentions_increase_offset_rule` |
| [Zepiany ES-Bee](https://www.zepiany.com/pages/es-bee1) / [Melonchillo magic-circle law](https://melonchillo.com/anillo-magico/) | 5th language notation (vuelta/pb/aum); symmetric 30-peak sphere; 3rd published contradiction (V1 notation 6 vs prose 8); start-count-per-stitch-height law (sc 6 / hdc 8 / dc 12); safety-eye under-3/pets warning -> materials row | `test_intl_zepiany_es_bee_body_and_contradiction`, `test_intl_melonchillo_dc_circle_start_height_law` |

### Chinese-language patterns (image charts, vision-transcribed)

| Source | What it verified | Fixture |
|--------|------------------|---------|
| [Ziyou Handmade lop-ear rabbit](https://www.bianzhirensheng.com/a/44051_zhifa.html) / [Mr. Orange](https://www.bianzhirensheng.com/a/44093_zhifa.html) | face shaping with mixed inc/dec (prior fix #3 driving source), sc3tog (M), flat oval ear, 3-sector hat +3/round, 7-start headcover, foot decreasing to odd 7 | `test_cn_tuanzi_*`, `test_cn_rabbit_*`, `test_cn_orange_*` |
| [Bone Dunzi](https://www.bianzhirensheng.com/a/44074_zhifa.html) / [Gummy series](https://www.bianzhirensheng.com/a/44140_zhifa.html) | symmetric cadence, doubling round honestly downgraded (8→16), bobble (B) neutral semantics + legend | `test_cn_bone_doubling_round_passes_with_note`, `test_cn_gummy_*` |
| [Qingyi Handmade Little Rabbit Sister](https://www.bianzhirensheng.com/a/43996_zhifa.html) (Xiaohongshu-native) | overalls two-leg merge 24+24→48, carrot shoulder shaping, 5-start odd close | `test_cn_overalls_two_leg_join_passes`, `test_cn_carrot_*` |

## Method and honest record

- **Verbatim full text**: HTML is fetched and only round lines are
  taken; every round is mechanically checked against
  `st = prev + inc − dec` before becoming a fixture — four
  transcription errors were caught by the validator on the spot (bee
  R6, carrot R3, low-sew bunny elided rows, gummy), and the fixtures
  double as errata records.
- **Image charts (the dominant Chinese format)**: transcribed
  round-by-round by the editor's vision, then run through the same
  validator.
- **Reachability backlog** (not verifiable, recorded honestly): Etsy
  403, Ravelry login wall, Xiaohongshu login wall + image charts,
  Bianzhirensheng share platform 502, private forum sections,
  Raffamusa 403, Hobbii PDFs, Ami Amour 404, Supergurumi /patterns
  index 404. These sources are not in the fixtures; they will be
  added if they become reachable.


## Public photo/pattern pair probe (2026-10-09)

The [recorded probe](public-pair-probe-20261009.json) runs two source-site finished-item
photos through the local pipeline, with cloud APIs and optional pose disabled. Pattern
instructions are withheld from generation. Photos remain in temporary local storage;
only URLs, image hashes, source-code fingerprint and observations are recorded.
Clover AKIHIRO misses ears/tail; 53stitches Bunny misses ears and adds a skirt.
Both generated patterns pass stitch validation. Source construction also differs from
the default separate-part output. These are development cases already used in rule
fixtures, not held-out release evidence. Uncalibrated gauge prevents direct size claims.
Run `python -m scripts.probe_public_pairs --help` for reproduction arguments.


## Expanded public-pair probe (2026-10-09)

The [catalog](public-pair-catalog-20261009.json) now contains 10 photos from five
publishers, adding cat, pigeon, gummy worms, cupcakes, pretzel, bear, elephants and bee.
The [actual run](public-pair-probe-expanded-20261009.json) completes all 10, with 10
unique hashes and 10 valid stitch-arithmetic outputs. Canonical part sets match exactly
in 0/6 scored single-animal cases. Four multi-subject/non-animal boundary cases are
excluded from part metrics. This selected local-only development sample does not estimate
population accuracy or cloud-model performance. Unsupported anatomical features are listed
separately. Manual inspection places the bear's detected face box on its legs and the
pigeon's on its abdomen. Both inferred ratios reach the configured upper limit.

Use `--catalog docs/public-pair-catalog-20261009.json --image-dir <local-images> --out <report>`
with `python -m scripts.probe_public_pairs`. Download URLs and filenames are in the catalog;
images are not redistributed. Three new accounting tests, Ruff and script mypy pass.
Application code is unchanged; the full application suite was not rerun.


## First changes driven by the paired probe

The [guarded rerun](public-pair-probe-guarded-20261009.json) uses the same 10 images.
Automatic skirt false additions fall from two to zero. Five of six detected head
candidates are rejected for unsuitable position/relative size; default proportions are
explicitly marked for review. Canonical part-set matches remain 0/6 and stitch validity
remains 10/10. No new animal-semantic recognizer is claimed.
The photo UI requires user selection of a single representable subject before generation;
multiple/unsupported selections block that button. This is manual screening. CLI/direct
pipeline calls still emit unreviewed templates with explicit metadata and export notices.


## Second acquisition batch (2026-10-09)

Six original pattern pages were checked; five photo pairs were acquired and actually run:
lilleliis elf and tree, Spin a Yarn mermaid, Cuddly Stitches jellyfish, Yarnhild lamb.
Stitch by Fay mushroom remains a candidate after direct acquisition returned HTTP 403;
no photo result is claimed. See the [catalog](public-pair-catalog-wave2-20261009.json)
and [run](public-pair-probe-wave2-20261009.json). The accumulated sample has 15 distinct
photo hashes from nine sites; both latest batches share the same application source hash.
The jellyfish uses a single-subject source photo with text retained, replacing the collage
cover before labeling/running. All five pass arithmetic; none of three canonical-part
comparisons match exactly, with two boundary cases excluded. Elf misses hat/ears; mermaid
misses tail and gains legs; lamb misses ears/tail and gains arms. Tree/jellyfish still get
humanoid templates through the direct unreviewed pipeline. Panel construction and non-biped
anatomy are additional gaps. No application or probe code changed, and the full test suite
was not rerun for this acquisition-only batch.

## 2026-10-11: construction and local-color candidates

The [candidate catalog](public-pattern-candidates-20261011.json) adds seven primary-source
references: five readable origin pages and two indexed-origin-text references whose direct
fetch failed or required browser verification. It records source URLs, structural facts,
access limits and algorithm hypotheses. No new third-party photos were processed, no visual
labels were asserted, and these references do not increase the earlier 15-photo probe count.
They do not constitute G3/G4 evidence or authorize calibration.

The examples contrast sewn panda patches with in-round colorwork, flat-panel construction,
two-sided snail shells, a continuous flattened whale tail and a puppy head on a rattle handle.
See the linked catalog for each original source and evidence level.

An [original synthetic diagnostic](color-layout-diagnostic-20261011.json) isolates a limitation:
two separate black patches and one central patch, each containing 1280 black pixels on a
160×160 canvas, produce the same all-white horizontal bands even with a perfect supplied
foreground mask. This is representation loss, not a real-photo score. Reproduce with:

```bash
.venv/bin/python -m scripts.diagnose_color_layout --out /private/tmp/color-layout.json
```

Next algorithm work should retain minority-color coverage and 2D regions, accept reviewed
part/patch regions, distinguish in-round segments from applied decoration, and evaluate
construction mode separately from visible anatomy. These changes remain proposed; no
production vision behavior was changed in this source-discovery round.

### Follow-up implementation: spatial color observations

The [updated comparison](color-layout-observation-20261011.json) uses the same original
pixels and supplied masks. Majority bands remain all white, but observations now preserve
1280 black pixels in each image and distinguish two separate patches from one central patch.
The historical diagnostic remains unchanged; the command above now emits the updated report.

The existing quantization/mask pass supplies complete per-band color counts, mask provenance
and normalized region boxes. At most 64 regions are retained; fragments below
max(4, ceil(foreground_pixels * 0.002)) and overflow retain total counts and omission accounting.
A 2% aggregate within-band minority fraction triggers review text in the UI and Markdown/PDF;
this is a UI threshold, not calibrated confidence. Observations survive backups, size changes
and links that fit the existing URL limit; oversized links still require a backup file.
Coordinates describe the cropped image, not stitches. Applied decorations versus in-round
colorwork remain undecided. No new real-photo validation or local-color stitch generation
is claimed.

## 2026-10-12: Narrow stripes and boundary refinement

Three primary-source pages were read; no source photographs or pattern prose were copied:

- [Sharon Ojala's Little Bee](https://www.amigurumitogo.com/2020/04/little-bee-free-crochet-pattern.html)
  uses short color intervals and explicitly discusses stripe placement.
- [Stitch by Fay's No-Sew Bee](https://www.stitchbyfay.com/crochet-bee-pattern/)
  combines spiral construction, back-loop stripes and wings joined during crocheting.
- [Ollie + Holly's cotton stripe experiment](https://www.ollieholly.com/blog/2021/03/24/how-to-crochet-better-stripes-for-amigurumi-when-using-cotton-yarn-an-experiment)
  compares methods for reducing color-change jogs in cotton.

Our inference: preserve narrow color intervals independently of stitch and assembly semantics.
`vertical_color_bands` now overlays sustained row-majority runs on the existing coarse estimate.
Rows require 75% color agreement and max(4, ceil(maximum foreground row width * 0.2)) support;
runs require max(2, ceil(thumbnail height * 0.015)) rows. These are uncalibrated noise heuristics.
Empty, ambiguous and short runs retain coarse estimates. `refine_stripes=False` reproduces the baseline.
Raw band counts and spatial evidence remain unchanged, so review warnings remain conservative,
not a score of refined-band error.

The [reproducible comparison](color-stripe-comparison-20261012.json) uses nine original four-pixel
stripe fixtures with three heights and three positions, all with perfect supplied masks.
Exact stripe color/boundary recovery changes from **0/9 to 9/9**. Regression tests additionally cover
single-row noise, sparse foreground, minority patches, evidence preservation and round-color lookup.
Run `.venv/bin/python -m scripts.diagnose_color_stripes --out /private/tmp/color-stripes.json`.

These are development counterexamples, not held-out photographs, G3/G4 evidence or physical calibration.
The image's vertical axis is still assumed. Oblique stripes, occlusion, yarn texture and complex
backgrounds require authorized photo validation. Thumbnail reduction can erase subpixel stripes,
and round sampling can still skip intervals narrower than one generated round.

### Follow-up: interval coverage for round colors

Round allocation now sums overlap by color over each equal-height round interval and selects the
largest total. This minimizes vertical mismatch under the existing equal-height approximation;
it does not guarantee preservation of every stripe. Ties prefer the midpoint color, then image order.
Bottom-up parts reverse the completed top-down plan. Blocks with no overlapping round assigned their
color trigger review notes in patterns and exports, even if the same color appears elsewhere.

The [three original interval diagnostics](round-color-comparison-20261012.json) show mismatched-height
fractions of 9.8% → 0.2% for a midpoint sliver, 75% → 55% for three colors within one round, and
0% → 0% for a resolvable stripe. Run
`.venv/bin/python -m scripts.diagnose_round_colors --out /private/tmp/round-colors.json`.
An independent integer-pixel oracle checks 280 seeded cases; tests also cover reversal, repeated-color
loss, stitch algebra and exported review notes. These are development diagnostics, not photo accuracy,
3D surface-area measurements or physical trials.

[PlanetJune's color-change tutorial](https://www.planetjune.com/blog/amigurumi-help/how-to-change-colour-in-amigurumi/)
distinguishes switching yarn on the previous stitch's last pull-through from techniques for improving
full-stripe jogs. Generated instructions now acknowledge that spiral jogs can remain; no extra stitches
or unsupported joining technique are inserted.
