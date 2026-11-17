# Generator output snapshots

These fixtures freeze complete serialized `generate_params` results. The original capture
preceded the shape-dispatch refactor at `60084d09db40d8f5d068980b99c632f736fc5de8`;
`baseline_commit` retains that provenance. Revision `construction-guidance-v1` incorporates
the reviewed eye/stuffing order, skirt test-fit, diameter and purchase-guidance corrections.
Before refreshing, all 102 cases were compared against the original capture: changes were
limited to part notes, assembly prose, hook purchase labels and the new guidance marker.
Every ordered stitch table and numeric output remained unchanged. `baseline_commit` does
not claim the revised fixture is the exact output of that historical commit.

There are 102 cases: all 72 combinations of three gauge presets, three sphere modes,
one-piece on/off, ring/attached skirts, and ruffled/plain hems; nine exact neck openings;
nine profile-and-color cases; and twelve independent-gauge, dispatch-priority, empty,
and legacy-fallback cases. Empty structures retain their public generation failure;
the other 99 cases retain complete successful results. All output fields, notes, materials, assembly text, quantities,
derived metadata, and ordered round lists are retained.

The three gzip files contain ordinary indented UTF-8 JSON. Compression keeps repeated
pattern prose out of repository bulk; it does not replace full outputs with hashes.
Inspect a fixture with `gzip -dc tests/fixtures/generate_params/classic.json.gz`.

Tests only read fixtures. For an intentional behavior change, inspect the difference before
explicitly refreshing with `python -m tests.test_generator_output_snapshots --write`.
The compressed headers omit filenames and timestamps so refreshes are deterministic.
