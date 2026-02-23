# Fanspage Delay Feature

## Overview
Fitur delay 1 jam antar fanspage telah ditambahkan untuk mencegah spam detection oleh Facebook.

## Cara Kerja

### Interval Per Fanspage (Tetap)
- Setiap fanspage tetap memiliki interval posting sendiri (default: 3 jam)
- Interval ini mengatur kapan fanspage tersebut boleh posting lagi

### Delay Antar Fanspage (Baru)
- Ketika script berjalan dan ada multiple fanspages yang siap posting
- Script akan menunggu **1 jam** setelah posting ke fanspage pertama sebelum posting ke fanspage kedua
- Begitu seterusnya untuk fanspage ketiga, keempat, dst

## Contoh Skenario

### Skenario 1: 3 Fanspages
Misalkan Anda punya 3 fanspages (A, B, C) dengan interval 3 jam:

```
Jam 09:00 - Script berjalan
  ├─ 09:00 - Post ke Fanspage A ✅
  ├─ 10:00 - Post ke Fanspage B ✅ (delay 1 jam)
  └─ 11:00 - Post ke Fanspage C ✅ (delay 1 jam)

Jam 12:00 - Script berjalan lagi
  └─ Semua fanspage di-skip (belum 3 jam sejak post terakhir)

Jam 12:00 - Fanspage A sudah 3 jam sejak post terakhir
Jam 13:00 - Fanspage B sudah 3 jam sejak post terakhir
Jam 14:00 - Fanspage C sudah 3 jam sejak post terakhir
```

### Skenario 2: Beberapa Fanspage Disabled
Jika ada fanspage yang disabled atau belum waktunya posting:

```
Jam 09:00 - Script berjalan
  ├─ Fanspage A - Disabled (skip)
  ├─ 09:00 - Post ke Fanspage B ✅
  └─ 10:00 - Post ke Fanspage C ✅ (delay 1 jam dari B)
```

## Keuntungan

1. **Anti-Spam Detection**: Facebook tidak mendeteksi aktivitas posting massal
2. **Natural Posting Pattern**: Pola posting terlihat lebih natural dan organik
3. **Interval Tetap Terjaga**: Setiap fanspage tetap posting sesuai interval yang ditentukan
4. **Flexible**: Delay hanya terjadi saat ada multiple posts dalam satu run

## Konfigurasi

Delay saat ini di-hardcode ke **3600 detik (1 jam)**. 

Jika ingin mengubah delay, edit file `auto_poster.py` baris:
```python
delay_seconds = 3600  # 1 hour
```

Ubah nilai sesuai kebutuhan:
- 1800 = 30 menit
- 3600 = 1 jam (default)
- 7200 = 2 jam

## Testing

Untuk testing tanpa menunggu 1 jam, Anda bisa sementara ubah delay menjadi lebih kecil:
```python
delay_seconds = 60  # 1 menit untuk testing
```

Jangan lupa kembalikan ke 3600 setelah testing!

## Log Output

Saat delay aktif, Anda akan melihat output seperti ini:
```
✅ Success! Post ID: 123456789

⏳ Waiting 1 hour before next fanspage to avoid spam detection...
   Next post at: 10:00:00
```

## Catatan Penting

- Delay **hanya terjadi** jika ada posting yang sukses
- Jika posting gagal, tidak ada delay (langsung ke fanspage berikutnya)
- Delay **tidak terjadi** jika hanya ada 1 fanspage yang aktif
- Script akan otomatis cek apakah masih ada fanspage yang perlu posting sebelum delay
