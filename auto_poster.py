#!/usr/bin/env python3
"""
GoldGen Auto Poster - Automated Facebook Posting
Generates gold price posters and posts to Facebook every 3 hours
"""

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
from core.safe_log import redact
from comment_analyzer import CommentAnalyzer

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
            
            for image_path in IMAGES_DIR.glob('*.png'):
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
                self.image_model = config.get('image_model', 'gemini-3.1-flash-image')
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
    

    def generate_content(self, page_id=None):
        """Generate educational content about gold prospecting"""
        topic = None
        try:
            topic = self.goldgen.get_next_topic(page_id)
            caption = self.goldgen.generate_caption(topic, page_id)
            return caption, topic
        except Exception as e:
            print(f"   ⚠️  GoldGen caption error: {e}, using fallback...")
            # Fallback using the fetched topic, or default to first if get_next_topic failed
            if not topic:
                topic = self.goldgen.topics[0]
            list_text = "\n".join([f"• {point}" for point in topic['list_points']])
            caption = f"""{topic['headline']}

{topic['subtitle']}

{topic['list_header']}:
{list_text}

#GoldProspecting #PlacerGold #ProspectingTips"""
            return caption, topic
    
    
    def generate_image(self, topic, fanspage_name=None, page_id=None):
        """Generate educational infographic using Gemini image model"""
        # Prompt dibangun di luar blok retry supaya retry tidak crash karena
        # variabel yang belum sempat terbentuk saat error terjadi di sini.
        try:
            image_prompt = self.goldgen.generate_image_prompt(topic, page_id)
        except Exception as e:
            print(f"   ⚠️  Gagal membangun image prompt: {e}, using PIL fallback...")
            return self._generate_fallback_image(topic, fanspage_name)

        if fanspage_name:
            image_prompt += f"\n\nIMPORTANT INSTRUCTION: Add a subtle text watermark that says '{fanspage_name}' placed clearly in one of the corners of the image (e.g. bottom-right or bottom-left corner). Do NOT put the watermark in the center of the image."

        max_attempts = 2
        for attempt in range(max_attempts):
            try:
                from google.genai import types

                label = f"{self.image_model}" + (" (retry)" if attempt else "")
                print(f"   Generating image with {label}...")

                client = genai.Client(api_key=self.gemini_api_key)
                response = client.models.generate_content(
                    model=self.image_model,
                    contents=image_prompt,
                    config=types.GenerateContentConfig(
                        response_modalities=['TEXT', 'IMAGE'],
                        image_config=types.ImageConfig(
                            aspect_ratio="9:16",
                            image_size="2K"
                        )
                    )
                )

                for part in response.parts:
                    if image := part.as_image():
                        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                        image_path = IMAGES_DIR / f"gold_prospecting_{timestamp}.png"
                        image.save(str(image_path))
                        print(f"   ✅ Image generated with {label}")
                        return image_path

                print(f"   ⚠️  No image in response, using PIL fallback...")
                return self._generate_fallback_image(topic, fanspage_name)

            except Exception as e:
                if attempt < max_attempts - 1:
                    print(f"   ⚠️  Gemini error: {redact(e)}, retrying in 30s...")
                    time.sleep(30)
                else:
                    print(f"   ⚠️  Gemini retry failed: {redact(e)}, using PIL fallback...")

        return self._generate_fallback_image(topic, fanspage_name)
    
    def _generate_fallback_image(self, topic, fanspage_name=None):
        """Generate professional infographic locally with PIL"""
        # Create image 1080x1920 (vertical format)
        width, height = 1080, 1920
        
        # Create gradient background (dark earth tones)
        img = Image.new('RGB', (width, height))
        draw = ImageDraw.Draw(img)
        
        # Draw gradient from dark brown to darker
        for i in range(height):
            ratio = i / height
            r = int(42 - ratio * 20)
            g = int(37 - ratio * 20)
            b = int(32 - ratio * 20)
            draw.rectangle([(0, i), (width, i+1)], fill=(r, g, b))
        
        # Gold accent borders
        border_width = 20
        gold_color = '#D4A523'
        draw.rectangle([(0, 0), (width, border_width)], fill=gold_color)
        draw.rectangle([(0, height-border_width), (width, height)], fill=gold_color)
        draw.rectangle([(0, 0), (border_width, height)], fill=gold_color)
        draw.rectangle([(width-border_width, 0), (width, height)], fill=gold_color)
        
        # Load fonts
        try:
            title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 90)
            subtitle_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 50)
            header_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 55)
            list_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 42)
            footer_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 32)
        except:
            title_font = ImageFont.load_default()
            subtitle_font = ImageFont.load_default()
            header_font = ImageFont.load_default()
            list_font = ImageFont.load_default()
            footer_font = ImageFont.load_default()
        
        # Icon/emoji at top
        y_pos = 120
        draw.text((width/2, y_pos), "🪨", font=title_font, anchor="mm")
        
        # Headline (gold color, centered)
        y_pos += 150
        draw.text((width/2, y_pos), topic['headline'], 
                 fill=gold_color, font=title_font, anchor="mm", stroke_width=2, stroke_fill='#000000')
        
        # Subtitle (white, centered)
        y_pos += 130
        draw.text((width/2, y_pos), topic['subtitle'], 
                 fill='#FFFFFF', font=subtitle_font, anchor="mm")
        
        # Decorative line
        y_pos += 80
        line_margin = 150
        draw.rectangle([(line_margin, y_pos), (width-line_margin, y_pos+5)], fill=gold_color)
        
        # List header (gold, centered)
        y_pos += 100
        draw.text((width/2, y_pos), topic['list_header'], 
                 fill=gold_color, font=header_font, anchor="mm")
        
        # List points (white, left-aligned with bullets)
        y_pos += 100
        left_margin = 120
        for point in topic['list_points']:
            # Bullet point
            draw.ellipse([(left_margin, y_pos+15), (left_margin+15, y_pos+30)], fill=gold_color)
            # Text
            draw.text((left_margin + 40, y_pos), point, 
                     fill='#FFFFFF', font=list_font)
            y_pos += 90
        
        # Footer text
        y_pos = height - 200
        draw.text((width/2, y_pos), "Learn the signs. Find the gold.", 
                 fill='#AAAAAA', font=footer_font, anchor="mm")
        
        y_pos += 60
        draw.text((width/2, y_pos), "🤖 Content created with AI assistance", 
                 fill='#888888', font=footer_font, anchor="mm")
        
        # Save image
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        image_path = IMAGES_DIR / f"gold_prospecting_{timestamp}.png"
        img.save(image_path, 'PNG', quality=95)
        
        print(f"   ✅ Infographic generated successfully")
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
            reason = "PARAMETER DITOLAK: request tidak diterima Facebook (mis. place/feeling tidak valid)."
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
        url = f"https://graph.facebook.com/v18.0/{fanspage['page_id']}"
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
                    print(f"   ⚠️  Network/DNS glitch validating token for {fanspage.get('name')}: {e}. Retrying in {delay}s ({attempt + 1}/{max_retries})...")
                    time.sleep(delay)
                else:
                    return False, f"Network error after {max_retries} attempts: {str(e)}"
        
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

    def post_to_facebook(self, fanspage, content, image_path):
        """Post content and image to Facebook page with retry"""
        # Validate token first
        valid, error = self.validate_token(fanspage)
        if not valid:
            print(f"   ❌ {error}")
            return None, error
        
        # Facebook Feeling/Activity IDs (official)
        feelings = {
            'excited': '115',
            'motivated': '106',
            'blessed': '242',
            'determined': '114',
            'hopeful': '109'
        }
        
        # Top gold mining locations worldwide with Facebook Place IDs
        top_locations = [
            # USA
            {'name': 'Fairbanks, Alaska', 'place_id': '110843418940484'},
            {'name': 'Nevada City, California', 'place_id': '111975398821990'},
            {'name': 'Juneau, Alaska', 'place_id': '105535939477573'},
            {'name': 'Denver, Colorado', 'place_id': '115590505119035'},
            {'name': 'Deadwood, South Dakota', 'place_id': '108424385857528'},
            # Australia
            {'name': 'Kalgoorlie, Western Australia', 'place_id': '108659255821735'},
            {'name': 'Ballarat, Victoria', 'place_id': '110822688939497'},
            # Canada
            {'name': 'Dawson City, Yukon', 'place_id': '111948228824766'},
            {'name': 'Timmins, Ontario', 'place_id': '109503229067684'},
            {'name': 'Yellowknife, Northwest Territories', 'place_id': '110560688970018'},
            # South Africa
            {'name': 'Johannesburg, South Africa', 'place_id': '110471888969932'},
            {'name': 'Kimberley, South Africa', 'place_id': '108103742550819'},
            # South America
            {'name': 'Ouro Preto, Brazil', 'place_id': '112149645469956'},
            {'name': 'La Rinconada, Peru', 'place_id': '106377926061356'},
            # Other
            {'name': 'Lihir Island, Papua New Guinea', 'place_id': '114952118520588'},
            {'name': 'Carlin, Nevada', 'place_id': '109435549074552'},
        ]
        
        # Rotate location
        import random
        location = random.choice(top_locations)
        feeling_id = random.choice(list(feelings.values()))
        
        # Try posting with retry
        max_retries = 3
        for attempt in range(max_retries):
            try:
                url = f"https://graph.facebook.com/v18.0/{fanspage['page_id']}/photos"
                
                with open(image_path, 'rb') as image_file:
                    files = {'source': image_file}
                    data = {
                        'message': content,
                        'access_token': fanspage['access_token'],
                        'feeling_id': feeling_id,
                        'place': location['place_id']
                    }
                    
                    response = requests.post(url, data=data, files=files, timeout=30)
                    
                    if response.status_code == 200:
                        post_id = self._extract_post_id(response.json())
                        print(f"   📍 Location: {location['name']}")

                        # Send Telegram notification
                        send_notification(f"✅ <b>Goldgen Bot</b>\n\n📝 Posted to Facebook\n📍 {location['name']}\n🆔 {post_id}")

                        return post_id, None
                    else:
                        error_msg = self._describe_fb_error(response)
                        raw_text = response.text or ''
                        # If place/feeling fails, retry without them
                        if 'place' in raw_text or 'feeling' in raw_text:
                            print(f"   ⚠️  Metadata failed, posting without location/feeling...")
                            data = {
                                'message': content,
                                'access_token': fanspage['access_token']
                            }
                            image_file.seek(0)  # Reset file pointer
                            response = requests.post(url, data=data, files={'source': image_file}, timeout=30)
                            if response.status_code == 200:
                                return self._extract_post_id(response.json()), None
                        
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
                if attempt < max_retries - 1:
                    delay = 2 ** attempt
                    print(f"   ⚠️  Error: {redact(e)}, retry {attempt + 1}/{max_retries} after {delay}s")
                    time.sleep(delay)
                else:
                    reason = f"GAGAL MENGIRIM: {type(e).__name__}: {redact(e)[:200]} (setelah {max_retries} percobaan)"
                    send_notification(f"❌ <b>Goldgen Bot Error</b>\n\n{reason[:300]}")
                    return None, reason

        return None, f"GAGAL MENGIRIM: batas percobaan ({max_retries}x) habis tanpa respons sukses dari Facebook"
    
    def log_post(self, fanspage, content, image_path, fb_post_id, status, error_message=None, layout_name=None, hook_type=None, editor_score=None, requested_hook=None, topic_id=None, topic_headline=None):
        """Log post to database"""
        from datetime import timezone, timedelta
        now_wib = datetime.now(timezone(timedelta(hours=7)))
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO posts (timestamp, page_id, page_name, content, image_path, fb_post_id, status, error_message, layout_name, hook_type, editor_score, requested_hook, topic_id, topic_headline)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            now_wib.isoformat(),
            fanspage['page_id'],
            fanspage['name'],
            content,
            str(image_path),
            fb_post_id,
            status,
            error_message,
            layout_name,
            hook_type,
            editor_score,
            requested_hook,
            topic_id,
            topic_headline
        ))
        conn.commit()
        conn.close()
    
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
            
            last_posted = datetime.fromisoformat(result[0])
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
            last_posted = datetime.fromisoformat(result[0])
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
            if not fanspage.get('enabled', True):
                print(f"⏭️  Skipping {fanspage['name']} (disabled)")
                continue
            
            if not self.should_post(fanspage):
                schedule_info = f"schedule: {fanspage.get('schedule_hours', 'N/A')}" if 'schedule_hours' in fanspage else f"interval: {fanspage.get('interval_hours', 6)}h"
                print(f"⏰ Skipping {fanspage['name']} ({schedule_info})")
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
                self.update_last_post_time(fanspage['page_id'])

                # [JIT ML RESEARCH] - Lakukan riset tepat sebelum merancang konten
                try:
                    analyzer = CommentAnalyzer()
                    jit_result = analyzer.analyze_single_page(fanspage)
                    if jit_result:
                        print(f"   🧠 JIT ML Research sukses untuk {fanspage['name']}")
                    else:
                        print(f"   ℹ️  JIT ML Research: data belum cukup untuk {fanspage['name']} (konten pakai rotasi biasa)")
                except Exception as e:
                    print(f"   ⚠️  JIT ML Research failed for {fanspage.get('name')}: {type(e).__name__}: {e} (continuing to post)")

                # Generate content with offset topic (different for each fanspage)
                # Bikin caption & prompt pake GoldGen AI (sekarang sudah terisolasi per-page)
                content, topic = self.generate_content(page_id=fanspage['page_id'])
                print(f"   Topic: {topic['headline']}")
                print(f"   Layout: {topic['layout']}")
                
                # Generate poster image
                print("   Generating infographic...")
                image_path = self.generate_image(topic, fanspage_name=fanspage['name'], page_id=fanspage['page_id'])
                
                # Post to Facebook
                print("   Posting to Facebook...")
                fb_post_id, error = self.post_to_facebook(fanspage, content, image_path)
                
                if fb_post_id:
                    print(f"   ✅ Success! Post ID: {fb_post_id}")
                    self.log_post(fanspage, content, image_path, fb_post_id, 'success', layout_name=topic.get('layout'), hook_type=topic.get('hook_type'), editor_score=topic.get('editor_score'), requested_hook=topic.get('requested_hook'), topic_id=topic.get('id'), topic_headline=topic.get('headline'))
                    posted_count += 1
                else:
                    print(f"   ❌ Failed: {error}")
                    self.log_post(fanspage, content, image_path, None, 'failed', error, layout_name=topic.get('layout'), hook_type=topic.get('hook_type'), editor_score=topic.get('editor_score'), requested_hook=topic.get('requested_hook'), topic_id=topic.get('id'), topic_headline=topic.get('headline'))
                
                print()

                
            except Exception as e:
                # Status 'failed' (bukan 'error') supaya ikut terhitung di statistik
                # dan tampil di dashboard bersama alasannya.
                import traceback
                error_msg = f"GAGAL DIPROSES: {type(e).__name__}: {redact(e)[:300]}"
                print(f"   ❌ {error_msg}\n")
                traceback.print_exc()
                self.log_post(fanspage, "", "", None, 'failed', error_msg)

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
        print(f"[{datetime.now()}] Starting forced manual post for {target_page_id}...")
        
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
            
            # 4. Generate Image
            print(f"   🎨 Generating image...")
            image_path = self.generate_image(topic, fanspage_name=page_name, page_id=page_id)
            
            print("   Posting to Facebook...")
            fb_post_id, error = self.post_to_facebook(target_fanspage, caption, image_path)
            
            if fb_post_id:
                print(f"   ✅ Success! Post ID: {fb_post_id}")
                self.log_post(target_fanspage, caption, image_path, fb_post_id, 'success', layout_name=topic.get('layout'), hook_type=topic.get('hook_type'), editor_score=topic.get('editor_score'), requested_hook=topic.get('requested_hook'), topic_id=topic.get('id'), topic_headline=topic.get('headline'))
                self.update_last_post_time(target_fanspage['page_id'])
                
                next_index = (base_topic_index + 1) % len(self.goldgen.topics)
                self.goldgen.state_file.parent.mkdir(parents=True, exist_ok=True)
                with open(self.goldgen.state_file, 'w') as f:
                    json.dump({'current_topic_index': next_index, 'last_updated': datetime.now().isoformat()}, f)
                    
                return True, fb_post_id
            else:
                print(f"   ❌ Failed: {error}")
                self.log_post(target_fanspage, caption, image_path, None, 'failed', error, layout_name=topic.get('layout'), hook_type=topic.get('hook_type'), editor_score=topic.get('editor_score'), requested_hook=topic.get('requested_hook'), topic_id=topic.get('id'), topic_headline=topic.get('headline'))
                return False, error
                
        except Exception as e:
            import traceback
            error_msg = f"GAGAL DIPROSES: {type(e).__name__}: {redact(e)[:300]}"
            print(f"   ❌ {error_msg}\n")
            traceback.print_exc()
            self.log_post(target_fanspage, "", "", None, 'failed', error_msg)
            return False, error_msg

    def process_queue(self):
        """Process queued posts from web app"""
        print("\n🔄 Checking post queue from web app...")
        
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Get pending posts
            cursor.execute('''
                SELECT id, page_id, content, image_path
                FROM post_queue
                WHERE status = 'pending'
                ORDER BY COALESCE(scheduled_time, created_at) ASC
                LIMIT 10
            ''')
            
            queued_posts = cursor.fetchall()
            
            if not queued_posts:
                print("   No queued posts found.\n")
                conn.close()
                return
            
            print(f"   Found {len(queued_posts)} queued post(s)\n")
            
            for post_id, page_id, caption, image_path in queued_posts:
                # Find fanspage config
                fanspage = None
                for page in self.fanspages:
                    if page['page_id'] == page_id:
                        fanspage = page
                        break
                
                if not fanspage:
                    print(f"   ⚠️  Page ID {page_id} not found in config, skipping...")
                    cursor.execute(
                        'UPDATE post_queue SET status = ?, error_message = ? WHERE id = ?',
                        ('error', f'Page ID {page_id} tidak ada di config', post_id)
                    )
                    continue
                
                if not fanspage.get('enabled', True):
                    print(f"   ⏭️  {fanspage['name']} disabled, skipping...")
                    continue
                
                print(f"   📤 Posting queued content to {fanspage['name']}...")
                
                try:
                    # Post to Facebook
                    fb_post_id, error = self.post_to_facebook(fanspage, caption, image_path)
                    
                    if fb_post_id:
                        print(f"      ✅ Success! Post ID: {fb_post_id}")
                        
                        # Update queue status
                        cursor.execute('''
                            UPDATE post_queue
                            SET status = ?, posted_at = ?, error_message = NULL
                            WHERE id = ?
                        ''', ('posted', datetime.now().isoformat(), post_id))
                        
                        # Log to posts table
                        self.log_post(fanspage, caption, image_path, fb_post_id, 'success')
                        self.update_last_post_time(fanspage['page_id'])
                    else:
                        print(f"      ❌ Failed: {error}")
                        cursor.execute(
                            'UPDATE post_queue SET status = ?, error_message = ? WHERE id = ?',
                            ('failed', str(error)[:500], post_id)
                        )
                        self.log_post(fanspage, caption, image_path, None, 'failed', error)

                except Exception as e:
                    print(f"      ❌ Error: {str(e)}")
                    cursor.execute(
                        'UPDATE post_queue SET status = ?, error_message = ? WHERE id = ?',
                        ('error', str(e)[:500], post_id)
                    )
            
            conn.commit()
            conn.close()
            print()
            
        except Exception as e:
            print(f"   ❌ Queue processing error: {str(e)}\n")

if __name__ == "__main__":
    import sys
    from core.locks import ProcessLock

    with ProcessLock('poster') as lock:
        if not lock.acquired:
            print("⏳ Another auto_poster instance is running. Exiting.")
            sys.exit(0)

        poster = GoldGenAutoPoster()
        poster.run()
