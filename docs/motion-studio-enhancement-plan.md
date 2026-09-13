# Rencana Penyempurnaan Motion Studio

Tanggal: 13 September 2026. Status: rencana, belum diimplementasikan.

## Sasaran produk

Membuat video edukasi GoldGen 30–60 detik, vertikal 1080×1920, dengan animasi 2D/2.5D yang menjelaskan materi, narasi sinkron, subtitle, musik opsional, dan revisi per scene. Render dilakukan sendiri tanpa API video AI. API teks, gambar, dan suara tetap boleh digunakan sesuai konfigurasi; aset unggahan dan narasi rekaman juga didukung. Durasi merupakan target editorial, bukan pemaksaan audio menjadi tepat 60 detik.

Keberhasilan awal: tiga video berbeda selesai dirender, diperiksa visual dan audionya, dapat diedit per scene, dan dapat diunduh melalui UI. Otomatisasi publikasi dan 3D kompleks menjadi pengembangan berikutnya.

## Bukti dari checkout lokal

- `core/motion_renderer.py`: FFmpeg, satu teks per scene; arrow belum dikomposisi, style/transition belum dikonsumsi; SVG diganti latar sederhana; durasi diskalakan ke 60 detik.
- `core/motion_assets.py`: pencocokan filename/tag, belum ada pemilihan berdasarkan kebutuhan setiap scene.
- `motion_worker.py`: manifest dibangun ulang saat render; narasi opsional berupa satu WAV; draft ikut diproses worker.
- `controllers/routes.py`: endpoint render menjalankan daemon thread selain worker terpisah. Klaim job harus dibuat atomik untuk menghindari render ganda.
- `docker-compose.yml`: volume Motion Studio baru dipasang pada worker, belum pada web. Konfigurasi deployment aktual harus diperiksa sebelum migrasi data.
- `core/motion_qa.py`: pemeriksaan teknis dasar, belum membuktikan keterbacaan, isi gambar, atau sinkronisasi.
- `templates/motion_studio.html`: alur masih tombol terpisah dan prompt browser; klaim generasi gambar otomatis belum sesuai worker.

Pemeriksaan ini bukan bukti kondisi produksi atau kualitas MP4 terbaru.

## Keputusan arsitektur

Pertahankan Flask sebagai API, SQLite terpisah untuk Motion Studio, dan worker khusus. Tambahkan renderer Node/Remotion yang dipanggil worker melalui kontrak JSON tervalidasi. Integrasikan React Player hanya pada halaman studio. FFmpeg menangani kebutuhan media dan encoding. Lakukan prototipe dan evaluasi lisensi Remotion sebelum menetapkan dependensi produksi; jangan menganggap semua penggunaan gratis.

Alur: topik → naskah bersumber → storyboard → aset → narasi → timing → preview → render final → QA → ekspor.

AI hanya mengusulkan data scene dari komponen yang diizinkan. Jangan mengeksekusi kode atau command hasil AI. Renderer memakai komponen yang sudah diuji, asset ID terdaftar, font lokal, versi tetap, dan seed tetap. File aset diselesaikan server dari registry, bukan path bebas dari klien.

## Tahap 1 — Fondasi job dan storage

- Periksa lokasi database/aset web dan worker, backup data Motion Studio, lalu satukan mount yang benar tanpa menimpa database salah satu sisi.
- Web hanya memasukkan job ke antrean; hilangkan render thread dari request. Worker hanya mengambil job yang sengaja diantrekan, bukan draft.
- Tambahkan klaim atomik, lease/heartbeat, attempt, timeout, retry terbatas, cancel, serta pemulihan setelah restart.
- Mulai dengan satu render aktif; batasi proses/CPU/memori dan ukur sebelum menaikkan concurrency.
- Gunakan direktori attempt terpisah dan finalisasi output secara atomik. Simpan kegagalan serta progress aktual.
- Perbaiki pesan UI sesuai kemampuan yang benar-benar tersedia.

Lulus jika: klik ganda menghasilkan satu attempt aktif, dua worker tidak memproses job sama, restart dapat pulih, draft tetap draft, hasil worker dapat diakses web, dan pipeline gambar tetap berjalan pada uji integrasi.

## Tahap 2 — Kontrak scene dan bukti kualitas renderer

- Buat manifest berversi: project/revision, ukuran, FPS, bahasa, gaya, scene ID, component type, narration, on-screen text, asset IDs, layers, timing, transition, dan claim/source references.
- Simpan snapshot topik dan manifest tiap revisi. Render harus memakai revisi tersimpan, tidak membangun ulang storyboard diam-diam.
- Prototipe renderer baru dengan tiga komponen: judul, ilustrasi berlapis, dan diagram berlabel.
- Implementasikan panah, masking/reveal, gerak kamera nyata, easing, line wrapping, font sizing, serta area aman teks.
- Buat satu contoh 30–60 detik tentang pengendapan emas di belakang batu. Mulai dengan aset terkurasi agar kualitas renderer dapat dinilai terpisah dari generasi AI.
- Ukur waktu render, peak RAM, ukuran file, dan kesamaan preview dengan ekspor pada lingkungan sasaran.

Lulus jika: seluruh layer terlihat, SVG sesuai aslinya, teks tidak terpotong, gerak membantu penjelasan, dan hasil dapat direproduksi dari manifest yang sama. Putuskan adopsi Remotion setelah prototipe, lisensi, dan benchmark layak.

## Tahap 3 — Narasi, timing, dan audio

- Buat/edit naskah lengkap, pilihan bahasa/suara, serta dengarkan preview sebelum render.
- Generate narasi per scene dengan cache berdasarkan teks, suara, model, dan pengaturan. Sediakan unggahan audio.
- Ukur panjang audio untuk menentukan durasi scene dan jeda; revisi naskah jika melampaui target durasi.
- Subtitle kalimat/frasa mengikuti audio. Highlight per kata hanya jika timestamp alignment tersedia dan lolos pemeriksaan, bukan perkiraan pembagian durasi rata-rata.
- Musik opsional dengan volume turun saat narasi, fade, dan pemeriksaan clipping. Efek suara dikaitkan dengan event scene.

Lulus jika: narasi tidak terpotong, urutan visual sesuai ucapan, caption frasa selaras dalam toleransi target 250 ms pada contoh uji, serta mode tanpa suara dinyatakan jelas. Mengubah satu scene tidak meregenerasi semua narasi.

## Tahap 4 — Storyboard dan aset berbantuan AI

- Gunakan katalog terkurasi sebagai sumber awal. Simpan referensi klaim, tandai klaim tambahan yang membutuhkan verifikasi, dan jangan menciptakan kutipan sumber.
- AI menghasilkan hook, urutan penjelasan, naskah, kebutuhan aset, serta pemilihan komponen melalui schema tervalidasi.
- Lengkapi delapan komponen: judul, annotated image, parallax, penampang, diagram aliran/partikel ilustratif, perbandingan, peta/timeline, dan rangkuman.
- Pilih aset per scene dari registry; tambahkan tag semantik, dimensi, subjek, focal point, asal, lisensi, dan status persetujuan.
- Prioritas aset: internal relevan → SVG/diagram terprogram → unggahan → generasi gambar opsional. Diagram faktual memakai struktur terkontrol; AI gambar terutama untuk ilustrasi.
- Aset hilang memicu kebutuhan perbaikan atau fallback visual yang disengaja, bukan latar gelap diam-diam.
- Preview biaya/pemakaian AI, cache aset, dan regenerasi hanya scene terpilih.

Lulus jika: tiga topik berbeda menghasilkan storyboard relevan dengan variasi komposisi; semua aset terlacak; referensi sesuai klaim; fallback tanpa API gambar tetap dapat menghasilkan video.

## Tahap 5 — Editor Motion Studio

Alur UI: pilih topik → atur durasi/gaya/bahasa → buat storyboard → revisi scene → preview → render final → download.

- Sidebar daftar scene, preview di tengah, panel pengaturan scene di samping; susunan responsif untuk layar kecil.
- Edit narasi dan teks secara terpisah; ganti aset, urutan scene, fokus gambar, dan preset gerak; preview satu scene.
- Tampilkan perkiraan durasi, audio preview, progres job, pesan kegagalan yang dapat ditindaklanjuti, retry, dan cancel.
- Simpan revisi dan tandai render lama ketika proyek diedit. Render memakai revision ID tertentu.
- Sediakan preview resolusi rendah, ekspor MP4 final, SRT, cover, dan caption; tampilkan biaya serta waktu aktual per job.

Lulus jika: pengguna dapat membuat, merevisi, dan mengekspor video melalui UI tanpa mengedit JSON atau memakai prompt browser untuk naskah; hasil preview dan final memakai revisi yang sama.

## Tahap 6 — QA dan kesiapan deployment

- Preflight: schema, aset/font, batas teks, durasi, dan status narasi.
- Post-render: stream, resolusi, FPS, durasi terhadap manifest, audio yang diwajibkan, clipping, file subtitle, serta deteksi frame kosong/gelap yang mempertimbangkan transisi sengaja.
- Ambil frame awal/tengah/akhir setiap scene dan contact sheet. Pemeriksaan manusia menilai keterbacaan, ketepatan diagram, continuity, serta sinkronisasi dengan menonton video penuh.
- Uji tiga materi: pengendapan emas, perbandingan emas/pyrite, dan penampang urat kuarsa. Verifikasi materi sebelum dijadikan contoh.
- Uji teks panjang, aset hilang, SVG, API gagal, restart worker, cancel, render ganda, revisi saat render, dan audio lebih panjang dari target.
- Tambahkan retention/cache cleanup yang tidak menghapus aset aktif atau output yang masih dipakai, observabilitas, dan rollback renderer berdasarkan versi proyek.
- Deployment dilakukan sesudah verifikasi lokal dan otorisasi rilis. Verifikasi image/container, volume, job end-to-end, dan hasil ekspor setelah deployment.
- Audit terpisah jalur publikasi: tombol saat ini menyebut Reels, sedangkan adapter memanggil endpoint videos. Jangan menyatakan publikasi Reels terverifikasi tanpa pemeriksaan integrasi aktual.

Lulus jika: tiga video lolos pemeriksaan penuh, kegagalan dapat dipulihkan, benchmark sesuai kapasitas host yang terukur, dan satu job produksi selesai serta dapat diputar/diunduh. Render sukses tidak otomatis berarti siap dipublikasikan.

## Urutan dan batas milestone

M1: tahap 1 + manifest minimal + prototipe tiga komponen + audio dasar; hasil satu video contoh berkualitas.

M2: narasi lengkap, storyboard AI, delapan komponen, dan editor per scene; hasil tiga video dari UI.

M3: penguatan QA, kapasitas, deployment, dan verifikasi integrasi publikasi yang terpisah.

Estimasi kalender dan kapasitas batch ditetapkan setelah benchmark M1. Jangan menjanjikan render real-time atau biaya nol. 3D kompleks, karakter realistis, editor timeline bebas, dan auto-publish tidak menjadi syarat milestone awal.

## Referensi teknis

- Remotion renderer: https://www.remotion.dev/docs/renderer
- Remotion Player: https://www.remotion.dev/docs/player
- Lisensi Remotion: https://www.remotion.dev/license
- FFmpeg filters: https://ffmpeg.org/ffmpeg-filters.html
