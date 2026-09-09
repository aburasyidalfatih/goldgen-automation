"""Recent, page-isolated observational evidence; not a causal audience model."""
import math
from datetime import datetime, timezone

WINDOW_DAYS = 30
HALF_LIFE_DAYS = 14
MIN_EFFECTIVE_SAMPLES = 5
# A page should have a meaningful local history before portfolio priors stop
# influencing selection. This is intentionally higher than the report minimum.
MIN_LOCAL_SAMPLES_FOR_AUTONOMY = 15


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
        # Lifetime views remain the primary signal.  Early velocity is the
        # secondary signal so a fast-rising post wins ties without allowing a
        # small early spike to outrank a proven high-view post.
        keys = sorted({(
            r['media_views'],
            round(float(r.get('velocity_per_hour') or 0.0), 2),
            r.get('engagement') or 0
        ) for r in measured})
        scores = {key: 1 + 3*(i+1)/len(keys) for i,key in enumerate(keys)}
        for row in members:
            row['views_ranked'] = bool(measured)
            # Unmeasured posts cannot outrank measured winners on likes alone.
            row['learning_outcome'] = (
                scores[(row['media_views'], round(float(row.get('velocity_per_hour') or 0.0), 2), row.get('engagement') or 0)]
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
            SELECT p.*,v.media_views,v.views_24h,v.views_48h,v.velocity_per_hour,v.unique_viewers,v.shares,v.fetched_at,
                   COALESCE(ec.likes+ec.comments,e.engagement) AS engagement,
                   e.rel_engagement
            FROM posts p
            LEFT JOIN post_views_current v ON v.fb_post_id=p.fb_post_id
            LEFT JOIN engagement_cache ec ON ec.fb_post_id=p.fb_post_id
            LEFT JOIN post_engagement e ON e.post_id=p.id
            WHERE p.page_id=? AND p.status='success'
              AND julianday(p.timestamp) BETWEEN julianday('now','-30 days') AND julianday('now')
        ''', (page_id,))])
    finally:
        conn.close()


def performance(page_id, field, normalize=None):
    local_rows = page_rows(page_id)
    groups = {}
    for row in local_rows:
        key = row.get(field)
        key = normalize(key) if normalize else key
        if key is not None and key != '':
            groups.setdefault(key, []).append(row)
    result = {key: summarize(rows) for key, rows in groups.items()}

    # Cold start: borrow a deliberately weak prior from the same GoldGen
    # portfolio until this page has enough measured evidence of its own.
    if sum(1 for row in local_rows if row.get('learning_outcome') is not None) < MIN_LOCAL_SAMPLES_FOR_AUTONOMY:
        from core.database import get_db_connection
        conn = get_db_connection()
        try:
            shared_rows = add_view_outcomes([dict(r) for r in conn.execute('''
                SELECT p.*,v.media_views,v.views_24h,v.views_48h,v.velocity_per_hour,v.unique_viewers,v.shares,v.fetched_at,
                       COALESCE(ec.likes+ec.comments,e.engagement) AS engagement,
                       e.rel_engagement
                FROM posts p
                LEFT JOIN post_views_current v ON v.fb_post_id=p.fb_post_id
                LEFT JOIN engagement_cache ec ON ec.fb_post_id=p.fb_post_id
                LEFT JOIN post_engagement e ON e.post_id=p.id
                WHERE p.status='success'
                  AND julianday(p.timestamp) BETWEEN julianday('now','-30 days') AND julianday('now')
            ''')])
        finally:
            conn.close()
        borrowed = {}
        for row in shared_rows:
            if row.get('page_id') == page_id:
                continue
            key = row.get(field)
            key = normalize(key) if normalize else key
            if key is not None and key != '':
                borrowed.setdefault(key, []).append(row)
        for key, rows in borrowed.items():
            remote = summarize(rows)
            local = result.get(key)
            if not local:
                result[key] = dict(remote, evidence='cold-start portfolio')
                result[key]['effective_n'] = round(remote['effective_n'] * 0.35, 3)
            else:
                weight = min(0.35, 0.35 * remote['effective_n'] / max(MIN_EFFECTIVE_SAMPLES, remote['effective_n']))
                total = local['effective_n'] + remote['effective_n'] * weight
                local['avg'] = (local['avg'] * local['effective_n'] + remote['avg'] * remote['effective_n'] * weight) / max(total, 1e-9)
                local['effective_n'] = total
                local['evidence'] = 'local + cold-start portfolio'
    return result


def report(page_id):
    from comment_analyzer import normalize_hook
    return {'window_days': WINDOW_DAYS, 'half_life_days': HALF_LIFE_DAYS,
            'minimum_effective_samples': MIN_EFFECTIVE_SAMPLES,
            'objective': 'Peringkat tayangan 30 hari; interaksi hanya pembeda jika tayangan sama',
            'views_baseline': 'Tayangan lifetime terkini untuk posting 30 hari per Fanspage; usia posting berbeda',
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
