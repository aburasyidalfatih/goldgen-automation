# Content quality and learning measurement

Automatic and on-demand AI posts require a reviewed caption (minimum 7/10,
recognized requested opening, no reported factual defects) and a reviewed image
(minimum 7/10). Failed review, unavailable review, and exhausted rewrites do not
authorize publication. The posting error records the reason; a scheduled post
can be skipped when all candidates fail. User-authored queued posts keep their
existing workflow.

Caption instructions prioritize useful, qualified field observations. No invented
prices, recovery statistics, personal experience, or future answer promises.
News is excluded from evergreen hook selection without a verified news source.
Limited USGS reference context is provided to caption and image reviewers:

- https://pubs.usgs.gov/gip/prospect1/goldgip.html
- https://pubs.usgs.gov/gip/prospect2/prospectgip.html

These references do not verify every generated assertion. AI review scores are
not audience approval or a substitute for expert geological verification.

A separate worker checks every 15 minutes for missing observations aged 48–50h.
It validates complete reaction/comment counters, retries missing counters, and
inserts each snapshot once. Missing clicks stay null, not zero. Outages lasting
past 50h cause a missing sample, not a mislabeled later observation.

Learning keeps only snapshots actually captured at 48–50h. Relative engagement
uses at least three earlier same-page snapshots in the preceding 14 days,
excluding the target post and future posts. All historical rows remain stored.
If insufficient comparable evidence remains, selection uses existing page
preferences and exploration until new observations mature. A lower available
training sample count after deployment is expected.

The ratio reduces some time-related differences; it does not isolate causal
content quality. Clicks are not reach, unique viewers, or a conversion denominator.

Verification:

    python -m unittest discover -s tests -v
    python scripts/verify_content_quality.py

The second command spends text-model quota but never posts, generates images,
or advances topic rotation. It prints generated captions for inspection.
