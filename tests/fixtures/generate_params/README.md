# Generator output snapshots

These fixtures freeze complete serialized `generate_params` results. The original capture
preceded the shape-dispatch refactor at `60084d09db40d8f5d068980b99c632f736fc5de8`;
`baseline_commit` retains that provenance. Revision `construction-guidance-v1` incorporates
the reviewed eye/stuffing order, skirt test-fit, diameter and purchase-guidance corrections.
Before refreshing, all 102 cases were compared against the original capture: changes were
limited to part notes, assembly prose, hook purchase labels and the new guidance marker.
Every ordered stitch table and numeric output remained unchanged. `baseline_commit` does
not claim the revised fixture is the exact output of that historical commit.

Revision `construction-guidance-v2` carries two reviewed prose changes. (1) The cup-part note
"帽围 N 针 > 头围，不收口可直接佩戴" was printed whatever the counts were; in 31 of the 96
cases that have a hat, the hat rim and the widest head round had the same stitch count. The
claim is removed from the part note, and the hat step of the assembly text now gives both
lengths as estimated from each part's own gauge and says to test-fit. The comparison lives in
the assembly text so that a hat with a fixed gauge stays unchanged when other parts are
regenerated. (2) For attached skirts (36 cases) the orientation sentence of the assembly text
no longer points to an audit label that is not in the repository ("见 F-11"); it tells the
maker how to check which side the reserved loops lie on. Before refreshing, all 102 cases were
compared against revision v1: 99 differ, in one or two fields each, and only in these places:
the note of a `cup` part made by `_cup_part` (96 hats, plus the cup-shaped body of the three
`shape-priority` cases), the hat step of `assembly_instructions` (96 cases) and the
attached-skirt sentence of `assembly_instructions`. Every ordered stitch table and every other
field is unchanged.

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
