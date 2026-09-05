"""Non-publishing caption smoke test. No rotation or posting-state updates."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.config import CONFIG_PATH
from goldgen_service import GoldGenService


def main():
    config = json.loads(CONFIG_PATH.read_text(encoding='utf-8'))
    service = GoldGenService(config['gemini_api_key'], config.get('text_model', 'gemini-3.5-flash'))
    failures = 0
    for page in config.get('fanspages', []):
        if not page.get('enabled', True):
            continue
        topic = {'headline': 'READING THE RIVER', 'subtitle': 'Compare small samples before digging',
                 'list_points': ['Compare sediment near an inside bend and bedrock cracks',
                                 'Black sand is an indicator to test, not proof of gold'],
                 'layout': 'CROSS-SECTION CUTAWAY'}
        try:
            caption = service.generate_caption(topic, page['page_id'])
            print(json.dumps({'page': page['name'], 'approved': topic.get('caption_approved'),
                              'score': topic.get('editor_score'), 'hook': topic.get('hook_type'),
                              'caption': caption}, ensure_ascii=False))
        except Exception as exc:
            from core.safe_log import redact
            failures += 1
            print(json.dumps({'page': page['name'], 'error': redact(exc)}, ensure_ascii=False))
    return failures


if __name__ == '__main__':
    raise SystemExit(main())
