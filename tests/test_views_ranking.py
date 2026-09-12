import unittest

from core.views_ranking import group_views_by_page


class ViewsRankingTests(unittest.TestCase):
    def test_pages_are_sorted_by_total_30_day_views(self):
        rows = [
            {'page_id': 'a', 'page_name': 'A', 'media_views': 100},
            {'page_id': 'b', 'page_name': 'B', 'media_views': 90},
            {'page_id': 'b', 'page_name': 'B', 'media_views': 80},
            {'page_id': 'c', 'page_name': 'C', 'media_views': None},
        ]
        groups = group_views_by_page(rows)
        self.assertEqual(['b', 'a', 'c'], [group['page_id'] for group in groups])
        self.assertEqual(170, groups[0]['total_views'])
        self.assertEqual(2, groups[0]['measured'])

    def test_missing_views_are_not_counted_as_zero_measurements(self):
        groups = group_views_by_page([
            {'page_id': 'a', 'page_name': 'A', 'media_views': None},
        ])
        self.assertEqual(0, groups[0]['total_views'])
        self.assertEqual(0, groups[0]['measured'])


if __name__ == '__main__':
    unittest.main()
