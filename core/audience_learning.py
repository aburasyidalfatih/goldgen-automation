"""Recent, page-isolated observational evidence; not a causal audience model."""
import math
from datetime import datetime, timezone

WINDOW_DAYS = 30
HALF_LIFE_DAYS = 14
MIN_EFFECTIVE_SAMPLES = 5


def add_view_outcomes(rows, now=None):
    """Rank comparable posts by views first, interactions only for tied views."""
    now = now or datetime.now(timezone.utc)
    recent = []
    for row in rows:
        stamp = datetime.fromisoformat(row['timestamp'])
        stamp = stamp.replace(tzinfo=timezone.utc) if stamp.tzinfo is None else stamp
        if 0 <= (now-stamp).total_seconds() <= WINDOW_DAYS*86400:
            recent.append(dict(row))
    pages = {row['page_id'] for row in recent}
    for page in pages:
        members = [r for r in recent if r['page_id'] == page]
        measured = [r for r in members if r.get('media_views') is not None]
        keys = sorted({(r['media_views'], r.get('engagement') or 0) for r in measured})
        scores = {key: 1 + 3*(i+1)/len(keys) for i,key in enumerate(keys)}
        for row in members:
            row['views_ranked'] = bool(measured)
            # Unmeasured posts cannot outrank measured winners on likes alone.
            row['learning_outcome'] = (
                scores[(row['media_views'], row.get('engagement') or 0)]
                if row.get('media_views') is not None else
                None if measured else row.get('rel_engagement'))
    return [row for row in recent if row['learning_outcome'] is not None]


def summarize(rows, now=None):
    now = now or datetime.now(timezone.utc)
    values = []
    for row in rows:
        try:
            stamp = datetime.fromisoformat(row['timestamp'])
            if stamp.tzinfo is None:
                stamp = stamp.replace(tzinfo=timezone.utc)
            age = (now - stamp).total_seconds() / 86400
            value = float(row.get('learning_outcome', row.get('rel_engagement')))
            if not 0 <= age <= WINDOW_DAYS or not math.isfinite(value) or value < 0:
                continue
            weight = 1.0 if row.get('views_ranked') else 2 ** (-age / HALF_LIFE_DAYS)
            # Limit single-post outliers; the uncapped outcome remains in the DB.
            values.append((min(value, 4.0), weight))
        except (ValueError, TypeError, KeyError):
            continue
    if not values:
        return {'avg': 0.0, 'n': 0, 'effective_n': 0.0, 'sd': 0.0, 'total': 0.0,
                'evidence': 'belum cukup'}
    mass = sum(w for _, w in values)
    mean = sum(v*w for v, w in values) / mass
    variance = sum(w*(v-mean)**2 for v,w in values) / mass
    return {'avg': mean, 'n': len(values), 'effective_n': mass,
            'sd': math.sqrt(variance), 'total': sum(v*w for v,w in values),
            'evidence': 'terbatas' if mass < MIN_EFFECTIVE_SAMPLES else 'observasional'}


def page_rows(page_id):
    from core.database import get_db_connection
    if not page_id:
        return []
    conn = get_db_connection()
    try:
        return add_view_outcomes([dict(r) for r in conn.execute('''
            SELECT * FROM post_engagement WHERE page_id=? AND source='snapshot48'
              AND julianday(timestamp) BETWEEN julianday('now','-30 days') AND julianday('now')
        ''', (page_id,))])
    finally:
        conn.close()


def performance(page_id, field, normalize=None):
    groups = {}
    for row in page_rows(page_id):
        key = row.get(field)
        key = normalize(key) if normalize else key
        if key is not None and key != '':
            groups.setdefault(key, []).append(row)
    return {key: summarize(rows) for key, rows in groups.items()}


def report(page_id):
    from comment_analyzer import normalize_hook
    return {'window_days': WINDOW_DAYS, 'half_life_days': HALF_LIFE_DAYS,
            'minimum_effective_samples': MIN_EFFECTIVE_SAMPLES,
            'objective': 'Peringkat tayangan 30 hari; interaksi hanya pembeda jika tayangan sama',
            'views_baseline': 'Snapshot 48 jam per Fanspage; tayangan tertinggi mendapat skor 4',
            'interpretation': 'Bukti observasional; bukan bukti sebab-akibat atau ukuran reach',
            'layouts': performance(page_id, 'layout_name'),
            'hooks': performance(page_id, 'hook_type', normalize_hook),
            'topics': performance(page_id, 'topic_headline')}


def update_rankings(items, page_id, field, label, normalize=None):
    """Preserve dashboard fields while using the same recency weights as selection."""
    stats = performance(page_id, field, normalize)
    for item in items:
        data = stats.get(item[label])
        if not data:
            continue
        item['relatif'] = round(data['avg'], 2)
        item['effective_n'] = round(data['effective_n'], 2)
        item['evidence'] = data['evidence']
        # A conservative ranking heuristic, not a calibrated confidence interval.
        item['confident_score'] = round(data['avg']-1.96*max(data['sd'],0.5)/math.sqrt(data['effective_n']),2)
    return sorted(items, key=lambda item: -item['confident_score'])
