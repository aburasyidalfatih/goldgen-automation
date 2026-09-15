"""Bounded image copy and page-scoped, equal-age design evidence."""
import json
import re
import statistics
from core.database import get_db_connection

BUDGETS = {'light': (4, 3), 'medium': (4, 5), 'detail': (4, 8)}
CATEGORIES = ('text', 'layout', 'color', 'facts', 'question')


def safe_trim_words(text, max_chars=120):
    """Trim string to word boundary within max_chars, never breaking words."""
    text = str(text or '').strip()
    if len(text) <= max_chars:
        return text
    trimmed = text[:max_chars]
    if ' ' in trimmed:
        trimmed = trimmed.rsplit(' ', 1)[0]
    return trimmed.rstrip('.,;:!- ')


def fallback_plan(topic):
    from goldgen_service import _visual_labels
    return {'title': _visual_labels(topic), 'labels': [],
            'subtitle': safe_trim_words(topic.get('subtitle', '') or '', 120),
            'question': 'Which detail here matches what you have seen in the field?',
            'question_type': 'experience', 'density': 'light',
            'selection_reason': 'Planner unavailable or invalid; conservative text fallback',
            'layout': topic.get('layout', ''), 'art_direction_used': False}


def parse_plan(raw, topic):
    try:
        data = json.loads(raw)
        if not isinstance(data, dict) or data.get('density') not in BUDGETS:
            return None
        def valid(text, low, high):
            return (isinstance(text, str) and text.isascii() and
                    low <= len(text.split()) <= high and
                    not re.search(r'[\n\r<>]|https?://', text))
        if not valid(data.get('title'), 1, 6):
            return None
        q = data.get('question')
        if not valid(q, 8, 14) or not q.endswith('?') or q.count('?') != 1:
            return None
        if re.search(r'\b(like|share|tag|vote|guaranteed)\b', q, re.I):
            return None
        labels = data.get('labels')
        count, words = BUDGETS[data['density']]
        if not isinstance(labels, list) or len(labels) > count:
            return None
        if any(not valid(label, 1, words) for label in labels):
            return None
        if len(set(label.lower() for label in labels)) != len(labels):
            return None
        if data.get('question_type') not in ('experience', 'sampling_choice', 'interpretation'):
            return None
        # AI checks semantics; deterministic validation only checks the contract.
        if data.get('caption_consistent') is not True:
            return None
        return {k: data[k] for k in ('title', 'labels', 'question', 'question_type', 'density')} | {
            'subtitle': safe_trim_words(topic.get('subtitle', '') or '', 120),
            'layout': topic.get('layout', ''), 'art_direction_used': True,
            'selection_reason': str(data.get('selection_reason', 'Topic-guided'))[:300]}
    except (ValueError, TypeError, AttributeError):
        return None


def render_plan(prompt, plan):
    # Replace conflicting legacy text limits, not just append an override.
    start = prompt.index('TEXT ALLOWED IN THE IMAGE')
    end = prompt.index('LAYOUT STYLE:', start)
    copy = {k: plan[k] for k in ('title', 'labels', 'question')}
    prompt = prompt[:start] + ('FINAL IMAGE COPY (render exactly; never invent or rewrite text):\n'
        + json.dumps(copy, ensure_ascii=True) + '\nDensity: ' + plan['density']
        + '. Keep text phone-readable, with generous space. Put the question in a compact bottom box '
          'clear of the diagram and watermark. Do not repeat it.\n\n') + prompt[end:]
    prompt = re.sub(r'- TEXT BUDGET[^\n]*',
        '- TEXT BUDGET: Render only FINAL IMAGE COPY and the requested corner watermark. '
        'No additional text. Do not shrink text to fit; simplify decorative detail instead.', prompt)
    return prompt


def save_plan(page_id, image_path, topic):
    conn = None
    try:
        conn = get_db_connection()
        with conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS visual_decisions (
                page_id TEXT, image_path TEXT, payload TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY(page_id,image_path))''')
            conn.execute('INSERT OR REPLACE INTO visual_decisions(page_id,image_path,payload) VALUES(?,?,?)',
                (str(page_id), str(image_path), json.dumps(topic.get('visual_plan', {}))))
    except Exception:
        pass  # Observability must not block publication.
    finally:
        if conn is not None:
            conn.close()


def design_report(page_id):
    conn = get_db_connection()
    try:
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='visual_decisions'").fetchone():
            return {'status': 'no design records', 'groups': []}
        rows = conn.execute('''SELECT d.payload,v.views_48h FROM visual_decisions d
            JOIN posts p ON p.page_id=d.page_id AND p.image_path=d.image_path
            JOIN post_views_current v ON v.fb_post_id=p.fb_post_id
            WHERE d.page_id=? AND p.status='success' AND v.views_48h IS NOT NULL
            AND julianday(p.timestamp)>=julianday('now','-30 days')''', (str(page_id),)).fetchall()
        groups = {}
        for row in rows:
            try:
                plan = json.loads(row['payload'])
                key = tuple(plan.get(k) for k in ('density', 'question_type', 'layout', 'art_direction_used'))
                groups.setdefault(key, []).append(row['views_48h'])
            except (ValueError, TypeError):
                continue
        return {'window': '30 days; measured 48-hour views only',
                'note': 'Observational, not causal; fewer than 5 samples is insufficient.',
                'groups': [dict(zip(('density', 'question_type', 'layout', 'art_direction_used'), key),
                    samples=len(values), median_views_48h=statistics.median(values),
                    evidence='limited' if len(values)<5 else 'observational') for key, values in groups.items()]}
    finally:
        conn.close()
