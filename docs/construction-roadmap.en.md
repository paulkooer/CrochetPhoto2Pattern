# From known patterns to complex reference pieces

[简体中文](construction-roadmap.md) · [Prototype usage](dressed-doll-design.en.md)

The objective is a workable pattern that resembles its reference. The current dressed-doll prototype
does not meet the construction requirements of complex clothed references. Named parts, successful
exports and balanced stitch counts do not establish reconstruction. Colour work remains deferred.

## Gate 1: represent known working paths

Describe where stitches are worked, which sites are held, when work moves to another edge, and how it
resumes. Unsupported construction must not be silently replaced with rectangles, tubes or seams.

On 2026-11-16, `working-path-v2` gained these generic capabilities:

- Foundation chains and chains resumed from an explicit root or current loop; skipped turning chains
  do not become working stitches.
- Partial work, held sites and separate bridge faces for body and sleeve paths.
- Corner sites derived from the two bridge-to-base junctions, with recorded sources.
- Row-end pickups from declared flat-row orientation, plus consecutive row-number and reversal checks.
- Explicit BLO/FLO use, with evidence required before later reusing a reserved half loop.
- Binding slips kept separate from live stitches; paired seams and invisible-join turn order.
- Buttonholes with explicit skipped stitches and replacement chains, without calling the skips decreases.
- Phase-specific hook and gauge records; unmeasured ribbing cannot inherit invented measurements.

Out-of-range sites, alias reuse, unsupported loop claims, invented row ends, row gaps and unexplained
live sites are rejected. Each output stitch retains its sources.

The original synthetic exercise starts with 28 sites. Its resulting body edge has 22 working sites,
including 16 single-crochet outputs and six chain sites. Each armhole path has nine sites. These counts
have no garment-size meaning and do not transcribe a doll pattern.

```bash
python -m app.working_paths --out-dir eval_outputs/armhole-working-path --pdf

python -m app.working_paths --plan /path/to/working-path.json \
  --out-dir eval_outputs/manual-recipe --pdf
```

This writes `path-plan.json`, `path-result.json`, `path-explanation.md`, and an optional PDF using the
existing `pdf` extra. Existing files are not overwritten. Manual recipe tables and diagrams derive from
the same checked operations rather than a separate handwritten stitch script. V1 inputs remain readable;
new operations require V2 instead of silently claiming old-format support.

In the manual tab, open **人工工序图解（校验与阅读）**, upload a working-path JSON and validate/load it.
Review notes and rows are shown before downloading the plan, explanation, PDF and source records.
Changing the upload disables stale downloads; invalid input or PDF layout failure retains the previous
plan. Inputs are limited to 2 MiB; duplicate keys, non-finite values and unknown schemas are rejected.

This is manual recipe checking and reading, not photo generation. Existing patterns, trial packages and
the older dressed-doll generator keep their formats and behaviour.

**This gate is still incomplete.** Control records do not establish physical orientation. Earlier-round
post stitches, mixed stitch heights and general crochet-as-you-go joins remain unsupported. There is no
cloth simulation, fit, likeness or physical-execution evidence. Half-loop and row-end sites are introduced
explicitly when supported by source records; this does not enumerate every unused loop in the fabric.
Within a declared section, turned continuations check canonical source order and alternating fabric
sides, including through held aliases. This does not infer continuity between sections or the geometry
of arbitrary pickup paths. Results list sites retired by declaration separately: a closed inventory
includes declared finished borders and does not mean every site was actually crocheted.

## Gate 2: complete an evidence-based cardigan

First represent one complete cardigan: neckline/shoulder shaping, skipped stitches and chain armholes,
sleeves picked up from those holes, front bands and buttonholes, hem and cuffs, and measured gauges for
the different constructions. Each must have explicit steps and sources. A complete local manually
encoded candidate now covers body, hem, three buttonholes, both sleeves, cuffs and seams. Source ambiguities
in row numbering, repeats and terminal attachment references are recorded separately. Candidate repairs
do not establish a literal pass of the source tutorial. A smaller yoke/armhole/first-sleeve-row exercise
avoids those hem and band repair choices.
Self-review found that the earlier 60-row hem argument treated continuing a live yarn loop as consuming
a base stitch. That derivation is invalid. The 60-row hem and terminal band attachment remain unverified
design assumptions; the full candidate is on hold for whole-garment trials. The local armhole exercise
does not depend on those choices and remains a manually encoded draft awaiting physical checking.

### Synthesize instructions from dimensions

The 2026-11-17 `app.models.attached_ribbing` experiment covers attached SC/slip-stitch ribbing.
It converts target edge length, width and construction-specific stitch/row gauges into integer counts,
distributes one or two base attachments on each return, then emits explicit working paths. Attachment
slips do not become next-row stitches. The method specifies base order, live loop, foundation face and
whether to turn after the foundation; these are not inferred from a total count.

With 18 base sites and a hypothetical 6cm target, 40 rows/10cm produces 24 rows with alternating 2/1
attachments; 30 rows/10cm produces 18 rows with two attachments per return. These are engineering inputs,
not measurements of IMG_0623. Quantized dimensions are reported separately. Missing ribbing gauges or an
unsupported attachment rate do not produce a pattern or silently substitute ordinary SC gauge. Unused
foundation faces, end rows and optional first-row front loops remain explicit; seam orientation is not
automatically resolved, and no sites are retired to manufacture a closed inventory.

```bash
python -m app.ribbing_design --target target.json --out-dir eval_outputs/ribbing-design
python -m app.ribbing_design --target target.json --base-plan base-plan.json \
  --method method.json --out-dir eval_outputs/ribbing-path --pdf
```

Inputs follow `RibbingTarget` and `RibbingMethod`. User-entered swatch numbers are not assistant-verified
measurements. The combined design below connects this layer to the yoke and band modules; the photo path
and older doll planner do not automatically use these methods.

### First parametric yoke, button band and combined candidate

The later 2026-11-17 increment adds `raglan_yoke`, `button_band`, and `cardigan_design`. The general
top-down yoke/body/sleeve sequence is checked against [DROPS' raglan cardigan explanation](https://www.garnstudio.com/pattern.php?cid=17&id=12821).
Our all-SC first row, symmetric five-panel allocation, increase scheduling and dimensional search are
independent prototype choices, not a reproduction or physical validation of that pattern or JOLA.

The yoke places eight increases at four panel boundaries and schedules increase rows within the target
depth. Incompatible neckline/body/sleeve constraints stop within an explicit count-adjustment policy.
Body span excludes bands. Armholes retain bridge faces, held stitches and two declared corner pickups;
their orientation and fit remain unverified. Bands traverse hem end, front side, neck, opposite side and
opposite hem end. Explicit `edge_path` transfers reservation ownership without creating fabric or letting
old aliases reuse it. One pickup per row end, terminal-row omission and retained root heads are declared
design assumptions. Buttonhole positions quantize to odd return rows; collisions, neck intrusion and
insufficient width stop. Mirrored button positions require physical pinning and checking.

Open **手动输入 → 开衫工艺设计（试验）** to edit targets and use unknown, hypothetical, or separately entered
swatch gauges. Own-swatch fields start empty; example values cannot simply be relabelled as measurements.
Changed inputs disable stale downloads. The CLI is:

```bash
python -m app.cardigan_design --design cardigan-design.json --out-dir eval_outputs/cardigan-design --pdf
```

`cardigan-design-v1` inputs produce `parametric_design` working paths. Missing later inputs preserve the
known stage and its gaps instead of falling back to a doll template. The combined candidate retains cuff
start/end loops and two root heads. Cuff seams, root-edge finishing, corner geometry, ease and elasticity
remain unresolved, so it is not ready for a whole-garment trial. Photo-driven method selection and G3/G4
qualification have not been established.

Cuffs remain open by default. An explicitly selected `blo_to_reserved_flo` alternative pairs the last
row in reverse, starting at its live-loop end, with the reserved first-row FLO in forward order; the
last-row side uses BLO. It is a new seam-design candidate, not a verified interpretation of the source
tutorial's inner/outer directions or folded appearance. Physical edge and fit checks remain outstanding.

### Yarn segments and finishing controls

New candidates enable `yarn_tracking`: one continuous segment from neckline through band, plus one
segment per sleeve. New-yarn starts, fastening off at the live loop, parking, resuming and weaving
individual ends are explicit instructions, and stitch events identify their segment. The general
cut-end-through-loop finish is checked against [PlanetJune's tutorial](https://www.planetjune.com/blog/amigurumi-help/fastening-off/).
The default 15cm tail is an adjustable design parameter, not a material estimate or source endorsement.

The selected-seam candidate contains three fastening-off and six end-weaving instructions. The open-cuff
review version parks each loop on a marker and weaves only its starting end. Parked work remains attached
to its yarn supply; starting the other sleeve needs another available yarn end. Checks reject replacing
an active loop without parking or fastening, finishing at the wrong location, weaving an uncut ending
tail, duplicate end declarations and missing turns between sections. The prototype now splits on RS and
quantizes depth to a supported odd row count; this is a method choice, not a general crochet rule.

Yarn controls do not consume fabric heads. A declared border is not a fasten-off. Legacy plans stay
readable but are marked untracked. Yarn accounting reports instruction declarations, never physical
execution. Root heads remain marked for edge inspection; geometry, fold and fit remain unverified.
Download caches bind to both inputs and engine version so an upgrade cannot serve an old generated PDF
as the current design.

Deliver complete instructions, source-site comparisons and unresolved items. Compare actual working
paths against the known tutorial. Part names and attractive previews cannot substitute for this check.

## Gate 3: review and local physical trials

The assistant owns initial technical checking. Its own review must not be described as independent
expert review. There is currently no independent crocheter review or physical result for these new
constructions. The user confirms the intended appearance, without being responsible for auditing stitch
logic.

Validate key construction and try the garment on an existing doll where available before committing
to a whole complex piece. Record every maker correction. Software checks neither prove physical success
nor establish that a proposed alternative is necessarily impossible to crochet.

## Gate 4: select construction from photos

After checked construction modules exist, image analysis can propose the neckline, armholes, outfit,
hat, hair, footwear and accessories. Distinguish visible observations from inferred choices. A photo
cannot uniquely determine hidden joins, original counts, hook size or gauge.

A vision model may help select candidate methods. Explicit working paths and parameters generate the
instructions, which are then checked. Identify unsupported construction rather than silently
simplifying it. Reading a supplied tutorial does not establish photo-to-pattern generation.

## Gate 5: test transfer on a different piece

The supplied reference and tutorial are development material, not independent generalization evidence.
Use another piece/tutorial excluded from development, plus key physical construction checks.
Existing G3/G4 gates are unchanged; this numerical experiment provides no physical-trial credit.

Report separately what can be represented, what was checked, what was physically demonstrated, and
what essential capabilities remain absent.
