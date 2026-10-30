# Synthetic trial bundle from the actual 4a19d70 source

`measured.zip` was generated using an isolated `git archive` of the `app/` tree at
`4a19d70f1e8f4000731580e7612e6d45d00ce168`, executed with the repository's locked
Python environment. It is a software compatibility fixture, not a physical trial.
No photographs, real maker identities or measured craft results are included.

Generation inputs and APIs, all taken from that archived version:

1. Call `app.cli.run(build_parser().parse_args(["--parts", "头部,身体,裙子"]))`.
2. Set `color_bands` to white `[0, 0.15)` and black `[0.15, 1]`; regenerate params
   with that version's `CrochetParamsGenerator.generate_params`, passing its
   `ImageAnalysis`, structure and those bands. Other values keep CLI defaults.
3. Call `create_trial_bundle(result, trial_id="audit-4a19d70",
   maker_id="synthetic-maker")`.
4. Call `update_trial_bundle` with the original swatch fields plus `measured=True`,
   `stitches_per_10cm=18`, `rows_per_10cm=24`, and `observation=None`.
5. Save `encode_trial_bundle(bundle)` as `measured.zip`.

Frozen checksums:

- ZIP SHA-256: `47395dd6ef7ed2b0194a3c647cb0b8c9e713da96cfa284771603c34a59babc9e`
- Original `pattern.json` SHA-256: `a287bc76903cee5447f86dbd1e468c6dd9efb93cdc63c9f50ad427b0b746cc39`

ZIP metadata timestamps need not match when regenerating; tests use these exact
frozen bytes to check raw evidence preservation separately from normalized session
identity. Do not regenerate this fixture with the current importer or generator.
