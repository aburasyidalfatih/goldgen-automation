"""Conservative page-local text-density guidance from measured manual images."""
import json
import statistics
from core.database import get_db_connection


def density_guidance(page_id):
    if not page_id:
        return ''
    conn = get_db_connection()
    try:
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='manual_content_analysis'").fetchone():
            return ''
        rows = conn.execute('''SELECT a.payload,v.views_48h FROM posts p
            JOIN manual_content_analysis a ON a.fb_post_id=p.fb_post_id
            JOIN post_views_current v ON v.fb_post_id=p.fb_post_id
            WHERE p.page_id=? AND p.status='success'
            AND julianday(p.timestamp) BETWEEN julianday('now','-30 days') AND julianday('now')
            AND v.views_48h IS NOT NULL AND a.analyzed_at IS NOT NULL''', (page_id,)).fetchall()
    finally:
        conn.close()
    groups = {}
    for row in rows:
        try:
            data = json.loads(row['payload'])
            if data.get('confidence',0) < 0.8 or data.get('readability') != 'good':
                continue
            density = data.get('text_density')
            if density in ('low','medium','high'):
                groups.setdefault(density, []).append(row['views_48h'])
        except (ValueError, TypeError):
            continue
    eligible = {k:v for k,v in groups.items() if len(v)>=5}
    if len(eligible)<2:
        return ''
    ranked = sorted(eligible, key=lambda k:statistics.median(eligible[k]), reverse=True)
    winner, runner = ranked[:2]
    if statistics.median(eligible[winner]) <= 1.2*statistics.median(eligible[runner]):
        return ''
    return (f'Page-local observational comparison: readable {winner}-text-density images '
            f'had higher median 48h-window views across {len(eligible[winner])} samples. '
            'Use this only as a weak composition hint, not proof of causation. '
            'Keep all existing label limits and factual safeguards; never add tiny text.')
