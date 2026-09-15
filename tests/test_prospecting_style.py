import re
import unittest

from core import prospecting_style as gaya
from core.layout_design import poster_prompt

TOPIC = {'headline': 'READING THE RIVER', 'layout': 'CROSS-SECTION CUTAWAY',
         'subtitle': 'Gold drops where water slows.', 'list_header': 'FIELD SIGNS',
         'list_points': ['Inside bends'], 'approved_caption': 'x' * 80}


class StyleBlockTests(unittest.TestCase):
    def test_visual_identity_does_not_dictate_a_rendering_look(self):
        """DESIGNS owns the look per layout - some photoreal, one engraved.

        A global 'aged paper / engraving' instruction would contradict half the
        catalogue and leave the model picking one at random, the same failure as
        the generic hook list sitting beside a mandated hook.
        """
        blok = gaya.VISUAL_DNA.lower()
        for bentrok in ('aged paper', 'engraving', 'weathered paper', 'woodcut', '3d'):
            self.assertNotIn(bentrok, blok, bentrok)

    def test_uncertain_indicators_are_hedged_not_asserted(self):
        blok = gaya.UNCERTAINTY_WORDS
        self.assertIn('never proof', blok.lower())
        for kata in ('CLUE', 'SIGN', 'CHECK HERE', 'SAMPLE ZONE'):
            self.assertIn(kata, blok)

    def test_label_planner_warns_against_copying_its_own_examples(self):
        """Empat contoh label pernah terbit apa adanya sebagai label poster
        ketika topiknya tidak memberi bahan."""
        blok = gaya.label_style()
        self.assertIn('LABEL STYLE', blok)
        self.assertIn('never be copied', blok)

    def test_headline_formulas_are_offered_as_variety_not_a_single_template(self):
        blok = gaya.headline_style()
        self.assertGreaterEqual(len(gaya.HEADLINE_FORMULAS.strip().splitlines()), 8)
        self.assertIn('do not reuse one formula repeatedly', blok)

    def test_density_facts_stay_minimal(self):
        """Every extra number is a chance for the model to invent a statistic."""
        angka = re.findall(r'\d+\.?\d*', gaya.DENSITY_FACTS)
        self.assertLessEqual(len(angka), 4, angka)
        self.assertIn('19.3', angka)


class PosterPromptTests(unittest.TestCase):
    def test_prompt_carries_the_composition_guidance(self):
        prompt = poster_prompt(dict(TOPIC), {})
        self.assertIn('ONE-SECOND TEST', prompt)
        self.assertIn('SUBJECT MATERIAL', prompt)

    def test_prompt_carries_the_poster_palette(self):
        """Palet hex sekarang memang milik gambar ini: gambarnya ADALAH
        posternya. Dulu palet ini membuat ilustrasi pucat karena ia cuma
        menempati kotak di tengah poster krem."""
        prompt = poster_prompt(dict(TOPIC), {})
        self.assertIn('#f5eedb', prompt)

    def test_art_direction_reaches_the_prompt_when_available(self):
        prompt = poster_prompt(dict(TOPIC), {'art_direction': {
            'focal_subject': 'A cut bank above a gravel bar',
            'avoid': 'duplicated boulders'}})
        self.assertIn('A cut bank above a gravel bar', prompt)
        self.assertIn('duplicated boulders', prompt)

    def test_prompt_survives_a_topic_missing_every_optional_field(self):
        prompt = poster_prompt({'layout': 'CROSS-SECTION CUTAWAY'}, {})
        self.assertIn('MANDATORY ART DIRECTION', prompt)


if __name__ == '__main__':
    unittest.main()
