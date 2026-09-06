import unittest
from core.audience_learning import add_view_outcomes


class ViewLearningTests(unittest.TestCase):
    def test_high_views_reward_low_interactions_without_future_or_other_page_leak(self):
        rows = [dict(page_id='a', timestamp=f'2026-09-0{i}T00:00:00+00:00',
                     media_views=100, rel_engagement=1) for i in (1, 2, 3)]
        target = dict(page_id='a', timestamp='2026-09-04T00:00:00+00:00',
                      media_views=1000, rel_engagement=0.1)
        rows += [target, dict(page_id='b', timestamp=rows[0]['timestamp'], media_views=99999),
                 dict(page_id='a', timestamp='2026-09-05T00:00:00+00:00', media_views=99999)]
        add_view_outcomes(rows)
        self.assertEqual(10, target['learning_outcome'])
        self.assertNotIn('rel_views', rows[0])

    def test_missing_views_keeps_engagement(self):
        row = dict(page_id='a', timestamp='2026-09-04T00:00:00', rel_engagement=2)
        self.assertEqual(2, add_view_outcomes([row])[0]['learning_outcome'])
