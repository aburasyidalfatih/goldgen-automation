# Pembelajaran tayangan

`post_media_view` disimpan sebagai `media_views` pada snapshot usia 48–50 jam.
Angka ini adalah total tayangan, bukan orang unik dan bukan pendapatan.
Kegagalan API menghasilkan NULL, bukan nol. Snapshot lama tidak diisi ulang
dengan angka lifetime saat ini karena umur pengukurannya berbeda.

Pemilihan topik, hook, dan layout memakai peringkat tayangan dalam 30 hari terakhir
per Fanspage. Interaksi hanya memecahkan seri jika tayangan sama. Peringkat
tertinggi mendapat skor 4. Tidak ada peluruhan skor tayangan di dalam 30 hari.
Jika belum ada tayangan sama sekali, interaksi menjadi fallback. Jika sudah ada,
postingan tanpa tayangan tidak ikut peringkat. Skor kelompok merupakan rata-rata
skor posting. Eksplorasi dan pertimbangan jumlah sampel tetap berjalan sehingga
pemenang tidak selalu diulang. Skor ini bukan prediksi penghasilan.
