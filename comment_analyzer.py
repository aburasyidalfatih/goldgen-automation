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
from core.database import get_db_connection
from core.config import CONFIG_PATH
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
        conn = get_db_connection()
        cursor = conn.cursor()
        # Tabel insight dari analisis komentar
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS comment_insights (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                analyzed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                page_id TEXT,
                page_name TEXT,
                total_comments_analyzed INTEGER,
                top_keywords TEXT,       -- JSON array of keywords
                requested_topics TEXT,   -- JSON array of topics audience minta
                sentiment TEXT,          -- positive/neutral/negative
                suggested_topics TEXT,   -- JSON array of topic suggestions for next content
                raw_analysis TEXT        -- Full Gemini response
            )
        ''')
        # Kolom di topic_preferences untuk boost topic tertentu
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS topic_preferences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                page_id TEXT,
                topic_keyword TEXT NOT NULL,
                boost_score INTEGER DEFAULT 1,  -- makin tinggi makin diprioritaskan
                source TEXT DEFAULT 'comment_analysis',
                last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        conn.close()

    def get_recent_comments(self, page_id, access_token, days=3):
        """Ambil semua komentar dari post 3 hari terakhir"""
        url = f"https://graph.facebook.com/v18.0/{page_id}/posts"
        params = {
            'access_token': access_token,
            'fields': 'id,message,created_time',
            'limit': 20
        }
        try:
            response = requests.get(url, params=params, timeout=30)
            posts = response.json().get('data', [])
        except Exception as e:
            print(f"❌ Error getting posts: {e}")
            return []

        cutoff = datetime.now() - timedelta(days=days)
        all_comments = []

        for post in posts:
            try:
                post_time = datetime.strptime(post['created_time'], '%Y-%m-%dT%H:%M:%S+0000')
                if post_time < cutoff:
                    continue
            except Exception:
                pass

            # Get hook_type from DB
            hook_type = "Unknown"
            try:
                conn = get_db_connection()
                db_post = conn.execute("SELECT hook_type FROM posts WHERE fb_post_id = ?", (post['id'],)).fetchone()
                if db_post and db_post['hook_type']:
                    hook_type = db_post['hook_type']
                conn.close()
            except Exception:
                pass

            # Get comments
            comments_url = f"https://graph.facebook.com/v18.0/{post['id']}/comments"
            try:
                r = requests.get(comments_url, params={
                    'access_token': access_token,
                    'fields': 'id,message,from',
                    'limit': 50
                }, timeout=30)
                comments = r.json().get('data', [])
                # Filter out page's own comments
                filtered = [c for c in comments if c.get('from', {}).get('id') != page_id]
                all_comments.extend([f"[HOOK: {hook_type}] {c['message']}" for c in filtered if c.get('message')])
            except Exception:
                continue

        return all_comments

    def get_most_engaged_image(self, page_id, access_token, days=3):
        """Find the local image path of the most commented post in the last N days"""
        url = f"https://graph.facebook.com/v18.0/{page_id}/posts"
        try:
            r = requests.get(url, params={'access_token': access_token, 'fields': 'id,created_time', 'limit': 20}, timeout=30)
            posts = r.json().get('data', [])
        except Exception:
            return None
            
        cutoff = datetime.now() - timedelta(days=days)
        best_post_id = None
        max_comments = -1
        
        for post in posts:
            try:
                if datetime.strptime(post['created_time'], '%Y-%m-%dT%H:%M:%S+0000') < cutoff:
                    continue
                r_com = requests.get(f"https://graph.facebook.com/v18.0/{post['id']}/comments?summary=1&access_token={access_token}", timeout=30)
                count = r_com.json().get('summary', {}).get('total_count', 0)
                if count > max_comments:
                    max_comments = count
                    best_post_id = post['id']
            except:
                pass
                
        if best_post_id:
            try:
                conn = get_db_connection()
                db_post = conn.execute("SELECT image_path FROM posts WHERE fb_post_id = ?", (best_post_id,)).fetchone()
                conn.close()
                if db_post and db_post['image_path']:
                    return db_post['image_path']
            except:
                pass
        return None

    def analyze_vision_styles(self, image_path):
        """Use Gemini Vision to extract winning visual aesthetics from the top image"""
        import base64
        import os
        import re
        if not image_path or not os.path.exists(image_path):
            return []
            
        try:
            with open(image_path, "rb") as f:
                encoded_image = base64.b64encode(f.read()).decode("utf-8")
                
            prompt = "Analyze this top-performing gold prospecting image. What specific visual aesthetics make it highly engaging to an American audience? (e.g. muddy hands, extreme macro shot, sun glare, rugged realism). Reply ONLY with a JSON array of strings representing the 3-5 best visual keywords. Example: [\"macro photography\", \"muddy realism\"]"
            
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={self.gemini_api_key}"
            payload = {
                "contents": [{
                    "parts": [
                        {"text": prompt},
                        {"inlineData": {"mimeType": "image/png", "data": encoded_image}}
                    ]
                }]
            }
            response = requests.post(url, json=payload, timeout=30)
            text = response.json()['candidates'][0]['content']['parts'][0]['text']
            match = re.search(r'\[.*\]', text, re.DOTALL)
            if match:
                return json.loads(match.group(0))
        except Exception as e:
            print(f"❌ Vision AI Error: {e}")
        return []

    def analyze_with_gemini(self, comments, page_name):
        """Kirim komentar ke Gemini untuk dianalisis"""
        if not comments:
            return None

        # Sanitize: hapus karakter yang bisa merusak JSON output Gemini
        clean_comments = []
        for c in comments[:100]:
            c = c.replace('"', "'").replace('\\', '').replace('\n', ' ').strip()
            if c:
                clean_comments.append(c)

        comments_text = '\n'.join([f"- {c}" for c in clean_comments])

        prompt = f"""Analyze these Facebook comments from a gold prospecting page "{page_name}".
Some comments have a prefix like [HOOK: Fear] which indicates the psychological hook used in the post that generated this comment.
Comments:
{comments_text}

Extract any preferred visual/image styles mentioned by the audience. Also suggest improvements for the AI prompt (for text or image generation) based on their complaints, questions, or engagement.
Evaluate which HOOK generated the most engagement or best quality comments. Add the best performing hook to 'suggested_topics' as a meta-topic (e.g. "Hook: Fear").

REPLY ONLY WITH THIS EXACT JSON FORMAT:
{{
    "top_keywords": ["keyword1", "keyword2"],
    "requested_topics": ["topic audience wants to learn"],
    "sentiment": "positive/neutral/negative",
    "suggested_topics": [
        {{"topic": "Hook: Secret", "reason": "Generated high curiosity"}}
    ],
    "avoid_patterns": ["complaints or boring things"],
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
            print(f"❌ Gemini analysis error: {e}")
            return None

    def save_insight(self, page_id, page_name, total_comments, analysis):
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

        # Update topic_preferences berdasarkan suggested topics
        for item in analysis.get('suggested_topics', []):
            topic_kw = item.get('topic', '').lower()
            if topic_kw:
                # Cek apakah sudah ada, kalau ada boost score-nya
                existing = cursor.execute(
                    'SELECT id, boost_score FROM topic_preferences WHERE topic_keyword = ? AND page_id = ?', (topic_kw, page_id)
                ).fetchone()
                if existing:
                    cursor.execute(
                        'UPDATE topic_preferences SET boost_score = boost_score + 1, last_updated = CURRENT_TIMESTAMP WHERE id = ?',
                        (existing[0],)
                    )
                else:
                    cursor.execute(
                        'INSERT INTO topic_preferences (page_id, topic_keyword, boost_score) VALUES (?, ?, 1)',
                        (page_id, topic_kw)
                    )

        conn.commit()
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
        cols = ['id', 'analyzed_at', 'page_id', 'page_name', 'total_comments_analyzed',
                'top_keywords', 'requested_topics', 'sentiment', 'suggested_topics', 'raw_analysis']
        return dict(zip(cols, row))

    def run(self):
        """Main: analisis komentar semua page"""
        print("=" * 60)
        print("🔍 COMMENT ANALYZER - GOLDGEN")
        print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)

        for page in self.fanspages:
            page_name = page['name']
            page_id = page['page_id']
            access_token = page['access_token']

            print(f"\n📘 Analyzing: {page_name}")
            comments = self.get_recent_comments(page_id, access_token, days=3)
            print(f"   💬 {len(comments)} comments collected")

            if len(comments) < 3:
                print("   ⚠️  Not enough comments to analyze, skipping")
                continue

            analysis = self.analyze_with_gemini(comments, page_name)
            if not analysis:
                print("   ❌ Analysis failed")
                continue

            self.save_insight(page_id, page_name, len(comments), analysis)

            print(f"   ✅ Insight saved")
            print(f"   📊 Sentiment: {analysis.get('sentiment')}")
            print(f"   🔑 Top keywords: {', '.join(analysis.get('top_keywords', [])[:3])}")
            print(f"   💡 Suggested topics: {len(analysis.get('suggested_topics', []))}")

        # Tampilkan top preferences
        prefs = self.get_top_preferences(5)
        if prefs:
            print(f"\n🎯 TOP AUDIENCE PREFERENCES:")
            for p in prefs:
                print(f"   [{p['score']}x] {p['keyword']}")

        print("\n✅ Analysis complete!")


if __name__ == '__main__':
    analyzer = CommentAnalyzer()
    analyzer.run()
