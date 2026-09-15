import re
import unittest

from core import prospecting_style as gaya
from core.layout_design import DESIGNS, artwork_prompt

TOPIC = {'headline': 'READING THE RIVER', 'layout': 'CROSS-SECTION CUTAWAY',
         'list_points': ['Inside bends'], 'approved_caption': 'x' * 80}


class StyleBlockTests(unittest.TestCase):
    def test_style_block_does_not_dictate_a_rendering_look(self):
        """DESIGNS owns the look per layout — some photoreal, one engraved.

        A global 'aged paper / engraving' instruction would contradict half the
        catalogue and leave the model picking one at random, the same failure as
        the generic hook list sitting beside a mandated hook.
        """
        blok = gaya.artwork_style().lower()
        for bentrok in ('aged paper', 'engraving', 'weathered paper', 'woodcut', '3d'):
            self.assertNotIn(bentrok, blok, bentrok)

    def test_style_block_carries_the_parts_that_apply_to_every_look(self):
        blok = gaya.artwork_style()
        self.assertIn('ONE-SECOND TEST', blok)
        self.assertIn('plastic-looking nuggets', blok)

    def test_artwork_block_says_nothing_about_choosing_words(self):
        """Model gambar dilarang menulis; mengajarinya memilih kata sia-sia.

        Lebih buruk: menyebut "black sand, quartz, iron staining" di prompt
        ilustrasi menyuruhnya MENGGAMBAR benda-benda itu, apa pun topiknya —
        salah satu sebab semua poster terlihat sama.
        """
        blok = gaya.artwork_style()
        self.assertNotIn('UNCERTAIN INDICATORS', blok)
        self.assertNotIn('LABEL STYLE', blok)
        self.assertNotIn('BEDROCK CREVICE', blok)

    def test_label_rules_live_with_the_label_planner_instead(self):
        blok = gaya.label_style()
        self.assertIn('UNCERTAIN INDICATORS', blok)
        self.assertIn('LABEL STYLE', blok)
        self.assertIn('never be copied', blok)

    def test_uncertain_indicators_are_hedged_not_asserted(self):
        blok = gaya.UNCERTAINTY_WORDS
        self.assertIn('never proof', blok.lower())
        for kata in ('CLUE', 'SIGN', 'CHECK HERE', 'SAMPLE ZONE'):
            self.assertIn(kata, blok)

    def test_headline_formulas_are_offered_as_variety_not_a_single_template(self):
        blok = gaya.headline_style()
        self.assertGreaterEqual(len(gaya.HEADLINE_FORMULAS.strip().splitlines()), 8)
        self.assertIn('do not reuse one formula repeatedly', blok)

    def test_density_facts_stay_minimal(self):
        """Every extra number is a chance for the model to invent a statistic."""
        angka = re.findall(r'\d+\.?\d*', gaya.DENSITY_FACTS)
        self.assertLessEqual(len(angka), 4, angka)
        self.assertIn('19.3', angka)


class ArtworkPromptTests(unittest.TestCase):
    def test_prompt_includes_the_style_block(self):
        prompt = artwork_prompt(dict(TOPIC), {'labels': ['INSIDE BEND']})
        self.assertIn('ONE-SECOND TEST', prompt)

    def test_prompt_does_not_carry_the_poster_palette(self):
        """Palet hex milik poster, digambar PIL. Mengirimnya ke model gambar
        membuat ilustrasi ikut pucat dan seragam."""
        prompt = artwork_prompt(dict(TOPIC), {'labels': []})
        self.assertNotIn('#f5eedb', prompt)
        self.assertNotIn('Palette:', prompt)

    def test_prompt_stays_short_enough_to_be_followed(self):
        """Dulu 489 kata; separuhnya larangan yang saling menduplikasi.

        Ambang 300 adalah penjaga agar tidak merayap kembali, bukan target.
        """
        prompt = artwork_prompt(dict(TOPIC), {'labels': ['INSIDE BEND']})
        self.assertLess(len(prompt.split()), 300, len(prompt.split()))

    def test_prompt_still_forbids_lettering(self):
        # Typography is drawn by PIL; the model must not letter anything.
        prompt = artwork_prompt(dict(TOPIC), {'labels': ['INSIDE BEND']})
        self.assertIn('NO TEXT anywhere', prompt)

    def test_every_layout_still_builds_a_prompt(self):
        for nama in DESIGNS:
            prompt = artwork_prompt(dict(TOPIC, layout=nama), {'labels': []})
            self.assertIn('ONE-SECOND TEST', prompt, nama)
            self.assertTrue(prompt.strip())


if __name__ == '__main__':
    unittest.main()
