"""Facebook tidak merender Markdown; bintangnya terbit apa adanya.

Caption produksi tayang berbunyi "**learn to read the** landscape", dan teks
yang sama diteruskan ke model gambar, yang menafsirkannya sebagai perintah
menebalkan sebagian subjudul di poster.
"""
import unittest
from unittest.mock import patch

from core.content_quality import strip_markdown
from core.layout_design import poster_prompt


class StripMarkdownTests(unittest.TestCase):
    def test_the_caption_that_shipped_is_cleaned(self):
        self.assertEqual(
            'Stop digging where the crowds have been; learn to read the landscape.',
            strip_markdown('Stop digging where the crowds have been; '
                           '**learn to read the** landscape.'))

    def test_every_emphasis_marker_is_removed(self):
        for kotor, bersih in (
                ('**tebal**', 'tebal'),
                ('__tebal__', 'tebal'),
                ('*miring*', 'miring'),
                ('_miring_', 'miring'),
                ('`kode`', 'kode'),
                ('### Judul', 'Judul'),
                ('[teks](https://contoh.id)', 'teks')):
            self.assertEqual(bersih, strip_markdown(kotor), kotor)

    def test_unpaired_markers_are_removed_too(self):
        """Model teks kadang membuka penanda tanpa menutupnya."""
        self.assertEqual('gold hides here', strip_markdown('**gold hides here'))

    def test_multiplication_and_bullets_survive(self):
        """Bintang dengan spasi sesudahnya bukan penanda Markdown."""
        self.assertEqual('5 * 3 = 15', strip_markdown('5 * 3 = 15'))
        self.assertEqual('* inside bends\n* bedrock',
                         strip_markdown('* inside bends\n* bedrock'))

    def test_underscores_inside_words_survive(self):
        self.assertEqual('views_48h and media_views',
                         strip_markdown('views_48h and media_views'))

    def test_several_emphases_in_one_line(self):
        self.assertEqual('read the river and the rock',
                         strip_markdown('read **the river** and **the rock**'))

    def test_empty_input_is_safe(self):
        self.assertEqual('', strip_markdown(None))


class PosterPromptTests(unittest.TestCase):
    def test_markdown_never_reaches_the_image_model(self):
        prompt = poster_prompt({'layout': 'CROSS-SECTION CUTAWAY',
                                'headline': '**READ** THE RIVER',
                                'subtitle': 'Look for **slow water**.',
                                'list_header': '**KEY** SIGNS',
                                'list_points': ['Check **inside bends**']}, {})
        self.assertNotIn('**', prompt)
        self.assertIn('READ THE RIVER', prompt)
        self.assertIn('Check inside bends', prompt)


class FacebookPathTests(unittest.TestCase):
    def test_the_single_door_to_facebook_cleans_the_caption(self):
        """Postingan terjadwal, manual, dan percobaan ulang semuanya lewat sini."""
        from auto_poster import GoldGenAutoPoster
        poster = GoldGenAutoPoster.__new__(GoldGenAutoPoster)
        terkirim = {}

        def kirim(url, data=None, files=None, timeout=None):
            terkirim['message'] = data['message']
            raise RuntimeError('cukup sampai sini')

        # Pengiriman dihentikan tepat setelah payload terbentuk; yang diperiksa
        # hanya teks yang sudah siap berangkat ke Facebook.
        with patch.object(poster, 'validate_token', return_value=(True, None)), \
                patch('core.generation_reliability.load_review', return_value={'caption_approved': True, 'image_score': 9}), \
                patch('core.generation_reliability.clock_ready', return_value=True), \
                patch('auto_poster.requests.post', side_effect=kirim), \
                patch('builtins.open'), patch('time.sleep'), \
                self.assertRaises(RuntimeError):
            poster.post_to_facebook({'page_id': '1', 'access_token': 't'},
                                    'Gold hides where **water slows**.', 'x.png',
                                    single_attempt=True)
        self.assertEqual('Gold hides where water slows.', terkirim['message'])


if __name__ == '__main__':
    unittest.main()
