# Dressed-doll construction prototype

The current construction does not meet complex reference reconstruction requirements. See the
[construction roadmap](construction-roadmap.en.md) for the next gates. A separate manual-recipe reader
can check explicitly encoded complex operations; this designer does not automatically use them.

[简体中文](dressed-doll-design.md) · [Documentation index](README.md)

This opt-in workflow creates reviewable component instructions for clothed dolls. It uses explicit
human-selected construction and dimensions. It does not recognize these structures from photographs,
recover an original pattern, or establish physical correctness or likeness. The photo pipeline,
G3/G4 gates and existing pattern/project/trial formats remain unchanged.

## Application workflow

Open the manual-input tab and expand `穿衣人偶结构原型（新增）` at the bottom.

1. Choose the wide-brim/curly-hair/dress or folded-band/straight-hair/jacket-and-skirts starter.
2. Enter the target height and this prototype's stitch/row gauge. The defaults, 24cm and 22 stitches/
   28 rows per 10cm, are design assumptions. Measure round, flat-row and ribbing swatches separately.
3. Adjust head, palm/wrist, sole dimensions, bodice length, hair and hat construction, then generate.
4. Inspect component sections and the assembly graph. Download the design JSON, plan JSON,
   Markdown, and optionally prepare a PDF.
5. Changing inputs retains the previous plan for inspection but disables its downloads until regeneration.

All editable dimensions and construction selections are in the design JSON, which can be edited
locally and reloaded. There is no new cloud model, photo upload or palette inference. The graph shows
actual assembly references; it is not a predicted finished object or a physical simulation.

## Construction coverage

- Head and torso: a separate head and hip/waist/chest/neck transitions.
- Hats: crown plus brim, or a separate flat BLO strip joined into a folded band.
- Hair: a cap, long strands and fringe, with straight or increased return rows.
- Arms: palm, wrist and forearm sections; individual thumbs/fingers are not implemented.
- Shoes: a two-sided chain oval sole, toe-specific decreases, heel shaping and an open shaft.
- Garments: full and split panels, specified shoulder stitches, an open neckline, armhole row edges
  and separate open sleeve tubes. Impossible armhole depth causes an error rather than silent clamping.
- Skirts: separate open layers with distinct waist and flare counts.
- Accessories: a folded bag panel, flap, strap and optional separate flower centres/petals.

Fit remains unverified. Sleeve stitches and panel row edges are different units: distribute seams by
length rather than assuming one stitch per row. The examples approximate structure in crochet and
do not reproduce every texture or material visible in a reference photograph.

## CLI and formats

```bash
python -m app.doll_cli --starter wide_brim_curls \
  --out-dir trial_outputs/dressed-wide-brim --pdf
python -m app.doll_cli --starter folded_cap_layers \
  --out-dir trial_outputs/dressed-folded-cap --pdf
python -m app.doll_cli --design trial_outputs/dressed-wide-brim/design.json \
  --out-dir trial_outputs/dressed-wide-brim-revised --pdf
```

Installing the current source also supplies `crochet2pattern-doll`. PDF export uses the existing
optional PDF dependency. Outputs are `design.json`, `plan.json`, `plan.md`, `assembly.dot` and optionally
`plan.pdf`. Existing destinations are not overwritten. Validation and optional export complete before
output writing begins.

The schemas are `dressed-doll-design-v1` and `dressed-doll-plan-v1`. These are not legacy PatternResult
backups, saved projects or trial ZIPs. Keep prototype photos and modifications separately; they do not
automatically become qualifying G4 records.

## What checks establish

Foundations distinguish magic rings, chain rings, flat chains and two-sided oval chains. Subsequent
steps must consume the preceding working stitches and produce exactly the declared count. Flat SC
turning chains are recorded separately, including in workload counts, and do not become working
stitches. Assembly references must exist and form a rooted acyclic graph. Export revalidates the model,
and JSON cannot upgrade the literal `unverified_prototype` evidence level.

These checks do not certify fit, fabric flatness, size, likeness or physical crochetability. No yarn
weight or time estimate is offered. Mixed stitch heights, vertical colourwork, complex petals,
individual fingers, buttonholes and any original knitting or non-yarn materials remain outside this
version. A successful basic component does not establish whole-object reconstruction.

## Method references

SC foundations and turning rules were checked against the [Craft Yarn Council pattern-reading guide](https://craftyarncouncil.com/standards/how-to-read-crochet-pattern)
and [PlanetJune's basic techniques](https://www.planetjune.com/blog/amigurumi-help/crochet-basics-right-handed/).
The principle of working around both sides of a foundation chain is described in the author's
[Shiny Happy World oval tutorial](https://www.shinyhappyworld.com/2018/02/how-to-crochet-oval-amigurumi.html).
This implementation's count selection, brim shaping, toe/heel changes and garment composition are
prototype assumptions. Those sources do not validate these generated plans; no complete doll pattern
was copied.
