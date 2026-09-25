"""Setiap postingan GoldGen mendapat komentar promo pertama dari page."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from core import database
from core import promo_comment
from core.promo_comment import (FALLBACK_SENTENCES, PROMO_URL, audience_comments,
                                clean_sentence, promo_message, send_pending_promo_comments,
                                send_promo_comment)


class PromoSentenceTests(unittest.TestCase):
    def test_model_quirks_are_cleaned(self):
        self.assertEqual('Ready for your first flake', clean_sentence('"**Ready for your first flake**:"'))

    def test_unsafe_or_long_sentences_are_rejected(self):
        for buruk in ('See https://evil.example', 'Visit bit.ly/x now', 'Guaranteed gold in 7 trips',
                      'Two lines\nof text', 'Nice #gold', 'x' * 121, '', None):
            self.assertIsNone(clean_sentence(buruk), buruk)

    def test_link_always_comes_from_code(self):
        self.assertEqual('Start here: ' + PROMO_URL, promo_message('p1', 'Start here'))
        self.assertTrue(promo_message('p1', 'See www.other.com').endswith(PROMO_URL))

    def test_fallback_rotates_across_posts(self):
        pesan = {promo_message(f'post{i}') for i in range(40)}
        self.assertGreater(len(pesan), 1)


def _ok(comment_id='c1'):
    response = MagicMock(status_code=200)
    response.json.return_value = {'id': comment_id}
    return response


class PromoCommentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.patcher = patch.object(database, 'DB_PATH', Path(self.tmp.name) / 'db.sqlite')
        self.patcher.start()
        database.init_db()
        self.add('p1')

    def tearDown(self):
        self.patcher.stop()
        self.tmp.cleanup()

    def add(self, fb_post_id, age='-1 hours', source='goldgen', status='success'):
        conn = database.get_db_connection()
        conn.execute("INSERT INTO posts(page_id,status,fb_post_id,source,timestamp) "
                     "VALUES ('a',?,?,?,datetime('now',?))", (status, fb_post_id, source, age))
        conn.commit()
        conn.close()

    def promo_id(self, fb_post_id):
        conn = database.get_db_connection()
        try:
            return conn.execute("SELECT promo_comment_id FROM posts WHERE fb_post_id=?",
                                (fb_post_id,)).fetchone()[0]
        finally:
            conn.close()

    def test_comment_uses_the_gemini_sentence_and_the_fixed_link(self):
        compose = MagicMock(return_value='Reading the river well? Take it further')
        with patch.object(promo_comment.requests, 'post', return_value=_ok()) as kirim:
            self.assertEqual(('c1', None), send_promo_comment('p1', 'token', compose, 'caption'))
        compose.assert_called_once_with('caption')
        self.assertTrue(kirim.call_args.args[0].endswith('/p1/comments'))
        self.assertEqual('Reading the river well? Take it further: ' + PROMO_URL,
                         kirim.call_args.kwargs['data']['message'])
        self.assertEqual('c1', self.promo_id('p1'))

    def test_gemini_failure_falls_back_instead_of_skipping(self):
        with patch.object(promo_comment.requests, 'post', return_value=_ok()) as kirim:
            send_promo_comment('p1', 'token', MagicMock(side_effect=RuntimeError('503')))
        pesan = kirim.call_args.kwargs['data']['message']
        self.assertIn(pesan[:-len(': ' + PROMO_URL)], FALLBACK_SENTENCES)
        self.assertTrue(pesan.endswith(PROMO_URL))

    def test_promo_is_never_sent_twice(self):
        with patch.object(promo_comment.requests, 'post', return_value=_ok()) as kirim:
            send_promo_comment('p1', 'token')
            comment_id, _ = send_promo_comment('p1', 'token')
        self.assertIsNone(comment_id)
        self.assertEqual(1, kirim.call_count)

    def test_rejection_is_retried_by_the_catch_up(self):
        ditolak = MagicMock(status_code=400)
        with patch.object(promo_comment.requests, 'post', return_value=ditolak):
            send_promo_comment('p1', 'token')
        self.assertIsNone(self.promo_id('p1'))
        with patch.object(promo_comment.requests, 'post', return_value=_ok()):
            send_pending_promo_comments([{'page_id': 'a', 'access_token': 'token'}])
        self.assertEqual('c1', self.promo_id('p1'))

    def test_uncertain_send_is_not_repeated(self):
        """Tanpa jawaban Facebook, komentar mungkin sudah terbit; jangan kirim ulang."""
        with patch.object(promo_comment.requests, 'post', side_effect=TimeoutError()):
            send_promo_comment('p1', 'token')
        with patch.object(promo_comment.requests, 'post', return_value=_ok()) as kirim:
            send_pending_promo_comments([{'page_id': 'a', 'access_token': 'token'}])
        kirim.assert_not_called()

    def test_catch_up_skips_old_manual_and_failed_posts(self):
        self.add('lama', age='-3 days')
        self.add('manual', source='manual')
        self.add('gagal', status='failed')
        with patch.object(promo_comment.requests, 'post', return_value=_ok()) as kirim:
            send_pending_promo_comments([{'page_id': 'a', 'access_token': 'token'}])
        dikomentari = {c.args[0].split('/')[-2] for c in kirim.call_args_list}
        self.assertEqual({'p1'}, dikomentari)

    def test_own_promo_is_not_audience_engagement(self):
        with patch.object(promo_comment.requests, 'post', return_value=_ok()):
            send_promo_comment('p1', 'token')
        self.add('p2')
        conn = database.get_db_connection()
        try:
            self.assertEqual(2, audience_comments(conn, 'p1', 3))
            self.assertEqual(0, audience_comments(conn, 'p1', 0))
            self.assertEqual(3, audience_comments(conn, 'p2', 3))
        finally:
            conn.close()


class PosterWiringTests(unittest.TestCase):
    def test_successful_post_gets_promo_and_failure_does_not_break_posting(self):
        from auto_poster import GoldGenAutoPoster
        poster = GoldGenAutoPoster.__new__(GoldGenAutoPoster)
        with patch('core.promo_comment.send_promo_comment', side_effect=RuntimeError('x')) as kirim:
            poster._send_promo_comment({'access_token': 't'}, 'p1', 'caption')
        kirim.assert_called_once_with('p1', 't', None, 'caption')


if __name__ == '__main__':
    unittest.main()
