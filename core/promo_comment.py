"""Komentar promo pertama dari page di setiap postingan GoldGen.

Tautan sengaja tidak ditaruh di caption: Facebook cenderung menurunkan
jangkauan postingan yang deskripsinya berisi tautan keluar.

Komentar ini milik page sendiri, jadi bukan engagement audiens. Hitungan
komentar yang disimpan untuk pembelajaran dikurangi satu lewat
audience_comments(), supaya postingan sesudah fitur ini tidak tampak lebih
ramai daripada postingan sebelumnya.
"""
import requests

from core.database import get_db_connection
from core.meta_api import GRAPH_API_BASE

PROMO_LINE = 'Find your first flake of gold in 7 trips : https://bit.ly/3Tpd46J'
_PENDING = 'pending'
# Postingan yang lebih tua dari ini tidak disusul, supaya deploy pertama tidak
# menghujani arsip lama dengan komentar promo.
CATCH_UP_HOURS = 24


def _claim(fb_post_id):
    """Klaim atomik agar dua proses tidak mengirim promo ganda."""
    conn = get_db_connection()
    try:
        with conn:
            return conn.execute(
                "UPDATE posts SET promo_comment_id=? WHERE fb_post_id=? AND promo_comment_id IS NULL",
                (_PENDING, fb_post_id)).rowcount == 1
    finally:
        conn.close()


def _finish(fb_post_id, comment_id):
    conn = get_db_connection()
    try:
        with conn:
            conn.execute("UPDATE posts SET promo_comment_id=? WHERE fb_post_id=? AND promo_comment_id=?",
                         (comment_id, fb_post_id, _PENDING))
    finally:
        conn.close()


def send_promo_comment(fb_post_id, access_token):
    """Kirim komentar promo. Mengembalikan (comment_id, error)."""
    if not fb_post_id or not _claim(fb_post_id):
        return None, 'sudah dikirim atau sedang dikirim'
    try:
        response = requests.post(f"{GRAPH_API_BASE}/{fb_post_id}/comments",
                                 data={'message': PROMO_LINE, 'access_token': access_token},
                                 timeout=30)
    except Exception as exc:
        # Hasilnya tidak pasti; klaim dibiarkan agar tidak berisiko dobel.
        return None, f'hasil kirim belum pasti: {type(exc).__name__}'
    if response.status_code != 200:
        _finish(fb_post_id, None)  # pasti gagal: lepas klaim, coba lagi nanti
        return None, f'Facebook menolak ({response.status_code})'
    comment_id = (response.json() or {}).get('id') or 'sent'
    _finish(fb_post_id, comment_id)
    return comment_id, None


def send_pending_promo_comments(fanspages):
    """Susulkan promo untuk postingan GoldGen baru yang belum mendapatkannya."""
    tokens = {str(p.get('page_id')): p.get('access_token') for p in fanspages}
    conn = get_db_connection()
    try:
        rows = conn.execute(f'''
            SELECT fb_post_id, page_id FROM posts
            WHERE status='success' AND fb_post_id IS NOT NULL AND promo_comment_id IS NULL
              AND COALESCE(source,'goldgen') != 'manual'
              AND (julianday('now') - julianday(timestamp)) * 24 <= {CATCH_UP_HOURS}
        ''').fetchall()
    finally:
        conn.close()
    for row in rows:
        token = tokens.get(str(row['page_id']))
        if token:
            _, error = send_promo_comment(row['fb_post_id'], token)
            if error:
                print(f"   ⚠️  Komentar promo {row['fb_post_id']}: {error}")


def audience_comments(conn, fb_post_id, total):
    """Jumlah komentar tanpa komentar promo milik page sendiri."""
    row = conn.execute("SELECT promo_comment_id FROM posts WHERE fb_post_id=?", (fb_post_id,)).fetchone()
    has_promo = bool(row and row[0] and row[0] != _PENDING)
    return max(0, (total or 0) - (1 if has_promo else 0))
