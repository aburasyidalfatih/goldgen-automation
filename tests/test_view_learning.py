import unittest
from datetime import datetime, timedelta, timezone
from core.audience_learning import add_view_outcomes, summarize

class ViewLearningTests(unittest.TestCase):
    def test_views_first_and_window_and_page_isolation(self):
        now = datetime.now(timezone.utc)
        def row(v,e,d=1,p='a'):
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
