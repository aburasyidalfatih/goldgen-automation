# GoldGen Auto Poster - Automated Facebook Posting

Sistem automasi untuk generate poster harga emas dan posting ke Facebook setiap 3 jam.

## Features

- ✅ Generate poster harga emas dengan AI (Gemini)
- ✅ Auto-post ke Facebook Page setiap 3 jam
- ✅ Database tracking untuk semua posts
- ✅ Error logging dan monitoring
- ✅ Custom poster design dengan gradient gold theme

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

## Cron Schedule

Automasi sudah dijadwalkan untuk berjalan setiap 3 jam:
- 00:00, 03:00, 06:00, 09:00, 12:00, 15:00, 18:00, 21:00

Cron job: `0 */3 * * * /home/ubuntu/goldgen-automation/run.sh`

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

### Stop Automation
```bash
crontab -e
# Comment out the goldgen line with #
```

### Start Automation
```bash
crontab -e
# Uncomment the goldgen line
```

## File Structure

```
goldgen-automation/
├── auto_poster.py          # Main script
├── setup.py                # Setup configuration
├── run.sh                  # Cron wrapper script
├── requirements.txt        # Python dependencies
├── venv/                   # Virtual environment
├── data/
│   ├── config.json        # Configuration (API keys, tokens)
│   └── posts.db           # SQLite database
├── logs/
│   └── auto_poster.log    # Execution logs
└── generated_images/       # Generated poster images
```

## Troubleshooting

### Error: Invalid Facebook Token
- Token expired → Generate new token di Facebook Developer Tools
- Update config: Edit `data/config.json` dan ganti `fb_access_token`

### Error: Gemini API
- Check API key di `data/config.json`
- Verify quota di Google AI Studio

### Posts Not Appearing
- Check logs: `tail -f logs/auto_poster.log`
- Verify cron is running: `crontab -l`
- Check Facebook Page permissions

## Customization

### Change Posting Interval
Edit crontab:
```bash
crontab -e

# Every 3 hours (default)
0 */3 * * * /home/ubuntu/goldgen-automation/run.sh

# Every 2 hours
0 */2 * * * /home/ubuntu/goldgen-automation/run.sh

# Every 6 hours
0 */6 * * * /home/ubuntu/goldgen-automation/run.sh
```

### Customize Poster Design
Edit `auto_poster.py` → `generate_poster_image()` method

### Add Real Gold Price API
Edit `auto_poster.py` → `get_gold_price()` method
Integrate with real API like:
- https://www.goldapi.io/
- https://metals-api.com/
- Or local Indonesian gold price API

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
- Rotate Facebook tokens regularly (every 60 days recommended)
