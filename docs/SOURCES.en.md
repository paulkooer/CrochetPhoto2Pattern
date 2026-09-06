# External Calibration Evidence Chain (Pattern Source Index)

[简体中文](SOURCES.md) | **English**

The domain assumptions in this system are not guessed: every example
comes from a real, hookable public pattern, transcribed verbatim,
mechanically verified round by round, and pinned as a runnable test
fixture ([`tests/test_reference_patterns.py`](../tests/test_reference_patterns.py),
52 tests). Real patterns overturned four generator priors, and the
validator was corrected each time — the evidence for every correction
is in the table below. Only stitch algebra and round structure are
taken from each source, never creative text (per each source's terms).

## Validator evolution: four prior corrections + one rule that held

| # | Rule | Change | Driving evidence | Fixture |
|---|------|--------|------------------|---------|
| 1 | Non-6-multiple rounds | hard error → note | Clover AKIHIRO's 22-st legs / 16-st arms / 9-st tail | `test_published_akihiro_*` |
| 2 | Adjacent-round jump ±6 | hard error → note (`allow_wide_jump` allowlist kept) | Spin a Yarn's 8→16 doubling; Ms Premise-Conclusion's sin-profile sphere | `test_professional_eight_stitch_ring_start_passes_validation`, `test_ideal_sphere_*` |
| 3 | Mixed inc/dec in one round | hard error → note | Ziyou Handmade lop-ear rabbit eye-socket round 7X,7V,A,7V,7X | `test_cn_rabbit_head_face_shaping_passes` |
| 4 | Increase ≤ source stitches | hard error → note | solid granny round 2: +16 into 4 chain corner spaces (12 source sts) | `test_intl_solid_granny_space_increase_downgraded_to_note` |
| — | Decrease ≤ half of previous | **stays hard** (positively verified) | Minion leg R3: sc4tog + 4×sc2tog across 18 sts, decrease equivalent 8 ≤ 9 | `test_intl_minion_leg_densest_real_decrease_round` |

Downgrading is not loosening: hard errors now contain only "physically
unhookable" items; notes mean "fully hookable but outside this
generator's uniform (aX,V)×n grouping — the exporter skips such rounds".

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
| [Chibiscraft Minion](https://blog.alwaysfreeamigurumi.com/cute-minion-amigurumi-free-crochet-pattern/) | densest real decrease round (rule holds), sole BLO/FLO alternation, 54→9 taper at the 18//2 boundary, oval start [12] | `test_intl_minion_*` |
| [Spin a Yarn Rudolph](https://spinayarncrochet.com/rudolph-ornament-free-crochet-pattern/) | 8-st doubling start (driving source of prior fix #2) | `test_professional_eight_stitch_ring_start_passes_validation` |
| [Ms Premise-Conclusion ideal sphere](https://mspremiseconclusion.wordpress.com/2010/03/14/the-ideal-crochet-sphere/) | sin profile vs independently recomputed values; craft-warning handling | `test_ideal_sphere_*` |

### Community tutorials and forums

| Source | What it verified | Fixture |
|--------|------------------|---------|
| [PlanetJune magic ring](https://www.planetjune.com/blog/amigurumi-help/how-to-crochet-a-magic-ring/) | 6-start +6 formula; seamless closing (front loops) | `test_generated_sphere_matches_community_formula` |
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
