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
from core.safe_log import redact

# Panduan penulisan untuk tiap gaya hook.
#
# Dipakai untuk MENGGANTIKAN daftar hook generik ketika sudah diketahui gaya
# mana yang menang di sebuah page. Sebelumnya kedua hal itu tampil bersamaan di
# prompt yang sama, dan model justru mengikuti daftar generiknya — akibatnya
# instruksi "wajib pakai gaya X" praktis diabaikan dan hampir semua caption
# keluar bergaya Mythbuster, apa pun yang sudah dipelajari.
HOOK_PLAYBOOK = {
    'fear': [
        '"That [common habit] is costing you gold every single trip."',
        '"Most folks lose the best paydirt before they even start digging. Here is how."',
        '"Keep doing [mistake] and you will walk right over a fortune."',
    ],
    'secret': [
        '"While beginners [do X], real veterans know [secret Y]."',
        '"Most people walk right past [thing] because they do not know [secret]."',
        '"What old timers know about [topic] that nobody talks about."',
    ],
    'mythbuster': [
        '"Everything you were told about [topic] is dead wrong."',
        '"Stop [common practice]. Here is what actually works."',
        '"That old rule about [topic]? It has been costing people gold for years."',
    ],
    'challenge': [
        '"Can you spot the gold in this picture? Most cannot."',
        '"Bet you cannot name the one indicator in this shot."',
        '"Real prospectors will catch this in two seconds. Can you?"',
    ],
    'story': [
        '"Twenty years back I watched a fella walk away from a fortune. Here is why."',
        '"I remember the day this creek finally gave up its gold."',
        '"An old timer showed me this trick once. It changed everything."',
    ],
    'fact': [
        '"Here is the geology that decides where gold actually settles."',
        '"Gold does one thing, always: it drops the second the water slows."',
        '"The science behind [topic] explains exactly where to dig."',
    ],
    'news': [
        '"Word just came in from [place] and it changes things."',
        '"A discovery this week has prospectors rethinking [topic]."',
        '"Fresh report out of [place] worth paying attention to."',
    ],
}

# Daftar generik — hanya dipakai saat page belum punya hook pemenang
GENERIC_HOOK_STYLES = """- "While beginners [do X], real veterans know [secret Y]"
- "Most people walk right past [thing] because they don't know [secret]"
- "The [number] secret(s) that separate amateur prospectors from legends"
- "Stop [common mistake]. Here's what actually works..."
- "What successful prospectors know about [topic] that nobody talks about\""""


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

        # Layout yang sudah terbukti merugikan tidak ikut diundi lagi. Ia tetap
        # disimpan di layouts.json (bukan dihapus) supaya keputusan ini bisa
        # ditinjau ulang dan komposisi promptnya tidak hilang.
        self.active_layouts = [l for l in self.layouts if not l.get('retired')]

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

    def _get_topic_keywords(self, page_id=None, limit=10):
        """Preferensi yang benar-benar TOPIK, bukan label hook.

        `topic_preferences` mencampur dua hal yang fungsinya berbeda:
        - "hook: secret" -> gaya pembuka caption
        - "black sand indicators" -> isi konten

        Karena hook disarankan ulang hampir tiap siklus riset, skornya menumpuk
        dan mendominasi. Pemeriksaan produksi menemukan preferensi ketiga page
        100% berisi label hook — nol topik nyata. Akibatnya:
        - pencocokan topik sebenarnya membandingkan kata "fact"/"secret" saja
        - generator topik dinamis diberi kata kunci "hook: fact", sehingga
          hanya sanggup menghasilkan judul generik yang berulang

        Fungsi ini memisahkan keduanya supaya masing-masing dipakai sesuai
        perannya.
        """
        return [p for p in self._get_audience_preferences(page_id, limit=limit * 3)
                if not p.lower().startswith('hook:')][:limit]

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
        """Performa tiap layout untuk SATU page.

        Sumber data: tabel posts (layout_name) di-join dengan engagement_cache
        yang diisi oleh comment_analyzer setiap siklus riset.
        Return: {layout_name: {'avg': float, 'n': int, 'total': float}}
        """
        if not page_id:
            return {}
        try:
            from core.database import get_db_connection
            conn = get_db_connection()
            # View post_engagement hanya memuat pengukuran yang matang (>=48 jam)
            # atau snapshot umur seragam, sehingga layout yang kebetulan baru
            # dipakai tidak dihukum karena engagement-nya belum sempat tumbuh.
            rows = conn.execute('''
                SELECT layout_name AS layout,
                       SUM(engagement) AS total_eng,
                       COUNT(*) AS n
                FROM post_engagement
                WHERE page_id = ?
                  AND layout_name IS NOT NULL
                  AND layout_name != ''
                GROUP BY layout_name
            ''', (page_id,)).fetchall()
            conn.close()
            result = {}
            for r in rows:
                total = float(r['total_eng'] or 0)
                n = int(r['n'] or 0)
                if n > 0:
                    result[r['layout']] = {'avg': total / n, 'n': n, 'total': total}
            return result
        except Exception as e:
            print(f"   ⚠️ Gagal membaca performa layout: {e}")
            return {}

    def _get_page_engagement_stats(self, page_id):
        """Rata-rata & simpangan baku engagement page — dipakai sebagai prior.

        Simpangan baku penting: itulah ukuran 'seberapa berisik' engagement page
        ini, yang menentukan seberapa besar sebuah sampel kecil boleh dipercaya.
        """
        try:
            from core.database import get_db_connection
            conn = get_db_connection()
            rows = conn.execute(
                'SELECT engagement AS eng FROM post_engagement WHERE page_id = ?', (page_id,)
            ).fetchall()
            conn.close()
            values = [float(r['eng'] or 0) for r in rows]
            if not values:
                return 0.0, 0.0
            mean = sum(values) / len(values)
            if len(values) < 2:
                return mean, max(mean, 1.0)
            var = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
            return mean, var ** 0.5
        except Exception:
            return 0.0, 0.0

    def _simpan_state(self, state_file, state, current_index, selected_index):
        """Simpan rotasi & daftar topik yang baru dipakai (anti pengulangan)"""
        recently_used = state.get('recently_used', [])
        recently_used.append(selected_index)
        if len(recently_used) > 20:
            recently_used = recently_used[-20:]
        try:
            state_file.parent.mkdir(parents=True, exist_ok=True)
            with open(state_file, 'w') as f:
                json.dump({
                    'current_topic_index': (current_index + 1) % max(len(self.topics), 1),
                    'last_updated': datetime.now().isoformat(),
                    'recently_used': recently_used
                }, f)
        except Exception as e:
            print(f"   ⚠️ Gagal menyimpan state topik: {redact(e)}")

    def _get_topic_performance(self, page_id):
        """Rata-rata engagement tiap topik untuk SATU page.

        Sebelumnya topik tidak pernah disimpan per postingan, jadi bot bisa
        belajar layout dan hook tapi buta terhadap ISI kontennya — padahal
        topik justru penentu terbesar apakah audiens suka atau tidak.
        """
        if not page_id:
            return {}
        try:
            from core.database import get_db_connection
            conn = get_db_connection()
            rows = conn.execute('''
                SELECT topic_headline AS judul,
                       SUM(engagement) AS total_eng,
                       COUNT(*) AS n
                FROM post_engagement
                WHERE page_id = ? AND topic_headline IS NOT NULL AND topic_headline != ''
                GROUP BY topic_headline
            ''', (page_id,)).fetchall()
            conn.close()
            return {r['judul']: {'avg': float(r['total_eng'] or 0) / r['n'], 'n': r['n']}
                    for r in rows if r['n']}
        except Exception as e:
            print(f"   ⚠️ Gagal membaca performa topik: {redact(e)}")
            return {}

    def _choose_topic_by_performance(self, page_id, preferences, recently_used):
        """Pilih topik dengan Thompson Sampling, dipandu preferensi audiens.

        Menggabungkan dua sumber pengetahuan yang selama ini terpisah:
        - preferensi dari komentar = apa yang audiens BILANG mereka mau
          (dipakai sebagai prior, menaikkan peluang topik yang relevan)
        - engagement nyata = apa yang audiens benar-benar SUKAI
          (dipakai sebagai bukti yang memperbarui posterior)

        Return index topik, atau None kalau belum ada bukti sama sekali
        sehingga pemanggil memakai jalur lama.
        """
        perf = self._get_topic_performance(page_id)
        if not perf:
            return None

        page_mean, page_sd = self._get_page_engagement_stats(page_id)
        if page_mean <= 0:
            nilai = [d['avg'] for d in perf.values() if d['avg'] > 0]
            page_mean = (sum(nilai) / len(nilai)) if nilai else 1.0
        sigma = max(page_sd, page_mean * 0.5, 1.0)
        tau = max(sigma * 0.5, 1.0)
        prior_precision = 1.0 / (tau ** 2)
        obs_precision_unit = 1.0 / (sigma ** 2)

        hindari = set(recently_used[-5:])
        terbaik, skor_terbaik = None, float('-inf')

        for i, topic in enumerate(self.topics):
            if i in hindari:
                continue
            judul = topic.get('headline')
            d = perf.get(judul)
            n = d['n'] if d else 0
            mean = d['avg'] if d else page_mean

            # Preferensi audiens menaikkan prior — topik yang mereka minta
            # dapat kesempatan lebih besar walau belum pernah diuji
            prior = page_mean
            if preferences:
                teks = f"{judul} {topic.get('subtitle', '')}"
                if any(self._topic_match_score(p, teks) > 0 for p in preferences):
                    prior = page_mean * 1.3

            precision = prior_precision + n * obs_precision_unit
            post_mean = (prior * prior_precision + mean * n * obs_precision_unit) / precision
            sample = random.gauss(post_mean, (1.0 / precision) ** 0.5)

            if sample > skor_terbaik:
                skor_terbaik = sample
                terbaik = (i, judul, n, mean)

        if not terbaik:
            return None

        i, judul, n, mean = terbaik
        asal = f"rata-rata {mean:.0f} dari {n} post" if n else "belum pernah dipakai"
        print(f"   📚 Topik dipilih dari performa: {judul[:44]} ({asal})")
        return i

    def _choose_layout(self, page_id, fallback_index):
        """Pilih layout memakai Thompson Sampling (Gamma-Poisson).

        Kenapa bukan sekadar "pilih yang rata-ratanya tertinggi":
        rata-rata dari 1 post dan rata-rata dari 9 post bukan bukti yang setara.
        Cara lama memperlakukan keduanya sama, sehingga satu post yang kebetulan
        viral bisa membajak seluruh strategi visual sebuah page.

        Thompson Sampling menyelesaikan ini. Engagement Facebook sangat
        overdispersed (satu post bisa meledak karena algoritma, bukan karena
        layoutnya), jadi TIDAK dimodelkan Poisson — model Poisson akan menganggap
        satu post 400-engagement sebagai bukti hampir pasti dan langsung terkunci
        di situ. Yang dipakai: konjugat Normal-Normal terhadap rata-rata layout.

            prior     : N(rata-rata page, tau^2)
            observasi : n post, rata-rata x, ragam sigma^2 (kebisingan page)
            posterior : presisi dijumlahkan -> rata-rata tertarik ke prior
                        sebanding dengan sedikitnya sampel (shrinkage)

        Tiap pemilihan, kita MENGAMBIL SAMPEL dari posterior tiap layout lalu
        memilih yang tertinggi. Efeknya otomatis:
        - Sampel sedikit -> tertarik kuat ke rata-rata page + sebaran lebar,
          jadi ia ikut dicoba tapi tidak bisa membajak keputusan
        - Sampel banyak  -> posterior sempit di nilai aslinya -> layout yang
          benar-benar terbukti menang lebih sering
        - Belum pernah dicoba -> murni prior -> tetap dapat giliran wajar

        Eksplorasi muncul dari ketidakpastian itu sendiri, tidak perlu slot acak.
        """
        if not self.active_layouts:
            return None, 'no-layout'

        perf = self._get_layout_performance(page_id)
        if not perf:
            return self.active_layouts[fallback_index % len(self.active_layouts)], "rotasi (belum ada data)"

        page_mean, page_sd = self._get_page_engagement_stats(page_id)
        if page_mean <= 0:
            observed = [d['avg'] for d in perf.values() if d['avg'] > 0]
            page_mean = (sum(observed) / len(observed)) if observed else 1.0
        # Kebisingan antar-post; jangan sampai nol supaya pembagian aman
        sigma = max(page_sd, page_mean * 0.5, 1.0)
        # Sebaran prior antar layout — diasumsikan setengah dari kebisingan post.
        # Makin kecil tau, makin kuat penyusutan ke rata-rata page.
        tau = max(sigma * 0.5, 1.0)

        prior_precision = 1.0 / (tau ** 2)
        obs_precision_unit = 1.0 / (sigma ** 2)

        best_layout, best_sample, best_note = None, float('-inf'), ''
        for layout in self.active_layouts:
            d = perf.get(layout['name'])
            n = d['n'] if d else 0

            # Prior tidak selalu "rata-rata page". Bukti gabungan lintas page
            # bisa memberi tahu sebelumnya bahwa sebuah layout cenderung di bawah
            # rata-rata; prior_factor menuliskan pengetahuan itu, sehingga layout
            # tersebut harus benar-benar membuktikan diri untuk naik lagi —
            # bukan mulai dari titik netral seolah kita belum tahu apa-apa.
            prior_mean = page_mean * layout.get('prior_factor', 1.0)
            mean = d['avg'] if d else prior_mean

            precision = prior_precision + n * obs_precision_unit
            post_mean = (prior_mean * prior_precision + mean * n * obs_precision_unit) / precision
            post_sd = (1.0 / precision) ** 0.5

            sample = random.gauss(post_mean, post_sd)

            if sample > best_sample:
                best_sample = sample
                best_layout = layout
                if n == 0:
                    best_note = "belum pernah dicoba (prior)"
                else:
                    best_note = (f"rata-rata {mean:.0f} dari {n} post "
                                 f"-> perkiraan wajar {post_mean:.0f}, undian {sample:.0f}")

        if not best_layout:
            return self.active_layouts[fallback_index % len(self.active_layouts)], "rotasi (fallback)"

        return best_layout, best_note

    def _get_live_gold_price(self):
        """Fetch real-time gold price via yfinance API"""
        try:
            import yfinance as yf
            gold = yf.Ticker("GC=F")
            current_price = gold.info.get('regularMarketPrice') or gold.fast_info.get('last_price')
            if current_price:
                return f"${current_price:.2f}/oz"
        except Exception as e:
            print(f"Warning: Could not fetch live gold price: {redact(e)}")
        return None

    def _editor_review(self, caption, requested_hook=None):
        """AI Editor to review scroll-stopping power and extract hook type.

        Kalau sebuah gaya hook sudah terbukti menang di page ini, editor ikut
        menegakkannya. Tanpa penegakan, instruksi 'wajib pakai gaya X' hanya
        jadi saran yang diabaikan model, dan sisi eksploitasi dari pembelajaran
        hook tidak pernah benar-benar berjalan.
        """
        try:
            hook_rule = ""
            if requested_hook:
                hook_rule = (
                    f"\n3. MANDATORY HOOK CHECK: The writer was REQUIRED to open with a "
                    f"'{requested_hook.upper()}' style hook. If the opening is clearly a different "
                    f"style, DEDUCT 4 POINTS and state plainly in the feedback which style was used "
                    f"instead and how to rewrite the opening as '{requested_hook.upper()}'.\n"
                )

            editor_prompt = f"""You are a cynical, highly-experienced American Facebook Marketing Editor for a gold prospecting page based in the US.
Review this drafted caption.
1. Does the first line grab attention? Is it engaging?
2. Does it sound like a rugged American veteran? (It MUST use Imperial units like oz/inches/feet, NOT metric).
{hook_rule}
Assign a SCORE from 1 to 10 for "Scroll-Stopping Power". If it uses metric units, automatically deduct 5 points.

HOOK_TYPE MUST BE EXACTLY ONE OF THESE SEVEN WORDS — never invent your own label:
Fear, Secret, Mythbuster, Challenge, Story, Fact, News
Pick the closest match. (Curiosity/mystery/insider angles = Secret. Contrast or
"everyone is wrong" angles = Mythbuster. Science/geology explanations = Fact.)

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
            print(f"Editor review failed: {redact(e)}")
            return {"score": 10, "feedback": "Valid", "hook_type": "Unknown"}

    def editor_score_correlation(self, page_id=None, min_samples=12):
        """Uji apakah skor editor AI benar-benar meramalkan engagement.

        Selama ini editor menilai caption 1-10 dan memaksa tulis ulang di bawah 8,
        tapi nilainya tidak pernah dicocokkan dengan hasil nyata. Kalau ternyata
        tidak berkorelasi, seluruh siklus tulis-ulang cuma membakar kuota API.

        Return dict: {'r': korelasi Pearson, 'n': jumlah sampel,
                      'avg_high': engagement rata2 skor >=8,
                      'avg_low': engagement rata2 skor <8, 'verdict': str}
        """
        try:
            from core.database import get_db_connection
            conn = get_db_connection()
            query = '''
                SELECT editor_score AS score, engagement AS eng
                FROM post_engagement
                WHERE editor_score IS NOT NULL
            '''
            params = []
            if page_id:
                query += ' AND page_id = ?'
                params.append(page_id)
            rows = conn.execute(query, params).fetchall()
            conn.close()
        except Exception as e:
            return {'r': None, 'n': 0, 'verdict': f'gagal membaca data: {e}'}

        pairs = [(float(r['score']), float(r['eng'])) for r in rows
                 if r['score'] is not None and r['eng'] is not None]
        n = len(pairs)
        if n < min_samples:
            return {'r': None, 'n': n, 'avg_high': None, 'avg_low': None,
                    'verdict': f'data belum cukup ({n}/{min_samples} post)'}

        xs = [p[0] for p in pairs]
        ys = [p[1] for p in pairs]
        mx, my = sum(xs) / n, sum(ys) / n
        num = sum((x - mx) * (y - my) for x, y in pairs)
        dx = sum((x - mx) ** 2 for x in xs) ** 0.5
        dy = sum((y - my) ** 2 for y in ys) ** 0.5
        r = (num / (dx * dy)) if dx > 0 and dy > 0 else 0.0

        high = [y for x, y in pairs if x >= 8]
        low = [y for x, y in pairs if x < 8]
        avg_high = sum(high) / len(high) if high else None
        avg_low = sum(low) / len(low) if low else None

        if r >= 0.2:
            verdict = 'editor BERGUNA (skor tinggi cenderung engagement tinggi)'
        elif r <= -0.2:
            verdict = 'editor MENYESATKAN (skor tinggi justru engagement rendah)'
        else:
            verdict = 'editor TIDAK BERPENGARUH (skornya acak terhadap hasil)'

        return {'r': r, 'n': n, 'avg_high': avg_high, 'avg_low': avg_low, 'verdict': verdict}

    def _editor_is_trustworthy(self, page_id=None):
        """True kalau siklus tulis-ulang editor layak dijalankan untuk page ini.

        Bersikap optimis saat data belum cukup (perilaku lama dipertahankan),
        dan baru mematikan tulis-ulang setelah ada bukti bahwa skor editor tidak
        berhubungan — atau malah berlawanan — dengan engagement nyata.
        """
        try:
            stats = self.editor_score_correlation(page_id)
        except Exception:
            return True, 'gagal mengevaluasi editor'

        if stats.get('r') is None:
            return True, stats.get('verdict', 'data belum cukup')
        if stats['r'] <= -0.1:
            return False, f"korelasi {stats['r']:+.2f} dari {stats['n']} post: {stats['verdict']}"
        return True, f"korelasi {stats['r']:+.2f} dari {stats['n']} post"

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

    def _cari_topik_serupa(self, judul, ambang=0.5):
        """Cari topik yang sudah ada dan sangat mirip dengan judul ini.

        Return index topik serupa, atau None. Dipakai agar generator tidak
        terus-menerus menciptakan ulang topik yang sebenarnya sudah ada —
        pemeriksaan produksi menemukan 63 pasang topik hasil generate yang
        kemiripannya >=50%, beberapa bahkan identik.
        """
        target = self._tokenize(judul or '')
        if not target:
            return None
        for i, t in enumerate(self.topics):
            lain = self._tokenize(t.get('headline') or '')
            if not lain:
                continue
            irisan = len(target & lain)
            gabungan = len(target | lain)
            if gabungan and irisan / gabungan >= ambang:
                return i
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
            print(f"⚠️ Dynamic Topic Generation failed: {redact(e)}")
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
                layout, why = self._choose_layout(page_id, random.randrange(len(self.active_layouts) or 1))
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

        if not self.topics:
            return None

        # Indeks rotasi disimpan di file dan bertahan lintas restart, sementara
        # kolam topik bisa menyusut (pembersihan duplikat, pembuangan topik
        # cacat). Tanpa dilipat, indeks lama menunjuk ke luar batas dan
        # menggagalkan seluruh siklus posting dengan IndexError.
        current_index %= len(self.topics)

        # Cek audience preferences dari analisis komentar.
        # Khusus untuk memilih TOPIK, label hook dibuang — hook mengatur gaya
        # pembuka caption, bukan isi konten. Mencampur keduanya membuat
        # pencocokan topik cuma membandingkan kata "fact"/"secret".
        preferences = self._get_topic_keywords(page_id)

        selected_index = current_index
        explore_mode = False

        # Jalur utama begitu ada bukti engagement per topik: Thompson Sampling
        # yang memakai preferensi audiens sebagai prior. Kalau belum ada bukti,
        # lanjut ke jalur lama (pencocokan preferensi + rotasi) di bawah.
        performa_index = self._choose_topic_by_performance(
            page_id, preferences, state.get('recently_used', [])
        )
        if performa_index is not None:
            topic = self.topics[performa_index].copy()
            layout, why = self._choose_layout(page_id, performa_index)
            if layout:
                topic['layout'] = layout['name']
                topic['composition'] = layout['composition']
                print(f"   🎨 Layout: {layout['name']} ({why})")
            self._simpan_state(state_file, state, current_index, performa_index)
            return topic

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
            elif best_matches:
                # Ada topik yang cocok, hanya saja baru dipakai. Pakai topik
                # cocok lain di luar 2 terakhir — JANGAN langsung bikin topik baru.
                cadangan = [i for i in best_matches if i not in recently_used[-2:]] or best_matches
                selected_index = random.choice(cadangan)
            elif preferences and random.random() < 0.15:
                # preferences di sini sudah bebas label hook, jadi generator
                # menerima kata kunci topik yang benar-benar bermakna
                # Benar-benar tidak ada topik yang cocok. Baru di sini boleh
                # menciptakan topik baru, dan itu pun jarang.
                #
                # Dulu generator dipanggil setiap kali kandidat kebetulan sudah
                # dipakai belakangan. Akibatnya topics.json membengkak 101 -> 199
                # dengan 63 pasang topik yang kemiripannya >=50% (beberapa
                # identik). Efek sampingnya fatal: hampir tiap postingan memakai
                # topik unik, sehingga tidak ada topik yang pernah mengumpulkan
                # cukup sampel untuk dipelajari.
                top_keyword = preferences[0]
                new_topic = self._generate_dynamic_topic(top_keyword)
                if new_topic:
                    kembar = self._cari_topik_serupa(new_topic.get('headline'))
                    if kembar is not None:
                        selected_index = kembar
                        print(f"   ♻️  Topik serupa sudah ada, memakai yang lama: "
                              f"{self.topics[kembar]['headline'][:50]}")
                    else:
                        self.topics.append(new_topic)
                        selected_index = len(self.topics) - 1
                        print(f"   🌟 Topik baru dibuat: {new_topic['headline'][:50]}")
                        try:
                            with open(Path(__file__).parent / 'data' / 'topics.json', 'w', encoding='utf-8') as f:
                                json.dump(self.topics, f, indent=4)
                        except Exception as e:
                            print(f"   ⚠️ Gagal menyimpan topik baru: {redact(e)}")

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
        requested_hook = winning_hooks[0] if winning_hooks else None
        topic['requested_hook'] = requested_hook

        if requested_hook:
            best_hook = requested_hook.upper()
            winning_hook_instruction = (
                f"\n🔥 CRITICAL INSTRUCTION: Based on real engagement data from THIS page, the "
                f"'{best_hook}' hook style performs best. Your opening MUST be a '{best_hook}' hook. "
                f"An editor will check this and reject the draft if the hook is any other style.\n"
            )
            # Hanya tampilkan template untuk gaya yang diminta. Menampilkan daftar
            # generik sekaligus membuat model mengikuti daftar itu dan mengabaikan
            # gaya yang sudah terbukti menang.
            examples = "\n".join(HOOK_PLAYBOOK.get(requested_hook, []))
            hook_style_block = (
                f"HOOK STYLE — WAJIB bergaya {best_hook} (jangan pakai gaya lain):\n{examples}\n"
                f"Tiru POLA-nya, jangan salin kalimatnya mentah-mentah."
            )
        else:
            best_hook = None
            hook_style_block = f"HOOK STYLE (MUST USE ONE):\n{GENERIC_HOOK_STYLES}"

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

{hook_style_block}

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
        # Kalau editor terbukti tidak berkorelasi dengan engagement nyata di page
        # ini, hentikan siklus tulis-ulang: itu hanya membakar kuota API untuk
        # mengejar nilai yang tidak berarti apa-apa.
        editor_trusted, trust_note = self._editor_is_trustworthy(page_id)
        max_retries = 2 if editor_trusted else 0
        if not editor_trusted:
            print(f"   🧪 Editor rewrite dimatikan untuk page ini — {trust_note}")

        final_caption = ""
        topic['hook_type'] = "Unknown"
        topic['editor_score'] = None

        # Draf terbaik sejauh ini. Menulis ulang tidak dijamin membaik — pada
        # 1 September percobaan berturut-turut menghasilkan 4/10 lalu 2/10 lalu
        # 2/10, dan versi 2/10 itulah yang tayang hanya karena kebetulan
        # terakhir. Kita simpan yang terbaik dan pakai itu kalau tidak ada satu
        # pun yang lolos ambang.
        draf_terbaik = None  # (skor, caption, hook_type)

        for attempt in range(max_retries + 1):
            import time
            try:
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=current_prompt
                )
                caption = response.text.strip()

                # Editor review — ikut memeriksa kepatuhan gaya hook
                review = self._editor_review(caption, requested_hook=requested_hook)
                print(f"   🕵️  Editor Review (Attempt {attempt+1}): Score {review.get('score')}/10 - Hook: {review.get('hook_type')}")

                # Normalisasi ke daftar resmi. Kalau editor tetap mengarang label
                # (mis. "mystery", "contrast"), pemetaan sinonim menyelamatkannya
                # supaya sinyal pembelajaran tidak terbuang seperti sebelumnya.
                from comment_analyzer import normalize_hook
                raw_hook = review.get('hook_type', 'Unknown')
                canonical = normalize_hook(raw_hook)
                if canonical:
                    hook_label = canonical.capitalize()
                    if canonical not in str(raw_hook).lower():
                        print(f"   🔤 Label editor '{raw_hook}' dipetakan ke '{canonical}'")
                else:
                    hook_label = raw_hook
                try:
                    skor = float(review.get('score')) if review.get('score') is not None else None
                except (TypeError, ValueError):
                    skor = None

                # Skor dan label hook harus menggambarkan caption yang BENAR-BENAR
                # tayang, bukan percobaan terakhir. Kalau tidak, data pembelajaran
                # kita salah label.
                if draf_terbaik is None or (skor or 0) > draf_terbaik[0]:
                    draf_terbaik = ((skor or 0), caption, hook_label, skor)

                if review.get('score', 0) >= 8:
                    topic['hook_type'] = hook_label
                    topic['editor_score'] = skor
                    final_caption = caption
                    break
                elif attempt == max_retries:
                    _, caption_terbaik, hook_terbaik, skor_terbaik = draf_terbaik
                    if caption_terbaik is not caption:
                        print(f"   ↩️  Tidak ada draf yang lolos; memakai yang terbaik "
                              f"(skor {skor_terbaik}) alih-alih percobaan terakhir (skor {skor})")
                    topic['hook_type'] = hook_terbaik
                    topic['editor_score'] = skor_terbaik
                    final_caption = caption_terbaik
                    break
                else:
                    print(f"   ✏️  Editor demanded rewrite: {review.get('feedback')}")
                    # Provide the rejected draft so Gemini knows what to fix
                    current_prompt = base_prompt + f"\n\n[YOUR PREVIOUS DRAFT - REJECTED]:\n{caption}\n\nEDITOR FEEDBACK: {review.get('feedback')}\n\n🔥 CRITICAL INSTRUCTION: Write a COMPLETELY NEW version that directly fixes the editor's feedback above. Do not repeat the same mistakes."
                    time.sleep(2)
            except Exception as e:
                print(f"   ⚠️  Gemini text error: {redact(e)}")
                if attempt < max_retries:
                    time.sleep(4)
                elif draf_terbaik:
                    # Percobaan terakhir gagal, tapi draf sebelumnya masih layak.
                    # Membuangnya berarti melewatkan satu jadwal posting tanpa
                    # alasan yang perlu.
                    _, caption_terbaik, hook_terbaik, skor_terbaik = draf_terbaik
                    print(f"   ↩️  Percobaan terakhir gagal; memakai draf sebelumnya (skor {skor_terbaik})")
                    topic['hook_type'] = hook_terbaik
                    topic['editor_score'] = skor_terbaik
                    final_caption = caption_terbaik
                    break
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
