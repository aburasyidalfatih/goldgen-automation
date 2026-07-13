#!/usr/bin/env python3
"""
Auto Reply Comments - Goldgen Automation
Membalas setiap komentar di Facebook Page menggunakan Gemini AI
"""

import json
import requests
import time
import sqlite3
import base64
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
            'fields': 'id,from,message,created_time,attachment',
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

    def get_user_history(self, user_name):
        """Fetch the last 3 conversational interactions with this user to build social memory context"""
        conn = get_db_connection()
        cursor = conn.cursor()
        # Ensure we don't fetch "[PROCESSING...]" or "[HIDDEN SPAM]"
        cursor.execute('''
            SELECT comment_text, reply_text 
            FROM replied_comments 
            WHERE user_name = ? AND reply_text NOT IN ('[PROCESSING...]', '[HIDDEN SPAM]')
            ORDER BY timestamp DESC LIMIT 3
        ''', (user_name,))
        history = cursor.fetchall()
        conn.close()
        return [{'comment': r[0], 'reply': r[1]} for r in history]

    def get_latest_insights(self, page_id):
        """Get the latest audience ML insights for this page"""
        try:
            conn = get_db_connection()
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                'SELECT raw_analysis FROM comment_insights WHERE page_id = ? ORDER BY analyzed_at DESC LIMIT 1', (page_id,)
            ).fetchone()
            conn.close()
            if row and row['raw_analysis']:
                return json.loads(row['raw_analysis'])
            return {}
        except Exception:
            return {}

    def _download_image_as_base64(self, url):
        """Download image from url and convert to base64 for Gemini Vision"""
        try:
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            return base64.b64encode(response.content).decode('utf-8')
        except Exception as e:
            print(f"   ❌ Failed to download attachment image: {e}")
            return None
    
    def generate_reply(self, comment_text, post_context="", user_name="User", past_interactions=None, ml_insights=None, image_b64=None):
        """Generate reply using Gemini AI with language detection and ML context"""
        
        # Inject ML context if available
        ml_context = ""
        if ml_insights and 'suggested_topics' in ml_insights:
            topics = [t.get('topic', '') for t in ml_insights['suggested_topics']]
            ml_context = f"\nML AUDIENCE INSIGHTS: The audience on this page is currently interested in: {', '.join(topics)}. If the user asks a question related to these, provide helpful information based on these insights."
            
        # Inject Memory context
        memory_context = ""
        if past_interactions and len(past_interactions) > 0:
            history_text = "\n".join([f"- User said: '{p['comment']}' | You replied: '{p['reply']}'" for p in past_interactions])
            memory_context = f"""
USER HISTORY: You have interacted with {user_name} before ({len(past_interactions)} prior interactions). 
Here is the transcript of your past conversations with them:
{history_text}
CRITICAL MEMORY INSTRUCTION: Acknowledge them warmly like a returning friend (e.g. 'Good to see you again!', 'Welcome back, John!'). If their current comment relates to their past comments, YOU MUST reference the past context to show you remember them. This builds immense loyalty!"""
            
        prompt = f"""You are a highly experienced veteran gold prospector. You run an educational gold prospecting page.
You are NOT selling anything, but you love helping people and sharing your knowledge about panning, sluicing, crevicing, and finding paydirt.

POST CONTEXT: {post_context if post_context else "Educational gold prospecting content"}
{ml_context}
{memory_context}

COMMENT FROM {user_name}: "{comment_text}"

CRITICAL INSTRUCTIONS:
1. MIRROR THE USER'S LANGUAGE: You MUST reply in the exact same language the user used in their comment. (e.g., if they comment in Indonesian, reply in Indonesian. If they comment in Turkish, reply in Turkish).
2. RETAIN YOUR PERSONA: Even when translating, keep the rugged, friendly, and expert prospector tone. Use appropriate local idioms if possible, but keep the core message educational.
3. If speaking English, use Imperial units ONLY (oz, inches, feet, yards). 
4. DO NOT mention buying gold bars or financial investments. We are PROSPECTORS, we dig for gold! If they ask about buying mining equipment (and ML insights support it), be helpful but clarify you don't sell them directly.
5. KEEP IT EXTREMELY SHORT: Facebook comments must be punchy. Your reply MUST NOT exceed 2 or 3 short sentences. Never write long paragraphs.
6. HANDLE JOKES & EMOJIS: If the user just posts an emoji (like 🤨, 😂, 👍) or makes a joke, lean into it! Reply with a witty, playful prospector joke or banter. Don't be stiff.
7. End with a friendly question to keep the discussion going."""

        if image_b64:
            prompt += "\n\nCRITICAL VISION INSTRUCTION: The user has attached a photo to their comment. Look at the photo carefully. Give expert geological insight based on what you see. If they ask if it's real gold, tell them! If it looks like Pyrite (Fool's Gold) because of sharp, cubic edges, explain it to them gently. Act like a true veteran prospector analyzing their find!"

        prompt += """

EXAMPLES OF GOOD REPLIES:

Comment (English): "Is that real gold?"
Reply: "You bet! That's what a solid picker looks like when it comes out of the sluice box. Have you ever seen raw gold in the pan?"

Comment (Indonesian): "Berapa harga alat ini bang?"
Reply: "Wah, semangat sekali! Saya tidak menjual alatnya secara langsung, tapi alat dulang seperti ini biasanya bisa dicari di toko peralatan tambang atau online. Sudah pernah mencoba mendulang di sungai terdekat?"

Comment (Turkish): "Bu altınları nerede bulabilirim?"
Reply: "Harika bir soru! Genellikle ana kayadaki çatlaklarda ve nehirlerin iç kıvrımlarında aramanız gerekir. Şu an hangi bölgede arama yapıyorsunuz?"

Just provide the direct reply without any quotes or explanations."""

        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.text_model}:generateContent?key={self.gemini_api_key}"
            
            parts = [{"text": prompt}]
            if image_b64:
                parts.append({
                    "inlineData": {
                        "mimeType": "image/jpeg",
                        "data": image_b64
                    }
                })

            payload = {
                "contents": [{
                    "parts": parts
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
            if any(char in comment_text.lower() for char in ['what', 'how', 'where']):
                return "That's a great question! There's always more to learn when you're out digging in the dirt. Are you panning in rivers or dry washing?"
            else:
                return "Appreciate you dropping by! Keep your pan wet and your eyes open for that yellow metal!"
    
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
            INSERT OR REPLACE INTO replied_comments (comment_id, post_id, user_name, comment_text, reply_text)
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

    def hide_comment(self, comment_id, access_token):
        """Hide a malicious comment using Facebook Graph API"""
        url = f"https://graph.facebook.com/v18.0/{comment_id}"
        params = {
            'access_token': access_token,
            'is_hidden': 'true'
        }
        try:
            response = requests.post(url, data=params, timeout=30)
            return response.status_code == 200
        except Exception:
            return False

    def check_spam(self, comment_text):
        """Use Gemini to detect if a comment is spam, scam, crypto bot, or hate speech."""
        prompt = f"""Analyze the following Facebook comment. Is it spam, a scam, phishing link, crypto promotion, or hate speech?
Respond ONLY with this exact JSON format: {{"is_spam": true/false}}

COMMENT: "{comment_text}"
"""
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.text_model}:generateContent?key={self.gemini_api_key}"
            payload = {"contents": [{"parts": [{"text": prompt}]}]}
            response = requests.post(url, json=payload, timeout=30)
            text = response.json()['candidates'][0]['content']['parts'][0]['text']
            import re
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                res = json.loads(match.group(0))
                return res.get('is_spam', False)
            return False
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
                    
                    image_b64 = None
                    attachment = comment.get('attachment')
                    if attachment and attachment.get('type') == 'photo':
                        img_url = attachment.get('media', {}).get('image', {}).get('src')
                        if img_url:
                            print(f"   📸 User attached an image. Downloading for Vision AI...")
                            image_b64 = self._download_image_as_base64(img_url)
                    
                    # Skip if already replied
                    if self.is_already_replied(comment_id):
                        continue
                    
                    print(f"\n   👤 {user_name}: {comment_text[:50]}...")
                    
                    # Pre-lock the comment to prevent concurrent overlapping crons from replying to the same comment
                    self.save_replied_comment(
                        comment_id, post_id, user_name, 
                        comment_text, "[PROCESSING...]"
                    )
                    
                    # Bouncer AI: Check for spam
                    print(f"   🛡️ Checking for spam...")
                    is_spam = self.check_spam(comment_text)
                    if is_spam:
                        print(f"   🚨 SPAM DETECTED! Hiding comment from public...")
                        if self.hide_comment(comment_id, access_token):
                            print(f"   ✅ Comment hidden successfully.")
                            self.save_replied_comment(comment_id, post_id, user_name, comment_text, "[HIDDEN SPAM]")
                        else:
                            print(f"   ❌ Failed to hide comment.")
                        continue
                    
                    # Fetch ML Insights for this page
                    ml_insights = self.get_latest_insights(page_id)
                    
                    # Fetch User History
                    past_interactions = self.get_user_history(user_name)
                    
                    # Generate reply
                    reply_text = self.generate_reply(
                        comment_text=comment_text, 
                        post_context=post_message,
                        user_name=user_name,
                        past_interactions=past_interactions,
                        ml_insights=ml_insights,
                        image_b64=image_b64
                    )
                    print(f"   🤖 Reply: {reply_text[:50]}...")
                    
                    # Post reply
                    if self.post_reply(comment_id, reply_text, access_token):
                        print(f"   ✅ Replied successfully!")
                        
                        # Save actual reply to database
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

if __name__ == "__main__":
    import sys
    try:
        import fcntl
        lock_file = open('data/replier.lock', 'w')
        try:
            fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except IOError:
            print("⏳ Another auto_reply_comments instance is running. Exiting.")
            sys.exit(0)
    except ImportError:
        import msvcrt
        lock_file = open('data/replier.lock', 'w')
        try:
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
        except IOError:
            print("⏳ Another auto_reply_comments instance is running. Exiting.")
            sys.exit(0)

    replier = CommentReplier()
    replier.process_comments()
