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


class BalasanTanpaGambarTests(unittest.TestCase):
    """Sebuah postingan produksi terbit sebagai poster teks tanpa ilustrasi.

    Penyebabnya balasan Gemini yang tidak memuat gambar di response.parts.
    Kode lama langsung menyerah ke poster PIL pada percobaan pertama, dan
    membuang teks balasannya sehingga alasannya tidak terbaca di log.
    """

    def test_image_is_found_when_only_candidates_carry_it(self):
        from auto_poster import _gambar_dari_balasan
        from PIL import Image

        class Bagian:
            def as_image(self):
                return Image.new('RGB', (4, 4))

        balasan = type('R', (), {'parts': [], 'candidates': [
            type('C', (), {'content': type('K', (), {'parts': [Bagian()]})()})()]})()
        self.assertEqual(1, len(list(_gambar_dari_balasan(balasan))))

    def test_image_is_found_when_only_inline_data_carries_it(self):
        from io import BytesIO
        from auto_poster import _gambar_dari_balasan
        from PIL import Image

        buf = BytesIO()
        Image.new('RGB', (4, 4)).save(buf, 'PNG')

        class Bagian:
            inline_data = type('D', (), {'data': buf.getvalue()})()

            def as_image(self):
                raise RuntimeError('SDK tidak mengenali bagian ini')

        balasan = type('R', (), {'parts': [Bagian()], 'candidates': []})()
        self.assertEqual(1, len(list(_gambar_dari_balasan(balasan))))

    def test_a_response_with_no_image_at_all_yields_nothing(self):
        from auto_poster import _gambar_dari_balasan
        balasan = type('R', (), {'parts': [], 'candidates': []})()
        self.assertEqual([], list(_gambar_dari_balasan(balasan)))


class ImageScoreGateTests(unittest.TestCase):
    """Ambang skor gambar dihitung sejak lama tapi tidak pernah dipakai.

    Selama PIL yang menyusun tipografi, poster bercacat masih terbaca. Sejak
    model gambar yang menulis seluruh teksnya, juri inilah satu-satunya yang
    bisa menangkap ejaan rusak sebelum poster tayang.
    """

    def _poster(self, skor_berurutan):
        from auto_poster import GoldGenAutoPoster
        poster = GoldGenAutoPoster.__new__(GoldGenAutoPoster)
        poster.image_model = 'gemini-3.1-flash-image'
        poster.gemini_api_key = 'k'
        poster.goldgen = type('S', (), {
            'generate_image_prompt': staticmethod(lambda topic, page_id: 'BASE PROMPT')})()
        self.skor = list(skor_berurutan)
        self.dinilai = []
        return poster

    def _jalankan(self, poster, tmp):
        from PIL import Image
        topic = {'headline': 'READING THE RIVER', 'layout': 'CROSS-SECTION CUTAWAY',
                 'list_points': ['a'], 'approved_caption': 'x' * 120}

        def simpan(path, output, watermark=''):
            Image.new('RGB', (8, 8)).save(output)

        def nilai(path, _topic, _page=None):
            skor = self.skor.pop(0)
            self.dinilai.append((path, skor))
            return skor, 'catatan'

        def arahan(_topic, prompt):
            _topic['visual_plan'] = {'labels': [], 'question': 'q'}
            return prompt

        with patch.object(poster, '_apply_art_direction', side_effect=arahan), \
                patch.object(poster, '_preflight_image_plan'), \
                patch.object(poster, '_review_image', side_effect=nilai), \
                patch('core.poster_renderer.stamp_watermark', side_effect=simpan), \
                patch('core.content_feedback.save_feedback'), \
                patch('core.visual_plan.save_plan'), \
                patch('auto_poster.IMAGES_DIR', tmp), \
                patch('google.genai.Client', side_effect=self.gemini), \
                patch('time.sleep'):
            return poster.generate_image(topic, 'Page', 'pid'), topic

    def gemini(self, **_):
        from PIL import Image

        class Bagian:
            def as_image(self):
                return Image.new('RGB', (8, 8))

        class Balasan:
            parts = [Bagian()]

        return type('C', (), {'models': type('M', (), {
            'generate_content': staticmethod(lambda **k: Balasan())})()})()

    def test_low_score_triggers_a_redraw(self):
        import tempfile
        from pathlib import Path
        poster = self._poster([4.0, 8.0])
        with tempfile.TemporaryDirectory() as tmp:
            path, topic = self._jalankan(poster, Path(tmp))
        self.assertEqual(2, len(self.dinilai))
        self.assertEqual(8.0, topic['image_score'])
        self.assertEqual(self.dinilai[1][0], path)

    def test_a_good_first_draw_is_not_redrawn(self):
        import tempfile
        from pathlib import Path
        poster = self._poster([9.0])
        with tempfile.TemporaryDirectory() as tmp:
            path, topic = self._jalankan(poster, Path(tmp))
        self.assertEqual(1, len(self.dinilai))
        self.assertEqual(9.0, topic['image_score'])

    def test_one_empty_response_does_not_cost_the_illustration(self):
        """Percobaan berikutnya sering berhasil. Menyerah pada percobaan
        pertama menukar satu balasan meleset dengan poster tanpa gambar, yang
        justru ditahan gerbang publikasi sehingga postingannya hilang."""
        import tempfile
        from pathlib import Path
        from PIL import Image
        poster = self._poster([8.0])
        self.kosong_dulu = [True, False]

        def gemini(**_):
            kosong = self.kosong_dulu.pop(0)

            class Bagian:
                def as_image(self):
                    return None if kosong else Image.new('RGB', (8, 8))

            return type('C', (), {'models': type('M', (), {
                'generate_content': staticmethod(
                    lambda **k: type('R', (), {'parts': [Bagian()], 'candidates': [],
                                               'text': 'maaf'})())})()})()

        self.gemini = gemini
        with tempfile.TemporaryDirectory() as tmp:
            path, topic = self._jalankan(poster, Path(tmp))
        self.assertEqual(8.0, topic['image_score'])
        self.assertEqual(1, len(self.dinilai))

    def test_when_every_attempt_is_poor_the_best_one_is_kept(self):
        """Gambar Gemini yang belum sempurna tetap lebih baik daripada poster
        teks tanpa ilustrasi, yang justru ditahan gerbang publikasi."""
        import tempfile
        from pathlib import Path
        poster = self._poster([3.0, 5.5, 4.0])
        with tempfile.TemporaryDirectory() as tmp:
            path, topic = self._jalankan(poster, Path(tmp))
        self.assertEqual(3, len(self.dinilai))
        self.assertEqual(5.5, topic['image_score'])
        self.assertEqual(self.dinilai[1][0], path)


if __name__ == '__main__':
    unittest.main()
