"""Kesehatan publikasi per Fanspage: posting yang gagal dan slot yang terlewat.

Slot yang gagal tiga kali dalam satu jam hilang begitu saja, dan tanpa angka
ini kegagalan beruntun baru ketahuan ketika seseorang kebetulan membuka daftar
posting. Semua angka hanya menghitung posting buatan bot (bukan posting manual).
"""
from core.database import get_db_connection

WINDOW_DAYS = 7
MIN_ATTEMPTS = 3
WARN_SUCCESS_RATE = 0.7
WARN_CONSECUTIVE = 3


def page_health(pages, days=WINDOW_DAYS):
    conn = get_db_connection()
    try:
        has_slots = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE name='posting_attempts'").fetchone() is not None
        report = []
        for page in pages:
            page_id = str(page.get('page_id'))
            rows = conn.execute('''SELECT status, timestamp, error_message FROM posts
                WHERE page_id=? AND COALESCE(source,'goldgen') != 'manual'
                  AND julianday(timestamp) >= julianday('now', ?)
                ORDER BY id DESC''', (page_id, f'-{days} days')).fetchall()
            success = sum(1 for r in rows if r['status'] == 'success')
            failed = len(rows) - success
            consecutive = 0
            for r in rows:
                if r['status'] == 'success':
                    break
                consecutive += 1
            last_error = next((r['error_message'] for r in rows if r['status'] != 'success'), None)
            last_success = conn.execute('''SELECT MAX(timestamp) FROM posts WHERE page_id=?
                AND status='success' AND COALESCE(source,'goldgen') != 'manual' ''', (page_id,)).fetchone()[0]
            missed = 0
            if has_slots:
                missed = conn.execute('''SELECT COUNT(*) FROM posting_attempts WHERE page_id=?
                    AND status != 'success'
                    AND julianday(slot) >= julianday('now', ?)
                    AND julianday(slot) < julianday('now', '-1 hour')''',
                    (page_id, f'-{days} days')).fetchone()[0]
            attempts = success + failed
            rate = success / attempts if attempts else None
            warnings = []
            if attempts >= MIN_ATTEMPTS and rate is not None and rate < WARN_SUCCESS_RATE:
                warnings.append(f'hanya {success} dari {attempts} percobaan berhasil ({rate:.0%})')
            if consecutive >= WARN_CONSECUTIVE:
                warnings.append(f'{consecutive} percobaan terakhir gagal berturut-turut')
            if missed:
                warnings.append(f'{missed} slot jadwal terlewat tanpa posting')
            report.append({'page_id': page_id, 'page_name': page.get('name') or page.get('page_name') or page_id,
                           'enabled': page.get('enabled', True), 'success': success, 'failed': failed,
                           'success_rate': round(rate, 3) if rate is not None else None,
                           'consecutive_failures': consecutive, 'missed_slots': missed,
                           'last_success': last_success, 'last_error': (last_error or '')[:300] or None,
                           'warnings': warnings})
        return report
    finally:
        conn.close()


def recent_pages(days=WINDOW_DAYS):
    """Page yang aktif memposting dalam jendela, untuk laporan tanpa config."""
    conn = get_db_connection()
    try:
        return [{'page_id': r[0], 'name': r[1]} for r in conn.execute('''
            SELECT page_id, MAX(page_name) FROM posts
            WHERE COALESCE(source,'goldgen') != 'manual'
              AND julianday(timestamp) >= julianday('now', ?)
            GROUP BY page_id''', (f'-{days} days',))]
    finally:
        conn.close()
