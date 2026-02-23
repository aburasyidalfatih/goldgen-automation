# ✅ INTEGRASI WEB APP → AUTO POSTER

## 🎯 Masalah Solved!

Sekarang konten yang di-generate di **https://gold.kelasmaster.id/** bisa langsung digunakan oleh **auto poster**!

---

## 🔄 Cara Kerja

### 1. User Generate di Web App
```
User → gold.kelasmaster.id
  ↓
Input harga emas
  ↓
Generate caption (Gemini AI)
  ↓
Generate poster image
  ↓
Klik "Queue for Auto Post"
```

### 2. Web App Kirim ke API
```javascript
// Di web app, tambahkan fungsi ini:
async function queueForAutoPost(caption, imageDataURL, pageIds) {
  const response = await fetch('http://127.0.0.1:18794/api/queue-post', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      caption: caption,
      image_data: imageDataURL,  // base64 image
      page_ids: pageIds  // ['488507404341313', '366143080610045']
    })
  });
  
  const result = await response.json();
  console.log(result);  // {success: true, message: "Queued for 2 page(s)"}
}
```

### 3. Auto Poster Process Queue
```
Cron job runs (every hour)
  ↓
Auto poster checks queue
  ↓
Found queued posts
  ↓
Post to Facebook
  ↓
Mark as posted
```

---

## 📡 API Endpoints

### POST /api/queue-post
Queue a post from web app

**Request:**
```json
{
  "caption": "Caption text here...",
  "image_data": "data:image/png;base64,iVBORw0KG...",
  "page_ids": ["488507404341313", "366143080610045"]
}
```

**Response:**
```json
{
  "success": true,
  "message": "Queued for 2 page(s)",
  "image_path": "queued_poster_20260222_194500.png"
}
```

### GET /api/queue
Get pending posts in queue

**Response:**
```json
{
  "queue": [
    {
      "id": 1,
      "page_id": "488507404341313",
      "caption": "Caption preview...",
      "image_path": "queued_poster_20260222_194500.png",
      "status": "pending",
      "created_at": "2026-02-22T19:45:00"
    }
  ]
}
```

---

## 🗄️ Database Schema

### New Table: post_queue
```sql
CREATE TABLE post_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    page_id TEXT NOT NULL,
    caption TEXT NOT NULL,
    image_path TEXT NOT NULL,
    status TEXT DEFAULT 'pending',  -- pending, posted, failed, error
    created_at TEXT NOT NULL,
    posted_at TEXT
);
```

---

## 🔧 Implementasi di Web App

### Step 1: Add Button di UI
```jsx
<button onClick={() => queueForAutoPost(caption, imageDataURL, selectedPages)}>
  📤 Queue for Auto Post
</button>
```

### Step 2: Add Function
```javascript
async function queueForAutoPost(caption, imageDataURL, pageIds) {
  try {
    const response = await fetch('http://127.0.0.1:18794/api/queue-post', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        caption: caption,
        image_data: imageDataURL,
        page_ids: pageIds
      })
    });
    
    const result = await response.json();
    
    if (result.success) {
      alert(`✅ Queued for ${pageIds.length} page(s)!`);
    } else {
      alert(`❌ Error: ${result.error}`);
    }
  } catch (error) {
    alert(`❌ Error: ${error.message}`);
  }
}
```

### Step 3: Get Selected Pages
```javascript
// Contoh: User pilih fanspage mana yang mau di-post
const selectedPages = ['488507404341313'];  // Erna Gold
// atau
const selectedPages = ['488507404341313', '366143080610045'];  // Both
```

---

## 🧪 Testing

### Test Queue API
```bash
# Test queue a post
curl -X POST http://127.0.0.1:18794/api/queue-post \
  -H "Content-Type: application/json" \
  -d '{
    "caption": "Test caption from web app",
    "image_data": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
    "page_ids": ["366143080610045"]
  }'

# Check queue
curl http://127.0.0.1:18794/api/queue

# Run auto poster to process queue
cd /home/ubuntu/goldgen-automation
./run.sh
```

---

## ✅ Benefits

1. **User Control** - User bisa review/edit konten sebelum posting
2. **Flexible** - Bisa pilih fanspage mana yang mau di-post
3. **Integrated** - Web app dan auto poster sekarang terhubung
4. **Queue System** - Posting tidak langsung, bisa di-schedule
5. **Tracking** - Semua queued posts tercatat di database

---

## 🚀 Next Steps

1. **Update Web App** - Tambahkan button "Queue for Auto Post"
2. **Add UI** - Tampilkan queue status di dashboard
3. **Add Approval** - Optional: Admin approval sebelum posting
4. **Add Scheduling** - Optional: Schedule posting untuk waktu tertentu

---

## 📊 Workflow Lengkap

```
┌─────────────────────────────────────────────────────────────┐
│                    WEB APP (gold.kelasmaster.id)            │
│                                                             │
│  User Input → Generate Caption → Generate Image            │
│                         ↓                                   │
│                  Click "Queue for Auto Post"                │
│                         ↓                                   │
│              POST /api/queue-post                           │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│                    API SERVER (port 18794)                  │
│                                                             │
│  Receive request → Save image → Insert to post_queue       │
│                         ↓                                   │
│                  Return success                             │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│              AUTO POSTER (cron every hour)                  │
│                                                             │
│  Check post_queue → Found pending posts                     │
│         ↓                                                   │
│  Post to Facebook → Update status to 'posted'               │
│         ↓                                                   │
│  Log to database                                            │
└─────────────────────────────────────────────────────────────┘
                          ↓
                    ✅ POSTED!
```

---

**Status**: ✅ READY TO USE  
**API**: Running on port 18794  
**Auto Poster**: Configured with queue processing
