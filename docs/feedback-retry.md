# Kritik dan pengiriman ulang

Kritik gambar disimpan untuk prompt selanjutnya, tanpa menggambar ulang karena
skor rendah. Caption tetap diperiksa faktanya sebelum gambar dibuat. Enam catatan
terbaru dalam 30 hari dipakai khusus pada Fanspage pemiliknya, sebagai saran bukan
sumber fakta. Kegagalan penyimpanan kritik tidak membatalkan publikasi.

Jika exception terjadi setelah generate, caption dan lokasi file dicatat untuk
retry. File yang dirujuk posting non-success dilindungi dari cleanup otomatis.
Record lama dengan lokasi kosong tidak membuktikan bahwa file sudah terhapus.

Retry memakai klaim atomik status failed -> retrying. Jika hasil kirim tidak pasti,
status tetap retrying dan operator harus memeriksa Facebook; jangan otomatis
mengembalikan ke failed karena bisa menggandakan posting. File retry harus berada
di folder hasil generate. Tombol dinonaktifkan selama pengiriman.

Evaluasi: `python -m scripts.feedback_report PAGE_ID` membandingkan snapshot 48 jam
sebelum/sesudah kritik pertama dalam jendela 30 hari. Ini laporan observasional,
bukan uji kausal atau pengukuran penghasilan. Tayangan tetap menjadi prioritas
pemilihan konten melalui pembelajaran 30 hari yang sudah ada.
