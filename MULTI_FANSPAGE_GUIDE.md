# Multi-Fanspage Support

Sistem sekarang sudah mendukung multiple fanspages dengan interval posting yang bisa diatur per fanspage.

## Fitur Baru

✅ **Multi-Fanspage**: Posting ke beberapa fanspage sekaligus
✅ **Custom Interval**: Setiap fanspage bisa punya interval posting sendiri (misal: Page A = 2 jam, Page B = 4 jam)
✅ **Enable/Disable**: Aktifkan atau nonaktifkan fanspage tanpa menghapus konfigurasi
✅ **Independent Tracking**: Setiap fanspage ditrack terpisah untuk waktu posting terakhir

## Struktur Config Baru

```json
{
  "gemini_api_key": "YOUR_API_KEY",
  "fanspages": [
    {
      "name": "Gold Page 1",
      "page_id": "PAGE_ID_1",
      "access_token": "TOKEN_1",
      "interval_hours": 3,
      "enabled": true
    },
    {
      "name": "Gold Page 2",
      "page_id": "PAGE_ID_2",
      "access_token": "TOKEN_2",
      "interval_hours": 6,
      "enabled": true
    }
  ]
}
```

## Cara Menggunakan

### 1. Manage Fanspages (CLI Tool)
```bash
python3 manage_fanspages.py
```

Menu:
- List fanspages: Lihat semua fanspage yang dikonfigurasi
- Add fanspage: Tambah fanspage baru
- Toggle enable/disable: Aktifkan/nonaktifkan fanspage
- Edit interval: Ubah interval posting per fanspage

### 2. Jalankan Auto Poster
```bash
./run.sh
```

Sistem akan:
- Cek semua fanspage yang enabled
- Cek apakah interval sudah tercapai untuk masing-masing page
- Post hanya ke page yang sudah waktunya
- Track waktu posting terakhir per page

## Database Schema Update

Tabel `posts` sekarang menyimpan:
- `page_id`: ID fanspage
- `page_name`: Nama fanspage
- Semua field lainnya tetap sama

Tabel baru `last_post_time`:
- `page_id`: ID fanspage (primary key)
- `last_posted`: Timestamp posting terakhir

## Backward Compatibility

Config lama (single fanspage) masih didukung dan otomatis dikonversi ke format baru saat aplikasi dijalankan.

## Contoh Output

```
[2026-02-22 18:51:00] Starting auto-post process...
Found 3 fanspage(s) configured

📄 Processing: Gold Page 1
   Page ID: 123456789
   Interval: 3 hours
   Gold price: Rp 1,050,000
   Generating content...
   Generating poster...
   Posting to Facebook...
   ✅ Success! Post ID: 123456789_987654321

⏰ Skipping Gold Page 2 (interval not reached)

📄 Processing: Gold Page 3
   Page ID: 987654321
   Interval: 6 hours
   ...
   ✅ Success! Post ID: 987654321_123456789

[2026-02-22 18:51:30] Process completed.
```
