"""Durable generation evidence and bounded scheduling; never stores provider bodies."""
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from core.database import get_db_connection
from core.safe_log import redact

UTC = timezone.utc
WIB = timezone(timedelta(hours=7))


def init_schema(conn):
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS generation_events (
            id INTEGER PRIMARY KEY, created_at TEXT NOT NULL, page_id TEXT,
            topic_id TEXT, headline TEXT, layout TEXT, experiment_id TEXT,
            experiment_arm INTEGER, stage TEXT, attempt INTEGER, model TEXT, detail TEXT);
        CREATE TABLE IF NOT EXISTS image_reviews (
            page_id TEXT, image_path TEXT, image_sha TEXT, caption_sha TEXT,
            topic TEXT NOT NULL, updated_at TEXT NOT NULL,
            PRIMARY KEY(page_id,image_path));
        CREATE TABLE IF NOT EXISTS posting_attempts (
            page_id TEXT, slot TEXT, attempts INTEGER NOT NULL DEFAULT 0,
            status TEXT, retry_at TEXT, PRIMARY KEY(page_id,slot));
    ''')


def event(page_id, topic, stage, detail='', attempt=0, model=''):
    topic = topic or {}
    conn = None
    try:
        conn = get_db_connection()
        with conn:
            conn.execute('''INSERT INTO generation_events
                (created_at,page_id,topic_id,headline,layout,experiment_id,experiment_arm,
                 stage,attempt,model,detail) VALUES(?,?,?,?,?,?,?,?,?,?,?)''',
                (datetime.now(UTC).isoformat(), str(page_id or ''), str(topic.get('id', '')),
                 topic.get('headline'), topic.get('layout'), topic.get('experiment_id'),
                 topic.get('experiment_arm'), stage, attempt, model, redact(detail)[:2000]))
    except Exception as exc:
        # Observability must not turn an already generated image into fallback.
        # Captured stderr is the durable alternative when SQLite is unavailable.
        import sys
        print(redact(f'Generation event persistence failed: {exc}; stage={stage}; detail={detail}'), file=sys.stderr)
    finally:
        if conn is not None:
            conn.close()


def digest(value):
    return hashlib.sha256(value).hexdigest()


def save_review(page_id, image_path, caption, topic):
    """Bind a review to the exact page, image bytes and caption being published."""
    path = Path(image_path).resolve()
    conn = get_db_connection()
    try:
        with conn:
            conn.execute('INSERT OR REPLACE INTO image_reviews VALUES(?,?,?,?,?,?)',
                         (str(page_id), str(path), digest(path.read_bytes()),
                          digest(caption.encode()), json.dumps(topic), datetime.now(UTC).isoformat()))
    finally:
        conn.close()


def load_review(page_id, image_path, caption):
    from core.content_quality import ContentQualityError
    path = Path(image_path).resolve()
    conn = get_db_connection()
    try:
        row = conn.execute('SELECT * FROM image_reviews WHERE page_id=? AND image_path=?',
                           (str(page_id), str(path))).fetchone()
        if not row or not path.is_file() or row['image_sha'] != digest(path.read_bytes()) or row['caption_sha'] != digest(caption.encode()):
            raise ContentQualityError('Gambar/caption belum memiliki pemeriksaan yang cocok; generate ulang atau periksa ulang sebelum mengirim.')
        return json.loads(row['topic'])
    finally:
        conn.close()


def claim_slot(page_id, now=None):
    """Atomically lease one scheduled hour; at most three attempts per slot."""
    now = (now or datetime.now(UTC)).astimezone(UTC)
    slot = now.astimezone(WIB).replace(minute=0, second=0, microsecond=0).isoformat()
    conn = get_db_connection()
    try:
        with conn:
            conn.execute('BEGIN IMMEDIATE')
            row = conn.execute('SELECT * FROM posting_attempts WHERE page_id=? AND slot=?', (str(page_id), slot)).fetchone()
            if row and (row['status'] in ('success', 'uncertain') or row['attempts'] >= 3 or datetime.fromisoformat(row['retry_at']) > now):
                return None
            attempts = row['attempts'] + 1 if row else 1
            conn.execute('INSERT OR REPLACE INTO posting_attempts VALUES(?,?,?,?,?)',
                         (str(page_id), slot, attempts, 'running', (now+timedelta(minutes=20)).isoformat()))
        return slot
    finally:
        conn.close()


def finish_slot(page_id, slot, status, now=None):
    now = now or datetime.now(UTC)
    conn = get_db_connection()
    try:
        with conn:
            conn.execute('UPDATE posting_attempts SET status=?,retry_at=? WHERE page_id=? AND slot=?',
                         (status, (now+timedelta(minutes=15)).isoformat(), str(page_id), slot))
    finally:
        conn.close()


def clock_ready():
    """Compare against HTTPS server time, failing closed on a wrong/unknown clock.

    No credentials, generation or publication. A bad host clock must not select
    the wrong schedule or write future timestamps after boot.
    """
    import requests
    from email.utils import parsedate_to_datetime
    for url in ('https://generativelanguage.googleapis.com/', 'https://graph.facebook.com/'):
        try:
            response = requests.head(url, timeout=8, allow_redirects=False)
            remote = parsedate_to_datetime(response.headers['Date'])
            if abs((datetime.now(UTC)-remote).total_seconds()) <= 120:
                return True
        except (requests.RequestException, KeyError, ValueError, TypeError):
            continue
    return False
