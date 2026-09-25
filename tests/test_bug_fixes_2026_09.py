"""Regression tests for the September 2026 bug sweep."""
import base64
import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

from flask import Flask

from core import database
from core.generation_reliability import UncertainSend

WIB = timezone(timedelta(hours=7))
PNG_1PX = ('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk'
           '+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==')


class DbTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.db = patch.object(database, 'DB_PATH', self.root / 'test.db')
        self.db.start()
        database.init_db()

    def tearDown(self):
        self.db.stop()
        self.tmp.cleanup()

    def query(self, sql, params=()):
        conn = database.get_db_connection()
        try:
            return conn.execute(sql, params).fetchall()
        finally:
            conn.close()

    def app(self):
        from controllers import routes
        app = Flask(__name__)
        app.secret_key = 'test'
        app.register_blueprint(routes.bp)
        return app


class QueueTimezoneTests(DbTestCase):
    def test_dashboard_queue_is_due_immediately(self):
        client = self.app().test_client()
        with client.session_transaction() as session:
            session['authenticated'] = True
        with patch('controllers.routes.IMAGES_DIR', self.root):
            response = client.post('/api/queue-post', json={
                'caption': 'caption', 'page_ids': ['a'],
                'image_data': 'data:image/png;base64,' + PNG_1PX})
        self.assertEqual(200, response.status_code)

        from auto_poster import GoldGenAutoPoster
        poster = GoldGenAutoPoster.__new__(GoldGenAutoPoster)
        poster.fanspages = [{'page_id': 'a', 'name': 'A', 'access_token': 't'}]
        poster._review_queued_image = Mock()
        poster.post_to_facebook = Mock(return_value=('1_2', None))
        poster.log_post = Mock()
        poster.update_last_post_time = Mock()
        poster.process_queue()
        poster.post_to_facebook.assert_called_once()
        self.assertEqual('posted', self.query('SELECT status FROM post_queue')[0][0])

    def test_two_uploads_in_the_same_second_do_not_share_a_file(self):
        client = self.app().test_client()
        with client.session_transaction() as session:
            session['authenticated'] = True
        with patch('controllers.routes.IMAGES_DIR', self.root):
            paths = {client.post('/api/queue-post', json={
                'caption': 'c', 'page_ids': ['a'],
                'image_data': 'data:image/png;base64,' + PNG_1PX}).json['image_path'] for _ in range(2)}
        self.assertEqual(2, len(paths))

    def test_legacy_naive_wib_queue_rows_are_migrated(self):
        local = (datetime.now(WIB) - timedelta(minutes=5)).replace(tzinfo=None).isoformat()
        conn = database.get_db_connection()
        with conn:
            conn.execute("INSERT INTO post_queue(page_id,content,image_path,status,scheduled_time,created_at) "
                         "VALUES('a','c','x.png','pending',?,?)", (local, local))
        conn.close()
        database.init_db()
        database.init_db()  # idempotent
        row = self.query("SELECT scheduled_time, datetime(scheduled_time) <= datetime('now') FROM post_queue")[0]
        self.assertEqual(local + '+07:00', row[0])
        self.assertEqual(1, row[1])

    def test_definite_queue_rejection_is_retried_later(self):
        conn = database.get_db_connection()
        with conn:
            conn.execute("INSERT INTO post_queue(page_id,content,image_path,status,scheduled_time) "
                         "VALUES('a','c','x.png','pending',datetime('now','-1 minute'))")
        conn.close()
        from auto_poster import GoldGenAutoPoster
        poster = GoldGenAutoPoster.__new__(GoldGenAutoPoster)
        poster.fanspages = [{'page_id': 'a', 'name': 'A'}]
        poster._review_queued_image = Mock()
        poster.post_to_facebook = Mock(return_value=(None, 'ERROR FACEBOOK: x'))
        poster.log_post = Mock()
        poster.process_queue()
        self.assertEqual(('pending', 1), tuple(self.query('SELECT status, attempts FROM post_queue')[0]))

    def test_uncertain_queue_send_is_held(self):
        conn = database.get_db_connection()
        with conn:
            conn.execute("INSERT INTO post_queue(page_id,content,image_path,status,scheduled_time) "
                         "VALUES('a','c','x.png','pending',datetime('now','-1 minute'))")
        conn.close()
        from auto_poster import GoldGenAutoPoster
        poster = GoldGenAutoPoster.__new__(GoldGenAutoPoster)
        poster.fanspages = [{'page_id': 'a', 'name': 'A'}]
        poster._review_queued_image = Mock()
        poster.post_to_facebook = Mock(side_effect=UncertainSend('timeout'))
        poster.process_queue()
        self.assertEqual('uncertain', self.query('SELECT status FROM post_queue')[0][0])


class ScheduledSlotTests(DbTestCase):
    def run_cycle(self, send):
        from auto_poster import GoldGenAutoPoster
        poster = GoldGenAutoPoster.__new__(GoldGenAutoPoster)
        poster.fanspages = [{'page_id': 'a', 'name': 'A', 'access_token': 't', 'schedule_hours': [1]}]
        poster.goldgen = MagicMock(state_file=self.root / 'state.json', topics=[{}])
        poster.process_queue = Mock()
        poster.should_post = Mock(return_value=True)
        poster.validate_token = Mock(return_value=(True, None))
        poster._resume_pending_review = Mock(return_value=None)
        poster.generate_content = Mock(return_value=('caption', {'headline': 'H', 'layout': 'L'}))
        poster.generate_image = Mock(return_value=self.root / 'img.png')
        poster.post_to_facebook = send
        poster.log_post = Mock()
        poster.update_last_post_time = Mock()
        with patch('core.generation_reliability.clock_ready', return_value=True), \
             patch('core.generation_reliability.save_review'), \
             patch('core.content_quality.require_publishable'), \
             patch('core.promo_comment.send_pending_promo_comments'), \
             patch('auto_poster.CommentAnalyzer'), \
             patch('auto_poster.BASE_DIR', self.root):
            poster.run()
        return self.query('SELECT status, attempts FROM posting_attempts')[0]

    def test_definite_facebook_rejection_leaves_slot_retryable(self):
        status, attempts = self.run_cycle(Mock(return_value=(None, 'IZIN KURANG')))
        self.assertEqual(('failed', 1), (status, attempts))

    def test_uncertain_send_holds_slot(self):
        status, _ = self.run_cycle(Mock(side_effect=UncertainSend('timeout')))
        self.assertEqual('uncertain', status)

    def test_error_before_sending_leaves_slot_retryable(self):
        status, _ = self.run_cycle(Mock(side_effect=ValueError('token check exploded')))
        self.assertEqual('failed', status)

    def test_success_is_kept_even_if_logging_fails(self):
        from auto_poster import GoldGenAutoPoster
        with patch.object(GoldGenAutoPoster, 'update_last_post_time', side_effect=OSError('disk')):
            status, _ = self.run_cycle(Mock(return_value=('1_2', None)))
        self.assertEqual('success', status)


class AutoReplySpamTests(DbTestCase):
    SPAM = 'slot gacor hari ini, daftar sekarang'

    def replier(self, comments):
        from auto_reply_comments import CommentReplier
        replier = CommentReplier.__new__(CommentReplier)
        replier.fanspages = [{'page_id': 'p', 'name': 'P', 'access_token': 't'}]
        replier._unsupported_posts = set()
        replier.validate_token = Mock(return_value=(True, None))
        replier.get_recent_posts = Mock(return_value=[{'id': 'p_1', 'message': 'post'}])
        replier.get_comments = Mock(return_value=comments)
        replier.gemini_api_key = 'k'
        replier.text_model = 'text'
        replier.hide_comment = Mock(return_value=True)
        replier.post_reply = Mock(return_value=True)
        replier._human_delay = Mock()
        replier._should_skip_comment_naturally = Mock(return_value=False)
        replier._download_image_as_base64 = Mock(return_value=None)
        replier.get_latest_insights = Mock(return_value={})
        return replier

    def test_promotional_spam_is_hidden_once_without_gemini(self):
        comments = [{'id': 'c1', 'from': {'id': 'u', 'name': 'U'}, 'message': self.SPAM}]
        replier = self.replier(comments)
        with patch('auto_reply_comments.requests.post') as gemini:
            replier.process_comments()
            replier.process_comments()
        gemini.assert_not_called()
        replier.hide_comment.assert_called_once()
        replier.post_reply.assert_not_called()
        self.assertEqual('[HIDDEN SPAM]', self.query('SELECT reply_text FROM replied_comments')[0][0])

    def test_refused_reply_is_not_reprocessed_every_cycle(self):
        comments = [{'id': 'c1', 'from': {'id': 'u', 'name': 'U'}, 'message': 'hello there'}]
        replier = self.replier(comments)
        replier.generate_reply = Mock(return_value=None)
        replier.process_comments()
        replier.process_comments()
        replier.generate_reply.assert_called_once()
        replier.post_reply.assert_not_called()

    def test_model_spam_verdict_shares_the_reply_call(self):
        comments = [{'id': 'c1', 'from': {'id': 'u', 'name': 'U'}, 'message': 'claim your free crypto now'}]
        replier = self.replier(comments)
        answer = MagicMock()
        answer.json.return_value = {'candidates': [{'content': {'parts': [{'text': '[[SPAM]]'}]}}]}
        with patch('auto_reply_comments.requests.post', return_value=answer) as gemini:
            replier.process_comments()
            replier.process_comments()
        self.assertEqual(1, gemini.call_count)
        replier.hide_comment.assert_called_once()
        replier.post_reply.assert_not_called()

    def test_normal_comment_needs_one_gemini_call(self):
        comments = [{'id': 'c1', 'from': {'id': 'u', 'name': 'U'}, 'message': 'where do I start panning?'}]
        replier = self.replier(comments)
        answer = MagicMock()
        answer.json.return_value = {'candidates': [{'content': {'parts': [{'text': 'Try the inside bends.'}]}}]}
        with patch('auto_reply_comments.requests.post', return_value=answer) as gemini:
            replier.process_comments()
        self.assertEqual(1, gemini.call_count)
        replier.post_reply.assert_called_once_with('c1', 'Try the inside bends.', 't')

    def test_failed_hide_is_recorded_and_not_retried(self):
        comments = [{'id': 'c1', 'from': {'id': 'u', 'name': 'U'}, 'message': self.SPAM}]
        replier = self.replier(comments)
        replier.hide_comment = Mock(return_value=False)
        replier.process_comments()
        replier.process_comments()
        replier.hide_comment.assert_called_once()
        self.assertEqual('[SPAM NOT HIDDEN]', self.query('SELECT reply_text FROM replied_comments')[0][0])

    def test_photo_of_already_replied_comment_is_not_downloaded(self):
        comments = [{'id': 'c1', 'from': {'id': 'u', 'name': 'U'}, 'message': 'look',
                     'attachment': {'type': 'photo', 'media': {'image': {'src': 'https://x/img.jpg'}}}}]
        replier = self.replier(comments)
        replier.save_replied_comment('c1', 'p_1', 'U', 'look', 'done', user_id='u')
        replier.process_comments()
        replier._download_image_as_base64.assert_not_called()


class DashboardTests(DbTestCase):
    def client(self, authenticated=True):
        client = self.app().test_client()
        if authenticated:
            with client.session_transaction() as session:
                session['authenticated'] = True
        return client

    def test_html_pages_redirect_to_login(self):
        client = self.client(authenticated=False)
        for path in ('/dashboard', '/analytics', '/schedule-insight', '/motion-studio'):
            response = client.get(path)
            self.assertEqual(302, response.status_code, path)
            self.assertTrue(response.headers['Location'].endswith('/login'), path)
        self.assertEqual(401, client.get('/api/stats').status_code)
        self.assertEqual(401, client.get('/api/images/x.png').status_code)

    def test_login_is_locked_after_repeated_wrong_pins(self):
        from controllers import routes
        routes._login_failures.clear()
        client = self.client(authenticated=False)
        with patch('controllers.routes.DASHBOARD_PIN', '123456'):
            for _ in range(routes.LOGIN_MAX_FAILURES):
                self.assertEqual(401, client.post('/api/auth/login', json={'pin': '000000'}).status_code)
            self.assertEqual(429, client.post('/api/auth/login', json={'pin': '123456'}).status_code)
            routes._login_failures.clear()
            self.assertEqual(200, client.post('/api/auth/login', json={'pin': '123456'}).status_code)

    def test_post_now_reports_busy_poster(self):
        from core.locks import ProcessLock
        with patch('core.locks.DATA_DIR', self.root):
            with ProcessLock('poster') as held:
                self.assertTrue(held.acquired)
                response = self.client().post('/api/trigger-post', json={'page_id': 'a'})
        self.assertEqual(409, response.status_code)
        self.assertFalse(response.json['success'])

    def test_post_now_releases_lock_when_done(self):
        from core.locks import ProcessLock
        with patch('core.locks.DATA_DIR', self.root), \
             patch('auto_poster.GoldGenAutoPoster') as poster_cls:
            response = self.client().post('/api/trigger-post', json={'page_id': 'a'})
            self.assertEqual(200, response.status_code)
            import time
            released = False
            for _ in range(50):
                with ProcessLock('poster') as lock:
                    released = lock.acquired
                if released:
                    break
                time.sleep(0.05)
            self.assertTrue(released)
            poster_cls.return_value.force_post.assert_called_once_with('a')

    def test_posts_limit_and_page_id(self):
        conn = database.get_db_connection()
        with conn:
            for i in range(30):
                conn.execute("INSERT INTO posts(page_id,page_name,status,timestamp) VALUES('a','A','success',?)",
                             (f'2026-09-24T10:{i:02d}:00+07:00',))
        conn.close()
        posts = self.client().get('/api/posts?limit=25').json['posts']
        self.assertEqual(25, len(posts))
        self.assertEqual('a', posts[0]['page_id'])

    def test_uncertain_post_can_be_resolved(self):
        conn = database.get_db_connection()
        with conn:
            conn.execute("INSERT INTO posts(id,page_id,status) VALUES(1,'a','retrying')")
            conn.execute("INSERT INTO posts(id,page_id,status) VALUES(2,'a','retrying')")
            conn.execute("INSERT INTO posts(id,page_id,status) VALUES(3,'a','failed')")
        conn.close()
        client = self.client()
        self.assertEqual(200, client.post('/api/posts/1/resolve',
                                          json={'outcome': 'published', 'fb_post_id': '11_22'}).status_code)
        self.assertEqual(200, client.post('/api/posts/2/resolve', json={'outcome': 'not_published'}).status_code)
        self.assertEqual(404, client.post('/api/posts/3/resolve', json={'outcome': 'published'}).status_code)
        self.assertEqual(400, client.post('/api/posts/1/resolve', json={'outcome': 'maybe'}).status_code)
        rows = self.query('SELECT status, fb_post_id FROM posts ORDER BY id')
        self.assertEqual([('success', '11_22'), ('failed', None), ('failed', None)], [tuple(r) for r in rows])


class NextRunTests(unittest.TestCase):
    def test_schedule_hours_skip_used_slot(self):
        from controllers.routes import _next_post_time
        now = datetime(2026, 9, 24, 10, 20, tzinfo=WIB)
        page = {'schedule_hours': [8, 10, 15]}
        self.assertEqual(now, _next_post_time(page, None, now))
        used = datetime(2026, 9, 24, 10, 5, tzinfo=WIB)
        self.assertEqual(datetime(2026, 9, 24, 15, 0, tzinfo=WIB), _next_post_time(page, used, now))
        late = datetime(2026, 9, 24, 22, 0, tzinfo=WIB)
        self.assertEqual(datetime(2026, 9, 25, 8, 0, tzinfo=WIB), _next_post_time(page, used, late))

    def test_interval_pages(self):
        from controllers.routes import _next_post_time
        now = datetime(2026, 9, 24, 10, 0, tzinfo=WIB)
        last = datetime(2026, 9, 24, 7, 0, tzinfo=WIB)
        self.assertEqual(datetime(2026, 9, 24, 13, 0, tzinfo=WIB),
                         _next_post_time({'interval_hours': 6}, last, now))

    def test_endpoint_handles_aware_timestamps(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        config = root / 'config.json'
        config.write_text(json.dumps({'fanspages': [
            {'page_id': 'a', 'name': 'A', 'schedule_hours': list(range(24))},
            {'page_id': 'b', 'name': 'B', 'interval_hours': 4}]}))
        with patch.object(database, 'DB_PATH', root / 'db.sqlite'), \
             patch('controllers.routes.CONFIG_PATH', config):
            database.init_db()
            conn = database.get_db_connection()
            with conn:
                conn.execute("INSERT INTO last_post_time(page_id,timestamp) VALUES('b',?)",
                             (datetime.now(WIB).isoformat(),))
            conn.close()
            from controllers import routes
            app = Flask(__name__)
            app.secret_key = 'test'
            app.register_blueprint(routes.bp)
            client = app.test_client()
            with client.session_transaction() as session:
                session['authenticated'] = True
            schedules = client.get('/api/next-run').json['all_schedules']
        self.assertEqual({'A', 'B'}, {s['page_name'] for s in schedules})
        self.assertTrue(all(s['next_post_time'] for s in schedules))


class MotionWorkerFlagTests(unittest.TestCase):
    def job_ids(self, value):
        from core import worker
        with patch.object(worker, 'BackgroundScheduler') as scheduler_cls, \
             patch.dict(os.environ, {'MOTION_EMBEDDED_WORKER': value}):
            worker.start_worker()
        return {c.kwargs.get('id') for c in scheduler_cls.return_value.add_job.call_args_list}

    def test_embedded_motion_worker_can_be_disabled(self):
        self.assertIn('motion_worker_job', self.job_ids('true'))
        self.assertNotIn('motion_worker_job', self.job_ids('false'))
        self.assertIn('auto_poster_job', self.job_ids('false'))


if __name__ == '__main__':
    unittest.main()
