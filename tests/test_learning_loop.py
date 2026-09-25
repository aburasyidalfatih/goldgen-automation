"""Learning signals reach generation and the schedule."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core import database
from core.content_feedback import image_learning_notes, save_feedback
from core.layout_design import poster_prompt
from core.schedule_tuning import apply_best_hours, propose


class ImageLearningTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = patch.object(database, 'DB_PATH', Path(self.tmp.name) / 'db.sqlite')
        self.db.start()
        database.init_db()

    def tearDown(self):
        self.db.stop()
        self.tmp.cleanup()

    def test_reviewer_lessons_and_styles_reach_the_image_prompt(self):
        topic = {'headline': 'River', 'visual_feedback': {
            'text': 'Enlarge the headline', 'layout': 'Give the cutaway more room',
            'color': '', 'facts': 'Remove depth numbers', 'question': 'Shorter'}}
        save_feedback('p', topic, 'image', 5, 'misspelling')
        notes = image_learning_notes('p', ['vintage field journal'])
        self.assertIn('Enlarge the headline', notes)
        self.assertIn('Give the cutaway more room', notes)
        self.assertIn('vintage field journal', notes)
        self.assertNotIn('Remove depth numbers', notes)  # facts stay with the quality gate
        prompt = poster_prompt({'layout': 'CROSS-SECTION CUTAWAY', 'headline': 'X'}, {}, learning=notes)
        printable, rest = prompt.split('END OF PRINTABLE COPY')
        self.assertIn('Enlarge the headline', rest)
        self.assertNotIn('Enlarge the headline', printable)

    def test_other_pages_and_empty_history_add_nothing(self):
        save_feedback('p', {'visual_feedback': {'text': 'Enlarge the headline'}}, 'image', 5, 'x')
        self.assertEqual('', image_learning_notes('other'))
        self.assertEqual('', image_learning_notes(None))

    def test_styles_survive_long_feedback(self):
        for i in range(6):
            save_feedback('p', {'visual_feedback': {'text': f'tip {i}', 'layout': f'lay {i}',
                                                    'color': f'col {i}'}}, 'image', 5, 'x')
        self.assertIn('field journal', image_learning_notes('p', ['field journal']))


def report(rows):
    return lambda page_id: rows


def hour(h, score, n=6, eff=4):
    return {'hour': h, 'n': n, 'effective_n': eff, 'confident_score': score}


class BestHoursTests(unittest.TestCase):
    def test_swaps_worst_scheduled_hour_for_better_proven_hour(self):
        page = {'page_id': 'a', 'schedule_hours': [8, 12, 19]}
        worst, best, _ = propose(page, report([hour(8, 2.0), hour(12, 1.1), hour(19, 2.5), hour(21, 3.0)]))
        self.assertEqual((12, 21), (worst, best))

    def test_keeps_schedule_without_enough_evidence(self):
        page = {'page_id': 'a', 'schedule_hours': [8, 12]}
        self.assertEqual((None, None), propose(page, report([hour(8, 2.0), hour(21, 3.0, n=2)]))[:2])
        self.assertEqual((None, None), propose(page, report([hour(8, 3.0), hour(12, 3.0), hour(21, 1.0)]))[:2])
        self.assertEqual((None, None), propose({'page_id': 'a', 'interval_hours': 6}, report([]))[:2])

    def test_apply_writes_one_swap_and_a_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'config.json'
            path.write_text(json.dumps({'fanspages': [{'page_id': 'a', 'name': 'A', 'schedule_hours': [8, 12, 19]}]}))
            results = apply_best_hours(path, timing_report=report(
                [hour(8, 2.0), hour(12, 1.1), hour(19, 2.5), hour(21, 3.0), hour(22, 2.9)]))
            self.assertEqual([8, 19, 21], json.loads(path.read_text())['fanspages'][0]['schedule_hours'])
            self.assertEqual([8, 19, 21], results[0]['after'])
            self.assertEqual(1, len(list(Path(tmp).glob('config.json.backup.*'))))

    def test_worker_respects_the_off_switch(self):
        from core import worker
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'config.json'
            path.write_text(json.dumps({'auto_best_hours': False, 'fanspages': []}))
            with patch('core.config.CONFIG_PATH', path), patch('core.locks.DATA_DIR', Path(tmp)), \
                 patch('core.schedule_tuning.apply_best_hours') as apply:
                worker.job_best_hours()
            apply.assert_not_called()


class CommentWindowTests(unittest.TestCase):
    def test_cutoff_is_utc(self):
        from datetime import datetime, timezone
        from comment_analyzer import _utc_now_naive
        delta = abs((_utc_now_naive() - datetime.now(timezone.utc).replace(tzinfo=None)).total_seconds())
        self.assertLess(delta, 5)


if __name__ == '__main__':
    unittest.main()
