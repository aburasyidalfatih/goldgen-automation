import unittest
from unittest.mock import patch

from core import reflection


def post(**kwargs):
    base = {'id': 1, 'layout_name': 'CROSS-SECTION CUTAWAY', 'page_name': 'P',
            'image_score': None, 'timestamp': '2026-09-15T08:00:00+00:00',
            'source': 'goldgen', 'image_path': None, 'status': 'success',
            'media_views': None, 'views_48h': None, 'shares': None}
    base.update(kwargs)
    return base


class ReflectionTests(unittest.TestCase):
    def test_reports_when_no_layout_has_enough_evidence(self):
        rows = [post(layout_name='A', views_48h=100) for _ in range(3)]
        rows += [post(layout_name='B', views_48h=200) for _ in range(2)]
        pesan = reflection._kelaparan_sampel(rows)
        self.assertIsNotNone(pesan)
        self.assertIn('belum layak', pesan.lower())

    def test_silent_when_evidence_is_sufficient(self):
        rows = [post(layout_name='A', views_48h=100) for _ in range(reflection.MIN_SAMPLES)]
        self.assertIsNone(reflection._kelaparan_sampel(rows))

    def test_flags_an_option_that_wins_one_metric_and_loses_another(self):
        # A: banyak tayangan, jarang dibagikan. B: sebaliknya.
        rows = [post(layout_name='A', views_48h=1000, shares=1) for _ in range(3)]
        rows += [post(layout_name='B', views_48h=100, shares=5) for _ in range(3)]
        pesan = reflection._metrik_bertentangan(rows)
        self.assertIsNotNone(pesan)
        self.assertIn('tidak sepakat', pesan)

    def test_reports_a_critic_score_that_predicts_nothing(self):
        # Skor naik-turun tanpa pola terhadap tayangan.
        rows = [post(image_score=s, views_48h=v) for s, v in
                ((9, 500), (5, 480), (8, 520), (6, 470), (10, 510),
                 (4, 505), (7, 495), (5, 515), (9, 490), (6, 500))]
        pesan = reflection._kritikus_tidak_meramalkan(rows)
        self.assertIsNotNone(pesan)
        self.assertIn('tidak meramalkan', pesan)

    def test_reports_a_critic_score_that_points_the_wrong_way(self):
        # Skor tinggi justru menandai postingan yang sepi — lebih buruk
        # daripada sekadar tak berguna, dan sempat lolos tanpa dilaporkan.
        rows = [post(image_score=s, views_48h=v) for s, v in
                ((9, 100), (5, 900), (8, 200), (6, 800), (10, 150),
                 (4, 850), (7, 300), (5, 700), (9, 120), (6, 640))]
        pesan = reflection._kritikus_tidak_meramalkan(rows)
        self.assertIsNotNone(pesan)
        self.assertIn('BERLAWANAN', pesan)

    def test_notices_manual_posts_still_carrying_a_layout(self):
        rows = [post(source='manual', layout_name='CROSS-SECTION CUTAWAY')]
        self.assertIn('manual', reflection._kebocoran_manual(rows))
        self.assertIsNone(reflection._kebocoran_manual([post(source='manual', layout_name=None)]))

    def test_a_broken_check_does_not_silence_the_others(self):
        def meledak(_rows):
            raise ValueError('rusak')

        with patch.object(reflection, 'PEMERIKSAAN',
                          (('rusak', meledak), ('bocor', reflection._kebocoran_manual))), \
                patch.object(reflection, '_rows',
                             return_value=[post(source='manual', layout_name='X')]):
            temuan = reflection.reflect()
        nama = [t['pemeriksaan'] for t in temuan]
        self.assertIn('rusak', nama)
        self.assertIn('bocor', nama)

    def test_report_says_plainly_when_nothing_is_wrong(self):
        self.assertIn('Tidak ada yang mencurigakan', reflection.format_laporan([]))

    def test_report_states_that_nothing_was_changed(self):
        laporan = reflection.format_laporan([{'pemeriksaan': 'x', 'pesan': 'y'}])
        self.assertIn('Laporan saja', laporan)


if __name__ == '__main__':
    unittest.main()
