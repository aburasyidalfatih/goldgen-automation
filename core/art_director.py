"""Turn a complete GoldGen prompt into a compact, safe art-direction layer."""

import json
import re


MAX_LABELS = 4


def _short_text(value, limit):
    return " ".join(str(value or "").split())[:limit]


def parse_art_direction(raw):
    """Validate Gemini's JSON and keep only bounded visual instructions."""
    text = str(raw or "").strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except (TypeError, ValueError):
        return None

    fields = {
        "focal_subject": _short_text(data.get("focal_subject"), 180),
        "composition_adjustment": _short_text(data.get("composition_adjustment"), 300),
        "palette_and_contrast": _short_text(data.get("palette_and_contrast"), 180),
        "avoid": _short_text(data.get("avoid"), 220),
    }
    labels = []
    for value in data.get("label_plan", []) if isinstance(data.get("label_plan"), list) else []:
        label = _short_text(value, 36)
        if label and len(label.split()) <= 3 and label.lower() not in {v.lower() for v in labels}:
            labels.append(label)
        if len(labels) >= MAX_LABELS:
            break
    fields["label_plan"] = labels

    if not fields["focal_subject"] or not fields["composition_adjustment"]:
        return None
    return fields


def render_art_direction(raw):
    plan = parse_art_direction(raw)
    if not plan:
        return None
    labels = ", ".join(f'"{label}"' for label in plan["label_plan"]) or "use the existing approved labels"
    return f"""
AI ART DIRECTOR — execution refinement only; the approved topic and facts above remain authoritative:
- DOMINANT FOCAL SUBJECT: {plan['focal_subject']}
- COMPOSITION REFINEMENT: {plan['composition_adjustment']}
- PALETTE AND PHONE CONTRAST: {plan['palette_and_contrast'] or 'follow the selected layout with strong mobile contrast'}
- SHORT LABEL PLAN: {labels}
- VISUAL CLUTTER / ERRORS TO AVOID: {plan['avoid'] or 'long text, decorative clutter, and unsupported details'}
Do not introduce new facts, quantities, claims, or extra text.
"""
