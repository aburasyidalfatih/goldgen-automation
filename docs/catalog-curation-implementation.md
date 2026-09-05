# Catalog curation from US prospecting research

Policy: core/topic_catalog.py; research: riset-topik-audiens-amerika-2026-09-05.md.

On service initialization, load_catalog applies an idempotent policy to the
persistent topics.json. Existing records keep their IDs, order and headlines.
New editorial_angle and corrected points guide caption and image generation.
Exact duplicate headlines and creator-marketing contamination are retired,
not deleted. The selection list excludes them, while the complete source list
is retained for subsequent dynamic-topic saves.

Nine unique legacy headlines receive corrected educational material. Two
research hypotheses are added with stable curation keys: checking sluice output
and practicing panning in a catch tub. They are not labeled proven audience
favorites and are excluded from new layout experiments while experimental_topic
is true, so a new topic is not simultaneously introduced as a layout test.

Production IDs and repository IDs are not equivalent. Match revisions by
headline; never replace the production catalog with the repository file.
Reserved addition IDs are changed if already occupied, and reruns identify
additions by curation_key instead of assigning duplicates.

Before a changed persistent catalog is replaced, a timestamped sibling backup
is created. Replacement is atomic under the topic-catalog process lock.
Legacy rotation positions are mapped via IDs to the active list. New rotation
state carries catalog_ids so later catalog revisions preserve topic identity.
Database posts are not rewritten or removed.

VPS dry-run: 140 source records -> 142 stored / 136 active. Retired: 76, 87,
88, 95, 103, 181. Two duplicates and four off-topic entries. Addition IDs in
this catalog: 10001 and 10002. This is a preview until the new release runs.

Run regression tests with: python -m unittest discover -s tests -v.
