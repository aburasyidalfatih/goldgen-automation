# Upgrade audit — 13 September 2026

## Follow-up, 14 September

- Render defect identified: Remotion premount measured the content at width 0,
  height 3548, so fitting cached a scale near 0.39. The content now has an
  explicit composition-relative width and remeasures on resize/font readiness.
  Build and one-second render passed; the resulting middle frame was inspected
  and now shows full-width content. Diagnostic logging was removed.
- Shared `core/meta_api.py` now supplies configurable Graph API v26.0 across
  image publishing, comments, collectors, manual sync, and video publishing.
  Read-only live checks of page identity, posts, post views, and comments on all
  five configured pages returned HTTP 200 with response version v26.0 (20 checks).
  Publishing has not been tested by sending a public post or comment.
- Python suite after fixes: 111 tests and 16 subtests passed; URL interpolation
  checks and diff checks passed.
- Isolated Linux build upload was rejected by automatic approval review, which
  requires explicit permission to export the build context to SchoolProNew.
  No upload/build/deployment occurred. The locally prepared archive inventory
  is `upgrade-build-manifest.json`; it excludes config.json, secrets, databases,
  logs, CSV files, generated media, node_modules, and local runtimes.

The original findings below are retained as audit history; items 1 and the
version-scattering part of item 2 have been addressed as described above.

Release assessment: not yet ready for an unconditional production release.

## Verified

- Python dependency compatibility check passed for 102 packages.
- pip-audit on the production lock reported no known vulnerabilities;
  machine-readable result is in `python-audit.json`.
- Node 24.21.0 / React 19.3.0 Motion Studio build passed; npm audit reported zero
  vulnerabilities in the preceding upgrade validation.
- Local Remotion render now completes: `motion_studio/upgrade-smoke/output.mp4`.
  The smoke input is a one-second cutaway scene at quarter video scale. This
  verifies encoder/browser execution, not complete movie quality.
- Middle-frame PNG inspected visually, not merely checked for file existence.

## Findings and limits

1. **Motion composition quality fails visual inspection.** The primary content
   occupies a small top-left region while most of the frame is empty. See
   `motion_studio/upgrade-smoke/scene-1-middle.png`. `src/film.jsx` contains
   dynamic scrollHeight-based fitting, but its causal role has not been proven.
   Compare the same fixture before/after dependency changes and inspect computed
   dimensions before altering layout logic. Do not claim render quality passed.
2. **Meta API versions are scattered.** Image posting, comments, manual sync,
   and metric collection use hardcoded v18.0, while video publishing and another
   controller use v21.0. Version migration needs endpoint-specific contract
   checks. The official version documentation returned HTTP 429 during this
   audit; no unsupported inference that every existing call is broken is made.
3. **Linux container build remains unverified.** Local Docker daemon is absent.
   Windows Python/Chromium success is not proof of Linux wheel availability,
   Debian Chromium/FFmpeg compatibility, or successful image startup.
4. **Live integrations remain untested for this upgrade.** No Gemini generation,
   Facebook publishing, comment sending, or production redeployment was performed.
   Unit/smoke checks do not certify these external contracts.

No production data or configuration was changed for this audit. The existing
mixed worktree should not be released wholesale without resolving these checks.
