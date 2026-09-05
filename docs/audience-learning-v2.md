# Recent evidence and layout experiments

Selection of topics, hooks and layouts uses only valid 48–50-hour snapshots
with the existing minimum of three previous same-page comparison posts.
Eligible outcomes are limited to 60 days. Each observation's weight halves
every 14 days. Weighted information mass (sum of weights) enters the posterior
instead of lifetime sample count. Single relative outcomes are capped at 4x
for selection; raw data is preserved. These are configurable design constants
in core/audience_learning.py, not parameters proven optimal by an experiment.

Below five weighted observations, reports explicitly label evidence limited.
Even above that threshold, evidence is observational; no label declares a
causal winner. Historical raw averages remain available for context, while
relative rankings use the same recency calculation as selection.

Scheduled AI posts may initiate a two-post layout experiment when the success
count is divisible by eight, with at least eight successes and no experiment
started in the last eight days. Only reviewed, catalog-backed topics and
compatible active layouts are eligible. Manual content generation is unchanged.

The two layouts run in randomized order. The approved caption, topic and hook
are deliberately identical across the pair. Images are generated separately
and must still pass the image critic. Plans persist across restarts and failed
generation attempts; only successfully logged posts advance the arm. Retired
layouts cannot be replayed. Pending plans expire after seven days.

The report rejects pairs whose caption/topic/hook changed or whose posts were
not 18–30 hours apart and within one hour of the same UTC posting time. Both
outcomes must have valid snapshots. Review at least five comparable pairs for
the same two layouts; no automatic winner promotion is implemented. Random
order reduces order bias but does not randomize viewers. Repeated-caption
fatigue and varying distribution remain limitations of sequential page tests.

Reports:

    python scripts/audience_learning_report.py
    python scripts/learning_report.py

The existing learning API also includes recent_evidence and layout_experiments.
No new posting schedule, Facebook permission or model subscription is required.

Tests:

    python -m unittest discover -s tests -v
