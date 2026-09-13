"""Single leased Motion worker. Requests enqueue; drafts are never rendered."""
import json
import logging
import threading
import time
from core import motion_studio as storage
from core.motion_projects import claim_job, project, heartbeat, progress, finish, save_project
from core.motion_pipeline import render_project, generate_speech, generate_storyboard, generate_scene_image, Cancelled
logger=logging.getLogger('motion-worker')

def process_one(job):
    token=job.get('lease_token')
    if not token:
        raise ValueError('Worker must atomically claim a queued job first')
    cancel=threading.Event(); done=threading.Event()
    def pulse():
        while not done.is_set():
            try:
                if not heartbeat(job['id'],token): cancel.set(); return
            except Exception:
                cancel.set(); return
            done.wait(5)
    thread=threading.Thread(target=pulse,daemon=True); thread.start()
    report=lambda p,d: progress(job['id'],token,p,d)
    try:
        manifest=project(job['id'],job['revision'])
        options=json.loads(job['action_json'])
        if job['action']=='render':
            folder=storage.MOTION_RENDERS_DIR/job['id']/token
            output,qa=render_project(manifest,folder,cancel,report)
            finish(job['id'],token,'ready',output=output,qa=qa,revision=job['revision'])
        else:
            if job['action']=='voiceover': manifest=generate_speech(manifest,options,cancel,report)
            elif job['action']=='storyboard': manifest=generate_storyboard(manifest,cancel)
            elif job['action']=='image': manifest=generate_scene_image(manifest,options,cancel)
            save_project(job['id'],manifest,job['revision'],token=token)
            finish(job['id'],token,'draft')
    except Exception as exc:
        logger.exception('Motion attempt failed: %s',token)
        finish(job['id'],token,'cancelled' if isinstance(exc,Cancelled) else 'failed',error=str(exc)[:1500])
    finally:
        done.set(); thread.join(timeout=6)

def run_once():
    storage.init_motion_storage()
    job=claim_job()
    if job: process_one(job)

if __name__=='__main__':
    logging.basicConfig(level=logging.INFO)
    while True:
        run_once()
        time.sleep(2)
