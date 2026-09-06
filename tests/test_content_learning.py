import unittest
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, Mock

from core.content_quality import caption_issues, require_publishable, ContentQualityError, valid_score, IMAGE_MIN_SCORE
from core import database
from goldgen_service import GoldGenService
from auto_poster import GoldGenAutoPoster

CAPTION = ('An inside bend can be a useful place to sample because slower water may deposit '
           'heavy sediment. Compare small test pans from several spots before deciding where '
           'to work. A black sand streak alone does not establish that gold is present.')
REVIEW = {'score': 8, 'hook_type': 'Fact', 'factual_issues': [], 'feedback': ''}


class QualityTests(unittest.TestCase):
    def test_failed_review_and_nonfinite_scores_are_not_approval(self):
        for score in (None, float('nan'), float('inf'), True, 11, 6):
            self.assertTrue(caption_issues(CAPTION, dict(REVIEW, score=score), 'fact'))
        self.assertEqual([], caption_issues(CAPTION, REVIEW, 'fact'))
        self.assertIsNone(valid_score('nan'))

    def test_unfounded_numbers_promises_and_wrong_hook_blocked(self):
        for text in (' You lose 40% of your haul.', " I'll reveal the answer later.",
                     ' Gold is 19 times denser than quartz.', " You've found the pay streak."):
            self.assertTrue(caption_issues(CAPTION + text, REVIEW, 'fact'))
        self.assertTrue(caption_issues(CAPTION, REVIEW, 'fear'))
        self.assertTrue(caption_issues(CAPTION, {'score': 10, 'hook_type': 'Fact'}, 'fact'))

    def test_image_failures_cannot_publish(self):
        for score in (None, 6, float('nan'), IMAGE_MIN_SCORE):
            require_publishable({'caption_approved': True, 'image_score': score})
        require_publishable({'caption_approved': True, 'image_score': 7})

    def service(self, reviews):
        svc = GoldGenService.__new__(GoldGenService)
        svc.model = 'test'
        svc.client = SimpleNamespace(models=SimpleNamespace(generate_content=Mock(return_value=SimpleNamespace(text=CAPTION))))
        svc._get_latest_insights = Mock(return_value={})
        svc._get_audience_preferences = Mock(return_value=[])
        svc._choose_hook = Mock(return_value=('fact', 'test'))
        svc._editor_is_trustworthy = Mock(return_value=(False, 'insufficient correlation'))
        svc._editor_review = Mock(side_effect=reviews)
        return svc

    @patch('time.sleep')
    def test_rewrite_then_approve_actual_final_draft(self, sleep):
        svc = self.service([dict(REVIEW, score=4), REVIEW])
        topic = {'headline': 'River sampling', 'subtitle': '', 'list_points': ['Sample first']}
        self.assertEqual(CAPTION, svc.generate_caption(topic, 'page'))
        self.assertTrue(topic['caption_approved'])
        self.assertEqual(8, topic['editor_score'])
        self.assertEqual(2, svc._editor_review.call_count)

    @patch('time.sleep')
    def test_all_rejected_drafts_do_not_fall_back_to_unreviewed_content(self, sleep):
        svc = self.service([dict(REVIEW, score=4)] * 3)
        topic = {'headline': 'River sampling', 'subtitle': '', 'list_points': []}
        svc.get_next_topic = Mock(return_value=topic)
        poster = GoldGenAutoPoster.__new__(GoldGenAutoPoster)
        poster.goldgen = svc
        with self.assertRaises(ContentQualityError):
            poster.generate_content('page')
        self.assertFalse(topic['caption_approved'])


class LearningDataTests(unittest.TestCase):
    def test_snapshot_collection_retries_missing_data_and_is_idempotent(self):
        from comment_analyzer import CommentAnalyzer
        with tempfile.TemporaryDirectory() as tmp, patch.object(database, 'DB_PATH', Path(tmp)/'test.db'):
            database.init_db()
            conn = database.get_db_connection()
            conn.execute("INSERT INTO posts(timestamp,page_id,page_name,fb_post_id,status) VALUES (datetime('now','-49 hours'),'a','A','p','success')")
            conn.commit(); conn.close()
            analyzer = CommentAnalyzer.__new__(CommentAnalyzer)
            analyzer.fanspages = [{'page_id': 'a', 'access_token': 'test'}]
            analyzer.fetch_post_clicks = Mock(return_value=None)
            good = {k: {'summary': {'total_count': 2}} for k in ('like_count','love','haha','wow','comments')}
            response = Mock()
            response.json.side_effect = [{'error': 'unavailable'}, good]
            with patch('comment_analyzer.requests.get', return_value=response) as get:
                analyzer.capture_due_snapshots()
                analyzer.capture_due_snapshots()
                analyzer.capture_due_snapshots()
                self.assertEqual(2, get.call_count)
            conn = database.get_db_connection()
            row = conn.execute('SELECT * FROM engagement_snapshots').fetchone()
            self.assertEqual(8, row['likes'])
            self.assertEqual(2, row['comments'])
            self.assertIsNone(row['clicks'])
            conn.close()

    def test_migration_capture_age_prior_peers_and_page_isolation(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(database, 'DB_PATH', Path(tmp)/'test.db'):
            database.init_db()
            conn = database.get_db_connection()
            def add(pid, day, engagement, captured_day, page='a'):
                stamp = f'2026-08-{day:02d}T00:00:00+07:00'
                captured = f'2026-08-{captured_day:02d} 17:30:00'
                conn.execute("INSERT INTO posts(timestamp,page_id,page_name,fb_post_id,status) VALUES (?,?,?,?,'success')", (stamp,page,page,pid))
                conn.execute('INSERT INTO engagement_snapshots(fb_post_id,age_hours,likes,comments,captured_at) VALUES (?,48,?,0,?)', (pid,engagement,captured))
            # 00:00 WIB = previous day 17:00 UTC: captured_day=day+1 gives 48.5h.
            for day in (1,2,3): add(str(day),day,10,day+1)
            add('target',4,20,5)
            add('future',5,9000,6)
            add('other-page',3,8000,4,'b')
            add('late',6,100,8)  # 72.5h, not a fair snapshot
            conn.commit()
            row=conn.execute("SELECT * FROM post_engagement WHERE fb_post_id='target'").fetchone()
            self.assertEqual(10, row['page_window_mean'])
            self.assertEqual(2, row['rel_engagement'])
            self.assertIsNone(conn.execute("SELECT rel_engagement FROM post_engagement WHERE fb_post_id='1'").fetchone()[0])
            self.assertIsNone(conn.execute("SELECT * FROM post_engagement WHERE fb_post_id='late'").fetchone())
            conn.close()
            database.init_db()  # repeat migration preserves observations
            conn=database.get_db_connection()
            self.assertEqual(7,conn.execute('SELECT count(*) FROM posts').fetchone()[0])
            conn.close()


if __name__ == '__main__':
    unittest.main()
