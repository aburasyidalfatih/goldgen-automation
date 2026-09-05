#!/usr/bin/env python3
"""
Learning Insights - Goldgen Automation

Membaca kembali hasil nyata (engagement) untuk mengukur apakah keputusan bot
benar-benar berdampak. Semua fungsi read-only dan aman dipanggil kapan saja.

Tiga pertanyaan yang dijawab modul ini:
  1. Layout mana yang benar-benar disukai audiens page ini? (sadar ukuran sampel)
  2. Apakah skor editor AI berkorelasi dengan engagement nyata?
  3. Jam berapa postingan page ini paling berhasil?
"""

from datetime import datetime

from core.database import get_db_connection


def _fetch_posts_with_engagement(page_id=None):
    """Ambil post sukses yang sudah punya angka engagement"""
    # Semua perhitungan memakai snapshot 48 jam saja, supaya laporan memakai
    # dasar yang persis sama dengan yang dipakai bot untuk mengambil keputusan.
    query = '''
        SELECT page_id, page_name, timestamp, layout_name, hook_type,
               editor_score, image_score, topic_id, topic_headline, content,
               clicks, engagement, rel_engagement, source
        FROM post_engagement
        WHERE source = 'snapshot48' AND rel_engagement IS NOT NULL
    '''
    params = []
    if page_id:
        query += ' AND page_id = ?'
        params.append(page_id)

    conn = get_db_connection()
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return rows


def _confident_lower_bound(values, z=1.96, sd_prior=0.9):
    """Batas bawah interval kepercayaan untuk rata-rata sekumpulan nilai.

    Dipakai agar layout dengan 1 post tidak disamakan dengan layout 10 post:
    makin sedikit sampel, makin besar potongannya. Ini yang membedakan
    "kelihatan bagus" dari "terbukti bagus".

    Versi sebelumnya memakai perkiraan Poisson (se = akar(mean/n)) yang hanya
    sah untuk data CACAH. Setelah engagement dinormalkan jadi rasio di sekitar
    1.0, perkiraan itu keliru dan hasilnya terjepit ke nol: 0.29x dan 0.53x
    sama-sama menjadi 0.00, sehingga urutan laporan jadi sembarang. Simpangan
    baku sampel sah di skala apa pun, jadi itu yang dipakai sekarang.

    Untuk n = 1 simpangan baku tidak terdefinisi; dipakai sd_prior sebagai
    perkiraan konservatif — satu sampel memang tidak membuktikan banyak.
    """
    n = len(values)
    if n == 0:
        return 0.0
    mean = sum(values) / n
    if n == 1:
        sd = sd_prior
    else:
        sd = (sum((v - mean) ** 2 for v in values) / (n - 1)) ** 0.5
        # Jangan terlalu yakin hanya karena beberapa sampel kebetulan seragam
        sd = max(sd, sd_prior * 0.3)
    return mean - z * sd / (n ** 0.5)


def layout_report(page_id):
    """Performa layout untuk satu page, diurut dari yang paling terbukti"""
    rows = [r for r in _fetch_posts_with_engagement(page_id) if r['layout_name']]

    # Diurut memakai engagement RELATIF — dasar yang sama dengan yang dipakai
    # bot saat memilih. Angka mentah tetap ditampilkan agar mudah dibaca.
    grouped = {}
    for r in rows:
        g = grouped.setdefault(r['layout_name'], [])
        g.append((float(r['engagement'] or 0), float(r['rel_engagement'] or 0)))

    report = []
    for layout, values in grouped.items():
        n = len(values)
        mean = sum(v[0] for v in values) / n
        rel = sum(v[1] for v in values) / n
        report.append({
            'layout': layout,
            'n': n,
            'avg': round(mean, 1),
            'relatif': round(rel, 2),
            'confident_score': round(_confident_lower_bound([v[1] for v in values]), 2),
            'best': round(max(v[0] for v in values), 1),
        })

    report.sort(key=lambda x: -x['confident_score'])
    return report


def editor_report(page_id=None, min_samples=12):
    """Apakah skor editor AI meramalkan engagement?"""
    rows = _fetch_posts_with_engagement(page_id)
    pairs = [(float(r['editor_score']), float(r['engagement'] or 0))
             for r in rows if r['editor_score'] is not None]

    n = len(pairs)
    result = {'n': n, 'r': None, 'avg_high': None, 'avg_low': None, 'verdict': ''}

    if n < min_samples:
        result['verdict'] = f'data belum cukup ({n}/{min_samples} post punya skor editor)'
        return result

    xs = [p[0] for p in pairs]
    ys = [p[1] for p in pairs]
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in pairs)
    dx = sum((x - mx) ** 2 for x in xs) ** 0.5
    dy = sum((y - my) ** 2 for y in ys) ** 0.5
    r = (num / (dx * dy)) if dx > 0 and dy > 0 else 0.0

    high = [y for x, y in pairs if x >= 8]
    low = [y for x, y in pairs if x < 8]

    result['r'] = round(r, 3)
    result['avg_high'] = round(sum(high) / len(high), 1) if high else None
    result['avg_low'] = round(sum(low) / len(low), 1) if low else None

    if r >= 0.2:
        result['verdict'] = 'BERGUNA — skor tinggi cenderung berbuah engagement tinggi'
    elif r <= -0.2:
        result['verdict'] = 'MENYESATKAN — skor tinggi justru engagement rendah'
    else:
        result['verdict'] = 'TIDAK BERPENGARUH — skor editor acak terhadap hasil'

    # Bukti konkret supaya penilaian editor bisa diperiksa manusia, bukan cuma
    # dipercaya angkanya: contoh caption yang dinilai tinggi tapi sepi, dan
    # sebaliknya. Dari sini terlihat selera editor menyimpang ke arah mana.
    scored = [(float(x['editor_score']), float(x['engagement'] or 0), x['content'] or '')
              for x in rows if x['editor_score'] is not None]
    tinggi_sepi = sorted([s for s in scored if s[0] >= 8], key=lambda x: x[1])[:2]
    rendah_ramai = sorted([s for s in scored if s[0] < 8], key=lambda x: -x[1])[:2]
    result['contoh_skor_tinggi_sepi'] = [
        {'skor': s, 'engagement': e, 'pembuka': c.strip().split('\n')[0][:90]} for s, e, c in tinggi_sepi
    ]
    result['contoh_skor_rendah_ramai'] = [
        {'skor': s, 'engagement': e, 'pembuka': c.strip().split('\n')[0][:90]} for s, e, c in rendah_ramai
    ]
    return result


def image_critic_report(page_id=None, min_samples=10):
    """Apakah skor kritikus gambar meramalkan engagement?

    Dibuat berbarengan dengan kritikusnya sendiri, karena pelajaran dari editor
    caption: juri yang tidak pernah diperiksa bisa berbulan-bulan memaksakan
    selera yang justru berlawanan dengan audiens. Skor gambar ikut disimpan
    sejak awal supaya pertanyaan itu bisa dijawab dengan angka, bukan dugaan.
    """
    rows = _fetch_posts_with_engagement(page_id)
    pairs = [(float(r['image_score']), float(r['engagement'] or 0))
             for r in rows if r['image_score'] is not None]

    n = len(pairs)
    hasil = {'n': n, 'r': None, 'avg_high': None, 'avg_low': None, 'verdict': ''}
    if n < min_samples:
        hasil['verdict'] = f'data belum cukup ({n}/{min_samples} post punya skor gambar)'
        return hasil

    xs = [a for a, _ in pairs]
    ys = [b for _, b in pairs]
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in pairs)
    dx = sum((x - mx) ** 2 for x in xs) ** 0.5
    dy = sum((y - my) ** 2 for y in ys) ** 0.5
    r = (num / (dx * dy)) if dx > 0 and dy > 0 else 0.0

    tinggi = [y for x, y in pairs if x >= 8]
    rendah = [y for x, y in pairs if x < 8]
    hasil['r'] = round(r, 3)
    hasil['avg_high'] = round(sum(tinggi) / len(tinggi), 1) if tinggi else None
    hasil['avg_low'] = round(sum(rendah) / len(rendah), 1) if rendah else None

    if r >= 0.2:
        hasil['verdict'] = 'BERGUNA — gambar yang dinilai bagus memang lebih disukai'
    elif r <= -0.2:
        hasil['verdict'] = 'MENYESATKAN — selera kritikus berlawanan dengan audiens'
    else:
        hasil['verdict'] = 'TIDAK BERPENGARUH — skor gambar acak terhadap hasil'
    return hasil


def hook_report(page_id, min_samples=2):
    """Engagement nyata per gaya hook — dasar pemilihan hook sekarang.

    Dikelompokkan menurut hook yang BENAR-BENAR keluar (hook_type), bukan yang
    diminta, dan dinormalkan ke daftar resmi supaya label bebas dari editor
    ('Contrast', 'Mystery') tidak tercecer jadi kategori sendiri.
    """
    from comment_analyzer import normalize_hook
    rows = _fetch_posts_with_engagement(page_id)

    kumpul = {}
    for r in rows:
        h = normalize_hook(r['hook_type']) if r['hook_type'] else None
        if h:
            kumpul.setdefault(h, []).append((float(r['engagement'] or 0), float(r['rel_engagement'] or 0)))

    hasil = []
    for h, v in kumpul.items():
        if len(v) < min_samples:
            continue
        avg = sum(x[0] for x in v) / len(v)
        rel = sum(x[1] for x in v) / len(v)
        hasil.append({
            'hook': h,
            'n': len(v),
            'avg': round(avg, 1),
            'relatif': round(rel, 2),
            'confident_score': round(_confident_lower_bound([x[1] for x in v]), 2),
        })
    return sorted(hasil, key=lambda x: -x['confident_score'])


def hook_compliance_report(page_id):
    """Seberapa sering generator benar-benar memakai hook yang diminta?

    Sistem bisa mempelajari hook mana yang menang, tapi kalau instruksinya tidak
    dipatuhi maka sisi eksploitasi tidak pernah berjalan — yang terjadi cuma
    eksplorasi acak. Angka ini membuat masalah itu terlihat, bukan tersembunyi.
    """
    conn = get_db_connection()
    rows = conn.execute('''
        SELECT requested_hook, hook_type
        FROM posts
        WHERE page_id = ? AND status = 'success' AND requested_hook IS NOT NULL
        ORDER BY id DESC LIMIT 30
    ''', (page_id,)).fetchall()
    conn.close()

    total = len(rows)
    if total == 0:
        return {'n': 0, 'patuh': 0, 'rasio': None, 'contoh': []}

    # Kedua sisi dinormalisasi lebih dulu. Editor kadang mengarang label
    # ("mystery", "contrast") yang maknanya sama dengan hook resmi — tanpa
    # pemetaan ini, caption yang sebenarnya sudah patuh akan terhitung melanggar.
    from comment_analyzer import normalize_hook

    patuh = 0
    contoh = []
    for r in rows:
        diminta_raw = (r['requested_hook'] or '').strip().lower()
        keluar_raw = (r['hook_type'] or '').strip().lower()
        diminta = normalize_hook(diminta_raw) or diminta_raw
        keluar = normalize_hook(keluar_raw)
        cocok = bool(diminta) and diminta == keluar
        patuh += 1 if cocok else 0
        if len(contoh) < 5:
            label_keluar = keluar_raw or '-'
            if keluar and keluar != keluar_raw:
                label_keluar = f"{keluar_raw} (= {keluar})"
            contoh.append({'diminta': diminta, 'keluar': label_keluar, 'cocok': cocok})

    return {'n': total, 'patuh': patuh, 'rasio': round(patuh / total, 2), 'contoh': contoh}


def timing_report(page_id):
    """Rata-rata engagement per jam posting (waktu WIB seperti tersimpan)"""
    rows = _fetch_posts_with_engagement(page_id)

    by_hour = {}
    for r in rows:
        try:
            hour = datetime.fromisoformat(r['timestamp']).hour
        except Exception:
            continue
        by_hour.setdefault(hour, []).append(float(r['engagement'] or 0))

    report = []
    for hour, values in sorted(by_hour.items()):
        n = len(values)
        mean = sum(values) / n
        report.append({
            'hour': hour,
            'n': n,
            'avg': round(mean, 1),
            'confident_score': round(_confident_lower_bound(values), 1),
        })
    return report


def best_hours(page_id, count=4, min_samples=2):
    """Rekomendasi jam posting, hanya dari jam yang datanya memadai"""
    solid = [h for h in timing_report(page_id) if h['n'] >= min_samples]
    solid.sort(key=lambda x: -x['confident_score'])
    return solid[:count]


def topic_report(page_id, limit=8):
    """Topik mana yang benar-benar disukai audiens page ini.

    Sebelumnya tidak ada laporan seperti ini sama sekali — topik tidak pernah
    disimpan per postingan, jadi bot mengoptimalkan pembungkus (layout, hook)
    tanpa pernah tahu isi mana yang laku.
    """
    rows = [r for r in _fetch_posts_with_engagement(page_id) if r['topic_headline']]

    grouped = {}
    for r in rows:
        grouped.setdefault(r['topic_headline'], []).append(
            (float(r['engagement'] or 0), float(r['rel_engagement'] or 0)))

    report = []
    for judul, values in grouped.items():
        n = len(values)
        mean = sum(v[0] for v in values) / n
        rel = sum(v[1] for v in values) / n
        report.append({
            'topik': judul,
            'n': n,
            'avg': round(mean, 1),
            'relatif': round(rel, 2),
            'confident_score': round(_confident_lower_bound([v[1] for v in values]), 2),
        })
    report.sort(key=lambda x: -x['confident_score'])
    return report[:limit]


def click_report(page_id):
    """Rasio engagement terhadap klik — ukuran daya tarik yang sudah dinormalkan.

    Like mentah mencampur dua hal: berapa banyak orang yang terpapar, dan
    seberapa menarik kontennya. Membaginya dengan klik memisahkan keduanya:
    klik turun = jangkauan menyempit; klik tetap tapi rasio turun = konten
    yang kurang memikat.
    """
    rows = [r for r in _fetch_posts_with_engagement(page_id)
            if r['clicks'] and r['clicks'] > 0]
    if not rows:
        return {'n': 0, 'klik_rata': None, 'rasio': None, 'terbaik': []}

    klik = [float(r['clicks']) for r in rows]
    eng = [float(r['engagement'] or 0) for r in rows]
    rasio = [e / k for e, k in zip(eng, klik)]

    terbaik = sorted(
        [{'topik': (r['topic_headline'] or r['layout_name'] or '-')[:40],
          'klik': int(r['clicks']),
          'engagement': int(r['engagement'] or 0),
          'rasio': round(float(r['engagement'] or 0) / float(r['clicks']) * 100, 1)}
         for r in rows],
        key=lambda x: -x['rasio']
    )[:3]

    return {
        'n': len(rows),
        'klik_rata': round(sum(klik) / len(klik), 1),
        'rasio': round(sum(rasio) / len(rasio) * 100, 1),
        'terbaik': terbaik,
    }


def caption_feature_report(page_id, min_samples=8):
    """Unsur caption mana yang berhubungan dengan engagement lebih tinggi.

    Menguji hal-hal yang selama ini hanya diatur lewat prompt tanpa pernah
    diverifikasi: panjang caption, ada tidaknya pertanyaan, jumlah emoji,
    dan jumlah tagar.
    """
    import re

    rows = [r for r in _fetch_posts_with_engagement(page_id) if r['content']]
    if len(rows) < min_samples:
        return {'n': len(rows), 'cukup': False, 'fitur': []}

    def emoji_count(teks):
        return sum(1 for ch in teks if ord(ch) > 0x2500)

    contoh = []
    for r in rows:
        teks = r['content'] or ''
        contoh.append({
            'eng': float(r['engagement'] or 0),
            'panjang': len(teks),
            'tanya': '?' in teks,
            'emoji': emoji_count(teks),
            'tagar': teks.count('#'),
        })

    hasil = []

    def bandingkan(nama, fungsi_pisah, label_ya, label_tidak):
        ya = [c['eng'] for c in contoh if fungsi_pisah(c)]
        tidak = [c['eng'] for c in contoh if not fungsi_pisah(c)]
        if len(ya) < 3 or len(tidak) < 3:
            return
        rata_ya = sum(ya) / len(ya)
        rata_tidak = sum(tidak) / len(tidak)
        selisih = ((rata_ya - rata_tidak) / rata_tidak * 100) if rata_tidak else 0
        hasil.append({
            'fitur': nama,
            'label_ya': label_ya, 'rata_ya': round(rata_ya, 1), 'n_ya': len(ya),
            'label_tidak': label_tidak, 'rata_tidak': round(rata_tidak, 1), 'n_tidak': len(tidak),
            'selisih_persen': round(selisih, 1),
        })

    median_panjang = sorted(c['panjang'] for c in contoh)[len(contoh) // 2]
    bandingkan('Panjang caption', lambda c: c['panjang'] > median_panjang,
               f'>{median_panjang} huruf', f'<={median_panjang} huruf')
    bandingkan('Ada pertanyaan', lambda c: c['tanya'], 'ada "?"', 'tanpa "?"')
    bandingkan('Banyak emoji', lambda c: c['emoji'] >= 3, '>=3 emoji', '<3 emoji')
    bandingkan('Jumlah tagar', lambda c: c['tagar'] >= 4, '>=4 tagar', '<4 tagar')

    hasil.sort(key=lambda x: -abs(x['selisih_persen']))
    return {'n': len(rows), 'cukup': True, 'fitur': hasil}


def audience_report(page_id):
    """Tren ukuran audiens + engagement relatif terhadapnya.

    Engagement mentah bisa turun karena dua sebab yang sangat berbeda:
    kontennya kurang menarik, atau postingannya tidak sampai ke orang.
    Menormalkan terhadap jumlah pengikut memisahkan keduanya sebagian —
    kalau pengikut naik tapi engagement per 1.000 pengikut turun, masalahnya
    ada di jangkauan atau daya tarik konten, bukan di ukuran audiens.
    """
    conn = get_db_connection()
    rows = conn.execute('''
        SELECT captured_date, COALESCE(followers_count, fan_count) AS pengikut
        FROM page_stats WHERE page_id = ? ORDER BY captured_date
    ''', (page_id,)).fetchall()

    # post_impressions sudah dihapus Meta; post_clicks jadi ukuran perhatian
    klik = conn.execute('''
        SELECT COUNT(*) n, AVG(s.clicks) rata
        FROM engagement_snapshots s JOIN posts p ON p.fb_post_id = s.fb_post_id
        WHERE p.page_id = ? AND s.clicks IS NOT NULL
    ''', (page_id,)).fetchone()

    # Interaksi harian seluruh halaman — sinyal jangkauan yang tidak tergantung
    # berapa kali kita posting
    harian = conn.execute('''
        SELECT captured_date, post_engagements, page_views
        FROM page_stats WHERE page_id = ? AND post_engagements IS NOT NULL
        ORDER BY captured_date DESC LIMIT 7
    ''', (page_id,)).fetchall()
    conn.close()

    riwayat = [{'tanggal': r['captured_date'], 'pengikut': r['pengikut']} for r in rows if r['pengikut']]

    hasil = {
        'riwayat': riwayat[-14:],
        'pengikut_terkini': riwayat[-1]['pengikut'] if riwayat else None,
        'pertumbuhan': None,
        'engagement_per_1000': None,
        'klik_tersedia': bool(klik and klik['n']),
        'klik_rata': round(klik['rata'], 1) if klik and klik['rata'] else None,
        'interaksi_harian': [
            {'tanggal': h['captured_date'], 'interaksi': h['post_engagements'], 'kunjungan': h['page_views']}
            for h in harian
        ],
    }

    if len(riwayat) >= 2:
        awal, akhir = riwayat[0]['pengikut'], riwayat[-1]['pengikut']
        if awal:
            hasil['pertumbuhan'] = round((akhir - awal) / awal * 100, 2)

    if hasil['pengikut_terkini']:
        posts = _fetch_posts_with_engagement(page_id)
        if posts:
            rata = sum(float(p['engagement'] or 0) for p in posts) / len(posts)
            hasil['engagement_per_1000'] = round(rata / hasil['pengikut_terkini'] * 1000, 2)

    return hasil


def full_report(fanspages):
    """Laporan lengkap untuk semua page — dipakai dashboard & CLI"""
    out = []
    for page in fanspages:
        pid = page.get('page_id')
        out.append({
            'page_name': page.get('name'),
            'page_id': pid,
            'schedule_hours': page.get('schedule_hours', []),
            'layouts': layout_report(pid),
            'editor': editor_report(pid),
            'image_critic': image_critic_report(pid),
            'hooks': hook_report(pid),
            'hook_compliance': hook_compliance_report(pid),
            'audience': audience_report(pid),
            'topics': topic_report(pid),
            'clicks': click_report(pid),
            'caption_features': caption_feature_report(pid),
            'timing': timing_report(pid),
            'best_hours': best_hours(pid),
        })
    return out
