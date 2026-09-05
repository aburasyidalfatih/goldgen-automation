#!/usr/bin/env python3
"""
Comment Analyzer - Goldgen Automation
Analisis komentar Facebook untuk extract topik yang diminati audience
dan pengaruhi konten berikutnya.
"""

import json
import sqlite3
import requests
from datetime import datetime, timedelta
from pathlib import Path
from core.database import get_db_connection, init_db
from core.config import CONFIG_PATH
from core.safe_log import redact

# Hook yang benar-benar dikenali sistem. Editor AI hanya menghasilkan label dari
# daftar ini, dan prompt caption hanya bisa menindaklanjuti label dari daftar ini.
# Apa pun di luar ini (mis. "unknown", "high engagement outliers",
# "physics/technical") tidak bisa dieksekusi dan hanya mengotori preferensi.
CANONICAL_HOOKS = ['fear', 'secret', 'mythbuster', 'challenge', 'story', 'fact', 'news']

# Nilai kosong yang sering dikembalikan AI dan tidak boleh masuk prompt
JUNK_VALUES = {
    '', '-', 'n/a', 'na', 'none', 'none identified', 'nothing', 'unknown',
    'not identified', 'no data', 'tidak ada', 'null', 'undefined',
}


def _is_meaningful(value):
    """False untuk nilai kosong/placeholder yang tidak berguna sebagai instruksi AI"""
    if not value or not isinstance(value, str):
        return False
    cleaned = value.strip().lower().strip('.')
    if cleaned in JUNK_VALUES or len(cleaned) < 3:
        return False
    # Buang frasa yang intinya "tidak teridentifikasi"
    return not any(cleaned.startswith(p) for p in ('none ', 'no specific', 'not enough', 'unknown'))


# Sinonim yang sering dikarang editor AI ("mystery", "curiosity", "contrast", ...).
# Tanpa pemetaan ini, label tersebut dibuang dan sinyal pembelajarannya hilang —
# padahal maknanya sama dengan salah satu hook resmi.
# Urutan penting: dicek dari yang paling spesifik.
HOOK_SYNONYMS = [
    ('secret',     ['mystery', 'curiosity', 'curious', 'intrigue', 'insider', 'hidden', 'reveal', 'unknown secret']),
    ('mythbuster', ['myth', 'debunk', 'contrarian', 'contrast', 'comparison', 'misconception', 'wrong', 'truth']),
    ('challenge',  ['quiz', 'guess', 'spot the', 'test yourself', 'game', 'puzzle']),
    ('story',      ['experience', 'personal', 'journey', 'testimonial', 'anecdote', 'memoir']),
    ('fear',       ['warning', 'danger', 'mistake', 'loss', 'risk', 'costly']),
    ('fact',       ['science', 'scientific', 'geology', 'geological', 'data', 'educational',
                    'technical', 'how-to', 'authority', 'expertise', 'informative']),
    ('news',       ['breaking', 'report', 'announcement', 'update']),
]


def normalize_hook(raw):
    """Petakan label hook bebas dari AI ke salah satu CANONICAL_HOOKS.

    Return None kalau tidak cocok — lebih baik tidak memaksakan gaya hook
    daripada menyuruh AI memakai gaya 'UNKNOWN (HIGH ENGAGEMENT OUTLIERS)'.
    """
    if not raw:
        return None
    text = str(raw).lower()
    if 'unknown' in text:
        return None

    # 1. Nama resmi disebut langsung
    for hook in CANONICAL_HOOKS:
        if hook in text:
            return hook

    # 2. Sinonim — editor kadang mengarang istilah sendiri
    for hook, aliases in HOOK_SYNONYMS:
        if any(alias in text for alias in aliases):
            return hook

    return None


class CommentAnalyzer:
    def __init__(self, config_path=CONFIG_PATH):
        with open(config_path, 'r') as f:
            self.config = json.load(f)

        self.gemini_api_key = self.config['gemini_api_key']
        self.text_model = self.config.get('text_model', 'gemini-3.5-flash')
        self.fanspages = [fp for fp in self.config.get('fanspages', []) if fp.get('enabled', True)]
        self.db_path = 'data/posts.db'
        self._init_db()

    def _init_db(self):
        """Initialize database (skema tunggal ada di core/database.py)"""
        init_db()

    def capture_due_snapshots(self):
        """Collect once at 48–50 hours, independently of content generation."""
        fields = ('id,comments.limit(0).summary(true),'
                  'reactions.type(LIKE).limit(0).summary(total_count).as(like_count),'
                  'reactions.type(LOVE).limit(0).summary(total_count).as(love),'
                  'reactions.type(HAHA).limit(0).summary(total_count).as(haha),'
                  'reactions.type(WOW).limit(0).summary(total_count).as(wow)')
        for page in self.fanspages:
            conn = get_db_connection()
            rows = conn.execute('''
                SELECT p.fb_post_id FROM posts p
                LEFT JOIN engagement_snapshots s ON s.fb_post_id=p.fb_post_id AND s.age_hours=48
                WHERE p.page_id=? AND p.status='success' AND p.fb_post_id IS NOT NULL
                  AND s.fb_post_id IS NULL
                  AND (julianday('now')-julianday(p.timestamp))*24 BETWEEN 48 AND 50
                ORDER BY julianday(p.timestamp) LIMIT 20
            ''', (page['page_id'],)).fetchall()
            conn.close()
            for row in rows:
                try:
                    post_id = row['fb_post_id']
                    response = requests.get(f'https://graph.facebook.com/v18.0/{post_id}',
                                            params={'fields': fields, 'access_token': page['access_token']},
                                            timeout=30)
                    response.raise_for_status()
                    data = response.json()
                    values = [data.get(k, {}).get('summary', {}).get('total_count')
                              for k in ('like_count', 'love', 'haha', 'wow', 'comments')]
                    if any(type(v) is not int or v < 0 for v in values):
                        raise ValueError('Metrik snapshot tidak lengkap; akan dicoba kembali')
                    clicks = self.fetch_post_clicks(post_id, page['access_token'])
                    conn = get_db_connection()
                    try:
                        with conn:
                            conn.execute('''INSERT OR IGNORE INTO engagement_snapshots
                                (fb_post_id,age_hours,likes,comments,clicks)
                                SELECT ?,48,?,?,? WHERE EXISTS (
                                  SELECT 1 FROM posts WHERE fb_post_id=?
                                  AND (julianday('now')-julianday(timestamp))*24 BETWEEN 48 AND 50)
                            ''', (post_id, sum(values[:4]), values[4], clicks, post_id))
                    finally:
                        conn.close()
                except Exception as exc:
                    print(f'Snapshot {row["fb_post_id"]} gagal: {redact(exc)}')

    def _get_hook_types(self, fb_post_ids):
        """Ambil hook_type untuk banyak post sekaligus (1 query, bukan 1 koneksi per post)"""
        if not fb_post_ids:
            return {}
        try:
            conn = get_db_connection()
            placeholders = ','.join('?' * len(fb_post_ids))
            rows = conn.execute(
                f"SELECT fb_post_id, hook_type FROM posts WHERE fb_post_id IN ({placeholders})",
                list(fb_post_ids)
            ).fetchall()
            conn.close()
            return {r['fb_post_id']: r['hook_type'] for r in rows if r['hook_type']}
        except Exception as e:
            print(f"   ⚠️ Gagal mengambil hook_type dari DB: {redact(e)}")
            return {}

    def _page_insight(self, page_id, access_token, metric):
        """Ambil nilai terbaru sebuah metrik level page (None kalau tidak tersedia)"""
        try:
            r = requests.get(
                f"https://graph.facebook.com/v18.0/{page_id}/insights",
                params={'access_token': access_token, 'metric': metric, 'period': 'day'},
                timeout=30
            ).json()
            data = r.get('data') or []
            if data and data[0].get('values'):
                return data[0]['values'][-1].get('value')
        except Exception:
            pass
        return None

    def capture_page_stats(self, page_id, access_token):
        """Rekam ukuran audiens & kesehatan jangkauan page (sekali per hari).

        Tanpa angka ini, penurunan engagement tidak bisa dibedakan antara
        "konten memburuk" dan "postingan tidak sampai ke orang".

        page_post_engagements sangat berguna: ia mengukur total interaksi
        halaman per hari, terlepas dari berapa kali kita posting. Kalau
        pengikut stabil tapi angka ini terjun, masalahnya distribusi.
        """
        try:
            r = requests.get(
                f"https://graph.facebook.com/v18.0/{page_id}",
                params={'access_token': access_token, 'fields': 'fan_count,followers_count'},
                timeout=30
            ).json()
            if 'fan_count' not in r and 'followers_count' not in r:
                return None

            # Metrik ini hanya terisi kalau token punya read_insights
            engagements = self._page_insight(page_id, access_token, 'page_post_engagements')
            views = self._page_insight(page_id, access_token, 'page_views_total')

            conn = get_db_connection()
            conn.execute('''
                INSERT OR REPLACE INTO page_stats
                    (page_id, captured_date, fan_count, followers_count, post_engagements, page_views)
                VALUES (?, date('now'), ?, ?, ?, ?)
            ''', (page_id, r.get('fan_count'), r.get('followers_count'), engagements, views))
            conn.commit()
            conn.close()

            if engagements is not None:
                print(f"   📊 Interaksi halaman hari ini: {engagements} | kunjungan: {views}")
            return r.get('followers_count') or r.get('fan_count')
        except Exception as e:
            print(f"   ⚠️ Gagal merekam statistik page: {redact(e)}")
            return None

    def fetch_post_clicks(self, fb_post_id, access_token):
        """Read post clicks when available. Clicks are not reach or unique viewers."""
        try:
            r = requests.get(
                f"https://graph.facebook.com/v18.0/{fb_post_id}/insights",
                params={'access_token': access_token, 'metric': 'post_clicks'},
                timeout=30
            ).json()
            data = r.get('data') or []
            if data and data[0].get('values'):
                return data[0]['values'][0].get('value')
        except Exception:
            pass
        return None

    def get_recent_comments(self, page_id, access_token, days=3):
        """Ambil komentar yang dibuat dalam N hari terakhir, dari 30 postingan terakhir"""
        url = f"https://graph.facebook.com/v18.0/{page_id}/posts"
        params = {
            'access_token': access_token,
            'fields': 'id,message,created_time',
            'limit': 30
        }
        try:
            response = requests.get(url, params=params, timeout=30)
            posts = response.json().get('data', [])
        except Exception as e:
            print(f"❌ Error getting posts: {redact(e)}")
            return []

        cutoff = datetime.now() - timedelta(days=days)
        all_comments = []
        hook_types = self._get_hook_types([p['id'] for p in posts])

        for post in posts:
            hook_type = hook_types.get(post['id'], "Unknown")

            # Get comments
            comments_url = f"https://graph.facebook.com/v18.0/{post['id']}/comments"
            try:
                r = requests.get(comments_url, params={
                    'access_token': access_token,
                    'fields': 'id,message,from,created_time',
                    'limit': 50
                }, timeout=30)
                comments = r.json().get('data', [])
                
                filtered = []
                for c in comments:
                    if c.get('from', {}).get('id') == page_id:
                        continue
                    if not c.get('message'):
                        continue
                        
                    # Filter komentar berdasarkan tanggal pembuatannya
                    if 'created_time' in c:
                        try:
                            comment_time = datetime.strptime(c['created_time'], '%Y-%m-%dT%H:%M:%S+0000')
                            if comment_time < cutoff:
                                continue
                        except Exception:
                            pass
                            
                    filtered.append(c)
                    
                all_comments.extend([f"[HOOK: {hook_type}] {c['message']}" for c in filtered])
            except Exception:
                continue

        return all_comments

    def get_silent_engagement_metrics(self, page_id, access_token, days=3):
        """Ambil metrik Like, Share, dan Reactions dari postingan untuk mendeteksi emosi audiens (positif & negatif)"""
        url = f"https://graph.facebook.com/v18.0/{page_id}/posts"
        params = {
            'access_token': access_token,
            'fields': 'id,message,created_time,likes.summary(true),comments.summary(true),shares,reactions.type(LOVE).limit(0).summary(total_count).as(love),reactions.type(HAHA).limit(0).summary(total_count).as(haha),reactions.type(WOW).limit(0).summary(total_count).as(wow),reactions.type(ANGRY).limit(0).summary(total_count).as(angry),reactions.type(SAD).limit(0).summary(total_count).as(sad)',
            'limit': 30
        }
        try:
            response = requests.get(url, params=params, timeout=30)
            posts = response.json().get('data', [])
        except Exception as e:
            print(f"❌ Error getting metrics: {redact(e)}")
            return []

        # Perluas jangkauan keviralan bisu menjadi 14 hari ke belakang
        silent_cutoff = datetime.now() - timedelta(days=14)
        metrics = []
        engagement_samples = []  # untuk update baseline
        perf_rows = []           # performa per-post untuk pembelajaran layout
        hook_types = self._get_hook_types([p['id'] for p in posts])

        for post in posts:
            try:
                post_time = datetime.strptime(post['created_time'], '%Y-%m-%dT%H:%M:%S+0000')
                if post_time < silent_cutoff:
                    continue
            except Exception:
                continue

            likes = post.get('likes', {}).get('summary', {}).get('total_count', 0)
            shares = post.get('shares', {}).get('count', 0)
            love = post.get('love', {}).get('summary', {}).get('total_count', 0)
            haha = post.get('haha', {}).get('summary', {}).get('total_count', 0)
            wow = post.get('wow', {}).get('summary', {}).get('total_count', 0)
            angry = post.get('angry', {}).get('summary', {}).get('total_count', 0)
            sad = post.get('sad', {}).get('summary', {}).get('total_count', 0)

            comments_count = post.get('comments', {}).get('summary', {}).get('total_count', 0)
            total = likes + shares + love + haha + wow + angry + sad
            engagement_samples.append(total)


            # Simpan performa per-post supaya pemilihan LAYOUT bisa belajar dari
            # data nyata. Sebelumnya angka ini cuma dipakai sesaat lalu dibuang,
            # dan engagement_cache hanya terisi kalau dashboard Analytics dibuka.
            perf_rows.append((post['id'], likes + love + haha + wow, comments_count))

            # Ambang diturunkan agar page kecil ikut belajar. Dengan ambang lama (5),
            # page dengan engagement rendah tidak pernah menghasilkan riset sama
            # sekali, sehingga kontennya tidak pernah membaik (jebakan cold-start).
            if total >= 2:
                # Get hook_type from DB, fallback ke deteksi keyword dari caption jika Unknown
                message = post.get('message') or ''
                hook_type = hook_types.get(post['id']) or "Unknown"

                # Fallback: deteksi hook dari pola caption (keyword-based heuristics)
                if hook_type == "Unknown" and message:
                    msg_lower = message.lower()
                    if any(k in msg_lower for k in ['warning', 'danger', 'mistake', 'stop ', 'never ', 'avoid']):
                        hook_type = "Fear (inferred)"
                    elif any(k in msg_lower for k in ['secret', 'nobody talks', 'insider', "don't know", 'hidden']):
                        hook_type = "Secret (inferred)"
                    elif any(k in msg_lower for k in ['myth', 'wrong', 'truth', 'actually']):
                        hook_type = "Mythbuster (inferred)"
                    elif any(k in msg_lower for k in ['story', 'i remember', 'years ago', 'back in']):
                        hook_type = "Story (inferred)"
                    elif any(k in msg_lower for k in ['can you', 'quiz', 'guess', 'spot the']):
                        hook_type = "Challenge (inferred)"
                    elif any(k in msg_lower for k in ['did you know', 'fact', 'science', 'because']):
                        hook_type = "Fact (inferred)"

                metrics.append({
                    'hook_type': hook_type,
                    'likes': likes, 'shares': shares,
                    'love': love, 'haha': haha, 'wow': wow,
                    'angry': angry, 'sad': sad,
                    'total': total,
                    'message_preview': message[:120]
                })


        # Simpan performa per-post ke engagement_cache — inilah bahan bakar
        # pembelajaran layout di goldgen_service._get_layout_performance()
        if perf_rows:
            try:
                conn = get_db_connection()
                conn.executemany('''
                    INSERT INTO engagement_cache (fb_post_id, likes, comments, cached_at)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(fb_post_id) DO UPDATE SET
                        likes = excluded.likes,
                        comments = excluded.comments,
                        cached_at = CURRENT_TIMESTAMP
                ''', perf_rows)
                conn.commit()
                conn.close()
                print(f"   💾 Performa {len(perf_rows)} postingan tersimpan untuk pembelajaran layout")
            except Exception as e:
                print(f"   ⚠️ Gagal menyimpan performa post: {redact(e)}")

        # Update baseline engagement untuk normalisasi (Tahap 4)
        #
        # Analisis ini jalan tiap siklus posting di atas 30 post yang sebagian besar sama,
        # jadi rata-rata kumulatif akan menghitung post yang sama ratusan kali dan membuat
        # sample_count membengkak sampai baseline praktis membeku.
        # Solusi: Exponential Moving Average — baseline mengikuti performa terkini,
        # dan sample_count merekam ukuran batch terakhir (bukan akumulasi semu).
        if engagement_samples:
            try:
                batch_avg = sum(engagement_samples) / len(engagement_samples)
                alpha = 0.3  # bobot data baru
                conn = get_db_connection()
                conn.execute('''
                    INSERT INTO engagement_baseline (page_id, avg_engagement, sample_count, last_updated)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(page_id) DO UPDATE SET
                        avg_engagement = CASE
                            WHEN engagement_baseline.avg_engagement > 0
                                THEN engagement_baseline.avg_engagement * (1 - ?) + ? * ?
                            ELSE ?
                        END,
                        sample_count = ?,
                        last_updated = CURRENT_TIMESTAMP
                ''', (page_id, batch_avg, len(engagement_samples),
                      alpha, batch_avg, alpha, batch_avg, len(engagement_samples)))
                conn.commit()
                conn.close()
            except Exception as e:
                print(f"   ⚠️ Failed to update engagement baseline: {redact(e)}")

        return metrics

    def get_most_engaged_image(self, page_id, access_token, days=3):
        """Cari file gambar lokal dari postingan dengan engagement tertinggi.

        Dua perbaikan penting dibanding versi lama:
        1. Peringkat memakai like + komentar + share, bukan komentar saja.
        2. Kandidat yang file gambarnya sudah terhapus (cleanup 3 hari) dilewati,
           lalu lanjut ke kandidat berikutnya. Versi lama langsung menyerah dan
           mengembalikan None, sehingga Vision AI sering tidak pernah jalan.
        """
        import os

        url = f"https://graph.facebook.com/v18.0/{page_id}/posts"
        try:
            r = requests.get(url, params={
                'access_token': access_token,
                'fields': 'id,created_time,likes.summary(true),comments.summary(true),shares',
                'limit': 25
            }, timeout=30)
            posts = r.json().get('data', [])
        except Exception as e:
            print(f"   ⚠️  Gagal mengambil postingan untuk Vision AI: {redact(e)}")
            return None

        cutoff = datetime.now() - timedelta(days=days)
        ranked = []

        for post in posts:
            try:
                if datetime.strptime(post['created_time'], '%Y-%m-%dT%H:%M:%S+0000') < cutoff:
                    continue
                likes = post.get('likes', {}).get('summary', {}).get('total_count', 0)
                comments = post.get('comments', {}).get('summary', {}).get('total_count', 0)
                shares = post.get('shares', {}).get('count', 0)
                ranked.append((likes + comments + shares, post['id']))
            except Exception:
                continue

        if not ranked:
            return None

        ranked.sort(reverse=True)
        try:
            conn = get_db_connection()
            for score, fb_post_id in ranked:
                row = conn.execute(
                    "SELECT image_path FROM posts WHERE fb_post_id = ?", (fb_post_id,)
                ).fetchone()
                if row and row['image_path'] and os.path.exists(row['image_path']):
                    conn.close()
                    print(f"   🏆 Gambar terbaik: engagement {score} ({os.path.basename(row['image_path'])})")
                    return row['image_path']
            conn.close()
        except Exception as e:
            print(f"   ⚠️  Gagal mencari gambar terbaik: {redact(e)}")

        print("   ⚠️  Tidak ada gambar pemenang yang filenya masih tersimpan")
        return None

    def analyze_vision_styles(self, image_path):
        """Use Gemini Vision to extract winning visual aesthetics from the top image.

        Model diambil dari config (self.text_model), BUKAN hardcoded. Versi lama
        memakai 'gemini-1.5-flash' yang sudah dipensiunkan Google (404), sehingga
        seluruh analisis visual gagal diam-diam dan tidak pernah berkontribusi.
        """
        import base64
        import os
        import re
        if not image_path or not os.path.exists(image_path):
            print(f"   ⚠️  Vision AI dilewati: file gambar tidak ada ({image_path})")
            return []

        try:
            with open(image_path, "rb") as f:
                encoded_image = base64.b64encode(f.read()).decode("utf-8")

            prompt = "Analyze this top-performing gold prospecting image. What specific visual aesthetics make it highly engaging to an American audience? (e.g. muddy hands, extreme macro shot, sun glare, rugged realism). Reply ONLY with a JSON array of strings representing the 3-5 best visual keywords. Example: [\"macro photography\", \"muddy realism\"]"

            url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.text_model}:generateContent?key={self.gemini_api_key}"
            payload = {
                "contents": [{
                    "parts": [
                        {"text": prompt},
                        {"inlineData": {"mimeType": "image/png", "data": encoded_image}}
                    ]
                }]
            }
            response = requests.post(url, json=payload, timeout=60)
            data = response.json()

            # Jangan telan error diam-diam — tampilkan alasan sebenarnya
            if 'candidates' not in data:
                err = (data.get('error') or {}).get('message', str(data)[:150])
                print(f"   ❌ Vision AI gagal (model={self.text_model}): {redact(err)[:180]}")
                return []

            text = data['candidates'][0]['content']['parts'][0]['text']
            match = re.search(r'\[.*\]', text, re.DOTALL)
            if match:
                styles = json.loads(match.group(0))
                return [s for s in styles if isinstance(s, str) and _is_meaningful(s)]
        except Exception as e:
            print(f"   ❌ Vision AI Error: {type(e).__name__}: {redact(e)}")
        return []

    def analyze_with_gemini(self, comments, page_name, silent_metrics=None, page_id=None):
        """Kirim komentar dan metrik ke Gemini untuk dianalisis"""
        if not comments and not silent_metrics:
            return None

        # Sanitize comments
        clean_comments = []
        if comments:
            for c in comments[:100]:
                c = c.replace('"', "'").replace('\\', '').replace('\n', ' ').strip()
                if c:
                    clean_comments.append(c)

        comments_text = '\n'.join([f"- {c}" for c in clean_comments]) if clean_comments else "No text comments."
        
        metrics_text = ""
        if silent_metrics:
            # Ambil baseline untuk normalisasi (post di atas rata-rata = outperforming)
            baseline = 0
            try:
                conn = get_db_connection()
                row = conn.execute('SELECT avg_engagement FROM engagement_baseline WHERE page_id = ?', (page_id,)).fetchone()
                if row:
                    baseline = row['avg_engagement'] or 0
                conn.close()
            except Exception:
                pass

            lines = []
            for m in silent_metrics:
                if isinstance(m, dict):
                    vs_avg = ""
                    if baseline > 0:
                        ratio = m['total'] / baseline
                        vs_avg = f" ({ratio:.1f}x page average)" if ratio >= 1.2 else (f" (BELOW average: {ratio:.1f}x)" if ratio <= 0.8 else "")
                    neg = ""
                    if m.get('angry', 0) + m.get('sad', 0) >= 3:
                        neg = f" ⚠️ NEGATIVE REACTIONS (Angry: {m.get('angry',0)}, Sad: {m.get('sad',0)})"
                    lines.append(
                        f"- [HOOK: {m['hook_type']}] Likes: {m['likes']}, Shares: {m['shares']}, "
                        f"Love: {m['love']}, Haha: {m['haha']}, Wow: {m['wow']}{vs_avg}{neg} | Post: \"{m['message_preview']}\""
                    )
                else:
                    # Backward compatibility jika masih string
                    lines.append(f"- {m}")
            metrics_text = (
                f"SILENT ENGAGEMENT METRICS (page average engagement: {baseline:.0f}):\n" + "\n".join(lines)
            )

        prompt = f"""Analyze this Facebook engagement data from a gold prospecting page "{page_name}".
Some data has a prefix like [HOOK: Fear] which indicates the psychological hook used in the post.

{metrics_text}

TEXT COMMENTS:
{comments_text}

Extract any preferred visual/image styles mentioned by the audience. Also suggest improvements for the AI prompt (for text or image generation) based on their complaints, questions, or engagement.
Evaluate which HOOK generated the most engagement or best quality comments, and report it in 'best_hook' (ONE word only: Fear, Secret, Mythbuster, Challenge, Story, Fact, or News).

CRITICAL — 'suggested_topics' MUST contain actual SUBJECT MATTER the audience
wants to learn about (e.g. "black sand indicators", "reading bedrock cracks",
"telling gold from pyrite"). Do NOT put hook styles there — the hook belongs in
'best_hook'. Give at least 2 concrete subject topics drawn from what people
actually asked about or reacted to.

IMPORTANT INSTRUCTION FOR EMOTIONAL REACTIONS:
- If a hook receives high 'Haha' reactions, it means the audience loves humor/memes. Suggest visual styles that are funny or absurd.
- If a hook receives high 'Wow' reactions, they want to see rare, majestic, or shocking gold nuggets. Suggest "rare/majestic" visual styles.
- If a hook receives high 'Love' reactions, the aesthetic is perfect. Strongly reinforce those visual styles in your suggestions.
- Posts marked with "⚠️ NEGATIVE REACTIONS" (Angry/Sad) are content the audience DISLIKES or finds offensive/misleading. Identify the pattern (topic, hook, or style) and add it to 'avoid_patterns' so we never repeat it.
- Posts performing "BELOW average" should be treated as weak content — identify what made them boring and add to 'avoid_patterns'.
- Prioritize hooks/topics from posts performing ABOVE the page average (marked with e.g. "2.5x page average") — those are the real winners for THIS audience size, not just raw big numbers.

REPLY ONLY WITH THIS EXACT JSON FORMAT:
{{
    "top_keywords": ["keyword1", "keyword2"],
    "requested_topics": ["topic audience wants to learn"],
    "sentiment": "positive/neutral/negative",
    "best_hook": "Secret",
    "suggested_topics": [
        {{"topic": "reading bedrock cracks", "reason": "Ditanyakan berulang di komentar"}},
        {{"topic": "telling gold from pyrite", "reason": "Reaksi Wow paling tinggi"}}
    ],
    "avoid_patterns": ["complaints, boring things, or patterns that triggered Angry/Sad reactions"],
    "preferred_visual_styles": ["realistic", "macro", "infographic"],
    "prompt_improvement_suggestions": ["use more casual tone", "explain X better"]
}}
"""

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.text_model}:generateContent?key={self.gemini_api_key}"
        try:
            response = requests.post(url, json={
                'contents': [{'parts': [{'text': prompt}]}],
                'generationConfig': {'temperature': 0.3, 'maxOutputTokens': 2048}
            }, timeout=30)
            text = response.json()['candidates'][0]['content']['parts'][0]['text']
            # Clean markdown code block
            text = text.strip()
            if '```' in text:
                text = text.split('```')[1]
                if text.startswith('json'):
                    text = text[4:]
            text = text.strip()
            # Try parse, fallback to extract JSON object
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                # Extract JSON object between first { and last }
                start = text.find('{')
                end = text.rfind('}')
                if start != -1 and end != -1:
                    return json.loads(text[start:end+1])
                return None
        except Exception as e:
            print(f"❌ Gemini analysis error: {redact(e)}")
            return None

    def save_insight(self, page_id, page_name, total_comments, analysis, weight=1):
        """Simpan hasil analisis ke DB"""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO comment_insights 
            (page_id, page_name, total_comments_analyzed, top_keywords, requested_topics, sentiment, suggested_topics, raw_analysis)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            page_id, page_name, total_comments,
            json.dumps(analysis.get('top_keywords', [])),
            json.dumps(analysis.get('requested_topics', [])),
            analysis.get('sentiment', 'neutral'),
            json.dumps(analysis.get('suggested_topics', [])),
            json.dumps(analysis)
        ))

        # best_hook disimpan sebagai preferensi hook tersendiri. Dulu hook
        # diminta ikut masuk 'suggested_topics', sehingga skornya menumpuk
        # tiap siklus dan menenggelamkan topik konten yang sesungguhnya.
        hook_terbaik = normalize_hook(analysis.get('best_hook'))
        daftar = list(analysis.get('suggested_topics') or [])
        if hook_terbaik:
            daftar.append({'topic': f'hook: {hook_terbaik}'})

        # Update topic_preferences berdasarkan suggested topics
        for item in daftar:
            if not isinstance(item, dict):
                continue
            topic_kw = (item.get('topic') or '').lower().strip()

            # Saring sampah sebelum masuk DB — preferensi yang tidak bisa
            # dieksekusi hanya akan menggeser sinyal yang benar-benar berguna
            if not _is_meaningful(topic_kw):
                continue
            if topic_kw.startswith('hook'):
                hook = normalize_hook(topic_kw)
                if not hook:
                    print(f"   ⏭️  Preferensi hook diabaikan (tidak dikenali): {topic_kw[:50]}")
                    continue
                topic_kw = f"hook: {hook}"

            if topic_kw:
                # Cek apakah sudah ada, kalau ada boost score-nya
                existing = cursor.execute(
                    'SELECT id, boost_score FROM topic_preferences WHERE topic_keyword = ? AND page_id = ?', (topic_kw, page_id)
                ).fetchone()
                if existing:
                    cursor.execute(
                        'UPDATE topic_preferences SET boost_score = boost_score + ?, last_updated = CURRENT_TIMESTAMP WHERE id = ?',
                        (weight, existing[0])
                    )
                else:
                    cursor.execute(
                        'INSERT INTO topic_preferences (page_id, topic_keyword, boost_score) VALUES (?, ?, ?)',
                        (page_id, topic_kw, weight)
                    )

        conn.commit()
        conn.close()

    def apply_time_decay(self, page_id=None):
        """Diskon boost_score lama sebesar 10% untuk memprioritaskan tren terbaru (Time Decay)"""
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            if page_id:
                # Hanya decay untuk page ini (JIT Mode)
                cursor.execute('''
                    UPDATE topic_preferences 
                    SET boost_score = MAX(1, CAST(boost_score * 0.9 AS INTEGER))
                    WHERE boost_score > 1 AND page_id = ?
                ''', (page_id,))
                print(f"   ⏳ Time Decay applied to topic_preferences for page {page_id}.")
            else:
                # Decay untuk semua page (Legacy mode)
                cursor.execute('''
                    UPDATE topic_preferences 
                    SET boost_score = MAX(1, CAST(boost_score * 0.9 AS INTEGER))
                    WHERE boost_score > 1
                ''')
                print("   ⏳ Time Decay applied to topic_preferences globally.")
            conn.commit()
        except Exception as e:
            print(f"   ❌ Failed to apply time decay: {redact(e)}")
        finally:
            conn.close()

    def get_top_preferences(self, limit=10, page_id=None):
        """Ambil topik dengan boost score tertinggi untuk dipakai di content generation"""
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if page_id:
            rows = cursor.execute(
                'SELECT topic_keyword, boost_score FROM topic_preferences WHERE page_id = ? ORDER BY boost_score DESC LIMIT ?',
                (page_id, limit)
            ).fetchall()
        else:
            rows = cursor.execute(
                'SELECT topic_keyword, boost_score FROM topic_preferences ORDER BY boost_score DESC LIMIT ?',
                (limit,)
            ).fetchall()
        conn.close()
        return [{'keyword': r[0], 'score': r[1]} for r in rows]

    def get_latest_insight(self):
        """Ambil insight terbaru untuk ditampilkan di dashboard"""
        conn = get_db_connection()
        cursor = conn.cursor()
        row = cursor.execute(
            'SELECT * FROM comment_insights ORDER BY analyzed_at DESC LIMIT 1'
        ).fetchone()
        conn.close()
        if not row:
            return None
        # Row factory sudah sqlite3.Row, jadi dict() aman terhadap perubahan urutan kolom
        return dict(row)

    def run(self):
        """Main: analisis komentar semua page (Legacy)"""
        print("=" * 60)
        print("🔍 COMMENT ANALYZER - GOLDGEN")
        print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)

        for page in self.fanspages:
            self.analyze_single_page(page)

        print("\n▶ Menerapkan efek peluruhan waktu (Time Decay) pada database...")
        self.apply_time_decay()
        
        # Tampilkan top preferences
        prefs = self.get_top_preferences(5)
        if prefs:
            print(f"\n🎯 TOP AUDIENCE PREFERENCES:")
            for p in prefs:
                print(f"   [{p['score']}x] {p['keyword']}")

        print("\n✅ Analysis complete!")

    def analyze_single_page(self, page_config):
        """Menganalisa satu spesifik fanspage secara Just-In-Time"""
        page_name = page_config['name']
        page_id = page_config['page_id']
        access_token = page_config['access_token']

        print(f"\n▶ [JIT ML RESEARCH] Menganalisa halaman: {page_name}")

        # Rekam ukuran audiens supaya engagement bisa dinilai relatif, bukan mutlak
        pengikut = self.capture_page_stats(page_id, access_token)
        if pengikut:
            print(f"   👥 Pengikut: {pengikut:,}")

        # Ambil komentar dari 3 hari terakhir
        comments = self.get_recent_comments(page_id, access_token, days=3)
        
        # Ambil metrik diam (Likes & Shares)
        silent_metrics = self.get_silent_engagement_metrics(page_id, access_token, days=3)
        if silent_metrics:
            print(f"   📈 Menemukan {len(silent_metrics)} postingan dengan Silent Engagement tinggi")

        # Riset hanya dilewati kalau benar-benar TIDAK ADA sinyal apa pun.
        # Ambang lama (butuh >=3 komentar) membuat page kecil tidak pernah belajar,
        # padahal justru merekalah yang paling perlu perbaikan konten.
        # Bukti lemah tetap aman: bobotnya kecil (lihat perhitungan weight di bawah).
        if not comments and not silent_metrics:
            print(f"   ⚠️ Tidak ada komentar maupun engagement sama sekali, riset dilewati")
            return False

        print(f"   🤖 Menganalisa {len(comments)} komentar dan {len(silent_metrics)} metrik dengan Gemini...")
        analysis = self.analyze_with_gemini(comments, page_name, silent_metrics=silent_metrics, page_id=page_id)
        
        if not analysis:
            print(f"   ❌ Gagal menganalisa dengan Gemini")
            return False

        print(f"   👁️  Mencari postingan visual terbaik (Vision AI)...")
        best_img = self.get_most_engaged_image(page_id, access_token)
        if best_img:
            vision_styles = self.analyze_vision_styles(best_img)
            if vision_styles:
                print(f"   ✅ Vision AI menemukan gaya visual pemenang: {vision_styles}")
                # Gabungkan, jangan timpa: gaya dari Vision AI (melihat gambar asli)
                # diprioritaskan, gaya dari analisis komentar tetap dipertahankan.
                text_styles = [s for s in (analysis.get('preferred_visual_styles') or [])
                               if isinstance(s, str) and _is_meaningful(s)]
                merged, seen = [], set()
                for style in vision_styles + text_styles:
                    key = style.strip().lower()
                    if key not in seen:
                        seen.add(key)
                        merged.append(style)
                analysis['preferred_visual_styles'] = merged[:6]
            else:
                print(f"   ⚠️  Vision AI gagal mengekstrak gaya visual")

        # Hitung Bobot Keviralan (Weighted Scoring)
        weight = 1 + int(len(comments) * 0.1) + int(len(silent_metrics or []) * 0.5)
        
        self.save_insight(page_id, page_name, len(comments), analysis, weight=weight)
        print(f"   ✅ Analisis JIT berhasil disimpan (Sentimen: {analysis.get('sentiment')}) dengan Bobot: {weight}")
        
        # Terapkan peluruhan (Time Decay) HANYA untuk page ini setiap kali ada analisis baru
        self.apply_time_decay(page_id=page_id)
        
        return True

if __name__ == '__main__':
    analyzer = CommentAnalyzer()
    analyzer.run()
