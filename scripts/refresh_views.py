"""Refresh current lifetime views without generating or publishing content."""
import json
from core.config import CONFIG_PATH
from core.database import init_db
from core.views_collector import collect_views
from core.locks import ProcessLock

if __name__ == '__main__':
    with ProcessLock('current_views') as lock:
        if not lock.acquired:
            raise SystemExit('Collection already running')
        init_db()
        print(collect_views(json.loads(CONFIG_PATH.read_text()).get('fanspages', [])))
