# 📊 ALUR KERJA APLIKASI GOLDGEN AUTO POSTER

## 🎯 Overview

Sistem ini memiliki **2 mode operasi**:
1. **Mode Manual** - User generate konten via web app
2. **Mode Otomatis** - Sistem generate & post otomatis

---

## 🔄 MODE 1: MANUAL (Via Web App)

### Alur Lengkap:

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. USER AKSES WEB APP                                           │
│    https://gold.kelasmaster.id/                                 │
└─────────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────────┐
│ 2. INPUT DATA                                                   │
│    • Harga emas: Rp 1,050,000                                   │
│    • Perubahan: +2.5%                                           │
│    • Tanggal: 22 Februari 2026                                  │
└─────────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────────┐
│ 3. GENERATE CAPTION (Gemini AI)                                 │
│    • Web app call Gemini API                                    │
│    • Model: gemini-3.1-pro-preview                              │
│    • Generate caption menarik & engaging                        │
└─────────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────────┐
│ 4. GENERATE POSTER IMAGE                                        │
│    • Canvas 1080x1080 px                                        │
│    • Gold theme design                                          │
│    • Display harga, perubahan, tanggal                          │
└─────────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────────┐
│ 5. PREVIEW & REVIEW                                             │
│    • User lihat caption & image                                 │
│    • Bisa edit jika perlu                                       │
└─────────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────────┐
│ 6. QUEUE FOR AUTO POST (Optional)                               │
│    • User klik "Queue for Auto Post"                            │
│    • Pilih fanspage mana yang mau di-post                       │
│    • POST /api/queue-post                                       │
│    • Data: caption + image + page_ids                           │
└─────────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────────┐
│ 7. SAVE TO QUEUE                                                │
│    • API save image ke server                                   │
│    • Insert ke database (post_queue table)                      │
│    • Status: pending                                            │
└─────────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────────┐
│ 8. MENUNGGU AUTO POSTER                                         │
│    • Queue akan diproses saat cron job jalan                    │
│    • Setiap jam (0 * * * *)                                     │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🤖 MODE 2: OTOMATIS (Auto Poster)

### Alur Lengkap:

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. CRON JOB TRIGGER                                             │
│    • Setiap jam (0 * * * *)                                     │
│    • Run: /home/ubuntu/goldgen-automation/run.sh                │
└─────────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────────┐
│ 2. AUTO POSTER START                                            │
│    • Load config.json                                           │
│    • Load fanspages (Putri Kejora, Erna Gold)                   │
│    • Connect to database                                        │
└─────────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────────┐
│ 3. PROCESS QUEUE (Dari Web App)                                 │
│    • Check post_queue table                                     │
│    • Ambil posts dengan status = 'pending'                      │
│    • Jika ada, post ke Facebook                                 │
│    • Update status = 'posted'                                   │
└─────────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────────┐
│ 4. CHECK INTERVAL (Per Fanspage)                                │
│    • Loop semua fanspage                                        │
│    • Check last_post_time table                                 │
│    • Hitung: sekarang - last_post >= interval?                  │
│    • Jika belum waktunya, skip                                  │
└─────────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────────┐
│ 5. FETCH GOLD PRICE                                             │
│    • Call gold_price_api.py                                     │
│    • Get current price (mock/real API)                          │
│    • Data: price, change, date                                  │
└─────────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────────┐
│ 6. GENERATE CAPTION (Gemini AI)                                 │
│    • Setup Gemini API                                           │
│    • Model: gemini-3.1-pro-preview                              │
│    • Prompt: Buat caption menarik untuk harga emas              │
│    • Response: Caption text                                     │
└─────────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────────┐
│ 7. GENERATE POSTER IMAGE                                        │
│    • Create canvas 1080x1080                                    │
│    • Draw gradient background                                   │
│    • Draw gold border                                           │
│    • Add text: title, price, change, date                       │
│    • Save to: generated_images/gold_poster_*.png                │
└─────────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────────┐
│ 8. POST TO FACEBOOK                                             │
│    • Facebook Graph API                                         │
│    • Endpoint: /{page_id}/photos                                │
│    • Upload: image + caption                                    │
│    • Response: post_id                                          │
└─────────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────────┐
│ 9. LOG TO DATABASE                                              │
│    • Insert ke posts table                                      │
│    • Data: timestamp, page_id, caption, image, fb_post_id       │
│    • Update last_post_time table                                │
└─────────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────────┐
│ 10. REPEAT FOR NEXT FANSPAGE                                    │
│     • Loop ke fanspage berikutnya                               │
│     • Ulangi step 4-9                                           │
└─────────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────────┐
│ 11. FINISH                                                      │
│     • Log completion                                            │
│     • Exit                                                      │
│     • Tunggu cron job berikutnya (1 jam lagi)                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🗄️ DATABASE FLOW

### Tables & Relationships:

```
┌─────────────────────────────────────────────────────────────────┐
│ config.json (File)                                              │
│ • gemini_api_key                                                │
│ • fanspages[]                                                   │
│   - name, page_id, access_token, interval_hours, enabled        │
└─────────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────────┐
│ posts.db (SQLite)                                               │
│                                                                 │
│ ┌─────────────────────────────────────────────────────────┐    │
│ │ posts                                                   │    │
│ │ • id, timestamp, page_id, page_name                     │    │
│ │ • content, image_path, fb_post_id                       │    │
│ │ • status, error_message                                 │    │
│ └─────────────────────────────────────────────────────────┘    │
│                                                                 │
│ ┌─────────────────────────────────────────────────────────┐    │
│ │ last_post_time                                          │    │
│ │ • page_id (PK)                                          │    │
│ │ • last_posted                                           │    │
│ └─────────────────────────────────────────────────────────┘    │
│                                                                 │
│ ┌─────────────────────────────────────────────────────────┐    │
│ │ post_queue (NEW!)                                       │    │
│ │ • id, page_id, caption, image_path                      │    │
│ │ • status (pending/posted/failed)                        │    │
│ │ • created_at, posted_at                                 │    │
│ └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🔀 DECISION FLOW

### Interval Check Logic:

```
START
  ↓
Load fanspage config
  ↓
Is fanspage enabled? ──NO──> Skip
  ↓ YES
Get last_post_time from DB
  ↓
Calculate: now - last_post_time
  ↓
Is >= interval_hours? ──NO──> Skip
  ↓ YES
Generate & Post
  ↓
Update last_post_time
  ↓
NEXT FANSPAGE
```

### Queue Processing Logic:

```
START
  ↓
Check post_queue table
  ↓
Any pending posts? ──NO──> Continue to auto-post
  ↓ YES
Get pending post
  ↓
Find fanspage config by page_id
  ↓
Fanspage found? ──NO──> Mark as error
  ↓ YES
Is enabled? ──NO──> Skip
  ↓ YES
Post to Facebook
  ↓
Success? ──YES──> Mark as posted
  ↓ NO
Mark as failed
  ↓
NEXT QUEUED POST
```

---

## 📊 COMPONENT INTERACTION

```
┌──────────────────────────────────────────────────────────────────┐
│                         USER INTERFACE                           │
│                                                                  │
│  ┌────────────────────┐         ┌─────────────────────┐         │
│  │  Web App           │         │  Dashboard          │         │
│  │  gold.kelasmaster  │         │  /dashboard         │         │
│  │  .id               │         │                     │         │
│  └────────────────────┘         └─────────────────────┘         │
│           ↓                              ↓                       │
└───────────┼──────────────────────────────┼───────────────────────┘
            ↓                              ↓
┌───────────┼──────────────────────────────┼───────────────────────┐
│           ↓                              ↓         API LAYER     │
│  ┌────────────────────────────────────────────────────┐          │
│  │  Flask API (port 18794)                            │          │
│  │  • POST /api/queue-post                            │          │
│  │  • GET  /api/queue                                 │          │
│  │  • GET  /api/config                                │          │
│  │  • POST /api/config                                │          │
│  │  • GET  /api/stats                                 │          │
│  │  • GET  /api/posts                                 │          │
│  └────────────────────────────────────────────────────┘          │
│                          ↓                                       │
└──────────────────────────┼───────────────────────────────────────┘
                           ↓
┌──────────────────────────┼───────────────────────────────────────┐
│                          ↓                  BUSINESS LOGIC       │
│  ┌────────────────────────────────────────────────────┐          │
│  │  auto_poster.py                                    │          │
│  │  • Load config                                     │          │
│  │  • Process queue                                   │          │
│  │  • Check intervals                                 │          │
│  │  • Generate caption (Gemini)                       │          │
│  │  • Generate image (PIL)                            │          │
│  │  • Post to Facebook                                │          │
│  │  • Log to database                                 │          │
│  └────────────────────────────────────────────────────┘          │
│           ↓              ↓              ↓                        │
└───────────┼──────────────┼──────────────┼────────────────────────┘
            ↓              ↓              ↓
┌───────────┼──────────────┼──────────────┼────────────────────────┐
│           ↓              ↓              ↓         DATA LAYER     │
│  ┌─────────────┐  ┌──────────┐  ┌──────────────┐                │
│  │ SQLite DB   │  │ Config   │  │ Images       │                │
│  │ posts.db    │  │ .json    │  │ /generated_  │                │
│  │             │  │          │  │ images/      │                │
│  └─────────────┘  └──────────┘  └──────────────┘                │
└──────────────────────────────────────────────────────────────────┘
            ↓
┌───────────┼──────────────────────────────────────────────────────┐
│           ↓                              EXTERNAL SERVICES       │
│  ┌─────────────────┐         ┌──────────────────────┐           │
│  │ Gemini AI       │         │ Facebook Graph API   │           │
│  │ (Google)        │         │                      │           │
│  └─────────────────┘         └──────────────────────┘           │
└──────────────────────────────────────────────────────────────────┘
```

---

## ⏰ TIMING & SCHEDULING

### Cron Job Schedule:
```
0 * * * *  →  Setiap jam (00:00, 01:00, 02:00, ...)
```

### Interval Per Fanspage:
```
Putri Kejora: 3 hours
  → Post jam: 00:00, 03:00, 06:00, 09:00, 12:00, 15:00, 18:00, 21:00

Erna Gold: 3 hours
  → Post jam: 00:00, 03:00, 06:00, 09:00, 12:00, 15:00, 18:00, 21:00
```

### Example Timeline:
```
00:00 → Cron runs → Check intervals → Post to both pages
01:00 → Cron runs → Check intervals → Skip (belum 3 jam)
02:00 → Cron runs → Check intervals → Skip (belum 3 jam)
03:00 → Cron runs → Check intervals → Post to both pages
...
```

---

## 🎯 SUMMARY

**2 Mode Operasi:**
1. **Manual** - User generate via web app → Queue → Auto poster process
2. **Otomatis** - Cron job → Generate → Post → Log

**Key Components:**
- Web App (React)
- API Server (Flask)
- Auto Poster (Python)
- Database (SQLite)
- External APIs (Gemini, Facebook)

**Flow:**
- User input → Generate → Queue/Post → Facebook → Log → Repeat

**Automation:**
- Cron job setiap jam
- Check interval per fanspage
- Process queue dari web app
- Generate & post otomatis
