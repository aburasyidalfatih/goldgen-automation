import logging
import os

import pytz
from apscheduler.schedulers.background import BackgroundScheduler

from core.locks import ProcessLock
from core.safe_log import capture_output

capture_output()

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

def job_engagement_snapshots():
    with ProcessLock('engagement_snapshots') as lock:
        if not lock.acquired:
            return
        try:
            from comment_analyzer import CommentAnalyzer
            CommentAnalyzer().capture_due_snapshots()
        except Exception as exc:
            from core.safe_log import redact
            logger.error('Snapshot collection failed: %s', redact(exc))


def job_current_views():
    with ProcessLock('current_views') as lock:
        if not lock.acquired:
            return
        try:
            import json
            from core.config import CONFIG_PATH
            from core.views_collector import collect_views
            pages = json.loads(CONFIG_PATH.read_text()).get('fanspages', [])
            logger.info('Current views: %s', collect_views(pages))
        except Exception as exc:
            from core.safe_log import redact
            logger.error('Current views failed: %s', redact(exc))


def job_manual_post_sync():
    """Register Page posts made manually so they can join audience learning."""
    with ProcessLock('manual_post_sync') as lock:
        if not lock.acquired:
            return
        try:
            from core.manual_post_sync import sync_from_config
            logger.info('Manual post sync: %s', sync_from_config())
            import json
            from core.config import CONFIG_PATH
            from core.manual_content_analysis import analyze_manual_content
            analyze_manual_content(json.loads(CONFIG_PATH.read_text()))
        except Exception as exc:
            from core.safe_log import redact
            logger.error('Manual post sync failed: %s', redact(exc))


def job_motion_worker():
    """Tugas untuk menjalankan render antrean Motion Studio di background"""
    with ProcessLock('motion_worker_scheduler') as lock:
        if not lock.acquired:
            return
        try:
            from motion_worker import run_once
            run_once()
        except Exception as exc:
            from core.safe_log import redact
            logger.error('Motion worker failed: %s', redact(exc))



def job_weekly_reflection():
    """Bot membaca datanya sendiri dan melaporkan keraguan. Tidak mengubah apa pun."""
    try:
        from core.reflection import reflect, format_laporan
        temuan = reflect()
        pesan = format_laporan(temuan)
        logger.info("[WORKER] Refleksi mingguan: %d temuan", len(temuan))
        for t in temuan:
            logger.info("[REFLEKSI] %s: %s", t['pemeriksaan'], t['pesan'])
        try:
            from telegram_notifier import send_notification
            send_notification(pesan)
        except Exception as exc:
            logger.warning("[WORKER] Refleksi gagal dikirim ke Telegram: %s", exc)
    except Exception as e:
        logger.error("[WORKER] Error pada Refleksi mingguan: %s", e, exc_info=True)


def job_best_hours():
    """Tukar maksimal satu jam posting per page dengan jam yang terbukti lebih baik.

    Bisa dimatikan lewat "auto_best_hours": false di data/config.json.
    """
    with ProcessLock('best_hours') as lock:
        if not lock.acquired:
            return
        try:
            import json
            from core.config import CONFIG_PATH
            from core.schedule_tuning import apply_best_hours
            if json.loads(CONFIG_PATH.read_text()).get('auto_best_hours', True) is False:
                logger.info('[WORKER] Penyesuaian jam posting otomatis dimatikan')
                return
            for entry in apply_best_hours(CONFIG_PATH):
                if entry['after']:
                    logger.info('[JADWAL] %s: %s (jadwal baru %s)', entry['page'], entry['reason'], entry['after'])
                else:
                    logger.info('[JADWAL] %s: tidak diubah — %s', entry['page'], entry['reason'])
        except Exception as exc:
            from core.safe_log import redact
            logger.error('Best-hours tuning failed: %s', redact(exc))


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

    scheduler.add_job(job_engagement_snapshots, 'cron', minute='*/15',
                      id='engagement_snapshots_job', max_instances=1,
                      coalesce=True, misfire_grace_time=300)
    scheduler.add_job(job_current_views, 'interval', minutes=30,
                      id='current_views_job', max_instances=1, coalesce=True)
    scheduler.add_job(job_manual_post_sync, 'interval', minutes=60,
                      id='manual_post_sync_job', max_instances=1, coalesce=True,
                      misfire_grace_time=300)

    # Refleksi mingguan: Senin 08:00 WIB. Melapor saja, tidak mengubah apa pun.
    # Setiap cacat pengukuran di proyek ini ditemukan manusia yang menyelidiki,
    # dan masing-masing sempat berjalan berminggu-minggu sebelum ketahuan.
    scheduler.add_job(job_weekly_reflection, 'cron', day_of_week='mon', hour=8,
                      id='weekly_reflection_job', max_instances=1, coalesce=True,
                      misfire_grace_time=3600)

    # Setelah refleksi: terapkan jam posting terbaik, satu tukar per page per minggu.
    scheduler.add_job(job_best_hours, 'cron', day_of_week='mon', hour=8, minute=30,
                      id='best_hours_job', max_instances=1, coalesce=True,
                      misfire_grace_time=3600)

    # 6. Motion Studio Worker (Setiap 30 detik memproses antrean video draft/queued)
    # Di docker-compose render dijalankan container goldgen-motion-worker yang
    # dibatasi CPU/RAM. Kalau worker ini juga aktif di container web, render
    # berat bisa jatuh ke container web tanpa batas dan memperlambat dashboard.
    # Set MOTION_EMBEDDED_WORKER=false bila worker terpisah sudah berjalan.
    embedded_motion = os.getenv('MOTION_EMBEDDED_WORKER', 'true').strip().lower() not in ('0', 'false', 'no', 'off')
    if embedded_motion:
        scheduler.add_job(job_motion_worker, 'interval', seconds=30,
                          id='motion_worker_job', max_instances=1, coalesce=True)

    scheduler.start()
    logger.info("✅ [WORKER] Internal Job Worker (APScheduler) berhasil dinyalakan! (Motion Studio worker %s)",
                "internal" if embedded_motion else "di container terpisah")
    return scheduler

if __name__ == '__main__':
    # Uji coba langsung dari command line (berguna untuk testing lokal)
    print("Menjalankan worker di foreground...")
    from apscheduler.schedulers.blocking import BlockingScheduler
    sched = BlockingScheduler(timezone=pytz.timezone('Asia/Jakarta'))
    sched.add_job(job_auto_poster, 'cron', minute='*/1', max_instances=1, coalesce=True)
    sched.start()
