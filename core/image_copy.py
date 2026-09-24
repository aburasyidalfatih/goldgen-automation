"""Separate reader-facing image copy from catalog drawing instructions."""
import re
from core.content_quality import strip_markdown

# Model gambar yang menulis seluruh tipografi poster, dan juri menjatuhkan skor
# ke 4 begitu SATU kata salah eja. Setiap kata tambahan adalah peluang gagal:
# dengan anggaran lama (subjudul 160 karakter, label 8 kata) poster rata-rata
# memuat 31 kata dan paling banyak 51, sehingga skor 3 menjadi hal biasa.
MAX_LABEL_WORDS = 4
MAX_SUBTITLE_WORDS = 8

# Tingkat kesederhanaan teks. Percobaan ulang menaikkan tingkatnya: gambar yang
# ditolak karena ejaan tidak akan lebih baik bila diminta menulis kata yang sama.
FULL, SIMPLER, MINIMAL = 0, 1, 2


def short_subtitle(text, max_words=MAX_SUBTITLE_WORDS):
    """Subjudul pendek yang utuh, atau kosong bila tidak bisa dipendekkan rapi.

    Memotong di tengah kalimat menghasilkan penggalan yang terbaca rusak, jadi
    yang dipakai hanya klausa pertama yang utuh.
    """
    text = ' '.join(strip_markdown(str(text or '')).split())
    if len(text.split()) <= max_words:
        return text
    for separator in (':', ' — ', ' - ', ';', ',', '.'):
        if separator in text:
            head = text.split(separator)[0].strip()
            if 3 <= len(head.split()) <= max_words:
                return head
    return ''


def approved_copy(topic, plan, level=FULL):
    from goldgen_service import _visual_labels
    # Curated experimental topics carry illustrator instructions in list_points.
    # Use the planner's short labels, never print those instructions verbatim.
    instruction = re.compile(r'\b(?:do not|don.t|avoid|depict|render|illustrat\w*|schematic|zoom|draw|caption|photograph|show|use a|make the)\b', re.I)
    points = topic.get('image_copy', {}).get('labels')
    if points is None:
        points = plan.get('labels')
    if not points:
        points = [p for p in topic.get('list_points', []) if not instruction.search(str(p))]
    label_words = 3 if level >= MINIMAL else MAX_LABEL_WORDS
    label_count = 4 if level == FULL else 3
    points = [strip_markdown(str(p)).strip() for p in points
              if 0 < len(str(p).split()) <= label_words and not instruction.search(str(p))][:label_count]
    question = str(plan.get('question') or '')
    if level > FULL or not (8 <= len(question.split()) <= 14 and question.endswith('?')):
        question = ''
    subtitle = '' if level >= MINIMAL else short_subtitle(topic.get('subtitle'))
    return {'title': _visual_labels(topic), 'subtitle': subtitle,
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
