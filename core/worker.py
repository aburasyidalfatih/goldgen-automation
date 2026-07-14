import sys
import os
from apscheduler.schedulers.background import BackgroundScheduler
import pytz
import logging
from datetime import datetime

# Setup basic logging for the scheduler
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('goldgen_worker')

def job_auto_poster():
    """Tugas untuk menjalankan auto_poster.py"""
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
    try:
        logger.info("[WORKER] Memulai rutinitas Auto Reply Comments...")
        from auto_reply_comments import CommentReplier
        
        # Pengecekan Lock file
        import fcntl
        lock_file = open('data/replier.lock', 'w')
        try:
            fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except IOError:
            logger.info("⏳ [WORKER] Another auto_reply_comments instance is running. Exiting.")
            return
            
        replier = CommentReplier()
        replier.process_comments()
        logger.info("[WORKER] Rutinitas Auto Reply Comments selesai.")
        
        # Release lock
        fcntl.flock(lock_file, fcntl.LOCK_UN)
        lock_file.close()
    except ImportError:
        # Fallback Windows
        try:
            import msvcrt
            lock_file = open('data/replier.lock', 'w')
            try:
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
            except IOError:
                logger.info("⏳ [WORKER] Another auto_reply_comments instance is running. Exiting.")
                return
            
            replier = CommentReplier()
            replier.process_comments()
            logger.info("[WORKER] Rutinitas Auto Reply Comments selesai.")
            
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
            lock_file.close()
        except Exception as e2:
            logger.error(f"[WORKER] Error Windows Lock: {e2}")
    except Exception as e:
        logger.error(f"[WORKER] Error pada Auto Reply Comments: {e}", exc_info=True)

def start_worker():
    """Memulai Internal Job Worker (Background Scheduler)"""
    scheduler = BackgroundScheduler(timezone=pytz.timezone('Asia/Jakarta'))
    
    # 1. Auto Poster (Setiap 15 Menit: 0, 15, 30, 45)
    scheduler.add_job(job_auto_poster, 'cron', minute='*/15', id='auto_poster_job')
    
    # 2. Auto Reply (Setiap 10 Menit: 0, 10, 20, 30, 40, 50)
    scheduler.add_job(job_auto_replier, 'cron', minute='*/10', id='auto_reply_job')
    
    scheduler.start()
    logger.info("✅ [WORKER] Internal Job Worker (APScheduler) berhasil dinyalakan!")

if __name__ == '__main__':
    # Uji coba langsung dari command line (berguna untuk testing lokal)
    print("Menjalankan worker di foreground...")
    from apscheduler.schedulers.blocking import BlockingScheduler
    
    scheduler = BlockingScheduler(timezone=pytz.timezone('Asia/Jakarta'))
    scheduler.add_job(job_auto_poster, 'cron', minute='*/1') # Tes tiap 1 menit
    scheduler.start()
