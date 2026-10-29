# Frozen synthetic trial fixtures

`trial_legacy_v2/` was produced with the unmodified code at
`5c209f1d6dae5488b86f45e2daac1bd34d1f5c4c`, using `tests.test_app_smoke._mock_result`,
`create_trial_bundle`, `update_trial_bundle` and `encode_trial_bundle`. It covers an empty
draft, a completed record and an incomplete-measurement sidecar. The original ZIP members
were extracted without reformatting: the pattern SHA and sidecar record SHA bind these exact
bytes. These files contain no fingerprint fields.

`trial_unversioned_fingerprint/` was produced with the unmodified code at
`83d7a50fe8fc07eee17c19498828fe18aa830989`, using the same synthetic generator and bundle
constructor. It covers the intermediate, order-dependent fingerprint without an algorithm
version. Its original hash is checked before migration to the versioned identity.

All fixtures use generated patterns, fabricated measurements and anonymous maker labels;
they contain no uploaded photographs, real measurements, third-party instructions or private
user information. They are test evidence, not G3/G4 real-world validation. Do not regenerate
them with the current implementation: that would remove the compatibility test boundary.
