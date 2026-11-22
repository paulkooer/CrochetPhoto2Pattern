# grid-colour area reviewer — working notes (scratch, not the report)

Audited tree: main @ 6c88b7df5d53c18d4c8190288419faeb02cc1b13
Scratch dir: eval_outputs/fable52-system-audit-20261117-fable-review/repro/grid-colour/

## Read so far (in full)
- app/models/grid_pattern.py (688)
- app/ui/tab_grid.py (528)
- app/utils/parade_export.py (467)  -- NB: this is the 3-D CrochetPARADE DSL exporter, NOT a grid exporter
- app/models/colors.py (469)
- app/models/color_design.py (455)
- app/services/color_selection.py (412)
- app/services/color_identity.py (98)
- app/ui/color_editor.py (274)
- app/utils/color_labels.py (44)
- app/theme.py (64)
- app/main.py, app/ui/uploads.py, tests/test_grid_pattern.py

## Candidate hypotheses to test (not findings yet)
H1 C2C handedness: BL start + odd rows "RS ↘", even "WS ↖" == left-handed layout; right-handed maker gets
   mirror image on the face labelled RS. Needs geometric simulator + doc check; ultimately a swatch.
H2 C2C "平行" rows (non-square grid) — header never explains 平行, nor which end increases/decreases.
H3 C2C uses square tiles but the grid is generated with stitch aspect (default 0.75) -> vertical squash.
H4 Tapestry chart: "每行符号从左向右阅读" + no working direction / foundation chain / turning chain.
H5 text chart row label R{n:02d} ; markdown indented code + symbols.
H6 pick_yarn_palette can return 1 colour (n_colors clamps to >=2 but palette may be 1) -> UI behaviour?
H7 grid_width > image width; 1xN / Nx1 images; grid_height min 2 forced.
H8 state: grid_view keys vs other tabs; undo stack; stale downloads; editor widget keys after replace.
H9 generate with aspect from gauge (non-finite / zero gauge) -> aspect option; select_slider value 0.75 not in options?
H10 legend percentages; replace colour leaves 0-cell palette entries in legend/exports ("yarn no longer used").
H11 import project: palette entries unused; duplicate colours; clamped_from.
H12 colour identity: display_colors custom names vs YARN names; whitespace/case variants; hex literal names.
