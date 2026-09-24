# Generation reliability repair

The generation pipeline now records redacted provider outcomes in
`generation_events`, retains rotating process logs in the persistent logs volume,
and binds review approval to page, image SHA-256 and caption SHA-256. Unknown,
low-scoring and fallback images cannot pass any publication path. A failed image
review can be retried using the saved artwork. Legacy failed posts without a
matching review must be generated again; they are not silently approved.

Scheduled generation has a durable lease and at most three attempts per hour,
15 minutes apart. Only successful publication updates `last_post_time`. A send
with an uncertain result is held instead of automatically repeated. HTTPS Date
checks before scheduled generation/publication stop work if clock skew exceeds
two minutes or neither time endpoint can be reached. DNS failures remain transient
generation failures, never a reason to replace page credentials automatically.

Layout experiments stop after two failures, including legacy failures matched by
page, exact caption and experiment creation time. One failure imposes a six-hour
pause. This releases the Kedai Digital experiment stuck since 21 September.

Catalog drawing instructions are separated from printable copy. The final image
prompt and image reviewer share the approved copy, and the final prompt is
checked before requesting image generation. Negative guardrails no longer match
the positive-claim substring filter.

## Deployment verification

- Back up the SQLite database before deploying. New tables and queue columns are
  additive and initialized on startup; stored error messages are redacted in place.
- Confirm `generation_events`, `image_reviews`, and `posting_attempts` exist.
- Check host NTP synchronization and both DNS resolutions from the container.
- Confirm `clock_ready()` returns true and the `/app/logs` volume receives logs.
- Observe the next scheduled cycle: approval must exist before publication;
  provider HTTP 200 alone is not generation success.
- Do not bulk retry historical failed posts. Fallbacks need regeneration; uncertain
  sends require checking the actual Facebook result first.
- Two Miners 24 records (13517 and 13518) were written with a clock seven hours
  ahead during the 24 September boot. Preserve their historical timestamps unless
  applying a separately audited repair using the system journal evidence. This
  release prevents recurrence rather than guessing timestamps during migration.

Local tests use mocked provider responses and temporary databases. Passing tests
does not prove live Gemini generation or Facebook delivery.
