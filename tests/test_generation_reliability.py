import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from core import database
from core.generation_reliability import claim_slot, finish_slot, save_review, load_review, event, clock_ready
from core.content_quality import require_publishable, ContentQualityError, FORBIDDEN_IMAGE_TERMS
from core.image_copy import forbidden_claims
from core.layout_design import poster_prompt
from core.layout_experiments import pending


class ReliabilityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.db = patch.object(database, 'DB_PATH', self.root/'test.db')
        self.db.start()
        database.init_db()

    def tearDown(self):
        self.db.stop()
        self.tmp.cleanup()

    def test_failed_attempt_does_not_consume_success_slot_and_retry_is_bounded(self):
        now = datetime(2026, 9, 24, 6, 0, tzinfo=timezone.utc)
        slot = claim_slot('a', now)
        self.assertIsNotNone(slot)
        self.assertIsNone(claim_slot('a', now))
        self.assertIsNotNone(claim_slot('b', now))
        finish_slot('a', slot, 'failed', now)
        self.assertIsNone(claim_slot('a', now+timedelta(minutes=14)))
        self.assertEqual(slot, claim_slot('a', now+timedelta(minutes=15)))
        finish_slot('a', slot, 'failed', now+timedelta(minutes=15))
        self.assertEqual(slot, claim_slot('a', now+timedelta(minutes=30)))
        finish_slot('a', slot, 'failed', now+timedelta(minutes=30))
        self.assertIsNone(claim_slot('a', now+timedelta(minutes=45)))

    def test_uncertain_publish_never_retries_in_same_slot(self):
        now = datetime(2026, 9, 24, 6, 0, tzinfo=timezone.utc)
        slot = claim_slot('a', now)
        finish_slot('a', slot, 'uncertain', now)
        self.assertIsNone(claim_slot('a', now+timedelta(minutes=30)))

    def test_review_cannot_be_reused_for_other_page_caption_or_image(self):
        path = self.root/'art.png'; path.write_bytes(b'image1')
        topic = {'caption_approved': True, 'image_score': 8}
        save_review('a', path, 'caption', topic)
        require_publishable(load_review('a', path, 'caption'))
        for page,caption in [('b','caption'),('a','changed')]:
            with self.assertRaises(ContentQualityError):load_review(page,path,caption)
        path.write_bytes(b'image2')
        with self.assertRaises(ContentQualityError):load_review('a',path,'caption')

    def test_unknown_or_low_image_scores_and_fallback_are_blocked(self):
        for score in [None,3,6,float('nan')]:
            with self.assertRaises(ContentQualityError):
                require_publishable({'caption_approved':True,'image_score':score})
        with self.assertRaises(ContentQualityError):
            require_publishable({'caption_approved':True,'image_score':9,'image_fallback':True})

    def test_instructions_are_not_printable_copy(self):
        prompt=poster_prompt({'headline':'GOLD TOO SMALL TO SEE', 'layout':'DEEP CUTAWAY EXPLAINER',
            'list_points':['Zoom from a rock sample to schematic tiny inclusions.',
                           'Do not invent fixed depths or recovery rates.']}, {'labels':['Rock sample']})
        printable=prompt.split('END OF PRINTABLE COPY')[0]
        self.assertNotIn('Zoom from',printable)
        self.assertNotIn('Do not invent',printable)
        self.assertIn('Rock sample',printable)
        self.assertIn('Zoom from',prompt.split('DRAWING CONTEXT')[1])

    def test_negative_guardrail_is_not_a_positive_claim(self):
        self.assertEqual([], forbidden_claims('Do not recommend chemical extraction. Not guaranteed gold.',FORBIDDEN_IMAGE_TERMS))
        self.assertEqual(['guaranteed gold'], forbidden_claims('Not a guess; guaranteed gold here.',FORBIDDEN_IMAGE_TERMS))

    def test_legacy_experiment_stops_after_repeated_unlinked_failures(self):
        conn=database.get_db_connection()
        topic={'headline':'River','approved_caption':'same caption'}
        with conn:
            conn.execute("INSERT INTO layout_experiments VALUES('e','a',datetime('now','-1 day'),?)",
                         (json.dumps({'topic':topic,'layouts':['A','B']}),))
            conn.executemany("INSERT INTO posts(page_id,status,content,timestamp) VALUES('a','failed','same caption',datetime('now'))",[(),()])
        conn.close()
        self.assertIsNone(pending('a',[{'name':'A','composition':''},{'name':'B','composition':''}]))

    def test_error_events_redact_keys_and_keep_topic_identity(self):
        event('a',{'id':3,'layout':'A','experiment_id':'e'},'image_error', 'access_token=EAA'+'x'*30)
        conn=database.get_db_connection()
        row=conn.execute('SELECT * FROM generation_events').fetchone();conn.close()
        self.assertNotIn('x'*30,row['detail'])
        self.assertEqual('e',row['experiment_id'])
        self.assertEqual('3',row['topic_id'])

    def test_clock_skew_or_missing_network_fails_closed(self):
        response=type('Response',(),{'headers':{'Date':'Thu, 24 Sep 2020 12:00:00 GMT'}})()
        with patch('requests.head',return_value=response):self.assertFalse(clock_ready())

    def test_retry_rechecks_saved_artwork_without_generating_or_sending_when_review_fails(self):
        from auto_poster import GoldGenAutoPoster
        from unittest.mock import Mock
        path=self.root/'art.png';path.write_bytes(b'art')
        topic={'caption_approved':True,'image_score':None,'headline':'River'}
        save_review('a',path,'caption',topic)
        conn=database.get_db_connection()
        with conn:
            conn.execute("INSERT INTO posts(id,page_id,content,image_path,status) VALUES(1,'a','caption',?,'failed')",(str(path),))
        conn.close()
        poster=GoldGenAutoPoster.__new__(GoldGenAutoPoster)
        poster.fanspages=[{'page_id':'a','name':'A'}]
        poster.validate_token=Mock(return_value=(True,None))
        poster._review_image=Mock(return_value=(None,'provider unavailable'))
        poster.post_to_facebook=Mock()
        with patch('auto_poster.IMAGES_DIR',self.root):
            ok,message=poster.retry_existing_post(1)
        self.assertFalse(ok)
        self.assertIn('menunggu pemeriksaan',message)
        poster._review_image.assert_called_once()
        poster.post_to_facebook.assert_not_called()
        conn=database.get_db_connection()
        self.assertEqual('failed',conn.execute('SELECT status FROM posts WHERE id=1').fetchone()[0]);conn.close()

    def test_queue_does_not_send_rejected_image_or_future_item(self):
        from auto_poster import GoldGenAutoPoster
        from unittest.mock import Mock
        conn=database.get_db_connection()
        with conn:
            for time in ["-1 hour","+1 hour"]:
                conn.execute("INSERT INTO post_queue(page_id,content,image_path,status,scheduled_time) VALUES('a','caption','x.png','pending',datetime('now',?))",(time,))
        conn.close()
        poster=GoldGenAutoPoster.__new__(GoldGenAutoPoster)
        poster.fanspages=[{'page_id':'a','name':'A'}]
        poster._review_queued_image=Mock(side_effect=ContentQualityError('Skor rendah'))
        poster.post_to_facebook=Mock()
        poster.process_queue()
        poster._review_queued_image.assert_called_once()
        poster.post_to_facebook.assert_not_called()
        conn=database.get_db_connection()
        self.assertEqual(['failed','pending'],[r[0] for r in conn.execute('SELECT status FROM post_queue ORDER BY id')]);conn.close()


if __name__=='__main__':unittest.main()
