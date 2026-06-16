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


class CommentAnalyzer:
    def __init__(self, config_path='data/config.json'):
        with open(config_path, 'r') as f:
            self.config = json.load(f)

        self.gemini_api_key = self.config['gemini_api_key']
        self.text_model = self.config.get('text_model', 'gemini-2.5-flash')
        self.fanspages = [fp for fp in self.config.get('fanspages', []) if fp.get('enabled', True)]
        self.db_path = 'data/posts.db'
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
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
                topic_keyword TEXT NOT NULL,
                boost_score INTEGER DEFAULT 1,  -- makin tinggi makin diprioritaskan
                source TEXT DEFAULT 'comment_analysis',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
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
                all_comments.extend([c['message'] for c in filtered if c.get('message')])
            except Exception:
                continue

        return all_comments

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
Comments:
{comments_text}

Reply ONLY with this JSON (no markdown, keep all strings simple ASCII):
{{"top_keywords":["kw1","kw2","kw3","kw4","kw5"],"requested_topics":["topic1","topic2","topic3"],"sentiment":"positive","sentiment_reason":"brief reason","suggested_topics":[{{"topic":"topic1","reason":"reason1"}},{{"topic":"topic2","reason":"reason2"}},{{"topic":"topic3","reason":"reason3"}},{{"topic":"topic4","reason":"reason4"}},{{"topic":"topic5","reason":"reason5"}}]}}"""

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
        conn = sqlite3.connect(self.db_path)
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
                    'SELECT id, boost_score FROM topic_preferences WHERE topic_keyword = ?', (topic_kw,)
                ).fetchone()
                if existing:
                    cursor.execute(
                        'UPDATE topic_preferences SET boost_score = boost_score + 1 WHERE id = ?',
                        (existing[0],)
                    )
                else:
                    cursor.execute(
                        'INSERT INTO topic_preferences (topic_keyword, boost_score) VALUES (?, 1)',
                        (topic_kw,)
                    )

        conn.commit()
        conn.close()

    def get_top_preferences(self, limit=10):
        """Ambil topik dengan boost score tertinggi untuk dipakai di content generation"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        rows = cursor.execute(
            'SELECT topic_keyword, boost_score FROM topic_preferences ORDER BY boost_score DESC LIMIT ?',
            (limit,)
        ).fetchall()
        conn.close()
        return [{'keyword': r[0], 'score': r[1]} for r in rows]

    def get_latest_insight(self):
        """Ambil insight terbaru untuk ditampilkan di dashboard"""
        conn = sqlite3.connect(self.db_path)
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
