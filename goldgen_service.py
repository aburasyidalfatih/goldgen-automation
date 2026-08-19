#!/usr/bin/env python3
"""
GoldGen Service - Generate educational content about gold prospecting
"""

from google import genai
import os
import json
import random
from pathlib import Path
from datetime import datetime

class GoldGenService:
    def __init__(self, api_key, model='gemini-3.5-flash'):
        self.client = genai.Client(api_key=api_key)
        self.model = model
        
        # Topic rotation state
        self.state_file = Path(__file__).parent / "data" / "topic_state.json"
        
        # Load layouts and topics from external JSON
        try:
            with open(Path(__file__).parent / 'data' / 'layouts.json', 'r', encoding='utf-8') as f:
                self.layouts = json.load(f)
            with open(Path(__file__).parent / 'data' / 'topics.json', 'r', encoding='utf-8') as f:
                self.topics = json.load(f)
        except Exception as e:
            print(f'Warning: Could not load layouts or topics. Fallback to empty lists. Error: {e}')
            self.layouts = []
            self.topics = []

    def _get_audience_preferences(self, page_id=None, limit=10):
        """Ambil top topic preferences dari analisis komentar.

        Diambil lebih banyak dari yang dibutuhkan lalu disaring, supaya
        preferensi sampah warisan lama (skornya terlanjur tinggi) tidak
        menghabiskan jatah slot preferensi yang benar-benar berguna.
        """
        try:
            from core.database import get_db_connection
            conn = get_db_connection()
            fetch = limit * 4
            if page_id:
                rows = conn.execute(
                    'SELECT topic_keyword, boost_score FROM topic_preferences WHERE page_id = ? ORDER BY boost_score DESC LIMIT ?', (page_id, fetch)
                ).fetchall()
            else:
                rows = conn.execute(
                    'SELECT topic_keyword, boost_score FROM topic_preferences ORDER BY boost_score DESC LIMIT ?', (fetch,)
                ).fetchall()
            conn.close()

            # Buang preferensi sampah warisan lama ("hook: unknown", dsb) agar
            # tidak ikut menentukan pemilihan topik maupun gaya hook
            from comment_analyzer import _is_meaningful, normalize_hook
            result = []
            for r in rows:
                kw = r[0]
                if not _is_meaningful(kw):
                    continue
                if kw.startswith('hook:') and not normalize_hook(kw):
                    continue
                result.append(kw)
            return result[:limit]
        except Exception:
            return []

    def _get_latest_insights(self, page_id=None):
        """Ambil insight terdalam terbaru dari analisis komentar"""
        try:
            from core.database import get_db_connection
            conn = get_db_connection()
            if page_id:
                row = conn.execute(
                    'SELECT raw_analysis FROM comment_insights WHERE page_id = ? ORDER BY analyzed_at DESC LIMIT 1', (page_id,)
                ).fetchone()
            else:
                row = conn.execute(
                    'SELECT raw_analysis FROM comment_insights ORDER BY analyzed_at DESC LIMIT 1'
                ).fetchone()
            conn.close()
            if row and row['raw_analysis']:
                return json.loads(row['raw_analysis'])
            return {}
        except Exception:
            return {}

    def _get_layout_performance(self, page_id):
        """Rata-rata engagement tiap layout untuk SATU page.

        Sumber data: tabel posts (layout_name) di-join dengan engagement_cache
        yang diisi oleh comment_analyzer setiap siklus riset.
        Return: {layout_name: {'avg': float, 'n': int}}
        """
        if not page_id:
            return {}
        try:
            from core.database import get_db_connection
            conn = get_db_connection()
            rows = conn.execute('''
                SELECT p.layout_name AS layout,
                       AVG(ec.likes + ec.comments) AS avg_eng,
                       COUNT(*) AS n
                FROM posts p
                JOIN engagement_cache ec ON ec.fb_post_id = p.fb_post_id
                WHERE p.page_id = ?
                  AND p.status = 'success'
                  AND p.layout_name IS NOT NULL
                  AND p.layout_name != ''
                GROUP BY p.layout_name
            ''', (page_id,)).fetchall()
            conn.close()
            return {r['layout']: {'avg': r['avg_eng'] or 0.0, 'n': r['n']} for r in rows}
        except Exception as e:
            print(f"   ⚠️ Gagal membaca performa layout: {e}")
            return {}

    def _choose_layout(self, page_id, fallback_index):
        """Pilih layout berdasarkan performa nyata di page ini.

        Sebelumnya layout ditentukan `index_topik % 16` — murni rotasi, tidak
        pernah melihat layout mana yang benar-benar disukai audiens, padahal
        datanya sudah dikumpulkan.

        Strategi (bandit sederhana):
        1. Layout yang belum pernah dicoba diprioritaskan (kumpulkan data dulu).
        2. 20% eksplorasi acak — supaya tidak terkunci di satu gaya dan
           audiens tidak bosan.
        3. Sisanya: undian berbobot berdasarkan rata-rata engagement, jadi
           layout terbaik paling sering muncul tanpa mematikan yang lain.
        """
        if not self.layouts:
            return None, 'no-layout'

        perf = self._get_layout_performance(page_id)
        MIN_SAMPLE = 2  # di bawah ini belum bisa disebut bukti

        proven = {name: d for name, d in perf.items() if d['n'] >= MIN_SAMPLE and d['avg'] > 0}

        # 1. Utamakan layout yang belum punya data — eksplorasi terarah
        untried = [l for l in self.layouts if l['name'] not in perf]
        if untried and random.random() < 0.35:
            layout = random.choice(untried)
            return layout, f"belum pernah dicoba di page ini"

        if not proven:
            # Belum ada bukti sama sekali -> rotasi lama (perilaku aman)
            return self.layouts[fallback_index % len(self.layouts)], "rotasi (data belum cukup)"

        # 2. Slot eksplorasi
        if random.random() < 0.20:
            layout = random.choice(self.layouts)
            return layout, "eksplorasi acak"

        # 3. Undian berbobot berdasarkan performa
        candidates = [l for l in self.layouts if l['name'] in proven]
        weights = [proven[l['name']]['avg'] for l in candidates]
        if not candidates or sum(weights) <= 0:
            return self.layouts[fallback_index % len(self.layouts)], "rotasi (bobot kosong)"

        layout = random.choices(candidates, weights=weights, k=1)[0]
        d = proven[layout['name']]
        return layout, f"pemenang: rata-rata {d['avg']:.1f} engagement dari {d['n']} post"

    def _get_live_gold_price(self):
        """Fetch real-time gold price via yfinance API"""
        try:
            import yfinance as yf
            gold = yf.Ticker("GC=F")
            current_price = gold.info.get('regularMarketPrice') or gold.fast_info.get('last_price')
            if current_price:
                return f"${current_price:.2f}/oz"
        except Exception as e:
            print(f"Warning: Could not fetch live gold price: {e}")
        return None

    def _editor_review(self, caption):
        """AI Editor to review scroll-stopping power and extract hook type"""
        try:
            editor_prompt = f"""You are a cynical, highly-experienced American Facebook Marketing Editor for a gold prospecting page based in the US.
Review this drafted caption. 
1. Does the first line grab attention? Is it engaging? 
2. Does it sound like a rugged American veteran? (It MUST use Imperial units like oz/inches/feet, NOT metric).
Assign a SCORE from 1 to 10 for "Scroll-Stopping Power". If it uses metric units, automatically deduct 5 points.
Also identify the HOOK_TYPE used (e.g., Fear, Secret, Mythbuster, Challenge, Story, Fact).

DRAFT CAPTION:
{caption}

REPLY ONLY WITH THIS EXACT JSON FORMAT:
{{"score": 8, "feedback": "Needs a stronger opening line. Too academic.", "hook_type": "Fact"}}
"""
            response = self.client.models.generate_content(
                model=self.model,
                contents=editor_prompt
            )
            import json
            import re
            json_str = response.text
            match = re.search(r'\{.*\}', json_str, re.DOTALL)
            if match:
                return json.loads(match.group(0))
            return {"score": 10, "feedback": "Valid", "hook_type": "Unknown"}
        except Exception as e:
            print(f"Editor review failed: {e}")
            return {"score": 10, "feedback": "Valid", "hook_type": "Unknown"}

    def _tokenize(self, text):
        """Tokenisasi + stemming sederhana untuk similarity matching"""
        import re
        # Stopwords yang tidak informatif untuk matching topik
        stopwords = {'the', 'a', 'an', 'of', 'in', 'on', 'for', 'to', 'and', 'or', 'with', 'your', 'how', 'what', 'why', 'is', 'are', 'hook'}
        tokens = re.findall(r'[a-z]+', text.lower())
        result = set()
        for t in tokens:
            if t in stopwords or len(t) < 3:
                continue
            # Stemming sederhana: hapus akhiran jamak/verb umum
            for suffix in ('ing', 'ers', 'ies', 'es', 's'):
                if t.endswith(suffix) and len(t) - len(suffix) >= 3:
                    t = t[:-len(suffix)]
                    if suffix == 'ies':
                        t += 'y'
                    break
            result.add(t)
        return result

    def _topic_match_score(self, preference, topic_text):
        """
        Hitung skor kecocokan antara keyword preferensi dan teks topik.
        Menggunakan token overlap (Jaccard-like) + bonus substring frasa penuh.
        Return float 0.0 - 2.0
        """
        pref_tokens = self._tokenize(preference)
        if not pref_tokens:
            return 0.0
        topic_tokens = self._tokenize(topic_text)
        if not topic_tokens:
            return 0.0

        overlap = pref_tokens & topic_tokens
        if not overlap:
            # Fallback: substring frasa penuh (untuk frasa multi-kata persis)
            if preference.lower() in topic_text.lower():
                return 1.0
            return 0.0

        # Jaccard-like: proporsi token preferensi yang muncul di topik
        coverage = len(overlap) / len(pref_tokens)
        score = coverage
        # Bonus jika frasa lengkap juga muncul sebagai substring
        if preference.lower() in topic_text.lower():
            score += 0.5
        # Hanya anggap match jika coverage bermakna (>= 40% token preferensi)
        if coverage < 0.4:
            return 0.0
        return score

    def _get_breaking_news(self):
        """Use duckduckgo-search to find breaking news about gold prospecting in the US"""
        try:
            from duckduckgo_search import DDGS
            with DDGS() as ddgs:
                results = list(ddgs.news("gold prospecting OR gold rush OR gold nugget discovery USA", max_results=3))
                if results:
                    best_news = results[0]
                    return {
                        "headline": f"BREAKING NEWS: {best_news.get('title')}",
                        "subtitle": f"Recent report from {best_news.get('source')}: {best_news.get('body')}",
                        "list_points": [
                            "What this means for local prospectors",
                            "Where this took place and why it matters",
                            "How you can learn from this discovery"
                        ],
                        "hook_type": "News"
                    }
        except Exception as e:
            print(f"⚠️ News Espionage failed: {e}")
        return None

    def _generate_dynamic_topic(self, keyword):
        """Generates a brand new topic structure dynamically based on audience keyword"""
        try:
            print(f"   🧠 Generating new dynamic topic for keyword: {keyword}")
            prompt = f"""You are an expert gold prospecting content strategist.
The audience is highly interested in the topic/keyword: "{keyword}"
However, our current knowledge base does not have a topic specifically about this.

Your task is to create a BRAND NEW educational topic structure about this keyword.
Format the output EXACTLY as this JSON format, nothing else:
{{
    "headline": "CATCHY HEADLINE ABOUT THE TOPIC",
    "subtitle": "A punchy, informative subtitle.",
    "list_header": "KEY POINTS",
    "list_points": [
        "First specific actionable point",
        "Second specific actionable point",
        "Third specific actionable point",
        "Fourth specific actionable point"
    ]
}}
Do not include any other text, markdown blocks, or quotes. Just the raw JSON.
"""
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt
            )
            import json
            import re
            json_str = response.text
            match = re.search(r'\{.*\}', json_str, re.DOTALL)
            if match:
                new_topic = json.loads(match.group(0))
                # Generate unique ID
                new_id = max([t.get('id', 0) for t in self.topics]) + 1 if self.topics else 1
                new_topic['id'] = new_id
                return new_topic
            return None
        except Exception as e:
            print(f"⚠️ Dynamic Topic Generation failed: {e}")
            return None

    def get_next_topic(self, page_id=None):
        """Get the next topic, prioritizing breaking news if available"""
        # News Espionage: 20% chance to check for breaking news to keep it organic
        import random
        if random.random() < 0.2:
            print("   🕵️‍♂️ Running News Espionage...")
            news_topic = self._get_breaking_news()
            if news_topic:
                print(f"   🚨 Found breaking news: {news_topic['headline']}")
                # Layout tetap dipilih berdasarkan performa page, bukan acak murni
                layout, why = self._choose_layout(page_id, random.randint(0, len(self.layouts) - 1))
                if layout:
                    news_topic['layout'] = layout['name']
                    news_topic['composition'] = layout['composition']
                    print(f"   🎨 Layout: {layout['name']} ({why})")
                return news_topic

        state_file = self.state_file
        if page_id:
            state_file = self.state_file.parent / f"topic_state_{page_id}.json"

        # Fallback to normal topic rotation
        state = {}
        if state_file.exists():
            with open(state_file, 'r') as f:
                state = json.load(f)
                current_index = state.get('current_topic_index', 0)
        else:
            current_index = 0

        # Cek audience preferences dari analisis komentar
        preferences = self._get_audience_preferences(page_id)

        selected_index = current_index
        explore_mode = False
        if preferences:
            # Exploration slot: 10% kemungkinan abaikan preferensi untuk mencegah feedback loop
            if random.random() < 0.10:
                explore_mode = True
                candidates = [i for i in range(len(self.topics)) if i not in state.get('recently_used', [])[-10:]]
                if candidates:
                    selected_index = random.choice(candidates)
                    print(f"   🎲 EXPLORATION MODE: mencoba topik acak di luar preferensi audience (index {selected_index})")
                else:
                    explore_mode = False

        if preferences and not explore_mode:
            # Cari topic yang paling match dengan preferences audience (token-based similarity)
            best_matches = []
            best_score = 0.0
            for i, topic in enumerate(self.topics):
                topic_text = f"{topic['headline']} {topic['subtitle']} {' '.join(topic.get('list_points', []))}"
                # Skor tertinggi dari semua preference untuk topik ini
                score = max((self._topic_match_score(pref, topic_text) for pref in preferences), default=0.0)
                if score > best_score:
                    best_score = score
                    best_matches = [i]
                elif score == best_score and score > 0:
                    best_matches.append(i)

            # Pakai topic yang match jika score > 0 dan belum dipakai baru-baru ini
            recently_used = state.get('recently_used', [])
            valid_matches = [i for i in best_matches if i not in recently_used[-5:]]
            if valid_matches:
                selected_index = random.choice(valid_matches)
            elif preferences and len(preferences) > 0:
                # Topik sangat diinginkan tapi tidak ada yang cocok di database (best_score == 0 atau semuanya recently used)
                # Mari kita ciptakan topik baru!
                top_keyword = preferences[0]
                new_topic = self._generate_dynamic_topic(top_keyword)
                if new_topic:
                    self.topics.append(new_topic)
                    selected_index = len(self.topics) - 1
                    print(f"   🌟 Successfully generated and injected new topic: {new_topic['headline']}")
                    # Save to topics.json permanently
                    try:
                        with open(Path(__file__).parent / 'data' / 'topics.json', 'w', encoding='utf-8') as f:
                            json.dump(self.topics, f, indent=4)
                    except Exception as e:
                        print(f"   ⚠️ Failed to save new topic to topics.json: {e}")

        # Get topic
        topic = self.topics[selected_index].copy()
        if explore_mode:
            topic['explore_mode'] = True

        # Assign layout — berdasarkan performa nyata di page ini, bukan rotasi buta
        layout, why = self._choose_layout(page_id, selected_index)
        if layout:
            topic['layout'] = layout['name']
            topic['composition'] = layout['composition']
            print(f"   🎨 Layout: {layout['name']} ({why})")

        # Update state
        next_index = (current_index + 1) % len(self.topics)
        recently_used = state.get('recently_used', [])
        recently_used.append(selected_index)
        if len(recently_used) > 20:
            recently_used = recently_used[-20:]

        state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(state_file, 'w') as f:
            json.dump({
                'current_topic_index': next_index,
                'last_updated': datetime.now().isoformat(),
                'recently_used': recently_used
            }, f)

        return topic
    

    def _enforce_hashtag_limit(self, caption, max_tags=4):
        """Safety net: trim hashtags so the caption never exceeds max_tags"""
        import re
        pattern = re.compile(r'#\w+')
        matches = list(pattern.finditer(caption))
        if len(matches) <= max_tags:
            return caption
        # Remove the excess hashtags (the last ones, keeping the first max_tags)
        for m in reversed(matches[max_tags:]):
            caption = caption[:m.start()] + caption[m.end():]
        # Clean up leftover double spaces / blank lines caused by removal
        caption = re.sub(r'[ \t]{2,}', ' ', caption)
        caption = re.sub(r'\n{3,}', '\n\n', caption)
        return caption.strip()

    def generate_caption(self, topic, page_id=None):
        """Generate educational caption for gold prospecting topic"""
        
        list_text = "\n".join([f"• {point}" for point in topic['list_points']])
        
        from comment_analyzer import _is_meaningful
        insights = self._get_latest_insights(page_id)
        avoid_patterns = [p for p in (insights.get('avoid_patterns') or []) if _is_meaningful(p)]
        prompt_suggestions = [p for p in (insights.get('prompt_improvement_suggestions') or []) if _is_meaningful(p)]
        
        dynamic_avoid = ""
        if avoid_patterns:
            dynamic_avoid = "❌ AVOID THESE PATTERNS (Based on recent negative feedback):\n" + "\n".join([f"- {p}" for p in avoid_patterns]) + "\n"
            
        dynamic_suggestions = ""
        if prompt_suggestions:
            dynamic_suggestions = "✅ APPLY THESE RECENT AUDIENCE FEEDBACKS:\n" + "\n".join([f"- {p}" for p in prompt_suggestions]) + "\n"
        
        live_gold_price = self._get_live_gold_price()
        price_injection = ""
        if live_gold_price:
            price_injection = f"CURRENT LIVE GOLD PRICE: {live_gold_price}\n(If relevant to the topic, weave this live price naturally into the hook or caption to create urgency and real-time relevance.)\n"
        
        layout_name = topic.get('layout', '')
        quiz_instruction = ""
        if "QUIZ" in layout_name or "GAMIFICATION" in layout_name:
            quiz_instruction = "IMPORTANT: The image for this post is a 4-panel QUIZ (A, B, C, D). You MUST structure the caption as an interactive quiz. Ask the audience to guess which one is the real gold. DO NOT GIVE THE ANSWER IN THE CAPTION! Tell them you will reveal the answer in the comments later.\n"
        
        minigame_instruction = ""
        if "MINI-GAME" in topic['headline']:
            minigame_instruction = "IMPORTANT GAMIFICATION INSTRUCTION: This is a 'Find the Hidden Gold' mini-game! You MUST write an exciting, challenging caption. Ask the audience to spot the hidden nugget in the picture, circle it, and post their screenshot in the comments. Promise them you will personally check their answers in the comments!\n"

        # Check for winning hook in preferences.
        # Hanya hook yang dikenali sistem yang dipakai — label seperti
        # "unknown (high engagement outliers)" tidak bisa dieksekusi AI dan
        # dulu justru diperintahkan sebagai gaya hook wajib.
        from comment_analyzer import normalize_hook
        prefs = self._get_audience_preferences(page_id)
        winning_hook_instruction = ""
        winning_hooks = [h for h in (normalize_hook(p) for p in prefs if p.startswith("hook:")) if h]
        if winning_hooks:
            best_hook = winning_hooks[0].upper()
            winning_hook_instruction = f"\n🔥 CRITICAL INSTRUCTION: Based on A/B testing, the '{best_hook}' hook style performs best for this specific audience. You MUST use a '{best_hook}' style hook for this post! (e.g. if Fear, use a warning. If Secret, use insider knowledge).\n"

        base_prompt = f"""Create a VIRAL EDUCATIONAL CAPTION for a gold prospecting Facebook post.

CRITICAL TONE INSTRUCTION: You MUST write in everyday, conversational, and rugged American English. Use American slang and phrasing typical of blue-collar workers or veteran outdoorsmen (e.g., "paydirt", "bustin' your back", "you bet", "ol' timer"). Do NOT sound like an AI, a textbook, or a corporate marketer. Sound like a gritty guy sitting by a campfire in Alaska or California sharing secrets.

TOPIC: {topic['headline']}
SUBTITLE: {topic['subtitle']}

{price_injection}
{quiz_instruction}
{minigame_instruction}
{winning_hook_instruction}
KEY POINTS TO EXPLAIN:
{list_text}

=== ANTI-BOREDOM & VARIETY INSTRUCTION ===
CRITICAL: Do NOT write this in a generic, predictable way. Pick a UNIQUE angle for this specific post (e.g., A controversial take, a "secret society" tone, an urgent warning, or a deeply philosophical prospector tale). Change up the formatting. Surprise the audience so they never feel like they are reading the same template twice!

=== PROVEN VIRAL FORMULA (based on top-performing posts analysis) ===

HOOK STYLE (MUST USE ONE):
- "While beginners [do X], real veterans know [secret Y]"
- "Most people walk right past [thing] because they don't know [secret]"
- "The [number] secret(s) that separate amateur prospectors from legends"
- "Stop [common mistake]. Here's what actually works..."
- "What successful prospectors know about [topic] that nobody talks about"

CONTENT STRUCTURE:
1. HEADLINE — Bombastic, provocative, promises exclusive insider knowledge
2. Opening hook (2 sentences) — Create urgency, highlight beginner mistake vs pro knowledge
3. The Cliffhanger — Tell them the exact secret or answer is hidden INSIDE the attached image/infographic (e.g. "Check out the picture below to see exactly what to look for!"). Make them intensely curious to study the picture closely.
4. CTA — Ask about their personal field experience with this specific indicator. Examples:
   - "What's your experience with [specific indicator] in your local area?"
   - "Have you encountered [specific sign] in the field? Tag a fellow prospector who needs to see this."
5. Hashtags (STRICTLY MAXIMUM 4, mix of: #GoldProspecting #[TopicSpecific] #ProspectingTips #GoldMining #Geology #FindGold). Do NOT use more than 4 hashtags total — pick only the 4 most relevant ones.

=== WHAT MAKES POSTS GO VIRAL (apply these) ===
✅ Focus on building intense CURIOSITY so the reader stops scrolling and studies the attached image
✅ Use "Pro vs Beginner" framing — makes reader feel like they're getting insider secrets
✅ Mention specific minerals by name (Magnetite, Garnet, Arsenopyrite) to build authority
✅ Length: SHORT AND PUNCHY (300-600 characters) — Do NOT write a long essay. Just tease the immense value that is inside the picture!

=== 🇺🇸 AMERICAN AUDIENCE LOCALIZATION (MANDATORY) ===
✅ USE IMPERIAL UNITS ONLY: ounces (oz), inches, feet, yards, miles, Fahrenheit. NEVER use metric (grams, meters, celsius).
✅ USE AMERICAN SLANG & IDIOMS: "paydirt", "sniper", "crevicing", "sluice box", "claim jumper", "flour gold", "picker", "nugget", "black sand".
✅ GEOGRAPHICAL NATIVE FEEL: Casually reference iconic US gold locations when giving examples (e.g., "Out in the Mother Lode...", "In the high streams of Colorado...", "Up in Alaska..."). Sound like a native American veteran prospector.

{dynamic_suggestions}
{dynamic_avoid}
❌ AVOID: Pure academic/historical theory with no field application
❌ AVOID: Administrative topics (permits, regulations, selling)
❌ AVOID: Equipment selection guides without connecting to gold discovery
❌ AVOID: Markdown symbols (**, ##, etc) — plain text only
❌ AVOID: More than 4 hashtags — STRICT LIMIT of 4 hashtags maximum
❌ AVOID: Metric system (meters, grams) - INSTANT REJECTION.

Requirements:
- Language: American English (US spelling)
- Format: Clean plain text, no markdown
- Tone: Gritty American expert prospector sharing "expensive field knowledge" — authoritative, rugged, but accessible
"""
        
        current_prompt = base_prompt
        max_retries = 2
        final_caption = ""
        topic['hook_type'] = "Unknown"
        
        for attempt in range(max_retries + 1):
            import time
            try:
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=current_prompt
                )
                caption = response.text.strip()
                
                # Editor review
                review = self._editor_review(caption)
                print(f"   🕵️  Editor Review (Attempt {attempt+1}): Score {review.get('score')}/10 - Hook: {review.get('hook_type')}")
                topic['hook_type'] = review.get('hook_type', 'Unknown')
                
                if review.get('score', 0) >= 8 or attempt == max_retries:
                    final_caption = caption
                    break
                else:
                    print(f"   ✏️  Editor demanded rewrite: {review.get('feedback')}")
                    # Provide the rejected draft so Gemini knows what to fix
                    current_prompt = base_prompt + f"\n\n[YOUR PREVIOUS DRAFT - REJECTED]:\n{caption}\n\nEDITOR FEEDBACK: {review.get('feedback')}\n\n🔥 CRITICAL INSTRUCTION: Write a COMPLETELY NEW version that directly fixes the editor's feedback above. Do not repeat the same mistakes."
                    time.sleep(2)
            except Exception as e:
                print(f"   ⚠️  Gemini text error: {e}")
                if attempt < max_retries:
                    time.sleep(4)
                else:
                    raise

        # Safety net: enforce max 4 hashtags before returning
        final_caption = self._enforce_hashtag_limit(final_caption, max_tags=4)
        return final_caption
    
    def generate_image_prompt(self, topic, page_id=None):
        """Generate image prompt for gold prospecting infographic"""
        
        list_text = "\n".join([f"- {point}" for point in topic['list_points']])
        
        # Get layout-specific visual instructions
        layout_name = topic.get('layout', 'CROSS-SECTION CUTAWAY')
        
        # Base prompt with topic content
        base_prompt = f"""Create a VERTICAL EDUCATIONAL INFOGRAPHIC about GOLD PROSPECTING.

TOPIC: {topic['headline']}
SUBTITLE: {topic['subtitle']}

KEY INFORMATION TO VISUALIZE:
{list_text}

LAYOUT STYLE: {layout_name}
COMPOSITION GUIDE: {topic['composition']}
"""
        
        insights = self._get_latest_insights(page_id)
        # Saring nilai kosong seperti "none identified" — kalau diteruskan, string
        # itu masuk ke prompt gambar sebagai instruksi gaya dan hanya membingungkan model
        from comment_analyzer import _is_meaningful
        visual_styles = [v for v in (insights.get('preferred_visual_styles') or []) if _is_meaningful(v)]
        if visual_styles:
            base_prompt += "\nAUDIENCE PREFERRED VISUAL STYLES (Incorporate these if possible):\n"
            base_prompt += "\n".join([f"- {v}" for v in visual_styles]) + "\n\n"
        
        # Add specific visual instructions based on layout
        if "CROSS-SECTION" in layout_name:
            visual_instruction = """VISUAL EXECUTION:
Create a realistic cross-section illustration showing underground layers. Display the surface at top, then soil/gravel layers, and bedrock at bottom. Show gold deposits trapped in crevices or layers. Use natural earth tones with clear labeling lines pointing to key features. Style: Educational textbook diagram with scientific accuracy."""

        elif "CHECKLIST" in layout_name or "SPLIT" in layout_name:
            visual_instruction = """VISUAL EXECUTION:
Create a split-screen comparison image with a clear vertical divider. Left side shows one condition/type, right side shows the contrasting condition/type. Each side should be clearly labeled. Use realistic, detailed photography style suitable for a field guide. Make the differences obvious and educational."""

        elif "STEP-BY-STEP" in layout_name or "PROCESS" in layout_name:
            visual_instruction = """VISUAL EXECUTION:
Create a sequence of 3-4 distinct panels or a numbered flow showing a progression. First panel shows raw state/discovery, middle panels show the action/process, final panel shows the result/gold. Use arrows or numbers connecting the steps. Clear instructional style."""

        elif "QUIZ" in layout_name or "GAMIFICATION" in layout_name:
            visual_instruction = """VISUAL EXECUTION:
Create a 2x2 grid containing 4 distinct rock/mineral samples labeled A, B, C, and D. Make them look very similar (e.g., all shiny metallic), but only ONE is real gold (smooth, buttery yellow, non-crystalline). The others should have cubic structures (Pyrite), flaky textures (Mica), or brassy colors (Chalcopyrite). This is for an interactive Facebook quiz."""

        elif "GRID" in layout_name:
            visual_instruction = """VISUAL EXECUTION:
Create a 2x2 or 3x2 grid layout showing distinct close-up images of different indicators or examples. Each grid cell should be clearly separated with borders. Images should be macro-style, highly detailed, and realistic. Each section can have a small label. Focus on texture and detail."""

        elif "GOLDEN PATH" in layout_name or "PATH" in layout_name:
            visual_instruction = """VISUAL EXECUTION:
Create a top-down aerial view or map-style illustration. Use arrows to mark flow direction or movement patterns. Highlight specific zones or areas with golden glow, markers, or circles to indicate important locations. Style: Strategic diagram or treasure map with realistic terrain features."""

        elif "MAGNIFYING GLASS" in layout_name:
            visual_instruction = """VISUAL EXECUTION:
Create an image showing a surface with a magnifying glass overlay. Inside the lens, show a highly magnified, detailed view revealing features invisible to the naked eye. The focus should be sharp inside the lens and slightly blurred outside. Style: Scientific discovery with emphasis on detail revelation."""

        elif "BEFORE" in layout_name and "AFTER" in layout_name:
            visual_instruction = """VISUAL EXECUTION:
Create a split landscape view showing the same location in two different states. Top half labeled 'BEFORE', bottom half labeled 'AFTER'. Show clear changes between the two states. Highlight new features or changes that are significant. Style: Realistic comparative photography."""

        elif "NOTEBOOK" in layout_name or "GEOLOGIST" in layout_name:
            visual_instruction = """VISUAL EXECUTION:
Create an image that looks like a page from a field notebook. Feature highly detailed, high-contrast ink and watercolor illustrations. Use strong, bold lines and rich colors. The diagram must be extremely sharp and readable. Add authentic touches like compass, rock samples, or a pencil resting on the side. Background: Aged but clean paper. DO NOT generate blurry or faded pencil sketches. DO NOT generate walls of illegible text."""

        elif "3D" in layout_name or "BLOCK" in layout_name:
            visual_instruction = """VISUAL EXECUTION:
Create a 3D isometric block diagram showing a cutaway section of earth. Display surface features on top and underground layers in cross-section. Show how geological features connect from deep underground to the surface. Style: Clean, educational, three-dimensional technical illustration."""

        elif "TOOLKIT" in layout_name or "FLATLAY" in layout_name:
            visual_instruction = """VISUAL EXECUTION:
Create a 'knolling' style top-down flatlay image. Show various tools, mineral samples, or equipment arranged meticulously in a neat grid or logical order on a textured surface (like old wood or canvas). The composition must be perfectly aligned, aesthetic, and highly detailed. Use rich, warm lighting. Style: Premium editorial photography, highly organized."""

        elif "MAP" in layout_name or "PROSPECTOR" in layout_name:
            visual_instruction = """VISUAL EXECUTION:
Create a highly detailed, colorful topographic map illustration with strong contrast. Mark key features like rivers in vivid blue, and add bold red markers (X marks, circles) at important locations. Use clear, sharp, dark ink for contour lines. Style: Adventurous but professional treasure map with rich colors and sharp details. Avoid faint or blurry lines."""

        elif "VICTORIAN" in layout_name or "WOODCUT" in layout_name:
            visual_instruction = """VISUAL EXECUTION:
Create an image mimicking a 19th-century Victorian woodcut or engraving. Use high-contrast, dense black ink cross-hatching to form the shapes. The background should be a solid warm sepia or aged newspaper color. Style: Historical Gold Rush era, rugged, monochrome, very detailed ink work."""

        elif "INDUSTRIAL" in layout_name or "MODERN" in layout_name:
            visual_instruction = """VISUAL EXECUTION:
Create a modern, industrial, high-resolution photographic style image. Focus on scale, heavy machinery, or engineering concepts. Use industrial colors like safety orange, metallic silver, and dark grays. Style: Professional mining industry magazine cover, clean and data-driven."""

        elif "MAXIMALIST" in layout_name or "DARK" in layout_name:
            visual_instruction = """VISUAL EXECUTION:
Create a dark, moody neo-romantic image. Use a pitch-black or very dark background with ornate, classical framing. The gold or minerals should glow with brilliant metallic reflections (bronze, chrome, gold). Style: Mysterious treasure, maximalist detail, highly intricate and luxurious."""

        elif "VECTOR" in layout_name or "FLAT" in layout_name:
            visual_instruction = """VISUAL EXECUTION:
Create a clean, minimalist flat vector graphic illustration. Use bright, solid contrasting colors without dirt or grunge textures. Incorporate bold, massive sans-serif typography elements (if text is needed). Style: Modern infographic poster, highly legible, Kurzgesagt-style simplicity."""

        elif "MINI-GAME" in topic['headline']:
            visual_instruction = """VISUAL EXECUTION:
Create an insanely realistic, highly detailed wide-angle shot of a rocky riverbed, bedrock crevices, or a pile of muddy gravel. IN THE SCENE, hide ONE small, distinctly shaped shiny gold nugget. It must be slightly camouflaged but definitely visible to someone looking closely. Style: Hyper-realistic macro nature photography, sharp focus. No text!"""

        else:
            # Default fallback
            visual_instruction = """VISUAL EXECUTION:
Create a realistic educational illustration combining the topic's key visual elements. Use clear composition with labeled features. Style: National Geographic field guide with scientific accuracy and visual appeal."""

        # Combine all parts
        full_prompt = base_prompt + visual_instruction + f"""

MANDATORY REQUIREMENTS:
- Format: Vertical 9:16 aspect ratio (story/poster format)
- Background & Color: Strictly follow the VISUAL EXECUTION instructions for background color, texture, and color scheme. If no specific background is mentioned, default to a weathered vintage parchment texture with earth tones.
- Contrast: HIGH CONTRAST. Ensure all lines, diagrams, and features are sharp, bold, and clearly visible. NO FADED OR BLURRY ELEMENTS.
- Texture: Realistic rock, soil, water, and mineral textures
- Atmosphere: Educational, scientific, professional
- Quality: High detail, sharp focus on key elements, photorealistic rendering where applicable.
- NO ABSTRACT ART. NO CARTOONS. Must look like a professional reference guide.
- TEXT WARNING: DO NOT generate paragraphs of illegible text or scribbles. If text is included, it must be minimal, bold, and highly legible.
"""
        
        return full_prompt
