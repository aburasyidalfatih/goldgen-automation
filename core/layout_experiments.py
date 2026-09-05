"""Small randomized-order layout pairs; never automatic winner promotion."""
import copy
import json
import random
import uuid
from datetime import datetime, timezone

from core.database import get_db_connection


def pending(page_id, layouts):
    conn = get_db_connection()
    try:
        plans = conn.execute('''SELECT * FROM layout_experiments WHERE page_id=?
            AND julianday(created_at)>=julianday('now','-7 days')
            ORDER BY created_at DESC''', (page_id,)).fetchall()
        active = {item['name']: item for item in layouts}
        for plan in plans:
            done = {r[0] for r in conn.execute("SELECT experiment_arm FROM posts WHERE experiment_id=? AND page_id=? AND status='success'", (plan['id'],page_id))}
            if {0,1}.issubset(done):
                continue
            payload = json.loads(plan['payload'])
            from core.topic_catalog import allowed, MARKETING
            if not allowed(payload['topic']) or MARKETING.search(payload['topic'].get('approved_caption','')):
                return None
            if any(name not in active for name in payload['layouts']):
                return None  # A retired layout must never be resurrected.
            arm = 1 if 0 in done else 0
            topic = copy.deepcopy(payload['topic'])
            layout = active[payload['layouts'][arm]]
            topic.update(layout=layout['name'], composition=layout['composition'],
                         experiment_id=plan['id'], experiment_arm=arm)
            return topic
    finally:
        conn.close()
    return None


def enroll(page_id, topic, caption, layouts):
    """Every eight successful scheduled opportunities, at most one two-post pair."""
    if not page_id or topic.get('id') is None or topic.get('caption_approved') is not True or topic.get('experimental_topic'):
        return topic
    # A quiz or a procedural caption may require a specific composition.
    excluded = ('QUIZ','GAME','PROCESS','STEP-BY-STEP','BEFORE')
    eligible = [l for l in layouts if not any(k in l['name'].upper() for k in excluded)]
    names = [l['name'] for l in eligible]
    if topic.get('layout') not in names or len(names)<2:
        return topic
    conn = get_db_connection()
    try:
        conn.execute('BEGIN IMMEDIATE')
        count = conn.execute("SELECT count(*) FROM posts WHERE page_id=? AND status='success'", (page_id,)).fetchone()[0]
        recent = conn.execute("SELECT 1 FROM layout_experiments WHERE page_id=? AND julianday(created_at)>julianday('now','-8 days')",(page_id,)).fetchone()
        if count < 8 or count % 8 != 0 or recent:
            return topic
        pair = [topic['layout'], random.choice([n for n in names if n!=topic['layout']])]
        random.shuffle(pair)
        experiment_id = uuid.uuid4().hex
        saved = copy.deepcopy(topic)
        saved['approved_caption'] = caption
        payload = {'topic': saved, 'layouts': pair}
        conn.execute('INSERT INTO layout_experiments VALUES (?,?,?,?)',
                     (experiment_id,page_id,datetime.now(timezone.utc).isoformat(),json.dumps(payload)))
        conn.commit()
        layout = next(l for l in eligible if l['name']==pair[0])
        topic.update(layout=layout['name'],composition=layout['composition'],
                     experiment_id=experiment_id,experiment_arm=0)
        return topic
    finally:
        conn.close()


def report(page_id):
    conn = get_db_connection()
    try:
        plans = conn.execute('''SELECT id,created_at FROM layout_experiments WHERE page_id=?
            AND julianday(created_at)>=julianday('now','-60 days') ORDER BY created_at DESC''',(page_id,)).fetchall()
        result=[]
        for plan in plans:
            rows=conn.execute('''SELECT p.*,e.engagement,e.source FROM posts p
                LEFT JOIN post_engagement e ON e.post_id=p.id
                WHERE p.experiment_id=? AND p.page_id=? AND p.status='success'
                ORDER BY p.experiment_arm''',(plan['id'],page_id)).fetchall()
            item={'id':plan['id'],'status':'menunggu pasangan/data','arms':[]}
            for r in rows:
                item['arms'].append({'layout':r['layout_name'],'post_id':r['id'],
                                     'engagement':r['engagement'] if r['source']=='snapshot48' else None})
            if len(rows)==2 and {r['experiment_arm'] for r in rows}=={0,1}:
                a,b=rows
                ta,tb=datetime.fromisoformat(a['timestamp']),datetime.fromisoformat(b['timestamp'])
                gap=abs((tb-ta).total_seconds())/3600
                local_a,local_b=ta.astimezone(timezone.utc),tb.astimezone(timezone.utc)
                hour_gap=abs((local_a.hour+local_a.minute/60)-(local_b.hour+local_b.minute/60))
                hour_gap=min(hour_gap,24-hour_gap)
                matched=(a['content']==b['content'] and a['topic_id']==b['topic_id']
                         and a['hook_type']==b['hook_type'] and a['layout_name']!=b['layout_name']
                         and 18<=gap<=30 and hour_gap<=1)
                if not matched:
                    item['status']='tidak sebanding: isi/jam/jarak posting berubah'
                elif all(r['source']=='snapshot48' for r in rows):
                    item['status']='pasangan terukur; belum menetapkan pemenang'
            result.append(item)
        return {'pairs':result,'minimum_pairs_for_review':5,
                'note':'Tinjau minimal 5 pasangan untuk perbandingan layout yang sama. Urutan diacak; audiens tidak diacak dan distribusi tetap dapat berbeda.'}
    finally:
        conn.close()
