import unittest
from pathlib import Path


class AnalyticsAccordionTests(unittest.TestCase):
    def test_views_groups_use_single_open_accordion(self):
        template = (
            Path(__file__).parents[1] / 'templates' / 'analytics.html'
        ).read_text(encoding='utf-8')
        self.assertIn("container.querySelectorAll('.ranking-card.is-open')", template)
        self.assertIn("openCard.classList.remove('is-open')", template)
        self.assertIn("toggle.setAttribute('aria-expanded', 'true')", template)
        self.assertIn("if (groupIndex === 0) card.classList.add('is-open')", template)


if __name__ == '__main__':
    unittest.main()
