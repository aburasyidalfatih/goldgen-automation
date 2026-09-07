"""Usage: python -m scripts.feedback_report PAGE_ID"""
import json
import sys
from core.content_feedback import outcome_report

if __name__ == '__main__':
    print(json.dumps(outcome_report(sys.argv[1]), ensure_ascii=False, indent=2))
