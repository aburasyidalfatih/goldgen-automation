import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from core import database
from core.views_collector import collect_views


class CurrentViewsTests(unittest.TestCase):
    def test_unique_zero_and_share_response(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(database,'DB_PATH',Path(tmp)/'test.db'):
            database.init_db()
            c=database.get_db_connection()
            c.execute("INSERT INTO posts(page_id,status,fb_post_id,timestamp) VALUES ('a','success','p',datetime('now','-3 days'))")
            c.commit(); c.close()
            def response(payload):
                result=Mock(); result.json.return_value=payload; return result
            replies=[response({'data':[{'name':'post_media_view','values':[{'value':100}]}]}),
                     response({'data':[{'name':'post_total_media_view_unique','values':[{'value':0}]}]}),
                     response({'shares':{'count':7}})]
            with patch('core.views_collector.requests.get',side_effect=replies):
                collect_views([{'page_id':'a','access_token':'test'}])
            c=database.get_db_connection()
            row=c.execute('SELECT * FROM post_views_current').fetchone()
            self.assertEqual(row['shares'],7)
            self.assertIsNone(row['unique_viewers'])
            self.assertEqual(c.execute('SELECT unique_status FROM post_metric_status').fetchone()[0],'inconsistent_zero')
            c.close()

    def test_old_post_refresh_failure_retains_value_and_retries(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(database,'DB_PATH',Path(tmp)/'test.db'):
            database.init_db()
            c=database.get_db_connection()
            c.execute("INSERT INTO posts(page_id,page_name,status,fb_post_id,timestamp) VALUES ('a','A','success','p',datetime('now','-20 days'))")
            c.commit();c.close()
            good=Mock();good.json.return_value={'data':[{'name':'post_media_view','values':[{'value':1234}]}]}
            with patch('core.views_collector.requests.get',return_value=good) as get:
                self.assertEqual(1,collect_views([{'page_id':'a','access_token':'test'}])['updated'])
                self.assertEqual(0,collect_views([{'page_id':'a','access_token':'test'}])['updated'])
                self.assertEqual(3,get.call_count)
            c=database.get_db_connection();c.execute("UPDATE post_views_current SET attempted_at=datetime('now','-2 hours')");c.commit();c.close()
            with patch('core.views_collector.requests.get',side_effect=RuntimeError('unavailable')):
                self.assertEqual(1,collect_views([{'page_id':'a','access_token':'test'}])['failed'])
            c=database.get_db_connection();r=c.execute('SELECT * FROM post_views_current').fetchone()
            self.assertEqual(1234,r['media_views']);self.assertIn('unavailable',r['error'])
            self.assertEqual(0,c.execute('SELECT count(*) FROM engagement_snapshots').fetchone()[0]);c.close()
