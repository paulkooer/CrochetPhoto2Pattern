# Release candidate evidence

[简体中文](release-process.zh-CN.md) | [System status](system-status.md)

Routine merges use their own CI results. `release-evidence.json` is a receipt for one
selected candidate, and is regenerated only when preparing another candidate. Keep the
existing receipt as historical evidence until then; do not describe it as covering `main`.

1. Select an exact, committed candidate and record its full SHA. Inspect that candidate's
   latest remote checks against `.github/required-checks.json`.
2. Identify the successful pip-audit commit. Use the candidate itself when its audit ran;
   otherwise the audit commit must have the identical Git tree. A dependency update alone
   or a similar application tree is not sufficient. If no matching audit exists, obtain
   one before binding evidence; an older receipt cannot fill the gap.
3. Generate the receipt with explicit SHAs:

   ```bash
   python scripts/bind_release_evidence.py --commit <candidate-sha> --audit-commit <audit-sha>
   ```

   The generator refuses missing, incomplete, or unsuccessful latest checks and a different
   audit tree. Review `commit`, `tree`, `checks_completed_at`, and `run_refs` in the result.
4. Check the saved binding without network access or writes:

   ```bash
   python scripts/bind_release_evidence.py --status --commit <candidate-sha>
   ```

   Exit 0 means that exact commit is covered; exit 1 means it is not. This compares committed
   identities, not uncommitted working files. A later commit that records the receipt is
   distinct from the candidate: use the candidate SHA when checking or reviewing it.
5. Review G3 and G4 independently using the [photo evaluation](evaluation.en.md) and
   [physical-trial](physical-trials.en.md) rules. A matching G1/G2 receipt does not clear
   those gates. Do not create a formal release tag until G1–G4 pass.

The [status pages](system-status.md) link to the receipt and this process. They do not copy
the candidate or audit hashes, run counts, or run ids. A future receipt update should not
require editing those pages or hard-coded test expectations.
