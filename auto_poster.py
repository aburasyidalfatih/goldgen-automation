#!/usr/bin/env python3
"""
GoldGen Auto Poster - Automated Facebook Posting
Generates gold price posters and posts to Facebook every 3 hours
"""

import os
import json
import sqlite3
import requests
from datetime import datetime, timedelta
from pathlib import Path
from google import genai
from PIL import Image, ImageDraw, ImageFont
import io
import base64
import time

# Configuration
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"
IMAGES_DIR = BASE_DIR / "generated_images"
DB_PATH = DATA_DIR / "posts.db"
CONFIG_PATH = DATA_DIR / "config.json"

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
    
    def cleanup_old_images(self, days=7):
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
        conn = sqlite3.connect(DB_PATH)
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
        conn.commit()
        conn.close()
    
    def setup_gemini(self):
        """Setup Gemini AI with GoldGen style"""
        from goldgen_service import GoldGenService
        self.goldgen = GoldGenService(self.gemini_api_key)
    

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
    
    def generate_poster_image(self, topic):
        """Generate educational infographic using Gemini 3.1 Pro"""
        try:
            from google.genai import types
            
            print(f"   Generating image with Gemini 3.1 Pro...")
            
            # Generate image prompt
            image_prompt = self.goldgen.generate_image_prompt(topic)
            
            # Use Gemini 3.1 Pro for image generation
            client = genai.Client(api_key=self.gemini_api_key)
            
            response = client.models.generate_content(
                model='gemini-3-pro-image-preview',
                contents=image_prompt,
                config=types.GenerateContentConfig(
                    image_config=types.ImageConfig(
                        aspect_ratio="9:16",  # Vertical story format
                        image_size="2K"
                    )
                )
            )
            
            # Extract image from response
            for part in response.parts:
                if hasattr(part, 'inline_data') and part.inline_data:
                    image_data = part.inline_data.data
                    
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    image_path = IMAGES_DIR / f"gold_prospecting_{timestamp}.png"
                    
                    with open(image_path, 'wb') as f:
                        f.write(image_data)
                    
                    print(f"   ✅ Image generated with Gemini 3.1 Pro")
                    return image_path
            
            print(f"   ⚠️  No image in response, using PIL fallback...")
            return self._generate_fallback_image(topic)
            
        except Exception as e:
            print(f"   ⚠️  Gemini error: {e}, using PIL fallback...")
            return self._generate_fallback_image(topic)
    
    def _generate_fallback_image(self, topic):
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
                        print(f"   📍 Location: {location['name']}")
                        return result.get('id'), None
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
                    return None, str(e)
        
        return None, "Max retries exceeded"
    
    def log_post(self, fanspage, content, image_path, fb_post_id, status, error_message=None):
        """Log post to database"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO posts (timestamp, page_id, page_name, content, image_path, fb_post_id, status, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            datetime.now().isoformat(),
            fanspage['page_id'],
            fanspage['name'],
            content,
            str(image_path),
            fb_post_id,
            status,
            error_message
        ))
        conn.commit()
        conn.close()
    
    def should_post(self, fanspage):
        """Check if enough time has passed since last post for this page"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('SELECT last_posted FROM last_post_time WHERE page_id = ?', (fanspage['page_id'],))
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            return True
        
        from datetime import timedelta
        last_posted = datetime.fromisoformat(result[0])
        interval = timedelta(hours=fanspage['interval_hours'])
        return datetime.now() >= last_posted + interval
    
    def update_last_post_time(self, page_id):
        """Update last post time for a page"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO last_post_time (page_id, last_posted)
            VALUES (?, ?)
        ''', (page_id, datetime.now().isoformat()))
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
        fanspage_offset = 0  # Track offset for topic assignment
        
        for idx, fanspage in enumerate(self.fanspages):
            if not fanspage.get('enabled', True):
                print(f"⏭️  Skipping {fanspage['name']} (disabled)")
                continue
            
            if not self.should_post(fanspage):
                print(f"⏰ Skipping {fanspage['name']} (interval not reached)")
                continue
            
            try:
                print(f"📄 Processing: {fanspage['name']}")
                print(f"   Page ID: {fanspage['page_id']}")
                print(f"   Interval: {fanspage['interval_hours']} hours")
                
                # Generate content with offset topic (different for each fanspage)
                print("   Generating educational content...")
                content, topic = self.generate_content_with_offset(fanspage_offset)
                print(f"   Topic: {topic['headline']}")
                print(f"   Layout: {topic['layout']}")
                
                # Generate poster image
                print("   Generating infographic...")
                image_path = self.generate_poster_image(topic)
                
                # Post to Facebook
                print("   Posting to Facebook...")
                fb_post_id, error = self.post_to_facebook(fanspage, content, image_path)
                
                if fb_post_id:
                    print(f"   ✅ Success! Post ID: {fb_post_id}")
                    self.log_post(fanspage, content, image_path, fb_post_id, 'success')
                    self.update_last_post_time(fanspage['page_id'])
                    posted_count += 1
                    fanspage_offset += 1  # Increment for next fanspage
                else:
                    print(f"   ❌ Failed: {error}")
                    self.log_post(fanspage, content, image_path, None, 'failed', error)
                
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
                        print(f"⏳ Waiting {self.fanspage_delay_minutes} minutes before next fanspage to avoid spam detection...")
                        print(f"   Next post at: {(datetime.now() + timedelta(seconds=delay_seconds)).strftime('%H:%M:%S')}\n")
                        time.sleep(delay_seconds)
                
            except Exception as e:
                error_msg = str(e)
                print(f"   ❌ Error: {error_msg}\n")
                self.log_post(fanspage, "", "", None, 'error', error_msg)
        
        # Update state once at the end of cycle
        if posted_count > 0:
            next_index = (base_topic_index + posted_count) % len(self.goldgen.topics)
            self.goldgen.state_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.goldgen.state_file, 'w') as f:
                json.dump({'current_topic_index': next_index, 'last_updated': datetime.now().isoformat()}, f)
            print(f"📊 Posted to {posted_count} fanspage(s) with different topics")
            print(f"   Next cycle will start from topic index: {next_index}\n")
        
        print(f"[{datetime.now()}] Process completed.\n")
    
    def process_queue(self):
        """Process queued posts from web app"""
        print("\n🔄 Checking post queue from web app...")
        
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            # Get pending posts
            cursor.execute('''
                SELECT id, page_id, caption, image_path
                FROM post_queue
                WHERE status = 'pending'
                ORDER BY created_at ASC
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
