"""Berita hanya boleh memilih TEMA, tidak boleh menulis posternya sendiri.

Sebuah resensi buku sejarah pernah terbit sebagai poster Facebook berjudul
"BREAKING NEWS", subjudulnya terpotong di tengah kalimat ("...makes the case
that the James"), dan ilustrasinya sungai generik yang tidak berhubungan dengan
apa pun. Penyebabnya: _get_breaking_news mengembalikan topik utuh langsung dari
hasil pencarian, melewati seluruh aturan editorial.
"""
import unittest
from unittest.mock import Mock, patch

from goldgen_service import GoldGenService, ISTILAH_LAPANGAN


def layanan():
    service = GoldGenService.__new__(GoldGenService)
    service.topics = []
    service.catalog_topics = []
    return service


class SaringanBeritaTests(unittest.TestCase):
    def jalankan(self, hasil):
        service = layanan()
        ddgs = Mock()
        ddgs.__enter__ = Mock(return_value=Mock(news=Mock(return_value=hasil)))
        ddgs.__exit__ = Mock(return_value=False)
        with patch.dict('sys.modules', {'ddgs': Mock(DDGS=Mock(return_value=ddgs))}):
            return service._kata_kunci_berita()

    def test_artikel_yang_dulu_terbit_kini_ditolak(self):
        """Artikel nyata yang lolos ke Facebook, disalin dari poster itu."""
        self.assertIsNone(self.jalankan([{
            'title': 'A Forgotten Chapter of the American Gold Rush',
            'body': 'A new book by historian Nathaniel Philbrick makes the case '
                    'that the James River settlement shaped the young republic.',
            'source': 'Smithsonian Magazine'}]))

    def test_satu_istilah_saja_belum_cukup(self):
        """Berita harga emas dan sengketa tambang hampir selalu kena satu."""
        self.assertIsNone(self.jalankan([{
            'title': 'Gold price hits record high',
            'body': 'Investors moved into bullion. One retired prospector said '
                    'he was not surprised.', 'source': 'Reuters'}]))

    def test_artikel_prospeksi_sungguhan_diterima(self):
        kata_kunci = self.jalankan([{
            'title': 'Placer claims reopen along the Fortymile',
            'body': 'Crews report coarse gold trapped in bedrock crevices below '
                    'the gravel bar.', 'source': 'Alaska Public Media'}])
        self.assertIsNotNone(kata_kunci)
        for bagian in kata_kunci.split(' and '):
            self.assertIn(bagian, ISTILAH_LAPANGAN)

    def test_artikel_relevan_dipakai_walau_bukan_hasil_pertama(self):
        """Versi lama mengambil results[0] tanpa memeriksa apa pun."""
        kata_kunci = self.jalankan([
            {'title': 'Gold price hits record high', 'body': 'Bullion demand.'},
            {'title': 'Weekend panning lesson draws a crowd',
             'body': 'Beginners learned to read a gravel bar and work a sluice.'}])
        self.assertIsNotNone(kata_kunci)

    def test_kata_kunci_tidak_pernah_memuat_kalimat_berita(self):
        """Inilah jaminan bahwa nama orang atau judul buku tidak bisa bocor."""
        kata_kunci = self.jalankan([{
            'title': 'Nathaniel Philbrick joins a placer panning trip',
            'body': 'The historian tried a gold pan on the gravel bar.'}])
        self.assertNotIn('philbrick', (kata_kunci or '').lower())
        self.assertNotIn('nathaniel', (kata_kunci or '').lower())

    def test_penelusuran_gagal_tidak_menjatuhkan_siklus_posting(self):
        service = layanan()
        with patch.dict('sys.modules', {'ddgs': Mock(DDGS=Mock(side_effect=RuntimeError('jaringan')))}):
            self.assertIsNone(service._kata_kunci_berita())

    def test_kosakata_menghindari_kata_emas_yang_terlalu_umum(self):
        """"gold", "mining", "claim", "rush" muncul di berita apa saja."""
        for umum in ('gold', 'mining', 'claim', 'rush', 'miner'):
            self.assertNotIn(umum, ISTILAH_LAPANGAN)


class TopikDariKeywordTests(unittest.TestCase):
    def test_topik_baru_masuk_katalog_dan_mengembalikan_indexnya(self):
        service = layanan()
        service.topics = [{'headline': 'READING THE RIVER'}]
        service.catalog_topics = list(service.topics)
        service._generate_dynamic_topic = Mock(return_value={'headline': 'BEDROCK CREVICE TRAPS'})
        with patch('builtins.open', side_effect=OSError('disk penuh')):
            indeks = service._topik_dari_keyword('bedrock')
        self.assertEqual(1, indeks)
        self.assertEqual(2, len(service.topics))

    def test_topik_kembar_memakai_yang_lama_alih_alih_menggandakan(self):
        """Kolam topik pernah membengkak 101 -> 199 karena pemeriksaan ini
        dilewati, dan tidak ada topik yang pernah cukup sampel untuk dipelajari."""
        service = layanan()
        service.topics = [{'headline': 'BEDROCK CREVICE TRAPS'}]
        service.catalog_topics = list(service.topics)
        service._generate_dynamic_topic = Mock(return_value={'headline': 'BEDROCK CREVICE TRAPS'})
        self.assertEqual(0, service._topik_dari_keyword('bedrock'))
        self.assertEqual(1, len(service.topics))

    def test_generator_gagal_dilaporkan_sebagai_none(self):
        service = layanan()
        service._generate_dynamic_topic = Mock(return_value=None)
        self.assertIsNone(service._topik_dari_keyword('bedrock'))


if __name__ == '__main__':
    unittest.main()
