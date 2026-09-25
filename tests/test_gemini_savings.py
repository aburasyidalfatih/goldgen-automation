"""An image failure must not throw away an approved caption."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

from core import database
from core.generation_reliability import save_review

CAPTION = 'x' * 150


class CaptionReuseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.db = patch.object(database, 'DB_PATH', self.root / 'test.db')
        self.db.start()
        database.init_db()
        from auto_poster import GoldGenAutoPoster
        self.poster = GoldGenAutoPoster.__new__(GoldGenAutoPoster)
        self.page = {'page_id': 'p', 'name': 'P', 'access_token': 't', 'schedule_hours': [1]}

    def tearDown(self):
        self.db.stop()
        self.tmp.cleanup()

    def failed_post(self, topic, content=CAPTION, name='img.png', status='failed'):
        image = self.root / name
        image.write_bytes(name.encode())
        save_review('p', image, content, topic)
        conn = database.get_db_connection()
        with conn:
            conn.execute("INSERT INTO posts(page_id,content,image_path,status,timestamp) "
                         "VALUES ('p',?,?,?,datetime('now','-20 minutes'))", (content, str(image), status))
        conn.close()

    def approved(self, **extra):
        return {'headline': 'River', 'layout': 'L', 'caption_approved': True,
                'visual_plan': {'x': 1}, **extra}

    def test_fallback_or_low_score_reuses_caption(self):
        self.failed_post(self.approved(image_fallback=True))
        content, topic = self.poster._resume_approved_caption(self.page)
        self.assertEqual(CAPTION, content)
        self.assertNotIn('image_fallback', topic)
        self.assertNotIn('visual_plan', topic)
        self.assertIsNone(topic['image_score'])
        self.assertEqual('River', topic['headline'])

    def test_low_score_reuses_caption(self):
        self.failed_post(self.approved(image_score=3))
        self.assertIsNotNone(self.poster._resume_approved_caption(self.page))

    def test_no_reuse_when_not_an_image_failure(self):
        self.failed_post(self.approved(image_score=8), name='a.png')           # failed for another reason
        self.failed_post(self.approved(image_score=None), content='y' * 150, name='b.png')  # unreviewed
        self.failed_post({'caption_approved': False, 'image_fallback': True}, content='z' * 150, name='c.png')
        self.assertIsNone(self.poster._resume_approved_caption(self.page))

    def test_no_reuse_after_publication_or_repeated_failures(self):
        self.failed_post(self.approved(image_fallback=True))
        self.failed_post(self.approved(), name='ok.png', status='success')
        self.assertIsNone(self.poster._resume_approved_caption(self.page))

    def test_gives_up_after_three_failures(self):
        for i in range(3):
            self.failed_post(self.approved(image_fallback=True), name=f'{i}.png')
        self.assertIsNone(self.poster._resume_approved_caption(self.page))

    def test_scheduled_run_skips_caption_generation(self):
        self.failed_post(self.approved(image_score=3))
        poster = self.poster
        poster.fanspages = [self.page]
        poster.goldgen = MagicMock(state_file=self.root / 'state.json', topics=[{}])
        poster.process_queue = Mock()
        poster.should_post = Mock(return_value=True)
        poster.validate_token = Mock(return_value=(True, None))
        poster.generate_content = Mock()
        poster.generate_image = Mock(return_value=self.root / 'new.png')
        poster.post_to_facebook = Mock(return_value=('1_2', None))
        poster.log_post = Mock()
        poster.update_last_post_time = Mock()
        with patch('core.generation_reliability.clock_ready', return_value=True), \
             patch('core.generation_reliability.save_review'), \
             patch('core.content_quality.require_publishable'), \
             patch('core.promo_comment.send_pending_promo_comments'), \
             patch('auto_poster.CommentAnalyzer'), \
             patch('auto_poster.BASE_DIR', self.root):
            poster.run()
        poster.generate_content.assert_not_called()
        poster.generate_image.assert_called_once()
        self.assertEqual(CAPTION, poster.post_to_facebook.call_args.args[1])


if __name__ == '__main__':
    unittest.main()
