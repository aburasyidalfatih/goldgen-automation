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

# Telegram notifier
try:
    from telegram_notifier import send_notification
except:
    def send_notification(msg):
        pass

from core.config import BASE_DIR, DATA_DIR, LOGS_DIR, IMAGES_DIR, DB_PATH, CONFIG_PATH
from core.database import get_db_connection

# Ensure directories exist
DATA_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)
IMAGES_DIR.mkdir(exist_ok=True)

class GoldGenAutoPoster:
    def __init__(self):
        self.load_config()
        self.init_database()
        self.setup_gemini()
        self.cleanup_old_images()  # Cleanup on startup
    
    def cleanup_old_images(self, days=1):
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
        """Initialize SQLite database for tracking posts"""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                page_id TEXT NOT NULL,
                page_name TEXT,
                content TEXT NOT NULL,
                image_path TEXT,
                fb_post_id TEXT,
                status TEXT DEFAULT 'success',
                error_message TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS last_post_time (
                page_id TEXT PRIMARY KEY,
                last_posted TEXT NOT NULL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS post_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                page_id TEXT NOT NULL,
                caption TEXT,
                image_path TEXT,
                status TEXT DEFAULT 'pending',
                created_at TEXT NOT NULL,
                posted_at TEXT,
                error_message TEXT
            )
        ''')
        conn.commit()
        conn.close()
    
    def setup_gemini(self):
        """Setup Gemini AI with GoldGen style"""
        from goldgen_service import GoldGenService
        self.goldgen = GoldGenService(self.gemini_api_key, model=self.text_model)
    

    def generate_content(self):
        """Generate educational content about gold prospecting"""
        try:
            topic = self.goldgen.get_next_topic()
            caption = self.goldgen.generate_caption(topic)
            return caption, topic
        except Exception as e:
            print(f"   ⚠️  GoldGen caption error: {e}, using fallback...")
            # Fallback to first topic with layout
            topic = self.goldgen.get_next_topic()
            list_text = "\n".join([f"• {point}" for point in topic['list_points']])
            caption = f"""{topic['headline']}

{topic['subtitle']}

{topic['list_header']}:
{list_text}

#GoldProspecting #PlacerGold #ProspectingTips"""
            return caption, topic
    
    def generate_content_with_offset(self, offset=0):
        """Generate content with topic offset (for multiple fanspages in one cycle)"""
        try:
            topic = self.goldgen.get_topic_with_offset(offset)
            caption = self.goldgen.generate_caption(topic)
            return caption, topic
        except Exception as e:
            print(f"   ⚠️  GoldGen caption error: {e}, using fallback...")
            topic = self.goldgen.get_topic_with_offset(offset)
            list_text = "\n".join([f"• {point}" for point in topic['list_points']])
            caption = f"""{topic['headline']}

{topic['subtitle']}

{topic['list_header']}:
{list_text}

#GoldProspecting #PlacerGold #ProspectingTips"""
            return caption, topic
    
    def _generate_fallback_caption(self, gold_data):
        """Fallback caption if GoldGen fails"""
        return f"""💰 UPDATE HARGA EMAS HARI INI

Harga emas per gram: Rp {gold_data['price']:,}
Perubahan: {gold_data['change']}
Tanggal: {gold_data['date']}

Pantau terus pergerakan harga emas untuk keputusan investasi yang tepat!

#HargaEmas #InvestasiEmas #EmasHariIni #GoldPrice"""
    
    def generate_poster_image(self, topic, fanspage_name=None):
        """Generate educational infographic using Gemini image model"""
        try:
            from google.genai import types

            print(f"   Generating image with {self.image_model}...")

            image_prompt = self.goldgen.generate_image_prompt(topic)
            if fanspage_name:
                image_prompt += f"\n\nIMPORTANT INSTRUCTION: Add a subtle text watermark that says '{fanspage_name}' placed clearly in one of the corners of the image (e.g. bottom-right or bottom-left corner). Do NOT put the watermark in the center of the image."
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
                    print(f"   ✅ Image generated with {self.image_model}")
                    return image_path

            print(f"   ⚠️  No image in response, using PIL fallback...")
            return self._generate_fallback_image(topic, fanspage_name)

        except Exception as e:
            print(f"   ⚠️  Gemini error: {e}, retrying in 30s...")
            import time
            time.sleep(30)
            try:
                from google.genai import types
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
                        print(f"   ✅ Image generated with {self.image_model} (retry)")
                        return image_path
            except Exception as e2:
                print(f"   ⚠️  Gemini retry failed: {e2}, using PIL fallback...")
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
    
    def validate_token(self, fanspage):
        """Validate Facebook token before posting"""
        try:
            url = f"https://graph.facebook.com/v18.0/{fanspage['page_id']}"
            params = {'access_token': fanspage['access_token'], 'fields': 'name'}
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                return True, None
            else:
                error = response.json().get('error', {})
                return False, error.get('message', 'Unknown error')
        except Exception as e:
            return False, str(e)
    
    def post_to_facebook(self, fanspage, content, image_path):
        """Post content and image to Facebook page with retry"""
        # Validate token first
        valid, error = self.validate_token(fanspage)
        if not valid:
            print(f"   ❌ Token validation failed: {error}")
            return None, f"Invalid token: {error}"
        
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
                        result = response.json()
                        post_id = result.get('id')
                        print(f"   📍 Location: {location['name']}")
                        
                        # Send Telegram notification
                        send_notification(f"✅ <b>Goldgen Bot</b>\n\n📝 Posted to Facebook\n📍 {location['name']}\n🆔 {post_id}")
                        
                        return post_id, None
                    else:
                        error_msg = response.text
                        # If place/feeling fails, retry without them
                        if 'place' in error_msg or 'feeling' in error_msg:
                            print(f"   ⚠️  Metadata failed, posting without location/feeling...")
                            data = {
                                'message': content,
                                'access_token': fanspage['access_token']
                            }
                            image_file.seek(0)  # Reset file pointer
                            response = requests.post(url, data=data, files={'source': image_file}, timeout=30)
                            if response.status_code == 200:
                                return response.json().get('id'), None
                        
                        if attempt < max_retries - 1:
                            delay = 2 ** attempt
                            print(f"   ⚠️  Retry {attempt + 1}/{max_retries} after {delay}s")
                            time.sleep(delay)
                        else:
                            return None, error_msg
                        
            except Exception as e:
                if attempt < max_retries - 1:
                    delay = 2 ** attempt
                    print(f"   ⚠️  Error: {e}, retry {attempt + 1}/{max_retries} after {delay}s")
                    time.sleep(delay)
                else:
                    send_notification(f"❌ <b>Goldgen Bot Error</b>\n\n{str(e)[:200]}")
                    return None, str(e)
        
        return None, "Max retries exceeded"
    
    def log_post(self, fanspage, content, image_path, fb_post_id, status, error_message=None, layout_name=None):
        """Log post to database"""
        from datetime import timezone, timedelta
        now_wib = datetime.now(timezone(timedelta(hours=7)))
        conn = get_db_connection()
        cursor = conn.cursor()
        # Add layout_name column if not exists
        try:
            cursor.execute("ALTER TABLE posts ADD COLUMN layout_name TEXT")
            conn.commit()
        except Exception:
            pass
        cursor.execute('''
            INSERT INTO posts (timestamp, page_id, page_name, content, image_path, fb_post_id, status, error_message, layout_name)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            now_wib.isoformat(),
            fanspage['page_id'],
            fanspage['name'],
            content,
            str(image_path),
            fb_post_id,
            status,
            error_message,
            layout_name
        ))
        conn.commit()
        conn.close()
    
    def should_post(self, fanspage):
        """Check if current hour matches fanspage schedule"""
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
        cursor.execute('''
            INSERT OR REPLACE INTO last_post_time (page_id, timestamp)
            VALUES (?, ?)
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
                    print(f"   ❌ Token invalid: {token_error}")
                    print("   ⚠️  Skipping generation to save Gemini API tokens.")
                    self.log_post(fanspage, "[SKIPPED]", "", None, 'failed', f"Token validation failed before generation: {token_error}")
                    continue

                # Generate content with offset topic (different for each fanspage)
                print("   Generating educational content...")
                content, topic = self.generate_content_with_offset(idx)
                print(f"   Topic: {topic['headline']}")
                print(f"   Layout: {topic['layout']}")
                
                # Generate poster image
                print("   Generating infographic...")
                image_path = self.generate_poster_image(topic, fanspage_name=fanspage['name'])
                
                # Post to Facebook
                print("   Posting to Facebook...")
                fb_post_id, error = self.post_to_facebook(fanspage, content, image_path)
                
                if fb_post_id:
                    print(f"   ✅ Success! Post ID: {fb_post_id}")
                    self.log_post(fanspage, content, image_path, fb_post_id, 'success', layout_name=topic.get('layout'))
                    self.update_last_post_time(fanspage['page_id'])
                    posted_count += 1
                else:
                    print(f"   ❌ Failed: {error}")
                    self.log_post(fanspage, content, image_path, None, 'failed', error, layout_name=topic.get('layout'))
                
                print()
                
                # Delay 1 hour between fanspages to avoid spam detection
                if posted_count > 0 and idx < len(self.fanspages) - 1:
                    # Check if there are more enabled pages to post
                    has_more = any(
                        p.get('enabled', True) and self.should_post(p) 
                        for p in self.fanspages[idx+1:]
                    )
                    if has_more:
                        delay_seconds = self.fanspage_delay_minutes * 60
                        print(f"⏳ Waiting {self.fanspage_delay_minutes} minutes before next fanspage...")
                        print(f"   Next post at: {(datetime.now() + timedelta(seconds=delay_seconds)).strftime('%H:%M:%S')}\n")
                        time.sleep(delay_seconds)
                
            except Exception as e:
                error_msg = str(e)
                print(f"   ❌ Error: {error_msg}\n")
                self.log_post(fanspage, "", "", None, 'error', error_msg)
        
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
                
            idx = self.fanspages.index(target_fanspage)

            print("   Generating educational content...")
            content, topic = self.generate_content_with_offset(idx)
            
            print("   Generating infographic...")
            image_path = self.generate_poster_image(topic, fanspage_name=target_fanspage['name'])
            
            print("   Posting to Facebook...")
            fb_post_id, error = self.post_to_facebook(target_fanspage, content, image_path)
            
            if fb_post_id:
                print(f"   ✅ Success! Post ID: {fb_post_id}")
                self.log_post(target_fanspage, content, image_path, fb_post_id, 'success', layout_name=topic.get('layout'))
                self.update_last_post_time(target_fanspage['page_id'])
                
                next_index = (base_topic_index + 1) % len(self.goldgen.topics)
                self.goldgen.state_file.parent.mkdir(parents=True, exist_ok=True)
                with open(self.goldgen.state_file, 'w') as f:
                    json.dump({'current_topic_index': next_index, 'last_updated': datetime.now().isoformat()}, f)
                    
                return True, fb_post_id
            else:
                print(f"   ❌ Failed: {error}")
                self.log_post(target_fanspage, content, image_path, None, 'failed', error, layout_name=topic.get('layout'))
                return False, error
                
        except Exception as e:
            error_msg = str(e)
            print(f"   ❌ Error: {error_msg}\n")
            self.log_post(target_fanspage, "", "", None, 'error', error_msg)
            return False, error_msg

    def process_queue(self):
        """Process queued posts from web app"""
        print("\n🔄 Checking post queue from web app...")
        
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Get pending posts
            cursor.execute('''
                SELECT id, page_id, content as caption, image_path
                FROM post_queue
                WHERE status = 'pending'
                ORDER BY scheduled_time ASC
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
                    cursor.execute('UPDATE post_queue SET status = ? WHERE id = ?', ('error', post_id))
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
                            SET status = ?, posted_at = ?
                            WHERE id = ?
                        ''', ('posted', datetime.now().isoformat(), post_id))
                        
                        # Log to posts table
                        self.log_post(fanspage, caption, image_path, fb_post_id, 'success')
                        self.update_last_post_time(fanspage['page_id'])
                    else:
                        print(f"      ❌ Failed: {error}")
                        cursor.execute('UPDATE post_queue SET status = ? WHERE id = ?', ('failed', post_id))
                        self.log_post(fanspage, caption, image_path, None, 'failed', error)
                
                except Exception as e:
                    print(f"      ❌ Error: {str(e)}")
                    cursor.execute('UPDATE post_queue SET status = ? WHERE id = ?', ('error', post_id))
            
            conn.commit()
            conn.close()
            print()
            
        except Exception as e:
            print(f"   ❌ Queue processing error: {str(e)}\n")

if __name__ == "__main__":
    poster = GoldGenAutoPoster()
    poster.run()
