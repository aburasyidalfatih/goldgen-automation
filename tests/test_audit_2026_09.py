"""Regression tests for the September 2026 workflow audit."""
import json
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

from flask import Flask

from core import database

WIB = timezone(timedelta(hours=7))
CAPTION = ('Gold settles where the water slows down, so check the inside of each bend first. '
           'Dig a small test hole down to bedrock and compare what you find.')


class DbCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.db = patch.object(database, 'DB_PATH', self.root / 'test.db')
        self.db.start()
        database.init_db()

    def tearDown(self):
        self.db.stop()
        self.tmp.cleanup()

    def execute(self, sql, params=()):
        conn = database.get_db_connection()
        with conn:
            conn.execute(sql, params)
        conn.close()


class NoFakeLocationTests(DbCase):
    def test_post_carries_no_place_or_feeling(self):
        from auto_poster import GoldGenAutoPoster
        poster = GoldGenAutoPoster.__new__(GoldGenAutoPoster)
        poster.validate_token = Mock(return_value=(True, None))
        image = self.root / 'img.png'
        image.write_bytes(b'png')
        response = MagicMock(status_code=200)
        response.json.return_value = {'id': '1', 'post_id': '9_1'}
        with patch('core.generation_reliability.load_review', return_value={}), \
             patch('core.content_quality.require_publishable'), \
             patch('core.generation_reliability.clock_ready', return_value=True), \
             patch('auto_poster.requests.post', return_value=response) as post:
            post_id, _ = poster.post_to_facebook({'page_id': '9', 'access_token': 't'}, CAPTION, image)
        self.assertEqual('9_1', post_id)
        sent = post.call_args.kwargs['data']
        self.assertNotIn('place', sent)
        self.assertNotIn('feeling_id', sent)


class HookEnforcementTests(DbCase):
    def service(self, hooks, fail_after=None):
        from goldgen_service import GoldGenService
        service = GoldGenService.__new__(GoldGenService)
        service.model = 'text'
        service._get_latest_insights = lambda page_id: {}
        service._get_audience_preferences = lambda page_id: []
        service._choose_hook = lambda page_id, preferred: ('secret', 'test')
        service._editor_is_trustworthy = lambda page_id: (True, '')
        reviews = iter([{'score': 8, 'hook_type': h, 'factual_issues': [], 'feedback': ''} for h in hooks])
        service._editor_review = lambda caption, requested_hook=None: next(reviews)
        responses = [MagicMock(text=f'{CAPTION} v{i}') for i in range(len(hooks))]
        if fail_after is not None:
            responses = responses[:fail_after] + [RuntimeError('quota')] * (3 - fail_after)
        service.client = MagicMock()
        service.client.models.generate_content.side_effect = responses
        return service

    def topic(self):
        return {'headline': 'READ THE RIVER', 'subtitle': 's', 'list_points': ['a'], 'layout': 'X'}

    def test_mismatched_hook_is_rewritten(self):
        topic = self.topic()
        with patch('time.sleep'):
            caption = self.service(['Fact', 'Secret']).generate_caption(topic, 'p')
        self.assertTrue(caption.endswith('v1'))
        self.assertEqual('Secret', topic['hook_type'])

    def test_hook_rewrite_never_costs_the_post(self):
        topic = self.topic()
        with patch('time.sleep'):
            caption = self.service(['Fact'], fail_after=1).generate_caption(topic, 'p')
        self.assertTrue(caption.endswith('v0'))
        self.assertTrue(topic['caption_approved'])
        self.assertEqual('Fact', topic['hook_type'])

    def test_last_attempt_accepts_other_hook(self):
        topic = self.topic()
        with patch('time.sleep'):
            caption = self.service(['Fact', 'Fact', 'Story']).generate_caption(topic, 'p')
        self.assertTrue(caption.endswith('v2'))


class CommentAnalysisCacheTests(DbCase):
    def test_recent_analysis_is_reused(self):
        from comment_analyzer import CommentAnalyzer
        analyzer = CommentAnalyzer.__new__(CommentAnalyzer)
        analyzer.get_recent_comments = Mock()
        page = {'page_id': 'p', 'name': 'P', 'access_token': 't'}
        self.assertFalse(analyzer.analyzed_recently('p', 12))
        self.execute("INSERT INTO comment_insights(page_id, raw_analysis) VALUES ('p', '{}')")
        self.assertTrue(analyzer.analyzed_recently('p', 12))
        self.assertEqual('cached', analyzer.analyze_single_page(page, min_interval_hours=12))
        analyzer.get_recent_comments.assert_not_called()
        self.execute("UPDATE comment_insights SET analyzed_at=datetime('now','-13 hours')")
        self.assertFalse(analyzer.analyzed_recently('p', 12))


class BackupTests(unittest.TestCase):
    def test_backup_copies_and_rotates(self):
        from core.backup import backup_database
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / 'posts.db'
            conn = sqlite3.connect(db)
            conn.execute('CREATE TABLE t(x)'); conn.execute('INSERT INTO t VALUES (1)'); conn.commit(); conn.close()
            config = root / 'config.json'
            config.write_text('{}')
            start = datetime(2026, 9, 1)
            for day in range(9):
                target = backup_database(db, config, now=start + timedelta(days=day))
            self.assertEqual(7, len(list((root / 'backups').glob('posts-*.db'))))
            self.assertEqual(7, len(list((root / 'backups').glob('config-*.json'))))
            copy = sqlite3.connect(target)
            self.assertEqual(1, copy.execute('SELECT x FROM t').fetchone()[0])
            copy.close()


class ShippedCatalogTests(unittest.TestCase):
    def test_repo_retirements_and_additions_reach_old_volumes(self):
        from core.layout_policy import curate_layouts
        volume = [{'name': 'A', 'composition': 'volume'}, {'name': 'B', 'retired': True},
                  {'name': 'C', 'prior_factor': 0.8}]
        shipped = [{'name': 'A', 'composition': 'repo', 'retired': True, 'retired_reason': 'no shares'},
                   {'name': 'B'}, {'name': 'C'}, {'name': 'D', 'composition': 'new'}]
        result = {l['name']: l for l in curate_layouts(volume, shipped)}
        self.assertTrue(result['A']['retired'])
        self.assertEqual('volume', result['A']['composition'])
        self.assertTrue(result['B']['retired'])          # never un-retired
        self.assertEqual(0.8, result['C']['prior_factor'])
        self.assertIn('D', result)
        self.assertEqual(volume[0], {'name': 'A', 'composition': 'volume'})  # input untouched

    def test_repo_catalog_is_valid(self):
        from core.layout_policy import curate_layouts
        shipped = json.loads(Path('data/layouts.json').read_text())
        self.assertTrue(curate_layouts(shipped, shipped))
        self.assertIn('cp data/layouts.json /app/catalog/', Path('Dockerfile').read_text())


class BotHealthTests(DbCase):
    def add_post(self, status, hours_ago, page='p', source='goldgen', error=None):
        stamp = (datetime.now(WIB) - timedelta(hours=hours_ago)).isoformat()
        self.execute('INSERT INTO posts(page_id,page_name,status,timestamp,source,error_message) VALUES (?,?,?,?,?,?)',
                     (page, 'Page', status, stamp, source, error))

    def test_failures_and_missed_slots_are_reported(self):
        from core.bot_health import page_health
        self.add_post('success', 30)
        for hours in (5, 3, 1):
            self.add_post('failed', hours, error='DITAHAN KUALITAS: skor gambar 3')
        self.add_post('failed', 2, source='manual')
        slot = (datetime.now(WIB) - timedelta(hours=4)).replace(minute=0, second=0, microsecond=0).isoformat()
        self.execute("INSERT INTO posting_attempts VALUES ('p', ?, 3, 'failed', ?)", (slot, slot))
        report = page_health([{'page_id': 'p', 'name': 'Page'}])[0]
        self.assertEqual((1, 3, 3, 1), (report['success'], report['failed'],
                                        report['consecutive_failures'], report['missed_slots']))
        self.assertEqual(3, len(report['warnings']))
        self.assertIn('skor gambar 3', report['last_error'])

    def test_reflection_and_dashboard_surface_failures(self):
        for hours in (5, 3, 1):
            self.add_post('failed', hours, error='TOKEN TIDAK AKTIF: expired')
        from core.reflection import reflect
        self.assertIn('publikasi gagal', [f['pemeriksaan'] for f in reflect()])
        from controllers import routes
        app = Flask(__name__)
        app.secret_key = 'test'
        app.register_blueprint(routes.bp)
        config = self.root / 'config.json'
        config.write_text(json.dumps({'fanspages': [{'page_id': 'p', 'name': 'Page'}]}))
        client = app.test_client()
        with client.session_transaction() as session:
            session['authenticated'] = True
        with patch('controllers.routes.CONFIG_PATH', config), patch('controllers.routes.DATA_DIR', self.root):
            data = client.get('/api/health-report').json
        page = data['pages'][0]
        self.assertTrue(page['token_problem'])
        self.assertIn('token', page['warnings'][0])
        self.assertTrue(data['reflection'])
        self.assertTrue(data['auto_best_hours'])


class WorkerJobsTests(unittest.TestCase):
    def test_backup_and_best_hours_are_scheduled(self):
        from core import worker
        with patch.object(worker, 'BackgroundScheduler') as scheduler_cls:
            worker.start_worker()
        ids = {c.kwargs.get('id') for c in scheduler_cls.return_value.add_job.call_args_list}
        self.assertTrue({'backup_job', 'best_hours_job'} <= ids)


if __name__ == '__main__':
    unittest.main()
