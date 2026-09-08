"""Standalone Motion Studio worker.

Run this process separately from api.py/auto-poster. It only handles Motion
Studio jobs and can later be managed by its own Windows service or systemd
unit on the VPS.
"""

import logging
import time

from core.locks import ProcessLock
from core.motion_renderer import default_manifest, render_manifest
from core.motion_assets import select_assets_for_topic
from core.motion_qa import validate_render
from core.motion_studio import get_job, list_jobs, list_topics, update_job, init_motion_storage, MOTION_RENDERS_DIR

logging.basicConfig(level=logging.INFO, format="%(asctime)s - motion-worker - %(levelname)s - %(message)s")
logger = logging.getLogger("motion_worker")


def process_one(job):
    topic = next((item for item in list_topics() if item["id"] == job["topic_id"]), None)
    if not topic:
        update_job(job["id"], status="failed", error_message="Topic tidak ditemukan")
        return
    try:
        update_job(job["id"], status="rendering", progress_percent=12, current_stage="preparing", current_detail="Preparing topic, assets, and scene plan", scene_current=0, scene_total=6, error_message=None)
        # Voice-over bersifat opsional dan dibuat lewat endpoint terpisah.
        # Kalau belum ada, video tetap dirender tanpa suara — tapi itu harus
        # terlihat pada hasilnya, bukan diam-diam.
        audio_path = MOTION_RENDERS_DIR / f'{job["id"]}.wav'
        ada_suara = audio_path.is_file()
        update_job(job["id"], progress_percent=22, current_stage="assets", current_detail="Matching approved internal assets")
        manifest = default_manifest(topic, select_assets_for_topic(topic))
        update_job(job["id"], progress_percent=32, current_stage="voiceover",
                   current_detail="Voice-over ditemukan" if ada_suara else "Tanpa voice-over (belum dibuat)")
        def report(scene_current, scene_total, stage, detail):
            percent = 35 + round((scene_current / max(scene_total, 1)) * 50)
            update_job(job["id"], progress_percent=percent, current_stage=stage, current_detail=detail, scene_current=scene_current, scene_total=scene_total)
        result = render_manifest(job["id"], manifest, audio_path=audio_path, progress_callback=report)
        update_job(job["id"], progress_percent=92, current_stage="quality_check",
                   current_detail="Memeriksa video, subtitle, format potret"
                                  + (", dan audio" if ada_suara else ""))
        qa = validate_render(result["output_path"], result["manifest_path"], expect_audio=ada_suara)
        if not qa["ok"]:
            update_job(job["id"], status="failed", output_path=result["output_path"], error_message="; ".join(qa["errors"]))
            return
        update_job(job["id"], status="ready", progress_percent=100, current_stage="complete",
                   current_detail="Video siap" + ("" if qa.get("has_audio") else " (tanpa suara)"),
                   output_path=result["output_path"])
        logger.info("Motion job %s siap", job["id"])
    except Exception as exc:
        update_job(job["id"], status="failed", current_stage="failed", current_detail="Motion job failed", error_message=f"{type(exc).__name__}: {exc}")
        logger.exception("Motion job %s gagal", job["id"])


def run_once():
    init_motion_storage()
    with ProcessLock("motion-render") as lock:
        if not lock.acquired:
            logger.info("Worker Motion Studio lain sedang berjalan")
            return
        pending = [job for job in list_jobs(100) if job["status"] in {"draft", "queued"}]
        if pending:
            process_one(pending[0])


if __name__ == "__main__":
    while True:
        run_once()
        time.sleep(15)
