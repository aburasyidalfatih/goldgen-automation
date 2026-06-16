# 🚀 Panduan Migrasi Dokploy - GoldGen Auto Poster

Dokumen ini menjelaskan cara memigrasikan project **GoldGen Auto Poster** ke server baru menggunakan **Dokploy** (Docker Compose Bundle).

---

## 📦 Struktur Bundle Docker Compose

Pastikan file berikut sudah siap sebelum diunggah ke server baru:
1. `Dockerfile`: Mendefinisikan environment runtime Python 3.12-slim.
2. `docker-compose.yml`: Mendefinisikan service `goldgen-bot` dengan port mapping `18794` dan volume persistence.
3. `.dockerignore`: Mencegah data lokal, logs, dan `venv` masuk ke image build.

---

## 🛠️ Langkah-Langkah Deploy di Dokploy

Ada dua cara utama untuk mendeploy project ini di server Dokploy baru Anda:

### Metode A: Deploy Sebagai Dokploy "Compose" (Rekomendasi)
1. Buka dashboard **Dokploy** Anda.
2. Buat **Project** baru, lalu buat **Service** tipe **Compose**.
3. Pada tab **Source**, tempelkan isi dari file `docker-compose.yml` kita:
   ```yaml
   version: '3.8'
   services:
     goldgen-bot:
       build:
         context: .
         dockerfile: Dockerfile
       image: goldgen-automation:latest
       container_name: goldgen-bot
       ports:
         - "18794:18794"
       restart: unless-stopped
       volumes:
         - ./data:/app/data
         - ./generated_images:/app/generated_images
         - ./logs:/app/logs
       environment:
         - PORT=18794
         - HOST=0.0.0.0
         - PYTHONUNBUFFERED=1
   ```
4. Hubungkan ke repository Git Anda atau upload file project sebagai Zip.
5. Klik **Deploy**.

---

## 💾 Persistensi Data (Sangat Penting!)

Karena bot ini menggunakan database SQLite (`data/posts.db`) dan menyimpan data konfigurasi (`data/config.json`) serta poster gambar (`generated_images/`), Anda **wajib** mencadangkan data lama dan memindahkannya ke direktori volume yang dipetakan pada server baru.

### Cara Memindahkan Data Lama ke Server Baru:
1. Dari server lama, zip folder `data` dan `generated_images`:
   ```bash
   cd /home/ubuntu/goldgen-automation
   tar -czvf goldgen_data_backup.tar.gz data/ generated_images/
   ```
2. Transfer file `goldgen_data_backup.tar.gz` ke server baru menggunakan `scp` atau `rsync`.
3. Di server baru (dalam direktori deployment Dokploy Anda), ekstrak file tersebut:
   ```bash
   tar -xzvf goldgen_data_backup.tar.gz
   ```
4. Pastikan file `posts.db` dan `config.json` berada di dalam folder `data/` relatif terhadap folder compose di server baru Anda agar dapat ter-mount dengan benar oleh Docker.

---

## ⏰ Konfigurasi Cron Jobs di Dokploy

Pada deployment server lama, automation berjalan menggunakan crontab OS. Di Dokploy, Anda dapat mengaturnya langsung dari panel GUI Dokploy agar tetap rapi di dalam container.

1. Buka service **goldgen-bot** di dashboard Dokploy Anda.
2. Masuk ke tab **Cron** atau **Schedules**.
3. Tambahkan 2 cron job baru dengan konfigurasi berikut:

### Cron 1: Auto Posting (Setiap 15 Menit)
* **Cron Expression**: `*/15 * * * *`
* **Command**: `python3 auto_poster.py`

### Cron 2: Auto Reply Comments (Setiap 10 Menit)
* **Cron Expression**: `*/10 * * * *`
* **Command**: `python3 auto_reply_comments.py`

*Catatan: Anda tidak perlu masuk ke `venv` atau menggunakan wrapper `run.sh` lagi karena container Docker sudah terisolasi dan berjalan langsung menggunakan Python global di system container.*
