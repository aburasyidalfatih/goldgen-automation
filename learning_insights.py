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
    # Semua perhitungan memakai view post_engagement: hanya pengukuran matang
    # (>=48 jam) atau snapshot umur seragam, supaya perbandingannya adil.
    query = '''
        SELECT page_id, page_name, timestamp, layout_name, hook_type,
               editor_score, content, engagement, source
        FROM post_engagement
        WHERE 1=1
    '''
    params = []
    if page_id:
        query += ' AND page_id = ?'
        params.append(page_id)

    conn = get_db_connection()
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return rows


def _wilson_lower_bound(mean, n, z=1.96):
    """Batas bawah interval kepercayaan untuk rata-rata cacah.

    Dipakai agar layout dengan 1 post tidak disamakan dengan layout 10 post:
    makin sedikit sampel, makin besar potongannya. Ini yang membedakan
    "kelihatan bagus" dari "terbukti bagus".
    """
    if n <= 0:
        return 0.0
    # Perkiraan standard error untuk data cacah (Poisson): sqrt(mean / n)
    se = (mean / n) ** 0.5 if mean > 0 else 0.0
    return max(0.0, mean - z * se)


def layout_report(page_id):
    """Performa layout untuk satu page, diurut dari yang paling terbukti"""
    rows = [r for r in _fetch_posts_with_engagement(page_id) if r['layout_name']]

    grouped = {}
    for r in rows:
        g = grouped.setdefault(r['layout_name'], [])
        g.append(float(r['engagement'] or 0))

    report = []
    for layout, values in grouped.items():
        n = len(values)
        mean = sum(values) / n
        report.append({
            'layout': layout,
            'n': n,
            'avg': round(mean, 1),
            'confident_score': round(_wilson_lower_bound(mean, n), 1),
            'best': round(max(values), 1),
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
            'confident_score': round(_wilson_lower_bound(mean, n), 1),
        })
    return report


def best_hours(page_id, count=4, min_samples=2):
    """Rekomendasi jam posting, hanya dari jam yang datanya memadai"""
    solid = [h for h in timing_report(page_id) if h['n'] >= min_samples]
    solid.sort(key=lambda x: -x['confident_score'])
    return solid[:count]


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
            'hook_compliance': hook_compliance_report(pid),
            'audience': audience_report(pid),
            'timing': timing_report(pid),
            'best_hours': best_hours(pid),
        })
    return out
