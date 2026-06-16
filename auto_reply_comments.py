#!/usr/bin/env python3
"""
Auto Reply Comments - Goldgen Automation
Membalas setiap komentar di Facebook Page menggunakan Gemini AI
"""

import json
import requests
import time
import sqlite3
from datetime import datetime
from core.database import get_db_connection
from core.config import CONFIG_PATH

class CommentReplier:
    def __init__(self, config_path=CONFIG_PATH):
        with open(config_path, 'r') as f:
            self.config = json.load(f)
        
        # Gemini API key
        self.gemini_api_key = self.config['gemini_api_key']
        self.text_model = self.config.get('text_model', 'gemini-3.5-flash')
        
        # Get all fanspages
        self.fanspages = [fp for fp in self.config.get('fanspages', []) if fp.get('enabled', True)]
        
        if not self.fanspages:
            raise ValueError("No enabled fanspages found in config")
        
        # Database
        self.db_path = 'data/posts.db'
        self._init_db()
    
    def _init_db(self):
        """Initialize database for tracking replied comments"""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS replied_comments (
                comment_id TEXT PRIMARY KEY,
                post_id TEXT,
                user_name TEXT,
                comment_text TEXT,
                reply_text TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        conn.close()
    
    def get_recent_posts(self, page_id, access_token, limit=5):
        """Get recent posts from page"""
        url = f"https://graph.facebook.com/v18.0/{page_id}/posts"
        params = {
            'access_token': access_token,
            'fields': 'id,message,created_time',
            'limit': limit
        }
        
        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            return data.get('data', [])
        except Exception as e:
            print(f"❌ Error getting posts: {e}")
            return []
    
    def get_comments(self, post_id, access_token, page_id):
        """Get comments from a post"""
        url = f"https://graph.facebook.com/v18.0/{post_id}/comments"
        params = {
            'access_token': access_token,
            'fields': 'id,from,message,created_time',
            'filter': 'stream',  # Get all comments
            'limit': 100
        }
        
        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            comments = data.get('data', [])
            
            # Filter out comments from the page itself
            filtered_comments = [
                c for c in comments 
                if c.get('from', {}).get('id') != page_id
            ]
            
            return filtered_comments
        except Exception as e:
            print(f"❌ Error getting comments: {e}")
            return []
    
    def is_already_replied(self, comment_id):
        """Check if comment already replied"""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT comment_id FROM replied_comments WHERE comment_id = ?', (comment_id,))
        result = cursor.fetchone()
        conn.close()
        return result is not None
    
    def generate_reply(self, comment_text, post_context=""):
        """Generate reply using Gemini AI with language detection"""
        prompt = f"""Kamu adalah admin fanpage EDUKASI tentang emas, investasi, dan prospecting.
Tujuan fanpage: EDUKASI & DISKUSI, BUKAN JUALAN.

Seseorang berkomentar di postingan kita.

KONTEKS POST: {post_context if post_context else "Edukasi tentang emas"}

KOMENTAR: "{comment_text}"

INSTRUKSI PENTING:
1. WAJIB DETECT bahasa yang digunakan dalam komentar (English, Indonesian, Spanish, dll)
2. WAJIB BALAS dengan bahasa yang SAMA PERSIS 100% dengan komentar
3. Jika komentar English → Reply MUST be in English
4. Jika komentar Indonesian → Reply HARUS dalam Bahasa Indonesia
5. Fokus pada EDUKASI dan DISKUSI
6. JANGAN arahkan ke jualan/DM/WhatsApp
7. Ajak diskusi lebih lanjut dengan pertanyaan balik

GAYA BALASAN EDUKATIF:
- Ramah, informatif, dan engaging
- Berikan insight atau fakta menarik
- Ajak berpikir dengan pertanyaan balik
- Dorong diskusi lebih dalam
- Singkat (2-3 kalimat)
- Gunakan emoji yang sesuai (1-2 emoji)
- Natural dan conversational

CONTOH BALASAN EDUKATIF:

Komentar (ID): "Harga emas hari ini berapa?"
Reply (ID): "Harga emas fluktuatif mengikuti pasar global! 📊 Tahukah kamu faktor apa saja yang mempengaruhi harga emas? Ada 5 faktor utama lho!"

Komentar (EN): "What's the gold price today?"
Reply (EN): "Gold prices fluctuate with global markets! 📊 Do you know what factors influence gold prices? There are 5 main factors!"

Komentar (ID): "Mau beli emas batangan"
Reply (ID): "Bagus! Investasi emas batangan memang solid. 💰 Sudah tahu belum perbedaan emas 24K vs 22K? Ini penting untuk investasi jangka panjang!"

Komentar (EN): "Interested in buying gold bars"
Reply (EN): "Great choice! Gold bars are solid investments. 💰 Do you know the difference between 24K and 22K gold? It's crucial for long-term investing!"

Komentar (ID): "Bagus infonya"
Reply (ID): "Terima kasih! 🙏 Topik apa lagi tentang emas yang ingin kamu pelajari? Mining, investasi, atau sejarah emas?"

Komentar (EN): "Great info"
Reply (EN): "Thank you! 🙏 What other gold topics would you like to learn about? Mining, investing, or gold history?"

Komentar (ID): "Emas naik terus ya"
Reply (ID): "Betul! Emas cenderung naik saat ekonomi tidak stabil. 📈 Menurutmu, apakah sekarang waktu yang tepat untuk mulai investasi emas?"

Komentar (EN): "Gold keeps rising"
Reply (EN): "Indeed! Gold tends to rise during economic uncertainty. 📈 In your opinion, is now a good time to start investing in gold?"

PENTING:
- JANGAN mention DM, WhatsApp, atau kontak
- JANGAN hard selling atau soft selling
- FOKUS pada edukasi dan insight
- AJAK diskusi dengan pertanyaan balik
- Buat audience penasaran dan ingin belajar lebih
- Dorong engagement melalui diskusi

Langsung berikan balasan saja tanpa penjelasan tambahan."""

        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.text_model}:generateContent?key={self.gemini_api_key}"
            payload = {
                "contents": [{
                    "parts": [{"text": prompt}]
                }]
            }
            response = requests.post(url, json=payload, timeout=30)
            response.raise_for_status()
            data = response.json()
            reply = data['candidates'][0]['content']['parts'][0]['text'].strip()
            
            # Clean up reply
            reply = reply.replace('"', '').replace("'", "").strip()
            
            return reply
        except Exception as e:
            print(f"❌ Error generating reply: {e}")
            # Fallback reply - educational focus
            if any(char in comment_text.lower() for char in ['what', 'how', 'when', 'where', 'price', 'buy']):
                return "Great question! 🤔 Gold is fascinating - there's so much to learn about it. What aspect interests you most?"
            else:
                return "Terima kasih! 🙏 Ada pertanyaan lain tentang emas yang ingin didiskusikan?"
    
    def post_reply(self, comment_id, reply_text, access_token):
        """Post reply to a comment"""
        url = f"https://graph.facebook.com/v18.0/{comment_id}/comments"
        params = {
            'access_token': access_token,
            'message': reply_text
        }
        
        try:
            response = requests.post(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            return data.get('id') is not None
        except Exception as e:
            print(f"❌ Error posting reply: {e}")
            return False
    
    def save_replied_comment(self, comment_id, post_id, user_name, comment_text, reply_text):
        """Save replied comment to database"""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO replied_comments (comment_id, post_id, user_name, comment_text, reply_text)
            VALUES (?, ?, ?, ?, ?)
        ''', (comment_id, post_id, user_name, comment_text, reply_text))
        conn.commit()
        conn.close()
    
    def validate_token(self, page_id, access_token):
        """Validate Facebook token before processing"""
        try:
            url = f"https://graph.facebook.com/v18.0/{page_id}"
            params = {'access_token': access_token, 'fields': 'id,name'}
            response = requests.get(url, params=params, timeout=10)
            return response.status_code == 200
        except Exception:
            return False

    def process_comments(self):
        """Main process to reply comments"""
        print("=" * 60)
        print("🤖 AUTO REPLY COMMENTS - GOLDGEN")
        print("=" * 60)
        print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        total_replied = 0
        
        # Process each fanspage
        for fanspage in self.fanspages:
            page_name = fanspage['name']
            page_id = fanspage['page_id']
            access_token = fanspage['access_token']
            
            print(f"\n📘 {page_name}")
            print("=" * 60)
            
            # VALIDATE TOKEN BEFORE PROCESSING ANY POSTS
            if not self.validate_token(page_id, access_token):
                print(f"❌ Token for {page_name} is invalid or expired.")
                print("⚠️  Skipping this fanspage to save Gemini API tokens.")
                continue
            
            # Get recent posts (10 posts to balance coverage and speed)
            posts = self.get_recent_posts(page_id, access_token, limit=10)
            print(f"📊 Found {len(posts)} recent posts\n")
            
            for post in posts:
                post_id = post['id']
                post_message = post.get('message', '')[:100]
                
                print(f"📝 Post: {post_message}...")
                
                # Get comments (exclude page's own comments)
                comments = self.get_comments(post_id, access_token, page_id)
                print(f"   💬 {len(comments)} comments (excluding page's own)")
                
                for comment in comments:
                    comment_id = comment['id']
                    user_name = comment.get('from', {}).get('name', 'User')
                    comment_text = comment.get('message', '')
                    
                    # Skip if already replied
                    if self.is_already_replied(comment_id):
                        continue
                    
                    print(f"\n   👤 {user_name}: {comment_text[:50]}...")
                    
                    # Generate reply
                    reply_text = self.generate_reply(comment_text, post_message)
                    print(f"   🤖 Reply: {reply_text[:50]}...")
                    
                    # Post reply
                    if self.post_reply(comment_id, reply_text, access_token):
                        print(f"   ✅ Replied successfully!")
                        
                        # Save to database
                        self.save_replied_comment(
                            comment_id, post_id, user_name, 
                            comment_text, reply_text
                        )
                        
                        total_replied += 1
                        
                        # Rate limiting
                        time.sleep(2)
                    else:
                        print(f"   ❌ Failed to reply")
                
                print()
        
        print("=" * 60)
        print(f"✅ DONE! Replied to {total_replied} comments")
        print("=" * 60)
        
        return total_replied

def main():
    replier = CommentReplier()
    replier.process_comments()

if __name__ == '__main__':
    main()
