# 🔗 API ENDPOINTS UNTUK WEB APP GENERATOR

## 📋 Overview

Auto poster sekarang akan memanggil web app generator untuk membuat konten.
Web app perlu expose 2 API endpoints.

---

## 📡 API Endpoints yang Perlu Dibuat

### 1. **POST /api/generate** - Generate Caption

**Request:**
```json
{
  "price": 1050000,
  "change": "+2.5%",
  "date": "22 Februari 2026"
}
```

**Response:**
```json
{
  "success": true,
  "caption": "Caption text yang sudah di-generate..."
}
```

**Implementation Example (Express.js):**
```javascript
app.post('/api/generate', async (req, res) => {
  const { price, change, date } = req.body;
  
  // Call your Gemini AI function
  const caption = await generateCaption(price, change, date);
  
  res.json({
    success: true,
    caption: caption
  });
});
```

---

### 2. **POST /api/generate-image** - Generate Poster Image

**Request:**
```json
{
  "price": 1050000,
  "change": "+2.5%",
  "date": "22 Februari 2026"
}
```

**Response:**
```json
{
  "success": true,
  "image_data": "data:image/png;base64,iVBORw0KG..."
}
```

**Implementation Example (Express.js):**
```javascript
app.post('/api/generate-image', async (req, res) => {
  const { price, change, date } = req.body;
  
  // Generate image using your canvas logic
  const canvas = createCanvas(1080, 1080);
  const ctx = canvas.getContext('2d');
  
  // ... your drawing logic ...
  
  // Convert to base64
  const imageDataURL = canvas.toDataURL('image/png');
  
  res.json({
    success: true,
    image_data: imageDataURL
  });
});
```

---

## 🔄 Workflow Baru

```
Auto Poster (setiap 3 jam)
    ↓
Fetch gold price
    ↓
POST /api/generate (web app)
    ← Caption generated
    ↓
POST /api/generate-image (web app)
    ← Image generated
    ↓
Post to Facebook
    ↓
✅ DONE!
```

---

## 🎯 Keuntungan

1. ✅ **Single Source of Truth** - Semua konten dari 1 generator
2. ✅ **Consistent Design** - Design poster selalu sama
3. ✅ **Easy Update** - Update generator, otomatis apply ke auto poster
4. ✅ **Fallback** - Jika web app down, auto poster punya fallback

---

## 🔧 Implementation Checklist

### Di Web App:
- [ ] Buat endpoint POST /api/generate
- [ ] Buat endpoint POST /api/generate-image
- [ ] Test endpoints dengan curl/Postman
- [ ] Enable CORS untuk auto poster server

### Di Auto Poster:
- [x] Update generate_content() untuk call web app API
- [x] Update generate_poster_image() untuk call web app API
- [x] Add fallback jika web app unavailable
- [x] Test integration

---

## 🧪 Testing

### Test Caption API:
```bash
curl -X POST https://gold.kelasmaster.id/api/generate \
  -H "Content-Type: application/json" \
  -d '{
    "price": 1050000,
    "change": "+2.5%",
    "date": "22 Februari 2026"
  }'
```

### Test Image API:
```bash
curl -X POST https://gold.kelasmaster.id/api/generate-image \
  -H "Content-Type: application/json" \
  -d '{
    "price": 1050000,
    "change": "+2.5%",
    "date": "22 Februari 2026"
  }'
```

### Test Auto Poster:
```bash
cd /home/ubuntu/goldgen-automation
./run.sh
```

---

## 📝 Notes

- Auto poster akan call web app API setiap kali posting
- Jika web app down/error, auto poster akan fallback ke generate sendiri
- Timeout: 30 detik per API call
- CORS harus di-enable untuk auto poster server IP

---

## ✅ Status

- [x] Auto poster updated
- [ ] Web app API endpoints (perlu dibuat)
- [ ] Testing integration
- [ ] Production deployment
