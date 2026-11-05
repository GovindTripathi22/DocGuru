# Security policy

## Supported versions

Security fixes are made against the current default branch. No release support window has been declared yet.

## Reporting a vulnerability

Do not include credentials, private documents, or exploit details in a public issue. Use the repository host's private vulnerability reporting feature when available. If that feature is unavailable, contact the project maintainer privately and include a short impact summary and steps to reproduce. A contact address has not been configured in this repository.

## Current safeguards

- Uploads have size, package-content, compression-ratio, page-count, and macro/encryption checks.
- API keys and signed session identifiers protect backend access; per-session rate limits and artifact ownership checks limit cross-session access.
- User content is not included in logs by default. Generated files are stored under the configured data directories and removed by retention cleanup.
- Image downloads require HTTPS and allowlisted hosts, reject redirects, and enforce byte and image-dimension limits.
- The Next.js BFF keeps backend credentials and session signing material on the server.

Safeguards reduce risk but do not replace infrastructure controls, dependency updates, or review of generated content.
