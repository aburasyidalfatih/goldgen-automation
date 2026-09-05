"""Read-only report of recent evidence and layout experiments."""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.config import CONFIG_PATH
from core.audience_learning import report
from core.layout_experiments import report as experiments

if __name__ == '__main__':
    config = json.loads(CONFIG_PATH.read_text(encoding='utf-8'))
    for page in config.get('fanspages', []):
        if page.get('enabled', True):
            print(json.dumps({'page': page['name'], 'evidence': report(page['page_id']),
                              'experiments': experiments(page['page_id'])}, ensure_ascii=False, indent=2))
