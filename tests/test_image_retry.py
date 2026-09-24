"""Image prompts carry few words, and retries change the prompt instead of repeating it."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

from PIL import Image

from core import database
from core.image_copy import FULL, SIMPLER, MINIMAL, approved_copy, short_subtitle
from core.layout_design import poster_prompt

QUESTION = 'Which of these river spots have you actually sampled before today?'
TOPIC = {'layout': 'CROSS-SECTION CUTAWAY', 'headline': 'Reading the River',
         'subtitle': 'Bedrock Cracks: Places to Test, Not Promises of Gold',
         'list_points': ['Inside bends', 'Behind large boulders', 'Bedrock cracks',
                         'Moss roots', 'Explain the local geometry without inventing mechanisms.'],
         'approved_caption': 'x' * 200}


def words(copy):
    return (len(copy['title'].split()) + len(copy['subtitle'].split())
            + len(copy['question'].split()) + sum(len(p.split()) for p in copy['labels']))


class CopyBudgetTests(unittest.TestCase):
    def test_subtitle_keeps_a_whole_clause_or_nothing(self):
        self.assertEqual('Gold drops where water slows down.', short_subtitle('Gold drops where water slows down.'))
        long = 'Check retained output from every run before guessing whether gold is lost downstream'
        self.assertEqual('', short_subtitle(long))
        self.assertEqual('Places worth testing first',
                         short_subtitle('Places worth testing first, not promises of gold in every crack'))

    def test_every_catalog_topic_fits_the_budget(self):
        with open('data/topics.json', encoding='utf-8') as handle:
            topics = json.load(handle)
        for topic in topics:
            copy = approved_copy(topic, {'question': QUESTION})
            self.assertLessEqual(len(copy['subtitle'].split()), 8, topic['headline'])
            self.assertTrue(all(len(p.split()) <= 4 for p in copy['labels']), topic['headline'])
            self.assertLessEqual(words(copy), 40, topic['headline'])

    def test_levels_remove_text(self):
        full = approved_copy(TOPIC, {'question': QUESTION}, FULL)
        simpler = approved_copy(TOPIC, {'question': QUESTION}, SIMPLER)
        minimal = approved_copy(TOPIC, {'question': QUESTION}, MINIMAL)
        self.assertEqual(QUESTION, full['question'])
        self.assertEqual('', simpler['question'])
        self.assertEqual(('', ''), (minimal['subtitle'], minimal['question']))
        self.assertLessEqual(len(minimal['labels']), 3)
        self.assertGreater(words(full), words(simpler))
        self.assertGreater(words(simpler), words(minimal))


class PosterPromptTests(unittest.TestCase):
    def test_empty_sections_are_not_sent(self):
        prompt = poster_prompt({'layout': 'CROSS-SECTION CUTAWAY', 'headline': 'X'}, {})
        printable = prompt.split('END OF PRINTABLE COPY')[0]
        for name in ('SUBTITLE:', 'LABELS', 'DISCUSSION QUESTION:', 'LIST HEADER'):
            self.assertNotIn(name, printable)

    def test_reviewer_note_reaches_the_prompt_outside_printable_copy(self):
        prompt = poster_prompt(dict(TOPIC), {}, SIMPLER, 'The word RIVRE is misspelled')
        self.assertIn('RIVRE', prompt.split('END OF PRINTABLE COPY')[1])
        self.assertNotIn('RIVRE', prompt.split('END OF PRINTABLE COPY')[0])

    def test_word_count_is_stated(self):
        plan = {'question': QUESTION}
        prompt = poster_prompt(dict(TOPIC), plan)
        self.assertIn(f"exactly {words(plan['approved_image_copy'])} words", prompt)


def _response(with_image=True):
    part = MagicMock()
    part.as_image.return_value = Image.new('RGB', (90, 160), 'white') if with_image else None
    part.inline_data = None
    response = MagicMock(parts=[part] if with_image else [], candidates=[], text='')
    return response


class GenerateImageRetryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.db = patch.object(database, 'DB_PATH', self.root / 'test.db')
        self.db.start()
        database.init_db()

    def tearDown(self):
        self.db.stop()
        self.tmp.cleanup()

    def generate(self, responses, scores):
        from auto_poster import GoldGenAutoPoster
        from core.visual_plan import fallback_plan
        poster = GoldGenAutoPoster.__new__(GoldGenAutoPoster)
        poster.image_model = 'gemini-3.1-flash-image'
        poster.text_model = 'text'
        poster.gemini_api_key = 'k'
        poster.goldgen = Mock()
        poster.goldgen.generate_image_prompt.return_value = 'base prompt'

        def art(topic, base):
            topic['visual_plan'] = fallback_plan(topic) | {'question': QUESTION}
            return base
        poster._apply_art_direction = art
        poster._review_image = Mock(side_effect=[(s, f'misspelled word {i}') for i, s in enumerate(scores)])
        client = MagicMock()
        client.models.generate_content.side_effect = responses
        topic = dict(TOPIC)
        with patch('auto_poster.genai.Client', return_value=client), \
             patch('auto_poster.IMAGES_DIR', self.root), \
             patch('auto_poster.time.sleep'):
            path = poster.generate_image(topic, 'Page', 'p')
        prompts = [c.kwargs['contents'] for c in client.models.generate_content.call_args_list]
        return path, topic, prompts

    def test_low_score_retry_uses_fewer_words_and_the_reviewer_note(self):
        path, topic, prompts = self.generate([_response()] * 2, [3, 8])
        self.assertEqual(8, topic['image_score'])
        self.assertEqual(2, len(prompts))
        self.assertIn('misspelled word 0', prompts[1])
        count = lambda p: int(p.split('carries exactly ')[1].split()[0])
        self.assertLess(count(prompts[1]), count(prompts[0]))
        self.assertIn(QUESTION, prompts[0])
        self.assertNotIn(QUESTION, prompts[1])

    def test_empty_replies_simplify_and_keep_the_best_image(self):
        path, topic, prompts = self.generate([_response(), _response(False), _response(False)], [5])
        self.assertEqual(3, len(prompts))
        self.assertNotEqual(prompts[1], prompts[2])
        self.assertFalse(topic.get('image_fallback'))
        self.assertEqual(5, topic['image_score'])
        self.assertTrue(Path(path).exists())


if __name__ == '__main__':
    unittest.main()
