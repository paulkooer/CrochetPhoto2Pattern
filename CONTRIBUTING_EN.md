# Contributing Guide

[简体中文](CONTRIBUTING.md) | **English**

Thank you for improving CrochetPhoto2Pattern. The project is in Beta and prioritizes
changes that improve pattern correctness, evidence quality, reproducibility, privacy,
or maintainability.

## Before you start

- Use the structured issue forms for bugs and feature proposals.
- Do not open a public issue for a vulnerability; follow [SECURITY_EN.md](SECURITY_EN.md).
- Never commit API keys, `.env`, unauthorized personal photos, raw evaluation images,
  identifying trial data, or patterns whose origin or license is unclear.
- For substantial algorithm, format, or product-claim changes, open an issue first and
  describe the problem, evidence, compatibility, and failure modes.

## Local development

Python 3.11–3.14 is supported. The repository defaults to Python 3.12 and `uv.lock`:

```bash
uv sync --locked --extra dev
uv run --locked --extra dev ruff check .
uv run --locked --extra dev pytest -q --cov=app --cov-report=term-missing
uv lock --check
```

For PDF or pose changes, also run the corresponding extra:

```bash
uv sync --locked --extra dev --extra pdf
uv run --locked --extra dev --extra pdf pytest -q
uv sync --locked --extra dev --extra pose
uv run --locked --extra dev --extra pose pytest -q
```

The pose extra is supported only on Python 3.11–3.12 and requires `libEGL.so.1` and
`libGLESv2.so.2` on Linux (`libegl1 libgles2` on Ubuntu).

## Design and evidence constraints

1. **Keep the deterministic core testable.** Model output must enter structured contracts
   and validation gates. It may not bypass stitch arithmetic, input limits, attachment
   checks, or shaping limits.
2. **Separate observation, inference, and user targets.** A single photo provides relative
   observations; absolute size comes from the user. Hidden depth and attachments must not
   be presented as photo measurements.
3. **Do not equate automation with physical testing.** New algorithms need unit/property
   tests. Claims about crochetability, size, materials, or time also need independent
   evidence under [docs/physical-trials.en.md](docs/physical-trials.en.md).
4. **Protect evaluation rights.** Real-photo evaluation must follow the authorization,
   purpose, retention, and hash rules in [docs/evaluation.en.md](docs/evaluation.en.md).
5. **Preserve compatibility.** Version backup/share/pattern/trial format changes, support
   backward reading or document a migration, and update tests and the changelog.

## Pull request requirements

- Keep one independently reviewable objective per pull request.
- Explain user-visible changes, risks, commands, and actual results. Attach redacted
  screenshots for UI changes.
- Add tests for new behavior and a reproducer for defect fixes.
- Update both language entry points when user-visible behavior, installation, privacy,
  data formats, or release gates change.
- Ensure `git diff --check` passes and no generated files or local paths are included.

By submitting a pull request, you confirm that you have the right to contribute the
material and agree that it is released under this repository's MIT License.
