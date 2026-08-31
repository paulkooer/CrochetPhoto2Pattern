# Single-Image 3D Reconstruction → Pattern Pipeline (S6, Not Implemented)

[简体中文](3d-reconstruction-design.md) | **English** | [Documentation index](README.md)

> Status: **design document**. This path requires a GPU (roughly 16 GB for TRELLIS or
> 8 GB+ for TripoSR, otherwise slow CPU execution). It is not part of the current product.

## Goal

Turn one or more views into an explicit, inspectable 3D intermediate representation, then
derive crochetable part profiles. The 3D stage must remain optional and may not weaken the
current deterministic geometry, stitch arithmetic, or evidence boundaries.

## Proposed architecture

```text
authorized image(s)
  → segmentation / normalization
  → reconstruction adapter (local model or explicitly selected provider)
  → mesh/field quality checks
  → canonical orientation and scale-free measurements
  → part decomposition and profile sampling
  → StructureGeometry version upgrade
  → existing gauge-aware crochet generator and validator
```

## Non-negotiable boundaries

- A single view remains ambiguous. Reconstructed backs and hidden depth must be labeled as
  model inference, never as measured photo facts.
- Absolute centimetres still come from the user's target size or a documented reference,
  not from an uncalibrated image.
- Remote reconstruction requires explicit consent, provider disclosure, retention rules,
  and the same Base URL/key isolation as vision parsing.
- Meshes and source photos may contain identifiable geometry. They must be local by
  default, excluded from Git/history/share URLs, and removable by the user.
- Low-confidence or invalid reconstruction must fall back to StructureGeometry v2 rather
  than generating plausible but unreviewable geometry.

## Adapter contract

A reconstruction adapter should return versioned metadata, provider/model identity,
input-view provenance, normalized mesh or field output, orientation confidence, coverage,
and explicit warnings. Downstream code should consume a provider-neutral contract.

Quality gates should reject or flag disconnected components, extreme aspect ratios,
missing scale provenance, low foreground coverage, non-finite vertices, implausible volume,
and unsupported topology.

## Pattern projection

The crochet projection should sample cross-sectional circumference along each decomposed
part, smooth noise conservatively, convert the profile through the existing gauge model,
quantize changes to executable six-section operations, and preserve attachment anchors.
Every projected round still passes the current arithmetic and shaping validators.

## Validation plan

1. Synthetic primitives with known profiles for numerical and topology checks.
2. Authorized multi-view objects with repeatable scale references.
3. Comparison against the existing template path, with inference differences exposed.
4. Independent physical trials; mesh similarity alone is not evidence of crochetability.
5. Resource, timeout, malformed-output, privacy, and fallback tests.

## Delivery phases

1. Define the provider-neutral IR and local file/privacy lifecycle.
2. Implement one local adapter behind an experimental flag.
3. Add quality gates and template fallback before any UI exposure.
4. Add multi-view alignment and user correction tools.
5. Run authorized evaluation and independent physical trials before changing product claims.
