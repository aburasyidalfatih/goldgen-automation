"""Discover Page posts created outside GoldGen and register them for learning."""
import json
import logging
from datetime import datetime, timedelta, timezone

import requests

from core.config import CONFIG_PATH
from core.database import get_db_connection, init_db
from core.safe_log import redact

logger = logging.getLogger("goldgen_manual_sync")


def _parse_created(value):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else None
    except (ValueError, TypeError, AttributeError):
        return None


def sync_manual_posts(pages, lookback_hours=72, limit=25):
    """Import newly discovered Page posts, idempotently and page-isolated.

    Only posts belonging to a configured page are queried. Existing fb_post_id
    rows are left untouched, so GoldGen metadata is never overwritten.
    """
    init_db()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
    imported = 0
    checked = 0

    for page in pages:
        if not page.get("enabled", True) or not page.get("page_id") or not page.get("access_token"):
            continue
        try:
            response = requests.get(
                f"https://graph.facebook.com/v18.0/{page['page_id']}/posts",
                params={
                    "access_token": page["access_token"],
                    "fields": "id,message,created_time",
                    "limit": min(max(int(limit), 1), 50),
                }, timeout=30)
            response.raise_for_status()
            payload = response.json()
            if 'error' in payload:
                raise ValueError('Meta rejected Page post discovery')
            rows = payload.get("data", [])
            # Follow cursors only on the fixed Graph endpoint; never forward
            # credentials to a paging URL supplied by the response.
            seen = set()
            for _ in range(9):
                paging = payload.get('paging', {})
                after = paging.get('cursors', {}).get('after')
                if not paging.get('next') or not after or after in seen:
                    break
                if any((_parse_created(p.get('created_time')) or cutoff) < cutoff for p in payload.get('data', [])):
                    break
                seen.add(after)
                response = requests.get(
                    f"https://graph.facebook.com/v18.0/{page['page_id']}/posts",
                    params={'access_token': page['access_token'],
                            'fields': 'id,message,created_time',
                            'limit': min(max(int(limit), 1), 50), 'after': after}, timeout=30)
                response.raise_for_status()
                payload = response.json()
                if 'error' in payload:
                    raise ValueError('Meta rejected Page post pagination')
                rows.extend(payload.get('data', []))
        except Exception as exc:
            logger.warning("Manual post sync gagal untuk %s: %s", page.get("name"), redact(exc))
            continue

        conn = get_db_connection()
        try:
            for post in rows:
                post_id = post.get("id")
                created = _parse_created(post.get("created_time"))
                if not post_id or not created or created < cutoff or created > datetime.now(timezone.utc):
                    continue
                if not post_id.startswith(str(page['page_id']) + '_'):
                    continue
                checked += 1
                content = (post.get("message") or "").strip()
                cur = conn.execute(
                    """INSERT OR IGNORE INTO posts
                    (timestamp,page_name,page_id,content,image_path,fb_post_id,status,source,topic_headline)
                    VALUES (?,?,?,?,?,?,?,?,?)""",
                    (created.astimezone(timezone.utc).isoformat(timespec="seconds"), page.get("name", page["page_id"]),
                     page["page_id"], content, None, post_id, "success", "manual", content[:180] or None),
                )
                if cur.rowcount:
                    imported += 1
            conn.commit()
        finally:
            conn.close()

    logger.info("Manual post sync selesai: checked=%d imported=%d", checked, imported)
    return {"checked": checked, "imported": imported}


def sync_from_config():
    pages = json.loads(CONFIG_PATH.read_text()).get("fanspages", [])
    return sync_manual_posts(pages)


if __name__ == "__main__":
    print(sync_from_config())
