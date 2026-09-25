"""Page-scoped editorial memory linked to later measured outcomes."""
import json
from core.database import get_db_connection
from core.safe_log import redact


def save_feedback(page_id, topic, kind, score, note):
    if not page_id:
        return
    if kind == 'image' and topic.get('visual_feedback'):
        note = json.dumps({'summary': str(note)[:250], 'improvements': topic['visual_feedback']}, ensure_ascii=True)
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


def image_learning_notes(page_id, visual_styles=(), limit=3):
    """Ringkasan pendek pelajaran visual untuk model GAMBAR itu sendiri.

    Sebelumnya kritik juri gambar dan gaya visual favorit audiens hanya masuk ke
    prompt dasar, yang tidak pernah dikirim ke model gambar — hanya dibaca art
    director, dan hilang sama sekali saat rencana art director tidak lolos
    validasi. Yang diteruskan di sini hanya perbaikan tata letak, warna dan
    tipografi; koreksi fakta tetap diurus caption dan gerbang kualitas.
    """
    lines = []
    if page_id:
        conn = None
        try:
            conn = get_db_connection()
            if conn.execute("SELECT 1 FROM sqlite_master WHERE name='content_feedback'").fetchone():
                rows = conn.execute('''SELECT note FROM content_feedback
                    WHERE page_id=? AND kind='image' AND created_at >= datetime('now','-30 days')
                    ORDER BY id DESC LIMIT 12''', (str(page_id),)).fetchall()
                seen = set()
                for row in rows:
                    try:
                        improvements = json.loads(row['note']).get('improvements') or {}
                    except (ValueError, TypeError, AttributeError):
                        continue
                    for category in ('text', 'layout', 'color'):
                        tip = ' '.join(str(improvements.get(category) or '').split())[:160]
                        if tip and tip.lower() not in seen:
                            seen.add(tip.lower())
                            lines.append(f'- {category}: {tip}')
                    if len(lines) >= limit * 2:
                        break
        except Exception:
            pass  # Learning notes are advisory; never block generation.
        finally:
            if conn is not None:
                conn.close()
    lines = lines[:limit * 2]
    styles = [' '.join(str(s).split())[:120] for s in visual_styles if str(s).strip()][:3]
    if styles:
        lines.append('- audience-preferred style, only where it fits the selected layout: '
                     + '; '.join(styles))
    if not lines:
        return ''
    return ('LESSONS FROM THIS PAGE\'S EARLIER POSTERS (visual guidance only, never text to print):\n'
            + '\n'.join(lines))


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
