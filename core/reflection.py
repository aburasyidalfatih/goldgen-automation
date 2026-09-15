"""Pemeriksaan mingguan: bot membaca datanya sendiri dan melaporkan keraguan.

Bot ini mengumpulkan data dengan rajin tetapi tidak pernah membacanya. Setiap
cacat pengukuran yang pernah ditemukan di proyek ini ditemukan oleh manusia yang
menyelidiki, bukan oleh botnya, dan masing-masing sempat berjalan berminggu-minggu:

- hook dipilih serakah dari pendapat model, tidak pernah diadu dengan hasil
- skor kritikus gambar tidak meramalkan performa sama sekali
- engagement mentah terseret pergeseran jangkauan antar era
- share mentah hanya mengikuti jangkauan
- 61 postingan tulisan tangan ikut terpelajari dengan layout yang tidak pernah
  benar-benar mereka pakai

Modul ini HANYA MELAPOR. Ia tidak mengubah bobot, tidak mempensiunkan apa pun,
dan tidak menyentuh konfigurasi. Tujuannya membuat kecurigaan muncul dalam
hitungan hari, bukan bulan.
"""

import statistics as st

from core.database import get_db_connection

WINDOW_DAYS = 7
MIN_SAMPLES = 5          # di bawah ini sebuah pilihan belum layak disimpulkan
REACH_SHIFT = 0.5        # pergeseran median tayangan yang dianggap patut dilaporkan


def _rows(conn, days=30):
    return [dict(r) for r in conn.execute('''
        SELECT p.id, p.layout_name, p.page_name, p.image_score, p.timestamp,
               p.source, p.image_path, p.status,
               v.media_views, v.views_48h, v.shares
        FROM posts p
        LEFT JOIN post_views_current v ON v.fb_post_id = p.fb_post_id
        WHERE p.status = 'success'
          AND julianday(p.timestamp) >= julianday('now', ?)
    ''', (f'-{days} days',))]


def _dalam_jendela(row, days=WINDOW_DAYS):
    """Apakah postingan ini terjadi dalam jendela laporan mingguan?"""
    import datetime
    batas = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)
    try:
        t = datetime.datetime.fromisoformat(str(row.get('timestamp')))
    except (ValueError, TypeError):
        return False
    if t.tzinfo is None:
        t = t.replace(tzinfo=datetime.timezone.utc)
    return t >= batas


def _korelasi(pasangan):
    pasangan = [(a, b) for a, b in pasangan if a is not None and b is not None]
    n = len(pasangan)
    if n < 8:
        return None, n
    xs = [a for a, _ in pasangan]
    ys = [b for _, b in pasangan]
    mx, my = sum(xs) / n, sum(ys) / n
    atas = sum((a - mx) * (b - my) for a, b in pasangan)
    dx = sum((a - mx) ** 2 for a in xs) ** 0.5
    dy = sum((b - my) ** 2 for b in ys) ** 0.5
    return (atas / (dx * dy) if dx and dy else 0.0), n


def _kelaparan_sampel(rows):
    """Dimensi yang belum punya satu pun pilihan dengan bukti memadai."""
    diukur = [r for r in rows if r.get('views_48h') is not None and r.get('layout_name')]
    per_layout = {}
    for r in diukur:
        per_layout.setdefault(r['layout_name'], []).append(r['views_48h'])
    layak = {k: v for k, v in per_layout.items() if len(v) >= MIN_SAMPLES}
    if layak:
        return None
    terbaik = max((len(v) for v in per_layout.values()), default=0)
    return ('Belum ada layout dengan >=%d sampel terukur (tertinggi %d). '
            'Peringkat layout apa pun belum layak dijadikan keputusan.'
            % (MIN_SAMPLES, terbaik))


def _metrik_bertentangan(rows):
    """Pilihan yang menang di satu metrik tapi kalah di metrik lain."""
    per = {}
    for r in rows:
        if not r.get('layout_name') or r.get('views_48h') is None:
            continue
        per.setdefault(r['layout_name'], {'v': [], 's': []})
        per[r['layout_name']]['v'].append(r['views_48h'])
        if r.get('shares') is not None and r['views_48h']:
            per[r['layout_name']]['s'].append(1000.0 * r['shares'] / r['views_48h'])

    layak = {k: d for k, d in per.items() if len(d['v']) >= 3 and len(d['s']) >= 3}
    if len(layak) < 2:
        return None
    med_v = st.median([x for d in layak.values() for x in d['v']])
    med_s = st.median([x for d in layak.values() for x in d['s']])
    bentrok = []
    for k, d in layak.items():
        tayangan = st.median(d['v']) >= med_v
        dibagikan = st.median(d['s']) >= med_s
        if tayangan != dibagikan:
            bentrok.append('%s (tayangan %s, share %s)' % (
                k, 'tinggi' if tayangan else 'rendah', 'tinggi' if dibagikan else 'rendah'))
    if bentrok:
        return ('Metrik tidak sepakat untuk: ' + '; '.join(bentrok[:4]) +
                '. Jangan naikkan bobotnya sebelum diuji berpasangan.')
    return None


def _kritikus_tidak_meramalkan(rows):
    """Apakah skor kritikus gambar masih tidak berhubungan dengan hasil?"""
    r, n = _korelasi([(x.get('image_score'), x.get('views_48h')) for x in rows])
    if r is None:
        return None
    if r <= -0.2:
        # Lebih buruk daripada tidak berguna: skor tinggi justru menandai
        # postingan yang lebih sepi.
        return ('Skor kritikus gambar BERLAWANAN dengan tayangan (r=%+.2f, n=%d). '
                'Kalau ia ikut menyetir pemilihan, ia sedang menjauhkan kita '
                'dari konten yang berhasil.' % (r, n))
    if abs(r) < 0.2:
        return ('Skor kritikus gambar tidak meramalkan tayangan (r=%+.2f, n=%d). '
                'Pakai ia sebagai penjaga cacat, bukan sinyal pembelajaran.' % (r, n))
    return None


def _pergeseran_jangkauan(rows):
    """Median tayangan minggu ini dibanding minggu sebelumnya."""
    import datetime
    batas = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=WINDOW_DAYS)
    baru, lama = [], []
    for r in rows:
        if r.get('views_48h') is None:
            continue
        try:
            t = datetime.datetime.fromisoformat(str(r['timestamp']))
            if t.tzinfo is None:
                t = t.replace(tzinfo=datetime.timezone.utc)
        except ValueError:
            continue
        (baru if t >= batas else lama).append(r['views_48h'])
    if len(baru) < 3 or len(lama) < 3:
        return None
    a, b = st.median(lama), st.median(baru)
    if a <= 0:
        return None
    ubah = (b - a) / a
    if abs(ubah) >= REACH_SHIFT:
        return ('Median tayangan bergeser %+.0f%% (%.0f -> %.0f, n=%d vs %d). '
                'Perbandingan lintas minggu jadi tidak adil sampai ini stabil.'
                % (100 * ubah, a, b, len(lama), len(baru)))
    return None


def _kebocoran_manual(rows):
    """Postingan tulisan tangan yang masih membawa label layout."""
    bocor = [r for r in rows if r.get('source') == 'manual' and r.get('layout_name')]
    if bocor:
        return ('%d postingan manual masih punya layout_name. Pembelajaran sudah '
                'menyaringnya, tetapi laporan apa pun yang membaca tabel posts '
                'langsung akan tetap tercemar.' % len(bocor))
    return None


def _gambar_tanpa_ilustrasi(rows):
    """Poster teks tanpa gambar yang berhasil tayang.

    Dibatasi jendela mingguan: ini INSIDEN, bukan keadaan yang berlangsung.
    Tanpa batas itu, satu kejadian lama akan dilaporkan ulang setiap minggu
    selama sebulan dan membuat laporan ini gampang diabaikan.
    """
    import os
    diam = 0
    for r in rows:
        if not _dalam_jendela(r):
            continue
        p = str(r.get('image_path') or '')
        if p and p not in ('None', '') and os.path.exists(p) and os.path.getsize(p) < 400 * 1024:
            diam += 1
    if diam:
        return ('%d postingan tayang tanpa ilustrasi dalam 7 hari terakhir. Gerbang '
                'publikasi seharusnya menahannya — periksa jalur mana yang lolos.' % diam)
    return None


PEMERIKSAAN = (
    ('kelaparan sampel', _kelaparan_sampel),
    ('metrik bertentangan', _metrik_bertentangan),
    ('kritikus gambar', _kritikus_tidak_meramalkan),
    ('pergeseran jangkauan', _pergeseran_jangkauan),
    ('kebocoran data manual', _kebocoran_manual),
    ('poster tanpa ilustrasi', _gambar_tanpa_ilustrasi),
)


def reflect():
    """Jalankan semua pemeriksaan. Return daftar temuan (kosong = tidak ada)."""
    conn = get_db_connection()
    try:
        rows = _rows(conn)
    finally:
        conn.close()

    temuan = []
    for nama, periksa in PEMERIKSAAN:
        try:
            pesan = periksa(rows)
        except Exception as exc:  # noqa: BLE001
            # Satu pemeriksaan yang rusak tidak boleh membungkam sisanya.
            pesan = 'pemeriksaan gagal dijalankan: %s: %s' % (type(exc).__name__, exc)
        if pesan:
            temuan.append({'pemeriksaan': nama, 'pesan': pesan})
    return temuan


def format_laporan(temuan, total_post=None):
    if not temuan:
        return '🪞 <b>Refleksi mingguan</b>\n\nTidak ada yang mencurigakan minggu ini.'
    baris = ['🪞 <b>Refleksi mingguan</b>', '']
    for t in temuan:
        baris.append('⚠️ <b>%s</b>\n%s' % (t['pemeriksaan'], t['pesan']))
        baris.append('')
    baris.append('<i>Laporan saja — tidak ada bobot atau konfigurasi yang diubah.</i>')
    return '\n'.join(baris)
