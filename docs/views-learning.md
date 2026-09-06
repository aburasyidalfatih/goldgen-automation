# Pembelajaran tayangan

`post_media_view` disimpan sebagai `media_views` pada snapshot usia 48–50 jam.
Angka ini adalah total tayangan, bukan orang unik dan bukan pendapatan.
Kegagalan API menghasilkan NULL, bukan nol. Snapshot lama tidak diisi ulang
dengan angka lifetime saat ini karena umur pengukurannya berbeda.

Pemilihan topik, hook, dan layout memakai nilai terbaik antara interaksi relatif
dan tayangan relatif. Baseline tayangan membutuhkan minimal tiga posting terdahulu
dari Fanspage yang sama dalam 14 hari. Tanpa baseline, interaksi tetap digunakan.
Pembobotan kebaruan dan pembatasan outlier tetap berlaku. Ini merupakan heuristik
untuk menghargai distribusi maupun interaksi, bukan prediksi penghasilan.
