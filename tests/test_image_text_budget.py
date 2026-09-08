import json
import unittest
from unittest.mock import patch

from goldgen_service import GoldGenService, _visual_labels, MAX_EXTRA_LABELS

TOPIC = {
    'headline': 'CHECK YOUR SLUICE TAILINGS',
    'subtitle': 'Check retained output before guessing whether gold is being lost.',
    'list_header': 'How to check',
    'list_points': [
        'Collect a manageable representative portion of processed output for checking.',
        'Keep test material labeled so different settings are not mixed.',
        'Change one setting at a time, following the equipment manual.',
        'A limited test does not establish a recovery percentage or perfect capture.',
    ],
    'layout': 'CROSS-SECTION CUTAWAY',
    'composition': 'A realistic cross-section of a riverbed.',
}


class VisualLabelTests(unittest.TestCase):
    def test_curated_headline_is_rendered_unchanged(self):
        self.assertEqual('CHECK YOUR SLUICE TAILINGS', _visual_labels(TOPIC))

    def test_accents_are_stripped_before_rendering(self):
        # Diacritics are among the characters the image model most often turns
        # into scribbles, so they must never reach the render instruction.
        label = _visual_labels({'headline': "Hjulstrom̈'s Curve"})
        self.assertTrue(label.isascii())
        self.assertIn('CURVE', label)

    def test_long_headline_does_not_end_on_a_connector(self):
        self.assertEqual(
            'THE SECRET OF READING A RIVER',
            _visual_labels({'headline': 'The Secret Of Reading A River For The'}))

    def test_missing_headline_still_yields_renderable_text(self):
        for topic in ({'headline': ''}, {'headline': None}, {}):
            self.assertTrue(_visual_labels(topic).strip())


class ImagePromptTests(unittest.TestCase):
    def _prompt(self, topic=None):
        service = GoldGenService.__new__(GoldGenService)
        service._get_latest_insights = lambda page_id: {}
        with patch('core.content_feedback.feedback_prompt', return_value=''):
            return service.generate_image_prompt(dict(topic or TOPIC), page_id=None)

    def test_body_text_is_supplied_as_guidance_not_as_words_to_write(self):
        prompt = self._prompt()
        # The model still needs the facts to draw the right thing...
        self.assertIn('Collect a manageable representative portion', prompt)
        # ...but must be told not to letter them onto the image.
        self.assertIn('do NOT copy this wording into the image', prompt)

    def test_render_budget_is_stated_as_a_limit_not_a_vague_warning(self):
        prompt = self._prompt()
        self.assertIn('CHECK YOUR SLUICE TAILINGS', prompt)
        self.assertIn('At most %d additional labels' % MAX_EXTRA_LABELS, prompt)
        for banned in ('No sentences', 'no paragraphs', 'no formulas'):
            self.assertIn(banned, prompt)

    def test_every_catalog_topic_produces_a_short_ascii_title(self):
        with open('data/topics.json', encoding='utf-8') as handle:
            topics = json.load(handle)
        self.assertTrue(topics)
        for topic in topics:
            title = _visual_labels(topic)
            self.assertTrue(title.isascii(), topic.get('headline'))
            self.assertLessEqual(len(title.split()), 6, topic.get('headline'))


if __name__ == '__main__':
    unittest.main()
