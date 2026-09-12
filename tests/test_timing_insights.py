import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

import learning_insights


def row(hour, views, engagement=10, relative=1.0, days=1):
    stamp = (datetime.now() - timedelta(days=days)).replace(hour=hour, minute=0, second=0, microsecond=0)
    return {
        'timestamp': stamp.isoformat(),
        'media_views': views,
        'engagement': engagement,
        'rel_engagement': relative,
    }


class TimingInsightsTests(unittest.TestCase):
    def test_views_48h_are_primary_when_available(self):
        rows = [row(1, 1000, engagement=1, days=i + 1) for i in range(5)]
        rows += [row(20, 100, engagement=9999, days=i + 1) for i in range(5)]
        with patch.object(learning_insights, '_fetch_timing_rows', return_value=rows):
            report = learning_insights.timing_report('page')
        by_hour = {item['hour']: item for item in report}
        self.assertEqual('views_48h', by_hour[1]['metric'])
        self.assertGreater(by_hour[1]['confident_score'], by_hour[20]['confident_score'])

    def test_recommendation_requires_five_posts(self):
        rows = [row(1, 1000, days=i + 1) for i in range(4)]
        rows += [row(20, 100, days=i + 1) for i in range(5)]
        with patch.object(learning_insights, '_fetch_timing_rows', return_value=rows):
            best = learning_insights.best_hours('page')
        self.assertEqual([20], [item['hour'] for item in best])

    def test_falls_back_to_relative_engagement(self):
        rows = [row(14, None, relative=2.0, days=i + 1) for i in range(5)]
        with patch.object(learning_insights, '_fetch_timing_rows', return_value=rows):
            report = learning_insights.timing_report('page')
        self.assertEqual('engagement_48h', report[0]['metric'])


if __name__ == '__main__':
    unittest.main()
