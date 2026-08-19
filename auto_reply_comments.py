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
import random
from datetime import datetime
from core.database import get_db_connection, init_db
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
        """Initialize database (skema tunggal ada di core/database.py)"""
        init_db()
    
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
    
    # === Human-like behavior configuration ===
    # Membuat pola balasan tidak robotik agar tidak terdeteksi sebagai bot oleh Meta
    MAX_REPLIES_PER_RUN = 7       # Batas balasan per siklus (manusia tidak membalas puluhan sekaligus)
    REPLY_DELAY_MIN = 20          # Delay minimum antar balasan (detik)
    REPLY_DELAY_MAX = 95          # Delay maksimum antar balasan (detik)
    REPLY_SKIP_PROBABILITY = 0.15 # 15% komentar non-pertanyaan sengaja dilewati (dibiarkan untuk siklus berikutnya)

    def _should_skip_comment_naturally(self, comment_text):
        """
        Simulasi perilaku manusia: tidak semua komentar dibalas.
        Pertanyaan & komentar dengan foto SELALU dibalas (engagement berkualitas).
        Sisanya, 15% dilewati secara acak agar tidak 100% response rate yang robotik.
        """
        text = comment_text.lower().strip()
        is_question = '?' in comment_text or any(
            w in text for w in ['what', 'how', 'where', 'when', 'why', 'which', 'is it', 'is that', 'can i', 'should i']
        )
        if is_question:
            return False
        return random.random() < self.REPLY_SKIP_PROBABILITY

    def _human_delay(self, first=False):
        """Delay acak ala manusia antar balasan komentar"""
        if first:
            return
        delay = random.uniform(self.REPLY_DELAY_MIN, self.REPLY_DELAY_MAX)
        print(f"   ⏳ Human-like pause: {delay:.0f}s before next reply...")
        time.sleep(delay)

    def is_already_replied(self, comment_id):
        """Check if comment already replied"""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT comment_id FROM replied_comments WHERE comment_id = ?', (comment_id,))
        result = cursor.fetchone()
        conn.close()
        return result is not None

    def get_user_history(self, user_name, user_id=None):
        """Fetch total interactions and the last 3 conversational interactions with this user to build social memory context.

        Identitas diambil dari Facebook user_id kalau tersedia (nama bisa kembar
        antar orang); nama hanya dipakai sebagai fallback untuk data lama.
        """
        conn = get_db_connection()
        cursor = conn.cursor()

        if user_id:
            where, params = 'user_id = ?', (user_id,)
        else:
            where, params = 'user_id IS NULL AND user_name = ?', (user_name,)

        # Get total count
        cursor.execute(f'''
            SELECT COUNT(*) FROM replied_comments
            WHERE {where} AND reply_text NOT IN ('[PROCESSING...]', '[HIDDEN SPAM]')
        ''', params)
        total_count = cursor.fetchone()[0]

        # Get history
        cursor.execute(f'''
            SELECT comment_text, reply_text
            FROM replied_comments
            WHERE {where} AND reply_text NOT IN ('[PROCESSING...]', '[HIDDEN SPAM]')
            ORDER BY timestamp DESC LIMIT 3
        ''', params)
        history = cursor.fetchall()
        conn.close()

        return {
            'total_count': total_count,
            'interactions': [{'comment': r[0], 'reply': r[1]} for r in history]
        }

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
    
    def generate_reply(self, comment_text, post_context="", user_name="User", user_history=None, ml_insights=None, image_b64=None):
        """Generate reply using Gemini AI with language detection and ML context"""
        
        # Inject ML context if available
        ml_context = ""
        if ml_insights and 'suggested_topics' in ml_insights:
            topics = [t.get('topic', '') for t in ml_insights['suggested_topics']]
            ml_context = f"\nML AUDIENCE INSIGHTS: The audience on this page is currently interested in: {', '.join(topics)}. If the user asks a question related to these, provide helpful information based on these insights."
            
        # Inject Memory and Gamification context
        memory_context = ""
        if user_history and user_history.get('total_count', 0) > 0:
            past_interactions = user_history.get('interactions', [])
            total_count = user_history.get('total_count', 0)
            
            # Loyalty Ranking Gamification
            rank = "Greenhorn"
            if total_count >= 10:
                rank = "Gold Baron"
            elif total_count >= 6:
                rank = "Sluice Master"
            elif total_count >= 3:
                rank = "Prospector"
                
            history_text = "\n".join([f"- User said: '{p['comment']}' | You replied: '{p['reply']}'" for p in past_interactions])
            memory_context = f"""
USER HISTORY: You have interacted with {user_name} before (Total {total_count} prior interactions). 
Based on their interactions, their official Prospector Rank is: '{rank}'. 
Here is the transcript of your recent conversations with them:
{history_text}

CRITICAL MEMORY INSTRUCTION: 
- Acknowledge them warmly like a returning friend (e.g. 'Good to see you again!'). 
- You MUST address them by their official rank '{rank}' to gamify their experience and make them feel honored!
- If their current comment relates to their past comments, YOU MUST reference the past context to show you remember them."""
            
        prompt = f"""You are a highly experienced veteran gold prospector. You run an educational gold prospecting page.
You are NOT selling anything, but you love helping people and sharing your knowledge about panning, sluicing, crevicing, and finding paydirt.

POST CONTEXT: {post_context if post_context else "Educational gold prospecting content"}
{ml_context}
{memory_context}

COMMENT FROM {user_name}: "{comment_text}"

CRITICAL INSTRUCTIONS:
1. ENGLISH ONLY: You MUST reply in rugged American English, REGARDLESS of the language the user used in their comment. If they comment in Spanish, Indonesian, or Turkish, you must reply in American English. We are targeting a strictly US audience.
2. RETAIN YOUR PERSONA: Keep the rugged, friendly, and expert prospector tone. Use American slang and phrasing typical of blue-collar workers or veteran outdoorsmen (e.g., "paydirt", "bustin' your back", "you bet", "ol' timer").
3. IMPERIAL UNITS ONLY: Always use oz, inches, feet, yards, miles. NEVER use metric.
4. MONETIZATION (SILENT AFFILIATE): DO NOT push sales aggressively. BUT, if the user EXPLICITLY asks where to buy tools, equipment, pans, or metal detectors, you MUST casually recommend a high-quality brand (like Garrett or Minelab) and append this exact affiliate link placeholder: [INSERT_AFFILIATE_LINK_HERE]. Example: 'We don't sell 'em, but veterans swear by this Garrett Pan: [INSERT_AFFILIATE_LINK_HERE].'
5. KEEP IT EXTREMELY SHORT: Facebook comments must be punchy. Your reply MUST NOT exceed 2 or 3 short sentences. Never write long paragraphs.
6. HANDLE JOKES & EMOJIS: If the user just posts an emoji (like 🤨, 😂, 👍) or makes a joke, lean into it! Reply with a witty, playful prospector joke or banter. Don't be stiff.
7. VARY YOUR ENDINGS (CRITICAL): Do NOT end every reply with a question — that is a robotic pattern. Rotate naturally between these ending styles:
   - A friendly follow-up question (only ~40% of the time)
   - A short statement of encouragement (e.g., "Keep at it, the gold is out there.")
   - A brief piece of hard-earned wisdom (e.g., "Black sand is your best friend out there.")
   - A simple acknowledgment with an emoji (e.g., "That's the spirit! ⛏️")
   - An invitation to share their own story
   Never use the same ending style twice in a row."""

        if image_b64:
            prompt += "\n\nCRITICAL VISION INSTRUCTION: The user has attached a photo to their comment. Look at the photo carefully. Give expert geological insight based on what you see. If they ask if it's real gold, tell them! If it looks like Pyrite (Fool's Gold) because of sharp, cubic edges, explain it to them gently. Act like a true veteran prospector analyzing their find!"
            prompt += "\nUGC (USER-GENERATED CONTENT) INSTRUCTION: If the photo they attached shows a GENUINE, HIGH-QUALITY gold find that looks amazing, you MUST compliment them wildly and explicitly ASK FOR PERMISSION to feature their photo on our main page. Example: 'Sweet mother of pearl! That is a monster nugget! Can we feature this beauty on our main page to inspire the others?'"

        prompt += """

EXAMPLES OF GOOD REPLIES:

Comment: "Is that real gold?"
Reply: "You bet! That's what a solid picker looks like when it comes out of the sluice box. Have you ever seen raw gold in the pan?"

Comment (Foreign Language): "Berapa harga alat ini bang?"
Reply: "Love the enthusiasm! We don't sell gear directly, but most veterans around here swear by checking local mining shops. Have you ever tried panning down at your local creek?"

Comment (Foreign Language): "Bu altınları nerede bulabilirim?"
Reply: "Great question, friend! You generally want to look in bedrock cracks and the inside bends of rivers. What kind of ground are you working right now?"

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

            # Clean up reply: buang tanda kutip pembungkus saja.
            # Apostrof di dalam kalimat WAJIB dipertahankan — slang seperti
            # "don't" / "ol' timer" adalah bagian dari persona yang diminta prompt.
            reply = reply.strip()
            for quote in ('"', '"', '"', "'"):
                if len(reply) > 1 and reply.startswith(quote) and reply.endswith(quote):
                    reply = reply[1:-1].strip()
                    break

            return reply
        except Exception as e:
            print(f"❌ Error generating reply: {e}")
            # Fallback pool - variasi agar tidak identik jika API error berulang
            question_fallbacks = [
                "That's a great question! There's always more to learn when you're out digging in the dirt. Are you panning in rivers or dry washing?",
                "Good question, friend! Every creek has its own secrets. What kind of ground are you working these days?",
                "Now that's the right question to ask! The devil is always in the details out in the field. Where are you prospecting?"
            ]
            general_fallbacks = [
                "Appreciate you dropping by! Keep your pan wet and your eyes open for that yellow metal!",
                "Love seeing folks excited about the hunt! Tight lines and heavy pans to you. ⛏️",
                "That's the spirit! The gold doesn't find itself — keep swinging!",
                "Right on! Every day in the field teaches you something new."
            ]
            if any(word in comment_text.lower() for word in ['what', 'how', 'where']):
                return random.choice(question_fallbacks)
            else:
                return random.choice(general_fallbacks)
    
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
    
    def save_replied_comment(self, comment_id, post_id, user_name, comment_text, reply_text, user_id=None):
        """Save replied comment to database"""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO replied_comments (comment_id, post_id, user_id, user_name, comment_text, reply_text)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (comment_id, post_id, user_id, user_name, comment_text, reply_text))
        conn.commit()
        conn.close()

    def remove_replied_comment(self, comment_id):
        """Remove a comment from database (e.g., if processing fails)"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM replied_comments WHERE comment_id = ?", (comment_id,))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"   ❌ Failed to remove lock for comment {comment_id}: {e}")
    
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
        # Batas acak per siklus agar tidak selalu angka bulat yang sama (lebih manusiawi)
        max_replies_this_run = random.randint(5, self.MAX_REPLIES_PER_RUN)
        print(f"🎯 Reply quota for this run: {max_replies_this_run}")
        
        # Process each fanspage
        for fanspage in self.fanspages:
            if total_replied >= max_replies_this_run:
                print(f"\n🛑 Reply quota reached ({total_replied}/{max_replies_this_run}). Remaining comments will be handled next cycle.")
                break
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
            
            # Get recent posts (30 posts to cover delayed virality)
            posts = self.get_recent_posts(page_id, access_token, limit=30)
            print(f"📊 Found {len(posts)} recent posts\n")
            
            for post in posts:
                if total_replied >= max_replies_this_run:
                    break
                post_id = post['id']
                post_message = post.get('message', '')[:100]
                
                print(f"📝 Post: {post_message}...")
                
                # Get comments (exclude page's own comments)
                comments = self.get_comments(post_id, access_token, page_id)
                print(f"   💬 {len(comments)} comments (excluding page's own)")
                
                for comment in comments:
                    if total_replied >= max_replies_this_run:
                        break
                    comment_id = comment['id']
                    commenter = comment.get('from', {}) or {}
                    user_name = commenter.get('name', 'User')
                    user_id = commenter.get('id')
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
                    
                    # Human-like skip: ~15% komentar non-pertanyaan dilewati (dicoba lagi siklus berikutnya)
                    # Komentar dengan foto tidak pernah dilewati (UGC berharga)
                    if image_b64 is None and self._should_skip_comment_naturally(comment_text):
                        print(f"   ⏭️  Skipping naturally (will retry next cycle): {comment_text[:40]}...")
                        continue
                    
                    print(f"\n   👤 {user_name}: {comment_text[:50]}...")
                    
                    # Pre-lock the comment to prevent concurrent overlapping crons from replying to the same comment
                    self.save_replied_comment(
                        comment_id, post_id, user_name,
                        comment_text, "[PROCESSING...]", user_id=user_id
                    )
                    
                    try:
                        # Bouncer AI: Check for spam
                        print(f"   🛡️ Checking for spam...")
                        is_spam = self.check_spam(comment_text)
                        if is_spam:
                            print(f"   🚨 SPAM DETECTED! Hiding comment from public...")
                            if self.hide_comment(comment_id, access_token):
                                print(f"   ✅ Comment hidden successfully.")
                                self.save_replied_comment(comment_id, post_id, user_name, comment_text, "[HIDDEN SPAM]", user_id=user_id)
                            else:
                                print(f"   ❌ Failed to hide comment.")
                            continue
                        
                        # Fetch ML Insights for this page
                        ml_insights = self.get_latest_insights(page_id)
                        
                        # Fetch User History
                        user_history_data = self.get_user_history(user_name, user_id=user_id)
                        
                        # Generate reply
                        reply_text = self.generate_reply(
                            comment_text=comment_text, 
                            post_context=post_message,
                            user_name=user_name,
                            user_history=user_history_data,
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
                                comment_text, reply_text, user_id=user_id
                            )
                            
                            total_replied += 1
                            
                            # Human-like randomized pause antar balasan (bukan delay tetap yang robotik)
                            self._human_delay()
                        else:
                            print(f"   ❌ Failed to reply. Removing lock...")
                            self.remove_replied_comment(comment_id)
                    except Exception as e:
                        print(f"   ❌ Error processing reply: {e}")
                        self.remove_replied_comment(comment_id)
                
                print()
        
        print("=" * 60)
        print(f"✅ DONE! Replied to {total_replied} comments")
        print("=" * 60)
        
        return total_replied

if __name__ == "__main__":
    import sys
    from core.locks import ProcessLock

    with ProcessLock('replier') as lock:
        if not lock.acquired:
            print("⏳ Another auto_reply_comments instance is running. Exiting.")
            sys.exit(0)

        replier = CommentReplier()
        replier.process_comments()
