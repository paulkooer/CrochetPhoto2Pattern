# Security Policy

[简体中文](SECURITY.md) | **English**

## Supported versions

| Version | Security fixes |
|---|---|
| `0.2.x` Beta / `main` | Supported |
| `< 0.2` | Not supported |

Beta releases may change data formats, but credential handling, image parsing,
share/import boundaries, and third-party Base URL isolation are always treated as
security-sensitive.

## Report a vulnerability privately

Do not disclose an unpatched vulnerability in a public issue. Do not attach a real API
key, private photo, or other sensitive data.

1. Open the repository's **Security → Advisories** page and select
   **Report a vulnerability**. Private vulnerability reporting is enabled.
2. If that entry is temporarily unavailable, use a private contact method shown on the
   repository owner's GitHub profile and initially send only the impact and a minimal,
   redacted reproducer.
3. Include the affected version/commit, prerequisites, impact, reproduction steps, and a
   possible remediation. Use visibly invalid credentials and self-created or authorized images.

The maintainer will aim to acknowledge a report within seven days and coordinate
disclosure after reproduction and a repair window are established. Do not publish exploit
details before a fix is available.

## Security-sensitive boundaries

- API keys, redacted error output, and custom OpenAI/Anthropic Base URL isolation.
- Malicious or oversized images, EXIF, backup JSON, grid projects, share URLs, and
  Markdown/PDF exports.
- Local SQLite history and its access boundary.
- Prompt/model output bypassing Pydantic, stitch arithmetic, shaping, or attachment checks.
- Dependency, workflow, wheel, and packaged-data supply-chain integrity.

Use the regular issue forms for non-sensitive defects and feature requests.
