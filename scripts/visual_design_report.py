"""Run: python -m scripts.visual_design_report PAGE_ID (read-only report)."""
import argparse
import json
from core.visual_plan import design_report

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('page_id')
    args = parser.parse_args()
    print(json.dumps(design_report(args.page_id), indent=2, ensure_ascii=False))
