"""Publication checks shared by automatic and on-demand AI generation."""
import math
import re

# Limited reference context, not a claim that all generated geology is verified.
FACT_CONTEXT = '''Reference: USGS Gold, https://pubs.usgs.gov/gip/prospect1/goldgip.html
Placer gold is concentrated by gravity after erosion of source rock. Stream gold
can accumulate near bedrock. Magnetite is common in black sands alongside other
heavy minerals. These general observations do not identify a deposit at a specific site.
Reference: USGS Prospecting for Gold,
https://pubs.usgs.gov/gip/prospect2/prospectgip.html
Panning separates gold from stream silt, sand and gravel; prospecting success is uncertain.
Editorial limits: More black sand alone does not establish greater gold yield.
One or two pans do not establish a pay streak or economic viability. Recommend
further comparable sampling, not immediate excavation based on black sand alone.
Do not depict entering deep or fast-moving water as a routine prospecting step.
'''


class ContentQualityError(ValueError):
    pass


def valid_score(value):
    if isinstance(value, bool):
        return None
    try:
        score = float(value)
        return score if math.isfinite(score) and 1 <= score <= 10 else None
    except (TypeError, ValueError):
        return None


def caption_issues(caption, review, requested_hook):
    issues = []
    score = valid_score(review.get('score'))
    if score is None or score < 7:
        issues.append('caption belum mencapai skor kualitas 7/10')
    # Missing structured checks must not silently approve a failed reviewer.
    if review.get('factual_issues') != []:
        issues.append('klaim faktual belum lolos pemeriksaan: ' + str(review.get('factual_issues'))[:300])
    if str(review.get('hook_type') or '').lower() != (requested_hook or '').lower():
        issues.append('gaya pembuka tidak sesuai pilihan pembelajaran')
    if len(caption) < 100 or len(caption) > 1400:
        issues.append('panjang caption harus 100–1400 karakter')
    if re.search(r'\b\d+(?:\.\d+)?\s*(?:%|percent\b|times\b)|\b(?:retirement fund|mortgage payment)\b', caption, re.I):
        issues.append('hapus statistik hasil atau janji kekayaan yang tidak terverifikasi')
    if re.search(r"\b(?:I|we)[’']?ll\s+(?:reveal|check|announce)|\b(?:reveal|answer)\b.{0,45}\b(?:later|tomorrow|tonight)\b", caption, re.I):
        issues.append('jangan menjanjikan tindak lanjut yang belum dijadwalkan')
    if re.search(r"found the pay\s?streak|signal to start digging|waist.deep.{0,35}(?:rushing|creek|river)", caption, re.I):
        issues.append('hapus kesimpulan deposit tanpa bukti atau skenario masuk air dalam')
    return issues


def require_publishable(topic):
    if topic.get('caption_approved') is not True:
        raise ContentQualityError('DITAHAN KUALITAS: caption belum lolos pemeriksaan')
    score = valid_score(topic.get('image_score'))
    if score is None or score < 7:
        raise ContentQualityError('DITAHAN KUALITAS: gambar belum lolos pemeriksaan 7/10')
