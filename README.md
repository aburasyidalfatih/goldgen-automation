# GoldGen Auto Poster - Automated Facebook Posting

Sistem automasi untuk generate poster edukasi Gold Prospecting & Mining dan mem-posting ke Facebook setiap jadwal yang ditentukan.

## Features

- ✅ Generate poster edukasi dengan AI (Gemini)
- ✅ Auto-post ke Facebook Page sesuai jadwal
- ✅ Database tracking untuk semua posts
- ✅ Error logging dan monitoring
- ✅ Custom poster design berdasarkan topik

## Setup

### 1. Install Dependencies

```bash
cd /home/ubuntu/goldgen-automation
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure Facebook

Anda perlu:
1. **Facebook Page ID** - ID dari fanpage Anda
2. **Page Access Token** - Token dengan permission `pages_manage_posts`

Cara mendapatkan:
1. Buka https://developers.facebook.com/tools/explorer/
2. Pilih aplikasi Anda (atau buat baru)
3. Pilih Page yang ingin digunakan
4. Generate token dengan permission: `pages_manage_posts`, `pages_read_engagement`
5. Copy Page ID dan Access Token

### 3. Run Setup

```bash
python3 setup.py
```

Masukkan:
- Gemini API Key (sudah terisi default)
- Facebook Page ID
- Facebook Page Access Token

### 4. Test Manual

```bash
python3 auto_poster.py
```

Jika berhasil, akan muncul:
- ✅ Successfully posted! FB Post ID: xxxxx

## Scheduling (Internal Worker)

Sejak migrasi ke Dokploy, penjadwalan **tidak lagi memakai cron**. Scheduler
berjalan di dalam proses aplikasi (APScheduler, lihat `core/worker.py`):

| Job | Interval | Jitter | Anti-tumpuk |
|-----|----------|--------|-------------|
| Auto Poster | tiap 15 menit | ±4 menit | file lock + `max_instances=1` |
| Auto Reply | tiap 10 menit | ±3 menit | file lock + `max_instances=1` |

Jadwal jam posting per fanpage tetap diatur lewat `schedule_hours` di
`data/config.json` (atau lewat dashboard) — worker hanya menentukan seberapa
sering bot mengecek apakah sudah waktunya posting.

## Environment Variables

Lihat `.env.example`. Yang penting untuk produksi:

- `DASHBOARD_PIN` — PIN login dashboard (default `888888`, **wajib diganti**)
- `SECRET_KEY` — kunci session; kalau kosong akan dibuat otomatis di `data/secret.key`
- `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` — notifikasi (opsional)

## Management Commands

### View Logs
```bash
tail -f /home/ubuntu/goldgen-automation/logs/auto_poster.log
```

### Check Post History
```bash
sqlite3 /home/ubuntu/goldgen-automation/data/posts.db "SELECT * FROM posts ORDER BY id DESC LIMIT 10;"
```

### Manual Run
```bash
cd /home/ubuntu/goldgen-automation
source venv/bin/activate
python3 auto_poster.py
```

### Stop / Start Automation
Pakai tombol toggle di dashboard, atau file penanda:
```bash
touch .DISABLED   # bot berhenti posting (worker tetap hidup)
rm .DISABLED      # bot aktif lagi
```

## File Structure

```
goldgen-automation/
├── api.py                     # Entrypoint: Flask + internal worker (port 18794)
├── auto_poster.py             # Siklus posting utama
├── auto_reply_comments.py     # Auto-reply komentar (Gemini + Vision)
├── comment_analyzer.py        # JIT ML research dari komentar & reaksi
├── auto_analyzer.py           # Analisis batch semua page (manual/CLI)
├── goldgen_service.py         # Pemilihan topik, caption, prompt gambar
├── telegram_notifier.py       # Notifikasi Telegram (opsional)
├── core/
│   ├── config.py             # Path, PIN, secret key
│   ├── database.py           # Skema DB tunggal + auto-migration
│   ├── locks.py              # File lock anti proses dobel
│   └── worker.py             # APScheduler internal
├── controllers/routes.py      # Semua endpoint HTTP
├── templates/                 # Dashboard, analytics, login, detail
├── data/
│   ├── config.json           # Konfigurasi (API key, token FB)
│   ├── posts.db              # Database SQLite
│   ├── topics.json           # Basis pengetahuan topik
│   ├── layouts.json          # Gaya visual poster
│   └── secret.key            # Kunci session (auto-generate, jangan di-commit)
├── generated_images/          # Poster hasil generate
└── logs/                      # Log eksekusi
```

## Troubleshooting

### Error: Invalid Facebook Token
- Token expired → Generate new token di Facebook Developer Tools
- Update config: Edit `data/config.json` dan ganti `fb_access_token`

### Error: Gemini API
- Check API key di `data/config.json`
- Verify quota di Google AI Studio

### Posts Not Appearing
- Cek log worker di output container (job `auto_poster_job` / `auto_reply_job`)
- Pastikan file `.DISABLED` tidak ada
- Cek apakah page sedang cooldown: `sqlite3 data/posts.db "SELECT * FROM last_post_time;"`
- Cek permission Facebook Page & masa berlaku token

## Customization

### Change Posting Interval
Atur per fanpage lewat dashboard, atau langsung di `data/config.json`:
```json
"schedule_hours": [7, 12, 17, 21]   // jam posting (WIB)
"interval_hours": 6                 // alternatif: jarak antar posting
```
Frekuensi pengecekan worker diatur di `core/worker.py`.

### Customize Poster Design
Edit `goldgen_service.py` → `generate_image_prompt()` (prompt AI) atau
`auto_poster.py` → `_generate_fallback_image()` (poster PIL saat AI gagal)

### Add Custom Topics
Edit `data/topics.json` untuk menambahkan materi edukasi baru. Bot akan memilih topik ini secara acak (atau berdasarkan sentimen komentar) dan membuat gambar instruksional yang menarik.

## Monitoring

Check system status:
```bash
# View recent posts
sqlite3 data/posts.db "SELECT timestamp, status, fb_post_id FROM posts ORDER BY id DESC LIMIT 5;"

# Count successful posts
sqlite3 data/posts.db "SELECT COUNT(*) FROM posts WHERE status='success';"

# View errors
sqlite3 data/posts.db "SELECT timestamp, error_message FROM posts WHERE status='failed';"
```

## Security Notes

- `config.json` contains sensitive data (API keys, tokens)
- File permissions are set to user-only access
- Never commit config.json to git
- Long-lived page token tidak punya masa kedaluwarsa; ia hanya mati kalau
  password diganti, izin dicabut, atau app kena review. Cek kapan saja dengan:
  `python check_tokens.py`
- Ganti `DASHBOARD_PIN` dari nilai default sebelum dipakai di produksi

## Changelog

### 2026-08-20
- **Skema database disatukan** di `core/database.py` + migrasi otomatis dari
  skema lama (memperbaiki cooldown anti-ban & antrean posting yang gagal senyap)
- **Endpoint sensitif dikunci PIN** (config, fanspages, settings, bot-toggle, queue)
- **Alasan kegagalan selalu tercatat & tampil** di dashboard, termasuk token tidak aktif
- **Status token berbasis bukti** — hitung mundur 60 hari dihapus karena
  long-lived page token tidak punya masa kedaluwarsa
- **Vision AI diperbaiki** — model hardcoded `gemini-1.5-flash` sudah 404
  (dipensiunkan Google), sekarang memakai model dari config
- **Layout gambar belajar dari engagement** via Thompson Sampling (Normal-Normal),
  sadar ukuran sampel — 1 post viral tidak lagi membajak strategi visual
- **Skor editor AI divalidasi** terhadap engagement nyata; tulis-ulang dimatikan
  otomatis kalau terbukti tidak berkorelasi
- **Analisis & UI jam posting** per fanspage di `/schedule-insight`
- Total topics: **101** · layouts: **16**
- File baru: `core/locks.py`, `telegram_notifier.py`, `learning_insights.py`,
  `check_tokens.py`, `templates/schedule_insight.html`

### 2026-03-27
- **Fitur Analisa Komentar** — tombol "💬 Analisa Komentar" di halaman Analytics
  - Ambil komentar dari semua page (3 hari terakhir)
  - Analisis dengan Gemini AI: sentiment, top keywords, suggested topics
  - Simpan ke tabel `comment_insights` & `topic_preferences` di DB
  - Tampilkan akumulasi preferensi audience
- **5 topik baru** ditambahkan ke hardcode berdasarkan hasil analisis komentar:
  - [76] GOLD VS PYRITE
  - [77] FIELD TESTS FOR GOLD
  - [78] MINERAL IDENTIFICATION
  - [79] GOLD DEPOSIT TYPES
  - [80] GEOLOGICAL FORMATIONS
- Total topics: **80**
- File baru: `comment_analyzer.py`
