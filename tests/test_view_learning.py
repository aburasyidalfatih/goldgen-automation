import unittest
from datetime import datetime, timedelta, timezone
from core.audience_learning import add_view_outcomes, summarize

class ViewLearningTests(unittest.TestCase):
    def test_views_first_and_window_and_page_isolation(self):
        now = datetime.now(timezone.utc)
        def row(v,e,d=3,p='a'):
            return dict(page_id=p,timestamp=(now-timedelta(days=d)).isoformat(),media_views=v,engagement=e,rel_engagement=999)
        result=add_view_outcomes([row(1000,0,29),row(100,9999),row(100,1),row(99999,1,31),row(99999,1,-1),row(None,9999),row(1,1,p='b')],now)
        self.assertEqual(4,len(result))
        self.assertEqual(4,result[0]['learning_outcome'])
        self.assertGreater(result[0]['learning_outcome'],result[1]['learning_outcome'])
        self.assertGreater(result[1]['learning_outcome'],result[2]['learning_outcome'])
        self.assertEqual(4,result[3]['learning_outcome'])
        self.assertEqual(4,summarize([result[0]],now)['avg'])

    def test_no_views_fallback(self):
        row=dict(page_id='a',timestamp=datetime.now(timezone.utc).isoformat(),rel_engagement=2)
        self.assertEqual(2,add_view_outcomes([row])[0]['learning_outcome'])


class MaturityTests(unittest.TestCase):
    def rows(self, specs, now):
        return [dict(page_id='a', layout_name=l, media_views=v, views_48h=v48,
                     timestamp=(now-timedelta(hours=h)).isoformat()) for l, h, v, v48 in specs]

    def test_young_posts_are_not_judged_yet(self):
        now = datetime.now(timezone.utc)
        result = add_view_outcomes(self.rows([('A', 480, 1400, None), ('A', 240, 1300, None),
                                              ('B', 3, 80, None), ('B', 30, 600, None)], now), now)
        self.assertEqual({'A'}, {r['layout_name'] for r in result})

    def test_same_age_views_beat_lifetime_views(self):
        now = datetime.now(timezone.utc)
        # Old posts gathered more lifetime views, but B was better at 48 hours.
        specs = [('A', 480 - i, 5000, 900) for i in range(3)] + [('B', 60 + i, 1200, 1100) for i in range(3)]
        result = add_view_outcomes(self.rows(specs, now), now)
        best = max(result, key=lambda r: r['learning_outcome'])
        self.assertEqual('B', best['layout_name'])
        self.assertEqual('views_48h', best['view_metric'])
