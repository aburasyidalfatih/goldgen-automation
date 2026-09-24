"""Separate reader-facing image copy from catalog drawing instructions."""
import re
from core.content_quality import strip_markdown


def approved_copy(topic, plan):
    from goldgen_service import _visual_labels
    # Curated experimental topics carry illustrator instructions in list_points.
    # Use the planner's short labels, never print those instructions verbatim.
    instruction = re.compile(r'\b(?:do not|don.t|avoid|depict|render|illustrat\w*|schematic|zoom|draw|caption|photograph|show|use a|make the)\b', re.I)
    points = topic.get('image_copy', {}).get('labels')
    if points is None:
        points = plan.get('labels')
    if not points:
        points = [p for p in topic.get('list_points', []) if not instruction.search(str(p))]
    points = [strip_markdown(str(p)).strip() for p in points
              if 0 < len(str(p).split()) <= 8 and not instruction.search(str(p))][:4]
    question = str(plan.get('question') or '')
    if not (8 <= len(question.split()) <= 14 and question.endswith('?')):
        question = ''
    return {'title': _visual_labels(topic),
            'subtitle': strip_markdown(str(topic.get('subtitle') or ''))[:160],
            'labels': points, 'question': question}


def forbidden_claims(prompt, terms):
    """Negated guardrails are allowed; positive claims in any clause are not."""
    hits = []
    for clause in re.split(r'[\n.;!?]|\bbut\b', prompt.lower()):
        for term in terms:
            pos = clause.find(term)
            if pos < 0:
                continue
            before = clause[:pos]
            if re.search(r'\b(?:no|not|never|avoid|without|don.t)\b', before):
                continue
            hits.append(term)
    return sorted(set(hits))
