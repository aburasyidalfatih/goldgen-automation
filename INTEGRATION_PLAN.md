# 🔗 Integrasi Web App dengan Auto Poster

## Situasi Saat Ini

### 1. Web App (https://gold.kelasmaster.id/)
- React app untuk generate poster manual
- User input harga emas
- Generate caption dengan Gemini AI
- Generate poster image
- **TIDAK** terintegrasi dengan auto poster

### 2. Auto Poster (/home/ubuntu/goldgen-automation/)
- Python script untuk posting otomatis
- Generate caption & image sendiri
- Post ke Facebook otomatis
- **TIDAK** menggunakan konten dari web app

## Masalah
❌ Konten yang di-generate di web app tidak digunakan oleh auto poster
❌ Dua sistem terpisah, tidak sinkron

## Solusi: 3 Opsi Integrasi

### Opsi 1: API Bridge (Recommended)
**Cara Kerja:**
1. Web app save generated content ke database/API
2. Auto poster ambil konten dari database/API
3. Auto poster post ke Facebook

**Keuntungan:**
- ✅ User bisa review/edit sebelum posting
- ✅ Fleksibel
- ✅ Konten terkontrol

**Implementasi:**
- Add API endpoint: POST /api/queue-post
- Web app kirim konten ke queue
- Auto poster ambil dari queue

### Opsi 2: Shared Database
**Cara Kerja:**
1. Web app save ke SQLite database
2. Auto poster baca dari database yang sama
3. Auto poster post konten yang belum di-post

**Keuntungan:**
- ✅ Simple
- ✅ No additional API needed

**Implementasi:**
- Web app write to posts.db
- Auto poster read pending posts

### Opsi 3: File-Based Queue
**Cara Kerja:**
1. Web app save JSON file ke folder queue/
2. Auto poster scan folder queue/
3. Auto poster process & delete file

**Keuntungan:**
- ✅ Very simple
- ✅ No database changes

**Implementasi:**
- Web app: Save to queue/*.json
- Auto poster: Process queue files

## Rekomendasi

**Gunakan Opsi 1 (API Bridge)** karena:
- Paling profesional
- Mudah di-extend
- User experience terbaik
- Bisa add approval workflow

## Next Steps

Pilih opsi mana yang Anda inginkan, saya akan implementasikan.
