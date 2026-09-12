import unittest
from pathlib import Path


class SharedHeaderTests(unittest.TestCase):
    def test_internal_pages_use_one_shared_header(self):
        root = Path(__file__).parents[1] / 'templates'
        for name in ('dashboard_schedule.html', 'analytics.html',
                     'schedule_insight.html', 'motion_studio.html', 'app_detail.html'):
            with self.subTest(template=name):
                text = (root / name).read_text(encoding='utf-8')
                self.assertIn("{% include '_app_header.html' %}", text)

    def test_header_contains_every_primary_destination(self):
        text = (Path(__file__).parents[1] / 'templates' / '_app_header.html').read_text(encoding='utf-8')
        for href in ('/dashboard', '/analytics', '/schedule-insight', '/motion-studio', '/detail'):
            self.assertIn(f'href="{href}"', text)
        self.assertIn("fetch('/api/auth/logout'", text)
        self.assertIn('aria-label="Menu utama"', text)
        self.assertIn('grid-template-columns: 220px minmax(0,1fr) 90px', text)
        self.assertIn('justify-content: center', text)
        self.assertNotIn('⌂ Dashboard', text)


if __name__ == '__main__':
    unittest.main()
