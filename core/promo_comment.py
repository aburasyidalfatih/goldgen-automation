"""Komentar promo pertama dari page di setiap postingan GoldGen.

Tautan sengaja tidak ditaruh di caption: Facebook cenderung menurunkan
jangkauan postingan yang deskripsinya berisi tautan keluar.

Komentar ini milik page sendiri, jadi bukan engagement audiens. Hitungan
komentar yang disimpan untuk pembelajaran dikurangi satu lewat
audience_comments(), supaya postingan sesudah fitur ini tidak tampak lebih
ramai daripada postingan sebelumnya.
"""
import re
import zlib

import requests

from core.content_quality import FORBIDDEN_IMAGE_TERMS, strip_markdown
from core.database import get_db_connection
from core.meta_api import GRAPH_API_BASE

PROMO_URL = 'https://bit.ly/3Tpd46J'
PROMO_LINE = f'Find your first flake of gold in 7 trips : {PROMO_URL}'
# Dipakai bergiliran bila kalimat dari Gemini tidak tersedia atau tidak lolos,
# supaya komentar bertautan tidak identik di setiap postingan.
FALLBACK_SENTENCES = (
    'Find your first flake of gold in 7 trips',
    'Want your first flake of gold within 7 trips? Start here',
    'Turn your next 7 trips into your first gold flake',
    'Still chasing your first flake? This guide gets you there in 7 trips',
    'New to prospecting? Find your first flake of gold in 7 trips',
)
MAX_SENTENCE_CHARS = 120
_PENDING = 'pending'
# Postingan yang lebih tua dari ini tidak disusul, supaya deploy pertama tidak
# menghujani arsip lama dengan komentar promo.
CATCH_UP_HOURS = 24


def promo_prompt(caption):
    return (
        'Write ONE short English sentence (max 15 words) that invites readers of this '
        'Facebook gold-prospecting post to a beginner guide promising their first flake '
        'of gold in 7 trips. Connect it naturally to the post topic. No link, no hashtags, '
        'no emojis, no quotes, no guarantees. Return only the sentence.\n\n'
        f'POST CAPTION:\n{str(caption or "")[:1500]}')


def clean_sentence(text):
    """Kalimat Gemini yang layak dipakai, atau None."""
    kalimat = strip_markdown(str(text or '')).strip().strip('"\'“”‘’ ').rstrip(':').strip()
    if not kalimat or '\n' in kalimat or len(kalimat) > MAX_SENTENCE_CHARS:
        return None
    lower = kalimat.lower()
    if re.search(r'https?://|www\.|bit\.ly|#', lower):
        return None
    if 'guarantee' in lower or any(term in lower for term in FORBIDDEN_IMAGE_TERMS):
        return None
    return kalimat


def promo_message(fb_post_id, sentence=None):
    """Satu kalimat + tautan. Tautan selalu dari kode, tidak pernah dari model."""
    kalimat = clean_sentence(sentence)
    if not kalimat:
        indeks = zlib.crc32(str(fb_post_id or '').encode()) % len(FALLBACK_SENTENCES)
        kalimat = FALLBACK_SENTENCES[indeks]
    return f'{kalimat}: {PROMO_URL}'


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


def send_promo_comment(fb_post_id, access_token, compose=None, caption=''):
    """Kirim komentar promo. Mengembalikan (comment_id, error).

    compose(caption) boleh mengembalikan satu kalimat pembuka (dari Gemini);
    kegagalannya jatuh ke kalimat cadangan, bukan membatalkan komentar.
    """
    if not fb_post_id or not _claim(fb_post_id):
        return None, 'sudah dikirim atau sedang dikirim'
    sentence = None
    if compose:
        try:
            sentence = compose(caption)
        except Exception:
            sentence = None
    try:
        response = requests.post(f"{GRAPH_API_BASE}/{fb_post_id}/comments",
                                 data={'message': promo_message(fb_post_id, sentence),
                                       'access_token': access_token},
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


def send_pending_promo_comments(fanspages, compose=None):
    """Susulkan promo untuk postingan GoldGen baru yang belum mendapatkannya."""
    tokens = {str(p.get('page_id')): p.get('access_token') for p in fanspages}
    conn = get_db_connection()
    try:
        rows = conn.execute(f'''
            SELECT fb_post_id, page_id, content FROM posts
            WHERE status='success' AND fb_post_id IS NOT NULL AND promo_comment_id IS NULL
              AND COALESCE(source,'goldgen') != 'manual'
              AND (julianday('now') - julianday(timestamp)) * 24 <= {CATCH_UP_HOURS}
        ''').fetchall()
    finally:
        conn.close()
    for row in rows:
        token = tokens.get(str(row['page_id']))
        if token:
            _, error = send_promo_comment(row['fb_post_id'], token, compose, row['content'])
            if error:
                print(f"   ⚠️  Komentar promo {row['fb_post_id']}: {error}")


def audience_comments(conn, fb_post_id, total):
    """Jumlah komentar tanpa komentar promo milik page sendiri."""
    row = conn.execute("SELECT promo_comment_id FROM posts WHERE fb_post_id=?", (fb_post_id,)).fetchone()
    has_promo = bool(row and row[0] and row[0] != _PENDING)
    return max(0, (total or 0) - (1 if has_promo else 0))
