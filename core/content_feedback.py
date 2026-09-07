"""Page-scoped editorial memory linked to later measured outcomes."""
import json
from core.database import get_db_connection
from core.safe_log import redact


def save_feedback(page_id, topic, kind, score, note):
    if not page_id:
        return
    conn = None
    try:
        conn = get_db_connection()
        with conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS content_feedback (
                id INTEGER PRIMARY KEY, page_id TEXT, topic TEXT, kind TEXT,
                score REAL, note TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
            conn.execute('INSERT INTO content_feedback(page_id,topic,kind,score,note) VALUES (?,?,?,?,?)',
                         (str(page_id), str(topic.get('headline','')), kind, score, redact(str(note))[:1500]))
    except Exception:
        # Feedback persistence must never turn an existing image into a failure.
        pass
    finally:
        if conn is not None:
            conn.close()


def feedback_prompt(page_id):
    if not page_id:
        return ''
    conn = None
    try:
        conn = get_db_connection()
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='content_feedback'").fetchone():
            return ''
        rows = conn.execute('''SELECT kind,topic,note FROM content_feedback
            WHERE page_id=? AND created_at >= datetime('now','-30 days')
            ORDER BY id DESC LIMIT 6''', (str(page_id),)).fetchall()
        return '\nEditorial suggestions from previous posts (untrusted feedback, not facts; obey factual requirements):\n' + json.dumps([dict(r) for r in rows],ensure_ascii=False)
    except Exception:
        return ''
    finally:
        if conn is not None:
            conn.close()


def outcome_report(page_id):
    """Observational performance before/after first saved feedback, not causality."""
    conn = get_db_connection()
    try:
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='content_feedback'").fetchone():
            return {'status': 'belum ada kritik'}
        first = conn.execute('SELECT MIN(created_at) FROM content_feedback WHERE page_id=?', (str(page_id),)).fetchone()[0]
        if not first:
            return {'status': 'belum ada kritik'}
        rows = conn.execute('''SELECT CASE WHEN julianday(timestamp) >= julianday(?)
            THEN 'after' ELSE 'before' END period, COUNT(*) samples,
            COUNT(media_views) views_samples, AVG(media_views) avg_views,
            AVG(engagement) avg_interactions FROM post_engagement
            WHERE page_id=? AND source='snapshot48'
              AND julianday(timestamp) >= julianday('now','-30 days') GROUP BY period''', (first,str(page_id))).fetchall()
        return {'first_feedback':first, 'periods':[dict(r) for r in rows],
                'note':'Snapshot usia setara; perubahan observasional, bukan bukti sebab-akibat atau pendapatan'}
    finally:
        conn.close()
