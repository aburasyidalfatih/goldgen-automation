#!/usr/bin/env python3
"""
GoldGen Auto Poster - Automated Facebook Posting
Generates gold price posters and posts to Facebook every 3 hours
"""
from core.meta_api import GRAPH_API_BASE

import os
import json
import sqlite3
import requests
import sys
from datetime import datetime, timedelta
from pathlib import Path
from google import genai
from PIL import Image, ImageDraw, ImageFont
import io
import base64
import time

# Telegram notifier (opsional — no-op kalau kredensial belum dikonfigurasi)
try:
    from telegram_notifier import send_notification
except Exception as _e:
    print(f"⚠️  Telegram notifier tidak tersedia: {_e}")

    def send_notification(msg):
        return False

from core.config import BASE_DIR, DATA_DIR, LOGS_DIR, IMAGES_DIR, DB_PATH, CONFIG_PATH
from core.database import get_db_connection, init_db
from core.art_director import render_art_direction
from core.generation_reliability import UncertainSend


def _gambar_dari_balasan(response):
    """Semua gambar di dalam balasan Gemini, lewat jalur mana pun ia datang.

    `response.parts` adalah jalan pintas SDK dan bisa kosong meski gambarnya
    ada — misalnya ketika balasan hanya terisi di candidates[0].content.parts,
    atau ketika bagian gambarnya berupa inline_data mentah. Membaca satu jalur
    saja membuat gambar yang sebenarnya berhasil dibuat tetap dianggap gagal,
    dan postingan jatuh ke poster teks tanpa ilustrasi.
    """
    from io import BytesIO

    bagian = list(getattr(response, 'parts', None) or [])
    if not bagian:
        for kandidat in (getattr(response, 'candidates', None) or []):
            isi = getattr(kandidat, 'content', None)
            bagian.extend(getattr(isi, 'parts', None) or [])

    for part in bagian:
        gambar = None
        try:
            gambar = part.as_image()
        except Exception:
            pass
        if gambar is None:
            data = getattr(getattr(part, 'inline_data', None), 'data', None)
            if data:
                try:
                    gambar = Image.open(BytesIO(data))
                except Exception:
                    continue
        if gambar is not None:
            yield gambar
from core.model_catalog import image_size_for_model, normalize_image_model
from core.safe_log import redact
from comment_analyzer import CommentAnalyzer

# Analisis komentar paling sering dijalankan sekali per jendela ini per page.
JIT_INTERVAL_HOURS = 12

# Ensure directories exist
DATA_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)
IMAGES_DIR.mkdir(exist_ok=True)

class GoldGenAutoPoster:
    def __init__(self):
        self.load_config()
        self.init_database()
        self.setup_gemini()
        self.cleanup_old_images(days=3)  # Keep for 3 days for Vision AI
    
    def cleanup_old_images(self, days=3):
        """Delete images older than N days to save disk space"""
        try:
            import time
            cutoff = time.time() - (days * 86400)
            deleted = 0
            conn = get_db_connection()
            try:
                protected = {Path(r['image_path']).resolve() for r in conn.execute(
                    "SELECT image_path FROM posts WHERE status != 'success' AND image_path != ''")}
            finally:
                conn.close()
            
            for image_path in IMAGES_DIR.glob('*.png'):
                if image_path.resolve() in protected:
                    continue
                if image_path.stat().st_mtime < cutoff:
                    image_path.unlink()
                    deleted += 1
            
            if deleted > 0:
                print(f"🗑️  Cleaned up {deleted} old image(s)")
        except Exception as e:
            print(f"⚠️  Cleanup error: {e}")
        
    def load_config(self):
        """Load configuration from file"""
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, 'r') as f:
                config = json.load(f)
                self.gemini_api_key = config.get('gemini_api_key')
                self.image_model = normalize_image_model(config.get('image_model'))
                self.text_model = config.get('text_model', 'gemini-3.5-flash')
                self.fanspages = config.get('fanspages', [])
                self.fanspage_delay_minutes = config.get('fanspage_delay_minutes', 60)
                
                # Backward compatibility
                if not self.fanspages and config.get('fb_page_id'):
                    self.fanspages = [{
                        'name': 'Default Page',
                        'page_id': config.get('fb_page_id'),
                        'access_token': config.get('fb_access_token'),
                        'interval_hours': 3,
                        'enabled': True
                    }]
        else:
            raise Exception("Config file not found. Please run setup first.")
    
    def init_database(self):
        """Initialize SQLite database (skema tunggal ada di core/database.py)"""
        init_db()
    
    def setup_gemini(self):
        """Setup Gemini AI with GoldGen style"""
        from goldgen_service import GoldGenService
        self.goldgen = GoldGenService(self.gemini_api_key, model=self.text_model)
    

    def generate_content(self, page_id=None, allow_experiment=False):
        """Generate educational content about gold prospecting"""
        topic = None
        try:
            if allow_experiment:
                from core.layout_experiments import pending
                topic = pending(page_id, self.goldgen.active_layouts)
                if topic:
                    return topic['approved_caption'], topic
            topic = self.goldgen.get_next_topic(page_id)
            caption = self.goldgen.generate_caption(topic, page_id)
            if allow_experiment:
                from core.layout_experiments import enroll
                topic = enroll(page_id, topic, caption, self.goldgen.active_layouts)
            return caption, topic
        except Exception as e:
            # The caller records the failure; never bypass the quality review.
            raise
    
    
    def _review_image(self, image_path, topic, fanspage_name=None):
        """Nilai gambar sebelum tayang, memakai Gemini Vision.

        Caption sudah lama punya juri; gambar tidak. Padahal pengukuran atas 53
        postingan (semuanya pada usia 48 jam) menunjukkan justru layout gambar
        yang paling menentukan: layout bergaya daftar berada di 0.64x dengan
        selang 0.41-0.87 — seluruhnya di bawah rata-rata. Caption kita bahkan
        menyuruh pembaca melihat gambarnya.

        Rubriknya sengaja memeriksa hal yang benar-benar sering rusak pada
        infografis buatan AI: teks kacau, komposisi tidak sesuai layout yang
        diminta, dan cacat bentuk.

        Mengembalikan (skor, catatan). Vision gagal menghasilkan skor None;
        pemeriksaan akhir publikasi akan menahan gambar yang belum dinilai.
        """
        import re
        topic.pop('visual_feedback', None)
        if not image_path or not os.path.exists(str(image_path)):
            return None, 'file gambar tidak ada'

        layout = topic.get('layout', '-')
        komposisi = (topic.get('composition') or '')[:300]
        judul = topic.get('headline', '')

        from core.content_quality import FACT_CONTEXT
        prompt = f"""You are a careful art director reviewing a vertical (9:16) infographic before publication.

INTENDED TOPIC: {judul}
INTENDED LAYOUT: {layout}
INTENDED COMPOSITION: {komposisi}
CAPTION TO ILLUSTRATE: {topic.get('approved_caption', '')}
APPROVED IMAGE COPY: {json.dumps(topic.get('visual_plan', {}).get('approved_image_copy', {}))}
FACTUAL LIMITS: {FACT_CONTEXT}

The image model renders ALL of this poster's typography, so spelling is the
defect most likely to be present and the one that cannot be repaired afterwards.
Read every visible word letter by letter before scoring. Compare the headline,
subtitle, list header and list points against the approved copy above: a single
misspelled, invented, duplicated or truncated word means the poster is unusable.

Score the image 1-10 against these criteria, in order of importance:
1. TEXT LEGIBILITY — is every word real, correctly spelled and readable on a phone? Garbled or nonsense lettering is the single worst defect. Score at most 4 if any word is misspelled or nonsensical.
2. LAYOUT MATCH — does the composition actually deliver the intended layout above? A cross-section must really show a cut through the ground.
3. SUBJECT CORRECTNESS — is this genuinely about gold prospecting geology, not a generic landscape or unrelated mining scene?
4. ARTEFACTS — malformed hands, impossible tools, duplicated limbs, melted objects.
5. WATERMARK — a small text watermark reading "{fanspage_name or ''}" should sit in a corner, never across the centre.
6. FACTUAL ALIGNMENT — flag unsupported recovery percentages, guaranteed finds,
dangerous chemical instructions, misleading geology, and contradiction with the caption.
If any factual defect is present, or text is unreadable, score at most 6.

Also review the separately authorized discussion question: exactly one,
8-14 English words, related to the depicted topic, readable, and clear of
the main diagram and watermark. It must not invent controversy or request
likes, shares, tags, or votes. Report any question issue in discussion_feedback
as advice for FUTURE posts only; do not lower the score for question quality
or absence. Do not confuse this authorized question with forbidden extra labels.

Give actionable future-post improvements by category: text, layout, color, facts,
and question. Use an empty string when no correction is needed. Do not merely praise.
For layout, assess visual hierarchy, focal subject size, separation of detail,
balanced space and whether every panel adds useful information. For color,
assess mineral/material separation, contrast and palette coherence. Report any
lettering beyond the approved copy — invented labels, body paragraphs, fake
signatures, page numbers — as a text defect.
Facebook crops this 9:16 frame to its middle 4:5 in the feed: report a headline
or subtitle falling in the top or bottom eighth as a layout defect, since a
reader scrolling past would never see it.
Reply ONLY with JSON:
{{"improvements": {{"text": "", "layout": "", "color": "", "facts": "", "question": ""}}, "score": <1-10>, "verdict": "<one short sentence>", "worst_problem": "<the single most damaging flaw, or 'none'>", "discussion_feedback": "<question improvement for future posts, or 'none'>"}}"""

        try:
            with open(str(image_path), 'rb') as f:
                encoded = base64.b64encode(f.read()).decode('utf-8')

            url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
                   f"{self.text_model}:generateContent?key={self.gemini_api_key}")
            payload = {"contents": [{"parts": [
                {"text": prompt},
                {"inlineData": {"mimeType": "image/png", "data": encoded}}
            ]}]}
            from core.generation_reliability import event
            response = None
            for review_attempt in range(3):
                response = requests.post(url, json=payload, timeout=90)
                if response.status_code not in (429, 500, 502, 503, 504):
                    break
                event(topic.get('_visual_page_id'), topic, 'review_retry',
                      f'HTTP {response.status_code}', review_attempt+1, self.text_model)
                if review_attempt < 2:
                    time.sleep(5 * (review_attempt+1))
            data = response.json()

            if 'candidates' not in data:
                err = (data.get('error') or {}).get('message', str(data)[:150])
                print(f"   ⚠️  Kritikus gambar tidak bisa menilai: {redact(err)[:160]}")
                return None, 'vision gagal'

            teks = data['candidates'][0]['content']['parts'][0]['text']
            match = re.search(r'\{.*\}', teks, re.DOTALL)
            if not match:
                return None, 'jawaban juri tidak terbaca'

            hasil = json.loads(match.group(0))
            from core.content_quality import valid_score
            skor = valid_score(hasil.get('score'))
            catatan = str(hasil.get('worst_problem') or hasil.get('verdict') or '')[:200]
            from core.visual_plan import CATEGORIES
            categorized = hasil.get('improvements')
            if isinstance(categorized, dict):
                topic['visual_feedback'] = {k: str(categorized.get(k) or '')[:220] for k in CATEGORIES}
            discussion = str(hasil.get('discussion_feedback') or '').strip()
            if discussion and discussion.lower() != 'none':
                catatan += ' | Discussion question: ' + discussion[:400]
            return skor, catatan
        except Exception as e:
            print(f"   ⚠️  Kritikus gambar error: {type(e).__name__}: {redact(e)}")
            return None, 'error juri'

    def generate_image(self, topic, fanspage_name=None, page_id=None):
        """Generate educational infographic using Gemini image model"""
        topic['_visual_page_id'] = page_id
        from core.generation_reliability import event
        topic['image_score'] = None
        # Prompt dibangun di luar blok retry supaya retry tidak crash karena
        # variabel yang belum sempat terbentuk saat error terjadi di sini.
        # Prompt dasar bersifat deterministik dan sudah patuh aturan; yang bisa
        # menyelipkan klaim terlarang adalah lapisan Art Director di atasnya.
        # Karena itu penolakan preflight TIDAK boleh membatalkan ilustrasi —
        # cukup ulangi arahan seninya, lalu kalau tetap gagal pakai prompt dasar
        # tanpa arahan seni. Sebelumnya kegagalan di sini langsung jatuh ke
        # poster teks tanpa gambar, dan itu tetap tayang ke Facebook.
        try:
            base_prompt = self.goldgen.generate_image_prompt(topic, page_id)
        except Exception as e:
            print(f"   ⚠️  Gagal membangun image prompt dasar: {redact(e)}, using PIL fallback...")
            return self._generate_fallback_image(topic, fanspage_name)

        image_prompt = None
        for percobaan in range(2):
            try:
                kandidat = self._apply_art_direction(topic, base_prompt)
                self._preflight_image_plan(topic, kandidat)
                image_prompt = kandidat
                break
            except Exception as e:
                print(f"   ⚠️  Arahan seni ditolak (percobaan {percobaan + 1}): {redact(e)}")

        if image_prompt is None:
            # Kembalikan rencana visual ke bentuk konservatif supaya tidak
            # menyisakan arahan yang baru saja ditolak.
            from core.visual_plan import fallback_plan
            topic['visual_plan'] = fallback_plan(topic)
            topic['art_direction_used'] = False
            try:
                self._preflight_image_plan(topic, base_prompt)
                image_prompt = base_prompt
                print("   ↩️  Memakai prompt dasar tanpa arahan seni")
            except Exception as e:
                print(f"   ⚠️  Prompt dasar pun ditolak: {redact(e)}, using PIL fallback...")
                return self._generate_fallback_image(topic, fanspage_name)

        # CATATAN: image_prompt di atas TIDAK dikirim ke model gambar. Baris di
        # bawah menimpanya seluruhnya. Dari seluruh tahap art director, yang
        # benar-benar sampai ke model hanyalah dict art_direction di dalam
        # topic['visual_plan'] — focal_subject, composition_adjustment,
        # palette_and_contrast, dan avoid.
        #
        # Sisa isi rencana visual (label, pertanyaan, density) tidak lagi
        # tercetak di poster sejak model gambar yang menyusun tipografinya;
        # teks poster diambil langsung dari topiknya. Rencana itu masih dicatat
        # ke visual_decisions sebagai bahan laporan desain.
        from core.layout_design import poster_prompt, DESIGN_VERSION
        from core.visual_plan import safe_trim_words
        topic['visual_plan']['design_version'] = DESIGN_VERSION
        topic['visual_plan']['subtitle'] = safe_trim_words(topic['visual_plan'].get('subtitle') or topic.get('subtitle', ''), 120)
        topic['_image_learning'] = self._image_learning(page_id)
        image_prompt = poster_prompt(topic, topic['visual_plan'], learning=topic['_image_learning'])
        try:
            self._preflight_image_plan(topic, image_prompt)
        except Exception:
            # Catatan belajar berasal dari model; kalau ia memuat frasa
            # terlarang, buang catatannya, jangan batalkan ilustrasinya.
            topic['_image_learning'] = ''
            image_prompt = poster_prompt(topic, topic['visual_plan'])
            self._preflight_image_plan(topic, image_prompt)

        prompt_saat_ini = image_prompt
        # Satu kali gambar ulang kalau juri menolak. Gambar 2K mahal dan lambat,
        # jadi jatahnya sengaja lebih ketat daripada siklus tulis-ulang caption.
        from core.content_quality import IMAGE_MIN_SCORE
        from core.image_copy import FULL, MINIMAL
        AMBANG_GAMBAR = IMAGE_MIN_SCORE
        max_attempts = 3
        gambar_terbaik = None  # (skor, path)
        topic['image_score'] = None
        # Percobaan ulang TIDAK boleh memakai prompt yang sama persis: salah eja
        # dan balasan tanpa gambar hanya akan terulang. Setiap penolakan
        # mengurangi jumlah kata di poster dan meneruskan catatan juri.
        text_level, catatan_juri = FULL, ''

        for attempt in range(max_attempts):
            try:
                if attempt:
                    prompt_saat_ini = self._retry_prompt(topic, text_level, catatan_juri)
                from google.genai import types

                label = f"{self.image_model}" + (" (retry)" if attempt else "")
                image_size = image_size_for_model(self.image_model)
                print(f"   Generating {image_size} image with {label}...")

                client = genai.Client(api_key=self.gemini_api_key)
                response = client.models.generate_content(
                    model=self.image_model,
                    contents=prompt_saat_ini,
                    config=types.GenerateContentConfig(
                        # Hanya IMAGE. Dengan TEXT ikut diizinkan, model boleh
                        # menjawab dengan tulisan saja — dan prompt poster yang
                        # sekarang penuh instruksi "render every word exactly as
                        # written" justru mengundang jawaban berupa teks.
                        # Jawaban tanpa gambar berakhir di poster cadangan PIL.
                        response_modalities=['IMAGE'],
                        image_config=types.ImageConfig(
                            # Ilustrasi kini mengisi seluruh kanvas poster
                            # 1440x2560, jadi rasionya harus sama dengan
                            # posternya. Ketika ilustrasi masih ditempel
                            # sebagai kotak 1312x1180 di tengah, 1:1 memang
                            # yang paling sedikit terbuang; sekarang 1:1
                            # berarti membuang 44% tinggi gambar saat dipaskan.
                            aspect_ratio="9:16",
                            image_size=image_size
                        )
                    )
                )

                image_path = None
                for gambar in _gambar_dari_balasan(response):
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_') + str(attempt)
                    image_path = IMAGES_DIR / f"gold_prospecting_{timestamp}.png"
                    gambar.save(str(image_path))
                    from core.poster_renderer import stamp_watermark
                    stamp_watermark(image_path, image_path, fanspage_name or '')
                    print(f"   ✅ Image generated with {label}")
                    break

                if image_path is None:
                    # Balasan tanpa gambar TIDAK langsung jatuh ke poster teks.
                    # Sebelumnya begitu, dan satu balasan meleset sudah cukup
                    # membuat postingan kehilangan ilustrasinya — padahal
                    # percobaan berikutnya sering berhasil.
                    #
                    # Teks balasan ikut dicetak: di situlah alasan penolakan
                    # model berada, dan sebelumnya dibuang begitu saja sehingga
                    # kegagalan ini tidak bisa didiagnosis dari log.
                    alasan = str(getattr(response, 'text', '') or '')[:200]
                    print(f"   ⚠️  Balasan tanpa gambar (teks: {alasan})")
                    reasons = [str(getattr(c, 'finish_reason', '')) for c in (getattr(response, 'candidates', None) or [])]
                    event(page_id, topic, 'image_empty', json.dumps({
                        'text': redact(alasan), 'finish_reasons': reasons,
                        'block_reason': str(getattr(getattr(response, 'prompt_feedback', None), 'block_reason', ''))}),
                        attempt+1, self.image_model)
                    # Prompt yang lebih sederhana jauh lebih sering dijawab
                    # dengan gambar daripada mengulang permintaan yang sama.
                    text_level = min(MINIMAL, text_level + 1)
                    if attempt < max_attempts - 1:
                        time.sleep(10)
                        continue
                    break  # gambar terbaik (bila ada) dipakai di bawah

                skor, catatan = self._review_image(image_path, topic, fanspage_name)
                event(page_id, topic, 'image_review', f'score={skor}; {catatan}', attempt+1, getattr(self, 'text_model', ''))
                from core.content_feedback import save_feedback
                save_feedback(page_id, topic, 'image', skor, catatan)
                from core.visual_plan import save_plan
                save_plan(page_id, image_path, topic)

                # Ambang ini sebelumnya dihitung lalu tidak pernah dipakai:
                # gambar dinilai, skornya disimpan, dan tetap terbit berapa pun
                # nilainya. Selama PIL yang menyusun tipografi hal itu masih bisa
                # ditolerir. Sekarang model gambar yang menulis seluruh teksnya,
                # jadi juri inilah satu-satunya yang bisa menangkap ejaan rusak
                # sebelum poster tayang.
                if skor is not None and skor < AMBANG_GAMBAR:
                    if gambar_terbaik is None or skor > gambar_terbaik[0]:
                        gambar_terbaik = (skor, image_path)
                    if attempt < max_attempts - 1:
                        print(f"   ♻️  Skor {skor:.1f} di bawah {AMBANG_GAMBAR}; menggambar ulang dengan teks lebih sedikit. {str(catatan or '')[:120]}")
                        text_level = min(MINIMAL, text_level + 1)
                        catatan_juri = self._reviewer_note(catatan, topic)
                        continue
                    print(f"   ⚠️  Percobaan habis; memakai gambar terbaik (skor {gambar_terbaik[0]:.1f})")
                    topic['image_score'] = gambar_terbaik[0]
                    return gambar_terbaik[1]

                topic['image_score'] = skor
                return image_path

            except Exception as e:
                event(page_id, topic, 'image_error', f'{type(e).__name__}: {redact(e)}', attempt+1, self.image_model)
                if attempt < max_attempts - 1:
                    print(f"   ⚠️  Gemini error: {redact(e)}, retrying in 30s...")
                    time.sleep(30)
                elif gambar_terbaik:
                    # Percobaan terakhir gagal, tapi gambar sebelumnya sudah ada.
                    # Gambar Gemini yang belum sempurna tetap jauh lebih baik
                    # daripada fallback PIL.
                    skor_pakai, path_pakai = gambar_terbaik
                    print(f"   ↩️  Percobaan terakhir gagal; memakai gambar sebelumnya (skor {skor_pakai:.0f})")
                    topic['image_score'] = skor_pakai
                    return path_pakai
                else:
                    print(f"   ⚠️  Gemini retry failed: {redact(e)}, using PIL fallback...")

        if gambar_terbaik:
            skor_pakai, path_pakai = gambar_terbaik
            topic['image_score'] = skor_pakai
            return path_pakai

        return self._generate_fallback_image(topic, fanspage_name)

    def _image_learning(self, page_id):
        """Pelajaran visual Page ini untuk model gambar; kosong bila gagal."""
        try:
            from comment_analyzer import _is_meaningful
            from core.content_feedback import image_learning_notes
            insights = self.goldgen._get_latest_insights(page_id) or {}
            styles = [v for v in (insights.get('preferred_visual_styles') or [])
                      if isinstance(v, str) and _is_meaningful(v)]
            return image_learning_notes(page_id, styles)
        except Exception as e:
            print(f"   ⚠️  Catatan belajar visual tidak tersedia: {redact(e)}")
            return ''

    def _reviewer_note(self, catatan, topic):
        """Catatan juri untuk percobaan berikutnya, tanpa saran pertanyaan diskusi."""
        note = str(catatan or '').split(' | Discussion question:')[0]
        text_fix = (topic.get('visual_feedback') or {}).get('text', '')
        if text_fix and text_fix not in note:
            note = f'{note}. Text: {text_fix}' if note else f'Text: {text_fix}'
        return note.strip()[:300]

    def _retry_prompt(self, topic, level, note):
        """Prompt percobaan ulang: teks lebih sedikit + catatan juri.

        Catatan juri berasal dari model, jadi ia ikut diperiksa preflight; bila
        catatan itu memuat frasa terlarang, prompt dibangun ulang tanpanya.
        """
        from core.layout_design import poster_prompt
        plan = topic['visual_plan']
        learning = topic.get('_image_learning', '')
        try:
            prompt = poster_prompt(topic, plan, level, note, learning)
            self._preflight_image_plan(topic, prompt)
        except Exception:
            prompt = poster_prompt(topic, plan, level, learning=learning)
            self._preflight_image_plan(topic, prompt)
        print(f"   ✂️  Percobaan ulang dengan {len(plan['approved_image_copy']['labels'])} label"
              f"{', tanpa subjudul' if not plan['approved_image_copy']['subtitle'] else ''}"
              f"{', tanpa pertanyaan' if not plan['approved_image_copy']['question'] else ''}")
        return prompt

    def _apply_art_direction(self, topic, base_prompt):
        """Ask the text model to refine visual execution without changing facts.

        This advisory step is fail-open: API or JSON failures leave the proven,
        deterministic GoldGen prompt untouched, so a scheduled post still runs.
        """
        from core.visual_plan import fallback_plan, parse_plan, render_plan
        from core.prospecting_style import label_style
        topic['art_direction_used'] = False
        topic['visual_plan'] = fallback_plan(topic)
        evidence = {}
        try:
            from core.visual_plan import design_report
            evidence = design_report(topic.get('_visual_page_id'))
            evidence['groups'] = [g for g in evidence.get('groups', [])
                                  if g['samples'] >= 5 and g['layout'] == topic.get('layout')][:12]
        except Exception:
            pass
        request_prompt = f"""You are the AI Art Director for a Facebook educational infographic.

Refine visual execution BEFORE image generation. Preserve the approved topic,
caption, factual limits, and selected layout exactly. Finalize image copy now. Do
not invent facts, measurements, recovery rates, guarantees, or extra labels.
Prioritize a strong focal subject, phone-readable hierarchy, useful information
density, and the visual style selected from this page's measured audience data.
Preserve exactly one topic-specific discussion question of 8-14 English words
in its own bottom box.
Always provide exactly 4 concise callout labels of 1 to 4 words each.
Choose light (4 labels, up to 3 words each) or medium (4 labels, up to 4 words each).
Never exceed 4 words per label: the image model letters every word onto the
poster, and a single misspelled word gets the poster rejected.
{label_style()}
These budgets replace the base brief label limits. Self-check English spelling
and every label against the approved caption. No new claims or quantities. Do not
change the topic, invent controversy, or add engagement bait.
The image model letters the final title, labels and question onto the poster,
so prefer common, short, easy-to-spell words and avoid rare technical terms when
a plain word works. Questions must identify visible features by name.

APPROVED TOPIC: {topic.get('headline', '')}
APPROVED CAPTION: {topic.get('approved_caption', '')}
SELECTED LAYOUT: {topic.get('layout', '')}
MEASURED DESIGN EVIDENCE (same page, same layout, 48-hour views;
observational guidance only, no automatic winner): {json.dumps(evidence)}
CURRENT IMAGE BRIEF:
{base_prompt}

Return JSON only:
{{
  "focal_subject": "one concrete dominant visual subject",
  "composition_adjustment": "specific placement, hierarchy and visual flow",
  "palette_and_contrast": "brief color and mobile-legibility direction",
  "title": "final English title, at most six words",
  "labels": ["exactly 4 labels, 1-4 common words each"],
  "question": "final topic-specific English question, 8-14 words ending in ?",
  "question_type": "experience or sampling_choice or interpretation",
  "density": "light or medium",
  "caption_consistent": true,
  "selection_reason": "why this density and question fit this topic and available evidence",
  "avoid": "specific clutter, ambiguity or visual mistakes to avoid"
}}"""
        try:
            from google.genai import types

            client = genai.Client(api_key=self.gemini_api_key)
            response = client.models.generate_content(
                model=self.text_model,
                contents=request_prompt,
                config=types.GenerateContentConfig(response_mime_type='application/json'),
            )
            raw = getattr(response, 'text', '')
            plan = parse_plan(raw, topic)
            direction = render_art_direction(raw)
            if not direction or not plan:
                print("   ⚠️  AI Art Director returned an invalid plan; using base prompt")
                return render_plan(base_prompt, topic['visual_plan'])
            topic['visual_plan'] = plan
            plan['evidence_used'] = evidence
            from core.art_director import parse_art_direction
            plan['art_direction'] = parse_art_direction(raw) or {}
            topic['art_direction_used'] = True
            print("   🎨 AI Art Director refined the image plan")
            return render_plan(base_prompt, plan) + direction
        except Exception as e:
            print(f"   ⚠️  AI Art Director unavailable: {redact(e)}; using base prompt")
            return render_plan(base_prompt, topic['visual_plan'])

    def _preflight_image_plan(self, topic, prompt):
        """Validate the visual plan before spending an image-generation call.

        This is intentionally deterministic: it checks that the image request
        contains the approved content contract, rather than judging a rendered
        image after the expensive call has already happened.
        """
        from core.content_quality import ContentQualityError, FORBIDDEN_IMAGE_TERMS

        caption = str(topic.get('approved_caption') or '').strip()
        required = {
            'topic': str(topic.get('headline') or '').strip(),
            'layout': str(topic.get('layout') or '').strip(),
            'caption': caption,
            'prompt': str(prompt or '').strip(),
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ContentQualityError(
                'DITAHAN SEBELUM GENERATE: rencana visual belum lengkap ('
                + ', '.join(missing) + ')'
            )

        if len(caption) < 100:
            raise ContentQualityError(
                'DITAHAN SEBELUM GENERATE: caption terlalu pendek untuk menjadi acuan visual'
            )

        from core.image_copy import forbidden_claims
        found = forbidden_claims(required['prompt'], FORBIDDEN_IMAGE_TERMS)
        if found:
            raise ContentQualityError(
                'DITAHAN SEBELUM GENERATE: prompt memuat klaim/arah visual terlarang ('
                + ', '.join(found) + ')'
            )
    
    def _generate_fallback_image(self, topic, fanspage_name=None):
        """Generate professional infographic locally with PIL.

        Ditandai `image_fallback` supaya pemeriksaan publikasi tahu poster ini
        TIDAK memuat ilustrasi. Hasilnya masih berguna untuk pratinjau manual
        dan diagnosis, tapi tidak boleh tayang sebagai konten.
        """
        from core.poster_renderer import compose_poster
        from core.visual_plan import fallback_plan, save_plan
        from core.layout_design import DESIGN_VERSION
        import uuid
        topic['image_fallback'] = True
        from core.generation_reliability import event
        event(topic.get('_visual_page_id'), topic, 'image_fallback', 'No publishable illustration; see preceding attempt events')
        plan = fallback_plan(topic)
        plan['fallback_points'] = [str(p)[:220] for p in topic.get('list_points', [])[:4]]
        plan['design_version'] = DESIGN_VERSION
        plan['density'] = 'fallback'
        plan['selection_reason'] = 'Typeset fallback with approved topic points; no invented illustration'
        topic['visual_plan'] = plan
        image_path = IMAGES_DIR / f"gold_prospecting_{datetime.now():%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:6]}.png"
        compose_poster(plan, image_path, fanspage_name or '')
        save_plan(topic.get('_visual_page_id'), image_path, topic)
        return image_path

    def _describe_fb_error(self, response=None, raw_text=None):
        """Terjemahkan error Facebook jadi alasan yang bisa dibaca manusia.

        Selalu mengembalikan string non-kosong, supaya kolom error_message di DB
        tidak pernah kosong saat sebuah postingan gagal.
        """
        error = {}
        text = raw_text or ''

        if response is not None:
            text = text or (response.text or '')
            try:
                error = response.json().get('error', {}) or {}
            except Exception:
                pass

        code = error.get('code')
        subcode = error.get('error_subcode')
        message = error.get('message') or ''
        user_msg = error.get('error_user_msg') or ''
        haystack = f"{message} {user_msg} {text}".lower()

        # Token tidak aktif lagi — penyebab paling sering & paling penting dikenali
        if code in (190, 102) or 'expired' in haystack or 'oauth' in haystack or 'session has been invalidated' in haystack:
            reason = "TOKEN TIDAK AKTIF: token Facebook sudah kedaluwarsa/dicabut. Update token di Dashboard."
        elif code in (200, 10, 3) or 'permission' in haystack:
            reason = "IZIN KURANG: token tidak punya permission yang dibutuhkan (pages_manage_posts)."
        elif code in (368, 17, 4, 613) or 'limit' in haystack or 'spam' in haystack or 'blocked' in haystack:
            reason = "DIBATASI FACEBOOK: kena rate limit / dianggap spam. Bot masuk cooldown."
        elif code == 100:
            reason = "PARAMETER DITOLAK: request tidak diterima Facebook (parameter atau file tidak valid)."
        elif code == 1 or code == 2 or 'temporarily' in haystack:
            reason = "FACEBOOK BERMASALAH: error sementara di sisi Facebook, akan dicoba lagi."
        elif message:
            reason = f"ERROR FACEBOOK: {message}"
        else:
            reason = f"ERROR FACEBOOK: {(text or 'tidak ada detail dari Facebook')[:200]}"

        # Sertakan kode teknis supaya tetap bisa ditelusuri
        detail = []
        if code is not None:
            detail.append(f"code={code}")
        if subcode is not None:
            detail.append(f"subcode={subcode}")
        if message and message not in reason:
            detail.append(message[:150])
        if detail:
            reason = f"{reason} [{' | '.join(detail)}]"

        return reason[:500]

    def validate_token(self, fanspage, max_retries=3):
        """Validate Facebook token before posting with network retry"""
        url = f"{GRAPH_API_BASE}/{fanspage['page_id']}"
        params = {'access_token': fanspage['access_token'], 'fields': 'name'}
        
        for attempt in range(max_retries):
            try:
                response = requests.get(url, params=params, timeout=15)
                
                if response.status_code == 200:
                    return True, None
                else:
                    reason = self._describe_fb_error(response)

                    # Token expired or OAuth error -> no need to retry network, notify admin
                    if reason.startswith("TOKEN TIDAK AKTIF"):
                        send_notification(
                            f"🚨 <b>Token Facebook Tidak Aktif!</b>\n\n"
                            f"📄 Page: {fanspage.get('name')}\n"
                            f"⚠️ {reason}\n"
                            f"👉 Harap update token di Dashboard."
                        )

                    return False, reason
            except (requests.exceptions.RequestException, Exception) as e:
                if attempt < max_retries - 1:
                    delay = 3 * (attempt + 1)
                    print(f"   ⚠️  Network/DNS glitch validating token for {fanspage.get('name')}: {redact(e)}. Retrying in {delay}s ({attempt + 1}/{max_retries})...")
                    time.sleep(delay)
                else:
                    return False, f"Network error after {max_retries} attempts: {redact(e)}"
        
        return False, "Token validation failed: Max retries exceeded"
    
    def _extract_post_id(self, result):
        """Ambil ID POSTINGAN dari respons /photos, bukan ID foto.

        Endpoint /photos mengembalikan dua ID:
            id      -> ID objek foto            (mis. 122199562316591645)
            post_id -> ID postingan di feed     (mis. 488507404341313_122199562340591645)

        Selama ini yang disimpan adalah 'id', padahal semua pembacaan balik
        memakai endpoint /posts yang mengembalikan format post_id. Keduanya tidak
        pernah cocok, sehingga:
          - Vision AI tidak pernah menemukan gambar pemenang untuk dianalisis
          - hook_type tidak pernah terbaca balik dan selalu jadi "Unknown"
            (inilah sumber preferensi sampah "hook: unknown")
          - baris engagement_cache jadi yatim dan tidak ikut melatih layout
        """
        post_id = result.get('post_id') or result.get('id')
        photo_id = result.get('id')
        if post_id and photo_id and post_id != photo_id:
            print(f"   🔗 Post ID: {post_id} (foto: {photo_id})")
        return post_id

    def post_to_facebook(self, fanspage, content, image_path, single_attempt=False):
        """Post content and image to Facebook page with retry"""
        # Validate token first
        valid, error = self.validate_token(fanspage)
        if not valid:
            print(f"   ❌ {error}")
            return None, error
        
        # Facebook tidak merender Markdown. Dibersihkan di sini, bukan di
        # generate_caption, karena inilah satu-satunya pintu menuju Facebook —
        # postingan terjadwal, manual, dan percobaan ulang semuanya lewat sini.
        from core.content_quality import strip_markdown, require_publishable
        from core.generation_reliability import load_review, clock_ready
        require_publishable(load_review(fanspage['page_id'], image_path, content))
        if not clock_ready():
            return None, 'Waktu server/jaringan belum terverifikasi; publikasi ditunda'
        content = strip_markdown(content)

        # Try posting with retry
        max_retries = 1 if single_attempt else 3
        for attempt in range(max_retries):
            try:
                url = f"{GRAPH_API_BASE}/{fanspage['page_id']}/photos"
                
                with open(image_path, 'rb') as image_file:
                    files = {'source': image_file}
                    # Tanpa check-in lokasi atau "feeling". Dulu lokasi dipilih
                    # acak dari seluruh dunia (Peru, Afrika Selatan, ...) di setiap
                    # posting: menyesatkan audiens Amerika dan tidak menambah
                    # jangkauan, sementara pola acak itu bisa terbaca seperti spam.
                    data = {
                        'message': content,
                        'access_token': fanspage['access_token'],
                    }
                    
                    response = requests.post(url, data=data, files=files, timeout=30)
                    
                    if response.status_code == 200:
                        post_id = self._extract_post_id(response.json())

                        # Send Telegram notification
                        send_notification(f"✅ <b>Goldgen Bot</b>\n\n📝 Posted to Facebook\n🆔 {post_id}")

                        return post_id, None
                    else:
                        error_msg = self._describe_fb_error(response)

                        if attempt < max_retries - 1:
                            delay = 2 ** attempt
                            print(f"   ⚠️  {error_msg}")
                            print(f"   ⚠️  Retry {attempt + 1}/{max_retries} after {delay}s")
                            time.sleep(delay)
                        else:
                            # Deteksi berdasarkan hasil terjemahan, bukan cocok-cocokan
                            # substring angka pada teks mentah (dulu '17' bisa cocok tak sengaja)
                            if error_msg.startswith("DIBATASI FACEBOOK"):
                                print(f"   🚨 FACEBOOK BAN/LIMIT DETECTED! Activating Self-Healing Cooldown for 24h...")
                                self.set_cooldown(fanspage['page_id'], hours=24)
                            if error_msg.startswith("TOKEN TIDAK AKTIF"):
                                send_notification(
                                    f"🚨 <b>Token Facebook Tidak Aktif!</b>\n\n"
                                    f"📄 Page: {fanspage.get('name')}\n"
                                    f"⚠️ {error_msg}\n"
                                    f"👉 Harap update token di Dashboard."
                                )
                            return None, f"{error_msg} (setelah {max_retries} percobaan)"

            except Exception as e:
                if single_attempt:
                    raise UncertainSend('Hasil kirim belum pasti: ' + type(e).__name__) from e
                if attempt < max_retries - 1:
                    delay = 2 ** attempt
                    print(f"   ⚠️  Error: {redact(e)}, retry {attempt + 1}/{max_retries} after {delay}s")
                    time.sleep(delay)
                else:
                    reason = f"GAGAL MENGIRIM: {type(e).__name__}: {redact(e)[:200]} (setelah {max_retries} percobaan)"
                    send_notification(f"❌ <b>Goldgen Bot Error</b>\n\n{reason[:300]}")
                    return None, reason

        return None, f"GAGAL MENGIRIM: batas percobaan ({max_retries}x) habis tanpa respons sukses dari Facebook"
    
    def log_post(self, fanspage, content, image_path, fb_post_id, status, error_message=None, layout_name=None, hook_type=None, editor_score=None, requested_hook=None, topic_id=None, topic_headline=None, image_score=None, experiment_id=None, experiment_arm=None):
        """Log post to database"""
        from datetime import timezone, timedelta
        now_wib = datetime.now(timezone(timedelta(hours=7)))
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO posts (timestamp, page_id, page_name, content, image_path, fb_post_id, status, error_message, layout_name, hook_type, editor_score, requested_hook, topic_id, topic_headline, image_score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            now_wib.isoformat(),
            fanspage['page_id'],
            fanspage['name'],
            content,
            str(image_path),
            fb_post_id,
            status,
            redact(error_message) if error_message else None,
            layout_name,
            hook_type,
            editor_score,
            requested_hook,
            topic_id,
            topic_headline,
            image_score
        ))
        if experiment_id:
            cursor.execute('UPDATE posts SET experiment_id=?,experiment_arm=? WHERE id=?',
                           (experiment_id,experiment_arm,cursor.lastrowid))
        conn.commit()
        conn.close()
        if status == 'success' and fb_post_id:
            self._send_promo_comment(fanspage, fb_post_id, content)

    def _send_promo_comment(self, fanspage, fb_post_id, caption=''):
        """Komentar promo pertama; kegagalannya tidak boleh menggagalkan posting."""
        from core.promo_comment import send_promo_comment
        try:
            # Kalimat pembuka bergilir dari FALLBACK_SENTENCES, tanpa Gemini:
            # penjualan hanya sampingan, jadi satu panggilan model per posting
            # untuk kalimat promo tidak sepadan.
            comment_id, error = send_promo_comment(fb_post_id, fanspage['access_token'],
                                                   None, caption)
            if comment_id:
                print(f"   💬 Komentar promo terkirim")
            else:
                print(f"   ⚠️  Komentar promo belum terkirim: {error} (disusulkan siklus berikutnya)")
        except Exception as exc:
            print(f"   ⚠️  Komentar promo gagal: {type(exc).__name__}: {redact(exc)[:200]}")
    
    def set_cooldown(self, page_id, hours=24):
        """Set a cooldown period for a page (e.g. after a rate limit or ban)"""
        from datetime import timezone, timedelta
        now_wib = datetime.now(timezone(timedelta(hours=7)))
        cooldown_until = (now_wib + timedelta(hours=hours)).isoformat()
        
        conn = get_db_connection()
        cursor = conn.cursor()
        # Ensure row exists first
        cursor.execute('INSERT OR IGNORE INTO last_post_time (page_id, timestamp) VALUES (?, ?)', (page_id, now_wib.isoformat()))
        cursor.execute('UPDATE last_post_time SET cooldown_until = ? WHERE page_id = ?', (cooldown_until, page_id))
        conn.commit()
        conn.close()
        print(f"   🧊 Cooldown aktif untuk page {page_id} sampai {cooldown_until}")

    def is_in_cooldown(self, page_id):
        """Check if a page is currently in cooldown mode"""
        from datetime import timezone, timedelta
        now_wib = datetime.now(timezone(timedelta(hours=7)))
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT cooldown_until FROM last_post_time WHERE page_id = ?', (page_id,))
        result = cursor.fetchone()
        conn.close()
        
        if result and result['cooldown_until']:
            try:
                cooldown_time = datetime.fromisoformat(result['cooldown_until'])
                if now_wib < cooldown_time:
                    return True
            except:
                pass
        return False

    def should_post(self, fanspage):
        """Check if current hour matches fanspage schedule and not in cooldown"""
        if self.is_in_cooldown(fanspage['page_id']):
            print(f"   🧊 {fanspage['name']} is in COOLDOWN mode. Skipping.")
            return False

        from datetime import timezone, timedelta
        now_wib = datetime.now(timezone(timedelta(hours=7)))
        current_hour = now_wib.hour
        
        # Support both old interval_hours and new schedule_hours
        if 'schedule_hours' in fanspage:
            schedule_hours = fanspage['schedule_hours']
            
            # Check if current hour is in schedule
            if current_hour not in schedule_hours:
                return False
            
            # Check if already posted this hour
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT timestamp FROM last_post_time WHERE page_id = ?', (fanspage['page_id'],))
            result = cursor.fetchone()
            conn.close()
            
            if not result:
                return True
            
            last_posted = datetime.fromisoformat(result[0]).astimezone(timezone(timedelta(hours=7)))
            # Only post once per scheduled hour (different hour OR different day)
            return last_posted.hour != current_hour or last_posted.date() != now_wib.date()
        
        # Fallback to old interval-based logic
        else:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT timestamp FROM last_post_time WHERE page_id = ?', (fanspage['page_id'],))
            result = cursor.fetchone()
            conn.close()
            
            if not result:
                return True
            
            from datetime import timedelta
            last_posted = datetime.fromisoformat(result[0]).astimezone(timezone(timedelta(hours=7)))
            interval = timedelta(hours=fanspage.get('interval_hours', 6))
            return now_wib >= last_posted + interval
    
    def update_last_post_time(self, page_id):
        """Update last post time for a page"""
        from datetime import timezone, timedelta
        now_wib = datetime.now(timezone(timedelta(hours=7)))
        conn = get_db_connection()
        cursor = conn.cursor()
        # Pakai UPSERT (bukan INSERT OR REPLACE) supaya cooldown_until tidak ikut terhapus
        cursor.execute('''
            INSERT INTO last_post_time (page_id, timestamp)
            VALUES (?, ?)
            ON CONFLICT(page_id) DO UPDATE SET timestamp = excluded.timestamp
        ''', (page_id, now_wib.isoformat()))
        conn.commit()
        conn.close()
    
    def run(self):
        """Main execution flow"""
        print(f"[{datetime.now()}] Starting auto-post process...")
        
        # Check if bot is disabled
        disabled_file = BASE_DIR / ".DISABLED"
        if disabled_file.exists():
            print("⏸️  Bot is DISABLED. Skipping auto-post.")
            print(f"   (Delete {disabled_file} to re-enable)")
            return
        
        from core.generation_reliability import clock_ready, claim_slot, finish_slot, event, save_review
        if not clock_ready():
            print('Waktu server/jaringan belum terverifikasi; scheduler ditunda')
            return

        # First, process queued posts from web app
        self.process_queue()
        
        # Then, do regular auto-posting
        print(f"Found {len(self.fanspages)} fanspage(s) configured\n")
        
        # Get starting topic index for this cycle
        if self.goldgen.state_file.exists():
            with open(self.goldgen.state_file, 'r') as f:
                state = json.load(f)
                base_topic_index = state.get('current_topic_index', 0)
        else:
            base_topic_index = 0
        
        posted_count = 0
        
        for idx, fanspage in enumerate(self.fanspages):
            content, image_path, topic = '', None, {}
            slot, slot_status = None, 'failed'
            if not fanspage.get('enabled', True):
                print(f"⏭️  Skipping {fanspage['name']} (disabled)")
                continue
            
            if not self.should_post(fanspage):
                schedule_info = f"schedule: {fanspage.get('schedule_hours', 'N/A')}" if 'schedule_hours' in fanspage else f"interval: {fanspage.get('interval_hours', 6)}h"
                print(f"⏰ Skipping {fanspage['name']} ({schedule_info})")
                continue
            
            slot = claim_slot(fanspage['page_id'])
            if slot is None:
                continue
            try:
                print(f"📄 Processing: {fanspage['name']}")
                print(f"   Page ID: {fanspage['page_id']}")
                schedule_info = f"Schedule: {fanspage['schedule_hours']}" if 'schedule_hours' in fanspage else f"Interval: {fanspage.get('interval_hours', 6)} hours"
                print(f"   {schedule_info}")
                
                # VALIDATE TOKEN BEFORE GENERATING ANYTHING
                print("   Validating Facebook token...")
                valid, token_error = self.validate_token(fanspage)
                if not valid:
                    print(f"   ❌ {token_error}")
                    print("   ⚠️  Skipping generation to save Gemini API tokens.")
                    self.log_post(fanspage, "[TIDAK JADI POSTING]", "", None, 'failed',
                                  f"{token_error} — dibatalkan sebelum generate konten.")
                    continue

                # Lock this fanpage immediately to prevent race conditions with concurrent crons
                # Successful publication alone updates last_post_time.

                # [JIT ML RESEARCH] - Lakukan riset tepat sebelum merancang konten
                try:
                    analyzer = CommentAnalyzer()
                    jit_result = analyzer.analyze_single_page(fanspage, min_interval_hours=JIT_INTERVAL_HOURS)
                    if jit_result == 'cached':
                        print(f"   🧠 JIT ML Research: memakai insight terbaru (< {JIT_INTERVAL_HOURS} jam)")
                    elif jit_result:
                        print(f"   🧠 JIT ML Research sukses untuk {fanspage['name']}")
                    else:
                        print(f"   ℹ️  JIT ML Research: data belum cukup untuk {fanspage['name']} (konten pakai rotasi biasa)")
                except Exception as e:
                    print(f"   ⚠️  JIT ML Research failed for {fanspage.get('name')}: {type(e).__name__}: {e} (continuing to post)")

                # Generate content with offset topic (different for each fanspage)
                # Bikin caption & prompt pake GoldGen AI (sekarang sudah terisolasi per-page)
                resumed = self._resume_pending_review(fanspage)
                reused = None if resumed else self._resume_approved_caption(fanspage)
                if resumed:
                    content, topic, image_path = resumed
                elif reused:
                    # Hanya gambarnya yang gagal; caption yang sudah lolos
                    # pemeriksaan tidak dibuat ulang (hemat 2-6 panggilan Gemini).
                    content, topic = reused
                    print("   ♻️  Memakai caption yang sudah lolos dari percobaan sebelumnya; hanya gambar yang dibuat ulang")
                else:
                    content, topic = self.generate_content(page_id=fanspage['page_id'], allow_experiment=True)
                topic['approved_caption'] = content
                print(f"   Topic: {topic['headline']}")
                print(f"   Layout: {topic['layout']}")
                
                # Generate poster image
                print("   Generating infographic...")
                if not resumed:
                    image_path = self.generate_image(topic, fanspage_name=fanspage['name'], page_id=fanspage['page_id'])

                # Gerbang terakhir sebelum tayang. Dulu fungsi ini ada, diuji,
                # tapi tidak pernah dipanggil — dan justru inilah yang mestinya
                # mencegah poster tanpa ilustrasi terbit pada 15 September.
                from core.content_quality import require_publishable
                save_review(fanspage['page_id'], image_path, content, topic)
                require_publishable(topic)

                # Post to Facebook
                print("   Posting to Facebook...")
                slot_status = 'uncertain'
                finish_slot(fanspage['page_id'], slot, 'uncertain')
                fb_post_id, error = self.post_to_facebook(fanspage, content, image_path, single_attempt=True)

                if fb_post_id:
                    # Tandai sukses SEBELUM pencatatan: kalau log_post gagal,
                    # slot tidak boleh dibuka lagi karena postingan sudah tayang.
                    slot_status = 'success'
                    print(f"   ✅ Success! Post ID: {fb_post_id}")
                    self.log_post(fanspage, content, image_path, fb_post_id, 'success', layout_name=topic.get('layout'), hook_type=topic.get('hook_type'), editor_score=topic.get('editor_score'), requested_hook=topic.get('requested_hook'), topic_id=topic.get('id'), topic_headline=topic.get('headline'), image_score=topic.get('image_score'), experiment_id=topic.get('experiment_id'), experiment_arm=topic.get('experiment_arm'))
                    posted_count += 1
                    self.update_last_post_time(fanspage['page_id'])
                else:
                    # Facebook menolak dengan jawaban pasti: belum tayang, jadi
                    # slot boleh dicoba lagi (maks. 3x per jam, jeda 15 menit).
                    slot_status = 'failed'
                    print(f"   ❌ Failed: {error}")
                    self.log_post(fanspage, content, image_path, None, 'failed', error, layout_name=topic.get('layout'), hook_type=topic.get('hook_type'), editor_score=topic.get('editor_score'), requested_hook=topic.get('requested_hook'), topic_id=topic.get('id'), topic_headline=topic.get('headline'), image_score=topic.get('image_score'), experiment_id=topic.get('experiment_id'), experiment_arm=topic.get('experiment_arm'))
                
                print()

                
            except Exception as e:
                # Status 'failed' (bukan 'error') supaya ikut terhitung di statistik
                # dan tampil di dashboard bersama alasannya.
                import traceback
                if slot_status != 'success':
                    slot_status = 'uncertain' if isinstance(e, UncertainSend) else 'failed'
                error_msg = f"GAGAL DIPROSES: {type(e).__name__}: {redact(e)[:300]}"
                print(f"   ❌ {error_msg}\n")
                traceback.print_exc()
                event(fanspage['page_id'], topic, 'generation_failed', error_msg)
                if slot_status == 'success':
                    # Sudah tayang; hanya pencatatan sesudahnya yang gagal.
                    continue
                self.log_post(fanspage, content, str(image_path or ''), None,
                              'retrying' if slot_status == 'uncertain' else 'failed', error_msg,
                              layout_name=topic.get('layout'), hook_type=topic.get('hook_type'),
                              topic_id=topic.get('id'), topic_headline=topic.get('headline'),
                              image_score=topic.get('image_score'), experiment_id=topic.get('experiment_id'),
                              experiment_arm=topic.get('experiment_arm'))
            finally:
                finish_slot(fanspage['page_id'], slot, slot_status)

        # Susulkan komentar promo yang gagal terkirim sebelumnya.
        try:
            from core.promo_comment import send_pending_promo_comments
            # Tanpa Gemini: susulan bisa berulang tiap 15 menit selama 24 jam
            # kalau Facebook terus menolak, dan tiap percobaan akan memakan satu
            # panggilan model. Kalimat cadangan bergilir sudah cukup di sini.
            send_pending_promo_comments(self.fanspages)
        except Exception as exc:
            print(f"⚠️  Susulan komentar promo gagal: {type(exc).__name__}: {redact(exc)[:200]}")

        # Update state once at the end of cycle
        # ALWAYS update state even if posted_count = 0 to prevent stuck topics
        if posted_count > 0:
            next_index = (base_topic_index + posted_count) % len(self.goldgen.topics)
            self.goldgen.state_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.goldgen.state_file, 'w') as f:
                json.dump({'current_topic_index': next_index, 'last_updated': datetime.now().isoformat()}, f)
            print(f"📊 Posted to {posted_count} fanspage(s) with different topics")
            print(f"   Next cycle will start from topic index: {next_index}\n")
        else:
            # Update timestamp even if no posts (to track bot is running)
            if self.goldgen.state_file.exists():
                with open(self.goldgen.state_file, 'r') as f:
                    state = json.load(f)
                state['last_updated'] = datetime.now().isoformat()
                with open(self.goldgen.state_file, 'w') as f:
                    json.dump(state, f)
            print(f"📊 No posts made this cycle (all fanspages waiting for interval)\n")
        
        print(f"[{datetime.now()}] Process completed.\n")
    
    def force_post(self, target_page_id):
        """Force a post to a specific fanspage regardless of schedule or queue"""
        caption, image_path, topic = '', None, {}
        print(f"[{datetime.now()}] Starting forced manual post for {target_page_id}...")
        
        from core.generation_reliability import clock_ready, save_review, event
        if not clock_ready():
            return False, 'Waktu server/jaringan belum terverifikasi'
        target_fanspage = next((f for f in self.fanspages if f['page_id'] == target_page_id), None)
        if not target_fanspage:
            print(f"❌ Error: Fanspage with ID {target_page_id} not found in configuration.")
            return False, "Fanspage not found"
            
        try:
            print(f"📄 Processing Manual Post: {target_fanspage['name']}")
            
            print("   Validating Facebook token...")
            valid, token_error = self.validate_token(target_fanspage)
            if not valid:
                error_msg = f"Token validation failed: {token_error}"
                print(f"   ❌ {error_msg}")
                self.log_post(target_fanspage, "[SKIPPED]", "", None, 'failed', error_msg)
                return False, error_msg

            if self.goldgen.state_file.exists():
                with open(self.goldgen.state_file, 'r') as f:
                    state = json.load(f)
                    base_topic_index = state.get('current_topic_index', 0)
            else:
                base_topic_index = 0
                
            page_id = target_fanspage['page_id']
            page_name = target_fanspage['name']

            # 3. Generate Content
            print(f"   📝 Generating content with Gemini...")
            caption, topic = self.generate_content(page_id=page_id)
            topic['approved_caption'] = caption
            
            # 4. Generate Image
            print(f"   🎨 Generating image...")
            image_path = self.generate_image(topic, fanspage_name=page_name, page_id=page_id)

            # Jalur manual memakai gerbang yang sama dengan jalur terjadwal.
            # Justru lewat sinilah poster tanpa ilustrasi itu tayang.
            from core.content_quality import require_publishable
            save_review(target_page_id, image_path, caption, topic)
            require_publishable(topic)

            print("   Posting to Facebook...")
            fb_post_id, error = self.post_to_facebook(target_fanspage, caption, image_path, single_attempt=True)
            
            if fb_post_id:
                print(f"   ✅ Success! Post ID: {fb_post_id}")
                self.log_post(target_fanspage, caption, image_path, fb_post_id, 'success', layout_name=topic.get('layout'), hook_type=topic.get('hook_type'), editor_score=topic.get('editor_score'), requested_hook=topic.get('requested_hook'), topic_id=topic.get('id'), topic_headline=topic.get('headline'), image_score=topic.get('image_score'))
                self.update_last_post_time(target_fanspage['page_id'])
                
                next_index = (base_topic_index + 1) % len(self.goldgen.topics)
                self.goldgen.state_file.parent.mkdir(parents=True, exist_ok=True)
                with open(self.goldgen.state_file, 'w') as f:
                    json.dump({'current_topic_index': next_index, 'last_updated': datetime.now().isoformat()}, f)
                    
                return True, fb_post_id
            else:
                print(f"   ❌ Failed: {error}")
                self.log_post(target_fanspage, caption, image_path, None, 'failed', error, layout_name=topic.get('layout'), hook_type=topic.get('hook_type'), editor_score=topic.get('editor_score'), requested_hook=topic.get('requested_hook'), topic_id=topic.get('id'), topic_headline=topic.get('headline'), image_score=topic.get('image_score'))
                return False, error
                
        except Exception as e:
            import traceback
            error_msg = f"GAGAL DIPROSES: {type(e).__name__}: {redact(e)[:300]}"
            print(f"   ❌ {error_msg}\n")
            traceback.print_exc()
            event(target_page_id, topic, 'generation_failed', error_msg)
            self.log_post(target_fanspage, caption, str(image_path or ''), None,
                          'retrying' if isinstance(e, UncertainSend) else 'failed', error_msg,
                          layout_name=topic.get('layout'), topic_id=topic.get('id'),
                          topic_headline=topic.get('headline'), image_score=topic.get('image_score'))
            return False, error_msg

    def retry_existing_post(self, post_id):
        # Atomically claim before sending; a concurrent click cannot send twice.
        conn = get_db_connection()
        try:
            with conn:
                claimed = conn.execute("UPDATE posts SET status='retrying' WHERE id=? AND status='failed' AND fb_post_id IS NULL", (post_id,)).rowcount
        finally:
            conn.close()
        if not claimed:
            return False, 'Posting sedang diproses, sudah berhasil, atau perlu pemeriksaan hasil sebelumnya'
        try:
            result = self._retry_claimed_post(post_id)
        except Exception as exc:
            result = (False, 'Hasil pengiriman belum pasti; periksa Facebook lalu tandai hasilnya di dashboard (Sudah tayang / Tidak tayang). ' + redact(str(exc))[:120])
            # Leave retrying after an uncertain exception to prevent duplicates:
            # the exception may come after Facebook already accepted the post.
            conn = get_db_connection()
            try:
                with conn:
                    conn.execute('UPDATE posts SET error_message=? WHERE id=?', (result[1], post_id))
            finally:
                conn.close()
            return result
        if not result[0]:
            conn = get_db_connection()
            try:
                with conn:
                    conn.execute("UPDATE posts SET status='failed',error_message=? WHERE id=? AND status='retrying'", (result[1],post_id))
            finally:
                conn.close()
        return result

    def _retry_claimed_post(self, post_id):
        """Retry a failed post using its already-generated caption and image."""
        conn = get_db_connection()
        row = conn.execute(
            "SELECT * FROM posts WHERE id = ? AND status != 'success'", (post_id,)
        ).fetchone()
        conn.close()
        if not row:
            return False, 'Postingan tidak ditemukan atau sudah berhasil diposting'

        if not row['image_path']:
            return False, 'Lokasi gambar tidak tercatat; belum tentu file telah terhapus'
        image_path = Path(row['image_path']).resolve()
        if not image_path.is_relative_to(IMAGES_DIR.resolve()):
            return False, 'Lokasi gambar berada di luar folder hasil generate'
        if not image_path or not image_path.exists():
            return False, 'File gambar hasil generate sudah tidak tersedia'
        if not (row['content'] or '').strip():
            return False, 'Caption hasil generate tidak tersedia'

        page = next((p for p in self.fanspages if str(p.get('page_id')) == str(row['page_id'])), None)
        if not page:
            return False, 'Konfigurasi Fanspage tidak ditemukan'
        valid, token_error = self.validate_token(page)
        if not valid:
            return False, token_error

        # Never send the old text-only fallback. Unreviewed real artwork can
        # be reviewed again without paying for another image generation.
        from core.generation_reliability import load_review, save_review
        from core.content_quality import require_publishable, ContentQualityError
        try:
            topic = load_review(page['page_id'], image_path, row['content'])
            if topic.get('image_fallback'):
                return False, 'Ilustrasi fallback tidak boleh dikirim; gunakan generate ulang'
            if topic.get('image_score') is None:
                topic['image_score'], _ = self._review_image(image_path, topic, page['name'])
                save_review(page['page_id'], image_path, row['content'], topic)
            require_publishable(topic)
        except ContentQualityError as exc:
            return False, str(exc)

        fb_post_id, error = self.post_to_facebook(page, row['content'], image_path, single_attempt=True)
        conn = get_db_connection()
        if fb_post_id:
            conn.execute(
                "UPDATE posts SET fb_post_id = ?, status = 'success', error_message = NULL, timestamp = ? WHERE id = ?",
                (fb_post_id, datetime.now().astimezone().isoformat(), post_id),
            )
        else:
            conn.execute("UPDATE posts SET error_message = ? WHERE id = ?", (error, post_id))
        conn.commit()
        conn.close()
        if fb_post_id:
            self._send_promo_comment(page, fb_post_id, row['content'])
        return (True, fb_post_id) if fb_post_id else (False, error)

    def process_queue(self):
        """Claim each due queue item before network work; uncertain sends stay held."""
        from core.content_quality import ContentQualityError
        conn = get_db_connection()
        try:
            rows = conn.execute("""SELECT * FROM post_queue WHERE status='pending'
                AND datetime(COALESCE(scheduled_time,created_at)) <= datetime('now')
                AND (next_attempt_at IS NULL OR datetime(next_attempt_at)<=datetime('now'))
                AND attempts<3 ORDER BY id LIMIT 10""").fetchall()
        finally:
            conn.close()
        for row in rows:
            page = next((p for p in self.fanspages if str(p['page_id'])==str(row['page_id']) and p.get('enabled',True)), None)
            if not page:
                continue
            conn = get_db_connection()
            try:
                with conn:
                    claimed = conn.execute("UPDATE post_queue SET status='processing',attempts=attempts+1 WHERE id=? AND status='pending'", (row['id'],)).rowcount
            finally:
                conn.close()
            if not claimed:
                continue
            status, message, fb_id = 'failed', '', None
            retries_left = row['attempts'] + 1 < 3
            try:
                self._review_queued_image(page, row['content'], row['image_path'])
                fb_id, message = self.post_to_facebook(page, row['content'], row['image_path'], single_attempt=True)
                # Penolakan pasti dari Facebook belum menayangkan apa pun, jadi
                # boleh dicoba lagi 15 menit kemudian selama jatah masih ada.
                status = 'posted' if fb_id else ('pending' if retries_left else 'failed')
                self.log_post(page, row['content'], row['image_path'], fb_id,
                              'success' if fb_id else 'failed', message)
                if fb_id:
                    self.update_last_post_time(page['page_id'])
            except Exception as exc:
                message = redact(exc)
                if status == 'posted':
                    pass  # sudah tayang; hanya pencatatan yang gagal
                elif isinstance(exc, UncertainSend):
                    status = 'uncertain'
                elif 'menunggu pemeriksaan' in message and retries_left:
                    status = 'pending'
                else:
                    status = 'failed'
            conn = get_db_connection()
            try:
                with conn:
                    conn.execute("""UPDATE post_queue SET status=?,error_message=?,
                        next_attempt_at=datetime('now','+15 minutes'),
                        posted_at=CASE WHEN ?='posted' THEN datetime('now') ELSE posted_at END
                        WHERE id=?""", (status, redact(message)[:500] if message else None,status,row['id']))
            finally:
                conn.close()

    def _review_queued_image(self, page, caption, image_path):
        from core.content_quality import caption_issues, require_publishable, ContentQualityError
        from core.generation_reliability import load_review, save_review
        # A known rejected image cannot be reclassified as a fresh upload.
        conn = get_db_connection()
        try:
            row = conn.execute('SELECT payload FROM visual_decisions WHERE image_path=? LIMIT 1',
                               (str(image_path),)).fetchone()
            if row and json.loads(row['payload']).get('density') == 'fallback':
                raise ContentQualityError('Poster fallback tidak boleh dipublikasikan')
        finally:
            conn.close()
        try:
            topic = load_review(page['page_id'], image_path, caption)
        except ContentQualityError:
            review = self.goldgen._editor_review(caption)
            issues = caption_issues(caption, review, None)
            if issues:
                raise ContentQualityError('; '.join(issues))
            topic = {'headline': caption.split('\n')[0][:100], 'approved_caption': caption,
                     'caption_approved': True, '_visual_page_id': page['page_id'],
                     'visual_plan': {'approved_image_copy': {'context': 'User uploaded artwork; check text and caption alignment'}}}
        if topic.get('image_score') is None:
            topic['image_score'], _ = self._review_image(image_path, topic, page['name'])
        save_review(page['page_id'], image_path, caption, topic)
        require_publishable(topic)

    # Batas pemakaian ulang caption yang gambarnya terus gagal: topik yang sulit
    # digambar tidak boleh menahan page selamanya.
    CAPTION_REUSE_HOURS = 3
    CAPTION_REUSE_MAX_FAILURES = 3

    def _resume_approved_caption(self, page):
        """Caption + topik yang sudah lolos, dari posting yang gagal HANYA karena gambar.

        Dulu setiap percobaan ulang slot membuat caption dari nol (2-6 panggilan
        teks) walau caption sebelumnya sudah disetujui editor.
        """
        from core.generation_reliability import load_review
        from core.content_quality import ContentQualityError, IMAGE_MIN_SCORE, valid_score
        conn = get_db_connection()
        try:
            rows = conn.execute('''SELECT content, image_path FROM posts
                WHERE page_id=? AND status='failed' AND content IS NOT NULL AND content != ''
                  AND image_path IS NOT NULL AND image_path != ''
                  AND julianday(timestamp) >= julianday('now', ?)
                ORDER BY id DESC LIMIT 3''', (str(page['page_id']), f'-{self.CAPTION_REUSE_HOURS} hours')).fetchall()
            for row in rows:
                published = conn.execute("SELECT 1 FROM posts WHERE page_id=? AND content=? AND status='success' LIMIT 1",
                                         (str(page['page_id']), row['content'])).fetchone()
                failures = conn.execute("SELECT COUNT(*) FROM posts WHERE page_id=? AND content=? AND status='failed'",
                                        (str(page['page_id']), row['content'])).fetchone()[0]
                if published or failures >= self.CAPTION_REUSE_MAX_FAILURES:
                    continue
                try:
                    topic = load_review(page['page_id'], row['image_path'], row['content'])
                except (ContentQualityError, OSError):
                    continue
                score = valid_score(topic.get('image_score'))
                image_failed = topic.get('image_fallback') or (score is not None and score < IMAGE_MIN_SCORE)
                if topic.get('caption_approved') is not True or not image_failed:
                    continue
                for key in ('image_fallback', 'visual_plan', '_image_learning', 'visual_feedback'):
                    topic.pop(key, None)
                topic['image_score'] = None
                return row['content'], topic
        finally:
            conn.close()
        return None

    def _resume_pending_review(self, page):
        """Reuse an unreviewed image from a failed generation within six hours."""
        from core.generation_reliability import load_review
        from core.content_quality import ContentQualityError
        conn = get_db_connection()
        try:
            rows = conn.execute('''SELECT content,image_path FROM posts
                WHERE page_id=? AND status='failed' AND image_score IS NULL
                AND datetime(timestamp)>=datetime('now','-6 hours')
                ORDER BY id DESC LIMIT 3''', (str(page['page_id']),)).fetchall()
        finally:
            conn.close()
        for row in rows:
            try:
                topic = load_review(page['page_id'], row['image_path'], row['content'])
            except (ContentQualityError, OSError):
                continue
            if topic.get('image_fallback') or topic.get('image_score') is not None:
                continue
            topic['image_score'], _ = self._review_image(row['image_path'], topic, page['name'])
            return row['content'], topic, row['image_path']
        return None

if __name__ == "__main__":
    import sys
    from core.locks import ProcessLock

    with ProcessLock('poster') as lock:
        if not lock.acquired:
            print("⏳ Another auto_poster instance is running. Exiting.")
            sys.exit(0)

        poster = GoldGenAutoPoster()
        poster.run()
