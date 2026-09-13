# Stack upgrade, 13 September 2026

The application now targets Python 3.14.7 and Node 24.21.0 LTS.
Docker uses explicit runtime tags. `.python-version` and `.node-version`
document the local runtime contract. Local isolated validation used
`.venv-upgrade` and `.node-runtime`; these directories are excluded from Git
and the Docker build context.

## Dependencies

`requirements.in` holds dependency inputs; `requirements.txt` locks resolved
production versions. `requirements-dev.in` includes the production lock plus
pytest; `requirements-dev.txt` locks the full development environment.
Regenerate using uv pip compile with `--python-version 3.14 --universal`.
Install the development lock in a Python 3.14.7 environment with uv pip sync.

- google-genai 1.73.1 -> 2.23.0
- Pillow 12.2.0 -> 12.3.0
- APScheduler 3.10.4 -> 3.11.3
- Pydantic 2.13.3 -> 2.13.5
- pandas 2.3.3 -> 3.0.5
- numpy 2.4.4 -> 2.5.3
- Legacy google-generativeai and google-ai-generativelanguage removed;
  application code uses google-genai.
- duckduckgo-search replaced with ddgs 9.16.0, including the application import.
- Previously unpinned production dependencies are now pinned in the lock.
- React/react-dom 19.1.1 -> 19.3.0; esbuild 0.25.9 -> 0.28.2;
  font packages -> 5.3.0. Remotion remains 4.0.524, the latest stable version
  returned by the npm registry during the upgrade; all Remotion packages agree.

## Validation

- Python dependency check: 102 installed packages compatible.
- Motion Studio npm ci and build succeeded under Node 24.21.0.
- npm audit: zero reported vulnerabilities (not a Python security audit).
- Isolated Flask login returned HTTP 200, using a temporary database and
  disabling application worker startup during the smoke test.
- SDK image 2K / JSON configuration and APScheduler Asia/Jakarta smoke passed.
- Baseline tests on Python 3.12 and upgraded Python 3.14 both initially showed
  110 passes and the same pre-existing outdated cold-start provenance assertion.
  The assertion now checks the intentional portfolio-prior behavior and parity
  with the dashboard; no production learning behavior was changed for this fix.
- Final Python 3.14 suite: 111 tests and 16 subtests passed. Python compileall
  and git diff whitespace checks passed.

## Remaining release checks

Docker daemon is unavailable locally, so a Linux container build has not been
verified. FFmpeg and Chromium remain distribution-managed packages rather than
claims of latest upstream versions. A local video render attempt was rejected
by automatic approval review due to account usage limits; no bypass was used.
Live Gemini generation and production deployment have not been performed.
The working tree contains pre-existing Motion Studio changes and unpublished
visual-planning changes; those need to be included in a deliberate release
scope rather than staging the entire worktree blindly.
