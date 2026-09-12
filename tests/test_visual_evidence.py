import json
import unittest
from unittest.mock import Mock, patch
from core.visual_evidence import density_guidance


class VisualEvidenceTests(unittest.TestCase):
    def guidance(self, counts):
        rows=[]
        for density,n,views in counts:
            rows.extend([{'payload':json.dumps(dict(text_density=density,readability='good',confidence=.9)),
                          'views_48h':views} for _ in range(n)])
        conn=Mock()
        conn.execute.return_value.fetchone.return_value=(1,)
        conn.execute.return_value.fetchall.return_value=rows
        with patch('core.visual_evidence.get_db_connection',return_value=conn):
            result=density_guidance('page-a')
        self.assertEqual(conn.execute.call_args.args[1],('page-a',))
        return result

    def test_insufficient_comparison_does_not_steer(self):
        self.assertEqual(self.guidance([('low',5,100),('high',4,50)]),'')

    def test_comparable_groups_produce_weak_guidance(self):
        self.assertIn('weak composition hint',self.guidance([('low',5,100),('high',5,50)]))

    def test_small_difference_does_not_steer(self):
        self.assertEqual(self.guidance([('low',5,100),('high',5,95)]),'')
