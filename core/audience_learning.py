"""Recent, page-isolated observational evidence; not a causal audience model."""
import math
from datetime import datetime, timezone

WINDOW_DAYS = 60
HALF_LIFE_DAYS = 14
MIN_EFFECTIVE_SAMPLES = 5


def add_view_outcomes(rows):
    """Compare views only to earlier 48h observations of the same page.

    Views can independently reward distribution; low engagement cannot cancel
    that reward. Missing views preserve the existing engagement-only outcome.
    """
    for row in rows:
        row['learning_outcome'] = row.get('rel_engagement')
        stamp = datetime.fromisoformat(row['timestamp'])
        stamp = stamp.replace(tzinfo=timezone.utc) if stamp.tzinfo is None else stamp
        peers = []
        for other in rows:
            date = datetime.fromisoformat(other['timestamp'])
            date = date.replace(tzinfo=timezone.utc) if date.tzinfo is None else date
            if other['page_id'] == row['page_id'] and 0 < (stamp-date).total_seconds() <= 14*86400:
                if other.get('media_views') is not None:
                    peers.append(other['media_views'])
        if row.get('media_views') is not None and len(peers) >= 3 and sum(peers) > 0:
            row['rel_views'] = row['media_views'] / (sum(peers)/len(peers))
            row['learning_outcome'] = max(row.get('rel_engagement') or 0, row['rel_views'])
    return rows


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
            weight = 2 ** (-age / HALF_LIFE_DAYS)
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
              AND julianday(timestamp) BETWEEN julianday('now','-60 days') AND julianday('now')
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
            'objective': 'Nilai terbaik antara interaksi relatif dan tayangan relatif; bukan pendapatan',
            'views_baseline': 'Minimal 3 snapshot terdahulu dalam 14 hari pada Fanspage yang sama',
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
