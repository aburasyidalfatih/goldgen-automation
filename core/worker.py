import logging

import pytz
from apscheduler.schedulers.background import BackgroundScheduler

from core.locks import ProcessLock

# Setup basic logging for the scheduler
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('goldgen_worker')

def job_auto_poster():
    """Tugas untuk menjalankan auto_poster.py"""
    with ProcessLock('poster') as lock:
        if not lock.acquired:
            logger.info("⏳ [WORKER] Another auto_poster instance is running. Exiting.")
            return
        try:
            logger.info("[WORKER] Memulai rutinitas Auto Poster...")
            # Kita import di dalam fungsi agar tidak memberatkan memori saat inisialisasi
            from auto_poster import GoldGenAutoPoster
            poster = GoldGenAutoPoster()
            poster.run()
            logger.info("[WORKER] Rutinitas Auto Poster selesai.")
        except Exception as e:
            logger.error(f"[WORKER] Error pada Auto Poster: {e}", exc_info=True)

def job_auto_replier():
    """Tugas untuk menjalankan auto_reply_comments.py"""
    with ProcessLock('replier') as lock:
        if not lock.acquired:
            logger.info("⏳ [WORKER] Another auto_reply_comments instance is running. Exiting.")
            return
        try:
            logger.info("[WORKER] Memulai rutinitas Auto Reply Comments...")
            from auto_reply_comments import CommentReplier
            replier = CommentReplier()
            replier.process_comments()
            logger.info("[WORKER] Rutinitas Auto Reply Comments selesai.")
        except Exception as e:
            logger.error(f"[WORKER] Error pada Auto Reply Comments: {e}", exc_info=True)

def start_worker():
    """Memulai Internal Job Worker (Background Scheduler)"""
    scheduler = BackgroundScheduler(timezone=pytz.timezone('Asia/Jakarta'))

    # Jitter acak agar job tidak selalu berjalan tepat di menit yang sama (pola robotik mudah terdeteksi Meta).
    # APScheduler 'jitter' menggeser waktu eksekusi ±N detik secara acak setiap run.
    # max_instances=1 + coalesce=True mencegah job menumpuk kalau satu siklus berjalan lama
    # (auto_reply bisa memakan beberapa menit karena human-like delay).

    # 1. Auto Poster (Setiap 15 Menit + jitter hingga ±4 menit)
    scheduler.add_job(job_auto_poster, 'cron', minute='*/15', id='auto_poster_job',
                      jitter=240, max_instances=1, coalesce=True, misfire_grace_time=300)

    # 2. Auto Reply (Setiap 10 Menit + jitter hingga ±3 menit)
    scheduler.add_job(job_auto_replier, 'cron', minute='*/10', id='auto_reply_job',
                      jitter=180, max_instances=1, coalesce=True, misfire_grace_time=300)

    scheduler.start()
    logger.info("✅ [WORKER] Internal Job Worker (APScheduler) berhasil dinyalakan! (dengan human-like jitter)")
    return scheduler

if __name__ == '__main__':
    # Uji coba langsung dari command line (berguna untuk testing lokal)
    print("Menjalankan worker di foreground...")
    from apscheduler.schedulers.blocking import BlockingScheduler

    scheduler = BlockingScheduler(timezone=pytz.timezone('Asia/Jakarta'))
    scheduler.add_job(job_auto_poster, 'cron', minute='*/1', max_instances=1, coalesce=True)  # Tes tiap 1 menit
    scheduler.start()
