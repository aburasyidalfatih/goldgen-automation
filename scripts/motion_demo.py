"""Isolated, source-backed demo. Never starts the image poster or publishes.

  python scripts/motion_demo.py --prepare
  python scripts/motion_demo.py --render
  python scripts/motion_demo.py --serve
"""
import argparse
import json
import os
from pathlib import Path
import sys
import secrets
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
os.environ['MOTION_STORAGE_DIR']=str(ROOT/'motion_studio/demo')
os.environ.setdefault('SECRET_KEY','motion-demo-isolated-local-session')
if os.name=='nt':
    os.environ.setdefault('MOTION_BROWSER_PATH',r'C:\Program Files\Google\Chrome\Application\chrome.exe')
from core import motion_studio as storage
from core.motion_projects import initial_manifest,project,save_project,queue_job

TOPICS=[
 {'id':90001,'headline':'How rivers concentrate gold','reference_url':'https://pubs.usgs.gov/gip/prospect1/goldgip.html',
  'list_points':['Erosion releases gold from its source rock.','Stream transport redistributes sediment.','Gold can concentrate on or near bedrock.']},
 {'id':90002,'headline':'Gold or fool’s gold?','reference_url':'https://www.usgs.gov/faqs/what-fools-gold',
  'list_points':['Pyrite is often mistaken for gold.','A golden appearance alone does not identify a mineral.','Compare multiple properties before drawing a conclusion.']},
 {'id':90003,'headline':'From rock to river','reference_url':'https://www.usgs.gov/publications/gold-placer-deposits',
  'list_points':['Lode deposits can be a source of placer gold.','Weathering releases gold from its host rock.','Transport and concentration can form placer deposits.']},
]
storage.list_topics=lambda:TOPICS

def prepare():
    storage.init_motion_storage()
    if storage.list_jobs(): return
    components=[['title','flow','cutaway','summary'],['title','comparison','annotated','summary'],['title','cutaway','timeline','summary']]
    for i,topic in enumerate(TOPICS):
        job=storage.create_job(topic['id']);manifest=project(job['id'])
        manifest['style']=['field-journal','midnight','blueprint'][i]
        manifest['scenes']=manifest['scenes'][:4]
        for n,s in enumerate(manifest['scenes']):
            s['component']=components[i][n]
            s['duration']=[6,9,9,6][n]
            s['title']=([topic['headline'],'Follow the water','Look beneath the gravel','Observe. Record. Compare.'] if i==0 else
                        [topic['headline'],'Appearance is a starting point','Look beyond the sparkle','Compare the evidence'] if i==1 else
                        [topic['headline'],'Start with the source','A geological journey','Connect the landscape'])[n]
            s['labels']=(['Gold','Pyrite'] if s['component']=='comparison' else ['Weathering','Transport','Concentration'] if s['component']=='timeline' else [])
            s['source_note']=topic['reference_url']
            s['verified']=True
        save_project(job['id'],manifest,1)
    print('Prepared three isolated demo projects')

def render():
    from motion_worker import run_once
    for job in reversed(storage.list_jobs()):
        queue_job(job['id']);run_once()
        result=storage.get_job(job['id'])
        print(json.dumps({k:result[k] for k in ('id','status','error_message','output_path','elapsed_seconds')},indent=2))

def serve():
    from flask import Flask,session,redirect
    from controllers.motion_routes import bp
    app=Flask(__name__,template_folder=str(ROOT/'templates'),static_folder=str(ROOT/'static'))
    app.secret_key=secrets.token_hex(32);app.register_blueprint(bp)
    token=secrets.token_urlsafe(24)
    @app.get('/demo-start/'+token)
    def start():
        session['authenticated']=True
        return redirect('/motion-studio')
    print('DEMO_URL=http://127.0.0.1:18796/demo-start/'+token,flush=True)
    app.run(host='127.0.0.1',port=18796,use_reloader=False)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--prepare',action='store_true');p.add_argument('--render',action='store_true');p.add_argument('--serve',action='store_true');args=p.parse_args()
    prepare()
    if args.render:render()
    if args.serve:serve()
