import unittest
from unittest.mock import patch

from core.content_quality import require_publishable, ContentQualityError
from goldgen_service import _visual_labels


class FallbackPosterTests(unittest.TestCase):
    """On 15 September a safety block on the visual plan fell through to a
    text-only PIL poster, which was then published to Facebook as a success."""

    def test_text_only_fallback_is_not_publishable(self):
        topic = {'caption_approved': True, 'image_score': 9, 'image_fallback': True}
        with self.assertRaises(ContentQualityError) as ctx:
            require_publishable(topic)
        self.assertIn('ilustrasi', str(ctx.exception).lower())

    def test_real_artwork_still_passes(self):
        require_publishable({'caption_approved': True, 'image_score': 9})
        require_publishable({'caption_approved': True, 'image_score': 9,
                             'image_fallback': False})

    def test_unapproved_caption_is_still_blocked_first(self):
        with self.assertRaises(ContentQualityError):
            require_publishable({'caption_approved': False, 'image_fallback': True})


class PosterTitleTests(unittest.TestCase):
    def test_subtitle_after_colon_is_dropped_not_spliced(self):
        # Previously rendered as "MASTERING THE SLUICE BOX THE PHYSICS".
        self.assertEqual(
            'MASTERING THE SLUICE BOX',
            _visual_labels({'headline': 'Mastering the Sluice Box: The Physics of Particle Settlement'}))

    def test_other_clause_separators_are_handled(self):
        for headline, expected in (
                ('Read the River - How to Decode Geology', 'READ THE RIVER'),
                ('Why does gold sink? The physics explained', 'WHY DOES GOLD SINK'),
                ("The Prospector's Reality Check: How to Spot Real Gold",
                 "THE PROSPECTOR'S REALITY CHECK")):
            self.assertEqual(expected, _visual_labels({'headline': headline}))

    def test_short_catalog_headlines_are_untouched(self):
        for headline in ('READING THE RIVER', 'BEDROCK TRAPS', 'TEST PANNING'):
            self.assertEqual(headline, _visual_labels({'headline': headline}))

    def test_separator_is_ignored_when_it_would_leave_one_word(self):
        # Splitting here would leave a single letter, which is not a title.
        self.assertEqual('A B', _visual_labels({'headline': 'A: B'}))


class ArtDirectionRetryTests(unittest.TestCase):
    """A rejected art-direction layer must not cost the whole illustration:
    the deterministic base prompt is already rule-compliant."""

    def _poster(self):
        from auto_poster import GoldGenAutoPoster
        poster = GoldGenAutoPoster.__new__(GoldGenAutoPoster)
        poster.goldgen = type('S', (), {
            'generate_image_prompt': staticmethod(lambda topic, page_id: 'BASE PROMPT')})()
        return poster

    def test_rejected_art_direction_falls_back_to_the_base_prompt(self):
        poster = self._poster()
        poster.image_model = 'gemini-3.1-flash-image'
        poster.gemini_api_key = 'k'
        topic = {'headline': 'READING THE RIVER', 'layout': 'CROSS-SECTION CUTAWAY',
                 'list_points': ['a'], 'approved_caption': 'x' * 120}
        seen = []

        def preflight(_topic, prompt):
            seen.append(prompt)
            if prompt != 'BASE PROMPT':
                raise ContentQualityError('klaim terlarang (guaranteed gold)')

        # Image generation is out of scope here; stop it immediately so the test
        # only observes which prompt the pipeline settled on.
        with patch.object(poster, '_apply_art_direction', side_effect=lambda t, p: p + ' +ART'), \
                patch.object(poster, '_preflight_image_plan', side_effect=preflight), \
                patch.object(poster, '_generate_fallback_image', return_value='fallback.png'), \
                patch('google.genai.Client', side_effect=RuntimeError('stop here')), \
                patch('time.sleep'):
            poster.generate_image(topic, 'Page', 'pid')

        # The art layer was tried twice, then the safe deterministic prompt was
        # accepted for generation instead of the illustration being abandoned.
        self.assertEqual(['BASE PROMPT +ART', 'BASE PROMPT +ART', 'BASE PROMPT'], seen)
        self.assertFalse(topic.get('art_direction_used'))


if __name__ == '__main__':
    unittest.main()
