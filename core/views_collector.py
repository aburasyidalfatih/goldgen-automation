"""Refresh lifetime views independently from fixed-age learning snapshots."""
import requests
from core.database import get_db_connection
from core.safe_log import redact


def collect_views(pages, limit=100):
    result = {'updated': 0, 'failed': 0}
    for page in pages:
        if not page.get('access_token'):
            continue
        conn = get_db_connection()
        try:
            rows = conn.execute('''SELECT DISTINCT p.fb_post_id FROM posts p
                LEFT JOIN post_views_current v ON v.fb_post_id=p.fb_post_id
                WHERE p.page_id=? AND p.status='success' AND p.fb_post_id IS NOT NULL
                  AND julianday(p.timestamp) BETWEEN julianday('now','-30 days') AND julianday('now')
                  AND (v.attempted_at IS NULL OR julianday(v.attempted_at)<julianday('now','-1 hour'))
                ORDER BY v.attempted_at IS NOT NULL,v.attempted_at LIMIT ?''',
                (page['page_id'],limit)).fetchall()
        finally:
            conn.close()
        for row in rows:
            post_id = row['fb_post_id']
            values, error = {}, None
            try:
                response = requests.get(f'https://graph.facebook.com/v18.0/{post_id}/insights',
                    params={'access_token':page['access_token'],'metric':'post_media_view'},timeout=25)
                response.raise_for_status()
                for metric in response.json().get('data',[]):
                    if metric.get('name') == 'post_media_view':
                        value = metric['values'][0]['value']
                        if type(value) is int and value >= 0:
                            values['media_views'] = value
                if 'media_views' not in values:
                    raise ValueError('API tidak memberikan angka tayangan')
            except Exception as exc:
                error = redact(str(exc))[:300]
            conn = get_db_connection()
            try:
                with conn:
                    conn.execute('''INSERT INTO post_views_current(fb_post_id,media_views,fetched_at,attempted_at,error)
                        VALUES (?,?,CASE WHEN ? IS NOT NULL THEN CURRENT_TIMESTAMP END,CURRENT_TIMESTAMP,?)
                        ON CONFLICT(fb_post_id) DO UPDATE SET
                        media_views=COALESCE(excluded.media_views,post_views_current.media_views),
                        fetched_at=COALESCE(excluded.fetched_at,post_views_current.fetched_at),
                        attempted_at=excluded.attempted_at,error=excluded.error''',
                        (post_id,values.get('media_views'),values.get('media_views'),error))
            finally:
                conn.close()
            result['failed' if error else 'updated'] += 1
    return result
