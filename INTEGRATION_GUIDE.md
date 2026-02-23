# 🔗 PANDUAN INTEGRASI WEB APP → AUTO POSTER

## 📋 Overview

Dokumen ini menjelaskan cara mengintegrasikan aplikasi generator yang sudah ada (https://gold.kelasmaster.id/) dengan sistem auto poster.

---

## 🎯 Yang Perlu Dilakukan

### 1. **Tambahkan Button "Queue for Auto Post"**

Di aplikasi generator Anda, tambahkan button setelah user generate caption & image:

```jsx
<button onClick={handleQueuePost}>
  📤 Queue for Auto Post
</button>
```

### 2. **Tambahkan Function untuk Kirim ke API**

```javascript
async function handleQueuePost() {
  // Get canvas element (poster yang sudah di-generate)
  const canvas = document.getElementById('your-canvas-id');
  const imageDataURL = canvas.toDataURL('image/png');
  
  // Get caption yang sudah di-generate
  const caption = document.getElementById('caption-textarea').value;
  
  // Kirim ke API
  const response = await fetch('http://YOUR_SERVER_IP:18794/api/queue-post', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      caption: caption,
      image_data: imageDataURL,
      page_ids: ['366143080610045', '488507404341313']  // Erna Gold & Putri Kejora
    })
  });
  
  const result = await response.json();
  
  if (result.success) {
    alert('✅ Queued for auto posting!');
  } else {
    alert('❌ Error: ' + result.error);
  }
}
```

---

## 📡 API Endpoint

### **POST /api/queue-post**

**URL:** `http://YOUR_SERVER_IP:18794/api/queue-post`

**Request Body:**
```json
{
  "caption": "Caption text here...",
  "image_data": "data:image/png;base64,iVBORw0KG...",
  "page_ids": ["366143080610045", "488507404341313"]
}
```

**Response (Success):**
```json
{
  "success": true,
  "message": "Queued for 2 page(s)",
  "image_path": "queued_poster_20260222_195700.png"
}
```

**Response (Error):**
```json
{
  "error": "Error message here"
}
```

---

## 🔧 Implementasi Step-by-Step

### **Step 1: Identifikasi Canvas Element**

Di aplikasi Anda, cari element canvas yang menampilkan poster:

```javascript
// Contoh jika menggunakan canvas
const canvas = document.getElementById('poster-canvas');

// Atau jika menggunakan React ref
const canvasRef = useRef(null);
const canvas = canvasRef.current;
```

### **Step 2: Convert Canvas to Base64**

```javascript
const imageDataURL = canvas.toDataURL('image/png');
// Result: "data:image/png;base64,iVBORw0KG..."
```

### **Step 3: Get Caption Text**

```javascript
// Jika caption di state (React)
const caption = captionState;

// Atau dari textarea
const caption = document.getElementById('caption').value;
```

### **Step 4: Get Selected Fanspages**

```javascript
// Option 1: Hardcode (post ke semua)
const pageIds = ['366143080610045', '488507404341313'];

// Option 2: User pilih via checkbox
const pageIds = selectedFanspages.map(page => page.id);
```

### **Step 5: Send to API**

```javascript
async function queuePost() {
  try {
    const response = await fetch('http://YOUR_SERVER_IP:18794/api/queue-post', {
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
      // Show success message
      alert('✅ ' + result.message);
    } else {
      // Show error
      alert('❌ ' + result.error);
    }
  } catch (error) {
    alert('❌ Network error: ' + error.message);
  }
}
```

---

## 📦 Ready-to-Use Component

File: `web-app-integration.js` sudah disediakan dengan:

1. ✅ `queueForAutoPost()` - Function untuk queue posting
2. ✅ `getFanspages()` - Function untuk get list fanspages
3. ✅ `QueueButton` - React component siap pakai
4. ✅ Error handling
5. ✅ Loading states

**Cara pakai:**

```javascript
import { QueueButton } from './web-app-integration';

// Di component Anda
<QueueButton 
  caption={generatedCaption}
  imageCanvas={canvasElement}
  onSuccess={(result) => console.log('Success!', result)}
  onError={(error) => console.error('Error!', error)}
/>
```

---

## 🧪 Testing

### **Test 1: Manual Test**

```javascript
// Di browser console
const testData = {
  caption: "Test caption from web app",
  image_data: "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
  page_ids: ["366143080610045"]
};

fetch('http://YOUR_SERVER_IP:18794/api/queue-post', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify(testData)
})
.then(r => r.json())
.then(console.log);
```

### **Test 2: Check Queue**

```bash
curl http://YOUR_SERVER_IP:18794/api/queue
```

### **Test 3: Process Queue**

```bash
cd /home/ubuntu/goldgen-automation
./run.sh
```

---

## 🔄 Workflow Setelah Integrasi

```
User di Web App
    ↓
Input harga emas
    ↓
Generate caption (Gemini AI)
    ↓
Generate poster (Canvas)
    ↓
Preview hasil
    ↓
Klik "Queue for Auto Post"
    ↓
Pilih fanspage (optional)
    ↓
POST /api/queue-post
    ↓
Saved to database (post_queue)
    ↓
Auto poster process queue (setiap jam)
    ↓
Post to Facebook
    ↓
✅ POSTED!
```

---

## 📝 Checklist Integrasi

- [ ] Identifikasi canvas element di web app
- [ ] Identifikasi caption element/state
- [ ] Tambahkan button "Queue for Auto Post"
- [ ] Implementasi function `queueForAutoPost()`
- [ ] Test dengan 1 fanspage dulu
- [ ] Add fanspage selector (optional)
- [ ] Add loading state
- [ ] Add error handling
- [ ] Test end-to-end
- [ ] Deploy to production

---

## 🆘 Troubleshooting

### **CORS Error**

Jika ada CORS error, tambahkan di `api.py`:

```python
from flask_cors import CORS
CORS(app, origins=['https://gold.kelasmaster.id'])
```

### **Network Error**

Pastikan:
1. API server running (port 18794)
2. Firewall allow port 18794
3. URL correct (http://YOUR_SERVER_IP:18794)

### **Image Too Large**

Jika image terlalu besar, compress dulu:

```javascript
canvas.toDataURL('image/png', 0.8);  // 80% quality
```

---

## 📞 Support

Jika ada masalah, cek:
1. API logs: `tail -f /home/ubuntu/goldgen-automation/logs/api.log`
2. Auto poster logs: `tail -f /home/ubuntu/goldgen-automation/logs/auto_poster.log`
3. Database: `sqlite3 /home/ubuntu/goldgen-automation/data/posts.db "SELECT * FROM post_queue"`

---

## ✅ Next Steps

1. **Update web app** dengan kode integrasi
2. **Test** posting dari web app
3. **Verify** queue di database
4. **Monitor** auto poster process queue
5. **Enjoy** automated posting! 🚀
