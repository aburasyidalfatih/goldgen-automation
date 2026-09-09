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
            rows = conn.execute('''SELECT DISTINCT p.fb_post_id,p.timestamp FROM posts p
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
            from datetime import datetime, timezone
            stamp = datetime.fromisoformat(row['timestamp'])
            if stamp.tzinfo is None:
                stamp = stamp.replace(tzinfo=timezone.utc)
            age_hours = max(0.0, (datetime.now(timezone.utc) - stamp).total_seconds() / 3600)
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
            # Optional metrics must not invalidate a valid view measurement.
            for metric, key in (('post_total_media_view_unique', 'unique_viewers'),):
                try:
                    response = requests.get(f'https://graph.facebook.com/v18.0/{post_id}/insights',
                        params={'access_token':page['access_token'],'metric':metric}, timeout=25)
                    response.raise_for_status()
                    for item in response.json().get('data', []):
                        if item.get('name') == metric and item.get('values'):
                            value = item['values'][0].get('value')
                            if type(value) is int and value >= 0:
                                values[key] = value
                except Exception:
                    pass
            try:
                response = requests.get(f'https://graph.facebook.com/v18.0/{post_id}',
                    params={'access_token':page['access_token'],'fields':'shares.summary(true)'}, timeout=25)
                response.raise_for_status()
                value = response.json().get('shares', {}).get('summary', {}).get('total_count')
                if type(value) is int and value >= 0:
                    values['shares'] = value
            except Exception:
                pass
            conn = get_db_connection()
            try:
                with conn:
                    conn.execute('''INSERT INTO post_views_current(fb_post_id,media_views,views_24h,views_48h,velocity_per_hour,unique_viewers,shares,fetched_at,attempted_at,error)
                        VALUES (?,?,?,?,?,?,?,CASE WHEN ? IS NOT NULL THEN CURRENT_TIMESTAMP END,CURRENT_TIMESTAMP,?)
                        ON CONFLICT(fb_post_id) DO UPDATE SET
                        media_views=COALESCE(excluded.media_views,post_views_current.media_views),
                        views_24h=COALESCE(post_views_current.views_24h,excluded.views_24h),
                        views_48h=COALESCE(post_views_current.views_48h,excluded.views_48h),
                        velocity_per_hour=COALESCE(excluded.velocity_per_hour,post_views_current.velocity_per_hour),
                        unique_viewers=COALESCE(excluded.unique_viewers,post_views_current.unique_viewers),
                        shares=COALESCE(excluded.shares,post_views_current.shares),
                        fetched_at=COALESCE(excluded.fetched_at,post_views_current.fetched_at),
                        attempted_at=excluded.attempted_at,error=excluded.error''',
                        (post_id,values.get('media_views'),
                         values.get('media_views') if 24 <= age_hours < 30 else None,
                         values.get('media_views') if 48 <= age_hours < 54 else None,
                         (values.get('media_views') / age_hours) if values.get('media_views') is not None and age_hours > 0 else None,
                         values.get('unique_viewers'),values.get('shares'),
                         values.get('media_views'),error))
            finally:
                conn.close()
            result['failed' if error else 'updated'] += 1
    return result
