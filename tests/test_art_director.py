import unittest

from core.art_director import parse_art_direction, render_art_direction


class ArtDirectorTests(unittest.TestCase):
    def test_valid_plan_is_bounded_and_rendered(self):
        raw = '''```json
        {"focal_subject":"one river bend cutaway", "composition_adjustment":"River in upper third; bedrock cutaway dominates below.", "palette_and_contrast":"blue water, earth tones, bright gold accents", "label_plan":["DROP ZONE", "BEDROCK CRACK", "TOO MANY WORDS HERE"], "avoid":"long paragraphs and decorative nuggets"}
        ```'''
        plan = parse_art_direction(raw)
        self.assertEqual(["DROP ZONE", "BEDROCK CRACK"], plan["label_plan"])
        rendered = render_art_direction(raw)
        self.assertIn("DOMINANT FOCAL SUBJECT", rendered)
        self.assertIn("Do not introduce new facts", rendered)

    def test_invalid_or_incomplete_plan_falls_back(self):
        self.assertIsNone(render_art_direction("not json"))
        self.assertIsNone(render_art_direction('{"focal_subject":"river"}'))

    def test_excess_labels_are_limited(self):
        raw = '{"focal_subject":"river", "composition_adjustment":"clear cutaway", "label_plan":["ONE", "TWO", "THREE", "FOUR", "FIVE"]}'
        self.assertEqual(4, len(parse_art_direction(raw)["label_plan"]))


if __name__ == "__main__":
    unittest.main()
