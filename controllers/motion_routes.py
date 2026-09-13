"""Authenticated Motion Studio API. No render processes run in web requests."""
import hashlib
import json
import uuid
from functools import wraps
from pathlib import Path
from flask import Blueprint, jsonify, request, session, render_template, send_file
from core import motion_studio as storage
from core.motion_projects import project, save_project, queue_job, cancel_job, Conflict, COMPONENTS, STYLES
from core.motion_assets import get_asset, register_asset, search_assets, scan_existing_images, select_assets_for_topic
from core.motion_pipeline import resolved_manifest, media_duration

bp=Blueprint('motion',__name__)

@bp.before_request
def authenticate():
    if not session.get('authenticated'): return jsonify(error='Unauthorized',require_auth=True),401
    if request.method in ('POST','PUT','DELETE'):
        # Browser origins must be same-site; protect cookie-authenticated mutations.
        origin=request.headers.get('Origin')
        if origin and origin.rstrip('/') != request.host_url.rstrip('/'):
            return jsonify(error='Origin tidak diizinkan'),403
        if request.headers.get('Sec-Fetch-Site')=='cross-site':
            return jsonify(error='Cross-site request ditolak'),403

@bp.errorhandler(ValueError)
def invalid(exc): return jsonify(error=str(exc)),409 if isinstance(exc,Conflict) else 400

def public_job(job):
    if not job: return None
    return {k:v for k,v in job.items() if k not in ('lease_token','lease_until','output_path','action_json')}

def asset_public(a):
    return {k:v for k,v in a.items() if k!='source_path'} | {'url':f'/api/motion/assets/{a["id"]}/file'}

def bundle(job_id):
    manifest=project(job_id)
    return {'job':public_job(storage.get_job(job_id)),'manifest':manifest,
            'preview':resolved_manifest(manifest,lambda a:f'/api/motion/assets/{a["id"]}/file')}

@bp.get('/motion-studio')
def studio(): return render_template('motion_studio.html')

@bp.get('/api/motion/catalog')
def catalog(): return jsonify(topics=storage.list_topics(),components=COMPONENTS,styles=STYLES)

@bp.route('/api/motion/jobs',methods=['GET','POST'])
def jobs():
    if request.method=='GET': return jsonify(jobs=[public_job(j) for j in storage.list_jobs(100)])
    data=request.get_json(silent=True) or {}
    try: topic_id=int(data.get('topic_id'))
    except (ValueError,TypeError): raise ValueError('Pilih topik')
    job=storage.create_job(topic_id)
    project(job['id'])
    return jsonify(bundle(job['id'])),201

@bp.route('/api/motion/jobs/<job_id>',methods=['GET','PUT'])
def detail(job_id):
    if not storage.get_job(job_id): return jsonify(error='Project tidak ditemukan'),404
    if request.method=='PUT':
        data=request.get_json(silent=True) or {}
        save_project(job_id,data.get('manifest'),data.get('revision'))
    return jsonify(bundle(job_id))

@bp.get('/api/motion/jobs/<job_id>/revisions')
def revisions(job_id):
    with storage.motion_db(storage.MOTION_DB_PATH) as conn:
        rows=conn.execute('SELECT revision,created_at FROM motion_revisions WHERE job_id=? ORDER BY revision DESC',(job_id,)).fetchall()
    return jsonify(revisions=[{'revision':r[0],'created_at':r[1]} for r in rows])

@bp.post('/api/motion/jobs/<job_id>/restore/<int:revision>')
def restore(job_id,revision):
    job=storage.get_job(job_id)
    if not job: return jsonify(error='Project tidak ditemukan'),404
    save_project(job_id,project(job_id,revision),job['revision'])
    return jsonify(bundle(job_id))

@bp.post('/api/motion/jobs/<job_id>/<action>')
def action(job_id,action):
    if action=='cancel': return jsonify(job=public_job(cancel_job(job_id)))
    if action not in ('render','voiceover','storyboard','image'): return jsonify(error='Aksi tidak dikenal'),404
    options=request.get_json(silent=True) or {}
    if not isinstance(options,dict): raise ValueError('Payload harus objek')
    if options.get('scene_id') and options['scene_id'] not in [s['id'] for s in project(job_id)['scenes']]: raise ValueError('Scene tidak ditemukan')
    return jsonify(job=public_job(queue_job(job_id,action,{k:options[k] for k in ('scene_id','voice') if k in options}))),202

@bp.post('/api/motion/jobs/batch-render')
def batch():
    data=request.get_json(silent=True) or {}
    try: limit=min(20,max(1,int(data.get('limit',10))))
    except (TypeError,ValueError): raise ValueError('Limit tidak valid')
    drafts=[j for j in storage.list_jobs(100) if j['status']=='draft'][:limit]
    jobs=[queue_job(j['id']) for j in drafts]
    return jsonify(queued_count=len(jobs),jobs=[public_job(j) for j in jobs])

@bp.get('/api/motion/assets')
def assets(): return jsonify(assets=[asset_public(a) for a in search_assets(request.args.get('q',''),request.args.get('type'),approved_only=True)])

@bp.post('/api/motion/assets/scan')
def scan():
    from core.config import IMAGES_DIR
    return jsonify(registered_count=len(scan_existing_images(IMAGES_DIR)))

@bp.post('/api/motion/jobs/<job_id>/match-assets')
def match(job_id):
    data=request.get_json(silent=True) or {}
    manifest=project(job_id)
    for s in manifest['scenes']:
        if data.get('scene_id') and data['scene_id']!=s['id']: continue
        selected=select_assets_for_topic({'headline':s['title'],'list_points':[s['text'],s['narration']]})
        images=[a for a in selected if a['asset_type']!='audio']
        if images: s['asset_id']=images[0]['id']
    save_project(job_id,manifest,data.get('revision'))
    return jsonify(bundle(job_id))

@bp.post('/api/motion/assets/upload')
def upload():
    request.max_content_length=25*1024*1024
    file=request.files.get('file')
    if not file: raise ValueError('Pilih file gambar atau audio')
    suffix=Path(file.filename or '').suffix.lower()
    if suffix not in ('.png','.jpg','.jpeg','.webp','.wav','.mp3','.m4a'): raise ValueError('Format tidak didukung')
    raw=file.read(25*1024*1024+1)
    if len(raw)>25*1024*1024: raise ValueError('Maksimum 25 MB')
    key=hashlib.sha256(raw).hexdigest(); path=storage.MOTION_ASSETS_DIR/(key+suffix)
    if suffix in ('.png','.jpg','.jpeg','.webp'):
        import io
        from PIL import Image
        try:
            with Image.open(io.BytesIO(raw)) as im:
                if im.width*im.height>20000000: raise ValueError('Gambar maksimum 20 megapiksel')
                path=path.with_suffix('.png'); im.convert('RGB').save(path)
        except (OSError,Image.DecompressionBombError): raise ValueError('Gambar tidak valid')
        kind='graphic'
    else:
        path.write_bytes(raw)
        try: media_duration(path)
        except ValueError:
            path.unlink(missing_ok=True); raise
        kind='audio'
    aid=register_asset(path,asset_type=kind,tags=(request.form.get('tags','')[:300],),status='approved',
                       license_name=request.form.get('license','User supplied')[:100],origin='upload')
    return jsonify(asset=asset_public(get_asset(aid))),201

@bp.get('/api/motion/assets/<asset_id>/file')
def asset_file(asset_id):
    asset=get_asset(asset_id)
    if not asset or asset['status']!='approved' or not Path(asset['source_path']).is_file(): return jsonify(error='Aset tidak ditemukan'),404
    response=send_file(asset['source_path'],conditional=True)
    response.headers['Content-Security-Policy']="default-src 'none'; sandbox"
    response.headers['X-Content-Type-Options']='nosniff'
    return response

@bp.get('/api/motion/jobs/<job_id>/download')
@bp.get('/api/motion/jobs/<job_id>/preview')
@bp.get('/api/motion/jobs/<job_id>/exports/<kind>')
def export(job_id,kind='video'):
    job=storage.get_job(job_id)
    if not job or not job.get('output_path'): return jsonify(error='Belum ada hasil render'),404
    path=Path(job['output_path']).resolve()
    if not path.is_relative_to(storage.MOTION_RENDERS_DIR.resolve()): return jsonify(error='Path output tidak valid'),400
    names={'video':path.name,'subtitle':'video.srt','cover':'cover.png','contact':'contact-sheet.jpg','caption':'caption.txt','qa':'qa.json','manifest':'video.manifest.json'}
    if kind not in names: return jsonify(error='Ekspor tidak dikenal'),404
    target=path.with_name(names[kind])
    if not target.is_file(): return jsonify(error='File tidak tersedia'),404
    return send_file(target,as_attachment=not request.path.endswith('/preview') and kind not in ('cover','contact'),conditional=True)

@bp.get('/api/motion/readiness')
def readiness():
    import shutil
    from core.motion_tts import _configured_api_key
    ready=bool(shutil.which('node') and shutil.which('ffmpeg') and shutil.which('ffprobe') and (storage.BASE_DIR/'motion_engine/build/index.html').is_file())
    return jsonify(ready_for_local_render=ready,gemini_tts_key_present=bool(_configured_api_key()),manual_export_enabled=True,automatic_publishing_enabled=False)

@bp.post('/api/motion/jobs/<job_id>/publish')
def publish(job_id):
    # Preserve existing manual publisher but never imply that /videos is a verified Reels API.
    from core.config import CONFIG_PATH
    from core.motion_publisher import publish_video
    job=storage.get_job(job_id)
    if not job or job['status']!='ready' or job['render_revision']!=job['revision']:
        raise Conflict('Render revisi terbaru sebelum publikasi')
    data=request.get_json(silent=True) or {}
    config=json.loads(CONFIG_PATH.read_text('utf8')) if CONFIG_PATH.is_file() else {}
    page=next((p for p in config.get('fanspages',[]) if str(p.get('page_id'))==str(data.get('page_id'))),None)
    if not page: raise ValueError('Fanspage tidak ditemukan')
    if data.get('reviewed') is not True: raise ValueError('Tinjau video sebelum publikasi')
    result=publish_video(page['page_id'],page['access_token'],job['output_path'],str(data.get('caption') or project(job_id)['caption']),manual=True)
    return jsonify(result=result)
