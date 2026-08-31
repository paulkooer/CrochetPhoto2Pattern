# Processing Flow

[简体中文](flow.md) | **English** | [Documentation index](README.md)

## Five-stage pipeline

```text
photo upload
   ↓
1. image preprocessing (Pillow resize, orientation, RGB conversion)
   ↓
2. provider-independent geometric observation + semantic parsing
   geometry: versioned width profile, flare, confidence, single-view limitations
   semantics: body type, parts, features, pose, relative proportions, difficulty
   ↓
3. target-size transform
   no absolute centimetres are inferred from a single photo; relative proportions are
   scaled to the user's selected finished height
   ↓
4. part structure design
   StructureGeometry v2 template skeleton, not a reconstructed 3D mesh:
   shape/ratio, normalized position, Euler rotation, instances, mirrored groups,
   attachment anchors, logical quantity, and template-inference confidence
   ↓
5. crochet parameter generation
   per-logical-part rounds, stitch counts, increases/decreases, materials, assembly
   shaping uses ΔN = 2π × row height / stitch width and executable six-section topology;
   V/A source-stitch constraints prevent impossible instructions
   ↓
deterministic validation → JSON/UI → corrections → downloads/backups
```

Entity quantities drive total stitches, materials, time, and progress. StructureGeometry
v2 attachments are projected into `assembly_plan`; legacy name-based assembly is used
only when an old structure has no attachment graph.

## Main modules

| Path | Responsibility |
|---|---|
| `app/main.py` | thin Streamlit entry point and tab dispatch |
| `app/ui/` | sidebar, photo/manual/grid tabs, result rendering, progress, corrections, downloads |
| `app/utils/images.py` | defensive loading, size limits, EXIF orientation, transparent-image handling |
| `app/models/image_parser.py` | provider calls, structured parsing, local/mock fallbacks |
| `app/models/local_vision.py` | face proportions and silhouette profile without an LLM |
| `app/models/sizing.py` | relative observation to user target dimensions, with provenance metadata |
| `app/models/geometry.py` | shared observation IR and StructureGeometry v2 graph |
| `app/models/color_design.py` | longitudinal photo colors to part/round color bands |
| `app/models/structure_designer.py` | semantic parts to versioned template geometry |
| `app/models/gauge.py` | gauge, stitch geometry, and shaping-limit source of truth |
| `app/models/crochet_params.py` | sphere/cylinder/profile rounds and six-section bridges |
| `app/models/grid_pattern.py` | cropped, editable, versioned 2D grid projects |
| `app/models/colors.py` | yarn palette and CIEDE2000 distance |
| `app/models/subject.py` | shared subject mask with defensive fallback |
| `app/models/pose.py` | optional measured pose spans with prior fallback |
| `app/models/validator.py` | stitch arithmetic and active-gauge shaping gates |
| `app/models/ring_chart.py` | top-view SVG ring chart |
| `app/models/orchestrator.py` | pipeline coordination |
| `app/utils/history.py` | local SQLite history |
| `app/utils/pdf_export.py` | optional PDF export |
| `app/evaluation.py` | authorized-photo evaluation and reports |
| `app/trials.py` | physical-trial records, holdout checks, and calibration candidates |

## Single-image limitations

- Back thickness and hidden connections are inferred, not observed.
- Position, rotation, and attachment fields are explicit template priors, not measured depth.
- Absolute head diameter/height cannot be measured from one photo; the user selects the target.
- Users may edit dimensions and StructureGeometry v2 before local regeneration.
- Advanced structure regeneration does not make another AI call.

## Roadmap

1. Multi-view front/side/back input for better structural inference.
2. A reusable body-template library.
3. More stitch families and spiral/joined-round modes.
4. Server sync or cross-device history migration.
5. Standard crochet-symbol diagrams beyond the current top-view ring approximation.
