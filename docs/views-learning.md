# Pembelajaran tayangan

`post_media_view` disimpan pada tabel `post_views_current` untuk posting 30 hari
terakhir. Worker memeriksa tiap 30 menit; setiap posting diambil ulang paling
cepat satu jam. Waktu berhasil/percobaan dan alasan gagal dicatat. Kegagalan
mempertahankan nilai terakhir. Peringkat dashboard dan pemilihan konten memakai
tayangan lifetime terkini ini; usia posting berbeda dapat memengaruhi jumlah.

Secara terpisah, `media_views` juga dikumpulkan pada snapshot usia 48–50 jam.
Angka ini adalah total tayangan, bukan orang unik dan bukan pendapatan.
Kegagalan API menghasilkan NULL, bukan nol. Snapshot lama tidak diisi ulang
dengan angka lifetime saat ini karena umur pengukurannya berbeda.

Pemilihan topik, hook, dan layout memakai peringkat tayangan dalam 30 hari terakhir
per Fanspage. Tayangan lifetime tumbuh bersama umur posting, jadi membandingkan
posting 3 jam dengan posting 20 hari membuat setiap pilihan baru tampak kalah.
Karena itu (sejak September 2026):

- posting berumur kurang dari 48 jam belum ikut dinilai;
- bila minimal 5 posting matang punya `views_48h` (tayangan pada usia 48 jam),
  peringkat memakai angka usia setara itu;
- bila belum cukup, tayangan lifetime dipakai, tetapi hanya antar posting yang
  sudah matang.

Interaksi hanya memecahkan seri jika tayangan sama. Peringkat tertinggi mendapat
skor 4. Tidak ada peluruhan skor tayangan di dalam 30 hari. Jika belum ada
tayangan sama sekali, interaksi menjadi fallback. Jika sudah ada, postingan
tanpa tayangan tidak ikut peringkat. Skor kelompok merupakan rata-rata skor
posting. Eksplorasi dan pertimbangan jumlah sampel tetap berjalan sehingga
pemenang tidak selalu diulang. Skor ini bukan prediksi penghasilan.

## Pelajaran visual dan jadwal

- Saran juri gambar (teks, tata letak, warna) dan gaya visual favorit audiens
  kini dikirim langsung ke model gambar sebagai blok "LESSONS FROM THIS PAGE'S
  EARLIER POSTERS", bukan hanya lewat art director.
- Setiap Senin 08:30 WIB worker menukar maksimal satu jam posting per page
  dengan jam yang terbukti lebih baik (minimal 5 posting per jam). Cadangan
  `config.json.backup.*` dibuat sebelum menulis. Matikan dengan
  `"auto_best_hours": false` di `data/config.json`.
