"""Versioned projects and a single, leased work queue on Motion Studio SQLite."""
import copy
import json
import math
import re
import time
import uuid
from contextlib import contextmanager

from core import motion_studio as storage

COMPONENTS = ('title', 'annotated', 'parallax', 'cutaway', 'flow', 'comparison', 'timeline', 'summary')
STYLES = ('field-journal', 'midnight', 'blueprint')
ACTIVE = ('queued', 'rendering')

class Conflict(ValueError):
    pass

@contextmanager
def transaction():
    with storage.motion_db(storage.MOTION_DB_PATH) as conn:
        conn.row_factory = __import__('sqlite3').Row
        conn.execute('PRAGMA busy_timeout=10000')
        conn.execute('BEGIN IMMEDIATE')
        yield conn

def init_projects():
    with storage.motion_db(storage.MOTION_DB_PATH) as conn:
        columns = {r[1] for r in conn.execute('PRAGMA table_info(motion_jobs)')}
        for key, definition in {
            'revision': 'INTEGER NOT NULL DEFAULT 0', 'render_revision': 'INTEGER',
            'action': "TEXT NOT NULL DEFAULT 'render'", 'action_json': "TEXT NOT NULL DEFAULT '{}'",
            'lease_token': 'TEXT', 'lease_until': 'REAL', 'attempt': 'INTEGER NOT NULL DEFAULT 0',
            'cancel_requested': 'INTEGER NOT NULL DEFAULT 0', 'qa_json': 'TEXT',
            'started_at': 'REAL', 'elapsed_seconds': 'REAL',
        }.items():
            if key not in columns:
                conn.execute(f'ALTER TABLE motion_jobs ADD COLUMN {key} {definition}')
        conn.execute('''CREATE TABLE IF NOT EXISTS motion_revisions (
            job_id TEXT NOT NULL, revision INTEGER NOT NULL, manifest_json TEXT NOT NULL,
            created_at REAL NOT NULL, PRIMARY KEY(job_id, revision))''')
        conn.execute('''CREATE TABLE IF NOT EXISTS motion_attempts (
            token TEXT PRIMARY KEY, job_id TEXT NOT NULL, revision INTEGER NOT NULL,
            action TEXT NOT NULL, started_at REAL NOT NULL, ended_at REAL, status TEXT,
            output_path TEXT, error TEXT)''')
        conn.execute('CREATE INDEX IF NOT EXISTS motion_queue ON motion_jobs(status, created_at)')

def _text(value, limit, label):
    if not isinstance(value, str) or len(value) > limit:
        raise ValueError(f'{label}: maksimum {limit} karakter')
    return value.strip()

def validate_manifest(raw):
    if not isinstance(raw, dict) or raw.get('version') != 2:
        raise ValueError('Manifest versi 2 diperlukan')
    scenes = raw.get('scenes')
    if not isinstance(scenes, list) or not 1 <= len(scenes) <= 12:
        raise ValueError('Gunakan 1–12 scene')
    out = {'version': 2, 'width': 1080, 'height': 1920, 'fps': 30,
           'title': _text(raw.get('title', ''), 160, 'Judul'),
           'language': raw.get('language', 'en'), 'style': raw.get('style', 'field-journal'),
           'target_duration': raw.get('target_duration', 60), 'scenes': [],
           'music_asset_id': raw.get('music_asset_id') or None,
           'caption': _text(raw.get('caption', ''), 2200, 'Caption'),
           'source_url': _text(raw.get('source_url', ''), 1000, 'Sumber')}
    if out['language'] not in ('en', 'id') or out['style'] not in STYLES:
        raise ValueError('Bahasa atau gaya tidak dikenal')
    if type(out['target_duration']) not in (int, float) or not 10 <= out['target_duration'] <= 120:
        raise ValueError('Target durasi 10–120 detik')
    ids = set()
    for i, s in enumerate(scenes):
        if not isinstance(s, dict):
            raise ValueError('Scene harus berupa objek')
        sid = str(s.get('id', ''))
        if not re.fullmatch(r'[a-zA-Z0-9_-]{1,48}', sid) or sid in ids:
            raise ValueError('ID scene harus unik dan valid')
        ids.add(sid)
        component = s.get('component', 'annotated')
        seconds = s.get('duration', 6)
        if component not in COMPONENTS or type(seconds) not in (float, int) or not math.isfinite(seconds) or not 1 <= seconds <= 45:
            raise ValueError('Komponen atau durasi scene tidak valid (1–45 detik)')
        labels = s.get('labels', [])
        if not isinstance(labels, list) or len(labels) > 4:
            raise ValueError('Maksimum empat label per scene')
        scene = {'id': sid, 'component': component, 'duration': round(seconds * 30) / 30,
                 'title': _text(s.get('title', ''), 120, 'Judul scene'),
                 'text': _text(s.get('text', ''), 280, 'Teks scene'),
                 'narration': _text(s.get('narration', ''), 1200, 'Narasi'),
                 'labels': [_text(x, 65, 'Label') for x in labels],
                 'asset_id': s.get('asset_id') or None, 'audio_asset_id': s.get('audio_asset_id') or None,
                 'motion': s.get('motion', 'push-in'), 'transition': s.get('transition', 'fade'),
                 'source_note': _text(s.get('source_note', ''), 1000, 'Catatan sumber'),
                 'verified': s.get('verified') is True,
                 'diagram': s.get('diagram', 'quartz-vein'),
                 'focal_x': s.get('focal_x', 50), 'focal_y': s.get('focal_y', 50)}
        if scene['motion'] not in ('push-in', 'glide', 'float', 'hold') or scene['transition'] not in ('fade', 'push', 'cut'):
            raise ValueError('Gerakan atau transisi tidak dikenal')
        if scene['diagram'] not in ('quartz-vein','river-bed'):
            raise ValueError('Jenis penampang tidak dikenal')
        for key in ('focal_x', 'focal_y'):
            if type(scene[key]) not in (int, float) or not 0 <= scene[key] <= 100:
                raise ValueError('Fokus gambar harus 0–100')
        out['scenes'].append(scene)
    if sum(s['duration'] for s in out['scenes']) > 180:
        raise ValueError('Durasi total maksimum 180 detik')
    from core.motion_assets import get_asset
    for asset_id, audio in [(out['music_asset_id'], True)] + [(s[k], k == 'audio_asset_id') for s in out['scenes'] for k in ('asset_id', 'audio_asset_id')]:
        if asset_id:
            if not isinstance(asset_id, str):
                raise ValueError('Asset ID tidak valid')
            asset = get_asset(asset_id)
            if not asset or asset['status'] != 'approved':
                raise ValueError('Aset belum tersedia/disetujui')
            if (asset['asset_type'] == 'audio') != audio:
                raise ValueError('Jenis aset tidak sesuai')
    return out

def initial_manifest(topic):
    points = topic.get('list_points') or [topic.get('subtitle') or topic['headline']]
    title = str(topic.get('headline', 'GoldGen'))[:120]
    scenes = [{'id': 'hook', 'component': 'title', 'title': title, 'text': str(topic.get('subtitle') or '')[:280], 'narration': title}]
    for i, point in enumerate(points[:5]):
        scenes.append({'id': f'fact-{i+1}', 'component': 'annotated', 'title': f'{i+1:02d} / Field notes',
                       'text': str(point)[:280], 'narration': str(point)[:1200]})
    scenes.append({'id': 'outro', 'component': 'summary', 'title': 'Observe. Test. Compare.',
                   'text': 'Save these field notes for your next trip.', 'narration': 'Observe, test, and compare.'})
    for s in scenes:
        s['duration'] = 60 / len(scenes)
        s['source_note'] = str(topic.get('reference_url') or '')
    return validate_manifest({'version': 2, 'title': title, 'scenes': scenes,
                              'source_url': str(topic.get('reference_url') or ''), 'caption': title + '\n\n#GoldProspecting #Geology #GoldGen'})

def project(job_id, revision=None):
    job = storage.get_job(job_id)
    if not job:
        raise ValueError('Project tidak ditemukan')
    rev = revision if revision is not None else job['revision']
    with storage.motion_db(storage.MOTION_DB_PATH) as conn:
        row = conn.execute('SELECT manifest_json FROM motion_revisions WHERE job_id=? AND revision=?', (job_id, rev)).fetchone()
    if row:
        return json.loads(row[0])
    if revision is not None:
        raise ValueError('Revisi tidak ditemukan')
    topic = next((x for x in storage.list_topics() if x['id'] == job['topic_id']), {'headline': job['topic_headline']})
    manifest = initial_manifest(topic)
    try:
        save_project(job_id, manifest, job['revision'])
    except Conflict:
        pass
    return project(job_id)

def save_project(job_id, manifest, expected_revision, token=None):
    clean = validate_manifest(manifest)
    with transaction() as conn:
        job = conn.execute('SELECT * FROM motion_jobs WHERE id=?', (job_id,)).fetchone()
        if not job:
            raise ValueError('Project tidak ditemukan')
        if job['revision'] != expected_revision:
            raise Conflict('Revisi berubah. Muat ulang sebelum menyimpan.')
        if job['status'] in ACTIVE and (not token or job['lease_token'] != token or job['cancel_requested']):
            raise Conflict('Tunggu proses selesai atau batalkan dahulu.')
        # Editing narration invalidates audio so a prior recording cannot silently survive.
        previous = conn.execute('SELECT manifest_json FROM motion_revisions WHERE job_id=? AND revision=?', (job_id, expected_revision)).fetchone()
        if previous and not token:
            prior = {s['id']: s for s in json.loads(previous[0])['scenes']}
            for scene in clean['scenes']:
                old = prior.get(scene['id'])
                if old and old['narration'] != scene['narration'] and old.get('audio_asset_id') == scene.get('audio_asset_id'):
                    scene['audio_asset_id'] = None
        revision = expected_revision + 1
        conn.execute('INSERT INTO motion_revisions VALUES (?,?,?,?)', (job_id, revision, json.dumps(clean, ensure_ascii=False), time.time()))
        conn.execute('UPDATE motion_jobs SET revision=?, updated_at=? WHERE id=?', (revision, storage.datetime.now(storage.timezone.utc).isoformat(), job_id))
    return revision

def queue_job(job_id, action='render', options=None):
    if action not in ('render', 'voiceover', 'storyboard', 'image'):
        raise ValueError('Aksi tidak dikenal')
    project(job_id)
    with transaction() as conn:
        job = conn.execute('SELECT * FROM motion_jobs WHERE id=?', (job_id,)).fetchone()
        if job['status'] in ACTIVE:
            return dict(job)
        conn.execute("""UPDATE motion_jobs SET status='queued', action=?, action_json=?, attempt=0,
            cancel_requested=0, lease_token=NULL, lease_until=NULL, progress_percent=0,
            current_stage='queued', current_detail='Menunggu worker', error_message=NULL WHERE id=?""",
            (action, json.dumps(options or {}), job_id))
    return storage.get_job(job_id)

def claim_job(lease_seconds=60):
    now = time.time()
    with transaction() as conn:
        expired = conn.execute("SELECT * FROM motion_jobs WHERE status='rendering' AND coalesce(lease_until,0)<?", (now,)).fetchall()
        for job in expired:
            status = 'cancelled' if job['cancel_requested'] else ('failed' if job['attempt'] >= 3 else 'queued')
            conn.execute('UPDATE motion_attempts SET ended_at=?, status=?, error=? WHERE token=?', (now, 'expired', 'Worker lease expired', job['lease_token']))
            conn.execute('UPDATE motion_jobs SET status=?, lease_token=NULL, lease_until=NULL, error_message=? WHERE id=?', (status, 'Worker terhenti; antrean dipulihkan', job['id']))
        if conn.execute("SELECT 1 FROM motion_jobs WHERE status='rendering'").fetchone():
            return None
        row = conn.execute("SELECT * FROM motion_jobs WHERE status='queued' ORDER BY created_at ASC LIMIT 1").fetchone()
        if not row:
            return None
        token = uuid.uuid4().hex
        conn.execute("UPDATE motion_jobs SET status='rendering', lease_token=?, lease_until=?, started_at=?, attempt=attempt+1, current_stage=action WHERE id=?", (token, now+lease_seconds, now, row['id']))
        conn.execute('INSERT INTO motion_attempts(token,job_id,revision,action,started_at,status) VALUES(?,?,?,?,?,?)', (token, row['id'], row['revision'], row['action'], now, 'running'))
        return dict(conn.execute('SELECT * FROM motion_jobs WHERE id=?', (row['id'],)).fetchone())

def heartbeat(job_id, token):
    with transaction() as conn:
        row = conn.execute("SELECT cancel_requested FROM motion_jobs WHERE id=? AND lease_token=? AND status='rendering'", (job_id, token)).fetchone()
        if not row or row[0]:
            return False
        conn.execute('UPDATE motion_jobs SET lease_until=? WHERE id=? AND lease_token=?', (time.time()+60, job_id, token))
    return True

def progress(job_id, token, percent, detail):
    with transaction() as conn:
        conn.execute('UPDATE motion_jobs SET progress_percent=?, current_detail=? WHERE id=? AND lease_token=?', (max(0, min(99, int(percent))), detail[:240], job_id, token))

def finish(job_id, token, status, output=None, qa=None, error=None, revision=None):
    with transaction() as conn:
        job = conn.execute('SELECT * FROM motion_jobs WHERE id=? AND lease_token=?', (job_id, token)).fetchone()
        if not job:
            return False
        if job['cancel_requested']:
            status, output = 'cancelled', None
        now = time.time()
        conn.execute('UPDATE motion_attempts SET ended_at=?,status=?,output_path=?,error=? WHERE token=?', (now,status,output,error,token))
        conn.execute('''UPDATE motion_jobs SET status=?, current_stage=?, current_detail=?, progress_percent=?,
            lease_token=NULL, lease_until=NULL, elapsed_seconds=?, error_message=?,
            output_path=coalesce(?,output_path), render_revision=coalesce(?,render_revision),
            qa_json=coalesce(?,qa_json) WHERE id=?''',
            (status,status,'Selesai' if status in ('ready','draft') else (error or status),100 if status in ('ready','draft') else 0,
             now-job['started_at'],error,output,revision if output else None,json.dumps(qa) if qa else None,job_id))
    return True

def cancel_job(job_id):
    with transaction() as conn:
        conn.execute("UPDATE motion_jobs SET cancel_requested=1, status=CASE WHEN status='queued' THEN 'cancelled' ELSE status END WHERE id=? AND status IN ('queued','rendering')", (job_id,))
    return storage.get_job(job_id)
