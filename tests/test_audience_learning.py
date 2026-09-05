import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from core import database
from core.audience_learning import summarize, performance
from core.layout_experiments import enroll, pending, report
from auto_poster import GoldGenAutoPoster


class RecencyTests(unittest.TestCase):
    def test_decay_cutoff_outlier_and_invalid_observations(self):
        now = datetime.now(timezone.utc)
        def row(age, value):
            return {'timestamp': (now-timedelta(days=age)).isoformat(), 'rel_engagement':value}
        stats = summarize([row(0,1),row(14,3),row(61,900),row(-1,30),row(0,float('nan'))], now)
        self.assertEqual(2, stats['n'])
        self.assertEqual(1.5, stats['effective_n'])
        self.assertAlmostEqual(5/3, stats['avg'])
        self.assertEqual('terbatas',stats['evidence'])
        self.assertEqual(4,summarize([row(0,1000)],now)['avg'])

    def test_recent_outcomes_outweigh_old_equal_sized_history(self):
        now = datetime.now(timezone.utc)
        rows=[{'timestamp':(now-timedelta(days=42)).isoformat(),'rel_engagement':4}]*10
        rows += [{'timestamp':now.isoformat(),'rel_engagement':0.5}]*10
        self.assertLess(summarize(rows,now)['avg'],1)


class ExperimentTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.patcher=patch.object(database,'DB_PATH',Path(self.tmp.name)/'db.sqlite')
        self.patcher.start(); database.init_db()
        conn=database.get_db_connection()
        conn.executemany("INSERT INTO posts(page_id,page_name,status,timestamp) VALUES ('a','A','success',datetime('now','-10 days'))",[()]*8)
        conn.commit();conn.close()
        self.layouts=[{'name':'CROSS-SECTION','composition':'cutaway'}, {'name':'GRID','composition':'grid'}]
        self.topic={'id':1,'headline':'River sampling','layout':'GRID','composition':'grid',
                    'hook_type':'Fact','caption_approved':True,'editor_score':8}

    def tearDown(self):
        self.patcher.stop(); self.tmp.cleanup()

    def test_pair_is_durable_page_isolated_and_retired_layout_not_reused(self):
        first=enroll('a',self.topic,'same caption',self.layouts)
        self.assertIn('experiment_id',first)
        retry=pending('a',self.layouts)
        self.assertEqual(first['experiment_id'],retry['experiment_id'])
        self.assertEqual(first['layout'],retry['layout'])
        self.assertIsNone(pending('b',self.layouts))
        poster=GoldGenAutoPoster.__new__(GoldGenAutoPoster)
        poster.log_post({'page_id':'a','name':'A'},'same caption','img','fb1','success',
                        layout_name=first['layout'],hook_type='Fact',topic_id=1,
                        experiment_id=first['experiment_id'],experiment_arm=0)
        second=pending('a',self.layouts)
        self.assertNotEqual(first['layout'],second['layout'])
        self.assertEqual('same caption',second['approved_caption'])
        self.assertEqual(1,second['experiment_arm'])
        self.assertIsNone(pending('a',self.layouts[:1]))
        self.assertEqual('menunggu pasangan/data',report('a')['pairs'][0]['status'])
        poster.log_post({'page_id':'a','name':'A'},'same caption','img','fb2','success',
                        layout_name=second['layout'],hook_type='Fact',topic_id=1,
                        experiment_id=first['experiment_id'],experiment_arm=1)
        self.assertIsNone(pending('a',self.layouts))
        self.assertIn('tidak sebanding',report('a')['pairs'][0]['status'])  # same-minute posts

    def test_no_experiment_on_manual_content_or_without_review(self):
        topic=dict(self.topic,caption_approved=False)
        self.assertNotIn('experiment_id',enroll('a',topic,'caption',self.layouts))
        self.assertIsNone(pending('a',self.layouts))

    def test_expired_pairs_are_not_replayed(self):
        enroll('a',self.topic,'caption',self.layouts)
        conn=database.get_db_connection()
        conn.execute("UPDATE layout_experiments SET created_at=datetime('now','-8 days')")
        conn.commit();conn.close()
        self.assertIsNone(pending('a',self.layouts))

    def test_evidence_is_page_isolated_and_dashboard_uses_same_weights(self):
        from core.audience_learning import update_rankings
        conn=database.get_db_connection()
        for page,value in [('a',1),('b',4)]:
            for days in [5,4,3,2]:
                pid=f'{page}-{days}'
                conn.execute("INSERT INTO posts(page_id,page_name,status,timestamp,fb_post_id,layout_name) VALUES (?,?,'success',datetime('now',?),?,'GRID')",(page,page,f'-{days} days',pid))
                conn.execute("INSERT INTO engagement_snapshots(fb_post_id,age_hours,likes,comments,captured_at) VALUES (?,48,?,0,datetime('now',?,'+49 hours'))",(pid,value,f'-{days} days'))
        conn.commit();conn.close()
        a=performance('a','layout_name')
        self.assertEqual(1,a['GRID']['n'])
        self.assertAlmostEqual(1,a['GRID']['avg'])
        item=update_rankings([{'layout':'GRID','confident_score':999}], 'a','layout_name','layout')[0]
        self.assertEqual(1,item['relatif'])
        self.assertEqual('terbatas',item['evidence'])


if __name__=='__main__':
    unittest.main()
