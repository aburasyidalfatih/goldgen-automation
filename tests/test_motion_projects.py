"""Behavior tests for durable queue, revisions, API and scene timing."""
import copy
import io
import json
import threading
import time
import wave
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import pytest
from flask import Flask
from core import motion_studio as storage
from core import motion_assets as assets
from core.motion_projects import (project,save_project,queue_job,claim_job,heartbeat,finish,cancel_job,validate_manifest,Conflict)

@pytest.fixture
def isolated(tmp_path,monkeypatch):
    for key,name in [('MOTION_DATA_DIR','data'),('MOTION_ASSETS_DIR','assets'),('MOTION_RENDERS_DIR','renders')]:
        monkeypatch.setattr(storage,key,tmp_path/name)
    monkeypatch.setattr(storage,'MOTION_DB_PATH',tmp_path/'data/jobs.db')
    monkeypatch.setattr(assets,'MOTION_ASSETS_DIR',tmp_path/'assets')
    monkeypatch.setattr(assets,'ASSET_DB_PATH',tmp_path/'data/assets.db')
    monkeypatch.setattr(storage,'list_topics',lambda:[{'id':1,'headline':'River gold','list_points':['Dense gold may settle in stream sediment.']}])
    storage.init_motion_storage()
    job=storage.create_job(1); manifest=project(job['id'])
    return job['id'],manifest

def test_draft_is_not_rendered(isolated):
    assert claim_job() is None

def test_duplicate_clicks_only_one_claim(isolated):
    jid,_=isolated
    queue_job(jid);queue_job(jid)
    with ThreadPoolExecutor(max_workers=4) as pool:
        claims=list(pool.map(lambda _:claim_job(),range(4)))
    assert sum(c is not None for c in claims)==1
    assert storage.get_job(jid)['attempt']==1

def test_global_single_render_and_next_job(isolated):
    jid,_=isolated
    second=storage.create_job(1)['id'];queue_job(jid);queue_job(second)
    first=claim_job();assert claim_job() is None
    finish(first['id'],first['lease_token'],'ready')
    assert claim_job()['id']==second

def test_stale_revision_cannot_overwrite(isolated):
    jid,m=isolated
    old=copy.deepcopy(m);m['scenes'][0]['text']='Changed'
    save_project(jid,m,1)
    with pytest.raises(Conflict):save_project(jid,old,1)
    assert project(jid)['scenes'][0]['text']=='Changed'
    assert project(jid,1)==old

def test_edits_blocked_during_render(isolated):
    jid,m=isolated;queue_job(jid)
    with pytest.raises(Conflict):save_project(jid,m,1)

def test_cancel_blocks_completion(isolated):
    jid,_=isolated;queue_job(jid);claim=claim_job();cancel_job(jid)
    assert not heartbeat(jid,claim['lease_token'])
    finish(jid,claim['lease_token'],'ready',output='bad.mp4',revision=1)
    assert storage.get_job(jid)['status']=='cancelled'
    assert storage.get_job(jid)['output_path'] is None

def test_lease_recovery_rejects_old_worker(isolated):
    jid,_=isolated;queue_job(jid);old=claim_job(lease_seconds=-1);new=claim_job()
    assert old['lease_token']!=new['lease_token']
    assert not heartbeat(jid,old['lease_token'])
    assert not finish(jid,old['lease_token'],'ready',output='old.mp4')

def test_lease_retries_are_bounded(isolated):
    jid,_=isolated;queue_job(jid)
    for _ in range(3):assert claim_job(lease_seconds=-1)
    assert claim_job() is None
    assert storage.get_job(jid)['status']=='failed'

@pytest.mark.parametrize('value',[float('nan'),float('inf'),0,99,'8'])
def test_bad_duration_rejected(isolated,value):
    _,m=isolated;m['scenes'][0]['duration']=value
    with pytest.raises(ValueError):validate_manifest(m)

def test_unregistered_asset_and_unknown_component_rejected(isolated):
    _,m=isolated;m['scenes'][0]['asset_id']='../../secret'
    with pytest.raises(ValueError):validate_manifest(m)
    m['scenes'][0]['asset_id']=None;m['scenes'][0]['component']='execute-code'
    with pytest.raises(ValueError):validate_manifest(m)

def audio(tmp_path,seconds=1):
    path=tmp_path/'speech.wav'
    with wave.open(str(path),'wb') as f:
        f.setnchannels(1);f.setsampwidth(2);f.setframerate(24000);f.writeframes(b'\0\0'*int(seconds*24000))
    return assets.register_asset(path,asset_type='audio',status='approved')

def test_narration_edit_invalidates_previous_audio(isolated,tmp_path):
    jid,m=isolated;m['scenes'][0]['audio_asset_id']=audio(tmp_path)
    save_project(jid,m,1);m['scenes'][0]['narration']='A different sentence.'
    save_project(jid,m,2)
    assert project(jid)['scenes'][0]['audio_asset_id'] is None

def test_voice_cache_measures_phrase_timing(isolated,tmp_path,monkeypatch):
    from core.motion_pipeline import generate_speech
    import core.motion_tts as tts
    calls=[]
    def fake(job_id,text,voice):
        calls.append(text);path=storage.MOTION_RENDERS_DIR/f'{job_id}.wav';path.parent.mkdir(parents=True,exist_ok=True)
        with wave.open(str(path),'wb') as f:
            f.setnchannels(1);f.setsampwidth(2);f.setframerate(24000);f.writeframes(b'\0\0'*24000)
    monkeypatch.setattr(tts,'generate_voiceover',fake)
    _,m=isolated;m['scenes'][0]['narration']='First sentence. Second sentence.'
    result=generate_speech(m,{'scene_id':'hook'},threading.Event(),lambda *a:None)
    generate_speech(m,{'scene_id':'hook'},threading.Event(),lambda *a:None)
    assert len(calls)==2
    a=assets.get_asset(result['scenes'][0]['audio_asset_id'])
    captions=json.loads(Path(a['source_path']).with_suffix('.captions.json').read_text())
    assert captions[1]['start']==1.15
    assert captions[1]['end']==2.15
    assert result['scenes'][0]['duration']==pytest.approx(2.6666667)

@pytest.fixture
def client(isolated):
    from controllers.motion_routes import bp
    app=Flask(__name__);app.secret_key='test-only';app.register_blueprint(bp)
    client=app.test_client()
    with client.session_transaction() as sess:sess['authenticated']=True
    return client

def test_api_queues_without_starting_threads(client,isolated,monkeypatch):
    jid,_=isolated
    monkeypatch.setattr(threading.Thread,'start',lambda self:pytest.fail('Request spawned worker'))
    assert client.post(f'/api/motion/jobs/{jid}/render',json={}).status_code==202
    assert storage.get_job(jid)['status']=='queued'

def test_auth_and_cross_origin(client,isolated):
    jid,_=isolated
    assert client.post(f'/api/motion/jobs/{jid}/render',json={},headers={'Origin':'https://evil.example'}).status_code==403
    with client.session_transaction() as sess:sess.clear()
    assert client.get('/api/motion/jobs').status_code==401

def test_api_does_not_expose_paths_or_lease(client,isolated):
    jid,_=isolated;queue_job(jid);claim_job()
    result=client.get('/api/motion/jobs').json['jobs'][0]
    assert 'output_path' not in result and 'lease_token' not in result

def test_batch_limit_is_respected(client,isolated):
    for _ in range(3):storage.create_job(1)
    result=client.post('/api/motion/jobs/batch-render',json={'limit':1})
    assert result.status_code==200
    assert len([j for j in storage.list_jobs() if j['status']=='queued'])==1

def test_upload_rejects_svg_script(client):
    response=client.post('/api/motion/assets/upload',data={'file':(io.BytesIO(b'<svg><script/></svg>'),'evil.svg')})
    assert response.status_code==400

def test_previous_output_is_kept_on_failure(isolated):
    jid,_=isolated;queue_job(jid);j=claim_job();finish(jid,j['lease_token'],'ready',output='old.mp4',revision=1)
    queue_job(jid);j=claim_job();finish(jid,j['lease_token'],'failed',error='Encoder failed')
    assert storage.get_job(jid)['output_path']=='old.mp4'

def test_process_cancellation(isolated):
    import sys
    from core.motion_pipeline import run_process,Cancelled
    event=threading.Event();event.set()
    with pytest.raises(Cancelled):run_process([sys.executable,'-c','import time;time.sleep(30)'],cancel=event)
